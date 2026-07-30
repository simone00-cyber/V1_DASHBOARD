"""Models for events generated exclusively by the published tactical matrix."""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class DocumentedSignal:
    date: pd.Timestamp
    action: str
    rating: int
    price: float
    quarterly_direction: str
    monthly_direction: str
    weekly_turn: str
    weekly_composite: float
    weekly_phase: str
