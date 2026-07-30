import pandas as pd

from analysis.execution import ExecutionPolicy, build_policy_trace
from analysis.signals.models import DocumentedSignal
from analysis.trades.execution import run_trade_engine


def signal(date, action, price=100.0):
    return DocumentedSignal(
        date=pd.Timestamp(date), action=action, rating=4, price=price,
        quarterly_direction="UP", monthly_direction="UP",
        weekly_turn="SVOLTA UP", weekly_composite=-20.0, weekly_phase="UP",
    )


def test_signal_only_keeps_exposure_on_take_profit():
    rows = build_policy_trace(
        [signal("2024-01-05", "BUY"), signal("2024-01-12", "TAKE PROFIT", 110)],
        ExecutionPolicy("LONG_ONLY", "SIGNAL_ONLY"),
    )
    assert rows[-1].exposure_before == 1.0
    assert rows[-1].exposure_after == 1.0
    assert rows[-1].action_taken == "REGISTER TAKE PROFIT"


def test_partial_take_profit_reduces_exposure_once_per_instruction_run():
    signals = [
        signal("2024-01-05", "BUY", 100),
        signal("2024-01-12", "TAKE PROFIT", 110),
        signal("2024-01-19", "TAKE PROFIT", 112),
    ]
    rows = build_policy_trace(signals, ExecutionPolicy("LONG_ONLY", "PARTIAL_EXIT", 0.50))
    assert rows[1].exposure_after == 0.5
    assert rows[2].exposure_after == 0.5
    trades = run_trade_engine(
        signals, pd.DatetimeIndex([s.date for s in signals]), "LONG_ONLY",
        take_profit_policy="PARTIAL_EXIT", partial_exit_fraction=0.50,
    )
    assert len(trades) == 1
    assert trades[0].size == 0.5
    assert trades[0].exit_reason == "TAKE PROFIT"


def test_new_buy_restores_full_exposure_after_partial_exit():
    signals = [
        signal("2024-01-05", "BUY"),
        signal("2024-01-12", "TAKE PROFIT"),
        signal("2024-01-19", "BUY"),
    ]
    rows = build_policy_trace(signals, ExecutionPolicy("LONG_ONLY", "PARTIAL_EXIT", 0.50))
    assert rows[-1].exposure_before == 0.5
    assert rows[-1].exposure_after == 1.0
    assert rows[-1].action_taken == "RESTORE LONG EXPOSURE"
