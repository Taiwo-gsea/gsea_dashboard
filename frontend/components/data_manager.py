"""
GSEA Dashboard - Data Manager
===============================
Central data orchestration layer that:
  1. Parses uploaded GMT / CodeCarbon CSV files
  2. Applies the SCI calculator to produce SCIResult objects
  3. Stores results in session state for use across all dashboard pages
  4. Provides consistent filter helpers used by every visualisation page

This is the glue between data ingestion (Phase 2) and visualisation (Phase 3).
All pages import from this module — no page duplicates parsing logic.
"""

from __future__ import annotations

import pandas as pd
# Safe Streamlit import — falls back gracefully in test environments
try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    st = None
    _HAS_STREAMLIT = False
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.sci_calculator import (
    SCICalculator,
    CARBON_INTENSITY_DEFAULTS, EMBODIED_CARBON_DEFAULTS,
)

calculator = SCICalculator()

# ── Default SCI parameters applied when source data lacks explicit values ──
DEFAULT_CI = CARBON_INTENSITY_DEFAULTS["UK"]          # gCO₂eq/kWh
DEFAULT_EMBODIED = EMBODIED_CARBON_DEFAULTS["cloud_vm_small"]  # gCO₂eq
DEFAULT_TDP_W = 65.0                                   # CPU TDP, Watts
DEFAULT_R = 1000.0                                     # Functional unit denominator
DEFAULT_R_LABEL = "request"
MEMORY_POWER_W_PER_GB = 0.3725  # Guldner et al. 2024, Table 2 — DRAM power per GB


# ═══════════════════════════════════════════════════════════════
# GMT CSV PARSER
# ═══════════════════════════════════════════════════════════════

def _cache(fn):
    """Apply st.cache_data when Streamlit is available, else no-op."""
    if _HAS_STREAMLIT and st is not None:
        return st.cache_data(fn)
    return fn

@_cache
def parse_gmt_csv(df: pd.DataFrame, region: str = "UK") -> pd.DataFrame:
    """
    Parse a Green Metrics Tool CSV into a normalised metrics DataFrame.

    Handles column name variations across GMT versions.
    Returns a clean DataFrame with standardised columns:
        timestamp, cpu_percent, memory_mb, network_io_kb, energy_kwh,
        sci_score, operational_carbon, embodied_carbon, total_carbon, rating
    """
    df = df.copy()

    # Normalise column names (GMT versions differ in casing/underscores)
    df.columns = [c.strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]

    # Timestamp
    for ts_col in ["timestamp", "time", "datetime", "date"]:
        if ts_col in df.columns:
            df["timestamp"] = pd.to_datetime(df[ts_col], errors="coerce")
            break
    if "timestamp" not in df.columns:
        df["timestamp"] = pd.date_range(start=datetime.now() - timedelta(hours=len(df)/12), periods=len(df), freq="5min")

    # CPU
    for c in ["cpu_percent", "cpu_%", "cpu", "cpu_utilization", "cpu_util"]:
        if c in df.columns:
            df["cpu_percent"] = pd.to_numeric(df[c], errors="coerce").clip(0, 100)
            break
    if "cpu_percent" not in df.columns:
        df["cpu_percent"] = 0.0

    # Memory
    for c in ["memory_mb", "mem_mb", "memory", "memory_usage_mb", "ram_mb"]:
        if c in df.columns:
            df["memory_mb"] = pd.to_numeric(df[c], errors="coerce")
            break
    if "memory_mb" not in df.columns:
        df["memory_mb"] = 0.0

    # Network I/O
    for c in ["network_io_kb", "network_kb", "net_io_kb", "net_kb"]:
        if c in df.columns:
            df["network_io_kb"] = pd.to_numeric(df[c], errors="coerce")
            break
    if "network_io_kb" not in df.columns:
        df["network_io_kb"] = 0.0

    # Energy — use directly if present, else estimate from CPU proxy
    if "energy_kwh" in df.columns:
        df["energy_kwh"] = pd.to_numeric(df["energy_kwh"], errors="coerce").fillna(0)
    else:
        # Proxy: E = TDP × cpu_fraction × interval_hours / 1000
        interval_h = 5 / 60  # Assume 5-min sampling interval
        # Energy = (TDP × CPU_fraction + memory_power) × duration
        # Memory DRAM power: Guldner et al. 2024, Table 2 — 0.3725 W/GB
        mem_gb_approx = df.get("memory_mb", pd.Series([2048.0]*len(df))) / 1024
        mem_power_w   = mem_gb_approx * MEMORY_POWER_W_PER_GB
        df["energy_kwh"] = ((DEFAULT_TDP_W * (df["cpu_percent"] / 100) + mem_power_w) * interval_h) / 1000

    # Carbon intensity
    ci = CARBON_INTENSITY_DEFAULTS.get(region, DEFAULT_CI)
    df["carbon_intensity"] = ci
    df["region"] = region

    # Fix 6+7+8: Vectorised SCI — no iterrows(), with memory power
    # Detect sampling interval from timestamps (default 5 min)
    if len(df) > 1:
        try:
            delta_s = (df["timestamp"].iloc[1] - df["timestamp"].iloc[0]).total_seconds()
            interval_h = max(delta_s, 60) / 3600
        except Exception:
            interval_h = 5 / 60
    else:
        interval_h = 5 / 60

    # Add memory power to energy estimate (Guldner et al. 2024, Table 2: 0.3725 W/GB)
    if "memory_mb" in df.columns:
        memory_gb_col = df["memory_mb"] / 1024
        memory_power_kwh = (memory_gb_col * MEMORY_POWER_W_PER_GB * interval_h) / 1000
        df["energy_kwh"] = (df["energy_kwh"] + memory_power_kwh).clip(lower=0)

    # Prorate embodied carbon — 4-year lifespan (GSF SCI spec v1.1.0 §4.3)
    prorated_m = DEFAULT_EMBODIED * (interval_h / (4 * 365 * 24))

    # Vectorised SCI = (E × I + M) / R
    df["operational_carbon"] = df["energy_kwh"].clip(lower=0) * ci
    df["embodied_carbon"]    = prorated_m
    df["total_carbon"]       = df["operational_carbon"] + prorated_m
    df["sci_score"]          = (df["total_carbon"] / DEFAULT_R).clip(lower=0)
    df["rating"]             = df["sci_score"].apply(_sci_rating)

    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════════════════════
