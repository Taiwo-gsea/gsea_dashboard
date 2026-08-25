"""
GSEA Dashboard - Comparative Analysis Page
============================================
Compare SCI scores across software versions, configurations,
or deployment environments. Includes delta charts and tables.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.sci_calculator import (
    SCICalculator, SCIComponents,
)

calculator = SCICalculator()
COLOURS = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9"]


def render_comparative_analysis():
    """Render the Comparative Analysis page.  Ch.5 §5.3.4 — Comparative Baseline View (SHOULD)."""

    st.markdown("""
    <div class="page-header">
        <div class="page-header-left">
            <div class="page-title">⚖️ Comparative Analysis</div>
            <span class="page-tab active">Compare</span>
            <span class="page-tab inactive">History</span>
        </div>
        <span class="badge badge-cyan">SHOULD Feature</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(
        "Compare SCI scores across software versions, deployment environments, "
        "or hardware configurations. Identify which configuration minimises carbon intensity."
    )

    # ── Session results ────────────────────────────────────────────────────
    session_results = st.session_state.get("sci_results", [])

    tab1, tab2 = st.tabs(["📊 Compare Configurations", "📈 Session Results History"])

    with tab1:
        _render_configuration_comparison()

    with tab2:
        _render_session_history(session_results)


def _render_configuration_comparison():
    """Interactive comparison tool for multiple SCI configurations."""

    st.markdown("### Configure Comparison")
    st.markdown("Add 2–6 configurations to compare side-by-side.")

    n_configs = st.slider("Number of configurations to compare", 2, 6, 3)

    configs = []
    labels = []

    with st.expander("Enter configurations", expanded=True):
        for i in range(n_configs):
            st.markdown(f"**Configuration {i+1}**")
            cols = st.columns(5)

            with cols[0]:
                label = st.text_input("Label", value=f"Config {i+1}", key=f"label_{i}")
            with cols[1]:
                energy = st.number_input("E (kWh)", 0.0001, value=round(0.3 + i * 0.2, 2),
                                         step=0.01, format="%.4f", key=f"e_{i}")
            with cols[2]:
                ci = st.number_input("I (gCO₂/kWh)", 1.0, value=float([233, 56, 386][i % 3]),
                                     step=1.0, key=f"i_{i}")
            with cols[3]:
                mc = st.number_input("M (gCO₂)", 0.0, value=10000.0, step=100.0, key=f"m_{i}")
            with cols[4]:
                r = st.number_input("R (unit)", 0.001, value=1000.0, step=1.0, key=f"r_{i}")

            labels.append(label)
            try:
                configs.append(SCIComponents(
                    energy_kwh=energy,
                    carbon_intensity=ci,
                    embodied_carbon=mc,
                    functional_unit=r,
                    functional_unit_label="request",
                ))
            except ValueError:
                st.error(f"Invalid values for Configuration {i+1}")

    if st.button("📊 Compare", type="primary") and len(configs) == n_configs:
        results = calculator.compare_configurations(configs, labels)

        # Bar chart
        fig = go.Figure()
        for j, res in enumerate(results):
            fig.add_trace(go.Bar(
                name=res["label"],
                x=[res["label"]],
                y=[res["sci_score"]],
                marker_color=COLOURS[j % len(COLOURS)],
                text=[f"{res['sci_score']:.4f}"],
                textposition="outside",
                hovertemplate=(
                    f"<b>{res['label']}</b><br>"
                    f"SCI: {res['sci_score']:.6f} gCO₂eq/request<br>"
                    f"Rating: {res['rating']}<extra></extra>"
                ),
            ))

        fig.update_layout(
            title="SCI Score Comparison",
            yaxis_title="SCI Score (gCO₂eq/request)",
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            height=400,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Results table
        st.markdown("#### Comparison Table")
        table_data = [{
            "Configuration": r["label"],
            "SCI Score": f"{r['sci_score']:.6f}",
            "Operational C (gCO₂eq)": f"{r['operational_carbon_gco2eq']:.3f}",
            "Embodied C (gCO₂eq)": f"{r['embodied_carbon_gco2eq']:.3f}",
            "Op %": f"{r['operational_pct']}%",
            "Rating": r["rating"],
        } for r in results]
        st.dataframe(pd.DataFrame(table_data), width="stretch")

        # Best/worst analysis
        best = results[0]
        worst = results[-1]
        if len(results) > 1:
            improvement = ((worst["sci_score"] - best["sci_score"]) / worst["sci_score"]) * 100
            st.success(
                f"✅ **{best['label']}** has the lowest SCI score ({best['sci_score']:.4f}). "
                f"Switching from {worst['label']} to {best['label']} reduces carbon intensity by "
                f"**{improvement:.1f}%** — benchmark: Gil (2024) reports 10–20% efficiency gains "
                f"from well-designed green dashboards."
            )


def _render_session_history(session_results: list):
    """Render SCI history from both the calculator and ingested datasets."""

    st.markdown("### SCI Score History (This Session)")

    # Also pull from ingested parsed datasets
    datasets = st.session_state.get("parsed_datasets", [])
    ingested_results = []
    for ds in datasets:
        df = ds["df"]
        if "sci_score" in df.columns:
            # Fix 9: Cap at 500 rows to prevent UI freeze on large uploads
            sample = df.head(500)
            for _, row in sample.iterrows():
                ingested_results.append({
                    "method": ds["source"],
                    "sci_score": row["sci_score"],
                    "operational_carbon_gco2eq": row.get("operational_carbon", 0),
                    "embodied_carbon_gco2eq": row.get("embodied_carbon", 0),
                    "total_carbon_gco2eq": row.get("total_carbon", 0),
                    "functional_unit_label": row.get("functional_unit_label", "req"),
                    "rating": row.get("rating", "—"),
                    "source_label": ds["label"],
                })
            if len(df) > 500:
                ingested_results.append({
                    "method": "info",
                    "sci_score": None,
                    "source_label": f"⚠️ {ds['label']}: showing 500/{len(df)} rows",
                })

    all_results = session_results + ingested_results

    if not all_results:
        st.info("No calculations yet. Use the **SCI Calculator** page or upload data via **Data Ingestion**.")
        return

    session_results = all_results  # shadow for rest of function

    df = pd.DataFrame([{
        "Method": r.get("method", "—"),
        "SCI Score": round(r["sci_score"], 6),
        "Op Carbon (gCO₂eq)": round(r["operational_carbon_gco2eq"], 4),
        "Embodied Carbon (gCO₂eq)": round(r["embodied_carbon_gco2eq"], 4),
        "Functional Unit": r["functional_unit_label"],
        "Rating": r.get("rating", "—"),
    } for r in session_results])

    st.dataframe(df, use_container_width=True)

    # Trend chart
    if len(session_results) > 1:
        fig = px.line(
            df,
            y="SCI Score",
            markers=True,
            title="SCI Score Trend (Session)",
            color_discrete_sequence=["#0072B2"],
        )
        fig.update_layout(xaxis_title="Calculation #", height=300, plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
