from __future__ import annotations
from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True)
class Trade:
    side: str
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: pd.Timestamp
    exit_price: float
    exit_reason: str
    entry_rating: int
    entry_quarterly: str
    entry_monthly: str
    entry_weekly_phase: str
    entry_weekly_composite: float
    bars_held: int
    gross_return: float
    net_return: float
    size: float = 1.0
