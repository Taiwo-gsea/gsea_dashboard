"""
GSEA Dashboard - Database Session Management
=============================================
Async SQLAlchemy engine and session factory.
Supports SQLite (development) and PostgreSQL (production)
via DATABASE_URL environment variable.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from backend.config import settings
from backend.models.database import Base

logger = logging.getLogger(__name__)

# ── Engine ─────────────────────────────────────────────────────────────────
_engine_kwargs = {
    "echo": settings.debug,
}

# SQLite requires special pool config for async use
if "sqlite" in settings.database_url:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = StaticPool

engine = create_async_engine(settings.database_url, **_engine_kwargs)

# ── Session factory ─────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── Dependency (FastAPI) ───────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session per request.
    Automatically commits on success, rolls back on exception.

    Usage in route:
        @app.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Context manager (non-FastAPI usage) ───────────────────────────────────
@asynccontextmanager
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions outside FastAPI.
    Used in scripts, background tasks, and tests.

    Usage:
        async with db_session() as session:
            result = await session.execute(...)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Initialisation ─────────────────────────────────────────────────────────
async def init_db() -> None:
    """
    Create all database tables on startup.
    Safe to call multiple times — only creates missing tables.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialised.")


async def drop_all_tables() -> None:
    """
    Drop all tables. FOR TESTING ONLY.
    Never call this in production.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("All database tables dropped.")
