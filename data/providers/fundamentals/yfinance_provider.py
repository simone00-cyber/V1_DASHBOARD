from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from data.providers.fundamentals.base import (
    FundamentalDataConfigurationError,
    FundamentalDataProvider,
    FundamentalDataUnavailableError,
)
from data.providers.fundamentals.models import RawFundamentalsBundle


def _default_ticker_factory(ticker: str) -> Any:
    import yfinance as yf

    return yf.Ticker(ticker)


def _safe_dict(getter: Callable[[], Any]) -> dict:
    try:
        value = getter()
    except Exception:
        return {}
    return dict(value) if isinstance(value, dict) else {}


def _safe_frame(getter: Callable[[], Any]) -> pd.DataFrame:
    try:
        value = getter()
    except Exception:
        return pd.DataFrame()
    return value if isinstance(value, pd.DataFrame) else pd.DataFrame()


class YFinanceFundamentalsProvider(FundamentalDataProvider):
    """Yahoo Finance implementation of `FundamentalDataProvider`.

    Wraps `yfinance.Ticker`. The rest of the application never imports
    `yfinance` directly for fundamentals — only this module does. Any single
    missing field/statement is left empty (never fabricated); only a total
    failure to reach the source raises `FundamentalDataUnavailableError`.
    """

    def __init__(self, *, ticker_factory: Callable[[str], Any] | None = None) -> None:
        self._ticker_factory = ticker_factory or _default_ticker_factory

    def fetch(self, ticker: str) -> RawFundamentalsBundle:
        normalized = ticker.strip().upper() if isinstance(ticker, str) else ""
        if not normalized:
            raise FundamentalDataConfigurationError("Ticker cannot be empty.")

        try:
            client = self._ticker_factory(normalized)
        except Exception as exc:
            raise FundamentalDataUnavailableError(
                f"Unable to reach Yahoo Finance for {normalized}: {exc}"
            ) from exc

        bundle = RawFundamentalsBundle(
            ticker=normalized,
            fetched_at=pd.Timestamp.utcnow(),
            info=_safe_dict(lambda: client.info),
            income_stmt=_safe_frame(lambda: client.income_stmt),
            quarterly_income_stmt=_safe_frame(lambda: client.quarterly_income_stmt),
            balance_sheet=_safe_frame(lambda: client.balance_sheet),
            quarterly_balance_sheet=_safe_frame(lambda: client.quarterly_balance_sheet),
            cashflow=_safe_frame(lambda: client.cashflow),
            quarterly_cashflow=_safe_frame(lambda: client.quarterly_cashflow),
        )

        if not bundle.info and not bundle.has_any_statement:
            raise FundamentalDataUnavailableError(
                f"Yahoo Finance returned no fundamentals data at all for {normalized}."
            )

        return bundle
