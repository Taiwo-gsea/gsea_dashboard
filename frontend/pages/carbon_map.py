"""
GSEA Dashboard - Carbon Intensity Map Page
============================================
SHOULD feature: Choropleth map of carbon intensity by region,
showing how grid location affects SCI scores.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.sci_calculator import CARBON_INTENSITY_DEFAULTS

# ISO-3166 alpha-3 country codes for choropleth mapping
REGION_TO_ISO3 = {
    "UK":     "GBR",
    "EU_avg": None,
    "US_avg": "USA",
    "DE":     "DEU",
    "FR":     "FRA",
    "NO":     "NOR",
    "IN":     "IND",
    "CN":     "CHN",
    "global": None,
}

REGION_NAMES = {
    "UK":     "United Kingdom",
    "EU_avg": "EU Average",
    "US_avg": "United States",
    "DE":     "Germany",
    "FR":     "France",
    "NO":     "Norway",
    "IN":     "India",
    "CN":     "China",
    "global": "Global Average",
}


def render_carbon_map():
    """Render the Carbon Intensity Map page.  Ch.5 §5.3.6 — Carbon Intensity Map (SHOULD)."""

    st.markdown("""
    <div class="page-header">
        <div class="page-header-left">
            <div class="page-title">🗺️ Carbon Intensity Map</div>
            <span class="page-tab active">Map</span>
            <span class="page-tab inactive">Compare</span>
        </div>
        <span class="badge badge-cyan">SHOULD Feature</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(
        "Grid carbon intensity (I in the SCI formula) varies dramatically by region. "
        "This map shows how choosing a greener deployment region directly lowers your SCI score. "
        "Source: *Electricity Maps 2024 regional averages*."
    )

    # Build display DataFrame
    rows = []
    for region, ci in CARBON_INTENSITY_DEFAULTS.items():
        iso3 = REGION_TO_ISO3.get(region)
        name = REGION_NAMES.get(region, region)
        rows.append({
            "region_key": region,
            "country": name,
            "iso_alpha3": iso3,
            "carbon_intensity": ci,
        })
    df = pd.DataFrame(rows)
    df_mapped = df.dropna(subset=["iso_alpha3"])

    # ── Choropleth map ─────────────────────────────────────────────────────
    fig = go.Figure(data=go.Choropleth(
        locations=df_mapped["iso_alpha3"],
        z=df_mapped["carbon_intensity"],
        text=df_mapped["country"],
        colorscale=[
            [0.0,  "#009E73"],   # Dark green — very low carbon
            [0.2,  "#56B4E9"],   # Sky blue
            [0.45, "#F0E442"],   # Yellow
            [0.70, "#E69F00"],   # Orange
            [1.0,  "#D55E00"],   # Red — very high carbon
        ],
        autocolorscale=False,
        reversescale=False,
        marker_line_color="white",
        marker_line_width=0.5,
        colorbar_title="gCO₂eq<br>/kWh",
        hovertemplate="<b>%{text}</b><br>%{z:.0f} gCO₂eq/kWh<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text="Grid Carbon Intensity by Country (gCO₂eq/kWh)", font_size=15),
        geo=dict(
            showframe=False,
            showcoastlines=True,
            coastlinecolor="lightgrey",
            projection_type="natural earth",
            bgcolor="white",
        ),
        height=460,
        margin=dict(t=50, b=10, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Fix 6: Visible anchor button so users don't miss the comparison tool
    st.markdown("""
    <div style="background:#161B22;border:1px solid #21262D;border-radius:8px;
                padding:.75rem 1rem;margin:.5rem 0;display:flex;
                align-items:center;justify-content:space-between;">
        <div>
            <div style="font-size:.82rem;font-weight:600;color:#E6EDF3;">
                🧮 Interactive Region Comparison
            </div>
            <div style="font-size:.72rem;color:#7D8590;margin-top:2px;">
                Enter your SCI components below to see how deployment region affects your score
            </div>
        </div>
        <span class="badge badge-cyan">↓ Scroll down</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Bar chart comparison ────────────────────────────────────────────────
    st.markdown("### Regional Comparison")

    df_sorted = df.sort_values("carbon_intensity")
    colours = []
    for ci in df_sorted["carbon_intensity"]:
        if ci < 100:   colours.append("#009E73")
        elif ci < 300: colours.append("#56B4E9")
        elif ci < 500: colours.append("#E69F00")
        else:          colours.append("#D55E00")

    fig2 = go.Figure(go.Bar(
        x=df_sorted["country"],
        y=df_sorted["carbon_intensity"],
        marker_color=colours,
        text=[f"{v:.0f}" for v in df_sorted["carbon_intensity"]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>%{y:.0f} gCO₂eq/kWh<extra></extra>",
    ))
    fig2.update_layout(
        yaxis_title="gCO₂eq/kWh",
        xaxis_title="Region",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=300,
        margin=dict(t=20, b=80, l=60, r=20),
    )
    fig2.update_xaxes(tickangle=-35)
    st.plotly_chart(fig2, use_container_width=True)

    # ── SCI impact calculator ───────────────────────────────────────────────
    st.divider()
    st.markdown("### 🧮 Region Impact on SCI Score")
    st.markdown(
        "Keeping all other SCI components equal, see how switching deployment "
        "region changes your SCI score."
    )

    col1, col2 = st.columns(2)
    with col1:
        energy_kwh = st.number_input("E — Energy (kWh)", value=0.5, min_value=0.0001,
                                     step=0.01, format="%.4f")
        embodied_carbon = st.number_input("M — Embodied carbon (gCO₂eq)", value=10000.0, step=100.0)
        functional_unit = st.number_input("R — Functional unit", value=1000.0, step=100.0)

    with col2:
        selected_regions = st.multiselect(
            "Compare regions",
            options=list(CARBON_INTENSITY_DEFAULTS.keys()),
            default=["UK", "FR", "NO", "IN"],
            format_func=lambda k: f"{REGION_NAMES.get(k, k)} ({CARBON_INTENSITY_DEFAULTS[k]} gCO₂/kWh)",
        )

    if selected_regions and st.button("📊 Compare Regions", type="primary"):
        from backend.services.sci_calculator import SCIComponents, SCICalculator
        calc = SCICalculator()
        results = []
        for r in selected_regions:
            ci = CARBON_INTENSITY_DEFAULTS[r]
            comp = SCIComponents(
                energy_kwh=energy_kwh,
                carbon_intensity=ci,
                embodied_carbon=embodied_carbon,
                functional_unit=functional_unit,
                region=r,
            )
            res = calc.calculate(comp)
            results.append({
                "Region": REGION_NAMES.get(r, r),
                "Carbon Intensity": f"{ci} gCO₂/kWh",
                "SCI Score": round(res.sci_score, 6),
                "Rating": res.get_rating(),
                "vs UK (%)": None,
            })

        results_df = pd.DataFrame(results)
        # Calculate vs UK baseline
        uk_sci = next((r["SCI Score"] for r in results if "United Kingdom" in r["Region"]), None)
        if uk_sci:
            results_df["vs UK (%)"] = results_df["SCI Score"].apply(
                lambda s: f"{((s - uk_sci) / uk_sci * 100):+.1f}%"
            )

        st.dataframe(results_df, use_container_width=True)

        # Mini bar chart
        fig3 = px.bar(
            results_df, x="Region", y="SCI Score",
            color="Rating",
            color_discrete_map={"Excellent": "#009E73", "Good": "#56B4E9",
                                "Acceptable": "#E69F00", "Poor": "#D55E00"},
            title="SCI Score by Deployment Region (same software, different grid)",
        )
        fig3.update_layout(height=300, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           margin=dict(t=40, b=60, l=60, r=20))
        st.plotly_chart(fig3, use_container_width=True)

        best = results_df.loc[results_df["SCI Score"].idxmin()]
        worst = results_df.loc[results_df["SCI Score"].idxmax()]
        saving_pct = (worst["SCI Score"] - best["SCI Score"]) / worst["SCI Score"] * 100
        st.success(
            f"✅ Deploying in **{best['Region']}** vs **{worst['Region']}** "
            f"reduces SCI by **{saving_pct:.1f}%** with zero code changes. "
            f"This is the 'I' lever in SCI = (E×I+M)/R."
        )

    # ── Academic context ────────────────────────────────────────────────────
    with st.expander("📚 Methodology & limitations"):
        st.markdown("""
        **Data source:** Electricity Maps (2024) annual average marginal carbon intensity.

        **Limitations:**
        - Annual averages mask hourly variation (renewable energy is time-dependent)
        - Real-time carbon intensity can be 2–5× lower during high-renewable periods
        - Connect the Electricity Maps API key in `.env` for live values

        **Academic note:** Choosing a low-carbon deployment region is the fastest
        single intervention to reduce SCI when energy optimisation is exhausted.
        France (nuclear-heavy, 56 gCO₂/kWh) produces ~4× lower SCI than India
        (coal-heavy, 708 gCO₂/kWh) for identical software.

        *Reference: Freitag et al. (2021); Green Software Foundation SOGS (2023).*
        """)
