"""
GSEA Dashboard - SCI Data Service
====================================
Repository-pattern service layer for persisting and querying
SCI measurements and proxy metric snapshots.

Separates business logic from the route layer, keeping FastAPI
handlers thin and testable.
"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
import logging

from backend.models.database import SCIMeasurement, ProxyMetricSnapshot, DataIngestionLog, utc_now
from backend.services.sci_calculator import SCIResult, SCICalculator

logger = logging.getLogger(__name__)
calculator = SCICalculator()


class SCIDataService:
    """
    Handles all database operations for SCI measurements.
    All methods accept an AsyncSession for proper transaction management.
    """

    # ── Create ─────────────────────────────────────────────────────────────

    async def save_measurement(
        self,
        db: AsyncSession,
        result: SCIResult,
        software_component: Optional[str] = None,
        deployment_env: Optional[str] = None,
        source: str = "manual",
        notes: Optional[str] = None,
    ) -> SCIMeasurement:
        """
        Persist a completed SCI calculation result to the database.

        Args:
            db:                 Active database session
            result:             SCIResult from the calculator
            software_component: Name of the measured component
            deployment_env:     cloud / on-premise / edge
            source:             Data origin: manual, gmt_csv, codecarbon, api
            notes:              Free-text notes

        Returns:
            Persisted SCIMeasurement ORM object with auto-assigned ID
        """
        measurement = SCIMeasurement(
            energy_kwh=result.components.energy_kwh,
            carbon_intensity=result.components.carbon_intensity,
            embodied_carbon=result.components.embodied_carbon,
            functional_unit=result.components.functional_unit,
            functional_unit_label=result.components.functional_unit_label,
            sci_score=result.sci_score,
            operational_carbon=result.operational_carbon,
            total_carbon=result.total_carbon,
            software_component=software_component or result.components.software_component,
            region=result.components.region,
            hardware_type=result.components.hardware_type,
            deployment_env=deployment_env,
            source=source,
            notes=notes,
        )
        db.add(measurement)
        await db.flush()  # Get ID before commit
        logger.info(f"Saved SCI measurement id={measurement.id} score={result.sci_score:.6f}")
        return measurement

    async def save_proxy_snapshot(
        self,
        db: AsyncSession,
        cpu_percent: Optional[float] = None,
        memory_gb: Optional[float] = None,
        memory_percent: Optional[float] = None,
        network_rx_mb: Optional[float] = None,
        network_tx_mb: Optional[float] = None,
        disk_read_mb: Optional[float] = None,
        disk_write_mb: Optional[float] = None,
        power_watts: Optional[float] = None,
        sci_measurement_id: Optional[int] = None,
        process_name: Optional[str] = None,
        source: str = "manual",
    ) -> ProxyMetricSnapshot:
        """Persist a single proxy metric snapshot."""
        snapshot = ProxyMetricSnapshot(
            sci_measurement_id=sci_measurement_id,
            cpu_percent=cpu_percent,
            memory_gb=memory_gb,
            memory_percent=memory_percent,
            network_rx_mb=network_rx_mb,
            network_tx_mb=network_tx_mb,
            disk_read_mb=disk_read_mb,
            disk_write_mb=disk_write_mb,
            power_watts=power_watts,
            process_name=process_name,
            source=source,
        )
        db.add(snapshot)
        await db.flush()
        return snapshot

    async def log_ingestion(
        self,
        db: AsyncSession,
        source_type: str,
        filename: Optional[str],
        records_imported: int,
        records_failed: int = 0,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> DataIngestionLog:
        """Record a data ingestion event for audit trail."""
        log = DataIngestionLog(
            source_type=source_type,
            filename=filename,
            records_imported=records_imported,
            records_failed=records_failed,
            status=status,
            error_message=error_message,
        )
        db.add(log)
        await db.flush()
        return log

    # ── Read ───────────────────────────────────────────────────────────────

    async def get_measurements(
        self,
        db: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        software_component: Optional[str] = None,
        region: Optional[str] = None,
        deployment_env: Optional[str] = None,
        source: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> list[SCIMeasurement]:
        """
        Retrieve SCI measurements with optional filtering.
        Powers the dashboard's Interactive Filtering feature (MUST requirement).
        """
        stmt = select(SCIMeasurement).order_by(desc(SCIMeasurement.created_at))

        # Apply filters
        filters = []
        if software_component:
            filters.append(SCIMeasurement.software_component == software_component)
        if region:
            filters.append(SCIMeasurement.region == region)
        if deployment_env:
            filters.append(SCIMeasurement.deployment_env == deployment_env)
        if source:
            filters.append(SCIMeasurement.source == source)
        if date_from:
            filters.append(SCIMeasurement.created_at >= date_from)
        if date_to:
            filters.append(SCIMeasurement.created_at <= date_to)

        if filters:
            stmt = stmt.where(and_(*filters))

        stmt = stmt.limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_measurement_by_id(
        self, db: AsyncSession, measurement_id: int
    ) -> Optional[SCIMeasurement]:
        """Retrieve a single SCI measurement by primary key."""
        result = await db.execute(
            select(SCIMeasurement).where(SCIMeasurement.id == measurement_id)
        )
        return result.scalar_one_or_none()

    async def get_proxy_snapshots(
        self,
        db: AsyncSession,
        sci_measurement_id: Optional[int] = None,
        hours_back: int = 24,
        limit: int = 500,
    ) -> list[ProxyMetricSnapshot]:
        """Retrieve proxy metric snapshots for time-series visualisation."""
        cutoff = utc_now() - timedelta(hours=hours_back)
        stmt = (
            select(ProxyMetricSnapshot)
            .where(ProxyMetricSnapshot.timestamp >= cutoff)
            .order_by(ProxyMetricSnapshot.timestamp)
            .limit(limit)
        )
        if sci_measurement_id:
            stmt = stmt.where(ProxyMetricSnapshot.sci_measurement_id == sci_measurement_id)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ── Aggregates ─────────────────────────────────────────────────────────

    async def get_sci_statistics(self, db: AsyncSession) -> dict:
        """
        Return aggregate statistics for the dashboard summary view.
        Includes mean, min, max SCI and record counts.
        """
        result = await db.execute(
            select(
                func.count(SCIMeasurement.id).label("total_records"),
                func.avg(SCIMeasurement.sci_score).label("avg_sci"),
                func.min(SCIMeasurement.sci_score).label("min_sci"),
                func.max(SCIMeasurement.sci_score).label("max_sci"),
                func.sum(SCIMeasurement.total_carbon).label("total_carbon_emitted"),
            )
        )
        row = result.one()
        return {
            "total_records": row.total_records or 0,
            "avg_sci_score": round(row.avg_sci, 6) if row.avg_sci else 0.0,
            "min_sci_score": round(row.min_sci, 6) if row.min_sci else 0.0,
            "max_sci_score": round(row.max_sci, 6) if row.max_sci else 0.0,
            "total_carbon_emitted_gco2eq": round(row.total_carbon_emitted, 4) if row.total_carbon_emitted else 0.0,
        }

    async def get_sci_trend(
        self,
        db: AsyncSession,
        days_back: int = 30,
    ) -> list[dict]:
        """
        Return daily average SCI scores for trend analysis.
        Used by the Energy Trend Analysis chart (MUST feature).
        """
        cutoff = utc_now() - timedelta(days=days_back)
        result = await db.execute(
            select(SCIMeasurement)
            .where(SCIMeasurement.created_at >= cutoff)
            .order_by(SCIMeasurement.created_at)
        )
        measurements = list(result.scalars().all())

        # Group by date
        daily: dict[str, list[float]] = {}
        for m in measurements:
            day_key = m.created_at.strftime("%Y-%m-%d")
            daily.setdefault(day_key, []).append(m.sci_score)

        return [
            {"date": day, "avg_sci": sum(scores) / len(scores), "count": len(scores)}
            for day, scores in sorted(daily.items())
        ]


# Module-level singleton
sci_data_service = SCIDataService()
