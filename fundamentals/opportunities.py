"""Fundamental Opportunities ranking.

Every ranking below is a transparent sort on one already-computed,
already-displayed field of `FundamentalOpportunityRow` — the same "no new
synthetic score" convention as `screener/opportunities.py`. Rows whose
underlying analysis was insufficient are excluded entirely (never ranked
with a guessed value), and rows missing the specific field a ranking sorts
on are excluded from that ranking only.
"""

from __future__ import annotations

from dataclasses import dataclass

from fundamentals.models import FundamentalAnalysis
from fundamentals.scan import FundamentalScanResult

RANKING_LABELS: tuple[str, ...] = (
    "Most Undervalued",
    "Highest Margin of Safety",
    "Highest Business Quality",
    "Strongest Financial Health",
    "Fastest Improving Fundamentals",
    "Best Capital Allocation",
    "Highest Composite Rating",
)


@dataclass(frozen=True)
class FundamentalOpportunityRow:
    ticker: str
    rating_band: str
    recommendation: str
    overall_score: int | None
    fair_value: float | None
    current_price: float | None
    margin_of_safety: float | None
    upside_pct: float | None
    valuation_band: str
    business_quality: int | None
    financial_strength: int | None
    growth_quality: int | None
    profitability: int | None
    capital_allocation: int | None
    net_improvement: int
    thesis: str
    main_risk: str


def _to_row(analysis: FundamentalAnalysis) -> FundamentalOpportunityRow | None:
    if not analysis.sufficient or analysis.quality is None or analysis.valuation is None or analysis.rating is None or analysis.narrative is None:
        return None
    narrative = analysis.narrative
    return FundamentalOpportunityRow(
        ticker=analysis.ticker,
        rating_band=analysis.rating.rating_band,
        recommendation=analysis.rating.recommendation,
        overall_score=analysis.rating.overall_score,
        fair_value=analysis.valuation.composite_fair_value,
        current_price=analysis.valuation.current_price,
        margin_of_safety=analysis.valuation.margin_of_safety,
        upside_pct=analysis.valuation.upside_pct,
        valuation_band=analysis.valuation.valuation_band,
        business_quality=analysis.quality.business_quality,
        financial_strength=analysis.quality.financial_strength,
        growth_quality=analysis.quality.growth_quality,
        profitability=analysis.quality.profitability,
        capital_allocation=analysis.quality.capital_allocation,
        net_improvement=len(narrative.improved) - len(narrative.deteriorated),
        thesis=narrative.thesis,
        main_risk=narrative.risks[0] if narrative.risks else "No specific risk identified from the available data.",
    )


def build_opportunity_rows(scan: FundamentalScanResult) -> list[FundamentalOpportunityRow]:
    return [row for row in (_to_row(analysis) for analysis in scan.rows) if row is not None]


def _sorted_by(rows: list[FundamentalOpportunityRow], attr: str, limit: int, *, reverse: bool = True) -> list[FundamentalOpportunityRow]:
    available = [row for row in rows if getattr(row, attr) is not None]
    ordered = sorted(available, key=lambda row: getattr(row, attr), reverse=reverse)
    return ordered[:limit]


def select_most_undervalued(rows: list[FundamentalOpportunityRow], limit: int = 10) -> list[FundamentalOpportunityRow]:
    undervalued = [row for row in rows if row.valuation_band == "Undervalued"]
    return _sorted_by(undervalued, "margin_of_safety", limit)


def select_highest_margin_of_safety(rows: list[FundamentalOpportunityRow], limit: int = 10) -> list[FundamentalOpportunityRow]:
    return _sorted_by(rows, "margin_of_safety", limit)


def select_highest_business_quality(rows: list[FundamentalOpportunityRow], limit: int = 10) -> list[FundamentalOpportunityRow]:
    return _sorted_by(rows, "business_quality", limit)


def select_strongest_financial_health(rows: list[FundamentalOpportunityRow], limit: int = 10) -> list[FundamentalOpportunityRow]:
    return _sorted_by(rows, "financial_strength", limit)


def select_fastest_improving_fundamentals(rows: list[FundamentalOpportunityRow], limit: int = 10) -> list[FundamentalOpportunityRow]:
    return _sorted_by(rows, "net_improvement", limit)


def select_best_capital_allocation(rows: list[FundamentalOpportunityRow], limit: int = 10) -> list[FundamentalOpportunityRow]:
    return _sorted_by(rows, "capital_allocation", limit)


def select_highest_composite_rating(rows: list[FundamentalOpportunityRow], limit: int = 10) -> list[FundamentalOpportunityRow]:
    return _sorted_by(rows, "overall_score", limit)


RANKING_FUNCTIONS = {
    "Most Undervalued": select_most_undervalued,
    "Highest Margin of Safety": select_highest_margin_of_safety,
    "Highest Business Quality": select_highest_business_quality,
    "Strongest Financial Health": select_strongest_financial_health,
    "Fastest Improving Fundamentals": select_fastest_improving_fundamentals,
    "Best Capital Allocation": select_best_capital_allocation,
    "Highest Composite Rating": select_highest_composite_rating,
}
