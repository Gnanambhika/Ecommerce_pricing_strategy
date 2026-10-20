"""Reusable UI building blocks.

All dynamic text inserted into HTML is escaped with ``html.escape`` (product
names, categories and file names can come from a user's uploaded CSV).
"""

from __future__ import annotations

import html
import inspect
import re
from dataclasses import dataclass

import pandas as pd
import streamlit as st

_PLOTLY_HAS_WIDTH = "width" in inspect.signature(st.plotly_chart).parameters
_DATAFRAME_HAS_WIDTH = "width" in inspect.signature(st.dataframe).parameters
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

PLOTLY_CONFIG = {
    "displaylogo": False,
    "displayModeBar": "hover",
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d", "toggleSpikelines"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def _rich(text: str) -> str:
    """Escape, then allow **bold** markers only."""
    return _BOLD_RE.sub(r"<b>\1</b>", esc(text))


def page_header(title: str, subtitle: str, eyebrow: str = "", badges: list[tuple[str, str]] | None = None) -> None:
    """badges: list of (text, css_class) e.g. ("Synthetic data", "synthetic")."""
    badge_html = ""
    if badges:
        items = "".join(f'<span class="badge {esc(cls)}">{esc(txt)}</span>' for txt, cls in badges)
        badge_html = f'<div class="badge-row">{items}</div>'
    eyebrow_html = f'<div class="eyebrow">{esc(eyebrow)}</div>' if eyebrow else ""
    st.markdown(
        f'<div class="page-header">{eyebrow_html}<h1>{esc(title)}</h1>'
        f"<p>{_rich(subtitle)}</p>{badge_html}</div>",
        unsafe_allow_html=True,
    )


@dataclass
class Kpi:
    label: str
    value: str
    delta: str | None = None
    sentiment: str = "neutral"  # good | bad | neutral
    help: str | None = None
    sub: str | None = None


def kpi_row(kpis: list[Kpi]) -> None:
    cards = []
    for k in kpis:
        info = f'<span class="info" title="{esc(k.help)}">i</span>' if k.help else ""
        arrow = ""
        if k.delta and k.sentiment in ("good", "bad"):
            arrow = "▲ " if not k.delta.strip().startswith("-") else "▼ "
        delta = f'<div class="delta {esc(k.sentiment)}">{arrow}{esc(k.delta)}</div>' if k.delta else ""
        sub = f'<div class="sub">{esc(k.sub)}</div>' if k.sub else ""
        cards.append(
            f'<div class="kpi"><div class="label">{esc(k.label)}{info}</div>'
            f'<div class="value">{esc(k.value)}</div>{delta}{sub}</div>'
        )
    st.markdown(f'<div class="kpi-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def section(title: str, subtitle: str = "") -> None:
    sub = f'<div class="section-sub">{_rich(subtitle)}</div>' if subtitle else ""
    st.markdown(f'<div class="section-title">{esc(title)}</div>{sub}', unsafe_allow_html=True)


def insight(text: str) -> None:
    st.markdown(f'<div class="insight">{_rich(text)}</div>', unsafe_allow_html=True)


def empty_state(title: str = "No data for this selection",
                message: str = "Widen the date range or clear some filters in the sidebar.") -> None:
    st.markdown(
        f'<div class="empty-state"><div class="title">{esc(title)}</div><div>{esc(message)}</div></div>',
        unsafe_allow_html=True,
    )


def show_chart(fig, key: str | None = None) -> None:
    kwargs = {"config": PLOTLY_CONFIG, "key": key}
    if _PLOTLY_HAS_WIDTH:
        kwargs["width"] = "stretch"
    else:
        kwargs["use_container_width"] = True
    st.plotly_chart(fig, **kwargs)


def show_table(df: pd.DataFrame, column_config: dict | None = None, height: int | None = None) -> None:
    kwargs = {"hide_index": True, "column_config": column_config or {}}
    if height is None and len(df) <= 20:
        height = 38 + 35 * max(len(df), 1)  # show every row without an inner scrollbar
    if height:
        kwargs["height"] = height
    if _DATAFRAME_HAS_WIDTH:
        kwargs["width"] = "stretch"
    else:
        kwargs["use_container_width"] = True
    st.dataframe(df, **kwargs)


def delta_sentiment(change: float, higher_is_better: bool = True) -> str:
    if change is None or pd.isna(change) or change == 0:
        return "neutral"
    return "good" if (change > 0) == higher_is_better else "bad"
