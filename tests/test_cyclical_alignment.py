from dataclasses import replace
import pandas as pd

from analysis.cyclical.alignment import assess_hierarchy
from analysis.cyclical.models import CycleState


def state(tf: str, direction: str, phase: str, turn: str = "PROSEGUE UP") -> CycleState:
    return CycleState(
        timeframe=tf,
        date=pd.Timestamp("2026-06-30"),
        composite=20.0,
        previous_composite=10.0,
        slope=10.0 if direction == "UP" else -10.0,
        previous_slope=5.0,
        direction=direction,
        phase=phase,
        zone="POSITIVO",
        excess="NESSUN ECCESSO",
        turn=turn,
        state_age=2,
        phase_start=pd.Timestamp("2026-03-31"),
        distance_from_zero=20.0,
        slope_change=5.0,
    )


def test_correction_in_uptrend_trigger():
    states = {
        "YEARLY": state("YEARLY", "UP", "ADVANCING"),
        "QUARTERLY": state("QUARTERLY", "UP", "ADVANCING"),
        "MONTHLY": state("MONTHLY", "UP", "ADVANCING"),
        "WEEKLY": state("WEEKLY", "DOWN", "DOWN", "PROSEGUE DOWN"),
    }
    result = assess_hierarchy(states)
    assert result.alignment == "BULLISH HIGHER-TIMEFRAME ALIGNMENT"
    assert "SVOLTA UP" in result.documented_trigger


def test_full_bearish_alignment():
    states = {
        "YEARLY": state("YEARLY", "DOWN", "DOWN", "PROSEGUE DOWN"),
        "QUARTERLY": state("QUARTERLY", "DOWN", "DOWN", "PROSEGUE DOWN"),
        "MONTHLY": state("MONTHLY", "DOWN", "TERMINATING", "PROSEGUE DOWN"),
        "WEEKLY": state("WEEKLY", "DOWN", "TERMINATING", "PROSEGUE DOWN"),
    }
    result = assess_hierarchy(states)
    assert result.alignment == "FULL BEARISH ALIGNMENT"
