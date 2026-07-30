from __future__ import annotations

import pandas as pd
import pytest

from data.providers.fundamentals.base import (
    FundamentalDataConfigurationError,
    FundamentalDataUnavailableError,
)
from data.providers.fundamentals.yfinance_provider import YFinanceFundamentalsProvider


class FakeTicker:
    def __init__(self, *, info=None, income_stmt=None, raise_on: set[str] | None = None):
        self._info = info if info is not None else {}
        self._income_stmt = income_stmt if income_stmt is not None else pd.DataFrame()
        self._empty = pd.DataFrame()
        self._raise_on = raise_on or set()

    def _get(self, name: str, value):
        if name in self._raise_on:
            raise RuntimeError(f"{name} failed")
        return value

    @property
    def info(self):
        return self._get("info", self._info)

    @property
    def income_stmt(self):
        return self._get("income_stmt", self._income_stmt)

    @property
    def quarterly_income_stmt(self):
        return self._get("quarterly_income_stmt", self._empty)

    @property
    def balance_sheet(self):
        return self._get("balance_sheet", self._empty)

    @property
    def quarterly_balance_sheet(self):
        return self._get("quarterly_balance_sheet", self._empty)

    @property
    def cashflow(self):
        return self._get("cashflow", self._empty)

    @property
    def quarterly_cashflow(self):
        return self._get("quarterly_cashflow", self._empty)


def test_fetch_returns_bundle_with_normalized_ticker_and_raw_fields():
    income = pd.DataFrame({pd.Timestamp("2023-12-31"): [100.0]}, index=["Total Revenue"])
    ticker_obj = FakeTicker(info={"currentPrice": 10.0}, income_stmt=income)
    provider = YFinanceFundamentalsProvider(ticker_factory=lambda t: ticker_obj)

    bundle = provider.fetch("aapl ")

    assert bundle.ticker == "AAPL"
    assert bundle.info == {"currentPrice": 10.0}
    assert not bundle.income_stmt.empty
    assert bundle.balance_sheet.empty


def test_empty_ticker_raises_configuration_error():
    provider = YFinanceFundamentalsProvider(ticker_factory=lambda t: FakeTicker())
    with pytest.raises(FundamentalDataConfigurationError):
        provider.fetch("   ")


def test_ticker_factory_failure_raises_unavailable_error():
    def factory(ticker):
        raise RuntimeError("network down")

    provider = YFinanceFundamentalsProvider(ticker_factory=factory)
    with pytest.raises(FundamentalDataUnavailableError, match="network down"):
        provider.fetch("AAPL")


def test_totally_empty_response_raises_unavailable_error():
    provider = YFinanceFundamentalsProvider(ticker_factory=lambda t: FakeTicker())
    with pytest.raises(FundamentalDataUnavailableError):
        provider.fetch("AAPL")


def test_partial_failure_leaves_only_that_field_empty_never_fabricated():
    ticker_obj = FakeTicker(info={"currentPrice": 10.0}, raise_on={"income_stmt"})
    provider = YFinanceFundamentalsProvider(ticker_factory=lambda t: ticker_obj)

    bundle = provider.fetch("AAPL")

    assert bundle.income_stmt.empty
    assert bundle.info == {"currentPrice": 10.0}
