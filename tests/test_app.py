"""UI smoke tests: every page renders without exceptions (Streamlit AppTest)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "src" / "pricing_intel" / "ui" / "pages"

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def run_page(page: str | None):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.run()
    if page:
        at.switch_page(str(PAGES / f"{page}.py"))
        at.run()
    return at


@pytest.mark.parametrize("page", [None, "pricing", "discounts", "elasticity", "simulator", "data_quality"])
def test_page_renders(page):
    at = run_page(page)
    assert not at.exception, [e.value for e in at.exception]


def test_synthetic_label_is_visible():
    at = run_page(None)
    assert any("Synthetic" in c.value for c in at.sidebar.caption)


def test_simulator_warns_below_cost():
    at = run_page("simulator")
    at.slider(key="sim_price_pct").set_value(-50).run()
    at.slider(key="sim_cost_pct").set_value(30).run()
    assert not at.exception
    texts = " ".join(w.value for w in at.warning)
    assert "outside ±" in texts


def test_empty_filter_shows_empty_state():
    at = run_page(None)
    at.date_input(key="f_dates").set_value((at.date_input(key="f_dates").value[0],) * 2).run()
    at.multiselect(key="f_platforms").set_value(["Direct Store (D2C)"]).run()
    assert not at.exception
