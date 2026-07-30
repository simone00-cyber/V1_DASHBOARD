"""The Executive Research Summary: the "five second read" at the top of the
Research page.

This module computes nothing analytical — it only arranges and, in two small
places, relabels outputs the engines already produced (`TechnicalAssessment`,
`FundamentalAnalysis`, `CombinedThesis`). `investment_horizon_label` and
`recommended_action_phrase` are pure presentation-layer relabelings of
`CombinedThesis.overall_label`, in the same spirit as
`screener/opportunities.py::classify_conviction` — a lookup over an
already-computed category, not a new score or model.

Deliberately kept visually quiet (small badges/tiles, no large colored
banner) so the chart rendered immediately below it remains the page's
dominant visual element.
"""

from __future__ import annotations

import html

import streamlit as st

from analysis.combined_thesis import CombinedThesis
from fundamentals.models import FundamentalAnalysis
from technical.assessment import TechnicalAssessment
from ui.components import stat_row
from ui.navigation_actions import navigate_to_build_strategy, navigate_to_opportunities

_HORIZON_LABELS: dict[str, str] = {
    "High Conviction Buy": "Core Position / Long-Term",
    "Buy": "Long-Term / Accumulate",
    "High Conviction Sell / Avoid": "Avoid",
    "Sell / Avoid": "Avoid / Reduce",
    "Excellent Company, Poor Timing — Wait": "Long-Term Interest — Short-Term Wait",
    "Weak Company, Strong Momentum — Caution": "Short-Term / Trading Only",
    "Hold / Mixed Signals": "No Clear Horizon — Monitor",
    "Partial View — Data Insufficient": "Insufficient Data",
}

_ACTION_PHRASES: dict[str, str] = {
    "High Conviction Buy": "Consider initiating or adding to a position",
    "Buy": "Consider a starter position",
    "High Conviction Sell / Avoid": "Avoid — exit or stay away",
    "Sell / Avoid": "Reduce exposure or avoid new entries",
    "Excellent Company, Poor Timing — Wait": "Hold off — wait for Technical/Cyclical confirmation",
    "Weak Company, Strong Momentum — Caution": "Trade with caution — not a core holding",
    "Hold / Mixed Signals": "Hold — monitor for a clearer signal",
    "Partial View — Data Insufficient": "Insufficient data for a confident action",
}

_BADGE_STYLE: dict[str, str] = {
    "High Conviction Buy": "is-good",
    "Buy": "is-good",
    "High Conviction Sell / Avoid": "is-critical",
    "Sell / Avoid": "is-critical",
    "Excellent Company, Poor Timing — Wait": "is-warning",
    "Weak Company, Strong Momentum — Caution": "is-warning",
    "Hold / Mixed Signals": "is-warning",
    "Partial View — Data Insufficient": "is-neutral",
}

_LENS_CHIP_STYLE = {"BUY": "is-good", "SELL": "is-critical", "HOLD": "is-warning", "INSUFFICIENT DATA": "is-neutral"}


def investment_horizon_label(overall_label: str) -> str:
    """Relabels the already-computed `CombinedThesis.overall_label` into an
    investment-horizon phrase. Pure presentation — no new computation."""
    return _HORIZON_LABELS.get(overall_label, "No Clear Horizon — Monitor")


def recommended_action_phrase(overall_label: str) -> str:
    """Relabels the already-computed `CombinedThesis.overall_label` into a
    plain-language next step. Pure presentation — no new computation."""
    return _ACTION_PHRASES.get(overall_label, "Hold — monitor for a clearer signal")


def _conviction_style(overall_label: str) -> str:
    return _BADGE_STYLE.get(overall_label, "is-neutral")


def _summary_line(label: str, value: str) -> str:
    return (
        "<div class='summary-line'>"
        f"<span class='summary-label'>{html.escape(label)}</span>"
        f"<span class='summary-value'>{html.escape(value)}</span>"
        "</div>"
    )


