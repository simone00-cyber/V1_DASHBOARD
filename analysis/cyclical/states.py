"""Composite Momentum states documented in the cyclical methodology."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from caruso_analysis import classify_excess, classify_position
from analysis.cyclical.models import CycleState


PHASE_UP = "UP"
PHASE_ADVANCING = "ADVANCING"
PHASE_DOWN = "DOWN"
PHASE_TERMINATING = "TERMINATING"
PHASE_NEUTRAL = "NEUTRAL"


def classify_cycle_phase(value: float, direction: str) -> str:
    """Apply the four documented Composite Momentum cyclical positions.

    - below zero and rising: UP
    - above zero and rising: ADVANCING
    - above zero and falling: DOWN
    - below zero and falling: TERMINATING

    A flat reading is labelled NEUTRAL because the source defines the four
    positions only for rising/falling momentum.
    """
    if direction == "UP":
        return PHASE_ADVANCING if value >= 0 else PHASE_UP
    if direction == "DOWN":
        return PHASE_DOWN if value >= 0 else PHASE_TERMINATING
    return PHASE_NEUTRAL


def direction_series(composite: pd.Series) -> pd.Series:
    diff = composite.diff()
    return pd.Series(
        np.select([diff > 0, diff < 0], ["UP", "DOWN"], default="FLAT"),
        index=composite.index,
        dtype="object",
    )


def phase_series(composite: pd.Series) -> pd.Series:
    directions = direction_series(composite)
    return pd.Series(
        [classify_cycle_phase(float(value), str(direction)) if pd.notna(value) else None
         for value, direction in zip(composite, directions)],
        index=composite.index,
        dtype="object",
    )


def turn_series(composite: pd.Series) -> pd.Series:
    slope = composite.diff()
    previous_slope = slope.shift(1)
    result = pd.Series("FLAT", index=composite.index, dtype="object")
    result.loc[(previous_slope <= 0) & (slope > 0)] = "SVOLTA UP"
    result.loc[(previous_slope >= 0) & (slope < 0)] = "SVOLTA DOWN"
    result.loc[(result == "FLAT") & (slope > 0)] = "PROSEGUE UP"
    result.loc[(result == "FLAT") & (slope < 0)] = "PROSEGUE DOWN"
    return result


def _current_run_length(values: pd.Series) -> int:
    clean = values.dropna()
    if clean.empty:
        return 0
    current = clean.iloc[-1]
    age = 0
    for value in reversed(clean.tolist()):
        if value != current:
            break
        age += 1
    return age


def _phase_start(values: pd.Series) -> pd.Timestamp:
    clean = values.dropna()
    if clean.empty:
        return pd.NaT
    current = clean.iloc[-1]
    start = clean.index[-1]
    for idx, value in reversed(list(clean.items())):
        if value != current:
            break
        start = idx
    return pd.Timestamp(start)


def build_cycle_state(timeframe: str, frame: pd.DataFrame) -> CycleState:
    clean = frame.dropna(subset=["Composite"]).copy()
    if len(clean) < 3:
        raise ValueError(f"Dati insufficienti per classificare {timeframe}.")

    composite = clean["Composite"].astype(float)
    directions = direction_series(composite)
    phases = phase_series(composite)
    turns = turn_series(composite)
    slope = composite.diff()
    slope_change = slope.diff()

    value = float(composite.iloc[-1])
    previous = float(composite.iloc[-2])
    previous_slope: Optional[float] = float(slope.iloc[-2]) if pd.notna(slope.iloc[-2]) else None
    current_slope = float(slope.iloc[-1])
    current_slope_change: Optional[float] = (
        float(slope_change.iloc[-1]) if pd.notna(slope_change.iloc[-1]) else None
    )

    return CycleState(
        timeframe=timeframe,
        date=pd.Timestamp(clean.index[-1]),
        composite=value,
        previous_composite=previous,
        slope=current_slope,
        previous_slope=previous_slope,
        direction=str(directions.iloc[-1]),
        phase=str(phases.iloc[-1]),
        zone=classify_position(value),
        excess=classify_excess(value),
        turn=str(turns.iloc[-1]),
        state_age=_current_run_length(phases),
        phase_start=_phase_start(phases),
        distance_from_zero=value,
        slope_change=current_slope_change,
    )
