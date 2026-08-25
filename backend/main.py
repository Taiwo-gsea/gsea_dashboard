"""
GSEA Dashboard - FastAPI Backend
==================================
RESTful API for data ingestion, SCI calculation, and metric retrieval.
Provides endpoints consumed by the Streamlit frontend.

API Documentation: http://localhost:8000/docs (auto-generated OpenAPI)
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
import io
import csv
import logging

from backend.config import settings
from backend.services.sci_calculator import (
    SCICalculator, SCIComponents,
    CARBON_INTENSITY_DEFAULTS, EMBODIED_CARBON_DEFAULTS
)
from backend.services.sci_data_service import sci_data_service
from backend.db.session import get_db

logger = logging.getLogger(__name__)

# ── App Initialisation ─────────────────────────────────────────────────────
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app_instance):
    """
    Fix 11: Create DB tables on startup so all endpoints can use the DB.
    Fix 12: Enforce the production secret-key check at startup, rather than
    leaving validate_production_secrets() defined but never called.
    """
    settings.validate_production_secrets()
    try:
        from backend.db.session import init_db
        await init_db()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"DB init skipped: {e}")
    yield  # app runs here
    # Shutdown: nothing to clean up for SQLite prototype

app = FastAPI(
    lifespan=lifespan,
    title="GSEA Dashboard API",
    description=(
        "Backend API for the Green Software Engineering Analysis (GSEA) Dashboard. "
        "Provides SCI calculation, data ingestion, and proxy metric endpoints. "
        "Aligned with ISO/IEC 21031 Software Carbon Intensity specification."
    ),
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow Streamlit frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "https://*.streamlit.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared calculator instance
calculator = SCICalculator()


# ── Pydantic Request / Response Models ────────────────────────────────────

class SCIRequest(BaseModel):
    """Request body for direct SCI calculation."""
    energy_kwh: float = Field(..., gt=0, description="Energy consumed (kWh) — E in SCI formula")
    carbon_intensity: float = Field(..., gt=0, description="Grid carbon intensity (gCO₂eq/kWh) — I")
    embodied_carbon: float = Field(..., ge=0, description="Embodied carbon (gCO₂eq) — M")
    functional_unit: float = Field(..., gt=0, description="Functional unit denominator — R")
    functional_unit_label: str = Field("request", description="Human-readable label for R (e.g., 'API call', 'user')")
    region: Optional[str] = Field(None, description="Grid region key (e.g., 'UK', 'US_avg')")
    hardware_type: Optional[str] = Field(None, description="Hardware type for embodied carbon reference")
    software_component: Optional[str] = Field(None, description="Name of the software component being measured")
    deployment_env: Optional[str] = Field(None, description="Deployment environment: cloud, on-premise, edge")

    model_config = {"json_schema_extra": {"example": {"energy_kwh": 0.5, "carbon_intensity": 233.0, "embodied_carbon": 10000.0, "functional_unit": 1000.0, "functional_unit_label": "API call", "region": "UK", "software_component": "web-frontend"}}}


class ProxyMetricRequest(BaseModel):
    """Request body for proxy-metric-based SCI estimation."""
    cpu_percent: float = Field(..., ge=0, le=100, description="Average CPU utilisation (0–100)")
    memory_gb: float = Field(..., ge=0, description="Average memory in use (GB)")
    duration_hours: float = Field(..., gt=0, description="Measurement period (hours)")
    region: str = Field("UK", description="Grid region key")
    hardware_type: str = Field("cloud_vm_small", description="Hardware type key")
    functional_unit: float = Field(1.0, gt=0, description="R denominator")
    functional_unit_label: str = Field("hour", description="R label")
    tdp_watts: float = Field(65.0, gt=0, description="CPU Thermal Design Power (W)")

    model_config = {"json_schema_extra": {"example": {"cpu_percent": 45.0, "memory_gb": 2.5, "duration_hours": 1.0, "region": "UK", "hardware_type": "cloud_vm_small", "functional_unit": 1.0, "functional_unit_label": "hour", "tdp_watts": 65.0}}}


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "message": "GSEA Dashboard API is running."
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check for monitoring."""
    return {
        "status": "healthy",
        "api_version": settings.app_version,
        "sci_formula": "SCI = (E × I + M) / R",
        "iso_standard": "ISO/IEC 21031",
    }


