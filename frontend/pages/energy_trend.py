"""
GSEA Dashboard - Energy Trend Analysis Page
=============================================
MUST feature: Line chart of energy consumption and SCI scores over time
with moving averages, anomaly detection, and interactive filtering.

Aligned with Gil (2024): interactive filtering is the most impactful
feature for green dashboards.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from frontend.components.data_manager import (
    load_sample_gmt, load_sample_codecarbon, load_sample_sci_history,
    apply_date_filter, rolling_average, detect_anomalies, get_date_range,
    CARBON_INTENSITY_DEFAULTS,
)

# Colour-blind safe Okabe-Ito palette
C = {
    "energy":    "#0072B2",
    "sci":       "#009E73",
    "carbon":    "#E69F00",
    "anomaly":   "#D55E00",
    "ma":        "#333333",
    "grid":      "#f0f0f0",
}


def render_energy_trend():
    """Render the Energy Trend Analysis page.  Ch.5 §5.3.2 — Energy Trend Analysis (MUST)."""

    st.markdown("""
    <div class="page-header">
        <div class="page-header-left">
            <div class="page-title">📉 Energy Trend Analysis</div>
            <span class="page-tab active">Trend</span>
            <span class="page-tab inactive">Anomalies</span>
        </div>
        <span class="badge badge-cyan">MUST Feature</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(
        "Longitudinal analysis of energy consumption, SCI scores, and carbon emissions over time. "
        "Use interactive filters to zoom in on specific periods, components, or regions."
    )

    # ── Data Source ────────────────────────────────────────────────────────
    with st.expander("⚙️ Data source & settings", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            # Build dynamic source list from session-stored datasets
            _base_sources = ["GMT sample data", "CodeCarbon sample", "SCI history (60 days)"]
            _session_ds   = st.session_state.get("parsed_datasets", [])
            _session_opts = [d["label"] for d in _session_ds]
            _all_sources  = _base_sources + _session_opts
            source = st.selectbox(
                "Data source",
                _all_sources,
                help="Upload files via Data Ingestion to add them here automatically.",
            )

        with col2:
            region = st.selectbox(
                "Grid region",
                list(CARBON_INTENSITY_DEFAULTS.keys()),
                index=0,
                format_func=lambda k: f"{k}  ({CARBON_INTENSITY_DEFAULTS[k]} gCO₂/kWh)",
            )

        with col3:
            ma_window = st.slider("Moving average window", 3, 30, 12,
                                  help="Number of data points for the rolling mean.")

    # ── Load data ──────────────────────────────────────────────────────────
    df = _load_data(source, region)

    if df is None or df.empty:
        st.warning("No data available for the selected source. Upload a file via **Data Ingestion** first.")
        return

    # ── Date range filter ──────────────────────────────────────────────────
    min_dt, max_dt = get_date_range(df)
    col_a, col_b = st.columns(2)
    with col_a:
        date_from = st.date_input("From", value=min_dt.date(), min_value=min_dt.date(), max_value=max_dt.date())
    with col_b:
        date_to   = st.date_input("To",   value=max_dt.date(), min_value=min_dt.date(), max_value=max_dt.date())

    df = apply_date_filter(df, datetime.combine(date_from, datetime.min.time()),
                               datetime.combine(date_to,   datetime.max.time()))

    if df.empty:
        st.warning("No data in selected date range.")
        return

    st.divider()

    # ── KPI summary row ────────────────────────────────────────────────────
    _render_kpis(df)

    st.divider()

    # ── Main charts ────────────────────────────────────────────────────────
    show_anomalies = st.toggle("Highlight anomalies", value=True)

    _render_energy_chart(df, ma_window, show_anomalies)
    _render_sci_trend_chart(df, ma_window, show_anomalies)
    _render_carbon_breakdown_chart(df)
    _render_correlation_scatter(df)


# ── helpers ────────────────────────────────────────────────────────────────

def _load_data(source: str, region: str) -> pd.DataFrame | None:
    """Load data — sample sets or any dataset ingested via Data Ingestion page."""
    try:
        if source == "GMT sample data":
            return load_sample_gmt(region=region)
        elif source == "CodeCarbon sample":
            return load_sample_codecarbon()
        elif source == "SCI history (60 days)":
            return load_sample_sci_history()
        else:
            # Look up by label in the shared parsed_datasets session store
            datasets = st.session_state.get("parsed_datasets", [])
            match = next((d for d in datasets if d["label"] == source), None)
            if match is None:
                st.warning(f"Dataset '{source}' no longer in session. Re-upload via Data Ingestion.")
                return None
            return match["df"]
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None


def _render_kpis(df: pd.DataFrame):
    """Render the KPI summary row."""
    cols = st.columns(5)

    energy_col = "energy_kwh" if "energy_kwh" in df.columns else None
    sci_col    = "sci_score"  if "sci_score"  in df.columns else None
    carbon_col = "total_carbon" if "total_carbon" in df.columns else None

    with cols[0]:
        if energy_col:
            st.metric("Total Energy", f"{df[energy_col].sum():.5f} kWh",
                      help="Sum of all energy readings in selected period")
        else:
            st.metric("Total Energy", "N/A")

    with cols[1]:
        if sci_col:
            mean_sci = df[sci_col].mean()
            st.metric("Mean SCI Score", f"{mean_sci:.4f}",
                      help="Average SCI across all measurements in the period")
        else:
            st.metric("Mean SCI Score", "N/A")

    with cols[2]:
        if sci_col:
            st.metric("Min SCI Score", f"{df[sci_col].min():.4f}",
                      delta="Best reading",
                      delta_color="normal")
        else:
            st.metric("Min SCI Score", "N/A")

    with cols[3]:
        if carbon_col:
            total_c = df[carbon_col].sum()
            st.metric("Total Carbon", f"{total_c:.2f} gCO₂eq",
                      help="Cumulative carbon across operational + embodied components")
        else:
            st.metric("Total Carbon", "N/A")

    with cols[4]:
        if sci_col and len(df) > 1:
            # Improvement: first half vs second half average
            mid = len(df) // 2
            early_avg = df[sci_col].iloc[:mid].mean()
            late_avg  = df[sci_col].iloc[mid:].mean()
            if early_avg > 0:
                pct = ((early_avg - late_avg) / early_avg) * 100
                st.metric("SCI Improvement", f"{pct:+.1f}%",
                          delta="vs period start",
                          delta_color="inverse",
                          help="Compares first-half vs second-half mean SCI. Negative = improvement.")
        else:
            st.metric("Data Points", str(len(df)))


def _render_energy_chart(df: pd.DataFrame, ma_window: int, show_anomalies: bool):
    """Render the energy consumption time-series chart."""
    if "energy_kwh" not in df.columns:
        return

    st.markdown("### ⚡ Energy Consumption Over Time")

    fig = go.Figure()

    # Raw trace
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["energy_kwh"],
        mode="lines", name="Energy (kWh)",
        line=dict(color=C["energy"], width=1.2),
        opacity=0.65,
        hovertemplate="<b>%{x}</b><br>%{y:.6f} kWh<extra></extra>",
    ))

    # Moving average
    ma = rolling_average(df["energy_kwh"], window=ma_window)
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=ma,
        mode="lines", name=f"Moving avg ({ma_window}pt)",
        line=dict(color=C["ma"], width=2, dash="dash"),
        hovertemplate="MA: %{y:.6f} kWh<extra></extra>",
    ))

    # Anomalies
    if show_anomalies:
        mask = detect_anomalies(df["energy_kwh"])
        anom = df[mask]
        if not anom.empty:
            fig.add_trace(go.Scatter(
                x=anom["timestamp"], y=anom["energy_kwh"],
                mode="markers", name="Anomaly",
                marker=dict(color=C["anomaly"], size=7, symbol="x-open", line=dict(width=2)),
                hovertemplate="⚠️ Anomaly<br>%{x}<br>%{y:.6f} kWh<extra></extra>",
            ))

    # Filled area under curve for visual clarity
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["energy_kwh"],
        fill="tozeroy", fillcolor="rgba(0,212,255,0.06)",
        line=dict(width=0), showlegend=False, hoverinfo="skip",
    ))

    fig.update_layout(
        height=310, hovermode="x unified",
        xaxis_title="Time", yaxis_title="Energy (kWh)",
        legend=dict(orientation="h", y=1.02),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=30, b=40, l=60, r=20),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#21262D")
    fig.update_yaxes(showgrid=True, gridcolor="#21262D")
    st.plotly_chart(fig, use_container_width=True)


