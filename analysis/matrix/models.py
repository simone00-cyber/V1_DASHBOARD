"""Transparent decision-state models for the public 12-case matrix."""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True)
class MatrixDecision:
    date: pd.Timestamp
    price: float
    quarterly_direction: str
    monthly_direction: str
    weekly_turn: str
    weekly_phase: str
    weekly_composite: float
    instruction: str
    rating: int
    decision_type: str
    is_new_event: bool
    stability_weeks: int
    explanation: str
    provenance: str
