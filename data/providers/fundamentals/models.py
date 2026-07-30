from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True)
class RawFundamentalsBundle:
    """Unmodified raw fundamentals for one ticker, as published by the source.

    Every DataFrame is indexed by line-item label with one column per
    period-end date (the native `yfinance` statement shape), newest period
    first. An empty DataFrame means the source did not publish that
    statement — it is never backfilled or estimated.
    """

    ticker: str
    fetched_at: pd.Timestamp
    info: dict = field(default_factory=dict)
    income_stmt: pd.DataFrame = field(default_factory=pd.DataFrame)
    quarterly_income_stmt: pd.DataFrame = field(default_factory=pd.DataFrame)
    balance_sheet: pd.DataFrame = field(default_factory=pd.DataFrame)
    quarterly_balance_sheet: pd.DataFrame = field(default_factory=pd.DataFrame)
    cashflow: pd.DataFrame = field(default_factory=pd.DataFrame)
    quarterly_cashflow: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def has_any_statement(self) -> bool:
        return any(
            not frame.empty
            for frame in (
                self.income_stmt,
                self.quarterly_income_stmt,
                self.balance_sheet,
                self.quarterly_balance_sheet,
                self.cashflow,
                self.quarterly_cashflow,
            )
        )
