"""
GSEA Dashboard - Application Configuration
==========================================
Central configuration using Pydantic Settings.
All configuration values are loaded from environment variables
or .env file, with sensible defaults for development.
"""

from pydantic_settings import BaseSettings
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Application
    app_name: str = "GSEA Dashboard"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # Backend API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"

    # Database
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR}/data/gsea.db"

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    allowed_hosts: str = "localhost,127.0.0.1"

    # External APIs
    electricity_maps_api_key: str = ""

    # NLP
    spacy_model: str = "en_core_web_sm"
    hf_model: str = "distilbert-base-uncased"

    # Upload constraints
    max_upload_size_mb: int = 50
    allowed_upload_types: str = "csv,json,xlsx"

    model_config = {
        "env_file": str(BASE_DIR / ".env"),
        "case_sensitive": False,
        "extra": "ignore",  # unrecognised .env vars (e.g. STREAMLIT_PORT, which
                            # Streamlit itself controls via --server.port, not
                            # this settings object) must not crash startup
    }

    @property
    def is_production(self) -> bool:
        import os
        return os.getenv("ENVIRONMENT", "dev").lower() == "production"

    def validate_production_secrets(self) -> None:
        """Fix 12: Raise if default secret key is used in production."""
        if self.is_production and self.secret_key == "dev-secret-key-change-in-production":
            raise ValueError(
                "SECRET_KEY must be changed from the default in production. "
                "Set ENVIRONMENT=production and SECRET_KEY=<secure-value>."
            )


# Singleton instance
settings = Settings()
