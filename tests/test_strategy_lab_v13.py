import numpy as np
import pandas as pd

from analysis.strategy_lab import run_technical_backtest, monte_carlo_trades, parameter_search, walk_forward_test


def sample_data(n=320):
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    close = pd.Series(100 + np.linspace(0, 35, n) + np.sin(np.arange(n) / 7) * 4, index=idx)
    return pd.DataFrame({
        "Open": close.shift(1).fillna(close.iloc[0]),
        "High": close + 1.5,
        "Low": close - 1.5,
        "Close": close,
        "Volume": 1_000_000 + np.arange(n) * 100,
    })


def spec():
    return {
        "entry_long": [{
            "enabled": True,
            "left": {"kind": "indicator", "name": "Close", "period": 1, "secondary": 26, "multiplier": 1},
            "operator": "crosses above",
            "right": {"kind": "indicator", "name": "SMA", "period": 20, "secondary": 26, "multiplier": 1},
            "persistence": 1,
        }],
        "entry_logic": "AND",
        "exit_long": [{
            "enabled": True,
            "left": {"kind": "indicator", "name": "Close", "period": 1, "secondary": 26, "multiplier": 1},
            "operator": "crosses below",
            "right": {"kind": "indicator", "name": "SMA", "period": 20, "secondary": 26, "multiplier": 1},
            "persistence": 1,
        }],
        "exit_logic": "OR",
        "allow_short": False,
        "execution": "Next open",
        "initial_capital": 100000,
        "position_fraction": 1,
        "commission_bps": 2,
        "slippage_bps": 2,
        "stop_loss_pct": 0,
        "take_profit_pct": 0,
        "trailing_stop_pct": 0,
        "max_bars": 0,
        "bars_per_year": 252,
        "close_open_trade": True,
    }


def test_technical_backtest_produces_reproducible_ledger():
    result = run_technical_backtest(sample_data(), spec())
    assert "Equity" in result.frame
    assert result.metrics["Trades"] > 0
    assert all(t.entry_reason for t in result.trades)
    assert all(t.exit_reason for t in result.trades)


def test_monte_carlo_and_walk_forward_outputs():
    data = sample_data()
    result = run_technical_backtest(data, spec())
    mc = monte_carlo_trades(result.trades, simulations=100)
    assert not mc["paths"].empty
    assert 0 <= mc["summary"]["Probability profitable"] <= 1
    wf = walk_forward_test(data, spec(), train_bars=160, test_bars=40)
    assert not wf.empty
    assert "OOS Sharpe" in wf


def test_parameter_search_changes_nested_period():
    out = parameter_search(sample_data(), spec(), "entry_long.0.right.period", [10, 20, 30], "Sharpe")
    assert set(out["Parameter"]) == {10, 20, 30}
    assert "Sharpe" in out
