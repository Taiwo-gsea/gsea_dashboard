"""
GSEA Dashboard - Data Ingestion Page
======================================
Multi-source data ingestion with end-to-end SCI pipeline wiring.
Uploaded files are parsed → SCI-scored → stored in session state
so Energy Trend, Comparative Analysis and Reports pages
can use them immediately without re-uploading.

MoSCoW: MUST — Multi-source Data Ingestion
Ch.5 §5.3.3
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from frontend.components.data_manager import (
    parse_gmt_csv, parse_codecarbon_csv,
    CARBON_INTENSITY_DEFAULTS,
)

GMT_EXPECTED  = ["timestamp", "cpu_percent", "memory_mb", "network_io_kb", "energy_kwh"]
CC_SIGNATURE  = {"emissions", "energy_consumed", "cpu_power"}


# ── session-state key used across all pages ─────────────────────────────
SS_PARSED = "parsed_datasets"   # list[dict] — {label, source, df, n_rows, ingested_at}


def _store(label: str, source: str, df: pd.DataFrame) -> None:
    """Push a fully-parsed, SCI-scored DataFrame into the shared session store."""
    if SS_PARSED not in st.session_state:
        st.session_state[SS_PARSED] = []
    # de-duplicate by label
    st.session_state[SS_PARSED] = [
        d for d in st.session_state[SS_PARSED] if d["label"] != label
    ]
    st.session_state[SS_PARSED].append({
        "label":       label,
        "source":      source,
        "df":          df,
        "n_rows":      len(df),
        "ingested_at": datetime.now().strftime("%H:%M:%S"),
    })


def render_data_ingestion():
    """Render the Data Ingestion page.  Ch.5 §5.3.3"""

    st.markdown("""
    <div class="page-header">
        <div class="page-header-left">
            <div class="page-title">📂 Data Ingestion</div>
            <span class="page-tab active">Upload</span>
            <span class="page-tab inactive">Manual</span>
        </div>
        <span class="badge badge-green">MUST Feature</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(
        "Import energy and carbon metrics from **Green Metrics Tool (GMT)**, "
        "**CodeCarbon**, or manual entry. Every uploaded file is automatically "
        "parsed and SCI-scored so results are immediately available in "
        "**Energy Trend**, **Comparative Analysis**, and **Reports**."
    )

    # ── Active datasets panel ────────────────────────────────────────────
    _render_active_datasets()

    st.divider()

    tab1, tab2, tab3 = st.tabs(["📁 GMT CSV", "🐍 CodeCarbon CSV", "✏️ Manual Entry"])
    with tab1:  _render_gmt_tab()
    with tab2:  _render_codecarbon_tab()
    with tab3:  _render_manual_tab()


# ── Active datasets ──────────────────────────────────────────────────────

def _render_active_datasets():
    datasets = st.session_state.get(SS_PARSED, [])
    if not datasets:
        st.info("No datasets loaded yet. Upload a file below or use the sample data in **Energy Trend Analysis**.", icon="ℹ️")
        return

    st.markdown(f"### ✅ {len(datasets)} dataset(s) loaded this session")
    cols = st.columns(len(datasets))
    for i, ds in enumerate(datasets):
        with cols[i]:
            st.metric(ds["label"], f"{ds['n_rows']} rows", ds["source"])
            st.caption(f"Loaded at {ds['ingested_at']}")

    if st.button("🗑️ Clear all datasets", width="content"):
        st.session_state[SS_PARSED] = []
        st.rerun()


# ── GMT upload tab ───────────────────────────────────────────────────────