@app.post("/api/v1/sci/calculate", tags=["SCI"])
async def calculate_sci(request: SCIRequest, db: AsyncSession = Depends(get_db)):
    """
    Calculate SCI score from explicit component values.

    Applies ISO/IEC 21031 formula: SCI = (E × I + M) / R

    Returns full breakdown including operational/embodied carbon split,
    percentage contributions, and qualitative rating. The result is also
    persisted to the sci_measurements table as an audit record (returned
    as measurement_id below); no page currently queries this table back
    for display, so persistence does not yet feed the Energy Trend or
    Comparative Analysis pages, which read from session state instead.
    """
    try:
        components = SCIComponents(
            energy_kwh=request.energy_kwh,
            carbon_intensity=request.carbon_intensity,
            embodied_carbon=request.embodied_carbon,
            functional_unit=request.functional_unit,
            functional_unit_label=request.functional_unit_label,
            region=request.region,
            hardware_type=request.hardware_type,
            software_component=request.software_component,
        )
        result = calculator.calculate(components)
        response = result.to_dict()
        response["rating"] = result.get_rating()

        saved = await sci_data_service.save_measurement(
            db,
            result,
            software_component=request.software_component,
            deployment_env=request.deployment_env,
            source="manual",
        )
        response["measurement_id"] = saved.id

        return JSONResponse(content=response)

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"SCI calculation error: {e}")
        raise HTTPException(status_code=500, detail="Internal calculation error")


@app.post("/api/v1/sci/estimate-from-proxy", tags=["SCI"])
async def estimate_sci_from_proxy(request: ProxyMetricRequest, db: AsyncSession = Depends(get_db)):
    """
    Estimate SCI score from proxy metrics (CPU%, memory, duration).

    Uses the energy estimation formula:
        E = TDP × CPU_utilisation × duration

    This approach is used when direct energy measurement (RAPL) is
    unavailable. Both the resulting SCI measurement and the raw proxy
    metric reading are persisted as an audit record, linked by foreign
    key; as with calculate_sci() above, no page currently reads this
    back for display.
    """
    try:
        result = calculator.calculate_from_proxy_metrics(
            cpu_percent=request.cpu_percent,
            memory_gb=request.memory_gb,
            duration_hours=request.duration_hours,
            region=request.region,
            hardware_type=request.hardware_type,
            functional_unit=request.functional_unit,
            functional_unit_label=request.functional_unit_label,
            tdp_watts=request.tdp_watts,
        )
        response = result.to_dict()
        response["rating"] = result.get_rating()
        response["estimation_method"] = "proxy_metrics"
        response["estimation_note"] = (
            "Energy estimated via TDP × CPU_fraction × duration. "
            "Direct measurement preferred where available."
        )

        saved = await sci_data_service.save_measurement(
            db, result, source="proxy_metrics",
        )
        await sci_data_service.save_proxy_snapshot(
            db,
            cpu_percent=request.cpu_percent,
            memory_gb=request.memory_gb,
            sci_measurement_id=saved.id,
            source="proxy_metrics",
        )
        response["measurement_id"] = saved.id

        return JSONResponse(content=response)

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Proxy SCI estimation error: {e}")
        raise HTTPException(status_code=500, detail="Internal estimation error")


