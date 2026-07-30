from __future__ import annotations

import pandas as pd

from data.providers.fundamentals.models import RawFundamentalsBundle
from fundamentals.engine import build_fundamental_analysis
from fundamentals.metrics import compute_metrics_history
from fundamentals.narrative import build_fundamental_narrative
from fundamentals.quality import build_quality_scores
from fundamentals.rating import build_fundamental_rating, classify_valuation_band
from fundamentals.valuation import build_valuation_estimate
import dataclasses


def _bundle() -> RawFundamentalsBundle:
    dates = [pd.Timestamp("2022-12-31"), pd.Timestamp("2023-12-31")]
    income = pd.DataFrame(
        {
            dates[0]: [100.0, 40.0, 20.0, 15.0, 2.0, 5.0],
            dates[1]: [120.0, 50.0, 28.0, 21.0, 2.5, 7.0],
        },
        index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income", "Interest Expense", "Diluted EPS"],
    )
    balance = pd.DataFrame(
        {
            # Debt rises and cash falls between periods -> net debt and
            # debt/equity both worsen, giving the narrative something to
            # flag under "what deteriorated".
            dates[0]: [500.0, 200.0, 300.0, 150.0, 60.0, 50.0, 40.0],
            dates[1]: [560.0, 230.0, 300.0, 160.0, 65.0, 30.0, 60.0],
        },
        index=[
            "Total Assets",
            "Total Liabilities Net Minority Interest",
            "Stockholders Equity",
            "Current Assets",
            "Current Liabilities",
            "Cash And Cash Equivalents",
            "Total Debt",
        ],
    )
    cashflow = pd.DataFrame(
        {dates[0]: [18.0, -5.0], dates[1]: [25.0, -6.0]},
        index=["Operating Cash Flow", "Capital Expenditure"],
    )
    return RawFundamentalsBundle(
        ticker="NARR",
        fetched_at=pd.Timestamp.utcnow(),
        info={"currentPrice": 40.0, "sharesOutstanding": 10.0},
        income_stmt=income,
        balance_sheet=balance,
        cashflow=cashflow,
    )


def _build_pipeline(bundle):
    metrics = compute_metrics_history(bundle)
    quality = build_quality_scores(metrics)
    valuation = build_valuation_estimate(metrics)
    valuation = dataclasses.replace(valuation, valuation_band=classify_valuation_band(valuation.margin_of_safety))
    rating = build_fundamental_rating(quality, valuation)
    narrative = build_fundamental_narrative("NARR", metrics, quality, valuation, rating)
    return metrics, quality, valuation, rating, narrative


def test_narrative_flags_revenue_and_fcf_as_improved():
    _, _, _, _, narrative = _build_pipeline(_bundle())
    assert any("Revenue" in sentence for sentence in narrative.improved)
    assert any("Free cash flow" in sentence for sentence in narrative.improved)


def test_narrative_flags_leverage_as_deteriorated():
    _, _, _, _, narrative = _build_pipeline(_bundle())
    assert any("Net debt" in sentence for sentence in narrative.deteriorated)
    assert any("Debt/Equity" in sentence for sentence in narrative.deteriorated)


def test_narrative_thesis_cites_rating_band_and_recommendation():
    _, _, _, rating, narrative = _build_pipeline(_bundle())
    assert rating.rating_band in narrative.thesis
    assert rating.recommendation in narrative.thesis


def test_narrative_strengths_cite_axis_scores_above_threshold():
    _, quality, _, _, narrative = _build_pipeline(_bundle())
    for strength in narrative.strengths:
        assert "/100" in strength


def test_engine_facade_produces_sufficient_analysis_end_to_end():
    class _FakeProvider:
        def fetch(self, ticker):
            return _bundle()

    analysis = build_fundamental_analysis("NARR", _FakeProvider())
    assert analysis.sufficient
    assert analysis.narrative is not None
    assert analysis.rating is not None
    assert analysis.rating.recommendation in {"BUY", "HOLD", "SELL", "INSUFFICIENT DATA"}
