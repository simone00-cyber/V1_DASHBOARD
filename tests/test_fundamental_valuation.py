from __future__ import annotations

import pandas as pd
import pytest

from fundamentals import config
from fundamentals.models import FinancialMetricsHistory, StatementSeries
from fundamentals.valuation import build_valuation_estimate


def _empty_series() -> pd.Series:
    return pd.Series(dtype=float)


def _series(values: list[float]) -> pd.Series:
    dates = [pd.Timestamp(year=2020 + i, month=12, day=31) for i in range(len(values))]
    return pd.Series(values, index=dates)


def _annual(eps_values: list[float], fcf_values: list[float]) -> StatementSeries:
    return StatementSeries(
        revenue=_empty_series(),
        gross_profit=_empty_series(),
        operating_income=_empty_series(),
        net_income=_empty_series(),
        ebitda=_empty_series(),
        eps_diluted=_series(eps_values),
        operating_cash_flow=_empty_series(),
        capital_expenditure=_empty_series(),
        free_cash_flow=_series(fcf_values),
        total_assets=_empty_series(),
        total_liabilities=_empty_series(),
        total_equity=_empty_series(),
        current_assets=_empty_series(),
        current_liabilities=_empty_series(),
        cash_and_equivalents=_empty_series(),
        total_debt=_empty_series(),
        interest_expense=_empty_series(),
        gross_margin=_empty_series(),
        operating_margin=_empty_series(),
        net_margin=_empty_series(),
        revenue_growth=_empty_series(),
        eps_growth=_empty_series(),
        net_debt=_empty_series(),
        current_ratio=_empty_series(),
        debt_to_equity=_empty_series(),
        interest_coverage=_empty_series(),
        roe=_empty_series(),
        roa=_empty_series(),
    )


def _metrics(eps_values, fcf_values, *, shares=10.0, price=50.0) -> FinancialMetricsHistory:
    annual = _annual(eps_values, fcf_values)
    return FinancialMetricsHistory(
        ticker="TEST",
        annual=annual,
        quarterly=annual,
        current_price=price,
        shares_outstanding=shares,
    )


def test_earnings_power_value_matches_gordon_growth_formula():
    metrics = _metrics(eps_values=[4.0, 5.0, 6.0], fcf_values=[])
    valuation = build_valuation_estimate(metrics)

    method = next(m for m in valuation.methods if m.label == "Earnings Power Value")
    normalized_eps = (4.0 + 5.0 + 6.0) / 3
    expected_base = normalized_eps / (config.REQUIRED_RETURN - config.EARNINGS_GROWTH_BASE)

    assert method.base == pytest.approx(expected_base)
    assert valuation.composite_fair_value == pytest.approx(expected_base)


def test_margin_of_safety_and_upside_are_derived_from_composite_and_price():
    metrics = _metrics(eps_values=[4.0, 5.0, 6.0], fcf_values=[])
    valuation = build_valuation_estimate(metrics)

    fair = valuation.composite_fair_value
    price = 50.0
    assert valuation.margin_of_safety == pytest.approx((fair - price) / fair)
    assert valuation.upside_pct == pytest.approx((fair - price) / price)


def test_fcf_power_value_is_computed_when_shares_and_positive_fcf_available():
    metrics = _metrics(eps_values=[], fcf_values=[10.0, 12.0, 14.0])
    valuation = build_valuation_estimate(metrics)

    method = next(m for m in valuation.methods if m.label == "FCF Power Value")
    assert method.base is not None
    assert method.base > 0


def test_no_valuation_when_eps_and_fcf_are_both_negative_or_missing():
    metrics = _metrics(eps_values=[-1.0, -2.0], fcf_values=[-5.0, -6.0])
    valuation = build_valuation_estimate(metrics)

    assert valuation.methods == ()
    assert valuation.composite_fair_value is None
    assert valuation.margin_of_safety is None
    assert valuation.upside_pct is None


def test_fcf_power_value_unavailable_without_shares_outstanding():
    metrics = _metrics(eps_values=[], fcf_values=[10.0, 12.0, 14.0], shares=None)
    valuation = build_valuation_estimate(metrics)
    assert all(m.label != "FCF Power Value" for m in valuation.methods)