# CODECARBON CSV PARSER
# ═══════════════════════════════════════════════════════════════

@_cache
def parse_codecarbon_csv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse a CodeCarbon emissions.csv into a normalised metrics DataFrame.
    Maps CodeCarbon columns → GSEA standard schema.
    """
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    # Timestamp
    for ts_col in ["timestamp", "datetime"]:
        if ts_col in df.columns:
            df["timestamp"] = pd.to_datetime(df[ts_col], errors="coerce")
            break
    if "timestamp" not in df.columns:
        df["timestamp"] = pd.date_range(start=datetime.now() - timedelta(days=7), periods=len(df), freq="1h")

    # Energy consumed (kWh) — CodeCarbon stores this directly
    df["energy_kwh"] = pd.to_numeric(df.get("energy_consumed", pd.Series([0]*len(df))), errors="coerce").fillna(0)

    # Emissions (kg CO₂eq) → convert to gCO₂eq
    if "emissions" in df.columns:
        df["emissions_gco2eq"] = pd.to_numeric(df["emissions"], errors="coerce").fillna(0) * 1000
    else:
        df["emissions_gco2eq"] = 0.0

    # CPU power (W)
    df["cpu_power_w"] = pd.to_numeric(df.get("cpu_power", pd.Series([DEFAULT_TDP_W]*len(df))), errors="coerce").fillna(DEFAULT_TDP_W)

    # Duration (seconds) → hours
    df["duration_h"] = pd.to_numeric(df.get("duration", pd.Series([3600]*len(df))), errors="coerce").fillna(3600) / 3600

    # Derive CPU% from cpu_power / TDP
    df["cpu_percent"] = ((df["cpu_power_w"] / DEFAULT_TDP_W) * 100).clip(0, 100)

    # Memory: CodeCarbon tracks ram_power, not GB directly — approximate
    df["memory_mb"] = pd.to_numeric(df.get("ram_power", pd.Series([0]*len(df))), errors="coerce").fillna(0) * 10  # rough proxy

    # Region / carbon intensity
    def _ci_from_row(row):
        region  = str(row.get("region", "")          if hasattr(row, "get") else "").upper()
        country = str(row.get("country_iso_code", "") if hasattr(row, "get") else "").upper()
        for key in [region, country]:
            if key in CARBON_INTENSITY_DEFAULTS:
                return CARBON_INTENSITY_DEFAULTS[key], key
        return DEFAULT_CI, "UK"

    # Vectorised CI lookup — apply() is faster than iterrows() for row-wise ops
    if len(df) > 0:
        ci_region = df.apply(_ci_from_row, axis=1)
        df["carbon_intensity"] = ci_region.apply(lambda x: x[0])
        df["region"]           = ci_region.apply(lambda x: x[1])
    else:
        df["carbon_intensity"] = DEFAULT_CI
        df["region"] = "UK"

    # Fix 6+7+8: Vectorised SCI — no iterrows(), with memory power
    df["duration_h"] = df["duration_h"].clip(lower=0.001)

    # Add memory power (Guldner et al. 2024, Table 2: 0.3725 W/GB DRAM power)
    if "memory_mb" in df.columns:
        memory_gb_col = df["memory_mb"] / 1024
        mem_kwh = (memory_gb_col * MEMORY_POWER_W_PER_GB * df["duration_h"]) / 1000
        df["energy_kwh"] = (df["energy_kwh"] + mem_kwh).clip(lower=0)

    # Prorate embodied carbon — 4-year lifespan (GSF SCI spec v1.1.0 §4.3)
    df["embodied_carbon"]    = DEFAULT_EMBODIED * (df["duration_h"] / (4 * 365 * 24))
    df["operational_carbon"] = df["energy_kwh"].clip(lower=0) * df["carbon_intensity"]
    df["total_carbon"]       = df["operational_carbon"] + df["embodied_carbon"]
    df["sci_score"]          = (df["total_carbon"] / DEFAULT_R).clip(lower=0)
    df["rating"]             = df["sci_score"].apply(_sci_rating)

    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════════════════════
# SCI HISTORY PARSER
# ═══════════════════════════════════════════════════════════════

def parse_sci_history_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Parse the sci_history.csv format produced by the sample data generator."""
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["date"], errors="coerce")
    df["sci_score"] = pd.to_numeric(df["sci_score"], errors="coerce")
    df["energy_kwh"] = pd.to_numeric(df.get("energy_kwh", 0), errors="coerce").fillna(0)
    df["carbon_intensity"] = pd.to_numeric(df.get("carbon_intensity", DEFAULT_CI), errors="coerce").fillna(DEFAULT_CI)
    df["rating"] = df["sci_score"].apply(lambda s: _sci_rating(s))
    return df.sort_values("timestamp").reset_index(drop=True)


