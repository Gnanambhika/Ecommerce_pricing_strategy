"""Streamlit entrypoint: E-commerce Pricing Strategy & Profitability Intelligence.

Run locally:   streamlit run app.py
Deploy:        Streamlit Community Cloud, main file path = app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st  # noqa: E402

from pricing_intel.config import APP_SUBTITLE, APP_TITLE, SYNTHETIC_NOTICE  # noqa: E402
from pricing_intel.ui import state, theme  # noqa: E402

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=":material/insights:",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={"About": f"{APP_TITLE}: a portfolio analytics project on synthetic data."},
)
theme.register_plotly_template()
theme.inject_css()

PAGES_DIR = SRC / "pricing_intel" / "ui" / "pages"
pages = {
    "Analysis": [
        st.Page(str(PAGES_DIR / "overview.py"), title="Executive Overview", icon=":material/space_dashboard:",
                default=True),
        st.Page(str(PAGES_DIR / "pricing.py"), title="Pricing & Competitors", icon=":material/sell:",
                url_path="pricing"),
        st.Page(str(PAGES_DIR / "discounts.py"), title="Discounts & Profitability", icon=":material/percent:",
                url_path="discounts"),
        st.Page(str(PAGES_DIR / "elasticity.py"), title="Demand & Elasticity", icon=":material/insights:",
                url_path="elasticity"),
    ],
    "Plan": [
        st.Page(str(PAGES_DIR / "simulator.py"), title="Scenario Simulator", icon=":material/tune:",
                url_path="simulator"),
    ],
    "Data": [
        st.Page(str(PAGES_DIR / "data_quality.py"), title="Data Quality & Methodology",
                icon=":material/fact_check:", url_path="data-quality"),
    ],
}

st.logo(str(ROOT / "assets" / "logo.svg"), size="large")
navigation = st.navigation(pages, position="sidebar")

try:
    dataset = state.active_dataset()
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

st.session_state["filters"] = state.render_sidebar_filters(dataset)

with st.sidebar:
    st.markdown('<div class="sidebar-section">Data source</div>', unsafe_allow_html=True)
    if dataset.synthetic:
        st.caption(SYNTHETIC_NOTICE)
    else:
        st.caption(f"{dataset.label}. Held in memory for this session only.")
    st.caption(f"{APP_SUBTITLE} · Built with Streamlit, SQLite and Plotly")

navigation.run()
