"""
GSEA Dashboard - SCI Calculator Page
======================================
Interactive SCI = (E × I + M) / R calculator with:
- Manual input for all four SCI components
- Proxy metric estimation mode
- Interactive Plotly breakdown chart
- Qualitative rating and recommendations
"""

import streamlit as st
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.sci_calculator import (
    SCICalculator, SCIComponents,
    CARBON_INTENSITY_DEFAULTS, EMBODIED_CARBON_DEFAULTS
)

calculator = SCICalculator()

# Colour-blind safe palette (Okabe-Ito)
COLOURS = {
    "operational": "#0072B2",   # Blue
    "embodied":    "#E69F00",   # Orange
    "green":       "#009E73",
    "red":         "#D55E00",
}


def render_sci_calculator():
    """Render the SCI Calculator page.  Ch.5 §5.3.1 — SCI Score Dashboard (MUST)."""

    # ── Fix 2: Wire NLP export → pre-fill ─────────────────────────────────
    exported = st.session_state.get("nlp_exported", [])
    if exported:
        energy_entities = [e for e in exported if e.get("entity_type") == "ENERGY_VALUE"]
        carbon_entities = [e for e in exported if e.get("entity_type") == "CARBON_METRIC"]
        st.info(
            f"💡 **NLP Extraction found** {len(energy_entities)} energy value(s) and "
            f"{len(carbon_entities)} carbon metric(s) from your uploaded text. "
            f"Click below to pre-fill the calculator from the highest-confidence energy entity.",
            icon="🔬"
        )
        col_a, col_b = st.columns([1, 4])
        with col_a:
            if st.button("⚡ Pre-fill from NLP", type="primary", width="stretch"):
                if energy_entities:
                    best = max(energy_entities, key=lambda e: e.get("confidence_score", 0))
                    if best.get("entity_value"):
                        st.session_state["nlp_prefill_energy"] = float(best["entity_value"])
                        st.success(f"Pre-filled E = {best['entity_value']} {best.get('entity_unit','kWh')} from NLP extraction")
                        st.rerun()
        with col_b:
            if st.button("✕ Dismiss", width="content"):
                del st.session_state["nlp_exported"]
                st.rerun()

    st.markdown("""
    <div class="page-header">
        <div class="page-header-left">
            <div class="page-title">📊 SCI Score Calculator</div>
            <span class="page-tab active">Calculate</span>
            <span class="page-tab inactive">History</span>
        </div>
        <span class="badge badge-cyan">ISO/IEC 21031</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(
        "Calculate your software's **Software Carbon Intensity (SCI)** score "
        "per **ISO/IEC 21031**. Enter component values below."
    )

    st.markdown("""
    <div style="background:#161B22; border:1px solid #1f4e6e; border-radius:8px; padding:1rem; margin-bottom:1rem;">
    <b>SCI = (E × I + M) / R</b> &nbsp;|&nbsp;
    E = Energy (kWh) &nbsp;|&nbsp; I = Carbon intensity (gCO₂eq/kWh) &nbsp;|&nbsp;
    M = Embodied carbon (gCO₂eq) &nbsp;|&nbsp; R = Functional unit
    </div>
    """, unsafe_allow_html=True)

    # ── Input Mode Selector — respects proxy_metrics page navigation ────────
    _mode_override = st.session_state.pop("sci_mode_override", None)
    _default_idx   = 1 if _mode_override == "proxy" else 0
    mode = st.radio(
        "Input mode",
        ["Manual Component Entry", "Estimate from Proxy Metrics"],
        index=_default_idx,
        horizontal=True,
    )

    st.divider()

    # Fix 14: First-time user help panel
    with st.expander("ℹ️ What does an SCI score mean? (click to expand)", expanded=False):
        col_h1, col_h2 = st.columns(2)
        with col_h1:
            st.markdown("""
            **SCI = (E × I + M) / R** — the ISO/IEC 21031 formula

            | Component | Meaning |
            |-----------|---------|
            | **E** | Energy your software uses (kWh) |
            | **I** | How dirty your grid is (gCO₂/kWh) |
            | **M** | Carbon cost of the hardware (gCO₂) |
            | **R** | What you are measuring *per* (e.g. 1 API call) |

            A **lower SCI score is better** — it means less carbon per unit of work.
            """)
        with col_h2:
            st.markdown("""
            **Rating bands**

            | Rating | SCI Score | What it means |
            |--------|-----------|---------------|
            | 🟢 **Excellent** | < 10 | Very low carbon intensity |
            | 🔵 **Good** | 10 – 50 | Better than average |
            | 🟡 **Acceptable** | 50 – 200 | Room for improvement |
            | 🟠 **Poor** | 200 – 500 | High carbon — act now |
            | 🔴 **Critical** | > 500 | Urgent optimisation needed |

            💡 **Quickest win:** switch to a greener grid region (the **I** lever).
            France (56 gCO₂/kWh) gives 4× better SCI than India (708 gCO₂/kWh).
            """)

    if mode == "Manual Component Entry":
        _render_manual_entry()
    else:
        _render_proxy_estimation()


def _render_manual_entry():
    """Render manual SCI component input form."""

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### ⚡ Energy & Carbon (E, I)")

        _nlp_energy = st.session_state.pop("nlp_prefill_energy", 0.5)
        energy_kwh = st.number_input(
            "E — Energy consumed (kWh)",
            min_value=0.0001,
            value=float(_nlp_energy),
            step=0.01,
            format="%.4f",
            help="Total energy consumed by the software system during the measurement period.",
        )

        # Carbon intensity: allow manual or preset
        ci_source = st.selectbox(
            "I — Carbon intensity source",
            ["Use regional default", "Enter manually"],
        )

        if ci_source == "Use regional default":
            region = st.selectbox(
                "Region",
                options=list(CARBON_INTENSITY_DEFAULTS.keys()),
                index=0,
                format_func=lambda k: f"{k} — {CARBON_INTENSITY_DEFAULTS[k]} gCO₂eq/kWh",
            )
            carbon_intensity = CARBON_INTENSITY_DEFAULTS[region]
            st.caption(f"Carbon intensity: **{carbon_intensity} gCO₂eq/kWh** (Electricity Maps 2024)")
        else:
            region = None
            carbon_intensity = st.number_input(
                "I — Carbon intensity (gCO₂eq/kWh)",
                min_value=0.0,
                value=233.0,
                step=1.0,
                help="Grid marginal carbon intensity for the region where software runs.",
            )

    with col2:
        st.markdown("#### 🏭 Embodied Carbon & Functional Unit (M, R)")

        m_source = st.selectbox(
            "M — Embodied carbon source",
            ["Use hardware default", "Enter manually"],
        )

        if m_source == "Use hardware default":
            hardware_type = st.selectbox(
                "Hardware type",
                options=list(EMBODIED_CARBON_DEFAULTS.keys()),
                index=4,  # cloud_vm_small default
                format_func=lambda k: f"{k} — {EMBODIED_CARBON_DEFAULTS[k]:,.0f} gCO₂eq",
            )
            embodied_carbon = EMBODIED_CARBON_DEFAULTS[hardware_type]
            st.caption(f"Embodied carbon: **{embodied_carbon:,.0f} gCO₂eq** (Guldner et al. 2024)")
        else:
            hardware_type = None
            embodied_carbon = st.number_input(
                "M — Embodied carbon (gCO₂eq)",
                min_value=0.0,
                value=10000.0,
                step=100.0,
                help="Embodied carbon of hardware, prorated for the measurement period.",
            )

        st.markdown("---")

        functional_unit = st.number_input(
            "R — Functional unit value",
            min_value=0.001,
            value=1000.0,
            step=1.0,
            help="The denominator — what are you measuring per? e.g., per 1000 API calls, per user, per hour.",
        )

        functional_unit_label = st.text_input(
            "R — Functional unit label",
            value="API call",
            help="Human-readable description of R (e.g., 'API call', 'user', 'hour', 'transaction').",
        )

    # Optional metadata
    with st.expander("Optional metadata"):
        software_component = st.text_input("Software component name", placeholder="e.g., web-frontend, ML inference")
        deployment_env = st.selectbox("Deployment environment", ["", "cloud", "on-premise", "edge", "hybrid"])
        notes = st.text_area("Notes", placeholder="Any relevant context about this measurement...")

    # ── Calculate ──────────────────────────────────────────────────────────
    if st.button("🔢 Calculate SCI Score", type="primary", width="stretch"):
        try:
            components = SCIComponents(
                energy_kwh=energy_kwh,
                carbon_intensity=carbon_intensity,
                embodied_carbon=embodied_carbon,
                functional_unit=functional_unit,
                functional_unit_label=functional_unit_label,
                region=region if ci_source == "Use regional default" else None,
                hardware_type=hardware_type if m_source == "Use hardware default" else None,
                software_component=software_component or None,
                deployment_env=deployment_env or None,
                notes=notes or None,
            )
            result = calculator.calculate(components)
            _render_results(result, "manual")

        except ValueError as e:
            st.error(f"Input error: {e}")


def _render_proxy_estimation():
    """Render proxy metrics estimation form."""

    # Fix 3: Read pre-fill from Proxy Metrics page
    prefill = st.session_state.pop("proxy_prefill", {})

    st.markdown("#### Estimate SCI from Proxy Metrics")
    st.info(
        "When direct energy measurement (e.g., RAPL) is unavailable, "
        "SCI can be estimated from CPU%, memory usage, and runtime duration. "
        "Aligned with Guldner et al. (2024) proxy measurement approach.",
        icon="ℹ️",
    )

    col1, col2 = st.columns(2)

    with col1:
        cpu_percent = st.slider("CPU utilisation (%)", 0.0, 100.0, float(prefill.get("cpu_percent", 45.0)), step=0.5)
        memory_gb = st.number_input("Memory in use (GB)", min_value=0.1, value=float(prefill.get("memory_gb", 2.5)), step=0.1)
        duration_hours = st.number_input("Duration (hours)", min_value=0.01, value=float(prefill.get("duration_hours", 1.0)), step=0.25)
        tdp_watts = st.number_input("CPU TDP (Watts)", min_value=1.0, value=65.0, step=5.0,
                                    help="Thermal Design Power. Typical: laptop ~45W, desktop ~65W, server ~150W")

    with col2:
        region = st.selectbox(
            "Region",
            options=list(CARBON_INTENSITY_DEFAULTS.keys()),
            index=0,
            format_func=lambda k: f"{k} — {CARBON_INTENSITY_DEFAULTS[k]} gCO₂eq/kWh",
        )
        hardware_type = st.selectbox(
            "Hardware type",
            options=list(EMBODIED_CARBON_DEFAULTS.keys()),
            index=4,
        )
        functional_unit = st.number_input("R — Functional unit value", min_value=0.001, value=1.0)
        functional_unit_label = st.text_input("R — Functional unit label", value="hour")

    # Show estimated energy preview
    est_energy = (tdp_watts * (cpu_percent / 100) * duration_hours) / 1000
    st.metric("Estimated energy consumption", f"{est_energy:.5f} kWh",
              help="E = TDP × CPU_fraction × duration / 1000")

    if st.button("🔢 Estimate SCI Score", type="primary", width="stretch"):
        result = calculator.calculate_from_proxy_metrics(
            cpu_percent=cpu_percent,
            memory_gb=memory_gb,
            duration_hours=duration_hours,
            region=region,
            hardware_type=hardware_type,
            functional_unit=functional_unit,
            functional_unit_label=functional_unit_label,
            tdp_watts=tdp_watts,
        )
        _render_results(result, "proxy")
        st.caption("⚠️ Proxy estimation — actual energy may vary. Direct measurement preferred.")


def _render_results(result, method: str):
    """Render SCI calculation results with visualisations."""

    st.divider()
    st.markdown("### 📊 Results")

    # ── Score summary ──────────────────────────────────────────────────────
    rating = result.get_rating()
    rating_colours = {
        "Excellent": "#009E73", "Good": "#56B4E9",
        "Acceptable": "#E69F00", "Poor": "#D55E00", "Critical": "#CC0000"
    }
    badge_colour = rating_colours.get(rating, "#999")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div style="background:#161B22; border:1px solid {badge_colour};
                    border-radius:10px; padding:1.4rem; text-align:center;
                    box-shadow:0 0 24px rgba(0,212,255,0.07);">
            <div style="font-size:0.68rem; color:#7D8590; text-transform:uppercase;
                        letter-spacing:0.08em; margin-bottom:0.5rem;">SCI Score</div>
            <div style="font-size:2.2rem; font-weight:700; color:{badge_colour};
                        letter-spacing:-0.02em; line-height:1;">
                {result.sci_score:.4f}
            </div>
            <div style="font-size:0.75rem; color:#7D8590; margin-top:0.3rem;">
                gCO₂eq / {result.functional_unit_label}
            </div>
            <div style="margin-top:0.7rem;">
                <span style="background:{badge_colour}22; color:{badge_colour};
                             border:1px solid {badge_colour}55; padding:3px 12px;
                             border-radius:12px; font-size:0.7rem;
                             font-weight:600; letter-spacing:0.04em;">{rating}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.metric(
            "Operational Carbon (E×I)",
            f"{result.operational_carbon:,.2f} gCO₂eq",
            help="Carbon from electricity consumption: Energy × Carbon Intensity"
        )

    with col3:
        st.metric(
            "Embodied Carbon (M)",
            f"{result.embodied_carbon:,.2f} gCO₂eq",
            help="Carbon from hardware manufacture, prorated for measurement period."
        )

    with col4:
        st.metric(
            "Total Carbon",
            f"{result.total_carbon:,.2f} gCO₂eq",
            help="(E×I) + M — total carbon before dividing by functional unit R"
        )

    # ── Breakdown donut chart ──────────────────────────────────────────────
    st.divider()
    chart_col, detail_col = st.columns([1.2, 1])

    with chart_col:
        fig = go.Figure(data=[go.Pie(
            labels=["Operational Carbon (E×I)", "Embodied Carbon (M)"],
            values=[result.operational_carbon, result.embodied_carbon],
            hole=0.55,
            marker_colors=[COLOURS["operational"], COLOURS["embodied"]],
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>%{value:.2f} gCO₂eq<br>%{percent}<extra></extra>",
        )])

        fig.update_layout(
            title="Carbon Breakdown",
            title_font_size=16,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
            margin=dict(t=50, b=50, l=20, r=20),
            height=350,
            annotations=[dict(
                text=f"<b>{result.sci_score:.3f}</b><br>gCO₂eq/{result.functional_unit_label}",
                x=0.5, y=0.5,
                font_size=14,
                showarrow=False,
            )],
        )
        st.plotly_chart(fig, use_container_width=True)

    with detail_col:
        st.markdown("#### Component Breakdown")
        data = result.to_dict()

        st.markdown(f"""
        | Component | Value | % |
        |-----------|-------|---|
        | E — Energy | {data['inputs']['energy_kwh']:.5f} kWh | — |
        | I — Carbon intensity | {data['inputs']['carbon_intensity_gco2eq_kwh']:.1f} gCO₂eq/kWh | — |
        | E×I — Operational | {data['operational_carbon_gco2eq']:.4f} gCO₂eq | {data['operational_pct']}% |
        | M — Embodied | {data['embodied_carbon_gco2eq']:.4f} gCO₂eq | {data['embodied_pct']}% |
        | Total carbon | {data['total_carbon_gco2eq']:.4f} gCO₂eq | 100% |
        | R — Functional unit | {data['functional_unit']} {data['functional_unit_label']} | — |
        | **SCI Score** | **{data['sci_score']:.6f} gCO₂eq/{data['functional_unit_label']}** | — |
        """)

        # Improvement suggestions
        st.markdown("#### 💡 Improvement Levers")
        if data["operational_pct"] > 70:
            st.markdown("- 🔵 **Operational dominant**: Switch to lower-carbon grid region (e.g., FR or NO)")
            st.markdown("- 🔵 Optimise CPU utilisation — reduce idle time")
        if data["embodied_pct"] > 40:
            st.markdown("- 🟠 **Embodied dominant**: Extend hardware lifespan or use shared cloud infrastructure")
        st.markdown("- 🌿 Use renewable energy sources where possible")
        st.markdown("- ⚡ Apply code-level optimisations to reduce E")

    # Store result in session state for export
    if "sci_results" not in st.session_state:
        st.session_state["sci_results"] = []
    result_dict = result.to_dict()
    result_dict["method"] = method
    result_dict["rating"] = result.get_rating()
    st.session_state["sci_results"].append(result_dict)
    st.success("✅ Result saved to session. Visit **Comparative Analysis** or **Reports** to export.")
