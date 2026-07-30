"""Combines Fundamental, Technical and Cyclical verdicts into one explained
Investment Thesis.

Extends the existing cross-check idea in
`analysis/cyclical/technical_cross_check.py` (which already compares
Technical against Cyclical) to all three engines. Every verdict feeding the
combination is itself already displayed elsewhere on the page — this module
only explains how they combine, in a small fully-enumerable table, never a
bare label.
"""

from __future__ import annotations

from dataclasses import dataclass

from analysis.security_signal import TacticalSignalState
from fundamentals.models import FundamentalAnalysis
from technical.assessment import TechnicalAssessment

INSUFFICIENT = "INSUFFICIENT DATA"


@dataclass(frozen=True)
class CombinedThesis:
    fundamental_verdict: str
    technical_verdict: str
    cyclical_verdict: str
    overall_label: str
    explanation: str


def derive_fundamental_verdict(fundamental: FundamentalAnalysis) -> str:
    if not fundamental.sufficient or fundamental.rating is None:
        return INSUFFICIENT
    return fundamental.rating.recommendation


def derive_technical_verdict(assessment: TechnicalAssessment) -> str:
    if assessment.direction.startswith("UPTREND"):
        return "BUY"
    if assessment.direction.startswith("DOWNTREND"):
        return "SELL"
    return "HOLD"


def derive_cyclical_verdict(signal_state: TacticalSignalState | None) -> str:
    if signal_state is None:
        return INSUFFICIENT
    return {"LONG": "BUY", "SHORT": "SELL", "NEUTRAL": "HOLD"}.get(signal_state.current_position, "HOLD")


def build_combined_thesis(
    fundamental_verdict: str,
    technical_verdict: str,
    cyclical_verdict: str,
) -> CombinedThesis:
    verdicts = (fundamental_verdict, technical_verdict, cyclical_verdict)
    cite = f"(Fundamentals {fundamental_verdict}, Technical {technical_verdict}, Cyclical {cyclical_verdict})"

    if INSUFFICIENT in verdicts:
        return CombinedThesis(
            *verdicts,
            overall_label="Partial View — Data Insufficient",
            explanation=(
                "One or more lenses could not be computed due to insufficient data "
                f"{cite}. Treat this as a partial read, not a full three-lens thesis."
            ),
        )

    buys = verdicts.count("BUY")
    sells = verdicts.count("SELL")

    if buys == 3:
        return CombinedThesis(
            *verdicts,
            overall_label="High Conviction Buy",
            explanation=f"Fundamentals, Technical and Cyclical analysis all read BUY {cite} — the strongest alignment the platform can show.",
        )
    if sells == 3:
        return CombinedThesis(
            *verdicts,
            overall_label="High Conviction Sell / Avoid",
            explanation=f"Fundamentals, Technical and Cyclical analysis all read SELL {cite} — the weakest alignment the platform can show.",
        )
    if fundamental_verdict == "BUY" and technical_verdict == "SELL" and cyclical_verdict == "SELL":
        return CombinedThesis(
            *verdicts,
            overall_label="Excellent Company, Poor Timing — Wait",
            explanation=(
                f"Fundamentals are rated BUY, but both Technical and Cyclical analysis currently read SELL {cite}. "
                "The business looks strong; the entry timing does not. Wait for Technical/Cyclical to turn before adding exposure."
            ),
        )
    if fundamental_verdict == "SELL" and technical_verdict == "BUY" and cyclical_verdict == "BUY":
        return CombinedThesis(
            *verdicts,
            overall_label="Weak Company, Strong Momentum — Caution",
            explanation=(
                f"Technical and Cyclical analysis currently read BUY, but the underlying fundamentals are rated SELL {cite}. "
                "This looks like a momentum/speculative setup rather than a quality investment — size and manage risk accordingly."
            ),
        )
    if buys >= 2 and sells == 0:
        return CombinedThesis(
            *verdicts,
            overall_label="Buy",
            explanation=f"A majority of the three lenses agree on BUY {cite}.",
        )
    if sells >= 2 and buys == 0:
        return CombinedThesis(
            *verdicts,
            overall_label="Sell / Avoid",
            explanation=f"A majority of the three lenses agree on SELL {cite}.",
        )
    return CombinedThesis(
        *verdicts,
        overall_label="Hold / Mixed Signals",
        explanation=f"The three lenses disagree {cite} — no clear conviction either way; monitor for alignment before acting.",
    )
