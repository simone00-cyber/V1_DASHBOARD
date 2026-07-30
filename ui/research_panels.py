from __future__ import annotations

import html
from typing import Any

import pandas as pd
import streamlit as st

from analysis.cyclical.cycle_timing import DOCUMENTED_CYCLE_BARS, dominant_cyclical_timeframe
from analysis.cyclical.models import CycleState, HierarchyAssessment
from analysis.cyclical.technical_cross_check import CrossCheckRead
from analysis.security_signal import TacticalSignalState
from config.theme import GREEN, MUTED, ORANGE, RED
from technical.assessment import TechnicalAssessment
from technical.engine import PatternReliability
from technical.market_structure import StructureRatings, build_structure_ratings
from technical.multi_timeframe import MultiTimeframeAlignment
from ui.components import confidence_color, direction_color, stars, stat_row
from ui.navigation_actions import navigate_to_build_strategy, navigate_to_opportunities


def render_confidence_bar(confidence: int, components: dict[str, int] | None = None) -> None:
    color = confidence_color(confidence)
    st.markdown(
        "<div class='confidence-row'>"
        f"<div class='confidence-track'><div class='confidence-fill' style='width:{confidence}%;background:{color}'></div></div>"
        f"<div class='confidence-label'>{confidence}/100</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    if components:
        parts = " · ".join(f"{name.replace('_', ' ').title()}: {value}" for name, value in components.items())
        st.markdown(f"<div class='small-note'>{html.escape(parts)}</div>", unsafe_allow_html=True)


# --- Above the fold: hero header (chart and the Executive Research Summary are
# rendered by views/research.py and ui/executive_summary.py respectively) ---


def render_hero_header(ticker: str, assessment: TechnicalAssessment, daily_frame: pd.DataFrame, signal_state: TacticalSignalState | None) -> None:
    """Ticker / Price (with the daily change as its delta) / Trend / Risk / Regime —
    a single glanceable row, the first thing on the page."""
    close = daily_frame["Close"].dropna()
    change_pct = (float(close.iloc[-1]) / float(close.iloc[-2]) - 1.0) * 100.0 if len(close) >= 2 else None

    regime = assessment.direction.split(" (")[0].title()
    if signal_state is not None:
        regime = f"{regime} · Cyclical {signal_state.current_position.title()}"

    cols = st.columns(5)
    cols[0].metric("TICKER", ticker)
    cols[1].metric("PRICE", f"{assessment.snapshot.last:,.2f}", f"{change_pct:+.2f}%" if change_pct is not None else None)
    cols[2].metric("TREND", assessment.trend_quality.label)
    cols[3].metric("RISK", assessment.risk_read.level)
    cols[4].metric("REGIME", regime)


def _navigate_to_build_strategy(ticker: str, company: str, assessment: TechnicalAssessment) -> None:
    navigate_to_build_strategy(
        f"Build a strategy idea around {ticker} ({company}), using its current technical structure "
        f"({assessment.trend_quality.label.lower()}-quality {assessment.current_assessment.split(' is ')[-1]}) as context."
    )


def _navigate_to_compare_sector() -> None:
    navigate_to_opportunities()


# --- Technical tab panels: the detail behind the chart and the top summary ---


def render_market_structure_panel(assessment: TechnicalAssessment) -> None:
    st.markdown("<div class='terminal-subheader'>MARKET STRUCTURE &amp; TREND QUALITY</div>", unsafe_allow_html=True)

    ratings: StructureRatings = build_structure_ratings(assessment.trend_quality, assessment.risk_read, assessment.snapshot)
    for label, score in (
        ("Trend", ratings.trend),
        ("Momentum", ratings.momentum),
        ("Structure", ratings.structure),
        ("Volatility", ratings.volatility),
        ("Risk", 100 - ratings.risk),
    ):
        st.markdown(
            f"<div class='star-row'><span class='star-label'>{label}</span>"
            f"<span class='stars'>{stars(score)}</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown(f"<div class='insight-banner'>{html.escape(assessment.current_assessment)}</div>", unsafe_allow_html=True)
    stat_row(
        [
            ("Trend Quality", f"{assessment.trend_quality.label} ({assessment.trend_quality.score}/100)"),
            ("Swing Structure", assessment.trend_quality.swing_structure.sequence.title()),
            ("MA Alignment", assessment.trend_quality.ma_alignment.title()),
            ("Risk Level", assessment.risk_read.level),
        ]
    )

    with st.expander("Supporting evidence, risk & confidence detail", expanded=False):
        st.markdown(
            "<ul class='evidence-list'>" + "".join(f"<li>{html.escape(item)}</li>" for item in assessment.supporting_evidence) + "</ul>",
            unsafe_allow_html=True,
        )
        st.markdown(f"<div class='risk-callout'><b>Risk:</b> {html.escape(assessment.risk)}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='invalidation-callout'><b>Invalidation:</b> {html.escape(assessment.invalidation)}</div>", unsafe_allow_html=True)
        st.markdown("<b>Confidence</b>", unsafe_allow_html=True)
        render_confidence_bar(assessment.confidence, assessment.confidence_components)


def render_key_levels_panel(assessment: TechnicalAssessment) -> None:
    st.markdown("<div class='terminal-subheader'>KEY LEVELS</div>", unsafe_allow_html=True)
    snapshot = assessment.snapshot
    support_text = f"{snapshot.support_low:,.2f} – {snapshot.support_high:,.2f}" if snapshot.support_low else "N/A"
    support_distance = f"{snapshot.distance_support_pct:+.2f}%" if snapshot.distance_support_pct is not None else "N/A"
    resistance_text = f"{snapshot.resistance_low:,.2f} – {snapshot.resistance_high:,.2f}" if snapshot.resistance_low else "N/A"
    resistance_distance = f"{snapshot.distance_resistance_pct:+.2f}%" if snapshot.distance_resistance_pct is not None else "N/A"
    stat_row(
        [
            ("Nearest Support", support_text),
            ("Distance to Support", support_distance),
            ("Nearest Resistance", resistance_text),
            ("Distance to Resistance", resistance_distance),
        ]
    )
    st.caption(f"Current state: {snapshot.state} — major/minor levels and their distance from price are drawn directly on the chart above.")


_STATUS_COLOR = {"DEVELOPING": ORANGE, "CONFIRMED": GREEN, "RETESTED": MUTED}


def render_developing_patterns_panel(
    patterns: list[dict[str, Any]],
    reliabilities: dict[str, PatternReliability],
) -> None:
    st.markdown("<div class='terminal-subheader'>DEVELOPING PATTERNS</div>", unsafe_allow_html=True)
    if not patterns:
        st.info("No pattern currently meets the precision threshold — this is treated as a feature, not a gap: no low-quality candidates are shown.")
        return
    st.caption("The highlighted setup (first below) is the one drawn on the chart above — boundary lines, breakout zone and trigger.")

    for pattern in patterns:
        color = _STATUS_COLOR.get(pattern["status"], MUTED)
        completion = pattern.get("completion_pct")
        completion_text = f"{completion:.0f}% toward trigger" if completion is not None else "directionally undefined"
        zone = pattern.get("expected_breakout_zone")
        zone_text = f"{zone[0]:,.2f} – {zone[1]:,.2f}" if zone else "N/A"
        invalidation = pattern.get("invalidation")
        invalidation_text = f"{invalidation:,.2f}" if invalidation is not None else "N/A"
        reliability = reliabilities.get(pattern["name"])

        with st.container(border=True):
            st.markdown(
                f"<div class='pattern-card-title'>{html.escape(pattern['name'])}"
                f"<span style='color:{color}'>{html.escape(pattern['status'])}</span></div>"
                f"<div class='pattern-card-meta'>{html.escape(pattern['category'])} · {html.escape(pattern['direction'])} · {completion_text}</div>",
                unsafe_allow_html=True,
            )
            stat_row(
                [
                    ("Confidence", f"{pattern['confidence']}/100"),
                    ("Expected Breakout Zone", zone_text),
                    ("Invalidation Level", invalidation_text),
                ]
            )
            st.caption(pattern.get("notes") or "No additional notes.")
            if reliability is None:
                pass
            elif reliability.favorable_rate is None:
                st.caption(f"Historical reliability: {reliability.note} (sample size {reliability.sample_size}).")
            else:
                st.caption(
                    f"Historical reliability on this ticker: {reliability.favorable_rate:.0%} of {reliability.sample_size} prior occurrences "
                    f"moved favorably over the next {reliability.horizon_bars} bars (median return {reliability.median_forward_return_pct:+.1f}%)."
                )


def render_momentum_volatility_panel(assessment: TechnicalAssessment) -> None:
    st.markdown("<div class='terminal-subheader'>MOMENTUM &amp; VOLATILITY</div>", unsafe_allow_html=True)
    snapshot = assessment.snapshot
    risk = assessment.risk_read
    volume_setups = [s for s in snapshot.setups if "volume" in s.lower()]
    stat_row(
        [
            ("RSI", f"{snapshot.rsi:.1f}" if snapshot.rsi is not None else "N/A"),
            ("Volatility Regime", risk.volatility_regime),
            ("ATR % of Price", f"{risk.atr_pct:.2f}%" if pd.notna(risk.atr_pct) else "N/A"),
            ("Volume Confirmation", volume_setups[0] if volume_setups else "No confirmation signal"),
        ]
    )
    divergence_setups = [s for s in snapshot.setups if "divergence" in s.lower()]
    if divergence_setups:
        st.caption(" · ".join(divergence_setups))


def render_multi_timeframe_panel(alignment: MultiTimeframeAlignment) -> None:
    st.markdown("<div class='terminal-subheader'>MULTI-TIMEFRAME ALIGNMENT</div>", unsafe_allow_html=True)
    if not alignment.reads:
        st.info(alignment.summary)
        return
    st.markdown(f"<div class='insight-banner'>{html.escape(alignment.summary)}</div>", unsafe_allow_html=True)
    for read in alignment.reads:
        color = direction_color(read.direction)
        dominant_tag = " (DOMINANT)" if read.timeframe == alignment.dominant_timeframe else ""
        st.markdown(
            "<div class='dot-row'>"
            f"<span class='status-dot' style='background:{color}'></span>"
            f"<span class='dot-timeframe'>{html.escape(read.timeframe.title())}{dominant_tag}</span>"
            f"<span class='dot-detail'>{html.escape(read.direction.split(' (')[0].title())} · quality {read.trend_quality.score}/100</span>"
            "</div>",
            unsafe_allow_html=True,
        )


_PHASE_COLOR = {"UP": GREEN, "ADVANCING": GREEN, "DOWN": RED, "TERMINATING": RED, "NEUTRAL": MUTED}


def render_cyclical_position_panel(
    signal_state: TacticalSignalState,
    hierarchy: HierarchyAssessment,
    cross_check: CrossCheckRead | None,
    cycle_states: dict[str, CycleState] | None = None,
) -> None:
    st.markdown("<div class='terminal-subheader'>CYCLICAL POSITION</div>", unsafe_allow_html=True)
    signal_color = GREEN if signal_state.current_position == "LONG" else RED if signal_state.current_position == "SHORT" else ORANGE
    st.markdown(
        f"<div class='signal-box' style='border-left-color:{signal_color}'>"
        f"<b style='color:{signal_color};font-size:1.1rem'>{html.escape(signal_state.position_label)}</b><br>"
        f"Status: <b>{html.escape(signal_state.status)}</b> · Alignment: <b>{html.escape(hierarchy.alignment)}</b><br>"
        f"<span class='small-note'>{html.escape(signal_state.weekly_phase)}</span></div>",
        unsafe_allow_html=True,
    )

    if cycle_states:
        dominant = dominant_cyclical_timeframe(cycle_states)
        for timeframe in ("QUARTERLY", "MONTHLY", "WEEKLY"):
            state = cycle_states.get(timeframe)
            if state is None:
                continue
            color = _PHASE_COLOR.get(state.phase, MUTED)
            dominant_tag = " (DOMINANT)" if timeframe == dominant else ""
            duration_note = ""
            documented = DOCUMENTED_CYCLE_BARS.get(timeframe)
            if documented:
                duration_note = f" · documented cycle length {documented[0]}-{documented[1]} bars trough-to-trough"
            st.markdown(
                "<div class='dot-row'>"
                f"<span class='status-dot' style='background:{color}'></span>"
                f"<span class='dot-timeframe'>{timeframe.title()}{dominant_tag}</span>"
                f"<span class='dot-detail'>{html.escape(state.phase)} · {state.state_age} bars in phase{duration_note}</span>"
                "</div>",
                unsafe_allow_html=True,
            )

    cols = st.columns(2)
    cols[0].markdown(f"<div class='risk-callout'><b>Next trigger:</b> {html.escape(signal_state.next_trigger)}</div>", unsafe_allow_html=True)
    cols[1].markdown(f"<div class='invalidation-callout'><b>Invalidation:</b> {html.escape(signal_state.invalidation_condition)}</div>", unsafe_allow_html=True)

    if cross_check is not None:
        chip_class = {"CONFIRMS": "is-good", "DIVERGES": "is-critical"}.get(cross_check.agreement, "is-neutral")
        st.markdown(
            f"<div class='status-chip {chip_class}'>TECHNICAL × CYCLICAL: {html.escape(cross_check.agreement)}</div>"
            f"<div class='small-note' style='margin-top:.4rem'>{html.escape(cross_check.summary)}</div>",
            unsafe_allow_html=True,
        )
