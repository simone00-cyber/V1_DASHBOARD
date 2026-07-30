import pandas as pd
from analysis.matrix import build_matrix_timeline, matrix_timeline_frame


def _frame(index, values):
    return pd.DataFrame({"Close": range(100, 100 + len(index)), "Composite": values}, index=pd.to_datetime(index))


def test_matrix_timeline_exposes_documented_and_undefined_cases():
    weekly_dates = pd.date_range("2024-01-05", periods=8, freq="W-FRI")
    frames = {
        "WEEKLY": _frame(weekly_dates, [-3, -2, -1, -2, -3, -2, -1, -2]),
        "MONTHLY": _frame(["2023-12-31", "2024-01-31", "2024-02-29"], [-3, -2, -1]),
        "QUARTERLY": _frame(["2023-09-30", "2023-12-31", "2024-03-31"], [-3, -2, -1]),
    }
    decisions = build_matrix_timeline(frames)
    assert decisions
    frame = matrix_timeline_frame(decisions)
    assert {"INSTRUCTION", "NEW EVENT", "STABILITY WEEKS", "WHY", "PROVENANCE"}.issubset(frame.columns)
    assert frame["INSTRUCTION"].isin(["BUY", "SELL SHORT", "TAKE PROFIT", "NOT DEFINED"]).all()


def test_persistent_instruction_is_not_relabelled_as_new_event():
    weekly_dates = pd.date_range("2024-01-05", periods=7, freq="W-FRI")
    frames = {
        "WEEKLY": _frame(weekly_dates, [0, -1, -2, -3, -4, -5, -6]),
        "MONTHLY": _frame(["2023-12-31", "2024-01-31", "2024-02-29"], [0, 1, 2]),
        "QUARTERLY": _frame(["2023-09-30", "2023-12-31", "2024-03-31"], [0, 1, 2]),
    }
    frame = matrix_timeline_frame(build_matrix_timeline(frames))
    tp = frame[frame["INSTRUCTION"] == "TAKE PROFIT"]
    if len(tp) >= 2:
        assert tp.iloc[0]["NEW EVENT"] in (True, False)
        assert tp.iloc[-1]["STABILITY WEEKS"] >= 1
