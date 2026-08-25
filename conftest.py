"""
GSEA Dashboard - Shared Test Fixtures
=======================================
conftest.py is automatically loaded by pytest.
Fixtures here are available to all tests without explicit import.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from backend.services.sci_calculator import SCIComponents, SCICalculator


@pytest.fixture(scope="session")
def sci_calculator_instance():
    """Shared calculator instance for all tests."""
    return SCICalculator()


@pytest.fixture
def minimal_components():
    """Minimal valid SCI components (no optional fields)."""
    return SCIComponents(
        energy_kwh=1.0,
        carbon_intensity=233.0,
        embodied_carbon=0.0,
        functional_unit=1.0,
    )


@pytest.fixture
def full_components():
    """Fully-specified SCI components with all optional metadata."""
    return SCIComponents(
        energy_kwh=0.5,
        carbon_intensity=233.0,
        embodied_carbon=10000.0,
        functional_unit=1000.0,
        functional_unit_label="API call",
        region="UK",
        hardware_type="cloud_vm_small",
        measurement_period_hours=1.0,
        software_component="web-api",
    )


@pytest.fixture
def sample_gmt_csv_content():
    """Sample GMT CSV content as bytes for upload tests."""
    return (
        b"timestamp,cpu_percent,memory_mb,network_io_kb,energy_kwh\n"
        b"2026-05-01T10:00:00,45.0,2048,512,0.00030\n"
        b"2026-05-01T10:05:00,55.0,2100,620,0.00040\n"
        b"2026-05-01T10:10:00,38.0,1980,400,0.00025\n"
    )


@pytest.fixture
def sample_codecarbon_csv_content():
    """Sample CodeCarbon CSV content as bytes."""
    return (
        b"timestamp,duration,emissions,emissions_rate,cpu_power,gpu_power,ram_power,"
        b"cpu_energy,gpu_energy,ram_energy,energy_consumed,country_name,region\n"
        b"2026-05-01T10:00:00,3600,0.0001047,2.9e-08,45.0,0.0,3.0,"
        b"0.000045,0.0,0.000003,0.000048,United Kingdom,england\n"
    )
