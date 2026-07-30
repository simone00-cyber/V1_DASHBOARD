from __future__ import annotations

import pandas as pd
import pytest

from data.providers.fundamentals.models import RawFundamentalsBundle
from fundamentals.metrics import compute_metrics_history, has_minimum_data


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
            dates[0]: [500.0, 200.0, 300.0, 150.0, 60.0, 50.0, 40.0],
            dates[1]: [560.0, 230.0, 330.0, 160.0, 65.0, 55.0, 35.0],
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
        ticker="TEST",
        fetched_at=pd.Timestamp.utcnow(),
        info={"currentPrice": 50.0, "sharesOutstanding": 10.0, "trailingPE": 12.0},
        income_stmt=income,
        quarterly_income_stmt=pd.DataFrame(),
        balance_sheet=balance,
        quarterly_balance_sheet=pd.DataFrame(),
        cashflow=cashflow,
        quarterly_cashflow=pd.DataFrame(),
    )


def test_compute_metrics_history_derives_margins_growth_and_ratios():
    metrics = compute_metrics_history(_bundle())
    annual = metrics.annual

    assert has_minimum_data(annual)
    assert annual.revenue_growth.dropna().iloc[-1] == pytest.approx(0.2)
    assert annual.gross_margin.dropna().iloc[-1] == pytest.approx(50 / 120)
    assert annual.net_debt.dropna().iloc[-1] == pytest.approx(35 - 55)
    assert annual.current_ratio.dropna().iloc[-1] == pytest.approx(160 / 65)
    assert annual.debt_to_equity.dropna().iloc[-1] == pytest.approx(35 / 330)
    assert annual.roe.dropna().iloc[-1] == pytest.approx(21 / 330)
    assert annual.roa.dropna().iloc[-1] == pytest.approx(21 / 560)
    assert annual.eps_growth.dropna().iloc[-1] == pytest.approx(0.4)
    # Free cash flow falls back to operating cash flow + capital expenditure
    # (capex is already a negative outflow) when no explicit FCF row exists.
    assert annual.free_cash_flow.dropna().iloc[-1] == pytest.approx(25.0 - 6.0)

    assert metrics.current_price == 50.0
    assert metrics.shares_outstanding == 10.0
    assert metrics.trailing_pe == 12.0


def test_missing_statement_is_nan_never_zero():
    bundle = _bundle()
    bundle_without_balance = RawFundamentalsBundle(
        ticker=bundle.ticker,
        fetched_at=bundle.fetched_at,
        info=bundle.info,
        income_stmt=bundle.income_stmt,
        quarterly_income_stmt=bundle.quarterly_income_stmt,
        balance_sheet=pd.DataFrame(),
        quarterly_balance_sheet=pd.DataFrame(),
        cashflow=bundle.cashflow,
        quarterly_cashflow=bundle.quarterly_cashflow,
    )

    metrics = compute_metrics_history(bundle_without_balance)

    assert metrics.annual.total_assets.isna().all()
    assert metrics.annual.current_ratio.isna().all()
    assert metrics.annual.debt_to_equity.isna().all()
    # Revenue/net income still compute fine — only balance-sheet-derived ratios are affected.
    assert has_minimum_data(metrics.annual)


def test_has_minimum_data_false_for_a_completely_empty_bundle():
    empty_bundle = RawFundamentalsBundle(ticker="EMPTY", fetched_at=pd.Timestamp.utcnow())
    metrics = compute_metrics_history(empty_bundle)
    assert not has_minimum_data(metrics.annual)