def _render_sci_trend_chart(df: pd.DataFrame, ma_window: int, show_anomalies: bool):
    """Render the SCI score trend line — core dissertation evaluation chart."""
    if "sci_score" not in df.columns:
        return

    st.markdown("### 🌿 SCI Score Trend")
    st.caption(
        "SCI = (E×I+M)/R per ISO/IEC 21031. Lower is better. "
        "Target: improvement trend across the measurement period."
    )

    fig = go.Figure()

    # Rating bands (background shading)
    rating_bands = [
        (0, 10,  "rgba(0,158,115,0.06)",  "Excellent"),
        (10, 50, "rgba(86,180,233,0.06)", "Good"),
        (50, 200,"rgba(230,159,0,0.06)",  "Acceptable"),
    ]
    y_max = max(df["sci_score"].max() * 1.1, 60)
    for lo, hi, colour, label in rating_bands:
        if lo < y_max:
            fig.add_hrect(y0=lo, y1=min(hi, y_max), fillcolor=colour,
                          line_width=0, annotation_text=label,
                          annotation_position="right",
                          annotation_font_size=10,
                          annotation_font_color="#999")

    # Raw SCI
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["sci_score"],
        mode="lines+markers", name="SCI score",
        line=dict(color=C["sci"], width=1.5),
        marker=dict(size=3, color=C["sci"]),
        hovertemplate="<b>%{x}</b><br>SCI: %{y:.6f} gCO₂eq/req<extra></extra>",
    ))

    # Moving average
    ma = rolling_average(df["sci_score"], window=ma_window)
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=ma,
        mode="lines", name=f"Moving avg ({ma_window}pt)",
        line=dict(color=C["ma"], width=2.5, dash="dot"),
    ))

    # Anomalies
    if show_anomalies:
        mask = detect_anomalies(df["sci_score"])
        anom = df[mask]
        if not anom.empty:
            fig.add_trace(go.Scatter(
                x=anom["timestamp"], y=anom["sci_score"],
                mode="markers", name="Spike",
                marker=dict(color=C["anomaly"], size=8, symbol="triangle-up"),
                hovertemplate="⚠️ Spike<br>%{x}<br>SCI: %{y:.4f}<extra></extra>",
            ))

    # Trend line (linear regression)
    if len(df) >= 5:
        x_num = np.arange(len(df))
        z = np.polyfit(x_num, df["sci_score"].values, 1)
        trend_y = np.polyval(z, x_num)
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=trend_y,
            mode="lines", name="Linear trend",
            line=dict(color="#CC79A7", width=1.5, dash="longdash"),
            hoverinfo="skip",
        ))
        slope = z[0]
        direction = "📉 Improving" if slope < 0 else "📈 Worsening"
        st.caption(f"Trend: **{direction}** (slope = {slope:.6f} gCO₂eq/req per interval). "
                   "Benchmark: Gil (2024) reports 10–20% efficiency gains from well-designed green dashboards.")

    fig.update_layout(
        height=340, hovermode="x unified",
        xaxis_title="Time", yaxis_title="SCI Score (gCO₂eq/req)",
        legend=dict(orientation="h", y=1.02),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=30, b=40, l=70, r=20),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#21262D")
    fig.update_yaxes(showgrid=True, gridcolor="#21262D", rangemode="tozero")
    st.plotly_chart(fig, use_container_width=True)


