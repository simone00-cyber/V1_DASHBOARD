"""Backtest of the public cyclical matrix with explicit execution policies."""
from __future__ import annotations
from typing import Dict
import pandas as pd

from analysis.audit import build_execution_audit
from analysis.backtest.diagnostics import build_trade_diagnostics
from analysis.backtest.metrics import calculate_metrics
from analysis.backtest.models import BacktestResult
from analysis.execution import ExecutionPolicy, build_policy_trace
from analysis.signals.engine import build_documented_signal_history
from analysis.matrix import build_matrix_timeline, matrix_timeline_frame
from analysis.trades.execution import run_trade_engine


def _position_series(index: pd.DatetimeIndex, signals, policy: ExecutionPolicy) -> pd.Series:
    position = pd.Series(0.0, index=index)
    transition_by_date = {row.date: row for row in build_policy_trace(signals, policy)}
    current = 0.0
    for date in index:
        transition = transition_by_date.get(pd.Timestamp(date))
        if transition is not None:
            current = transition.exposure_after
        position.loc[date] = current
    return position


def run_documented_backtest(frames: Dict[str, pd.DataFrame], mode: str = "LONG_ONLY",
                            cost_bps: float = 0.0,
                            close_open_trade: bool = True,
                            take_profit_policy: str = "SIGNAL_ONLY",
                            partial_exit_fraction: float = 0.50) -> BacktestResult:
    if "WEEKLY" not in frames:
        raise ValueError("WEEKLY timeframe required")
    weekly = frames["WEEKLY"].dropna(subset=["Close", "Composite"]).copy()
    valuation_column = "TotalReturnClose" if "TotalReturnClose" in weekly.columns else "Close"
    weekly = weekly.dropna(subset=[valuation_column])
    if len(weekly) < 3:
        raise ValueError("Insufficient weekly history")

    policy = ExecutionPolicy(
        direction_mode=mode,
        take_profit_policy=take_profit_policy,
        partial_exit_fraction=partial_exit_fraction,
    )
    matrix_timeline = matrix_timeline_frame(build_matrix_timeline(frames))
    signals = build_documented_signal_history(frames)
    position = _position_series(weekly.index, signals, policy)
    asset_return = weekly[valuation_column].pct_change().fillna(0.0)
    strategy_return = position.shift(1).fillna(0.0) * asset_return
    turnover = position.diff().abs().fillna(position.abs())
    strategy_return = strategy_return - turnover.shift(1).fillna(0.0) * cost_bps / 10000.0

    result_columns = ["Close", "Composite"]
    for column in ("MarketClose", valuation_column):
        if column in weekly.columns and column not in result_columns:
            result_columns.append(column)
    result_frame = weekly[result_columns].copy()
    result_frame["ValuationPrice"] = weekly[valuation_column]
    result_frame["Position"] = position
    result_frame["AssetReturn"] = asset_return
    result_frame["StrategyReturn"] = strategy_return
    result_frame["Equity"] = (1.0 + strategy_return).cumprod()
    result_frame["BenchmarkEquity"] = (1.0 + asset_return).cumprod()
    result_frame["Drawdown"] = result_frame["Equity"] / result_frame["Equity"].cummax() - 1.0

    trades = run_trade_engine(
        signals, weekly.index, mode, cost_bps, close_open_trade,
        float(weekly["MarketClose"].iloc[-1] if "MarketClose" in weekly.columns else weekly["Close"].iloc[-1]), take_profit_policy,
        partial_exit_fraction, valuation_prices=weekly[valuation_column],
    )
    metrics = calculate_metrics(result_frame, trades)
    diagnostics = build_trade_diagnostics(trades)
    audit = build_execution_audit(signals, trades, result_frame, policy)
    return BacktestResult(
        tuple(signals), tuple(trades), result_frame, metrics, diagnostics,
        mode, cost_bps, audit, take_profit_policy, partial_exit_fraction,
        policy.label, policy.provenance, matrix_timeline,
    )
