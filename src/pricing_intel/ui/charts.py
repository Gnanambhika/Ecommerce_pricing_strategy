"""Plotly chart builders. One measure per y-axis (no dual-axis charts),
entity colors fixed by name, recessive grid, hover on every mark."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..config import CURRENCY_SYMBOL
from . import theme as t

CUR = CURRENCY_SYMBOL


def _base(fig: go.Figure, title: str, height: int = 340) -> go.Figure:
    fig.update_layout(title_text=title, height=height)
    return fig


def bar_over_time(df: pd.DataFrame, x: str, y: str, title: str, currency: bool = True,
                  hover_label: str = "Value", height: int = 320) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=df[x], y=df[y], marker=dict(color=t.ACCENT, cornerradius=4),
        hovertemplate=f"%{{x|%b %Y}}<br>{hover_label}: {CUR if currency else ''}%{{y:,.0f}}<extra></extra>",
    ))
    fig.update_yaxes(tickprefix=CUR if currency else "", tickformat="~s")
    fig.update_xaxes(tickformat="%b %y")
    return _base(fig, title, height)


def line_over_time(df: pd.DataFrame, x: str, y: str, title: str, pct_axis: bool = True,
                   hover_label: str = "Value", height: int = 320) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=df[x], y=df[y], mode="lines+markers", line=dict(color=t.ACCENT, width=2),
        marker=dict(size=7, color=t.ACCENT, line=dict(color=t.SURFACE, width=2)),
        hovertemplate=f"%{{x|%b %Y}}<br>{hover_label}: %{{y:.1%}}<extra></extra>" if pct_axis
        else f"%{{x|%b %Y}}<br>{hover_label}: %{{y:,.0f}}<extra></extra>",
    ))
    if pct_axis:
        fig.update_yaxes(tickformat=".0%")
    fig.update_xaxes(tickformat="%b %y")
    fig.update_layout(hovermode="x unified")
    return _base(fig, title, height)


def hbar(df: pd.DataFrame, label: str, value: str, title: str, value_format: str = "currency",
         height: int | None = None, text: pd.Series | None = None, color: str = t.ACCENT) -> go.Figure:
    d = df.sort_values(value, ascending=True)
    if value_format == "currency":
        hover, tick = f"{CUR}%{{x:,.0f}}", dict(tickprefix=CUR, tickformat="~s")
    elif value_format == "pct":
        hover, tick = "%{x:.1%}", dict(tickformat=".0%")
    else:
        hover, tick = "%{x:,.0f}", dict(tickformat="~s")
    fig = go.Figure(go.Bar(
        y=d[label], x=d[value], orientation="h", marker=dict(color=color, cornerradius=4),
        text=None if text is None else text.loc[d.index], textposition="outside", cliponaxis=False,
        textfont=dict(color=t.INK_2, size=11),
        hovertemplate=f"%{{y}}<br>{hover}<extra></extra>",
    ))
    vmax = float(d[value].max()) if len(d) else 0.0
    room = 1.45 if text is not None else 1.05
    fig.update_xaxes(showgrid=True, gridcolor=t.GRID, range=[min(0.0, float(d[value].min())) * 1.1, vmax * room],
                     **tick)
    fig.update_yaxes(showgrid=False)
    return _base(fig, title, height or max(260, 46 * len(d) + 80))


def band_bars(df: pd.DataFrame, band: str, value: str, title: str, value_format: str,
              hover_label: str, height: int = 320, ordinal: bool = True) -> go.Figure:
    """Bars across ordered bands (discount depth, price position)."""
    labels = df[band].str.replace(r"^\d\.\s*", "", regex=True)
    n = len(df)
    if ordinal and n > 1:
        ramp = t.SEQUENTIAL_BLUE[2:]
        colors = [ramp[min(int(i * (len(ramp) - 1) / max(n - 1, 1)), len(ramp) - 1)] for i in range(n)]
    else:
        colors = [t.ACCENT] * n
    colors = [t.HIGHLIGHT_REST if "No competitor" in str(b) else c for b, c in zip(df[band], colors, strict=True)]
    if value_format == "pct":
        hover, ticks = "%{y:.1%}", dict(tickformat=".0%")
    elif value_format == "currency":
        hover, ticks = f"{CUR}%{{y:,.0f}}", dict(tickprefix=CUR, tickformat="~s")
    else:
        hover, ticks = "%{y:,.1f}", dict(tickformat="~s")
    fig = go.Figure(go.Bar(
        x=labels, y=df[value], marker=dict(color=colors, cornerradius=4),
        customdata=df[["observations"]] if "observations" in df else None,
        hovertemplate=f"%{{x}}<br>{hover_label}: {hover}"
        + ("<br>Observations: %{customdata[0]:,}" if "observations" in df else "") + "<extra></extra>",
    ))
    fig.update_yaxes(**ticks)
    return _base(fig, title, height)


def heatmap(pivot: pd.DataFrame, title: str, zmid: float | None = 0.0, pct: bool = True,
            colorscale=None, height: int | None = None, colorbar_title: str = "") -> go.Figure:
    z = pivot.to_numpy(dtype=float)
    text = np.vectorize(lambda v: "" if np.isnan(v) else (f"{v:+.1%}" if pct and zmid is not None
                                                       else f"{v:.1%}" if pct else f"{v:,.0f}"))(z)
    fig = go.Figure(go.Heatmap(
        z=z, x=list(pivot.columns), y=list(pivot.index), text=text, texttemplate="%{text}",
        textfont=dict(size=12), colorscale=colorscale or t.DIVERGING, zmid=zmid, xgap=2, ygap=2,
        hovertemplate="%{y} · %{x}<br>%{text}<extra></extra>",
        colorbar=dict(title=dict(text=colorbar_title, side="right"), thickness=10, outlinewidth=0,
                      tickformat=".0%" if pct else "~s"),
    ))
    fig.update_xaxes(showgrid=False, side="top", ticks="")
    fig.update_yaxes(showgrid=False, autorange="reversed")
    return _base(fig, title, height or max(280, 48 * len(pivot.index) + 110))


def price_vs_competitor_scatter(prod: pd.DataFrame, highlight: str | None) -> go.Figure:
    """Our average price vs competitor average price per product (log axes).
    One highlighted category in color, the rest muted, to stay readable."""
    fig = go.Figure()
    lo = float(min(prod["avg_price"].min(), prod["avg_comp"].min())) * 0.85
    hi = float(max(prod["avg_price"].max(), prod["avg_comp"].max())) * 1.15
    fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", line=dict(color=t.AXIS, width=1.5),
                             hoverinfo="skip", name="Price parity", showlegend=True))
    groups = [("Other categories", prod[prod["category"] != highlight], t.HIGHLIGHT_REST)] if highlight else []
    focus = prod[prod["category"] == highlight] if highlight else prod
    groups.append((highlight or "All products", focus, t.ACCENT))
    size_ref = 2.0 * prod["units"].max() / (26 ** 2) if prod["units"].max() > 0 else 1
    for name, d, color in groups:
        fig.add_trace(go.Scatter(
            x=d["avg_comp"], y=d["avg_price"], mode="markers", name=name,
            marker=dict(size=d["units"], sizemode="area", sizeref=size_ref, sizemin=5, color=color,
                        opacity=0.85, line=dict(color=t.SURFACE, width=1.5)),
            customdata=np.stack([d["product_name"], d["category"], d["gap_pct"], d["units"]], axis=-1),
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>"
                          f"Our avg price: {CUR}%{{y:,.0f}}<br>Competitor: {CUR}%{{x:,.0f}}<br>"
                          "Gap: %{customdata[2]:+.1%}<br>Units: %{customdata[3]:,.0f}<extra></extra>",
        ))
    ticks = [v for v in (50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000) if lo <= v <= hi]
    labels = [f"{CUR}{v / 1000:g}K" if v >= 1000 else f"{CUR}{v}" for v in ticks]
    fig.update_xaxes(type="log", title_text="Competitor average price (log scale)", showgrid=True,
                     gridcolor=t.GRID, tickvals=ticks, ticktext=labels)
    fig.update_yaxes(type="log", title_text="Our average selling price (log scale)", tickvals=ticks,
                     ticktext=labels)
    return _base(fig, "Our price vs competitor price, by product", 460)


def price_history(d: pd.DataFrame, title: str) -> go.Figure:
    fig = go.Figure()
    series = [
        ("original_price", "List price", t.AXIS, "dot"),
        ("competitor_price", "Competitor price", t.CATEGORICAL[1], "solid"),
        ("selling_price", "Our selling price", t.ACCENT, "solid"),
    ]
    for col, name, color, dash in series:
        fig.add_trace(go.Scatter(
            x=d["date"], y=d[col], name=name, mode="lines", connectgaps=False,
            line=dict(color=color, width=2, dash=dash, shape="hv"),
            hovertemplate=f"{name}: {CUR}%{{y:,.0f}}<extra></extra>",
        ))
    fig.update_yaxes(tickprefix=CUR, tickformat=",.0f")
    fig.update_layout(hovermode="x unified")
    return _base(fig, title, 340)


def units_history(d: pd.DataFrame, title: str) -> go.Figure:
    colors = np.where(d["promo_flag"].fillna(0) == 1, t.CATEGORICAL[1], t.ACCENT) \
        if "promo_flag" in d else t.ACCENT
    fig = go.Figure(go.Bar(
        x=d["date"], y=d["units_sold"], marker=dict(color=colors, cornerradius=3),
        hovertemplate="%{x|%d %b %Y}<br>Units: %{y:,}<extra></extra>", showlegend=False,
    ))
    fig.update_layout(bargap=0.2)
    return _base(fig, title, 260)


def pareto(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=df["product_share"], y=df["cumulative_share"], mode="lines",
        line=dict(color=t.ACCENT, width=2.5), fill="tozeroy", fillcolor="rgba(42,120,214,0.08)",
        customdata=np.stack([df["product_rank"], df["product_name"]], axis=-1),
        hovertemplate="Top %{x:.0%} of products (#%{customdata[0]})<br>"
                      "→ %{y:.0%} of gross profit<extra></extra>",
    ))
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=t.AXIS, width=1),
                             hoverinfo="skip", showlegend=False))
    fig.update_xaxes(tickformat=".0%", title_text="Share of products (ranked by gross profit)",
                     range=[0, 1])
    fig.update_yaxes(tickformat=".0%", title_text="Cumulative share of gross profit")
    fig.update_layout(showlegend=False)
    return _base(fig, "Profit concentration", 360)


def discount_margin_scatter(prod: pd.DataFrame, highlight: str | None) -> go.Figure:
    fig = go.Figure()
    groups = [("Other categories", prod[prod["category"] != highlight], t.HIGHLIGHT_REST)] if highlight else []
    groups.append((highlight or "All products", prod[prod["category"] == highlight] if highlight else prod, t.ACCENT))
    for name, d, color in groups:
        fig.add_trace(go.Scatter(
            x=d["effective_discount_rate"], y=d["gross_margin_pct"], mode="markers", name=name,
            marker=dict(size=9, color=color, opacity=0.85, line=dict(color=t.SURFACE, width=1.5)),
            customdata=np.stack([d["product_name"], d["category"], d["revenue"]], axis=-1),
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>Discount: %{x:.1%}"
                          f"<br>Gross margin: %{{y:.1%}}<br>Revenue: {CUR}%{{customdata[2]:,.0f}}<extra></extra>",
        ))
    fig.update_xaxes(tickformat=".0%", title_text="Effective discount rate", showgrid=True, gridcolor=t.GRID)
    fig.update_yaxes(tickformat=".0%", title_text="Gross margin")
    return _base(fig, "Discount depth vs gross margin, by product", 400)


def elasticity_forest(est: pd.DataFrame, truth: dict[str, float] | None = None) -> go.Figure:
    d = est.dropna(subset=["elasticity"]).iloc[::-1]
    fig = go.Figure()
    fig.add_vline(x=-1, line=dict(color=t.AXIS, width=1))
    fig.add_vline(x=0, line=dict(color=t.AXIS, width=1))
    fig.add_trace(go.Scatter(
        x=d["naive_elasticity"], y=d["group"], mode="markers", name="Naive (no controls)",
        marker=dict(symbol="circle-open", size=10, color=t.MUTED, line=dict(width=2)),
        hovertemplate="%{y}<br>Naive slope: %{x:.2f}<extra></extra>",
    ))
    if truth:
        tv = d["group"].map(truth)
        fig.add_trace(go.Scatter(
            x=tv, y=d["group"], mode="markers", name="True value (synthetic generator)",
            marker=dict(symbol="diamond", size=10, color=t.CATEGORICAL[1], line=dict(color=t.SURFACE, width=1.5)),
            hovertemplate="%{y}<br>Generator's true elasticity: %{x:.2f}<extra></extra>",
        ))
    fig.add_trace(go.Scatter(
        x=d["elasticity"], y=d["group"], mode="markers", name="Fixed-effects estimate (95% CI)",
        error_x=dict(type="data", symmetric=False, array=d["ci_high"] - d["elasticity"],
                     arrayminus=d["elasticity"] - d["ci_low"], color=t.ACCENT, thickness=2, width=0),
        marker=dict(size=11, color=t.ACCENT, line=dict(color=t.SURFACE, width=2)),
        customdata=np.stack([d["ci_low"], d["ci_high"], d["n_obs"]], axis=-1),
        hovertemplate="%{y}<br>Elasticity: %{x:.2f}<br>95% CI: %{customdata[0]:.2f} to %{customdata[1]:.2f}"
                      "<br>Observations: %{customdata[2]:,}<extra></extra>",
    ))
    fig.update_xaxes(title_text="Elasticity (% change in units per 1% change in price)", showgrid=True,
                     gridcolor=t.GRID, zeroline=False)
    fig.update_yaxes(showgrid=False)
    return _base(fig, "Estimated own-price elasticity by category", max(320, 52 * len(d) + 120))


def binned_scatter(b: pd.DataFrame, slope: float | None, title: str) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=b["price_dev_pct"], y=b["units_dev_pct"], mode="markers", name="Binned observations",
        marker=dict(size=10, color=t.ACCENT, line=dict(color=t.SURFACE, width=2)),
        customdata=b[["n"]],
        hovertemplate="Price vs usual: %{x:+.1f}%<br>Units vs usual: %{y:+.1f}%"
                      "<br>Observations in bin: %{customdata[0]:,}<extra></extra>",
    ))
    if slope is not None and not np.isnan(slope) and len(b):
        xs = np.linspace(b["price_dev_pct"].min(), b["price_dev_pct"].max(), 50)
        ys = (np.power(1 + xs / 100, slope) - 1) * 100
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=f"Fitted elasticity {slope:.2f}",
                                 line=dict(color=t.CATEGORICAL[1], width=2), hoverinfo="skip"))
    fig.update_xaxes(title_text="Price vs the product's usual level (%)", ticksuffix="%", showgrid=True,
                     gridcolor=t.GRID, zeroline=True, zerolinecolor=t.AXIS)
    fig.update_yaxes(title_text="Units vs usual level (%)", ticksuffix="%", zeroline=True, zerolinecolor=t.AXIS)
    return _base(fig, title, 380)


def profit_curve(curve: pd.DataFrame, baseline_price: float, scenario_price: float,
                 optimal_price: float | None = None) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=curve["price"], y=curve["revenue"], name="Revenue", mode="lines",
                             line=dict(color=t.CATEGORICAL[6], width=2),
                             hovertemplate=f"Price {CUR}%{{x:,.0f}}<br>Revenue {CUR}%{{y:,.0f}}<extra></extra>"))
    fig.add_trace(go.Scatter(x=curve["price"], y=curve["gross_profit"], name="Gross profit", mode="lines",
                             line=dict(color=t.ACCENT, width=2.5),
                             hovertemplate=f"Price {CUR}%{{x:,.0f}}<br>Gross profit {CUR}%{{y:,.0f}}<extra></extra>"))
    fig.add_vline(x=baseline_price, line=dict(color=t.MUTED, width=1.5),
                  annotation_text="Baseline", annotation_position="top left",
                  annotation_font=dict(color=t.INK_2, size=11))
    fig.add_vline(x=scenario_price, line=dict(color=t.CATEGORICAL[1], width=1.5),
                  annotation_text="Scenario", annotation_position="top right",
                  annotation_font=dict(color=t.INK_2, size=11))
    if optimal_price and curve["price"].min() <= optimal_price <= curve["price"].max():
        fig.add_vline(x=optimal_price, line=dict(color=t.CATEGORICAL[2], width=1.5),
                      annotation_text="Model optimum", annotation_position="bottom right",
                      annotation_font=dict(color=t.INK_2, size=11))
    fig.update_xaxes(tickprefix=CUR, tickformat=",.0f", title_text="Price per unit", showgrid=True, gridcolor=t.GRID)
    fig.update_yaxes(tickprefix=CUR, tickformat="~s", title_text="Weekly amount")
    fig.update_layout(hovermode="x unified")
    return _base(fig, "Revenue & gross profit by price", 400)


def baseline_vs_scenario(base: dict, scen: dict) -> go.Figure:
    metrics = [("revenue", "Revenue"), ("cogs", "COGS"), ("gross_profit", "Gross profit")]
    labels = [m[1] for m in metrics]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Baseline (observed)", x=labels, y=[base[k] for k, _ in metrics],
                         marker=dict(color=t.HIGHLIGHT_REST, cornerradius=4),
                         hovertemplate=f"%{{x}} baseline: {CUR}%{{y:,.0f}}<extra></extra>"))
    fig.add_trace(go.Bar(name="Scenario (simulated)", x=labels, y=[scen[k] for k, _ in metrics],
                         marker=dict(color=t.ACCENT, cornerradius=4),
                         hovertemplate=f"%{{x}} scenario: {CUR}%{{y:,.0f}}<extra></extra>"))
    fig.update_yaxes(tickprefix=CUR, tickformat="~s")
    fig.update_layout(barmode="group", bargroupgap=0.08)
    return _base(fig, "Baseline vs scenario", 340)


def completeness_bar(comp: dict[str, float]) -> go.Figure:
    d = pd.DataFrame({"column": list(comp.keys()), "complete": list(comp.values())})
    colors = [t.ACCENT if v >= 0.95 else "#fab219" if v >= 0.5 else "#d03b3b" for v in d["complete"]]
    d = d.iloc[::-1]
    fig = go.Figure(go.Bar(
        y=d["column"], x=d["complete"], orientation="h", marker=dict(color=colors[::-1], cornerradius=4),
        text=[f"{v:.1%}" for v in d["complete"]], textposition="outside", cliponaxis=False,
        textfont=dict(color=t.INK_2, size=11), hovertemplate="%{y}: %{x:.1%} populated<extra></extra>",
    ))
    fig.update_xaxes(range=[0, 1.2], tickformat=".0%", showgrid=True, gridcolor=t.GRID)
    return _base(fig, "Field completeness", 420)
