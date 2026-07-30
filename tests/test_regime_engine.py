import numpy as np
import pandas as pd

from analysis.regime import build_market_regime


def synthetic_close(rows: int = 260) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-01", periods=rows)
    trend = np.linspace(100, 130, rows)
    return pd.DataFrame(
        {
            "SPY": trend,
            "QQQ": trend * 1.05,
            "ACWI": trend * 0.95,
            "^VIX": np.linspace(22, 16, rows),
            "DX-Y.NYB": np.linspace(105, 100, rows),
            "HYG": np.linspace(75, 82, rows),
            "LQD": np.linspace(105, 108, rows),
            "HG=F": np.linspace(4, 5, rows),
            "GC=F": np.linspace(2000, 2100, rows),
            "^IRX": np.linspace(5.0, 4.0, rows),
            "^TNX": np.linspace(4.5, 4.0, rows),
        },
        index=index,
    )


def test_build_market_regime_returns_three_layers():
    result = build_market_regime(synthetic_close())
    assert set(result) == {"STRATEGIC", "TACTICAL", "DAILY"}
    assert all(-2 <= layer.score <= 2 for layer in result.values())
    assert all(layer.coverage > 0.8 for layer in result.values())


def test_missing_data_does_not_crash():
    data = synthetic_close().drop(columns=["^VIX", "HG=F"])
    result = build_market_regime(data)
    assert result["TACTICAL"].coverage < 1.0
