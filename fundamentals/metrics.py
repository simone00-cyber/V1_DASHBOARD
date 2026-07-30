"""Derives normalized financial metrics from a raw fundamentals bundle.

Every metric is computed strictly from data actually returned by the
provider. A line item Yahoo did not publish stays `NaN` at that position —
it is never filled with 0, an estimate, or a neighboring period's value.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from data.providers.fundamentals.models import RawFundamentalsBundle
from fundamentals.models import FinancialMetricsHistory, StatementSeries

_REVENUE = ("Total Revenue",)
_GROSS_PROFIT = ("Gross Profit",)
_OPERATING_INCOME = ("Operating Income",)
_NET_INCOME = ("Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations")
_EBITDA = ("EBITDA", "Normalized EBITDA")
_EPS_DILUTED = ("Diluted EPS",)
_INTEREST_EXPENSE = ("Interest Expense", "Interest Expense Non Operating")

_TOTAL_ASSETS = ("Total Assets",)
_TOTAL_LIABILITIES = ("Total Liabilities Net Minority Interest", "Total Liab")
_TOTAL_EQUITY = ("Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest")
_CURRENT_ASSETS = ("Current Assets",)
_CURRENT_LIABILITIES = ("Current Liabilities",)
_CASH = ("Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")
_TOTAL_DEBT = ("Total Debt",)

_OPERATING_CASH_FLOW = ("Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
_CAPEX = ("Capital Expenditure",)
_FREE_CASH_FLOW = ("Free Cash Flow",)


def _first_available_row(frame: pd.DataFrame, aliases: Sequence[str]) -> pd.Series | None:
    if frame is None or frame.empty:
        return None
    for alias in aliases:
        if alias in frame.index:
            row = frame.loc[alias]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            numeric = pd.to_numeric(row, errors="coerce")
            return numeric.sort_index()
    return None


def _combined_index(*series_list: pd.Series | None) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex([])
    for series in series_list:
        if series is not None and not series.empty:
            index = index.union(pd.DatetimeIndex(series.index))
    return index.sort_values()


def _reindexed(series: pd.Series | None, index: pd.DatetimeIndex) -> pd.Series:
    if series is None:
        return pd.Series(index=index, dtype=float)
    return series.reindex(index)


def _safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denom = denominator.mask(denominator == 0)
    return numerator / denom


def _num(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def _build_statement_series(
    income_frame: pd.DataFrame,
    balance_frame: pd.DataFrame,
    cashflow_frame: pd.DataFrame,
) -> StatementSeries:
    revenue = _first_available_row(income_frame, _REVENUE)
    gross_profit = _first_available_row(income_frame, _GROSS_PROFIT)
    operating_income = _first_available_row(income_frame, _OPERATING_INCOME)
    net_income = _first_available_row(income_frame, _NET_INCOME)
    ebitda = _first_available_row(income_frame, _EBITDA)
    eps_diluted = _first_available_row(income_frame, _EPS_DILUTED)
    interest_expense = _first_available_row(income_frame, _INTEREST_EXPENSE)

    total_assets = _first_available_row(balance_frame, _TOTAL_ASSETS)
    total_liabilities = _first_available_row(balance_frame, _TOTAL_LIABILITIES)
    total_equity = _first_available_row(balance_frame, _TOTAL_EQUITY)
    current_assets = _first_available_row(balance_frame, _CURRENT_ASSETS)
    current_liabilities = _first_available_row(balance_frame, _CURRENT_LIABILITIES)
    cash_and_equivalents = _first_available_row(balance_frame, _CASH)
    total_debt = _first_available_row(balance_frame, _TOTAL_DEBT)

    operating_cash_flow = _first_available_row(cashflow_frame, _OPERATING_CASH_FLOW)
    capital_expenditure = _first_available_row(cashflow_frame, _CAPEX)
    free_cash_flow = _first_available_row(cashflow_frame, _FREE_CASH_FLOW)

    index = _combined_index(
        revenue, gross_profit, operating_income, net_income, ebitda, eps_diluted,
        interest_expense, total_assets, total_liabilities, total_equity,
        current_assets, current_liabilities, cash_and_equivalents, total_debt,
        operating_cash_flow, capital_expenditure, free_cash_flow,
    )

    revenue = _reindexed(revenue, index)
    gross_profit = _reindexed(gross_profit, index)
    operating_income = _reindexed(operating_income, index)
    net_income = _reindexed(net_income, index)
    ebitda = _reindexed(ebitda, index)
    eps_diluted = _reindexed(eps_diluted, index)
    interest_expense = _reindexed(interest_expense, index)
    total_assets = _reindexed(total_assets, index)
    total_liabilities = _reindexed(total_liabilities, index)
    total_equity = _reindexed(total_equity, index)
    current_assets = _reindexed(current_assets, index)
    current_liabilities = _reindexed(current_liabilities, index)
    cash_and_equivalents = _reindexed(cash_and_equivalents, index)
    total_debt = _reindexed(total_debt, index)
    operating_cash_flow = _reindexed(operating_cash_flow, index)
    capital_expenditure = _reindexed(capital_expenditure, index)
    free_cash_flow = _reindexed(free_cash_flow, index)

    if free_cash_flow.isna().all() and not (operating_cash_flow.isna().all() and capital_expenditure.isna().all()):
        free_cash_flow = operating_cash_flow + capital_expenditure

    gross_margin = _safe_div(gross_profit, revenue)
    operating_margin = _safe_div(operating_income, revenue)
    net_margin = _safe_div(net_income, revenue)
    revenue_growth = revenue.pct_change()
    eps_growth = eps_diluted.pct_change()
    net_debt = total_debt - cash_and_equivalents
    current_ratio = _safe_div(current_assets, current_liabilities)
    debt_to_equity = _safe_div(total_debt, total_equity)
    interest_coverage = _safe_div(operating_income, interest_expense.abs())
    roe = _safe_div(net_income, total_equity)
    roa = _safe_div(net_income, total_assets)

    return StatementSeries(
        revenue=revenue,
        gross_profit=gross_profit,
        operating_income=operating_income,
        net_income=net_income,
        ebitda=ebitda,
        eps_diluted=eps_diluted,
        operating_cash_flow=operating_cash_flow,
        capital_expenditure=capital_expenditure,
        free_cash_flow=free_cash_flow,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        total_equity=total_equity,
        current_assets=current_assets,
        current_liabilities=current_liabilities,
        cash_and_equivalents=cash_and_equivalents,
        total_debt=total_debt,
        interest_expense=interest_expense,
        gross_margin=gross_margin,
        operating_margin=operating_margin,
        net_margin=net_margin,
        revenue_growth=revenue_growth,
        eps_growth=eps_growth,
        net_debt=net_debt,
        current_ratio=current_ratio,
        debt_to_equity=debt_to_equity,
        interest_coverage=interest_coverage,
        roe=roe,
        roa=roa,
    )


def has_minimum_data(annual: StatementSeries) -> bool:
    """At least one annual period must carry both revenue and net income."""
    return bool(annual.revenue.notna().any() and annual.net_income.notna().any())


def compute_metrics_history(bundle: RawFundamentalsBundle) -> FinancialMetricsHistory:
    annual = _build_statement_series(bundle.income_stmt, bundle.balance_sheet, bundle.cashflow)
    quarterly = _build_statement_series(
        bundle.quarterly_income_stmt, bundle.quarterly_balance_sheet, bundle.quarterly_cashflow
    )

    info = bundle.info or {}
    current_price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))

    return FinancialMetricsHistory(
        ticker=bundle.ticker,
        annual=annual,
        quarterly=quarterly,
        current_price=current_price,
        market_cap=_num(info.get("marketCap")),
        enterprise_value=_num(info.get("enterpriseValue")),
        shares_outstanding=_num(info.get("sharesOutstanding")),
        trailing_pe=_num(info.get("trailingPE")),
        forward_pe=_num(info.get("forwardPE")),
        peg_ratio=_num(info.get("pegRatio") or info.get("trailingPegRatio")),
        ev_to_ebitda=_num(info.get("enterpriseToEbitda")),
        price_to_sales=_num(info.get("priceToSalesTrailing12Months")),
        price_to_book=_num(info.get("priceToBook")),
        dividend_yield=_num(info.get("dividendYield")),
    )
