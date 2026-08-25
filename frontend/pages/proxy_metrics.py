"""
GSEA Dashboard - Proxy Metrics Visualisation Page
===================================================
Time-series charts of CPU%, memory, network I/O, storage.
Includes moving averages and anomaly detection.
Aligned with Guldner et al. 2024 proxy measurement approach.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# Colour-blind safe palette (Okabe-Ito)
METRIC_COLOURS = {
    "cpu_percent":   "#0072B2",
    "memory_percent":"#E69F00",
    "network_rx":    "#009E73",
    "network_tx":    "#CC79A7",
    "disk_read":     "#56B4E9",
    "disk_write":    "#D55E00",
}


def _generate_sample_data(hours: int = 24, interval_minutes: int = 5) -> pd.DataFrame:
    """
    Generate realistic sample proxy metrics data for demonstration.
    In production, this data comes from the FastAPI backend (GMT CSV or CodeCarbon uploads).
    """
    n_points = (hours * 60) // interval_minutes
    timestamps = [datetime.now() - timedelta(minutes=i * interval_minutes) for i in range(n_points, 0, -1)]

    np.random.seed(42)

    # Simulate realistic CPU with daily pattern and some spikes
    base_cpu = 30 + 20 * np.sin(np.linspace(0, 4 * np.pi, n_points))
    cpu_noise = np.random.normal(0, 5, n_points)
    cpu_spikes = np.where(np.random.random(n_points) > 0.97, np.random.uniform(60, 90, n_points), 0)
    cpu = np.clip(base_cpu + cpu_noise + cpu_spikes, 2, 100)

    # Memory slowly increases with noise
    memory_gb = 2.0 + np.cumsum(np.random.normal(0, 0.01, n_points))
    memory_gb = np.clip(memory_gb, 0.5, 8.0)
    memory_pct = (memory_gb / 8.0) * 100

    # Network I/O correlated with CPU
    network_rx = np.clip(cpu * 0.3 + np.random.exponential(5, n_points), 0, 200)
    network_tx = np.clip(cpu * 0.15 + np.random.exponential(2, n_points), 0, 100)

    return pd.DataFrame({
        "timestamp": timestamps,
        "cpu_percent": cpu,
        "memory_gb": memory_gb,
        "memory_percent": memory_pct,
        "network_rx_mb": network_rx,
        "network_tx_mb": network_tx,
    })


def _add_moving_average(df: pd.DataFrame, column: str, window: int = 12) -> pd.Series:
    """Calculate rolling moving average."""
    return df[column].rolling(window=window, center=True).mean()


def _detect_anomalies(series: pd.Series, threshold_sigma: float = 2.5) -> pd.Series:
    """Flag values beyond threshold_sigma standard deviations as anomalies."""
    mean = series.mean()
    std = series.std()
    return (series - mean).abs() > (threshold_sigma * std)


def render_proxy_metrics():
    """Render the Proxy Metrics visualisation page.  Ch.5 §5.3.2 — Proxy Metric Visualisation (MUST)."""

    st.markdown("## 📈 Proxy Metric Visualisation")
    st.markdown(
        "Time-series visualisation of system-level proxy metrics — CPU utilisation, "
        "memory, and network I/O. These proxy measurements are used to estimate energy "
        "consumption when direct measurement (e.g., RAPL) is unavailable *(Guldner et al., 2024)*."
    )

    # ── Data Source ────────────────────────────────────────────────────────
    st.markdown("### Data Source")

    data_source = st.radio(
        "Select data source",
        ["Use sample data (demonstration)", "Upload CSV"],
        horizontal=True,
    )

    df = None

    if data_source == "Use sample data (demonstration)":
        time_range = st.selectbox("Sample data time range", ["Last 6 hours", "Last 24 hours", "Last 7 days"])
        hours_map = {"Last 6 hours": 6, "Last 24 hours": 24, "Last 7 days": 168}
        df = _generate_sample_data(hours=hours_map[time_range])
        st.info(f"Showing {len(df)} sample data points. Upload real data for actual analysis.", icon="ℹ️")

    else:
        uploaded_file = st.file_uploader(
            "Upload metrics CSV",
            type=["csv"],
            help="Expected columns: timestamp, cpu_percent, memory_gb, memory_percent, network_rx_mb, network_tx_mb"
        )
        if uploaded_file:
            try:
                import sys
                from pathlib import Path
                sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                from frontend.components.data_manager import parse_gmt_csv
                raw = pd.read_csv(uploaded_file)
                # Normalise column names before parsing (Fix 3)
                raw.columns = [c.strip().lower().replace(" ","_").replace("-","_")
                               for c in raw.columns]
                # Ensure memory_mb exists — fall back from common alternatives
                for alt in ["memory_usage_mb","mem_mb","memory","ram_mb","memory_bytes"]:
                    if alt in raw.columns and "memory_mb" not in raw.columns:
                        raw["memory_mb"] = pd.to_numeric(raw[alt], errors="coerce")
                        if alt == "memory_bytes":
                            raw["memory_mb"] = raw["memory_mb"] / (1024*1024)
                        break
                df = parse_gmt_csv(raw)
                st.success(f"✅ Loaded and SCI-scored **{len(df)} rows** from `{uploaded_file.name}`")
            except Exception as e:
                st.error(f"Error loading file: {e}")
                import traceback
                with st.expander("Show error details"):
                    st.code(traceback.format_exc())

    if df is None:
        st.warning("No data loaded. Select a data source above.")
        return

    st.divider()

    # ── Filters ────────────────────────────────────────────────────────────
    st.markdown("### Filters")
    filter_cols = st.columns(3)

    with filter_cols[0]:
        show_ma = st.toggle("Show moving average", value=True)
        ma_window = st.slider("Moving average window (points)", 5, 30, 12, disabled=not show_ma)

    with filter_cols[1]:
        show_anomalies = st.toggle("Highlight anomalies", value=True)
        anomaly_sigma = st.slider("Anomaly threshold (σ)", 1.5, 4.0, 2.5, step=0.25, disabled=not show_anomalies)

    with filter_cols[2]:
        metrics_to_show = st.multiselect(
            "Metrics to display",
            ["CPU %", "Memory %", "Network RX (MB)", "Network TX (MB)"],
            default=["CPU %", "Memory %"],
        )

    st.divider()

    # ── Summary Statistics ─────────────────────────────────────────────────
    st.markdown("### Summary Statistics")
    stat_cols = st.columns(4)

    with stat_cols[0]:
        st.metric("Avg CPU %", f"{df['cpu_percent'].mean():.1f}%",
                  delta=f"Max: {df['cpu_percent'].max():.1f}%")
    with stat_cols[1]:
        st.metric("Avg Memory %", f"{df['memory_percent'].mean():.1f}%",
                  delta=f"Max: {df['memory_percent'].max():.1f}%")
    with stat_cols[2]:
        st.metric("Total Network RX", f"{df['network_rx_mb'].sum():.1f} MB")
    with stat_cols[3]:
        # Estimate energy from proxy metrics
        avg_cpu = df["cpu_percent"].mean() / 100
        duration_hours = (df["timestamp"].max() - df["timestamp"].min()).total_seconds() / 3600
        est_energy = (65 * avg_cpu * duration_hours) / 1000  # TDP 65W
        st.metric("Est. Energy", f"{est_energy:.4f} kWh",
                  help="Estimated: TDP × CPU_fraction × duration. Click SCI Calculator to compute full SCI.")

    st.divider()

    # ── Charts ─────────────────────────────────────────────────────────────
    st.markdown("### Time-Series Charts")

    metric_map = {
        "CPU %": ("cpu_percent", "CPU Utilisation (%)", METRIC_COLOURS["cpu_percent"]),
        "Memory %": ("memory_percent", "Memory Utilisation (%)", METRIC_COLOURS["memory_percent"]),
        "Network RX (MB)": ("network_rx_mb", "Network Received (MB)", METRIC_COLOURS["network_rx"]),
        "Network TX (MB)": ("network_tx_mb", "Network Transmitted (MB)", METRIC_COLOURS["network_tx"]),
    }

    for metric_label in metrics_to_show:
        if metric_label not in metric_map:
            continue

        col, title, colour = metric_map[metric_label]
        if col not in df.columns:
            st.warning(f"Column '{col}' not found in data.")
            continue

        fig = go.Figure()

        # Raw data
        fig.add_trace(go.Scatter(
            x=df["timestamp"],
            y=df[col],
            mode="lines",
            name=metric_label,
            line=dict(color=colour, width=1.5),
            opacity=0.7,
            hovertemplate=f"<b>{metric_label}</b><br>%{{x}}<br>%{{y:.2f}}<extra></extra>",
        ))

        # Moving average
        if show_ma:
            ma = _add_moving_average(df, col, window=ma_window)
            fig.add_trace(go.Scatter(
                x=df["timestamp"],
                y=ma,
                mode="lines",
                name=f"Moving Avg ({ma_window}pt)",
                line=dict(color="rgba(0,0,0,0.6)", width=2, dash="dash"),
                hovertemplate="MA: %{y:.2f}<extra></extra>",
            ))

        # Anomalies
        if show_anomalies:
            anomalies = _detect_anomalies(df[col], threshold_sigma=anomaly_sigma)
            anomaly_df = df[anomalies]
            if not anomaly_df.empty:
                fig.add_trace(go.Scatter(
                    x=anomaly_df["timestamp"],
                    y=anomaly_df[col],
                    mode="markers",
                    name="Anomaly",
                    marker=dict(color="#D55E00", size=8, symbol="x"),
                    hovertemplate="<b>⚠️ Anomaly</b><br>%{x}<br>%{y:.2f}<extra></extra>",
                ))

        fig.update_layout(
            title=dict(text=title, font_size=15),
            xaxis_title="Time",
            yaxis_title=title,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(t=60, b=40, l=60, r=20),
            height=280,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig.update_xaxes(showgrid=True, gridcolor="#21262D")
        fig.update_yaxes(showgrid=True, gridcolor="#21262D")

        st.plotly_chart(fig, use_container_width=True)

    # ── Energy Estimation from Proxy ────────────────────────────────────────
    st.divider()
    st.markdown("### ⚡ Energy Estimation from Proxy Metrics")
    st.markdown(
        "Based on the proxy metrics above, estimate energy consumption "
        "and proceed to full SCI calculation."
    )

    col_btn1, col_btn2 = st.columns([1, 2])
    with col_btn1:
        if st.button("📊 Estimate SCI from this data", type="primary", key="proxy_to_sci"):
            avg_cpu = df["cpu_percent"].mean()
            mem_col = "memory_gb" if "memory_gb" in df.columns else None
            avg_mem = df[mem_col].mean() if mem_col else 2.0
            duration_h = max(0.01, (
                df["timestamp"].max() - df["timestamp"].min()
            ).total_seconds() / 3600)
            # Fix 8: store prefill AND navigate to SCI Calculator proxy tab
            st.session_state["proxy_prefill"] = {
                "cpu_percent": round(avg_cpu, 1),
                "memory_gb":   round(float(avg_mem), 2),
                "duration_hours": round(duration_h, 2),
            }
            st.session_state["sci_mode_override"] = "proxy"
            st.session_state["nav_request"] = "📊  SCI Calculator"
            st.rerun()
    with col_btn2:
        avg_cpu_val = df["cpu_percent"].mean() if not df.empty else 0
        duration_val = max(0.01, (
            df["timestamp"].max() - df["timestamp"].min()
        ).total_seconds() / 3600) if not df.empty else 0
        st.markdown(f"""
        <div style="padding:.5rem 0;font-size:.78rem;color:#7D8590;">
            Will pre-fill: CPU = <strong style="color:#00D4FF;">{avg_cpu_val:.1f}%</strong> ·
            Duration = <strong style="color:#00D4FF;">{duration_val:.2f}h</strong>
            → then jump to SCI Calculator (Proxy tab)
        </div>""", unsafe_allow_html=True)