@app.post("/api/v1/ingest/gmt-csv", tags=["Data Ingestion"])
async def ingest_gmt_csv(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """
    Ingest a Green Metrics Tool (GMT) CSV export.

    Expected CSV columns:
        timestamp, cpu_percent, memory_mb, network_io_kb, energy_kwh (optional)

    Returns parsed records count and preview of first 5 rows. The ingestion
    event itself is logged to data_ingestion_logs for audit purposes,
    whether it succeeds or fails.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV (.csv)")

    if file.size and file.size > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_size_mb}MB limit")

    try:
        content = await file.read()
        decoded = content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(decoded))
        rows = list(reader)

        if not rows:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        await sci_data_service.log_ingestion(
            db, source_type="gmt_csv", filename=file.filename,
            records_imported=len(rows), status="success",
        )

        return {
            "status": "success",
            "source": "gmt_csv",
            "filename": file.filename,
            "records_parsed": len(rows),
            "columns_detected": list(rows[0].keys()) if rows else [],
            "preview": rows[:5],
            "message": f"Successfully parsed {len(rows)} records from GMT CSV."
        }

    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File encoding not supported — use UTF-8")
    except Exception as e:
        logger.error(f"GMT CSV ingestion error: {e}")
        try:
            await sci_data_service.log_ingestion(
                db, source_type="gmt_csv", filename=file.filename,
                records_imported=0, status="failed", error_message=str(e),
            )
        except Exception:
            pass  # logging the failure is best-effort; don't mask the original error
        raise HTTPException(status_code=500, detail="CSV processing error")


@app.post("/api/v1/ingest/codecarbon", tags=["Data Ingestion"])
async def ingest_codecarbon(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """
    Ingest a CodeCarbon emissions CSV export.

    CodeCarbon standard columns:
        timestamp, duration, emissions, emissions_rate, cpu_power,
        gpu_power, ram_power, cpu_energy, gpu_energy, ram_energy,
        energy_consumed, country_name, region, cloud_provider

    The ingestion event is logged to data_ingestion_logs for audit
    purposes, whether it succeeds or fails.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV (.csv)")

    try:
        content = await file.read()
        decoded = content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(decoded))
        rows = list(reader)

        if not rows:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        # Detect CodeCarbon format
        cc_columns = {"emissions", "energy_consumed", "cpu_power"}
        detected_columns = set(rows[0].keys())
        is_codecarbon_format = bool(cc_columns & detected_columns)

        await sci_data_service.log_ingestion(
            db, source_type="codecarbon", filename=file.filename,
            records_imported=len(rows), status="success",
        )

        return {
            "status": "success",
            "source": "codecarbon",
            "filename": file.filename,
            "records_parsed": len(rows),
            "is_codecarbon_format": is_codecarbon_format,
            "columns_detected": list(detected_columns),
            "preview": rows[:5],
            "message": f"Successfully parsed {len(rows)} CodeCarbon records."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CodeCarbon ingestion error: {e}")
        try:
            await sci_data_service.log_ingestion(
                db, source_type="codecarbon", filename=file.filename,
                records_imported=0, status="failed", error_message=str(e),
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="CSV processing error")


@app.get("/api/v1/reference/carbon-intensity", tags=["Reference Data"])
async def get_carbon_intensity_defaults():
    """
    Return default carbon intensity values by region (gCO₂eq/kWh).
    Source: Electricity Maps 2024 regional averages.
    """
    return {
        "data": CARBON_INTENSITY_DEFAULTS,
        "unit": "gCO₂eq/kWh",
        "source": "Electricity Maps 2024",
        "note": "Connect Electricity Maps API for real-time values."
    }


@app.get("/api/v1/reference/embodied-carbon", tags=["Reference Data"])
async def get_embodied_carbon_defaults():
    """
    Return default embodied carbon estimates by hardware type (gCO₂eq).
    Source: Guldner et al. 2024; Freitag et al. 2021.
    """
    return {
        "data": EMBODIED_CARBON_DEFAULTS,
        "unit": "gCO₂eq (full hardware lifetime)",
        "source": "Guldner et al. 2024; Freitag et al. 2021",
        "note": "Values are prorated for measurement period in calculations."
    }