def render_executive_research_summary(
    ticker: str,
    company: str,
    assessment: TechnicalAssessment,
    fundamental: FundamentalAnalysis | None,
    combined: CombinedThesis,
) -> None:
    st.markdown("<div class='terminal-subheader'>EXECUTIVE RESEARCH SUMMARY</div>", unsafe_allow_html=True)

    badge_class = _conviction_style(combined.overall_label)
    lens_chips = "".join(
        f"<span class='status-chip {_LENS_CHIP_STYLE.get(verdict, 'is-neutral')}'>{html.escape(label)}: {html.escape(verdict)}</span>"
        for label, verdict in (
            ("Fundamentals", combined.fundamental_verdict),
            ("Technical", combined.technical_verdict),
            ("Cycles", combined.cyclical_verdict),
        )
    )
    st.markdown(
        f"<div class='conviction-badge {badge_class}'>{html.escape(combined.overall_label)}</div>"
        f"<div class='lens-chip-row'>{lens_chips}</div>",
        unsafe_allow_html=True,
    )

    has_fundamentals = fundamental is not None and fundamental.sufficient and fundamental.quality is not None and fundamental.valuation is not None
    business_quality = (
        f"{fundamental.quality.business_quality}/100" if has_fundamentals and fundamental.quality.business_quality is not None else "N/A"
    )
    if has_fundamentals:
        valuation_text = f"{fundamental.valuation.valuation_band}"
        if fundamental.valuation.margin_of_safety is not None:
            valuation_text += f" ({fundamental.valuation.margin_of_safety:+.0%} MoS)"
    else:
        valuation_text = "N/A"

    stat_row(
        [
            ("Business Quality", business_quality),
            ("Valuation", valuation_text),
            ("Current Risk", assessment.risk_read.level.title()),
            ("Investment Horizon", investment_horizon_label(combined.overall_label)),
        ]
    )

    st.markdown(f"<div class='thesis-headline'>{html.escape(combined.explanation)}</div>", unsafe_allow_html=True)

    if has_fundamentals and fundamental.narrative and fundamental.narrative.opportunities:
        opportunity_text = fundamental.narrative.opportunities[0]
    else:
        opportunity_text = "No specific fundamental opportunity identified — see the Technical and Cyclical tabs for setup-level detail."

    if has_fundamentals and fundamental.narrative and fundamental.narrative.risks:
        risk_text = fundamental.narrative.risks[0]
    else:
        risk_text = assessment.risk

    lines = (
        _summary_line("Main Opportunity", opportunity_text)
        + _summary_line("Main Risk", risk_text)
        + _summary_line("Recommended Action", recommended_action_phrase(combined.overall_label))
    )
    st.markdown(lines, unsafe_allow_html=True)

    action_cols = st.columns(2)
    if action_cols[0].button("Build Strategy", key="research_build_strategy", width="stretch", type="primary"):
        navigate_to_build_strategy(
            f"Build a strategy idea around {ticker} ({company}), using its current investment thesis "
            f"({combined.overall_label}) as context."
        )
    if action_cols[1].button("Compare with Sector", key="research_compare_sector", width="stretch"):
        navigate_to_opportunities()

    if not has_fundamentals and fundamental is not None:
        st.caption(fundamental.insufficiency_reason or "Insufficient fundamental data for a reliable analysis.")

    with st.expander("Full thesis detail — supporting vs. contradicting evidence", expanded=False):
        evidence_cols = st.columns(2)
        with evidence_cols[0]:
            st.markdown("**Supporting evidence**")
            supporting = []
            if has_fundamentals and fundamental.narrative:
                supporting.extend(fundamental.narrative.strengths)
                supporting.extend(fundamental.narrative.opportunities)
            if not supporting:
                st.caption("None identified from the available data.")
            else:
                st.markdown(
                    "<ul class='evidence-list'>" + "".join(f"<li>{html.escape(item)}</li>" for item in supporting) + "</ul>",
                    unsafe_allow_html=True,
                )
        with evidence_cols[1]:
            st.markdown("**Contradicting evidence**")
            contradicting = []
            if has_fundamentals and fundamental.narrative:
                contradicting.extend(fundamental.narrative.weaknesses)
                contradicting.extend(fundamental.narrative.risks)
            if not contradicting:
                st.caption("None identified from the available data.")
            else:
                st.markdown(
                    "<ul class='evidence-list'>" + "".join(f"<li>{html.escape(item)}</li>" for item in contradicting) + "</ul>",
                    unsafe_allow_html=True,
                )
