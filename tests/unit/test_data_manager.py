"""
GSEA Dashboard - Unit Tests: Data Manager
==========================================
Tests for CSV parsing, SCI integration, and filter helpers.
Run: pytest tests/unit/test_data_manager.py -v
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from frontend.components.data_manager import (
    parse_gmt_csv, parse_codecarbon_csv,
    apply_date_filter, rolling_average, detect_anomalies, get_date_range,
    load_sample_gmt, load_sample_codecarbon, load_sample_sci_history,
    _sci_rating,
)


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def gmt_df():
    """Minimal valid GMT-style DataFrame."""
    n = 24
    start = datetime.now() - timedelta(hours=2)
    return pd.DataFrame({
        "timestamp": pd.date_range(start=start, periods=n, freq="5min"),
        "cpu_percent": [40.0 + i for i in range(n)],
        "memory_mb": [2048.0] * n,
        "network_io_kb": [500.0] * n,
        "energy_kwh": [0.0003] * n,
    })


@pytest.fixture
def codecarbon_df():
    """Minimal valid CodeCarbon-style DataFrame."""
    n = 10
    start = datetime.now() - timedelta(hours=10)
    return pd.DataFrame({
        "timestamp": pd.date_range(start=start, periods=n, freq="1h"),
        "duration": [3600.0] * n,
        "emissions": [0.0001] * n,
        "energy_consumed": [0.00045] * n,
        "cpu_power": [45.0] * n,
        "ram_power": [3.0] * n,
        "country_iso_code": ["GBR"] * n,
        "region": ["england"] * n,
    })


# ── parse_gmt_csv ──────────────────────────────────────────────────────────

class TestParseGMTCsv:
    def test_returns_dataframe(self, gmt_df):
        result = parse_gmt_csv(gmt_df)
        assert isinstance(result, pd.DataFrame)

    def test_output_has_sci_score_column(self, gmt_df):
        result = parse_gmt_csv(gmt_df)
        assert "sci_score" in result.columns

    def test_output_has_timestamp_column(self, gmt_df):
        result = parse_gmt_csv(gmt_df)
        assert "timestamp" in result.columns
        assert pd.api.types.is_datetime64_any_dtype(result["timestamp"])

    def test_sci_scores_are_non_negative(self, gmt_df):
        result = parse_gmt_csv(gmt_df)
        assert (result["sci_score"] >= 0).all()

    def test_output_has_rating_column(self, gmt_df):
        result = parse_gmt_csv(gmt_df)
        assert "rating" in result.columns
        valid_ratings = {"Excellent", "Good", "Acceptable", "Poor", "Critical"}
        assert set(result["rating"].unique()).issubset(valid_ratings)

    def test_energy_kwh_used_when_present(self, gmt_df):
        """If energy_kwh column present, it is used as the base then memory power added.
        Fix 7: memory DRAM power (Guldner et al. 2024) is added to base energy_kwh.
        Result will be >= original 0.0003 kWh."""
        result = parse_gmt_csv(gmt_df)
        # Energy is base + memory DRAM power — must be >= original value
        assert (result["energy_kwh"] >= 0.0003).all()
        assert "energy_kwh" in result.columns

    def test_energy_estimated_when_absent(self):
        """If energy_kwh missing, estimate from CPU proxy."""
        df = pd.DataFrame({
            "timestamp": pd.date_range(start=datetime.now(), periods=5, freq="5min"),
            "cpu_percent": [50.0] * 5,
            "memory_mb": [2048.0] * 5,
        })
        result = parse_gmt_csv(df)
        assert "energy_kwh" in result.columns
        assert (result["energy_kwh"] > 0).all()

    def test_column_name_normalisation(self):
        """GMT columns with different casing should still parse."""
        df = pd.DataFrame({
            "Timestamp": pd.date_range(start=datetime.now(), periods=3, freq="5min"),
            "CPU_Percent": [40.0, 50.0, 60.0],
            "Memory_MB": [2048.0] * 3,
        })
        result = parse_gmt_csv(df)
        assert "timestamp" in result.columns

    def test_region_sets_carbon_intensity(self, gmt_df):
        """Region parameter should affect carbon intensity column."""
        uk = parse_gmt_csv(gmt_df, region="UK")
        fr = parse_gmt_csv(gmt_df, region="FR")
        assert uk["carbon_intensity"].iloc[0] != fr["carbon_intensity"].iloc[0]

    def test_lower_carbon_intensity_region_yields_lower_sci(self, gmt_df):
        """France (56 gCO₂/kWh) should yield lower SCI than India (708)."""
        fr = parse_gmt_csv(gmt_df, region="FR")
        india = parse_gmt_csv(gmt_df, region="IN")
        assert fr["sci_score"].mean() < india["sci_score"].mean()


# ── parse_codecarbon_csv ───────────────────────────────────────────────────

class TestParseCodeCarbonCsv:
    def test_returns_dataframe(self, codecarbon_df):
        result = parse_codecarbon_csv(codecarbon_df)
        assert isinstance(result, pd.DataFrame)

    def test_output_has_sci_score(self, codecarbon_df):
        result = parse_codecarbon_csv(codecarbon_df)
        assert "sci_score" in result.columns

    def test_sci_scores_positive(self, codecarbon_df):
        result = parse_codecarbon_csv(codecarbon_df)
        assert (result["sci_score"] >= 0).all()

    def test_energy_consumed_mapped(self, codecarbon_df):
        """CodeCarbon energy_consumed is mapped to energy_kwh.
        Fix 7: memory DRAM power (Guldner et al. 2024) may be added if memory_mb present.
        Result must be >= base 0.00045 kWh."""
        result = parse_codecarbon_csv(codecarbon_df)
        assert "energy_kwh" in result.columns
        # Energy >= base CodeCarbon value (memory power may be added)
        assert (result["energy_kwh"] >= 0.00045).all()

    def test_cpu_percent_derived(self, codecarbon_df):
        result = parse_codecarbon_csv(codecarbon_df)
        assert "cpu_percent" in result.columns
        assert (result["cpu_percent"] >= 0).all()
        assert (result["cpu_percent"] <= 100).all()


# ── Filter helpers ─────────────────────────────────────────────────────────

class TestFilterHelpers:
    def test_apply_date_filter_returns_subset(self, gmt_df):
        parsed = parse_gmt_csv(gmt_df)
        min_dt, max_dt = get_date_range(parsed)
        mid = min_dt + (max_dt - min_dt) / 2
        filtered = apply_date_filter(parsed, min_dt, mid)
        assert len(filtered) < len(parsed)
        assert len(filtered) > 0

    def test_apply_date_filter_full_range_returns_all(self, gmt_df):
        parsed = parse_gmt_csv(gmt_df)
        min_dt, max_dt = get_date_range(parsed)
        filtered = apply_date_filter(parsed, min_dt, max_dt)
        assert len(filtered) == len(parsed)

    def test_rolling_average_same_length(self, gmt_df):
        series = gmt_df["cpu_percent"]
        ma = rolling_average(series, window=5)
        assert len(ma) == len(series)

    def test_rolling_average_smooths(self, gmt_df):
        series = gmt_df["cpu_percent"]
        ma = rolling_average(series, window=12)
        # MA std should be less than raw std (smoothed)
        assert ma.std() <= series.std()

    def test_detect_anomalies_returns_boolean_series(self, gmt_df):
        series = gmt_df["cpu_percent"].copy()
        # Plant a spike
        series.iloc[10] = 9999
        mask = detect_anomalies(series)
        assert mask.dtype == bool
        assert bool(mask.iloc[10]) is True

    def test_detect_anomalies_uniform_series_returns_false(self):
        series = pd.Series([50.0] * 20)
        mask = detect_anomalies(series)
        assert not mask.any()

    def test_get_date_range_returns_tuple(self, gmt_df):
        parsed = parse_gmt_csv(gmt_df)
        min_dt, max_dt = get_date_range(parsed)
        assert isinstance(min_dt, datetime)
        assert isinstance(max_dt, datetime)
        assert min_dt <= max_dt


# ── SCI rating ─────────────────────────────────────────────────────────────

class TestSciRating:
    def test_excellent(self): assert _sci_rating(5.0) == "Excellent"
    def test_good(self):      assert _sci_rating(25.0) == "Good"
    def test_acceptable(self):assert _sci_rating(100.0) == "Acceptable"
    def test_poor(self):      assert _sci_rating(400.0) == "Poor"
    def test_critical(self):  assert _sci_rating(600.0) == "Critical"


# ── Sample data loaders ────────────────────────────────────────────────────

class TestSampleDataLoaders:
    def test_load_sample_gmt_returns_dataframe(self):
        df = load_sample_gmt()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "sci_score" in df.columns

    def test_load_sample_codecarbon_returns_dataframe(self):
        df = load_sample_codecarbon()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_load_sample_sci_history_returns_dataframe(self):
        df = load_sample_sci_history()
        assert isinstance(df, pd.DataFrame)
        assert "sci_score" in df.columns
        assert len(df) == 60

    def test_sample_gmt_sci_scores_all_positive(self):
        df = load_sample_gmt()
        assert (df["sci_score"] >= 0).all()
