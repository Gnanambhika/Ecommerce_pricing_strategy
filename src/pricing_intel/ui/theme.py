"""Visual system: color tokens, global CSS and the Plotly chart template.

Palette follows a validated, colorblind-aware categorical order (slot order is
the CVD-safety mechanism, so categories always take colors in this fixed order
and keep them when filters change).
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# --- Tokens ---------------------------------------------------------------
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e9e8e2"
AXIS = "#c3c2b7"
SURFACE = "#ffffff"
PAGE = "#f7f7f4"
BORDER = "rgba(11,11,11,0.10)"
ACCENT = "#2a78d6"
ACCENT_SOFT = "#e8f1fc"
GOOD_TEXT = "#006300"
BAD_TEXT = "#c03030"
WARN_BG = "#fff6e0"
NEUTRAL_MID = "#f0efec"

CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
# Diverging blue (cheaper / better) <-> red (pricier), neutral grey midpoint.
DIVERGING = [[0.0, "#1c5cab"], [0.25, "#86b6ef"], [0.5, NEUTRAL_MID], [0.75, "#f0a0a0"], [1.0, "#c03030"]]
HIGHLIGHT_REST = "#d6d5cf"

FONT_STACK = "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"


def color_map(values) -> dict[str, str]:
    """Stable entity -> color assignment (sorted names, fixed slot order).
    More than eight entities fold the remainder into a neutral grey."""
    ordered = sorted({str(v) for v in values})
    return {v: CATEGORICAL[i] if i < len(CATEGORICAL) else MUTED for i, v in enumerate(ordered)}


# --- Plotly template --------------------------------------------------------
def register_plotly_template() -> None:
    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(family=FONT_STACK, size=13, color=INK_2),
        title=dict(font=dict(size=15, color=INK), x=0.02, xanchor="left", y=0.97),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=CATEGORICAL,
        margin=dict(l=16, r=20, t=52, b=16),
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=AXIS, font=dict(family=FONT_STACK, color=INK, size=12)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                    font=dict(size=12, color=INK_2), title_text=""),
        xaxis=dict(showgrid=False, linecolor=AXIS, ticks="outside", tickcolor=AXIS,
                   tickfont=dict(color=MUTED, size=11), title=dict(font=dict(color=MUTED, size=12)),
                   zeroline=False, automargin=True),
        yaxis=dict(gridcolor=GRID, gridwidth=1, linecolor="rgba(0,0,0,0)", zeroline=False,
                   tickfont=dict(color=MUTED, size=11), title=dict(font=dict(color=MUTED, size=12)),
                   automargin=True),
        bargap=0.35,
        hovermode="closest",
    )
    pio.templates["pricing"] = template
    pio.templates.default = "plotly_white+pricing"


# --- CSS ---------------------------------------------------------------------
_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea, select {{
    font-family: {FONT_STACK};
}}
.stApp {{ background: {PAGE}; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stDecoration"] {{ display: none; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1320px; }}

/* Sidebar */
[data-testid="stSidebar"] {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
[data-testid="stSidebar"] .sidebar-section {{
    font-size: 0.72rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
    color: {MUTED}; margin: 1.1rem 0 .4rem;
}}
[data-testid="stSidebarNav"] a span {{ font-weight: 500; }}

/* Typography */
h1, h2, h3 {{ color: {INK}; letter-spacing: -0.01em; }}
.page-header {{
    background: linear-gradient(135deg, {ACCENT_SOFT} 0%, {SURFACE} 55%);
    border: 1px solid {BORDER}; border-radius: 16px; padding: 1.4rem 1.6rem 1.2rem;
    margin-bottom: 1.4rem;
}}
.page-header .eyebrow {{ font-size: .75rem; font-weight: 600; letter-spacing: .08em;
    text-transform: uppercase; color: {ACCENT}; margin-bottom: .35rem; }}
.page-header h1 {{ font-size: 1.75rem; font-weight: 700; margin: 0; padding: 0; line-height: 1.25; }}
.page-header p {{ color: {INK_2}; margin: .45rem 0 0; font-size: .97rem; max-width: 820px; }}
.badge-row {{ display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .8rem; }}
.badge {{ display: inline-flex; align-items: center; gap: .3rem; font-size: .75rem; font-weight: 500;
    padding: .2rem .6rem; border-radius: 999px; border: 1px solid {BORDER}; background: {SURFACE};
    color: {INK_2}; }}
.badge.synthetic {{ background: {WARN_BG}; border-color: #f2d58a; color: #6b4e00; }}
.badge.sim {{ background: #f1eefc; border-color: #d4cdf6; color: #3d2f9e; }}

.section-title {{ font-size: 1.05rem; font-weight: 650; color: {INK}; margin: 1.6rem 0 .2rem; }}
.section-sub {{ font-size: .88rem; color: {INK_2}; margin: 0 0 .7rem; }}

/* KPI cards */
.kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: .8rem;
    margin: .2rem 0 .6rem; }}
.kpi {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; padding: 1rem 1.1rem .9rem;
    box-shadow: 0 1px 2px rgba(11,11,11,.04); }}
.kpi .label {{ font-size: .78rem; font-weight: 500; color: {INK_2}; display: flex; align-items: center;
    gap: .35rem; }}
.kpi .info {{ display: inline-flex; width: 15px; height: 15px; border-radius: 50%; border: 1px solid {AXIS};
    color: {MUTED}; font-size: .62rem; align-items: center; justify-content: center; cursor: help; }}
.kpi .value {{ font-size: 1.45rem; font-weight: 650; color: {INK}; margin-top: .3rem; line-height: 1.2; }}
.kpi .delta {{ font-size: .78rem; margin-top: .35rem; color: {MUTED}; }}
.kpi .delta.good {{ color: {GOOD_TEXT}; }}
.kpi .delta.bad {{ color: {BAD_TEXT}; }}
.kpi .sub {{ font-size: .75rem; color: {MUTED}; margin-top: .2rem; }}

/* Cards & callouts */
.card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; padding: 1rem 1.2rem; }}
.insight {{ background: {SURFACE}; border: 1px solid {BORDER}; border-left: 3px solid {ACCENT};
    border-radius: 10px; padding: .75rem 1rem; margin-bottom: .55rem; color: {INK_2}; font-size: .92rem; }}
.insight b {{ color: {INK}; }}
.empty-state {{ text-align: center; background: {SURFACE}; border: 1px dashed {AXIS}; border-radius: 14px;
    padding: 2.4rem 1rem; color: {INK_2}; }}
.empty-state .title {{ font-weight: 650; color: {INK}; font-size: 1.05rem; margin-bottom: .3rem; }}

/* Streamlit chart / table containers as cards */
[data-testid="stPlotlyChart"] {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px;
    overflow: hidden; }}
[data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 12px; overflow: hidden; }}
[data-testid="stExpander"] details {{ background: {SURFACE}; border-radius: 12px; }}

.sidebar-footer {{ font-size: .75rem; color: {MUTED}; line-height: 1.45; margin-top: 1rem; }}

@media (max-width: 640px) {{
    .block-container {{ padding-left: 1rem; padding-right: 1rem; padding-top: 1.2rem; }}
    .page-header {{ padding: 1rem 1.1rem; }}
    .page-header h1 {{ font-size: 1.35rem; }}
    .kpi .value {{ font-size: 1.3rem; }}
}}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
