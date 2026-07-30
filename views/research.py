from __future__ import annotations

import pandas as pd
import streamlit as st

from analysis.cyclical import build_cyclical_engine
from analysis.cyclical.technical_cross_check import CrossCheckRead, build_technical_cyclical_cross_check
from analysis.security_signal import build_tactical_signal_state
from charts.research_chart import build_research_chart
from screener.engine import download_universe_ohlc
from technical.assessment import build_technical_assessment
from technical.engine import PatternReliability, TechnicalSettings, compute_fibonacci_levels, estimate_pattern_reliability, parse_ma_periods
from technical.multi_timeframe import build_multi_timeframe_alignment
from ui.plotly import render_plotly
from ui.research_panels import (
    render_cyclical_position_panel,
    render_developing_patterns_panel,
    render_hero_header,
    render_key_levels_panel,
    render_market_structure_panel,
    render_momentum_volatility_panel,
    render_multi_timeframe_panel,
    render_research_summary,
)
from views.security import load_analysis as load_cyclical_analysis


@st.cache_data(ttl=3600, show_spinner=False, max_entries=32)
def _daily_prices(ticker: str) -> pd.DataFrame:
    data = download_universe_ohlc([ticker], period="max", chunk_size=1)
    return data.get(ticker, pd.DataFrame())


def _settings_panel(key_prefix: str) -> TechnicalSettings:
    with st.expander("ADJUST TECHNICAL PARAMETERS", expanded=False):
        cols = st.columns(4)
        ma_text = cols[0].text_input("MOVING AVERAGES", value="20, 50, 200", key=f"{key_prefix}_ma")
        swing_window = cols[1].slider("SWING WINDOW", 2, 10, 5, key=f"{key_prefix}_swing")
        rsi_period = cols[2].slider("RSI PERIOD", 5, 30, 14, key=f"{key_prefix}_rsi")
        pattern_tolerance = cols[3].slider("PATTERN TOLERANCE %", 1.0, 8.0, 3.0, step=0.5, key=f"{key_prefix}_tol")
    return TechnicalSettings(
        swing_window=swing_window,
        rsi_period=rsi_period,
        ma_periods=parse_ma_periods(ma_text) or (20, 50, 200),
        pattern_tolerance_pct=pattern_tolerance,
    )


def _developing_or_leading_patterns(snapshot_diagnostics: dict, limit: int = 3) -> list[dict]:
    details = snapshot_diagnostics.get("pattern_details", [])
    developing = [p for p in details if p["status"] == "DEVELOPING"]
    return (developing or details)[:limit]


