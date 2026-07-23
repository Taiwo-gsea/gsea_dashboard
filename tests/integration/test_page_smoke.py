"""
GSEA Dashboard - Smoke Tests: All Pages Load Cleanly
=======================================================
Lightweight regression net: confirms every one of the nine dashboard
pages renders without raising an exception on initial load, when
navigated to directly via st.session_state["main_nav"].

This does NOT test deep interaction within each page (form submission,
file upload, tab switching, button clicks beyond navigation) — see
test_navigation.py for the specific Home-page button interactions that
are covered. This file exists to catch the class of bug where a page
crashes immediately on render (import error, undefined variable,
missing session-state key, etc.) before any user interaction happens.

Run: pytest tests/integration/test_page_smoke.py -v
Requires: streamlit>=1.28 (streamlit.testing.v1.AppTest)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

pytest.importorskip("streamlit.testing.v1", reason="requires streamlit>=1.28")
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).parent.parent.parent / "app.py")

ALL_PAGES = [
    "🏠  Home",
    "📊  SCI Calculator",
    "📉  Energy Trend",
    "📈  Proxy Metrics",
    "🗺️  Carbon Map",
    "📂  Data Ingestion",
    "🔬  NLP Extraction",
    "⚖️  Comparative Analysis",
    "📋  Reports & Export",
]


class TestAllPagesLoadCleanly:
    """Every page must render without an exception on first load."""

    @pytest.mark.parametrize("nav_label", ALL_PAGES)
    def test_page_loads_without_exception(self, nav_label):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.session_state["main_nav"] = nav_label
        at.run()

        assert len(at.exception) == 0, (
            f"Page '{nav_label}' raised on load: "
            f"{[str(e.value) for e in at.exception]}"
        )
