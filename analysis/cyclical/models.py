"""Data models for the documented cyclical engine.

Only the Composite Momentum formula, its documented interpretation and the
published multi-timeframe hierarchy are represented here. The proprietary
Investitore Disciplinato algorithm is intentionally not implemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pandas as pd


@dataclass(frozen=True)
class CycleState:
    timeframe: str
    date: pd.Timestamp
    composite: float
    previous_composite: float
    slope: float
    previous_slope: Optional[float]
    direction: str
    phase: str
    zone: str
    excess: str
    turn: str
    state_age: int
    phase_start: pd.Timestamp
    distance_from_zero: float
    slope_change: Optional[float]


@dataclass(frozen=True)
class HierarchyAssessment:
    annual_phase: str
    quarterly_phase: str
    monthly_phase: str
    weekly_phase: str
    quarterly_direction: str
    monthly_direction: str
    weekly_direction: str
    alignment: str
    tactical_condition: str
    documented_trigger: str
    notes: Tuple[str, ...]


@dataclass(frozen=True)
class MethodologyStatus:
    component: str
    status: str
    source: str
    note: str
