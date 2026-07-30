from __future__ import annotations
from copy import deepcopy
from typing import Callable, Any
import numpy as np
import pandas as pd
from .technical_engine import run_technical_backtest, TechnicalTrade


def monte_carlo_trades(trades: list[TechnicalTrade], simulations: int = 1000, seed: int = 42, initial_equity: float = 1.0) -> dict[str, Any]:
    values = np.array([t.net_return for t in trades], dtype=float)
    if len(values) == 0:
        return {"paths": pd.DataFrame(), "summary": {}}
    rng = np.random.default_rng(seed)
    paths = np.empty((len(values) + 1, simulations))
    paths[0] = initial_equity
    max_dd = []
    finals = []
    for j in range(simulations):
        sample = rng.choice(values, size=len(values), replace=True)
        path = initial_equity * np.cumprod(np.r_[1.0, 1.0 + sample])
        paths[:, j] = path
        dd = path / np.maximum.accumulate(path) - 1
        max_dd.append(dd.min()); finals.append(path[-1])
    quantiles = pd.DataFrame({
        "p05": np.quantile(paths, 0.05, axis=1),
        "p25": np.quantile(paths, 0.25, axis=1),
        "median": np.quantile(paths, 0.50, axis=1),
        "p75": np.quantile(paths, 0.75, axis=1),
        "p95": np.quantile(paths, 0.95, axis=1),
    })
    summary = {
        "Median final equity": float(np.median(finals)),
        "Probability profitable": float(np.mean(np.array(finals) > initial_equity)),
        "Median max drawdown": float(np.median(max_dd)),
        "95% worst max drawdown": float(np.quantile(max_dd, 0.05)),
        "5% final equity": float(np.quantile(finals, 0.05)),
        "95% final equity": float(np.quantile(finals, 0.95)),
    }
    return {"paths": quantiles, "summary": summary}


def _set_path(spec: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    out = deepcopy(spec)
    target: Any = out
    parts = path.split(".")
    for part in parts[:-1]:
        target = target[int(part)] if part.isdigit() else target[part]
    last = parts[-1]
    if last.isdigit():
        target[int(last)] = value
    else:
        target[last] = value
    return out


def parameter_search(data: pd.DataFrame, base_spec: dict[str, Any], parameter_path: str, values: list[float], objective: str = "Sharpe") -> pd.DataFrame:
    rows = []
    for value in values:
        spec = _set_path(base_spec, parameter_path, value)
        result = run_technical_backtest(data, spec)
        row = {"Parameter": value, **result.metrics}
        rows.append(row)
    frame = pd.DataFrame(rows)
    if objective in frame.columns:
        frame = frame.sort_values(objective, ascending=False).reset_index(drop=True)
    return frame


def walk_forward_test(data: pd.DataFrame, specification: dict[str, Any], train_bars: int, test_bars: int) -> pd.DataFrame:
    rows = []
    start = 0; fold = 1
    while start + train_bars + test_bars <= len(data):
        train = data.iloc[start:start+train_bars]
        test = data.iloc[start+train_bars:start+train_bars+test_bars]
        train_result = run_technical_backtest(train, specification)
        test_result = run_technical_backtest(test, specification)
        rows.append({
            "Fold": fold, "Train Start": train.index[0], "Train End": train.index[-1],
            "Test Start": test.index[0], "Test End": test.index[-1],
            "IS CAGR": train_result.metrics.get("CAGR", 0.0), "IS Sharpe": train_result.metrics.get("Sharpe", 0.0),
            "OOS CAGR": test_result.metrics.get("CAGR", 0.0), "OOS Sharpe": test_result.metrics.get("Sharpe", 0.0),
            "OOS Max Drawdown": test_result.metrics.get("Max Drawdown", 0.0),
            "OOS Trades": test_result.metrics.get("Trades", 0.0),
        })
        start += test_bars; fold += 1
    return pd.DataFrame(rows)
