"""
GSEA Dashboard — NLP Extraction Page
=====================================
Primary academic contribution: automated extraction of GSE adoption
signals from dev.to grey literature using the dev.to public API.

Research Question:
    What green software engineering practices are being discussed and
    adopted in the software development community, as evidenced by
    grey literature on dev.to?

TOR v2.0, Objective O1 — NLP Literature Baseline (Primary Contribution)
"""

import sys
import json
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from nlp.gse_analyser import get_analyser, ArticleAnalysis

# ── Okabe-Ito colour-blind safe palette ──────────────────────────────────────
# Colour map for four GSEAS adoption levels (Okabe-Ito colour-blind safe palette)
OKABE_ITO = {
    "Strong":    "#009E73",   # green  — highest
    "Moderate":  "#0072B2",   # blue
    "Emerging":  "#E69F00",   # amber
    "Low":       "#999999",   # grey   — lowest
}
DIM_COLOURS = ["#0072B2","#009E73","#E69F00","#56B4E9","#CC79A7"]


def render_nlp_extraction():
    """Render the NLP Extraction page.  TOR v2.0 O1 — Primary Contribution."""

    st.markdown("""
    <div class="page-header">
        <div class="page-header-left">
            <div class="page-title">🔬 GSE Adoption Analysis</div>
            <span class="ph-tab active">dev.to Corpus</span>
            <span class="ph-tab inactive">Manual Text</span>
        </div>
        <span class="badge badge-cyan">Primary Contribution</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background:#161B22;border:1px solid #21262D;border-radius:8px;
                padding:.9rem 1.1rem;margin-bottom:1rem;">
        <div style="font-size:.85rem;color:#E6EDF3;font-weight:600;margin-bottom:.4rem;">
            What this page does
        </div>
        <div style="font-size:.8rem;color:#7D8590;line-height:1.6;">
            This page fetches real articles from <strong style="color:#00D4FF;">dev.to</strong>
            — a major developer blogging platform — and analyses them for Green Software Engineering
            (GSE) adoption signals. It answers the research question:
            <em style="color:#E6EDF3;">"What GSE practices are software developers actually
            talking about and adopting?"</em>
            Articles are scored across five dimensions: Energy Efficiency, Carbon Awareness,
            Hardware Efficiency, Green Practices, and Measurement & Tooling.
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs([
        "📡 Fetch from dev.to",
        "📊 Corpus Analysis",
        "✏️ Analyse Your Own Text",
    ])

    with tab1:
        _render_fetch_tab()
    with tab2:
        _render_corpus_tab()
    with tab3:
        _render_manual_tab()


# ── Tab 1: Fetch from dev.to ──────────────────────────────────────────────────

def _render_fetch_tab():
    st.markdown("### Fetch Articles from dev.to API")
    st.markdown(
        "The dev.to public API provides access to thousands of developer blog posts. "
        "This fetcher searches for articles tagged with green software engineering topics "
        "and downloads them for analysis. No API key is required."
    )

    col1, col2 = st.columns(2)
    with col1:
        tags_input = st.text_input(
            "Search tags (comma-separated)",
            value="green-software, sustainability, carbon, energy-efficiency",
            help="dev.to tags to search. Use the tags developers actually use.",
        )
        max_articles = st.slider(
            "Max articles to fetch",
            min_value=10, max_value=500, value=100, step=10,
            help="More articles = better analysis but slower fetch (~0.12s per page).",
        )
    with col2:
        use_cache = st.toggle(
            "Use cached data (faster)",
            value=True,
            help="If articles were fetched in the last 24 hours, use the cached version.",
        )
        st.markdown("""
        <div style="background:#1C2128;border:1px solid #21262D;border-radius:6px;
                    padding:.7rem;margin-top:.5rem;">
            <div style="font-size:.72rem;color:#7D8590;">dev.to API</div>
            <div style="font-size:.78rem;color:#00D4FF;font-family:monospace;">
                GET https://dev.to/api/articles?tag=...
            </div>
            <div style="font-size:.7rem;color:#7D8590;margin-top:.3rem;">
                Rate limit: 10 req/s · No auth required · Public data
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Cache stats
    try:
        from nlp.devto_fetcher import get_fetcher
        stats = get_fetcher().get_cache_stats()
        if stats["cached"]:
            st.info(
                f"📦 Cache available: **{stats['articles']} articles** "
                f"({stats['age_hours']}h old). Toggle off cache to refresh.",
                icon="📦"
            )
    except Exception:
        pass

    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        fetch_clicked = st.button(
            "📡 Fetch Articles", type="primary",
            key="fetch_devto", use_container_width=True
        )
    with col_btn2:
        if st.button("🗑️ Clear Cache", key="clear_cache"):
            try:
                get_fetcher().clear_cache()
                st.success("Cache cleared.")
            except Exception as e:
                st.error(str(e))

    if fetch_clicked:
        tags = [t.strip() for t in tags_input.split(",") if t.strip()]
        with st.spinner(f"Fetching up to {max_articles} articles from dev.to…"):
            try:
                from nlp.devto_fetcher import get_fetcher
                articles = get_fetcher().fetch_gse_articles(
                    tags=tags,
                    max_total=max_articles,
                    use_cache=use_cache,
                )
                st.session_state["devto_articles"] = articles
                st.success(
                    f"✅ Fetched **{len(articles)} articles** from dev.to. "
                    f"Switch to the **Corpus Analysis** tab to see the results."
                )
                _show_fetch_preview(articles)
            except Exception as e:
                st.error(f"Fetch failed: {e}")
                st.info(
                    "Check your internet connection. If the issue persists, "
                    "use the **Analyse Your Own Text** tab instead."
                )

    elif "devto_articles" in st.session_state:
        articles = st.session_state["devto_articles"]
        st.success(f"✅ {len(articles)} articles loaded. Switch to Corpus Analysis to view results.")
        _show_fetch_preview(articles)


def _show_fetch_preview(articles: list):
    """Show a quick preview table of fetched articles."""
    if not articles:
        return
    df = pd.DataFrame([{
        "Title":    a["title"][:60] + ("…" if len(a["title"]) > 60 else ""),
        "Author":   a["author"],
        "Tags":     ", ".join(a.get("tag_list", [])[:3]),
        "Published": a.get("published_at", "")[:10],
        "Reactions": a.get("reactions", 0),
    } for a in articles[:10]])
    st.markdown(f"**Preview — first 10 of {len(articles)} articles:**")
    st.dataframe(df, use_container_width=True)


# ── Tab 2: Corpus Analysis ────────────────────────────────────────────────────

def _render_corpus_tab():
    st.markdown("### GSE Adoption Signal Analysis")

    articles = st.session_state.get("devto_articles")
    if not articles:
        st.info(
            "No articles loaded yet. Go to the **Fetch from dev.to** tab "
            "and click **Fetch Articles** first.",
            icon="📡"
        )
        return

    # Run analysis
    if "corpus_results" not in st.session_state or \
       st.session_state.get("corpus_article_count") != len(articles):
        with st.spinner(f"Analysing {len(articles)} articles for GSE signals…"):
            analyser = get_analyser()
            results, report = analyser.analyse_corpus(articles)
            st.session_state["corpus_results"]       = results
            st.session_state["corpus_report"]        = report
            st.session_state["corpus_article_count"] = len(articles)
    else:
        results = st.session_state["corpus_results"]
        report  = st.session_state["corpus_report"]

    # ── KPI row ──────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Articles fetched",      report.total_articles)
    k2.metric("Software-relevant",     report.total_articles - report.excluded_off_topic)
    k3.metric("Mean adoption score",   f"{report.mean_adoption_score:.1f}/100")
    strong   = report.level_distribution.get("Strong", 0)
    moderate = report.level_distribution.get("Moderate", 0)
    k4.metric("Strong + Moderate",     strong + moderate)
    k5.metric("Dimensions tracked",    "5")
    k6.metric("Excluded (off-topic)",  report.excluded_off_topic)

    if report.excluded_off_topic > 0:
        st.caption(
            f"ℹ️ {report.excluded_off_topic} article(s) were excluded from the "
            f"statistics below because they matched the search tags (e.g. "
            f"'sustainability', 'carbon') but contained no software-engineering "
            f"context — for example, general agriculture or climate-policy content. "
            f"Their scores are still computed and available in the full results "
            f"table further down, just not counted in the corpus-level figures above."
        )

    st.divider()

    left, right = st.columns(2)

    # Adoption level distribution pie
    with left:
        st.markdown("#### Adoption Level Distribution")
        if report.level_distribution:
            levels = list(report.level_distribution.keys())
            counts = list(report.level_distribution.values())
            colours = [OKABE_ITO.get(l, "#888888") for l in levels]
            fig = go.Figure(data=[go.Pie(
                labels=levels, values=counts,
                marker=dict(colors=colours),
                hole=0.5, textinfo="label+percent",
                hovertemplate="%{label}: %{value} articles<extra></extra>"
            )])
            fig.update_layout(
                height=300, margin=dict(t=20,b=20,l=20,r=20),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(font=dict(color="#7D8590",size=11),
                            bgcolor="rgba(0,0,0,0)"),
                font=dict(color="#7D8590"),
            )
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False})

    # Dimension mean scores radar-style bar chart
    with right:
        st.markdown("#### GSE Dimension Coverage")
        if report.dimension_means:
            dims   = list(report.dimension_means.keys())
            scores = [v * 100 for v in report.dimension_means.values()]
            fig2 = go.Figure(go.Bar(
                x=scores, y=dims, orientation="h",
                marker_color=DIM_COLOURS,
                text=[f"{s:.1f}" for s in scores],
                textposition="outside",
                hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
            ))
            fig2.update_layout(
                height=300, margin=dict(t=20,b=20,l=160,r=60),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(range=[0,100], gridcolor="#21262D",
                           color="#7D8590", title="Mean signal strength (%)"),
                yaxis=dict(color="#7D8590"),
                font=dict(color="#7D8590"),
            )
            st.plotly_chart(fig2, use_container_width=True,
                            config={"displayModeBar": False})

    # Adoption trend over time
    if report.timeline:
        st.markdown("#### GSE Adoption Trend Over Time")
        tl_df = pd.DataFrame(report.timeline)
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(
            x=tl_df["month"], y=tl_df["article_count"],
            name="Articles", marker_color="rgba(0,114,178,0.3)",
            yaxis="y2", hovertemplate="%{x}: %{y} articles<extra></extra>",
        ))
        fig3.add_trace(go.Scatter(
            x=tl_df["month"], y=tl_df["mean_score"],
            name="Mean GSE Score", line=dict(color="#00D4FF", width=2),
            mode="lines+markers",
            hovertemplate="%{x}: score %{y:.1f}<extra></extra>",
        ))
        fig3.update_layout(
            height=300, margin=dict(t=20,b=40,l=50,r=60),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor="#21262D", color="#7D8590"),
            yaxis=dict(gridcolor="#21262D", color="#7D8590",
                       title="Mean adoption score"),
            yaxis2=dict(overlaying="y", side="right",
                        color="#7D8590", title="Article count"),
            legend=dict(font=dict(color="#7D8590"),
                        bgcolor="rgba(0,0,0,0)"),
            font=dict(color="#7D8590"),
        )
        st.plotly_chart(fig3, use_container_width=True,
                        config={"displayModeBar": False})

    # Top articles table
    st.markdown("#### Top Articles by GSE Adoption Score")
    if report.top_articles:
        top_df = pd.DataFrame([{
            "Title":          a["title"][:55] + "…" if len(a["title"]) > 55 else a["title"],
            "Author":         a["author"],
            "GSE Score":      f"{a['gse_adoption_score']:.1f}/100",
            "Level":          a["gse_level"],
            "Signals":        a["signal_count"],
            "Dominant":       a["dominant_dimension"],
            "Published":      a["published_at"][:10],
        } for a in report.top_articles])
        st.dataframe(
            top_df,
            use_container_width=True,
            column_config={
                "Title":     st.column_config.TextColumn(width="medium"),
                "Author":    st.column_config.TextColumn(width="small"),
                "GSE Score": st.column_config.TextColumn(width="small"),
                "Level":     st.column_config.TextColumn(width="small"),
                "Signals":   st.column_config.NumberColumn(width="small"),
                "Dominant":  st.column_config.TextColumn(width="medium"),
                "Published": st.column_config.TextColumn(width="small"),
            },
        )

    # Full results table with filter
    st.markdown("#### Full Results")
    col_f1, col_f2 = st.columns([3, 1])
    with col_f1:
        min_score = st.slider("Minimum GSE adoption score", 0, 100, 0, 5)
    with col_f2:
        hide_offtopic = st.toggle("Hide off-topic", value=False,
            help="Hide articles flagged as not software-relevant (matched search "
                 "tags but contained no software-engineering context).")
    all_df = pd.DataFrame([{
        "Title":     r.title[:40],
        "Author":    r.author,
        "Score":     r.gse_adoption_score,
        "Level":     r.gse_level,
        "Relevant":  "✅" if r.is_software_relevant else "⚠️ Off-topic",
        "Signals":   r.signal_count,
        "Energy":    round(r.energy_score * 100, 1),
        "Carbon":    round(r.carbon_score * 100, 1),
        "Hardware":  round(r.hardware_score * 100, 1),
        "Practices": round(r.practices_score * 100, 1),
        "Tooling":   round(r.tooling_score * 100, 1),
        "Published": r.published_at[:10],
        "URL":       r.url,
        "_relevant": r.is_software_relevant,
    } for r in results])
    filtered = all_df[all_df["Score"] >= min_score]
    if hide_offtopic:
        filtered = filtered[filtered["_relevant"]]
    st.caption(f"Showing {len(filtered)} of {len(all_df)} articles")
    st.caption("💡 If the Energy / Carbon / Hardware / Practices / Tooling columns "
               "aren't visible, click the ⛶ expand icon at the top-right of the "
               "table below, or scroll the table horizontally.")
    st.dataframe(
        filtered.drop(columns=["URL", "_relevant"]),
        use_container_width=True,
        column_config={
            "Title":     st.column_config.TextColumn(width="medium"),
            "Author":    st.column_config.TextColumn(width="small"),
            "Score":     st.column_config.NumberColumn(width="small"),
            "Level":     st.column_config.TextColumn(width="small"),
            "Relevant":  st.column_config.TextColumn(width="small"),
            "Signals":   st.column_config.NumberColumn(width="small"),
            "Energy":    st.column_config.NumberColumn(width="small"),
            "Carbon":    st.column_config.NumberColumn(width="small"),
            "Hardware":  st.column_config.NumberColumn(width="small"),
            "Practices": st.column_config.NumberColumn(width="small"),
            "Tooling":   st.column_config.NumberColumn(width="small"),
            "Published": st.column_config.TextColumn(width="small"),
        },
    )

    # Export
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        csv_data = filtered.drop(columns=["URL", "_relevant"]).to_csv(index=False)
        st.download_button(
            "📥 Export as CSV", csv_data,
            file_name="gse_adoption_analysis.csv",
            mime="text/csv", use_container_width=True,
        )
    with col_e2:
        json_results = [
            r for r in results
            if r.gse_adoption_score >= min_score
            and (r.is_software_relevant or not hide_offtopic)
        ]
        json_data = json.dumps(
            [r.to_dict() for r in json_results],
            indent=2, default=str
        )
        st.download_button(
            "📥 Export as JSON", json_data,
            file_name="gse_adoption_analysis.json",
            mime="application/json", use_container_width=True,
        )


