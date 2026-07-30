from types import SimpleNamespace

import pandas as pd

from analysis.security_signal import build_signal_history, build_tactical_signal_state


def _frame(index, values):
    return pd.DataFrame(
        {
            "Close": [100.0 + i for i in range(len(values))],
            "Composite": values,
        },
        index=pd.to_datetime(index),
    )


def test_buy_event_is_reconstructed_from_weekly_turn_up():
    frames = {
        "QUARTERLY": _frame(
            ["2025-03-31", "2025-06-30", "2025-09-30"],
            [-20, 10, 30],
        ),
        "MONTHLY": _frame(
            ["2025-07-31", "2025-08-31", "2025-09-30", "2025-10-31"],
            [-10, 0, 10, 20],
        ),
        "WEEKLY": _frame(
            ["2025-10-03", "2025-10-10", "2025-10-17", "2025-10-24"],
            [20, 10, 5, 12],
        ),
    }

    events = build_signal_history(frames)
    assert events[-1].action == "BUY"
    assert events[-1].rating == 4
    assert events[-1].weekly_turn == "SVOLTA UP"


def test_up_up_weekly_down_is_waiting_for_bullish_trigger_without_event():
    frames = {
        "QUARTERLY": _frame(
            ["2025-03-31", "2025-06-30", "2025-09-30"],
            [-20, 10, 30],
        ),
        "MONTHLY": _frame(
            ["2025-07-31", "2025-08-31", "2025-09-30", "2025-10-31"],
            [-10, 0, 10, 20],
        ),
        "WEEKLY": _frame(
            ["2025-10-03", "2025-10-10", "2025-10-17", "2025-10-24"],
            [30, 25, 20, 15],
        ),
    }
    summaries = {
        "QUARTERLY": SimpleNamespace(direction="UP"),
        "MONTHLY": SimpleNamespace(direction="UP"),
        "WEEKLY": SimpleNamespace(
            direction="DOWN",
            turn="PROSEGUE DOWN",
            date=pd.Timestamp("2025-10-24"),
        ),
    }

    state = build_tactical_signal_state(frames, summaries)
    assert state.status == "RISK REDUCTION / TAKE PROFIT"
    assert state.latest_event == "TAKE PROFIT"
    assert state.current_position == "NEUTRAL"
    assert "SVOLTA UP" in state.next_trigger
    assert state.weekly_phase == "CORREZIONE SETTIMANALE IN TREND RIALZISTA"


def test_active_long_is_preserved_when_latest_bar_has_no_new_event():
    frames = {
        "QUARTERLY": _frame(
            ["2025-03-31", "2025-06-30", "2025-09-30"],
            [-20, 10, 30],
        ),
        "MONTHLY": _frame(
            ["2025-07-31", "2025-08-31", "2025-09-30", "2025-10-31"],
            [-10, 0, 10, 20],
        ),
        "WEEKLY": _frame(
            ["2025-10-03", "2025-10-10", "2025-10-17", "2025-10-24", "2025-10-31"],
            [20, 10, 5, 12, 18],
        ),
    }
    summaries = {
        "QUARTERLY": SimpleNamespace(direction="UP"),
        "MONTHLY": SimpleNamespace(direction="UP"),
        "WEEKLY": SimpleNamespace(
            direction="UP",
            turn="PROSEGUE UP",
            date=pd.Timestamp("2025-10-31"),
        ),
    }

    state = build_tactical_signal_state(frames, summaries)
    assert state.current_position == "LONG"
    assert state.latest_event == "NO NEW SIGNAL"
    assert state.status == "ACTIVE / NO NEW EVENT"
    assert state.signal_date == pd.Timestamp("2025-10-24")
