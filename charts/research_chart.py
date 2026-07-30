"""The Research Workspace's primary chart: every analytical conclusion the workspace
draws (structure, levels, the featured pattern, invalidation, cyclical turning points)
is rendered directly on the chart rather than only described in text below it.

This module only reads outputs already computed elsewhere (technical/engine.py,
technical/assessment.py, analysis/security_signal.py) and draws them — it computes no
new indicator itself beyond simple geometry (extending a trendline, sizing a shaded
band).
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.security_signal import SignalEvent
from technical.assessment import TechnicalAssessment
from technical.engine import FibonacciLevels, TechnicalSettings, _swing_points, add_moving_averages, calculate_rsi

_MA_COLORS = ["#ff5b49", "#00d6b4", "#a95cff", "#f5b642", "#3d8bfd", "#f472b6", "#94a3b8", "#22c55e"]
_UP_COLOR = "#18d47b"
_DOWN_COLOR = "#ff4f5e"
_FIB_COLOR = "#c9a227"
_INVALIDATION_COLOR = "#ff3b3b"
_BREAKOUT_COLOR = {"BULLISH": "34,197,94", "BEARISH": "239,68,68", "NEUTRAL": "148,163,184"}


def _valid_zone(zone: dict[str, Any]) -> bool:
    try:
        low, high = float(zone["low"]), float(zone["high"])
        return np.isfinite(low) and np.isfinite(high) and 0 < low < high
    except (KeyError, TypeError, ValueError):
        return False


def _add_level_zones(fig: go.Figure, zones: Sequence[dict[str, Any]], role: str, index: pd.Index) -> None:
    color = "34,197,94" if role == "support" else "239,68,68"
    for position, zone in enumerate(z for z in zones if _valid_zone(z)):
        if position >= 4:
            break
        origin = pd.to_datetime(zone.get("first_date", index[0]), errors="coerce")
        if pd.isna(origin):
            origin = index[0]
        major = zone.get("strength", 0) >= 70
        nearest = position == 0
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=max(origin, index[0]),
            x1=index[-1],
            y0=float(zone["low"]),
            y1=float(zone["high"]),
            fillcolor=f"rgba({color},{0.26 if nearest else 0.12})",
            line={
                "color": f"rgba({color},{0.9 if nearest else 0.4})",
                "width": 1.4 if major else 0.7,
                "dash": "solid" if major else "dot",
            },
            layer="below",
        )
        fig.add_annotation(
            x=index[-1],
            y=float(zone["center"]),
            xanchor="left",
            text=f"{'MAJOR' if major else 'minor'} {role.upper()} {zone['center']:,.2f}" if nearest else "",
            showarrow=False,
            font={"size": 9, "color": f"rgb({color})"},
            xshift=6,
        )


def _extend_trendline(anchors: Sequence[tuple[Any, float]], end_date: Any) -> tuple[list[Any], list[float]]:
    ordered = sorted(anchors, key=lambda p: p[0])
    xs: list[Any] = [p[0] for p in ordered]
    ys: list[float] = [float(p[1]) for p in ordered]
    if len(ordered) >= 2 and pd.Timestamp(end_date) > pd.Timestamp(xs[-1]):
        x0, y0 = ordered[-2]
        x1, y1 = ordered[-1]
        dx_days = (pd.Timestamp(x1) - pd.Timestamp(x0)).days or 1
        slope = (y1 - y0) / dx_days
        extra_days = (pd.Timestamp(end_date) - pd.Timestamp(x1)).days
        xs.append(end_date)
        ys.append(y1 + slope * extra_days)
    return xs, ys


def _add_pattern_layer(fig: go.Figure, pattern: dict[str, Any], index: pd.Index) -> None:
    end_date = index[-1]
    direction_color = _BREAKOUT_COLOR.get(pattern.get("direction", "NEUTRAL"), _BREAKOUT_COLOR["NEUTRAL"])

    highlight_start = pattern.get("highlight_start")
    highlight_end = pattern.get("highlight_end")
    if highlight_start is not None and highlight_end is not None:
        short_name = pattern["name"].replace("Potential ", "").upper()
        fig.add_vrect(
            x0=highlight_start,
            x1=highlight_end,
            fillcolor=f"rgba({direction_color},0.10)",
            line_width=0,
            layer="below",
            annotation_text=short_name,
            annotation_position="top",
            annotation_font={"size": 10, "color": f"rgb({direction_color})"},
        )

    for boundary in (pattern.get("upper") or [], pattern.get("lower") or []):
        if len(boundary) < 2:
            continue
        xs, ys = _extend_trendline(boundary, end_date)
        fig.add_trace(
            go.Scatter(
                x=xs, y=ys, mode="lines", name=f"{pattern['name']} boundary",
                line={"width": 1.6, "color": f"rgb({direction_color})", "dash": "solid"},
                showlegend=False, hoverinfo="skip",
            )
        )

    zone = pattern.get("expected_breakout_zone")
    if zone:
        fig.add_shape(
            type="rect", xref="x", yref="y",
            x0=pattern.get("end", index[0]), x1=end_date,
            y0=zone[0], y1=zone[1],
            fillcolor=f"rgba({direction_color},0.22)",
            line={"color": f"rgb({direction_color})", "width": 1.0, "dash": "dot"},
            layer="below",
        )
        fig.add_annotation(
            x=end_date, y=(zone[0] + zone[1]) / 2, xanchor="left",
            text="BREAKOUT ZONE", showarrow=False,
            font={"size": 9, "color": f"rgb({direction_color})"}, xshift=6,
        )

    trigger = pattern.get("trigger")
    if trigger is not None:
        fig.add_hline(
            y=trigger, line_dash="dot", line_color=f"rgb({direction_color})", line_width=1.2,
            annotation_text=f"TRIGGER {trigger:,.2f}", annotation_position="right",
            annotation_font={"size": 9, "color": f"rgb({direction_color})"},
        )


def _add_fibonacci_layer(fig: go.Figure, fib: FibonacciLevels, index: pd.Index) -> None:
    start_date = fib.swing_start[0]
    for label, price in fib.levels.items():
        fig.add_shape(
            type="line", xref="x", yref="y",
            x0=start_date, x1=index[-1], y0=price, y1=price,
            line={"color": _FIB_COLOR, "width": 1.0, "dash": "dash"},
            layer="below",
        )
        fig.add_annotation(
            x=index[-1], y=price, xanchor="left", text=f"FIB {label}",
            showarrow=False, font={"size": 9, "color": _FIB_COLOR}, xshift=6,
        )


def _add_swing_markers(fig: go.Figure, frame: pd.DataFrame, settings: TechnicalSettings) -> None:
    recent = frame.tail(min(settings.lookback, 260))
    highs = _swing_points(recent["High"], settings.swing_window, "high")
    lows = _swing_points(recent["Low"], settings.swing_window, "low")
    if not highs.empty:
        fig.add_trace(
            go.Scatter(
                x=highs.index, y=highs.to_numpy() * 1.004, mode="markers", name="Swing high",
                marker={"symbol": "triangle-down", "size": 7, "color": "rgba(255,79,94,0.85)"},
                hovertemplate="Swing high: %{y:.2f}<extra></extra>", showlegend=False,
            )
        )
    if not lows.empty:
        fig.add_trace(
            go.Scatter(
                x=lows.index, y=lows.to_numpy() * 0.996, mode="markers", name="Swing low",
                marker={"symbol": "triangle-up", "size": 7, "color": "rgba(24,212,123,0.85)"},
                hovertemplate="Swing low: %{y:.2f}<extra></extra>", showlegend=False,
            )
        )


_TURNING_POINT_STYLE = {
    "BUY": {"symbol": "triangle-up", "color": "#18d47b"},
    "SELL SHORT": {"symbol": "triangle-down", "color": "#ff4f5e"},
    "TAKE PROFIT": {"symbol": "diamond", "color": "#ff9f00"},
}


def _add_cyclical_turning_points(fig: go.Figure, close: pd.Series, events: Sequence[SignalEvent]) -> None:
    by_action: dict[str, list[tuple[Any, float, str]]] = {}
    for event in events[-12:]:
        price = close.asof(event.date)
        if price is None or pd.isna(price):
            continue
        by_action.setdefault(event.action, []).append(
            (event.date, float(price), f"{event.action} · {pd.Timestamp(event.date).strftime('%d %b %Y')} · Rating {event.rating}/4")
        )
    for action, points in by_action.items():
        style = _TURNING_POINT_STYLE.get(action)
        if not style or not points:
            continue
        xs, ys, texts = zip(*points)
        fig.add_trace(
            go.Scatter(
                x=list(xs), y=list(ys), mode="markers", name=f"Cyclical: {action}",
                marker={"symbol": style["symbol"], "size": 11, "color": style["color"], "line": {"width": 1, "color": "#05070a"}},
                text=list(texts), hovertemplate="%{text}<extra></extra>",
            )
        )


def build_research_chart(
    ticker: str,
    daily_frame: pd.DataFrame,
    settings: TechnicalSettings,
    assessment: TechnicalAssessment,
    patterns: list[dict[str, Any]] | None = None,
    fib_levels: FibonacciLevels | None = None,
    turning_points: Sequence[SignalEvent] | None = None,
    visible_bars: int = 260,
) -> go.Figure:
    display = add_moving_averages(daily_frame.sort_index().copy(), settings.ma_periods)
    rsi = calculate_rsi(display["Close"], settings.rsi_period).reindex(display.index)

    volume = pd.Series(0.0, index=display.index)
    if "Volume" in display.columns:
        volume = pd.to_numeric(display["Volume"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)
    has_volume = bool(volume.gt(0).any())

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.012, row_heights=[0.68, 0.11, 0.21])

    diagnostics = assessment.snapshot.diagnostics
    _add_level_zones(fig, diagnostics.get("supports", []), "support", display.index)
    _add_level_zones(fig, diagnostics.get("resistances", []), "resistance", display.index)
    if fib_levels is not None:
        _add_fibonacci_layer(fig, fib_levels, display.index)
    if patterns:
        _add_pattern_layer(fig, patterns[0], display.index)

    fig.add_trace(
        go.Candlestick(
            x=display.index, open=display["Open"], high=display["High"], low=display["Low"], close=display["Close"],
            name=ticker, increasing_line_color=_UP_COLOR, decreasing_line_color=_DOWN_COLOR,
            increasing_fillcolor=_UP_COLOR, decreasing_fillcolor=_DOWN_COLOR, whiskerwidth=0.22,
        ),
        row=1, col=1,
    )

    for index, period in enumerate(settings.ma_periods):
        column = f"MA{period}"
        if column in display:
            fig.add_trace(
                go.Scatter(
                    x=display.index, y=display[column], mode="lines", name=column,
                    line={"width": 1.4, "color": _MA_COLORS[index % len(_MA_COLORS)]},
                    hovertemplate=f"{column}: %{{y:.2f}}<extra></extra>",
                ),
                row=1, col=1,
            )

    _add_swing_markers(fig, display, settings)

    if assessment.invalidation_price is not None:
        fig.add_hline(
            y=assessment.invalidation_price, line_dash="dash", line_color=_INVALIDATION_COLOR, line_width=1.8,
            annotation_text=f"INVALIDATION {assessment.invalidation_price:,.2f}", annotation_position="right",
            annotation_font={"size": 10, "color": _INVALIDATION_COLOR}, row=1, col=1,
        )

    if turning_points:
        _add_cyclical_turning_points(fig, display["Close"], turning_points)

    if has_volume:
        volume_colors = np.where(display["Close"].to_numpy() >= display["Open"].to_numpy(), "rgba(24,212,123,0.82)", "rgba(255,79,94,0.82)")
        fig.add_trace(
            go.Bar(x=display.index, y=volume, name="Volume", marker={"color": volume_colors, "line": {"width": 0}},
                   opacity=0.92, hovertemplate="Volume: %{y:,.0f}<extra></extra>", showlegend=False),
            row=2, col=1,
        )
    else:
        fig.add_annotation(text="Volume unavailable", xref="x2 domain", yref="y2 domain", x=0.01, y=0.52,
                            showarrow=False, font={"size": 10, "color": "#818a99"})

    fig.add_trace(
        go.Scatter(x=display.index, y=rsi, mode="lines", name=f"RSI({settings.rsi_period})",
                    line={"width": 1.4, "color": "#338dff"}, hovertemplate=f"RSI({settings.rsi_period}): %{{y:.1f}}<extra></extra>",
                    showlegend=False),
        row=3, col=1,
    )
    fig.add_hrect(y0=70, y1=100, fillcolor="rgba(239,68,68,0.075)", line_width=0, row=3, col=1)
    fig.add_hrect(y0=0, y1=30, fillcolor="rgba(51,141,255,0.075)", line_width=0, row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="rgba(148,163,184,0.62)", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="rgba(148,163,184,0.62)", row=3, col=1)

    visible = display.tail(visible_bars) if len(display) > visible_bars else display
    initial_range = [visible.index[0], visible.index[-1]]

    price_low, price_high = float(visible["Low"].min()), float(visible["High"].max())
    extra_prices: list[float] = []
    if assessment.invalidation_price is not None:
        extra_prices.append(assessment.invalidation_price)
    if fib_levels is not None:
        extra_prices.extend(fib_levels.levels.values())
    for zone in (diagnostics.get("supports", []) + diagnostics.get("resistances", []))[:8]:
        if _valid_zone(zone):
            extra_prices.extend([float(zone["low"]), float(zone["high"])])
    in_range = [p for p in extra_prices if price_low * 0.85 <= p <= price_high * 1.15]
    if in_range:
        price_low, price_high = min(price_low, min(in_range)), max(price_high, max(in_range))
    padding = max((price_high - price_low) * 0.06, price_high * 0.01)

    fig.update_yaxes(range=[max(0.01, price_low - padding), price_high + padding], fixedrange=False, zeroline=False, tickformat=",.2f", row=1, col=1)

    if has_volume:
        visible_volume = volume.reindex(visible.index)
        positive = visible_volume[visible_volume > 0]
        upper = float(positive.quantile(0.985) * 1.18) if not positive.empty else 1.0
        upper = max(upper, float(positive.median() * 2.0) if not positive.empty else 1.0)
        fig.update_yaxes(range=[0, upper], fixedrange=False, showgrid=False, zeroline=False, title_text="VOL", tickformat="~s", nticks=3, row=2, col=1)
    else:
        fig.update_yaxes(range=[0, 1], showticklabels=False, showgrid=False, row=2, col=1)

    fig.update_yaxes(range=[0, 100], fixedrange=False, zeroline=False, title_text=f"RSI({settings.rsi_period})", dtick=20, row=3, col=1)

    for row in (1, 2, 3):
        fig.update_xaxes(range=initial_range, fixedrange=False, showspikes=True, spikemode="across", spikesnap="cursor",
                          spikecolor="rgba(148,163,184,0.42)", spikethickness=1, row=row, col=1)
    fig.update_xaxes(matches="x", showticklabels=False, row=1, col=1)
    fig.update_xaxes(matches="x", showticklabels=False, row=2, col=1)
    fig.update_xaxes(matches="x", showticklabels=True, row=3, col=1)
    fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
    fig.update_xaxes(rangeslider_visible=False, row=2, col=1)
    fig.update_xaxes(rangeslider_visible=True, rangeslider_thickness=0.035, row=3, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=800,
        margin=dict(l=8, r=118, t=46, b=4),
        title={"text": f"{ticker} // RESEARCH CHART", "x": 0.0, "xanchor": "left"},
        legend={"orientation": "h", "y": 1.02, "x": 0, "font": {"size": 10}, "bgcolor": "rgba(0,0,0,0)"},
        hovermode="x unified",
        dragmode="pan",
        uirevision=f"research-{ticker}",
        bargap=0.06,
        plot_bgcolor="#05070a",
        paper_bgcolor="#05070a",
        hoverlabel={"bgcolor": "#10141a", "bordercolor": "#303846", "font": {"color": "#f5f7fa"}},
    )
    return fig
