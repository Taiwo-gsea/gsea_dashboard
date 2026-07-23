"""
GSEA Dashboard - Reports & Export Page
========================================
Export dashboard state, SCI results, and session data
as CSV or JSON for stakeholder sharing.
Addresses SOGS 2023 need for shareable green software reports.
"""

import streamlit as st
import pandas as pd
import json
from datetime import datetime
import io


def render_reports():
    """Render the Reports & Export page.  Ch.5 §5.3.7 — Reports & Export (SHOULD)."""

    st.markdown("""
    <div class="page-header">
        <div class="page-header-left">
            <div class="page-title">📋 Reports & Export</div>
            <span class="page-tab active">Export</span>
            <span class="page-tab inactive">Summary</span>
        </div>
        <span class="badge badge-grey">CSV · JSON</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(
        "Export your SCI analysis results and session data for stakeholder reporting. "
        "All exports include methodology notes aligned with ISO/IEC 21031 and GSF SOGS 2023."
    )

    tab1, tab2 = st.tabs(["📊 Export SCI Results", "📄 Session Summary"])

    with tab1:
        _render_export_tab()

    with tab2:
        _render_session_summary()


def _render_export_tab():
    """Render export options — pulls from SCI Calculator AND all ingested datasets."""

    sci_results  = st.session_state.get("sci_results", [])
    datasets     = st.session_state.get("parsed_datasets", [])

    # Flatten ingested datasets into SCI-result dicts for unified export
    ingested_results = []
    for ds in datasets:
        df = ds["df"]
        if "sci_score" not in df.columns:
            continue
        for _, row in df.iterrows():
            ingested_results.append({
                "sci_score":                  row.get("sci_score", 0),
                "operational_carbon_gco2eq":  row.get("operational_carbon", 0),
                "embodied_carbon_gco2eq":     row.get("embodied_carbon", 0),
                "total_carbon_gco2eq":        row.get("total_carbon", 0),
                "functional_unit":            row.get("functional_unit", 1000),
                "functional_unit_label":      row.get("functional_unit_label", "req"),
                "rating":                     row.get("rating", "—"),
                "inputs": {
                    "energy_kwh":                    row.get("energy_kwh", 0),
                    "carbon_intensity_gco2eq_kwh":   row.get("carbon_intensity", 0),
                    "region":                        row.get("region", "—"),
                },
                "method": ds["source"],
                "source_label": ds["label"],
            })

    all_results = sci_results + ingested_results

    if not all_results:
        st.info(
            "No results to export yet. Use the **SCI Calculator** to compute scores "
            "or upload data via **Data Ingestion**."
        )
        return

    st.markdown(f"**{len(all_results)} SCI records** available for export "
                f"({len(sci_results)} from calculator · {len(ingested_results)} from uploads).")
    sci_results = all_results  # unified

    if sci_results:
        df = pd.DataFrame([{
            "SCI Score (gCO₂eq/unit)": round(r["sci_score"], 8),
            "Operational Carbon (gCO₂eq)": round(r["operational_carbon_gco2eq"], 4),
            "Embodied Carbon (gCO₂eq)": round(r["embodied_carbon_gco2eq"], 4),
            "Total Carbon (gCO₂eq)": round(r["total_carbon_gco2eq"], 4),
            "Functional Unit": r["functional_unit"],
            "Functional Unit Label": r["functional_unit_label"],
            "Rating": r.get("rating", "—"),
            "Energy (kWh)": r["inputs"]["energy_kwh"],
            "Carbon Intensity (gCO₂/kWh)": r["inputs"]["carbon_intensity_gco2eq_kwh"],
            "Region": r["inputs"].get("region", "—"),
            "Method": r.get("method", "—"),
        } for r in sci_results])

        st.dataframe(df, use_container_width=True)

        col1, col2 = st.columns(2)

        with col1:
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            st.download_button(
                label="⬇️ Download as CSV",
                data=csv_buffer.getvalue(),
                file_name=f"gsea_sci_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                width="stretch",
            )

        with col2:
            export_data = {
                "export_metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "app_version": "1.0.0",
                    "sci_standard": "ISO/IEC 21031",
                    "formula": "SCI = (E × I + M) / R",
                    "records": len(sci_results),
                },
                "results": sci_results,
            }
            st.download_button(
                label="⬇️ Download as JSON",
                data=json.dumps(export_data, indent=2, default=str),
                file_name=f"gsea_sci_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                width="stretch",
            )


def _render_session_summary():
    """Render a summary of all session activity."""

    st.markdown("### Session Summary")

    datasets = st.session_state.get("parsed_datasets", [])
    ingested = [d for d in datasets if d.get("source") != "manual"]
    sci_results = st.session_state.get("sci_results", [])
    nlp_entities = st.session_state.get("nlp_entities", [])
    manual_ds = next((d for d in datasets if d.get("source") == "manual"), None)
    manual_entries = manual_ds["df"].to_dict("records") if manual_ds else []

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("SCI Calculations", len(sci_results))
    col2.metric("Data Sources Ingested", len(ingested))
    col3.metric("NLP Entities Extracted", len(nlp_entities))
    col4.metric("Manual Entries", len(manual_entries))

    if sci_results:
        best = min(sci_results, key=lambda x: x["sci_score"])
        worst = max(sci_results, key=lambda x: x["sci_score"])
        st.markdown(f"""
        - **Best SCI score this session:** `{best['sci_score']:.6f}` gCO₂eq/{best['functional_unit_label']}
        - **Worst SCI score this session:** `{worst['sci_score']:.6f}` gCO₂eq/{worst['functional_unit_label']}
        """)

    st.caption(
        "Data shown is session-only. For persistence across sessions, "
        "connect the FastAPI backend with SQLite/PostgreSQL database."
    )