def _sci_rating(score: float) -> str:
    if score < 10:   return "Excellent"
    if score < 50:   return "Good"
    if score < 200:  return "Acceptable"
    if score < 500:  return "Poor"
    return "Critical"


# ═══════════════════════════════════════════════════════════════
# FILTER HELPERS  (used by all visualisation pages)
# ═══════════════════════════════════════════════════════════════

def apply_date_filter(df: pd.DataFrame, date_from: datetime, date_to: datetime) -> pd.DataFrame:
    """Filter DataFrame to rows within [date_from, date_to] inclusive."""
    mask = (df["timestamp"] >= pd.Timestamp(date_from)) & (df["timestamp"] <= pd.Timestamp(date_to))
    return df[mask].reset_index(drop=True)


def apply_component_filter(df: pd.DataFrame, components: list[str]) -> pd.DataFrame:
    """Filter to selected software components (or return all if list is empty)."""
    if not components or "All" in components:
        return df
    col = "software_component" if "software_component" in df.columns else "container_name"
    if col in df.columns:
        return df[df[col].isin(components)].reset_index(drop=True)
    return df


def get_date_range(df: pd.DataFrame) -> tuple[datetime, datetime]:
    """Return (min_date, max_date) from a DataFrame's timestamp column."""
    if "timestamp" not in df.columns or df.empty:
        return datetime.now() - timedelta(days=7), datetime.now()
    return df["timestamp"].min().to_pydatetime(), df["timestamp"].max().to_pydatetime()


def rolling_average(series: pd.Series, window: int = 12) -> pd.Series:
    """Apply centred rolling average; forward-fill edges."""
    return series.rolling(window=window, center=True, min_periods=1).mean()


def detect_anomalies(series: pd.Series, sigma: float = 2.5) -> pd.Series:
    """Return boolean mask — True where |value - mean| > sigma * std."""
    mean, std = series.mean(), series.std()
    if std == 0:
        return pd.Series([False] * len(series), index=series.index)
    return (series - mean).abs() > sigma * std


# ═══════════════════════════════════════════════════════════════
# SAMPLE DATA LOADER (for demo / testing without uploads)
# ═══════════════════════════════════════════════════════════════

_SAMPLE_DIR = Path(__file__).parent.parent.parent / "data" / "sample"


def load_sample_gmt(region: str = "UK") -> pd.DataFrame:
    """Load and parse the bundled GMT sample CSV."""
    path = _SAMPLE_DIR / "gmt_sample.csv"
    return parse_gmt_csv(pd.read_csv(path), region=region)


def load_sample_codecarbon() -> pd.DataFrame:
    """Load and parse the bundled CodeCarbon sample CSV."""
    path = _SAMPLE_DIR / "codecarbon_sample.csv"
    return parse_codecarbon_csv(pd.read_csv(path))


def load_sample_sci_history() -> pd.DataFrame:
    """Load the bundled SCI history CSV."""
    path = _SAMPLE_DIR / "sci_history.csv"
    return parse_sci_history_csv(pd.read_csv(path))
