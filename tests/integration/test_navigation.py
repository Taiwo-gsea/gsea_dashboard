"""
GSEA Dashboard - Regression Tests: Home Page Navigation
=========================================================
Covers a real bug reported via screenshot: clicking any of the four
"Quick Start" buttons on the Home page crashed with

    streamlit.errors.StreamlitAPIException: st.session_state.main_nav
    cannot be modified after the widget with key main_nav is instantiated.

Root cause: app.py's render_home() button handlers wrote directly to
st.session_state["main_nav"] — the same key bound to the sidebar's
st.radio(..., key="main_nav") widget, which is instantiated earlier in
the same script run (render_sidebar() runs before render_home()).
Streamlit forbids writing to a widget's own session_state key once that
widget has been instantiated in the current run.

Fix: button handlers now set a separate st.session_state["nav_request"]
key and call st.rerun(). At the very top of main(), before the sidebar
(and therefore the radio widget) is instantiated, any pending
nav_request is popped and applied to main_nav — which is legal because
the widget has not yet been created in that fresh run.

The same bug pattern also existed in frontend/pages/proxy_metrics.py's
"Fix 8" cross-page navigation and was fixed the same way.

Run: pytest tests/integration/test_navigation.py -v
Requires: streamlit>=1.28 (streamlit.testing.v1.AppTest)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

streamlit_testing = pytest.importorskip(
    "streamlit.testing.v1", reason="streamlit.testing.v1.AppTest requires streamlit>=1.28"
)
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).parent.parent.parent / "app.py")

QUICK_START_BUTTONS = [
    ("qs_sci", "📊  SCI Calculator"),
    ("qs_ingest", "📂  Data Ingestion"),
    ("qs_trend", "📉  Energy Trend"),
    ("qs_map", "🗺️  Carbon Map"),
]


class TestHomePageLoadsCleanly:
    """Sanity check: the app must render with no exceptions before any
    interaction, matching Image 1's initial (working) state."""

    def test_initial_load_has_no_exceptions(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        assert len(at.exception) == 0

    def test_initial_nav_defaults_to_home(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        assert at.session_state["main_nav"] == "🏠  Home"


class TestQuickStartButtonsDoNotCrash:
    """
    Regression test for the exact crash shown in the bug report screenshots:
    every Quick Start button on Home raised StreamlitAPIException on click.
    """

    @pytest.mark.parametrize("button_key,expected_nav", QUICK_START_BUTTONS)
    def test_button_click_raises_no_exception(self, button_key, expected_nav):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()

        button = at.button(key=button_key)
        button.click().run()

        assert len(at.exception) == 0, (
            f"Clicking '{button_key}' raised: "
            f"{[str(e.value) for e in at.exception]}"
        )

    @pytest.mark.parametrize("button_key,expected_nav", QUICK_START_BUTTONS)
    def test_button_click_navigates_to_correct_page(self, button_key, expected_nav):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()

        button = at.button(key=button_key)
        button.click().run()

        assert at.session_state["main_nav"] == expected_nav


class TestNavRequestPattern:
    """
    Confirms the underlying fix mechanism directly: nav_request is
    consumed (removed from session_state) once applied, so a stale
    request can't re-trigger navigation on a later, unrelated rerun.
    """

    def test_nav_request_is_consumed_after_use(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()

        button = at.button(key="qs_sci")
        button.click().run()

        assert "nav_request" not in at.session_state
        assert at.session_state["main_nav"] == "📊  SCI Calculator"
