"""
GSEA Dashboard - Integration Tests: FastAPI Endpoints
=======================================================
Tests for all FastAPI route handlers.
Uses httpx.AsyncClient as the test transport layer.

Run: pytest tests/integration/test_api.py -v
"""

import pytest
import sys
from pathlib import Path
import io
import csv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import FastAPI app
from backend.main import app


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """
    Synchronous TestClient for endpoint tests.
    Used as a context manager so FastAPI's lifespan (table creation,
    production secret validation) actually runs before requests are made,
    the same way it does under a real uvicorn server.
    """
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi[testclient] not installed")
    with TestClient(app) as c:
        yield c


def _make_csv_bytes(rows: list[dict]) -> bytes:
    """Helper: create a CSV file as bytes for upload tests."""
    if not rows:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


# ── Health Endpoints ───────────────────────────────────────────────────────

class TestHealthEndpoints:
    """Tests for health check routes."""

    def test_root_returns_healthy(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_root_includes_app_name(self, client):
        response = client.get("/")
        assert "GSEA Dashboard" in response.json()["app"]

    def test_health_check_includes_sci_formula(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "SCI" in data["sci_formula"]
        assert data["iso_standard"] == "ISO/IEC 21031"


# ── SCI Calculation Endpoints ──────────────────────────────────────────────

class TestSCICalculationEndpoint:
    """Tests for POST /api/v1/sci/calculate."""

    def test_valid_sci_calculation_returns_200(self, client):
        payload = {
            "energy_kwh": 0.5,
            "carbon_intensity": 233.0,
            "embodied_carbon": 10000.0,
            "functional_unit": 1000.0,
            "functional_unit_label": "API call",
        }
        response = client.post("/api/v1/sci/calculate", json=payload)
        assert response.status_code == 200

    def test_sci_calculation_is_persisted(self, client):
        """A successful calculation should be saved and return a measurement_id."""
        payload = {
            "energy_kwh": 0.5,
            "carbon_intensity": 233.0,
            "embodied_carbon": 10000.0,
            "functional_unit": 1000.0,
        }
        response = client.post("/api/v1/sci/calculate", json=payload)
        data = response.json()
        assert "measurement_id" in data
        assert isinstance(data["measurement_id"], int)
        assert data["measurement_id"] > 0

    def test_sci_calculation_result_contains_sci_score(self, client):
        payload = {
            "energy_kwh": 0.5,
            "carbon_intensity": 233.0,
            "embodied_carbon": 10000.0,
            "functional_unit": 1000.0,
        }
        response = client.post("/api/v1/sci/calculate", json=payload)
        data = response.json()
        assert "sci_score" in data
        assert isinstance(data["sci_score"], float)
        assert data["sci_score"] > 0

    def test_sci_calculation_matches_formula(self, client):
        """Verify API result matches SCI = (E×I+M)/R."""
        payload = {
            "energy_kwh": 1.0,
            "carbon_intensity": 100.0,
            "embodied_carbon": 0.0,
            "functional_unit": 1.0,
        }
        response = client.post("/api/v1/sci/calculate", json=payload)
        data = response.json()
        # SCI = (1.0 × 100.0 + 0.0) / 1.0 = 100.0
        assert abs(data["sci_score"] - 100.0) < 1e-6

    def test_sci_calculation_includes_rating(self, client):
        payload = {
            "energy_kwh": 0.5,
            "carbon_intensity": 233.0,
            "embodied_carbon": 10000.0,
            "functional_unit": 1000.0,
        }
        response = client.post("/api/v1/sci/calculate", json=payload)
        data = response.json()
        assert "rating" in data
        assert data["rating"] in ["Excellent", "Good", "Acceptable", "Poor", "Critical"]

    def test_sci_calculation_includes_breakdown(self, client):
        """Result should include operational and embodied carbon percentages."""
        payload = {
            "energy_kwh": 0.5,
            "carbon_intensity": 233.0,
            "embodied_carbon": 10000.0,
            "functional_unit": 1000.0,
        }
        response = client.post("/api/v1/sci/calculate", json=payload)
        data = response.json()
        assert "operational_pct" in data
        assert "embodied_pct" in data
        # Percentages must sum to 100
        assert abs(data["operational_pct"] + data["embodied_pct"] - 100.0) < 0.1

    def test_negative_energy_returns_422(self, client):
        payload = {
            "energy_kwh": -1.0,
            "carbon_intensity": 233.0,
            "embodied_carbon": 0.0,
            "functional_unit": 1.0,
        }
        response = client.post("/api/v1/sci/calculate", json=payload)
        assert response.status_code in [422, 500]

    def test_zero_functional_unit_returns_error(self, client):
        payload = {
            "energy_kwh": 0.5,
            "carbon_intensity": 233.0,
            "embodied_carbon": 0.0,
            "functional_unit": 0.0,
        }
        response = client.post("/api/v1/sci/calculate", json=payload)
        assert response.status_code in [422, 500]

    def test_optional_region_field_accepted(self, client):
        payload = {
            "energy_kwh": 0.5,
            "carbon_intensity": 233.0,
            "embodied_carbon": 10000.0,
            "functional_unit": 1000.0,
            "region": "UK",
            "software_component": "test-service",
        }
        response = client.post("/api/v1/sci/calculate", json=payload)
        assert response.status_code == 200


# ── Proxy Estimation Endpoint ──────────────────────────────────────────────

class TestProxyEstimationEndpoint:
    """Tests for POST /api/v1/sci/estimate-from-proxy."""

    def test_valid_proxy_estimation_returns_200(self, client):
        payload = {
            "cpu_percent": 45.0,
            "memory_gb": 2.5,
            "duration_hours": 1.0,
            "region": "UK",
            "hardware_type": "cloud_vm_small",
            "functional_unit": 1.0,
            "functional_unit_label": "hour",
            "tdp_watts": 65.0,
        }
        response = client.post("/api/v1/sci/estimate-from-proxy", json=payload)
        assert response.status_code == 200

    def test_proxy_estimation_is_persisted(self, client):
        """A successful proxy estimation should save both a measurement and
        a proxy metric snapshot, and return the measurement_id."""
        payload = {
            "cpu_percent": 45.0,
            "memory_gb": 2.5,
            "duration_hours": 1.0,
            "region": "UK",
            "hardware_type": "cloud_vm_small",
            "functional_unit": 1.0,
            "functional_unit_label": "hour",
            "tdp_watts": 65.0,
        }
        response = client.post("/api/v1/sci/estimate-from-proxy", json=payload)
        data = response.json()
        assert "measurement_id" in data
        assert isinstance(data["measurement_id"], int)
        assert data["measurement_id"] > 0

    def test_proxy_estimation_includes_method_note(self, client):
        payload = {
            "cpu_percent": 50.0,
            "memory_gb": 2.0,
            "duration_hours": 1.0,
        }
        response = client.post("/api/v1/sci/estimate-from-proxy", json=payload)
        data = response.json()
        assert data.get("estimation_method") == "proxy_metrics"
        assert "estimation_note" in data

    def test_proxy_estimation_sci_score_positive(self, client):
        payload = {
            "cpu_percent": 30.0,
            "memory_gb": 1.0,
            "duration_hours": 2.0,
        }
        response = client.post("/api/v1/sci/estimate-from-proxy", json=payload)
        assert response.json()["sci_score"] > 0

    def test_cpu_over_100_returns_422(self, client):
        payload = {
            "cpu_percent": 150.0,
            "memory_gb": 2.0,
            "duration_hours": 1.0,
        }
        response = client.post("/api/v1/sci/estimate-from-proxy", json=payload)
        assert response.status_code == 422


# ── Data Ingestion Endpoints ───────────────────────────────────────────────

class TestGMTIngestionEndpoint:
    """Tests for POST /api/v1/ingest/gmt-csv."""

    def test_valid_gmt_csv_upload(self, client):
        csv_rows = [
            {"timestamp": "2026-05-01T10:00:00", "cpu_percent": "45.0",
             "memory_mb": "2048", "network_io_kb": "512", "energy_kwh": "0.0003"},
            {"timestamp": "2026-05-01T10:05:00", "cpu_percent": "55.0",
             "memory_mb": "2100", "network_io_kb": "620", "energy_kwh": "0.0004"},
        ]
        csv_bytes = _make_csv_bytes(csv_rows)
        response = client.post(
            "/api/v1/ingest/gmt-csv",
            files={"file": ("gmt_sample.csv", csv_bytes, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["records_parsed"] == 2

    def test_gmt_non_csv_file_returns_400(self, client):
        response = client.post(
            "/api/v1/ingest/gmt-csv",
            files={"file": ("data.xlsx", b"fake content", "application/octet-stream")},
        )
        assert response.status_code == 400

    def test_gmt_empty_csv_returns_400(self, client):
        response = client.post(
            "/api/v1/ingest/gmt-csv",
            files={"file": ("empty.csv", b"", "text/csv")},
        )
        assert response.status_code == 400

    def test_gmt_response_includes_columns_detected(self, client):
        csv_rows = [{"timestamp": "2026-05-01", "cpu_percent": "40", "energy_kwh": "0.001"}]
        csv_bytes = _make_csv_bytes(csv_rows)
        response = client.post(
            "/api/v1/ingest/gmt-csv",
            files={"file": ("test.csv", csv_bytes, "text/csv")},
        )
        data = response.json()
        assert "columns_detected" in data
        assert "timestamp" in data["columns_detected"]


class TestCodeCarbonIngestionEndpoint:
    """Tests for POST /api/v1/ingest/codecarbon."""

    def test_valid_codecarbon_csv_upload(self, client):
        csv_rows = [
            {"timestamp": "2026-05-01T10:00:00", "duration": "3600",
             "emissions": "0.0001047", "energy_consumed": "0.00045",
             "cpu_power": "45.0", "country_name": "United Kingdom"},
        ]
        csv_bytes = _make_csv_bytes(csv_rows)
        response = client.post(
            "/api/v1/ingest/codecarbon",
            files={"file": ("emissions.csv", csv_bytes, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["is_codecarbon_format"] is True


# ── Reference Data Endpoints ───────────────────────────────────────────────

class TestReferenceDataEndpoints:
    """Tests for /api/v1/reference/* endpoints."""

    def test_carbon_intensity_defaults_endpoint(self, client):
        response = client.get("/api/v1/reference/carbon-intensity")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "UK" in data["data"]
        assert data["unit"] == "gCO₂eq/kWh"

    def test_embodied_carbon_defaults_endpoint(self, client):
        response = client.get("/api/v1/reference/embodied-carbon")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "cloud_vm_small" in data["data"]

    def test_carbon_intensity_values_are_positive(self, client):
        response = client.get("/api/v1/reference/carbon-intensity")
        data = response.json()["data"]
        for region, value in data.items():
            assert value > 0, f"Carbon intensity for {region} should be positive"
