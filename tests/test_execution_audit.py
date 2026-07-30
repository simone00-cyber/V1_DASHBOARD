import pandas as pd
from analysis.audit import build_execution_trace, transition_for_signal
from analysis.audit.engine import build_execution_audit
from analysis.signals.models import DocumentedSignal
from analysis.trades.execution import run_trade_engine


def signal(date, action, price=100.0):
    return DocumentedSignal(
        date=pd.Timestamp(date), action=action, rating=4, price=price,
        quarterly_direction="UP", monthly_direction="UP",
        weekly_turn="SVOLTA UP", weekly_composite=-20.0, weekly_phase="UP",
    )


def test_take_profit_closes_long():
    signals = [signal("2024-01-05", "BUY", 100), signal("2024-01-12", "TAKE PROFIT", 110)]
    trace = build_execution_trace(signals, "LONG_ONLY")
    assert trace[0].state_after == "LONG"
    assert trace[1].action_taken == "CLOSE LONG"
    assert trace[1].state_after == "FLAT"
    trades = run_trade_engine(signals, pd.DatetimeIndex([s.date for s in signals]), "LONG_ONLY")
    assert len(trades) == 1
    assert trades[0].exit_reason == "TAKE PROFIT"


def test_take_profit_while_flat_is_visible_but_not_a_trade():
    signals = [signal("2024-01-05", "TAKE PROFIT")]
    trace = build_execution_trace(signals, "LONG_ONLY")
    assert trace[0].action_taken == "REMAIN FLAT"
    assert not run_trade_engine(signals, pd.DatetimeIndex([signals[0].date]), "LONG_ONLY")


def test_long_short_reversal_is_one_close_and_one_open():
    signals = [signal("2024-01-05", "BUY", 100), signal("2024-01-12", "SELL SHORT", 90)]
    trace = build_execution_trace(signals, "LONG_SHORT")
    assert trace[1].closed_side == "LONG"
    assert trace[1].opened_side == "SHORT"
    assert trace[1].state_after == "SHORT"


def test_repeated_buy_does_not_pyramid():
    signals = [signal("2024-01-05", "BUY"), signal("2024-01-12", "BUY")]
    trace = build_execution_trace(signals, "LONG_ONLY")
    assert trace[1].action_taken == "HOLD LONG"
    assert trace[1].state_after == "LONG"


def test_audit_reconciles_event_closes():
    signals = [signal("2024-01-05", "BUY", 100), signal("2024-01-12", "TAKE PROFIT", 110)]
    index = pd.DatetimeIndex([s.date for s in signals])
    trades = run_trade_engine(signals, index, "LONG_ONLY")
    weekly = pd.DataFrame({"Position": [1.0, 0.0], "StrategyReturn": [0.0, 0.1]}, index=index)
    audit = build_execution_audit(signals, trades, weekly, "LONG_ONLY")
    assert audit.passed
    assert any(row["CHECK"] == "TAKE PROFIT EVENTS" and row["VALUE"] == "1/1" for row in audit.checks)