def _render_carbon_breakdown_chart(df: pd.DataFrame):
    """Stacked area chart: operational vs embodied carbon over time."""
    if "operational_carbon" not in df.columns:
        return

    st.markdown("### 🌍 Carbon Breakdown Over Time")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["operational_carbon"],
        name="Operational (E×I)", fill="tozeroy",
        fillcolor="rgba(0,212,255,0.15)",
        line=dict(color=C["energy"], width=1),
        hovertemplate="Operational: %{y:.4f} gCO₂eq<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["embodied_carbon"],
        name="Embodied (M)", fill="tonexty",
        fillcolor="rgba(0,148,255,0.1)",
        line=dict(color=C["carbon"], width=1),
        hovertemplate="Embodied: %{y:.4f} gCO₂eq<extra></extra>",
    ))

    fig.update_layout(
        height=280, hovermode="x unified",
        xaxis_title="Time", yaxis_title="Carbon (gCO₂eq)",
        legend=dict(orientation="h", y=1.02),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=30, b=40, l=70, r=20),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#21262D")
    fig.update_yaxes(showgrid=True, gridcolor="#21262D")
    st.plotly_chart(fig, use_container_width=True)


def _render_correlation_scatter(df: pd.DataFrame):
    """Scatter plot: CPU% vs SCI score — shows proxy metric relationship."""
    if "cpu_percent" not in df.columns or "sci_score" not in df.columns:
        return

    st.markdown("### 🔗 CPU Utilisation vs SCI Score")
    st.caption(
        "Validates the proxy metric approach: higher CPU utilisation should correlate "
        "with higher SCI score, confirming energy estimation accuracy *(Guldner et al., 2024)*."
    )

    # trendline="ols" requires statsmodels, which is a soft dependency of
    # Plotly (not enforced at import time — it only fails when the chart is
    # actually built). Falling back to a plain scatter plot with no
    # trendline keeps this page usable even in an environment where
    # statsmodels wasn't installed (e.g. a stripped-down deployment), rather
    # than crashing the entire Energy Trend page.
    try:
        import statsmodels.api  # noqa: F401  (presence check only)
        trendline_kwargs = {"trendline": "ols"}
        trendline_available = True
    except ImportError:
        trendline_kwargs = {}
        trendline_available = False

    fig = px.scatter(
        df, x="cpu_percent", y="sci_score",
        color="rating" if "rating" in df.columns else None,
        color_discrete_map={"Excellent": "#009E73", "Good": "#56B4E9",
                            "Acceptable": "#E69F00", "Poor": "#D55E00", "Critical": "#CC0000"},
        opacity=0.6,
        labels={"cpu_percent": "CPU Utilisation (%)", "sci_score": "SCI Score (gCO₂eq/req)"},
        **trendline_kwargs,
    )
    if not trendline_available:
        st.caption(
            "ℹ️ Trend line unavailable — the `statsmodels` package is not installed "
            "in this environment. Run `pip install statsmodels` to enable it."
        )
    fig.update_layout(
        height=300, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=40, l=70, r=20),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#21262D")
    fig.update_yaxes(showgrid=True, gridcolor="#21262D")
    st.plotly_chart(fig, use_container_width=True)

    # Correlation coefficient
    corr = df["cpu_percent"].corr(df["sci_score"])
    st.caption(f"Pearson r = **{corr:.3f}** — "
               f"{'strong positive correlation, validating proxy approach ✅' if corr > 0.5 else 'moderate correlation — multiple factors influence SCI'}")