def _render_gmt_tab():
    st.markdown("### Green Metrics Tool (GMT) CSV")
    st.markdown(
        "Export a CSV from [Green Metrics Tool](https://www.green-coding.io) "
        "and upload here. The dashboard auto-detects columns and estimates "
        "any missing `energy_kwh` values from CPU proxy metrics."
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        uploaded = st.file_uploader("Upload GMT CSV", type=["csv"], key="gmt_upload")
    with col2:
        region = st.selectbox(
            "Grid region",
            list(CARBON_INTENSITY_DEFAULTS.keys()),
            index=0,
            format_func=lambda k: f"{k} ({CARBON_INTENSITY_DEFAULTS[k]} gCO₂/kWh)",
            key="gmt_region",
        )

    if uploaded is None:
        return

    try:
        raw = pd.read_csv(uploaded)
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        return

    # Fix 7: Auto-detect if this is actually a CodeCarbon file
    detected_lower = set(raw.columns.str.lower().str.strip())
    if CC_SIGNATURE & detected_lower:
        st.info(
            "🔍 **Auto-detected:** This looks like a **CodeCarbon** file "
            "(contains `emissions`, `energy_consumed`, `cpu_power`). "
            "Switch to the **🐍 CodeCarbon CSV** tab for best results.",
            icon="🔍"
        )

    st.success(f"✅ Read **{len(raw)} rows** · **{len(raw.columns)} columns** from `{uploaded.name}`")

    # column detection
    detected   = [col.lower().strip() for col in raw.columns]
    missing    = [col for col in GMT_EXPECTED if col not in detected]
    if missing:
        st.warning(f"⚠️ Missing expected columns: `{', '.join(missing)}` — they will be estimated where possible.")
    else:
        st.success("✅ All expected GMT columns detected.")

    st.dataframe(raw.head(5), width="stretch")

    if st.button("💾 Ingest & Score GMT Data", type="primary", width="stretch", key="gmt_ingest"):
        with st.spinner("Parsing and running SCI pipeline…"):
            scored = parse_gmt_csv(raw, region=region)
            label  = f"GMT · {uploaded.name[:20]} · {region}"
            _store(label, "gmt_csv", scored)

        st.success(
            f"✅ **{len(scored)} records** parsed and SCI-scored. "
            f"Mean SCI = **{scored['sci_score'].mean():.5f}** gCO₂eq/req. "
            "Available immediately in Energy Trend and Comparative Analysis."
        )
        _show_quick_stats(scored)


# ── CodeCarbon upload tab ────────────────────────────────────────────────

def _render_codecarbon_tab():
    st.markdown("### CodeCarbon `emissions.csv`")
    st.markdown(
        "Upload the CSV output from a [CodeCarbon](https://codecarbon.io) "
        "experiment. All energy, emissions, and regional data are mapped "
        "automatically to the SCI schema."
    )

    uploaded = st.file_uploader("Upload CodeCarbon CSV", type=["csv"], key="cc_upload")
    if uploaded is None:
        return

    try:
        raw = pd.read_csv(uploaded)
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        return

    cols_lower = set(raw.columns.str.lower())
    is_cc = bool(CC_SIGNATURE & cols_lower)

    # Fix 7: Warn if GMT file uploaded here by mistake
    if not is_cc and any(col in cols_lower for col in ["cpu_percent","memory_mb","network_io_kb"]):
        st.info(
            "🔍 **Auto-detected:** This looks like a **Green Metrics Tool** file. "
            "Switch to the **📁 GMT CSV** tab for best results.",
            icon="🔍"
        )

    if is_cc:
        st.success(f"✅ CodeCarbon format detected · **{len(raw)} runs**")
    else:
        st.warning("⚠️ File does not match standard CodeCarbon columns — best-effort parsing.")

    st.dataframe(raw.head(5), width="stretch")

    if is_cc:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total emissions", f"{raw['emissions'].sum()*1000:.4f} gCO₂eq")
        col2.metric("Total energy",    f"{raw['energy_consumed'].sum():.6f} kWh")
        if "duration" in raw.columns:
            col3.metric("Total duration", f"{raw['duration'].sum():.0f} s")

    if st.button("💾 Ingest & Score CodeCarbon Data", type="primary", width="stretch", key="cc_ingest"):
        with st.spinner("Parsing and running SCI pipeline…"):
            scored = parse_codecarbon_csv(raw)
            label  = f"CodeCarbon · {uploaded.name[:20]}"
            _store(label, "codecarbon", scored)

        st.success(
            f"✅ **{len(scored)} records** ingested and SCI-scored. "
            f"Mean SCI = **{scored['sci_score'].mean():.5f}** gCO₂eq/req. "
            "Available in Energy Trend and Comparative Analysis."
        )
        _show_quick_stats(scored)


# ── Manual entry tab ─────────────────────────────────────────────────────

def _render_manual_tab():
    st.markdown("### Manual Metric Entry")
    st.markdown("Enter proxy metrics manually — useful for ad-hoc calculations or when automated tools are unavailable.")

    with st.form("manual_entry_form"):
        c1, c2 = st.columns(2)
        with c1:
            component  = st.text_input("Software component", placeholder="e.g., api-server")
            env        = st.selectbox("Deployment environment", ["cloud", "on-premise", "edge", "hybrid"])
            mdate      = st.date_input("Date", value=datetime.today())
        with c2:
            region     = st.selectbox("Grid region", list(CARBON_INTENSITY_DEFAULTS.keys()),
                                      format_func=lambda k: f"{k} ({CARBON_INTENSITY_DEFAULTS[k]} gCO₂/kWh)")
            cpu_pct    = st.number_input("CPU % (avg)", 0.0, 100.0, 45.0, step=0.5)
            mem_gb     = st.number_input("Memory in use (GB)", 0.0, 1024.0, 2.0, step=0.1)
            duration_h = st.number_input("Duration (hours)", 0.01, 8760.0, 1.0, step=0.25)

        c3, c4 = st.columns(2)
        with c3:
            r_value = st.number_input("R — Functional unit", 0.001, value=1000.0, step=100.0)
            r_label = st.text_input("R label", value="request")
        with c4:
            notes = st.text_area("Notes", placeholder="Any relevant context…")

        submitted = st.form_submit_button("💾 Save & Score Entry", type="primary")

    if submitted:
        from backend.services.sci_calculator import SCICalculator, SCIComponents, CARBON_INTENSITY_DEFAULTS as CI_D, EMBODIED_CARBON_DEFAULTS as EM_D

        ci          = CI_D.get(region, 233.0)
        energy_kwh  = (65 * (cpu_pct / 100) * duration_h) / 1000
        prorated_m  = EM_D["cloud_vm_small"] * (duration_h / (3 * 365 * 24))

        try:
            comp   = SCIComponents(energy_kwh=energy_kwh, carbon_intensity=ci,
                                   embodied_carbon=prorated_m, functional_unit=r_value,
                                   functional_unit_label=r_label, region=region)
            result = SCICalculator().calculate(comp)
            entry  = {
                "timestamp":          pd.Timestamp(mdate),
                "software_component": component or "manual",
                "cpu_percent":        cpu_pct,
                "memory_gb":          mem_gb,
                "duration_hours":     duration_h,
                "energy_kwh":         energy_kwh,
                "carbon_intensity":   ci,
                "region":             region,
                "deployment_env":     env,
                "sci_score":          result.sci_score,
                "operational_carbon": result.operational_carbon,
                "embodied_carbon":    result.embodied_carbon,
                "total_carbon":       result.total_carbon,
                "rating":             result.get_rating(),
                "notes":              notes,
            }
            new_df = pd.DataFrame([entry])

            # Append to existing manual dataset or create new one
            existing = next((d for d in st.session_state.get(SS_PARSED, []) if d["source"] == "manual"), None)
            if existing:
                merged = pd.concat([existing["df"], new_df], ignore_index=True)
                _store("Manual entries", "manual", merged)
            else:
                _store("Manual entries", "manual", new_df)

            st.success(
                f"✅ Entry saved for **{component or 'component'}** — "
                f"SCI = **{result.sci_score:.5f}** gCO₂eq/{r_label} "
                f"({result.get_rating()})"
            )
        except Exception as e:
            st.error(f"Calculation error: {e}")

    # Show saved manual entries
    datasets = st.session_state.get(SS_PARSED, [])
    manual   = next((d for d in datasets if d["source"] == "manual"), None)
    if manual:
        st.markdown("#### Saved manual entries this session")
        show_cols = ["timestamp", "software_component", "sci_score", "rating", "cpu_percent", "energy_kwh", "region"]
        display_cols = [c for c in show_cols if c in manual["df"].columns]
        st.dataframe(manual["df"][display_cols], use_container_width=True)


# ── Quick stats helper ───────────────────────────────────────────────────

def _show_quick_stats(df: pd.DataFrame) -> None:
    """Show a 4-metric summary row after ingestion."""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows ingested",  len(df))
    c2.metric("Mean SCI",       f"{df['sci_score'].mean():.5f}")
    c3.metric("Min SCI",        f"{df['sci_score'].min():.5f}")
    if "total_carbon" in df.columns:
        c4.metric("Total carbon", f"{df['total_carbon'].sum():.3f} gCO₂eq")
    else:
        c4.metric("Max SCI",    f"{df['sci_score'].max():.5f}")
