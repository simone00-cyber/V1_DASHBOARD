from __future__ import annotations
import math
import numpy as np
import pandas as pd
from analysis.trades.models import Trade


def calculate_metrics(weekly: pd.DataFrame, trades: list[Trade]) -> dict:
    returns = weekly["StrategyReturn"].dropna()
    equity = weekly["Equity"].dropna()
    benchmark = weekly["BenchmarkEquity"].dropna()
    if equity.empty:
        return {}
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1 / 52)
    total = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    vol = float(returns.std(ddof=1) * math.sqrt(52)) if len(returns) > 1 else 0.0
    sharpe = float(returns.mean() / returns.std(ddof=1) * math.sqrt(52)) if len(returns) > 1 and returns.std(ddof=1) > 0 else 0.0
    dd = equity / equity.cummax() - 1.0
    benchmark_years = years
    benchmark_cagr = float(benchmark.iloc[-1] ** (1.0 / benchmark_years) - 1.0) if not benchmark.empty else np.nan
    net = np.array([t.net_return * getattr(t, "size", 1.0) for t in trades], dtype=float)
    gains = net[net > 0]
    losses = net[net < 0]
    profit_factor = float(gains.sum() / abs(losses.sum())) if len(losses) and abs(losses.sum()) > 0 else (float("inf") if len(gains) else 0.0)
    return {
        "Total Return": total,
        "CAGR": cagr,
        "Annualized Volatility": vol,
        "Sharpe (rf=0)": sharpe,
        "Max Drawdown": float(dd.min()),
        "Trades": int(len(trades)),
        "Win Rate": float((net > 0).mean()) if len(net) else 0.0,
        "Profit Factor": profit_factor,
        "Average Trade": float(net.mean()) if len(net) else 0.0,
        "Average Winner": float(gains.mean()) if len(gains) else 0.0,
        "Average Loser": float(losses.mean()) if len(losses) else 0.0,
        "Average Bars Held": float(np.mean([t.bars_held for t in trades])) if trades else 0.0,
        "Time Invested": float(weekly["Position"].abs().mean()),
        "Buy & Hold CAGR": benchmark_cagr,
    }
