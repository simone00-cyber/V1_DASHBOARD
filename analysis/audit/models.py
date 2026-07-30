from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import pandas as pd


@dataclass(frozen=True)
class ExecutionTransition:
    date: pd.Timestamp
    signal: str
    state_before: str
    action_taken: str
    state_after: str
    reason: str
    signal_rating: int
    signal_price: float
    opened_side: Optional[str] = None
    closed_side: Optional[str] = None
    exposure_before: float = 0.0
    exposure_after: float = 0.0


@dataclass(frozen=True)
class ExecutionAudit:
    passed: bool
    checks: Tuple[dict, ...]
    transitions: Tuple[ExecutionTransition, ...]
