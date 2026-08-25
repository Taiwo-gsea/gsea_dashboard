"""
GSEA Dashboard - Unit Tests: SCI Calculator
=============================================
Systematic unit tests for the SCI calculation engine.
Tests aligned with ISO/IEC 21031 specification requirements.

Run: pytest tests/unit/test_sci_calculator.py -v --cov=backend/services/sci_calculator
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.sci_calculator import (
    SCICalculator,
    SCIComponents,
    CARBON_INTENSITY_DEFAULTS,
    EMBODIED_CARBON_DEFAULTS,
    sci_calculator,
)


# ── Test fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def calculator():
    return SCICalculator()


@pytest.fixture
def valid_components():
    """Standard valid SCI components for baseline tests."""
    return SCIComponents(
        energy_kwh=0.5,
        carbon_intensity=233.0,
        embodied_carbon=10000.0,
        functional_unit=1000.0,
        functional_unit_label="API call",
        region="UK",
        hardware_type="cloud_vm_small",
    )


# ── Test: SCIComponents validation ────────────────────────────────────────

class TestSCIComponentsValidation:
    """Tests for input validation in SCIComponents."""

    def test_valid_components_instantiate_correctly(self, valid_components):
        """Valid inputs should instantiate without error."""
        assert valid_components.energy_kwh == 0.5
        assert valid_components.carbon_intensity == 233.0
        assert valid_components.embodied_carbon == 10000.0
        assert valid_components.functional_unit == 1000.0

    def test_metadata_fields_are_retained(self):
        """deployment_env and notes must survive instantiation and reach to_dict() —
        previously captured by the form but silently discarded."""
        components = SCIComponents(
            energy_kwh=0.5, carbon_intensity=233.0, embodied_carbon=10000.0,
            functional_unit=1000.0, deployment_env="cloud", notes="staging run",
        )
        assert components.deployment_env == "cloud"
        assert components.notes == "staging run"

        result = sci_calculator.calculate(components)
        d = result.to_dict()
        assert d["inputs"]["deployment_env"] == "cloud"
        assert d["inputs"]["notes"] == "staging run"

    def test_negative_energy_raises_value_error(self):
        """Energy (E) must not be negative."""
        with pytest.raises(ValueError, match="Energy"):
            SCIComponents(
                energy_kwh=-0.1,
                carbon_intensity=233.0,
                embodied_carbon=0.0,
                functional_unit=1.0,
            )

    def test_negative_carbon_intensity_raises_value_error(self):
        """Carbon intensity (I) must not be negative."""
        with pytest.raises(ValueError, match="Carbon intensity"):
            SCIComponents(
                energy_kwh=0.5,
                carbon_intensity=-10.0,
                embodied_carbon=0.0,
                functional_unit=1.0,
            )

    def test_negative_embodied_carbon_raises_value_error(self):
        """Embodied carbon (M) must not be negative."""
        with pytest.raises(ValueError, match="Embodied carbon"):
            SCIComponents(
                energy_kwh=0.5,
                carbon_intensity=233.0,
                embodied_carbon=-100.0,
                functional_unit=1.0,
            )

    def test_zero_functional_unit_raises_value_error(self):
        """Functional unit (R) must be > 0 to prevent division by zero."""
        with pytest.raises(ValueError, match="Functional unit"):
            SCIComponents(
                energy_kwh=0.5,
                carbon_intensity=233.0,
                embodied_carbon=0.0,
                functional_unit=0.0,
            )

    def test_zero_energy_is_valid(self):
        """Zero energy is valid (idle system with no load)."""
        comp = SCIComponents(
            energy_kwh=0.0,
            carbon_intensity=233.0,
            embodied_carbon=500.0,
            functional_unit=1.0,
        )
        assert comp.energy_kwh == 0.0

    def test_zero_embodied_carbon_is_valid(self):
        """Zero embodied carbon is valid (pure software measurement)."""
        comp = SCIComponents(
            energy_kwh=0.5,
            carbon_intensity=100.0,
            embodied_carbon=0.0,
            functional_unit=1.0,
        )
        assert comp.embodied_carbon == 0.0


# ── Test: SCI Formula calculation ─────────────────────────────────────────

class TestSCICalculation:
    """Tests for the core SCI = (E×I+M)/R formula."""

    def test_sci_formula_basic(self, calculator, valid_components):
        """
        SCI = (E×I + M) / R
        = (0.5 × 233.0 + 10000.0) / 1000.0
        = (116.5 + 10000.0) / 1000.0
        = 10116.5 / 1000.0
        = 10.1165
        """
        result = calculator.calculate(valid_components)
        expected = (0.5 * 233.0 + 10000.0) / 1000.0
        assert abs(result.sci_score - expected) < 1e-9

    def test_operational_carbon_calculation(self, calculator, valid_components):
        """Operational carbon = E × I."""
        result = calculator.calculate(valid_components)
        expected_op = 0.5 * 233.0  # = 116.5
        assert abs(result.operational_carbon - expected_op) < 1e-9

    def test_total_carbon_calculation(self, calculator, valid_components):
        """Total carbon = (E × I) + M."""
        result = calculator.calculate(valid_components)
        expected_total = (0.5 * 233.0) + 10000.0  # = 10116.5
        assert abs(result.total_carbon - expected_total) < 1e-9

    def test_embodied_carbon_passthrough(self, calculator, valid_components):
        """Embodied carbon in result equals M input."""
        result = calculator.calculate(valid_components)
        assert result.embodied_carbon == valid_components.embodied_carbon

    def test_sci_zero_energy_zero_embodied(self, calculator):
        """SCI of a zero-emission system should be 0."""
        comp = SCIComponents(
            energy_kwh=0.0,
            carbon_intensity=233.0,
            embodied_carbon=0.0,
            functional_unit=1.0,
        )
        result = calculator.calculate(comp)
        assert result.sci_score == 0.0

    def test_higher_functional_unit_reduces_sci(self, calculator):
        """Doubling R should halve the SCI score."""
        base = SCIComponents(energy_kwh=1.0, carbon_intensity=233.0,
                             embodied_carbon=1000.0, functional_unit=100.0)
        scaled = SCIComponents(energy_kwh=1.0, carbon_intensity=233.0,
                               embodied_carbon=1000.0, functional_unit=200.0)
        r1 = calculator.calculate(base)
        r2 = calculator.calculate(scaled)
        assert abs(r1.sci_score - 2 * r2.sci_score) < 1e-9

    def test_lower_carbon_intensity_region_improves_sci(self, calculator):
        """France (nuclear, 56 gCO2/kWh) should produce lower SCI than UK (233)."""
        uk = SCIComponents(energy_kwh=1.0, carbon_intensity=233.0,
                           embodied_carbon=1000.0, functional_unit=1.0, region="UK")
        fr = SCIComponents(energy_kwh=1.0, carbon_intensity=56.0,
                           embodied_carbon=1000.0, functional_unit=1.0, region="FR")
        uk_result = calculator.calculate(uk)
        fr_result = calculator.calculate(fr)
        assert fr_result.sci_score < uk_result.sci_score

    def test_percentage_breakdown_sums_to_100(self, calculator, valid_components):
        """Operational % + Embodied % should equal 100."""
        result = calculator.calculate(valid_components)
        assert abs(result.operational_pct + result.embodied_pct - 100.0) < 0.01


# ── Test: Proxy metric estimation ─────────────────────────────────────────

class TestProxyMetricEstimation:
    """Tests for proxy-metric-based SCI estimation."""

    def test_proxy_estimation_returns_sci_result(self, calculator):
        """Proxy estimation should return a valid SCIResult."""
        result = calculator.calculate_from_proxy_metrics(
            cpu_percent=50.0,
            memory_gb=2.0,
            duration_hours=1.0,
        )
        assert result.sci_score >= 0
        assert isinstance(result.sci_score, float)

    def test_higher_cpu_increases_sci(self, calculator):
        """Higher CPU utilisation should produce higher SCI score."""
        low_cpu = calculator.calculate_from_proxy_metrics(cpu_percent=10.0, memory_gb=2.0, duration_hours=1.0)
        high_cpu = calculator.calculate_from_proxy_metrics(cpu_percent=90.0, memory_gb=2.0, duration_hours=1.0)
        assert high_cpu.sci_score > low_cpu.sci_score

    def test_cpu_100_percent_uses_full_tdp(self, calculator):
        """At 100% CPU, energy = (TDP + memory_power) × duration.
        Fix 7: memory power now included — Guldner et al. 2024, Table 2.
        memory_power = 2.0 GB × 0.3725 W/GB = 0.745 W
        energy = (100W + 0.745W) × 1h / 1000 = 0.100745 kWh
        """
        result = calculator.calculate_from_proxy_metrics(
            cpu_percent=100.0,
            memory_gb=2.0,
            duration_hours=1.0,
            tdp_watts=100.0,
            region="UK",
            hardware_type="cloud_vm_small",
        )
        # Energy now includes memory DRAM power
        MEMORY_POWER_W_PER_GB = 0.3725
        expected = ((100.0 + 2.0 * MEMORY_POWER_W_PER_GB) * 1.0) / 1000
        assert abs(result.components.energy_kwh - expected) < 1e-6

    def test_cpu_zero_percent_produces_only_embodied_carbon(self, calculator):
        """At 0% CPU, operational carbon should be 0 (only embodied remains)."""
        result = calculator.calculate_from_proxy_metrics(
            cpu_percent=0.0,
            memory_gb=0.0,
            duration_hours=1.0,
        )
        assert result.operational_carbon == 0.0
        assert result.embodied_carbon > 0  # Embodied always present

    def test_longer_duration_increases_sci(self, calculator):
        """Longer measurement period should produce higher energy (and SCI)."""
        short = calculator.calculate_from_proxy_metrics(cpu_percent=50.0, memory_gb=2.0, duration_hours=1.0)
        long_ = calculator.calculate_from_proxy_metrics(cpu_percent=50.0, memory_gb=2.0, duration_hours=8.0)
        assert long_.operational_carbon > short.operational_carbon


# ── Test: Rating system ────────────────────────────────────────────────────

class TestRatingSystem:
    """Tests for qualitative SCI rating bands."""

    def test_excellent_rating(self, calculator):
        comp = SCIComponents(energy_kwh=0.001, carbon_intensity=10.0,
                             embodied_carbon=0.0, functional_unit=1.0)
        result = calculator.calculate(comp)
        assert result.get_rating() == "Excellent"

    def test_critical_rating(self, calculator):
        comp = SCIComponents(energy_kwh=10.0, carbon_intensity=700.0,
                             embodied_carbon=100000.0, functional_unit=1.0)
        result = calculator.calculate(comp)
        assert result.get_rating() == "Critical"

    def test_all_ratings_are_valid_strings(self, calculator):
        valid_ratings = {"Excellent", "Good", "Acceptable", "Poor", "Critical"}
        test_scores = [0.001, 0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]
        for score_multiplier in test_scores:
            comp = SCIComponents(
                energy_kwh=score_multiplier,
                carbon_intensity=233.0,
                embodied_carbon=0.0,
                functional_unit=1.0,
            )
            result = calculator.calculate(comp)
            assert result.get_rating() in valid_ratings


# ── Test: Comparative analysis ────────────────────────────────────────────

class TestComparativeAnalysis:
    """Tests for multi-configuration comparison."""

    def test_compare_configurations_returns_sorted_results(self, calculator):
        """Results should be sorted by SCI score ascending."""
        configs = [
            SCIComponents(energy_kwh=1.0, carbon_intensity=700.0, embodied_carbon=0.0, functional_unit=1.0),
            SCIComponents(energy_kwh=0.1, carbon_intensity=56.0, embodied_carbon=0.0, functional_unit=1.0),
            SCIComponents(energy_kwh=0.5, carbon_intensity=233.0, embodied_carbon=0.0, functional_unit=1.0),
        ]
        labels = ["Worst", "Best", "Middle"]
        results = calculator.compare_configurations(configs, labels)
        scores = [r["sci_score"] for r in results]
        assert scores == sorted(scores)

    def test_compare_mismatched_lengths_raises_error(self, calculator):
        """configs and labels must have equal length."""
        configs = [
            SCIComponents(energy_kwh=1.0, carbon_intensity=233.0, embodied_carbon=0.0, functional_unit=1.0),
        ]
        labels = ["A", "B"]
        with pytest.raises(ValueError):
            calculator.compare_configurations(configs, labels)


# ── Test: Serialisation ────────────────────────────────────────────────────

class TestSerialisation:
    """Tests for to_dict() output used by the API layer."""

    def test_to_dict_contains_required_keys(self, calculator, valid_components):
        result = calculator.calculate(valid_components)
        d = result.to_dict()
        required_keys = {
            "sci_score", "operational_carbon_gco2eq", "embodied_carbon_gco2eq",
            "total_carbon_gco2eq", "functional_unit", "functional_unit_label",
            "operational_pct", "embodied_pct", "inputs"
        }
        assert required_keys.issubset(set(d.keys()))

    def test_to_dict_sci_score_is_float(self, calculator, valid_components):
        result = calculator.calculate(valid_components)
        assert isinstance(result.to_dict()["sci_score"], float)


# ── Test: Reference data ───────────────────────────────────────────────────

class TestReferenceData:
    """Tests for carbon intensity and embodied carbon reference dictionaries."""

    def test_uk_carbon_intensity_present(self):
        assert "UK" in CARBON_INTENSITY_DEFAULTS
        assert CARBON_INTENSITY_DEFAULTS["UK"] > 0

    def test_cloud_vm_small_embodied_present(self):
        assert "cloud_vm_small" in EMBODIED_CARBON_DEFAULTS
        assert EMBODIED_CARBON_DEFAULTS["cloud_vm_small"] > 0

    def test_all_carbon_intensity_values_positive(self):
        for region, value in CARBON_INTENSITY_DEFAULTS.items():
            assert value > 0, f"Carbon intensity for {region} must be positive"

    def test_all_embodied_carbon_values_positive(self):
        for hw_type, value in EMBODIED_CARBON_DEFAULTS.items():
            assert value > 0, f"Embodied carbon for {hw_type} must be positive"

    def test_france_lower_than_uk(self):
        """France (nuclear) should have lower carbon intensity than UK."""
        assert CARBON_INTENSITY_DEFAULTS["FR"] < CARBON_INTENSITY_DEFAULTS["UK"]

    def test_server_rack_higher_than_laptop(self):
        """Server rack should have higher embodied carbon than laptop."""
        assert EMBODIED_CARBON_DEFAULTS["server_rack"] > EMBODIED_CARBON_DEFAULTS["laptop"]


# ── Test: Module-level singleton ──────────────────────────────────────────

def test_module_level_calculator_is_sci_calculator_instance():
    """The module-level sci_calculator should be a SCICalculator instance."""
    assert isinstance(sci_calculator, SCICalculator)
