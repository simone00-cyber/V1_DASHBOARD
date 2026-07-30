from __future__ import annotations

import pandas as pd

from data.providers.fundamentals.models import RawFundamentalsBundle
from fundamentals.metrics import compute_metrics_history
from fundamentals.quality import build_quality_scores


def _bundle() -> RawFundamentalsBundle:
    dates = [pd.Timestamp("2022-12-31"), pd.Timestamp("2023-12-31"), pd.Timestamp("2024-12-31")]
    income = pd.DataFrame(
        {
            dates[0]: [100.0, 50.0, 20.0, 15.0, 1.0, 3.0],
            dates[1]: [115.0, 58.0, 24.0, 18.0, 1.0, 3.6],
            dates[2]: [130.0, 66.0, 28.0, 21.0, 1.0, 4.2],
        },
        index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income", "Interest Expense", "Diluted EPS"],
    )
    balance = pd.DataFrame(
        {
            dates[0]: [400.0, 100.0, 300.0, 200.0, 80.0, 60.0, 40.0],
            dates[1]: [430.0, 105.0, 325.0, 215.0, 85.0, 65.0, 35.0],
            dates[2]: [460.0, 108.0, 352.0, 230.0, 90.0, 70.0, 30.0],
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
    return RawFundamentalsBundle(
        ticker="QUAL",
        fetched_at=pd.Timestamp.utcnow(),
        info={"currentPrice": 40.0},
        income_stmt=income,
        balance_sheet=balance,
    )


def test_build_quality_scores_produces_all_five_axes_with_reasons():
    metrics = compute_metrics_history(_bundle())
    quality = build_quality_scores(metrics)

    assert quality.business_quality is not None and "gross margin" in quality.business_quality_reason
    assert quality.financial_strength is not None and "current ratio" in quality.financial_strength_reason
    assert quality.growth_quality is not None and "revenue growth" in quality.growth_quality_reason
    assert quality.profitability is not None and "net margin" in quality.profitability_reason
    assert quality.capital_allocation is not None
    assert len(quality.available_scores) == 5


def test_quality_scores_are_none_with_a_reason_when_data_is_missing():
    empty_bundle = RawFundamentalsBundle(ticker="EMPTY", fetched_at=pd.Timestamp.utcnow())
    metrics = compute_metrics_history(empty_bundle)
    quality = build_quality_scores(metrics)

    assert quality.available_scores == ()
    assert quality.business_quality is None
    assert "Insufficient" in quality.business_quality_reason
    assert quality.financial_strength is None
    assert quality.growth_quality is None
    assert quality.profitability is None
    assert quality.capital_allocation is None
