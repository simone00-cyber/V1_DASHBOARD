import pandas as pd
import numpy as np
from analysis.signals.engine import build_documented_signal_history
from analysis.trades.execution import run_trade_engine
from analysis.backtest.engine import run_documented_backtest


def _frame(index, composite, close=None, total_return_close=None):
    close = close if close is not None else np.linspace(100, 120, len(index))
    frame = pd.DataFrame({
        "Open": close, "High": np.asarray(close) + 1, "Low": np.asarray(close) - 1,
        "Close": close, "Volume": 1000, "Composite": composite,
    }, index=pd.DatetimeIndex(index))
    if total_return_close is not None:
        frame["TotalReturnClose"] = total_return_close
    return frame


def synthetic_frames():
    weekly_idx = pd.date_range("2020-01-03", periods=14, freq="W-FRI")
    # Turns: up at bar 3, down at bar 6, up at bar 9, down at bar 12.
    weekly_cm = [-30, -25, -28, -20, -10, 0, -5, -15, -20, -12, -2, 8, 4, -4]
    weekly_close = [100, 101, 100, 103, 106, 108, 105, 102, 101, 104, 108, 111, 109, 106]
    monthly_idx = pd.to_datetime(["2019-12-31", "2020-01-31", "2020-02-29", "2020-03-31"])
    quarterly_idx = pd.to_datetime(["2019-09-30", "2019-12-31", "2020-03-31"])
    return {
        "WEEKLY": _frame(weekly_idx, weekly_cm, weekly_close),
        "MONTHLY": _frame(monthly_idx, [0, 10, 20, 30], [90, 95, 100, 105]),
        "QUARTERLY": _frame(quarterly_idx, [0, 10, 20], [80, 90, 100]),
    }


def test_signal_history_uses_public_matrix():
    signals = build_documented_signal_history(synthetic_frames())
    assert any(signal.action == "BUY" for signal in signals)
    assert any(signal.action == "SELL SHORT" for signal in signals)
    assert all(signal.price > 0 for signal in signals)


def test_long_only_trade_engine_closes_on_sell_short():
    frames = synthetic_frames()
    signals = build_documented_signal_history(frames)
    trades = run_trade_engine(signals, frames["WEEKLY"].index, mode="LONG_ONLY")
    assert trades
    assert all(trade.side == "LONG" for trade in trades)
    assert trades[0].exit_reason in {"SELL SHORT", "TAKE PROFIT", "END OF TEST"}


def test_backtest_position_is_lagged_and_metrics_exist():
    result = run_documented_backtest(synthetic_frames(), mode="LONG_ONLY", cost_bps=5)
    assert "Equity" in result.weekly
    assert "Max Drawdown" in result.metrics
    first_signal_date = result.signals[0].date
    loc = result.weekly.index.get_loc(first_signal_date)
    if loc > 0:
        # Return on the signal bar was earned with the prior position.
        expected = result.weekly["Position"].shift(1).fillna(0).iloc[loc] * result.weekly["AssetReturn"].iloc[loc]
        turnover_cost = result.weekly["Position"].diff().abs().fillna(result.weekly["Position"].abs()).shift(1).fillna(0).iloc[loc] * 5 / 10000
        assert result.weekly["StrategyReturn"].iloc[loc] == expected - turnover_cost


def test_long_short_can_open_short_positions():
    result = run_documented_backtest(synthetic_frames(), mode="LONG_SHORT")
    assert (result.weekly["Position"] == -1).any()


def test_backtest_uses_total_return_close_for_dividends():
    frames = synthetic_frames()
    weekly = frames["WEEKLY"].copy()
    # Simulate a cash dividend: raw price is unchanged while total-return value rises.
    total_return = weekly["Close"].astype(float).copy()
    total_return.iloc[4:] *= 1.05
    weekly["TotalReturnClose"] = total_return
    frames["WEEKLY"] = weekly
    result = run_documented_backtest(frames, mode="LONG_ONLY", cost_bps=0)
    expected = total_return.pct_change().fillna(0.0)
    pd.testing.assert_series_equal(result.weekly["AssetReturn"], expected, check_names=False)
    assert "ValuationPrice" in result.weekly.columns
    assert result.weekly["Close"].equals(weekly["Close"])