# ── Tab 3: Manual text ────────────────────────────────────────────────────────

def _render_manual_tab():
    st.markdown("### Analyse Your Own Text")
    st.markdown(
        "Paste any text — a blog post, a conference paper abstract, a tool documentation page — "
        "and the analyser will extract GSE adoption signals from it. "
        "This is also useful for validating the pipeline against known-good examples."
    )

    input_text = st.text_area(
        "Paste text here",
        value="",
        height=220,
        placeholder=(
            "Paste any developer blog post, abstract, or article here.\n\n"
            "Example: 'We measured the energy consumption of our microservices "
            "using CodeCarbon and found 0.45 kWh per request. The carbon intensity "
            "of our AWS EU-West-1 region is 316 gCO2eq/kWh, giving us an SCI score "
            "of 142 gCO2eq per 1000 API calls. We reduced this by 60% by moving "
            "our batch jobs to run during off-peak hours when the grid is greener.'"
        ),
        help="Any text that might discuss energy, carbon, green software, or sustainability.",
    )

    if st.button("🔬 Analyse Text", type="primary",
                 key="analyse_manual", use_container_width=False):
        if not input_text.strip():
            st.warning("Please paste some text first.")
            return

        analyser = get_analyser()
        article  = {
            "id": 0, "title": "Manual input", "url": "",
            "author": "You", "published_at": "",
            "body_markdown": input_text, "tag_list": [],
        }
        result = analyser.analyse_article(article)
        _show_manual_result(result)

    elif "last_manual_result" in st.session_state:
        _show_manual_result(st.session_state["last_manual_result"])


