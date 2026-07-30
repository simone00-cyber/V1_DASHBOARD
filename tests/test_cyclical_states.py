import pandas as pd

from analysis.cyclical.states import classify_cycle_phase, build_cycle_state


def test_documented_four_phases():
    assert classify_cycle_phase(-10.0, "UP") == "UP"
    assert classify_cycle_phase(10.0, "UP") == "ADVANCING"
    assert classify_cycle_phase(10.0, "DOWN") == "DOWN"
    assert classify_cycle_phase(-10.0, "DOWN") == "TERMINATING"
    assert classify_cycle_phase(0.0, "FLAT") == "NEUTRAL"


def test_state_age_and_phase_start():
    index = pd.date_range("2025-01-31", periods=6, freq="ME")
    frame = pd.DataFrame(
        {
            "Close": [10, 11, 12, 13, 14, 15],
            "Composite": [-30, -20, -5, 5, 15, 25],
        },
        index=index,
    )
    state = build_cycle_state("MONTHLY", frame)
    assert state.phase == "ADVANCING"
    assert state.state_age == 3
    assert state.phase_start == index[3]
    assert state.turn == "PROSEGUE UP"
