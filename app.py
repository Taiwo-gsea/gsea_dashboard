"""
GSEA Dashboard - Main Application
===================================
Dark-themed, panel-based UI.  Entry point: streamlit run app.py
"""

import streamlit as st
import sys, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GSEA Dashboard",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "GSEA Dashboard — Green Software Engineering Analysis\nISO/IEC 21031 SCI = (E × I + M) / R"}
)

# ── Global dark theme CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body,[data-testid="stAppViewContainer"]{background-color:#0D1117!important;color:#E6EDF3!important;font-family:'Inter','Segoe UI',sans-serif}
#MainMenu,footer,header{visibility:hidden}
[data-testid="stToolbar"],.stDeployButton{display:none}

/* ── Sidebar ── */
[data-testid="stSidebar"]{background-color:#0D1117!important;border-right:1px solid #21262D!important;min-width:224px!important;max-width:224px!important}
[data-testid="stSidebar"]>div:first-child{padding-top:0;padding-left:0;padding-right:0}
.sb-brand{display:flex;align-items:center;gap:10px;padding:.9rem 1.2rem 1rem;border-bottom:1px solid #21262D;margin-bottom:.4rem}
.sb-icon{width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#00D4FF,#0094FF);display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700;color:#0D1117;flex-shrink:0}
.sb-name{font-size:.92rem;font-weight:600;color:#E6EDF3;letter-spacing:-.01em}
.sb-sub{font-size:.68rem;color:#7D8590;margin-top:1px}
.sb-section{font-size:.62rem;font-weight:600;color:#7D8590;text-transform:uppercase;letter-spacing:.08em;padding:.7rem 1.2rem .25rem}
.sb-formula{margin:.6rem 1rem 0;background:#161B22;border:1px solid #21262D;border-radius:8px;padding:.75rem}
.sb-formula-title{font-size:.62rem;color:#7D8590;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.35rem}
.sb-formula-eq{font-family:monospace;font-size:.82rem;color:#00D4FF;font-weight:600}
.sb-formula-vars{font-size:.62rem;color:#7D8590;margin-top:.35rem;line-height:1.6}
.sb-footer{margin:.8rem 1rem 0;padding-top:.7rem;border-top:1px solid #21262D}
.sb-footer-text{font-size:.62rem;color:#7D8590;line-height:1.6}

/* ── Main content ── */
.main .block-container{padding:1.2rem 1.5rem 2rem!important;max-width:100%!important;background-color:#0D1117!important}

/* ── Page header ── */
.page-header{display:flex;align-items:center;justify-content:space-between;padding-bottom:1rem;border-bottom:1px solid #21262D;margin-bottom:1.2rem}
.page-header-left{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.page-title{font-size:1.05rem;font-weight:600;color:#E6EDF3;letter-spacing:-.01em}
.ph-tab{padding:.28rem .85rem;border-radius:6px;font-size:.78rem;font-weight:500}
.ph-tab.active{background:#00D4FF;color:#0D1117}
.ph-tab.inactive{background:#21262D;color:#7D8590}

/* ── Panel / Card ── */
.panel{background:#161B22;border:1px solid #21262D;border-radius:10px;padding:1.1rem 1.2rem;margin-bottom:1rem}
.panel-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:.85rem}
.panel-title{font-size:.88rem;font-weight:600;color:#E6EDF3}
.p-badge{background:#21262D;color:#7D8590;font-size:.68rem;padding:2px 8px;border-radius:12px}
.p-badge.green{background:rgba(0,212,255,.12);color:#00D4FF}
.p-badge.amber{background:rgba(227,179,65,.12);color:#E3B341}

/* ── KPI card ── */
.kpi-card{background:#161B22;border:1px solid #21262D;border-radius:12px;padding:1.15rem 1.3rem;transition:border-color .15s}
.kpi-card:hover{border-color:#3B3F8C}
.kpi-icon-row{display:flex;align-items:center;gap:7px;margin-bottom:.8rem}
.kpi-icon{width:22px;height:22px;border-radius:6px;background:rgba(124,127,242,.14);display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0}
.kpi-label{font-size:.68rem;color:#7D8590;text-transform:uppercase;letter-spacing:.07em;margin-bottom:.35rem;font-weight:500}
.kpi-label-plain{font-size:.82rem;color:#8B949E;font-weight:500}
.kpi-value{font-size:1.75rem;font-weight:700;color:#00D4FF;letter-spacing:-.02em;line-height:1}
.kpi-value.green{color:#3FB950}
.kpi-value.amber{color:#E3B341}
.kpi-value.white{color:#E6EDF3}
.kpi-value.muted{color:#7D8590;font-size:1.2rem}
.kpi-value-row{display:flex;align-items:baseline;gap:.55rem;flex-wrap:wrap}
.kpi-sub{font-size:.68rem;color:#7D8590;margin-top:.3rem}
.delta-up{color:#3FB950;font-size:.68rem}
.delta-dn{color:#F85149;font-size:.68rem}
.trend-badge{display:inline-flex;align-items:center;gap:2px;font-size:.68rem;font-weight:600;padding:2px 7px;border-radius:6px}
.trend-badge.up{background:rgba(63,185,80,.14);color:#3FB950}
.trend-badge.dn{background:rgba(248,81,73,.14);color:#F85149}

/* ── Status badges ── */
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:.68rem;font-weight:600}
.badge-green{background:rgba(63,185,80,.12);color:#3FB950}
.badge-red{background:rgba(248,81,73,.12);color:#F85149}
.badge-amber{background:rgba(227,179,65,.12);color:#E3B341}
.badge-cyan{background:rgba(0,212,255,.12);color:#00D4FF}
.badge-grey{background:rgba(125,133,144,.12);color:#7D8590}

/* ── Hero (Home landing) ── */
.hero{padding:2.2rem 0 1.8rem;position:relative}
.hero-eyebrow{display:inline-flex;align-items:center;gap:6px;font-size:.68rem;font-weight:600;color:#00D4FF;text-transform:uppercase;letter-spacing:.1em;margin-bottom:1rem}
.hero-eyebrow::before{content:"";width:6px;height:6px;border-radius:50%;background:#3FB950;box-shadow:0 0 0 3px rgba(63,185,80,.15)}
.hero-title{font-size:2.35rem;font-weight:700;color:#E6EDF3;letter-spacing:-.03em;line-height:1.12;margin-bottom:.85rem;max-width:640px}
.hero-title em{color:#00D4FF;font-style:normal}
.hero-sub{font-size:.95rem;color:#8B949E;line-height:1.6;max-width:560px;margin-bottom:1.9rem;font-weight:400}
.hero-grid{display:grid;grid-template-columns:1.15fr 1fr;gap:1.4rem;align-items:stretch;margin-bottom:.4rem}
@media(max-width:900px){.hero-grid{grid-template-columns:1fr}}

/* Formula instrument panel — the signature element */
.instrument{background:linear-gradient(180deg,#161B22 0%,#12161C 100%);border:1px solid #21262D;border-radius:14px;padding:1.5rem 1.6rem 1.3rem;position:relative;overflow:hidden}
.instrument-label{font-size:.62rem;font-weight:600;color:#7D8590;text-transform:uppercase;letter-spacing:.09em;margin-bottom:.7rem}
.instrument-eq{font-family:'JetBrains Mono','SF Mono',monospace;font-size:1.55rem;font-weight:600;color:#E6EDF3;letter-spacing:-.01em;margin-bottom:1rem}
.instrument-eq .var-e{color:#00D4FF}
.instrument-eq .var-i{color:#E3B341}
.instrument-eq .var-m{color:#F85149}
.instrument-eq .var-r{color:#3FB950}
.instrument-bar{height:4px;border-radius:4px;background:linear-gradient(90deg,#3FB950 0%,#E3B341 50%,#F85149 100%);margin-bottom:.65rem;opacity:.85}
.instrument-caption{font-size:.68rem;color:#7D8590;display:flex;justify-content:space-between;align-items:center}
.instrument-caption .std{font-weight:600;color:#8B949E}

/* Context panel beside the instrument */
.hero-context{background:#161B22;border:1px solid #21262D;border-radius:14px;padding:1.5rem 1.6rem;display:flex;flex-direction:column;justify-content:center;gap:1rem}
.hc-row{display:flex;align-items:flex-start;gap:.7rem}
.hc-dot{width:7px;height:7px;border-radius:50%;margin-top:.45rem;flex-shrink:0}
.hc-text{font-size:.8rem;color:#8B949E;line-height:1.5}
.hc-text strong{color:#E6EDF3;font-weight:600}

/* Polished CTA row */
.hero-cta-row{display:flex;gap:.6rem;margin-top:1.5rem;flex-wrap:wrap}
div[data-testid="column"] button[kind="primary"]{background:#00D4FF!important;border:1px solid #00D4FF!important;color:#0D1117!important;font-weight:600!important;box-shadow:0 0 0 0 rgba(0,212,255,.4)!important;transition:box-shadow .15s,transform .15s!important}
div[data-testid="column"] button[kind="primary"]:hover{box-shadow:0 0 0 4px rgba(0,212,255,.15)!important;transform:translateY(-1px)}
div[data-testid="column"] button[kind="secondary"]{background:#161B22!important;border:1px solid #30363D!important;color:#C9D1D9!important;font-weight:500!important;transition:border-color .15s,transform .15s!important}
div[data-testid="column"] button[kind="secondary"]:hover{border-color:#00D4FF!important;color:#00D4FF!important;transform:translateY(-1px)}
.hero-divider{height:1px;background:linear-gradient(90deg,#21262D 0%,#21262D 60%,transparent 100%);margin:2rem 0 1.6rem}

/* ── Progress bar ── */
.pb-bg{background:#21262D;border-radius:4px;height:5px;overflow:hidden;margin-top:5px}
.pb-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,#00D4FF,#0094FF)}
.pb-fill.green{background:linear-gradient(90deg,#3FB950,#26A641)}
.pb-fill.amber{background:#E3B341}
.pb-fill.red{background:#F85149}

/* ── Widgets ── */
.stSelectbox>div>div,.stTextInput>div>div>input,.stNumberInput>div>div>input,.stTextArea>div>div>textarea{background-color:#21262D!important;border:1px solid #30363D!important;color:#E6EDF3!important;border-radius:6px!important}
.stSelectbox label,.stTextInput label,.stNumberInput label,.stTextArea label,.stSlider label,.stRadio label,.stMultiSelect label{color:#7D8590!important;font-size:.78rem!important}
.stButton>button{background:#21262D!important;border:1px solid #30363D!important;color:#E6EDF3!important;border-radius:6px!important;font-size:.8rem!important;font-weight:500!important;padding:.4rem 1rem!important;transition:all .15s!important}
.stButton>button:hover{background:#30363D!important;border-color:#00D4FF!important;color:#00D4FF!important}
[data-testid="baseButton-primary"]{background:linear-gradient(135deg,#00D4FF,#0094FF)!important;border:none!important;color:#0D1117!important;font-weight:600!important}
[data-testid="baseButton-primary"]:hover{opacity:.9!important;color:#0D1117!important}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"]{background:transparent!important;border-bottom:1px solid #21262D!important;gap:0!important}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:#7D8590!important;border:none!important;border-bottom:2px solid transparent!important;font-size:.8rem!important;font-weight:500!important;padding:.5rem 1.1rem!important;border-radius:0!important}
.stTabs [aria-selected="true"]{color:#00D4FF!important;border-bottom-color:#00D4FF!important;background:transparent!important}

/* ── Expanders ── */
.streamlit-expanderHeader{background:#161B22!important;border:1px solid #21262D!important;border-radius:8px!important;color:#E6EDF3!important;font-size:.82rem!important}
.streamlit-expanderContent{background:#161B22!important;border:1px solid #21262D!important;border-top:none!important;border-radius:0 0 8px 8px!important}

/* ── File uploader ── */
[data-testid="stFileUploader"]{background:#161B22!important;border:1px dashed #30363D!important;border-radius:8px!important}
[data-testid="stFileUploader"]:hover{border-color:#00D4FF!important}

/* ── Metrics ── */
[data-testid="stMetricValue"]{color:#00D4FF!important;font-size:1.55rem!important;font-weight:700!important}
[data-testid="stMetricLabel"]{color:#7D8590!important;font-size:.72rem!important}

/* ── Alerts ── */
.stAlert{background:#161B22!important;border-radius:8px!important}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:#0D1117}
::-webkit-scrollbar-thumb{background:#30363D;border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:#484F58}

/* ── Toggle ── */
.stToggle>label>div[role="switch"][aria-checked="true"]{background:#00D4FF!important}

hr{border-color:#21262D!important}
</style>
""", unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div class="sb-brand">
            <div class="sb-icon">🌿</div>
            <div>
                <div class="sb-name">GSEA Dashboard</div>
                <div class="sb-sub">Green Software Analysis</div>
            </div>
        </div>
        <div class="sb-section">Navigation</div>
        """, unsafe_allow_html=True)

        pages = {
            "🏠  Home":                 "home",
            "📊  SCI Calculator":       "sci_calculator",
            "📉  Energy Trend":         "energy_trend",
            "📈  Proxy Metrics":        "proxy_metrics",
            "🗺️  Carbon Map":           "carbon_map",
            "📂  Data Ingestion":       "data_ingestion",
            "🔬  NLP Extraction":       "nlp_extraction",
            "⚖️  Comparative Analysis": "comparative_analysis",
            "📋  Reports & Export":     "reports",
        }

        selected = st.radio("nav", list(pages.keys()),
                            label_visibility="collapsed",
                            key="main_nav")

        st.markdown("""
        <div class="sb-section" style="margin-top:.5rem;">Reference</div>
        <div class="sb-formula">
            <div class="sb-formula-title">SCI Formula</div>
            <div class="sb-formula-eq">SCI = (E × I + M) / R</div>
            <div class="sb-formula-vars">
                E = Energy (kWh)<br>
                I = Carbon intensity (gCO₂/kWh)<br>
                M = Embodied carbon (gCO₂)<br>
                R = Functional unit
            </div>
        </div>
        <div class="sb-footer">
            <div class="sb-footer-text">
                ISO/IEC 21031 · GSF SOGS 2023<br>
                MMU MSc Computer Science 2026
            </div>
        </div>
        """, unsafe_allow_html=True)

        return pages[selected]


# ── Home page ──────────────────────────────────────────────────────────────
def render_home():
    import plotly.graph_objects as go

    # ── Hero ──────────────────────────────────────────────────────────
    st.markdown("""
    <div class="hero">
        <div class="hero-eyebrow">Live · dev.to + ISO/IEC 21031</div>
        <div class="hero-title">Measure what your software<br>costs <em>the planet</em>.</div>
        <div class="hero-sub">
            GSEA Dashboard implements the ISO/IEC 21031 Software Carbon Intensity
            standard and analyses real developer discourse on dev.to, so you can
            see how the industry is adopting green practices and score your own
            software's footprint — in one tool, one browser tab.
        </div>
        <div class="hero-grid">
            <div class="instrument">
                <div class="instrument-label">The formula this dashboard is built on</div>
                <div class="instrument-eq">SCI = (<span class="var-e">E</span> × <span class="var-i">I</span> + <span class="var-m">M</span>) / <span class="var-r">R</span></div>
                <div class="instrument-bar"></div>
                <div class="instrument-caption">
                    <span class="std">ISO/IEC 21031</span>
                    <span>Software Carbon Intensity</span>
                </div>
            </div>
            <div class="hero-context">
                <div class="hc-row">
                    <div class="hc-dot" style="background:#00D4FF;"></div>
                    <div class="hc-text"><strong>E</strong> — Energy consumed (kWh). <strong>I</strong> — Grid carbon intensity (gCO₂/kWh).</div>
                </div>
                <div class="hc-row">
                    <div class="hc-dot" style="background:#F85149;"></div>
                    <div class="hc-text"><strong>M</strong> — Embodied carbon of hardware, prorated per run.</div>
                </div>
                <div class="hc-row">
                    <div class="hc-dot" style="background:#3FB950;"></div>
                    <div class="hc-text"><strong>R</strong> — Your functional unit: per request, per user, per minute.</div>
                </div>
            </div>
        </div>
    </div>
    <div class="hero-divider"></div>
    """, unsafe_allow_html=True)

    # Page header
    st.markdown("""
    <div class="page-header">
        <div class="page-header-left">
            <div class="page-title">Dashboard Overview</div>
            <span class="ph-tab active">Overview</span>
            <span class="ph-tab inactive">Analytics</span>
        </div>
        <span class="badge badge-cyan">GSEA v5</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Sample data generator ─────────────────────────────────────────
    sample_path = Path(__file__).parent / "data" / "sample" / "gmt_sample.csv"
    if not sample_path.exists():
        st.markdown("""
        <div class="panel" style="border-color:#E3B341;">
            <div class="panel-header">
                <span class="panel-title">⚡ First-time setup required</span>
                <span class="p-badge amber">Action needed</span>
            </div>
            <div style="font-size:.82rem;color:#7D8590;">
                Sample data files are missing. Click the button below to generate
                them — this takes about 3 seconds and only needs to be done once.
                All dashboard pages will work immediately afterwards.
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🚀 Generate Sample Data — click here to get started",
                     type="primary", key="gen_data_home"):
            with st.spinner("Generating 3 sample CSV files…"):
                result = subprocess.run(
                    [sys.executable, "scripts/generate_sample_data.py"],
                    capture_output=True, text=True,
                    cwd=str(Path(__file__).parent)
                )
            if result.returncode == 0:
                st.success("✅ Sample data ready! All pages are now fully functional.")
                st.rerun()
            else:
                st.error(f"Generation failed: {result.stderr}")
        return  # Don't show rest of home until data is ready

    # ── Live KPIs ─────────────────────────────────────────────────────
    datasets   = st.session_state.get("parsed_datasets", [])
    sci_res    = st.session_state.get("sci_results", [])
    n_datasets = len(datasets)

    all_scores = []
    for d in datasets:
        if "sci_score" in d["df"].columns:
            all_scores.extend(d["df"]["sci_score"].dropna().tolist())
    all_scores.extend([r["sci_score"] for r in sci_res])

    mean_sci  = f"{sum(all_scores)/len(all_scores):.4f}" if all_scores else "—"
    sci_class = "kpi-value" if not all_scores else (
        "kpi-value green" if sum(all_scores)/len(all_scores) < 50 else "kpi-value amber"
    )
    total_energy = sum(
        d["df"]["energy_kwh"].sum() for d in datasets if "energy_kwh" in d["df"].columns
    )
    total_carbon = sum(
        d["df"]["total_carbon"].sum() for d in datasets if "total_carbon" in d["df"].columns
    )
    energy_str = f"{total_energy:.5f}" if total_energy else "—"
    carbon_str = f"{total_carbon:,.2f}" if total_carbon else "—"
    n_str = str(n_datasets) if n_datasets else "0"
    ds_label = ("dataset" + ("s" if n_datasets != 1 else "") + " loaded"
                if n_datasets else "Upload via Data Ingestion")

    sci_badge = ""
    if all_scores:
        good = (sum(all_scores) / len(all_scores)) < 50
        sci_badge = (
            '<span class="trend-badge up">▲ Good</span>' if good
            else '<span class="trend-badge dn">▼ High</span>'
        )

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon-row"><div class="kpi-icon">📊</div><div class="kpi-label-plain">Mean SCI Score</div></div>
            <div class="kpi-value-row"><span class="{sci_class}">{mean_sci}</span>{sci_badge}</div>
            <div class="kpi-sub">{"gCO₂eq / request" if all_scores else "Calculate or upload data"}</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon-row"><div class="kpi-icon">⚡</div><div class="kpi-label-plain">Total Energy</div></div>
            <div class="kpi-value-row"><span class="kpi-value white">{energy_str}</span></div>
            <div class="kpi-sub">{"kWh across all ingested datasets" if total_energy else "Upload data to measure"}</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon-row"><div class="kpi-icon">🌍</div><div class="kpi-label-plain">Total Carbon</div></div>
            <div class="kpi-value-row"><span class="kpi-value green">{carbon_str}</span></div>
            <div class="kpi-sub">{"gCO₂eq — operational + embodied" if total_carbon else "Upload data to measure"}</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-icon-row"><div class="kpi-icon">📁</div><div class="kpi-label-plain">Datasets Ingested</div></div>
            <div class="kpi-value-row"><span class="kpi-value amber">{n_str}</span></div>
            <div class="kpi-sub">{ds_label}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts row ─────────────────────────────────────────────────────
    left, right = st.columns([1.6, 1])

    with left:
        st.markdown("""
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">SCI Score Trend</span>
                <span class="p-badge green">Live session data</span>
            </div>
        """, unsafe_allow_html=True)

        if all_scores and len(all_scores) >= 2:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(range(len(all_scores))),
                y=all_scores,
                fill='tozeroy',
                mode='lines+markers',
                line=dict(color='#7C7FF2', width=2.5, shape='spline', smoothing=0.8),
                marker=dict(size=4, color='#7C7FF2'),
                fillcolor='rgba(124,127,242,0.14)',
                hovertemplate='Reading %{x}: %{y:.4f} gCO₂eq/req<extra></extra>'
            ))
            fig.update_layout(
                height=220, margin=dict(t=8, b=30, l=50, r=10),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, color='#7D8590',
                           tickfont=dict(size=10), title="Reading #"),
                yaxis=dict(showgrid=True, gridcolor='#1C2128',
                           color='#7D8590', tickfont=dict(size=10),
                           title="SCI"),
                showlegend=False,
                hoverlabel=dict(bgcolor='#161B22', bordercolor='#30363D',
                                 font=dict(color='#E6EDF3', size=11)),
            )
            st.plotly_chart(fig, config={'displayModeBar': False})
        else:
            st.markdown("""
            <div style="height:180px;display:flex;flex-direction:column;
                        align-items:center;justify-content:center;gap:8px;">
                <div style="font-size:1.8rem;">📊</div>
                <div style="font-size:.82rem;color:#7D8590;text-align:center;">
                    No SCI data yet.<br>
                    Use the <strong style="color:#00D4FF;">SCI Calculator</strong>
                    or <strong style="color:#00D4FF;">Data Ingestion</strong> page to get started.
                </div>
            </div>""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("""
        <div class="panel" style="height:100%;">
            <div class="panel-header">
                <span class="panel-title">Carbon Breakdown</span>
            </div>
        """, unsafe_allow_html=True)

        op_total  = sum(d["df"]["operational_carbon"].sum() for d in datasets if "operational_carbon" in d["df"].columns)
        emb_total = sum(d["df"]["embodied_carbon"].sum()    for d in datasets if "embodied_carbon"    in d["df"].columns)
        if op_total + emb_total > 0:
            op_pct  = round(op_total  / (op_total + emb_total) * 100)
            emb_pct = 100 - op_pct
            label   = f"{op_pct}%"
        else:
            op_pct, emb_pct, label = 73, 27, "—"

        fig2 = go.Figure(data=[go.Pie(
            labels=['Operational (E×I)', 'Embodied (M)'],
            values=[op_pct, emb_pct],
            hole=0.62,
            marker_colors=['#00D4FF', '#0094FF'],
            textinfo='none',
            hovertemplate='%{label}: %{value}%<extra></extra>'
        )])
        fig2.update_layout(
            height=200, margin=dict(t=8, b=8, l=8, r=8),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            showlegend=True,
            legend=dict(font=dict(color='#7D8590', size=10),
                        bgcolor='rgba(0,0,0,0)', orientation='v', x=0.82, y=0.5),
            annotations=[dict(text=label, x=0.38, y=0.5,
                              font=dict(size=16, color='#00D4FF', family='Inter'),
                              showarrow=False)]
        )
        st.plotly_chart(fig2, config={'displayModeBar': False})
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Quick Start panel ──────────────────────────────────────────────
    st.markdown("""
    <div class="panel">
        <div class="panel-header">
            <span class="panel-title">Quick Start</span>
            <span class="p-badge">Choose a workflow</span>
        </div>
    """, unsafe_allow_html=True)

    qa, qb, qc, qd = st.columns(4)
    with qa:
        if st.button("📊 Calculate SCI Score", type="primary", key="qs_sci"):
            st.session_state["nav_request"] = "📊  SCI Calculator"
            st.rerun()
    with qb:
        if st.button("📂 Upload Data", key="qs_ingest"):
            st.session_state["nav_request"] = "📂  Data Ingestion"
            st.rerun()
    with qc:
        if st.button("📉 Energy Trend", key="qs_trend"):
            st.session_state["nav_request"] = "📉  Energy Trend"
            st.rerun()
    with qd:
        if st.button("🗺️ Carbon Map", key="qs_map"):
            st.session_state["nav_request"] = "🗺️  Carbon Map"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Feature grid ───────────────────────────────────────────────────
    st.markdown("""
    <div class="panel">
        <div class="panel-header">
            <span class="panel-title">All Features</span>
            <span class="p-badge">9 modules</span>
        </div>
    """, unsafe_allow_html=True)

    features = [
        ("📊", "SCI Calculator",   "ISO/IEC 21031"),
        ("📉", "Energy Trend",     "Time-series"),
        ("📈", "Proxy Metrics",    "CPU · Memory"),
        ("🗺️", "Carbon Map",       "Regional CI"),
        ("📂", "Data Ingestion",   "GMT · CodeCarbon"),
        ("🔬", "NLP Extraction",   "spaCy · HF"),
        ("⚖️", "Comparative",      "Multi-config"),
        ("📋", "Reports",          "CSV · JSON"),
        ("🏠", "Home",             "Overview"),
    ]
    cols = st.columns(9)
    for col, (icon, name, sub) in zip(cols, features):
        with col:
            st.markdown(f"""
            <div style="background:#1C2128;border:1px solid #21262D;border-radius:8px;
                        padding:.7rem .4rem;text-align:center;">
                <div style="font-size:1.25rem;margin-bottom:.25rem;">{icon}</div>
                <div style="font-size:.68rem;font-weight:600;color:#E6EDF3;
                            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{name}</div>
                <div style="font-size:.6rem;color:#7D8590;margin-top:1px;">{sub}</div>
            </div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# ── Page router ────────────────────────────────────────────────────────────
def main():
    # Fix: consume any button-triggered navigation request BEFORE the
    # sidebar radio widget (key="main_nav") is instantiated below.
    # Streamlit forbids writing to st.session_state[key] for a widget's
    # own key once that widget has been instantiated in the current run —
    # this must happen first, not inside render_home()'s button handlers.
    if "nav_request" in st.session_state:
        st.session_state["main_nav"] = st.session_state.pop("nav_request")

    selected = render_sidebar()

    def _safe(fn, name):
        try:
            fn()
        except Exception as e:
            st.error(f"**{name}** failed to load: `{e}`")
            st.info("Try refreshing the page (F5).")
            import traceback
            with st.expander("Show error details"):
                st.code(traceback.format_exc())

    if selected == "home":
        render_home()
    elif selected == "sci_calculator":
        from frontend.pages.sci_calculator import render_sci_calculator
        _safe(render_sci_calculator, "SCI Calculator")
    elif selected == "energy_trend":
        from frontend.pages.energy_trend import render_energy_trend
        _safe(render_energy_trend, "Energy Trend Analysis")
    elif selected == "proxy_metrics":
        from frontend.pages.proxy_metrics import render_proxy_metrics
        _safe(render_proxy_metrics, "Proxy Metrics")
    elif selected == "carbon_map":
        from frontend.pages.carbon_map import render_carbon_map
        _safe(render_carbon_map, "Carbon Intensity Map")
    elif selected == "data_ingestion":
        from frontend.pages.data_ingestion import render_data_ingestion
        _safe(render_data_ingestion, "Data Ingestion")
    elif selected == "nlp_extraction":
        from frontend.pages.nlp_extraction import render_nlp_extraction
        _safe(render_nlp_extraction, "NLP Extraction")
    elif selected == "comparative_analysis":
        from frontend.pages.comparative_analysis import render_comparative_analysis
        _safe(render_comparative_analysis, "Comparative Analysis")
    elif selected == "reports":
        from frontend.pages.reports import render_reports
        _safe(render_reports, "Reports & Export")


if __name__ == "__main__":
    main()
