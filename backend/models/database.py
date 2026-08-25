"""
GSEA Dashboard - Database Models
==================================
SQLAlchemy ORM models for SCI measurements, proxy metrics,
ingestion history, and NLP extraction results.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, Float, String, DateTime, Boolean,
    ForeignKey, Text, JSON, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()


def utc_now() -> datetime:
    """Naive UTC timestamp, kept naive to match the existing column type
    and avoid mixing aware/naive datetimes in SQLite comparisons."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SCIMeasurement(Base):
    """
    Core table: stores each SCI calculation result.
    Directly maps to ISO/IEC 21031 SCI = (E×I+M)/R components.
    """
    __tablename__ = "sci_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # SCI Formula Components
    energy_kwh = Column(Float, nullable=False, comment="E - Energy consumed (kWh)")
    carbon_intensity = Column(Float, nullable=False, comment="I - Grid carbon intensity (gCO2eq/kWh)")
    embodied_carbon = Column(Float, nullable=False, comment="M - Embodied carbon (gCO2eq)")
    functional_unit = Column(Float, nullable=False, comment="R - Functional unit denominator")
    functional_unit_label = Column(String(64), default="request")

    # Computed results (denormalised for query performance)
    sci_score = Column(Float, nullable=False, comment="SCI = (E*I + M) / R")
    operational_carbon = Column(Float, nullable=False, comment="E * I component (gCO2eq)")
    total_carbon = Column(Float, nullable=False, comment="(E*I + M) total (gCO2eq)")

    # Metadata
    software_component = Column(String(128), nullable=True)
    region = Column(String(32), nullable=True)
    hardware_type = Column(String(64), nullable=True)
    deployment_env = Column(String(64), nullable=True, comment="cloud, on-premise, edge")
    source = Column(String(64), nullable=True, comment="manual, gmt_csv, codecarbon, api")
    notes = Column(Text, nullable=True)

    # Relationships
    proxy_metrics = relationship("ProxyMetricSnapshot", back_populates="sci_measurement", cascade="all, delete-orphan")

    # Indices for dashboard filter queries
    __table_args__ = (
        Index("ix_sci_measurements_created_at", "created_at"),
        Index("ix_sci_measurements_software_component", "software_component"),
        Index("ix_sci_measurements_region", "region"),
    )

    def __repr__(self):
        return f"<SCIMeasurement id={self.id} sci={self.sci_score:.4f} @ {self.created_at}>"


class ProxyMetricSnapshot(Base):
    """
    Time-series proxy metrics (CPU%, memory, network I/O, storage).
    Linked to an SCI measurement for correlation analysis.
    Used for the Proxy Metric Visualisation feature.
    """
    __tablename__ = "proxy_metric_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sci_measurement_id = Column(Integer, ForeignKey("sci_measurements.id"), nullable=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False)

    # Proxy metrics (all optional — not all sources provide all values)
    cpu_percent = Column(Float, nullable=True, comment="CPU utilisation 0–100")
    memory_gb = Column(Float, nullable=True, comment="Memory in use (GB)")
    memory_percent = Column(Float, nullable=True, comment="Memory utilisation 0–100")
    network_rx_mb = Column(Float, nullable=True, comment="Network received (MB)")
    network_tx_mb = Column(Float, nullable=True, comment="Network transmitted (MB)")
    disk_read_mb = Column(Float, nullable=True, comment="Disk read (MB)")
    disk_write_mb = Column(Float, nullable=True, comment="Disk write (MB)")
    gpu_percent = Column(Float, nullable=True, comment="GPU utilisation 0–100 (if available)")
    power_watts = Column(Float, nullable=True, comment="Direct power reading (W) from RAPL/IPMI")

    # Context
    process_name = Column(String(128), nullable=True)
    hostname = Column(String(128), nullable=True)
    source = Column(String(64), nullable=True)

    sci_measurement = relationship("SCIMeasurement", back_populates="proxy_metrics")

    __table_args__ = (
        Index("ix_proxy_metric_snapshots_timestamp", "timestamp"),
        Index("ix_proxy_metric_snapshots_sci_measurement_id", "sci_measurement_id"),
    )

    def __repr__(self):
        return f"<ProxyMetricSnapshot id={self.id} cpu={self.cpu_percent}% @ {self.timestamp}>"


class DataIngestionLog(Base):
    """
    Audit log of all data ingestion events.
    Tracks file uploads, API calls, and manual entries for provenance.
    """
    __tablename__ = "data_ingestion_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingested_at = Column(DateTime, default=utc_now, nullable=False)

    source_type = Column(String(32), nullable=False, comment="gmt_csv, codecarbon, manual, api")
    filename = Column(String(256), nullable=True)
    records_imported = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    status = Column(String(16), default="success", comment="success, partial, failed")
    error_message = Column(Text, nullable=True)
    raw_metadata = Column(JSON, nullable=True, comment="Source-specific metadata")

    def __repr__(self):
        return f"<DataIngestionLog id={self.id} source={self.source_type} status={self.status}>"


class NLPExtractionResult(Base):
    """
    Stores NLP extraction results from uploaded GSE papers and tool logs.
    Supports the human-in-the-loop validation workflow.
    """
    __tablename__ = "nlp_extraction_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    extracted_at = Column(DateTime, default=utc_now, nullable=False)

    source_filename = Column(String(256), nullable=True)
    source_text_excerpt = Column(Text, nullable=True, comment="The text segment the entity was extracted from")

    # Extracted entity
    entity_type = Column(String(64), nullable=False, comment="e.g., ENERGY_VALUE, CARBON_METRIC, SOFTWARE_TOOL")
    entity_text = Column(String(512), nullable=False, comment="Raw extracted text")
    entity_value = Column(Float, nullable=True, comment="Parsed numeric value if applicable")
    entity_unit = Column(String(32), nullable=True)
    confidence_score = Column(Float, nullable=True, comment="Model confidence 0.0–1.0")

    # Human-in-the-loop validation
    validated = Column(Boolean, default=False)
    validated_by = Column(String(64), nullable=True)
    validated_at = Column(DateTime, nullable=True)
    correction = Column(Text, nullable=True, comment="Reviewer's correction/note")
    accepted = Column(Boolean, nullable=True, comment="True=accepted, False=rejected, None=pending")

    __table_args__ = (
        Index("ix_nlp_extraction_results_entity_type", "entity_type"),
        Index("ix_nlp_extraction_results_validated", "validated"),
    )

    def __repr__(self):
        return f"<NLPExtractionResult id={self.id} type={self.entity_type} conf={self.confidence_score:.2f}>"