def render_research(*, ticker_override: str | None = None, embedded: bool = False) -> None:
    if not embedded:
        st.markdown("<div class='terminal-header'>RESEARCH WORKSPACE // CHART-CENTRIC MARKET STRUCTURE</div>", unsafe_allow_html=True)
        st.caption("The chart is the primary read — structure, levels, the featured pattern, invalidation and cyclical turning points are all drawn on it. Everything below explains what's already visible above.")

    if ticker_override:
        ticker = ticker_override.strip().upper()
        st.info(f"Workspace ticker: {ticker}")
    else:
        ticker = st.text_input("Yahoo Finance ticker", value="AAPL", key="research_direct_ticker").strip().upper()

    if not ticker:
        st.info("Enter a ticker to begin.")
        return

    settings = _settings_panel("research")

    try:
        with st.spinner(f"Analysing {ticker}..."):
            daily_frame = _daily_prices(ticker)
    except Exception as exc:
        st.error(f"Unable to download price history for {ticker}: {exc}")
        return
    if daily_frame.empty or len(daily_frame.dropna(subset=["Close"])) < 60:
        st.error(f"Not enough price history for {ticker} to build a research view.")
        return

    try:
        assessment = build_technical_assessment(ticker, daily_frame, settings)
    except ValueError as exc:
        st.error(str(exc))
        return

    alignment = build_multi_timeframe_alignment(daily_frame, settings)
    patterns = _developing_or_leading_patterns(assessment.snapshot.diagnostics)
    reliabilities: dict[str, PatternReliability] = {}
    for pattern in patterns:
        try:
            reliabilities[pattern["name"]] = estimate_pattern_reliability(daily_frame, settings, pattern["name"], pattern["direction"])
        except Exception:
            continue

    try:
        fib_levels = compute_fibonacci_levels(daily_frame, settings)
    except Exception:
        fib_levels = None

    signal_state = None
    hierarchy = None
    cycle_states = None
    cross_check: CrossCheckRead | None = None
    try:
        _, _, cyclical_frames, cyclical_summaries, _ = load_cyclical_analysis(ticker, "max")
        signal_state = build_tactical_signal_state(cyclical_frames, cyclical_summaries)
        cycle_states, hierarchy = build_cyclical_engine(cyclical_frames)
        cross_check = build_technical_cyclical_cross_check(assessment, hierarchy)
    except Exception:
        pass

    company = ticker
    turning_points = signal_state.history if signal_state is not None else None

    # --- Above the fold: hero header, the chart, the executive summary ---
    render_hero_header(ticker, assessment, daily_frame, signal_state)

    chart = build_research_chart(ticker, daily_frame, settings, assessment, patterns, fib_levels, turning_points)
    render_plotly(chart, page="research", chart="primary", ticker=ticker, timeframe=settings.timeframe)

    render_research_summary(ticker, company, assessment, patterns, cross_check)

    # --- Below the fold: the panels that explain what's on the chart ---
    render_market_structure_panel(assessment)
    render_key_levels_panel(assessment)
    render_developing_patterns_panel(patterns, reliabilities)
    render_momentum_volatility_panel(assessment)
    render_multi_timeframe_panel(alignment)

    if signal_state is not None and hierarchy is not None:
        render_cyclical_position_panel(signal_state, hierarchy, cross_check, cycle_states)
    else:
        st.markdown("<div class='terminal-subheader'>CYCLICAL POSITION</div>", unsafe_allow_html=True)
        st.info("Cyclical position unavailable — insufficient history to build the quarterly/monthly/weekly Composite Momentum hierarchy for this ticker.")

    # --- Progressive disclosure ---
    with st.expander("FULL PATTERN LIST", expanded=False):
        details = assessment.snapshot.diagnostics.get("pattern_details", [])
        if not details:
            st.caption("No patterns currently meet the precision threshold.")
        else:
            table = pd.DataFrame(
                [
                    {
                        "Pattern": d["name"],
                        "Category": d["category"],
                        "Direction": d["direction"],
                        "Status": d["status"],
                        "Confidence": d["confidence"],
                        "Completion %": d.get("completion_pct"),
                        "Trigger": d.get("trigger"),
                        "Invalidation": d.get("invalidation"),
                    }
                    for d in details
                ]
            )
            st.dataframe(table, width="stretch", hide_index=True)

    with st.expander("SUPPORT / RESISTANCE DIAGNOSTICS", expanded=False):
        for label, zones in (("SUPPORTS", assessment.snapshot.diagnostics.get("supports", [])), ("RESISTANCES", assessment.snapshot.diagnostics.get("resistances", []))):
            st.markdown(f"**{label}**")
            if not zones:
                st.caption("None detected.")
                continue
            st.dataframe(pd.DataFrame(zones)[["center", "low", "high", "role", "state", "strength", "touches"]], width="stretch", hide_index=True)

    if fib_levels is not None:
        with st.expander("FIBONACCI RETRACEMENT DETAIL", expanded=False):
            st.caption(f"{fib_levels.direction.title()} from {fib_levels.swing_start[1]:,.2f} to {fib_levels.swing_end[1]:,.2f}.")
            st.dataframe(
                pd.DataFrame([{"Level": label, "Price": price} for label, price in fib_levels.levels.items()]),
                width="stretch",
                hide_index=True,
            )

    if signal_state is not None:
        with st.expander("CYCLICAL SIGNAL HISTORY", expanded=False):
            if not signal_state.history:
                st.caption("No documented matrix events in the available history.")
            else:
                history_rows = [
                    {
                        "DATE": event.date.strftime("%d/%m/%Y"),
                        "EVENT": event.action,
                        "RATING": "●" * event.rating,
                        "QUARTERLY": event.quarterly_direction,
                        "MONTHLY": event.monthly_direction,
                        "WEEKLY": event.weekly_turn,
                        "WEEKLY CM": round(event.weekly_composite, 2),
                    }
                    for event in reversed(signal_state.history[-12:])
                ]
                st.dataframe(pd.DataFrame(history_rows), width="stretch", hide_index=True)

    with st.expander("METHODOLOGY &amp; PROVENANCE", expanded=False):
        st.write(
            "The chart is the primary analytical surface: candlesticks, volume, MA20/50/200, swing highs/lows, "
            "support/resistance zones (major vs. minor by strength), the featured pattern's boundaries/breakout "
            "zone/trigger, Fibonacci retracement levels for the most recent swing leg, the current invalidation "
            "level and — when available — the documented cyclical BUY/SELL SHORT/TAKE PROFIT turning points are "
            "all drawn directly on it (technical/engine.py, charts/research_chart.py). The panels below only "
            "explain what is already visible above."
        )
        st.write(
            "Pattern categories (triangles, flags, wedges, rectangles, double/triple top/bottom, head & shoulders, "
            "rounded formations, channels) and concepts (support/resistance, breakout/breakdown, divergence, RSI "
            "overbought/oversold, Fibonacci retracement) match the published Caruso technical glossary; the "
            "precision heuristics themselves (trendline fit quality, volume bias, completion %, per-ticker "
            "reliability replay) are this software's own, not part of that methodology."
        )
        st.write(
            "Cyclical Position reuses the documented Composite Momentum matrix and hierarchy unchanged "
            "(caruso_analysis.py, analysis/cyclical/*) — verified against the original ProRealTime and MetaStock "
            "source formulas. The documented cycle-length ranges shown next to each timeframe's phase are a direct "
            "citation from 'La Metodologia Ciclica', shown as historical context only. The Technical × Cyclical "
            "cross-check only compares the two engines' outputs; it does not feed back into or alter either one."
        )
