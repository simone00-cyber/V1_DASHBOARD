from __future__ import annotations

import pandas as pd

from fundamentals.models import (
    FundamentalAnalysis,
    FundamentalNarrative,
    FundamentalRating,
    QualityScores,
    ValuationEstimate,
)
from fundamentals.opportunities import (
    FundamentalOpportunityRow,
    build_opportunity_rows,
    select_best_capital_allocation,
    select_fastest_improving_fundamentals,
    select_highest_business_quality,
    select_highest_composite_rating,
    select_highest_margin_of_safety,
    select_most_undervalued,
    select_strongest_financial_health,
)
from fundamentals.scan import FundamentalScanResult


def _row(ticker: str, **overrides) -> FundamentalOpportunityRow:
    base = dict(
        ticker=ticker,
        rating_band="Good",
        recommendation="BUY",
        overall_score=50,
        fair_value=120.0,
        current_price=100.0,
        margin_of_safety=0.1,
        upside_pct=0.2,
        valuation_band="Fairly Valued",
        business_quality=50,
        financial_strength=50,
        growth_quality=50,
        profitability=50,
        capital_allocation=50,
        net_improvement=0,
        thesis="t",
        main_risk="r",
    )
    base.update(overrides)
    return FundamentalOpportunityRow(**base)


def test_select_most_undervalued_filters_band_and_sorts_by_margin_of_safety():
    rows = [
        _row("AAA", valuation_band="Undervalued", margin_of_safety=0.4),
        _row("BBB", valuation_band="Undervalued", margin_of_safety=0.2),
        _row("CCC", valuation_band="Fairly Valued", margin_of_safety=0.5),
    ]
    assert [r.ticker for r in select_most_undervalued(rows)] == ["AAA", "BBB"]


def test_select_highest_margin_of_safety_ignores_valuation_band():
    rows = [
        _row("AAA", margin_of_safety=0.1),
        _row("BBB", margin_of_safety=0.5),
        _row("CCC", margin_of_safety=None),
    ]
    assert [r.ticker for r in select_highest_margin_of_safety(rows)] == ["BBB", "AAA"]


def test_select_highest_business_quality():
    rows = [_row("AAA", business_quality=60), _row("BBB", business_quality=90)]
    assert [r.ticker for r in select_highest_business_quality(rows)] == ["BBB", "AAA"]


def test_select_strongest_financial_health():
    rows = [_row("AAA", financial_strength=40), _row("BBB", financial_strength=95)]
    assert [r.ticker for r in select_strongest_financial_health(rows)] == ["BBB", "AAA"]


def test_select_fastest_improving_fundamentals():
    rows = [_row("AAA", net_improvement=1), _row("BBB", net_improvement=5)]
    assert [r.ticker for r in select_fastest_improving_fundamentals(rows)] == ["BBB", "AAA"]


def test_select_best_capital_allocation():
    rows = [_row("AAA", capital_allocation=30), _row("BBB", capital_allocation=88)]
    assert [r.ticker for r in select_best_capital_allocation(rows)] == ["BBB", "AAA"]


def test_select_highest_composite_rating():
    rows = [_row("AAA", overall_score=55), _row("BBB", overall_score=95)]
    assert [r.ticker for r in select_highest_composite_rating(rows)] == ["BBB", "AAA"]


def _sufficient_analysis(ticker: str) -> FundamentalAnalysis:
    quality = QualityScores(
        business_quality=80, business_quality_reason="r",
        financial_strength=80, financial_strength_reason="r",
        growth_quality=80, growth_quality_reason="r",
        profitability=80, profitability_reason="r",
        capital_allocation=80, capital_allocation_reason="r",
    )
    valuation = ValuationEstimate(
        current_price=100.0, methods=(), bear_fair_value=None, base_fair_value=130.0,
        bull_fair_value=None, composite_fair_value=130.0, margin_of_safety=0.23,
        upside_pct=0.3, valuation_band="Undervalued",
    )
    rating = FundamentalRating(overall_score=80, rating_band="Excellent", recommendation="BUY")
    narrative = FundamentalNarrative(
        improved=("Revenue increased",), deteriorated=(), strengths=(), weaknesses=(),
        risks=("Some risk",), opportunities=(), thesis="Great company.",
    )
    return FundamentalAnalysis(
        ticker=ticker, sufficient=True, insufficiency_reason=None,
        metrics=None, quality=quality, valuation=valuation, rating=rating, narrative=narrative, raw=None,
    )


def _insufficient_analysis(ticker: str) -> FundamentalAnalysis:
    return FundamentalAnalysis(
        ticker=ticker, sufficient=False, insufficiency_reason="not enough data",
        metrics=None, quality=None, valuation=None, rating=None, narrative=None, raw=None,
    )


def test_build_opportunity_rows_excludes_insufficient_analyses():
    scan = FundamentalScanResult(
        rows=(_sufficient_analysis("AAA"), _insufficient_analysis("BBB")),
        failures=(), last_updated=pd.Timestamp.utcnow(), coverage=1, universe_size=2,
    )
    rows = build_opportunity_rows(scan)
    assert [row.ticker for row in rows] == ["AAA"]
    assert rows[0].rating_band == "Excellent"
    assert rows[0].main_risk == "Some risk"
