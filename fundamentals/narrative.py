"""Deterministic narrative generation — no LLM anywhere in this module.

Every sentence is a template filled in from an already-computed number (a
metric delta, a quality-axis score and its reason, a valuation band). This
matches the construction style already used by
`technical/assessment.py::build_technical_assessment` and
`screener/opportunities.py::build_reason`/`build_risk` elsewhere in the app.
"""

from __future__ import annotations

import pandas as pd

from fundamentals import config
from fundamentals.models import (
    FinancialMetricsHistory,
    FundamentalNarrative,
    FundamentalRating,
    QualityScores,
    StatementSeries,
    ValuationEstimate,
)

_QUALITY_STRENGTH_THRESHOLD = 65
_QUALITY_WEAKNESS_THRESHOLD = 45


def _format_value(value: float, kind: str) -> str:
    if kind == "currency":
        return f"{value:,.0f}"
    if kind == "percent":
        return f"{value:.1%}"
    return f"{value:.2f}"


def _trend_sentences(annual: StatementSeries) -> tuple[list[str], list[str]]:
    improved: list[str] = []
    deteriorated: list[str] = []
    candidates = [
        ("Revenue", annual.revenue, True, "currency"),
        ("Net margin", annual.net_margin, True, "percent"),
        ("Operating margin", annual.operating_margin, True, "percent"),
        ("Return on equity", annual.roe, True, "percent"),
        ("Free cash flow", annual.free_cash_flow, True, "currency"),
        ("Net debt", annual.net_debt, False, "currency"),
        ("Debt/Equity", annual.debt_to_equity, False, "ratio"),
    ]
    for label, series, higher_is_better, kind in candidates:
        clean = series.dropna()
        if len(clean) < 2:
            continue
        previous, latest = float(clean.iloc[-2]), float(clean.iloc[-1])
        if previous == latest:
            continue
        went_up = latest > previous
        is_improvement = went_up if higher_is_better else not went_up
        pct_change = (latest - previous) / abs(previous) if previous != 0 else None
        change_text = f" ({pct_change:+.1%})" if pct_change is not None else ""
        sentence = (
            f"{label} {'increased' if went_up else 'decreased'} from "
            f"{_format_value(previous, kind)} to {_format_value(latest, kind)}{change_text}."
        )
        (improved if is_improvement else deteriorated).append(sentence)
    return improved, deteriorated


def _quality_strengths_weaknesses(quality: QualityScores) -> tuple[list[str], list[str]]:
    axes = [
        ("Business quality", quality.business_quality, quality.business_quality_reason),
        ("Financial strength", quality.financial_strength, quality.financial_strength_reason),
        ("Growth quality", quality.growth_quality, quality.growth_quality_reason),
        ("Profitability", quality.profitability, quality.profitability_reason),
        ("Capital allocation", quality.capital_allocation, quality.capital_allocation_reason),
    ]
    strengths = [
        f"{label} scores {score}/100 — {reason}"
        for label, score, reason in axes
        if score is not None and score >= _QUALITY_STRENGTH_THRESHOLD
    ]
    weaknesses = [
        f"{label} scores {score}/100 — {reason}"
        for label, score, reason in axes
        if score is not None and score < _QUALITY_WEAKNESS_THRESHOLD
    ]
    return strengths, weaknesses


def _risks(annual: StatementSeries, quality: QualityScores, valuation: ValuationEstimate) -> list[str]:
    risks: list[str] = []
    if valuation.valuation_band == "Overvalued" and valuation.margin_of_safety is not None:
        risks.append(
            f"Trades above computed fair value — margin of safety is {valuation.margin_of_safety:+.1%}."
        )
    if quality.financial_strength is not None and quality.financial_strength < _QUALITY_WEAKNESS_THRESHOLD:
        risks.append(f"Balance-sheet strength is weak ({quality.financial_strength}/100): {quality.financial_strength_reason}")

    latest_fcf = annual.free_cash_flow.dropna()
    if not latest_fcf.empty and latest_fcf.iloc[-1] < 0:
        risks.append(f"Latest annual free cash flow is negative ({latest_fcf.iloc[-1]:,.0f}).")

    latest_ic = annual.interest_coverage.dropna()
    if not latest_ic.empty and latest_ic.iloc[-1] < config.INTEREST_COVERAGE_WEAK:
        risks.append(f"Interest coverage is thin ({latest_ic.iloc[-1]:.1f}x operating income over interest expense).")

    return risks


def _opportunities(quality: QualityScores, valuation: ValuationEstimate, rating: FundamentalRating) -> list[str]:
    opportunities: list[str] = []
    if valuation.valuation_band == "Undervalued" and rating.rating_band in {"Excellent", "Good"}:
        opportunities.append(
            f"Undervalued ({valuation.margin_of_safety:+.1%} margin of safety) while rated "
            f"{rating.rating_band.lower()} on fundamentals — a potential value/quality combination."
        )
    if quality.growth_quality is not None and quality.growth_quality >= _QUALITY_STRENGTH_THRESHOLD:
        opportunities.append(f"Growth quality scores {quality.growth_quality}/100: {quality.growth_quality_reason}")
    return opportunities


def _thesis(
    ticker: str,
    rating: FundamentalRating,
    valuation: ValuationEstimate,
    strengths: list[str],
    risks: list[str],
) -> str:
    parts = [
        f"{ticker} is rated {rating.rating_band} ({rating.overall_score}/100 fundamental score) "
        f"and screens as {valuation.valuation_band.lower()}"
        + (f" with a margin of safety of {valuation.margin_of_safety:+.1%}." if valuation.margin_of_safety is not None else "."),
        f"Overall recommendation: {rating.recommendation}.",
    ]
    if strengths:
        parts.append(f"Leading strength: {strengths[0]}")
    if risks:
        parts.append(f"Main risk: {risks[0]}")
    return " ".join(parts)


def build_fundamental_narrative(
    ticker: str,
    metrics: FinancialMetricsHistory,
    quality: QualityScores,
    valuation: ValuationEstimate,
    rating: FundamentalRating,
) -> FundamentalNarrative:
    improved, deteriorated = _trend_sentences(metrics.annual)
    strengths, weaknesses = _quality_strengths_weaknesses(quality)
    risks = _risks(metrics.annual, quality, valuation)
    opportunities = _opportunities(quality, valuation, rating)
    thesis = _thesis(ticker, rating, valuation, strengths, risks)

    return FundamentalNarrative(
        improved=tuple(improved),
        deteriorated=tuple(deteriorated),
        strengths=tuple(strengths),
        weaknesses=tuple(weaknesses),
        risks=tuple(risks),
        opportunities=tuple(opportunities),
        thesis=thesis,
    )