def _show_manual_result(result: ArticleAnalysis):
    st.session_state["last_manual_result"] = result

    level_colour = OKABE_ITO.get(result.gse_level, "#888888")
    st.markdown(
        f'<span style="background:{level_colour}22;color:{level_colour};'
        f'padding:4px 12px;border-radius:12px;font-size:0.85rem;font-weight:600;">'
        f'{result.gse_level} adoption</span>',
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("GSE Adoption Score",  f"{result.gse_adoption_score:.1f}/100")
    k2.metric("Adoption Level",      result.gse_level)
    k3.metric("Signals Found",       result.signal_count)
    k4.metric("Dominant Dimension",  result.dominant_dimension)

    # Dimension scores
    dims = {
        "Energy Efficiency":     result.energy_score * 100,
        "Carbon Awareness":      result.carbon_score * 100,
        "Hardware Efficiency":   result.hardware_score * 100,
        "Green Practices":       result.practices_score * 100,
        "Measurement & Tooling": result.tooling_score * 100,
    }
    fig = go.Figure(go.Bar(
        x=list(dims.values()),
        y=list(dims.keys()),
        orientation="h",
        marker_color=DIM_COLOURS,
        text=[f"{v:.1f}%" for v in dims.values()],
        textposition="outside",
    ))
    fig.update_layout(
        height=260, margin=dict(t=20,b=20,l=160,r=60),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[0,100], gridcolor="#21262D", color="#7D8590"),
        yaxis=dict(color="#7D8590"),
        font=dict(color="#7D8590"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

    # Show extracted signals
    if result.signals:
        st.markdown("#### Extracted Signals")
        with st.expander(
            f"Show all {result.signal_count} extracted signals", expanded=True
        ):
            sig_df = pd.DataFrame([{
                "Dimension": s.dimension,
                "Matched text": s.match_text,
                "Context": s.context[:100],
            } for s in result.signals])
            st.dataframe(sig_df, use_container_width=True)
    else:
        st.info(
            "No GSE signals found in this text. Try pasting text that discusses "
            "energy consumption, carbon emissions, or green software practices.",
            icon="ℹ️"
        )
