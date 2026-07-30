import pandas as pd

from analysis.cyclical.cycle_timing import DOCUMENTED_CYCLE_BARS, dominant_cyclical_timeframe
from analysis.cyclical.models import CycleState


def _state(timeframe: str, phase: str) -> CycleState:
    return CycleState(
        timeframe=timeframe,
        date=pd.Timestamp("2024-01-01"),
        composite=10.0,
        previous_composite=5.0,
        slope=1.0,
        previous_slope=0.5,
        direction="UP",
        phase=phase,
        zone="POSITIVO",
        excess="NESSUN ECCESSO",
        turn="PROSEGUE UP",
        state_age=4,
        phase_start=pd.Timestamp("2023-12-01"),
        distance_from_zero=10.0,
        slope_change=0.5,
    )


def test_documented_cycle_bars_covers_the_tactically_relevant_timeframes():
    assert set(DOCUMENTED_CYCLE_BARS) == {"WEEKLY", "MONTHLY", "QUARTERLY"}
    for low, high in DOCUMENTED_CYCLE_BARS.values():
        assert 0 < low < high


def test_dominant_cyclical_timeframe_prefers_the_highest_directional_timeframe():
    states = {
        "QUARTERLY": _state("QUARTERLY", "NEUTRAL"),
        "MONTHLY": _state("MONTHLY", "ADVANCING"),
        "WEEKLY": _state("WEEKLY", "UP"),
    }
    assert dominant_cyclical_timeframe(states) == "MONTHLY"


def test_dominant_cyclical_timeframe_falls_back_to_quarterly_when_directional():
    states = {"QUARTERLY": _state("QUARTERLY", "UP"), "WEEKLY": _state("WEEKLY", "DOWN")}
    assert dominant_cyclical_timeframe(states) == "QUARTERLY"


def test_dominant_cyclical_timeframe_falls_back_to_any_state_when_all_neutral():
    states = {"WEEKLY": _state("WEEKLY", "NEUTRAL")}
    assert dominant_cyclical_timeframe(states) == "WEEKLY"


def test_dominant_cyclical_timeframe_handles_empty_input():
    assert dominant_cyclical_timeframe({}) is None
