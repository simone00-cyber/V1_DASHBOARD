import pandas as pd
import pytest

from caruso_analysis import prepare_technical_prices, resample_ohlc
from analysis.signals.engine import build_documented_signal_history


def test_prepare_technical_prices_adjusts_ohlc_and_preserves_market_prices():
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    raw = pd.DataFrame(
        {
            "Open": [100.0, 98.0, 96.0],
            "High": [102.0, 100.0, 98.0],
            "Low": [99.0, 97.0, 95.0],
            "Close": [101.0, 99.0, 97.0],
            "Adj Close": [90.9, 89.1, 87.3],
            "TotalReturnClose": [90.9, 89.1, 87.3],
            "Volume": [10, 20, 30],
        },
        index=index,
    )

    adjusted = prepare_technical_prices(raw)

    assert adjusted["MarketClose"].tolist() == [101.0, 99.0, 97.0]
    assert adjusted["Close"].tolist() == pytest.approx([90.9, 89.1, 87.3])
    assert adjusted["Open"].tolist() == pytest.approx([90.0, 88.2, 86.4])
    assert adjusted["TotalReturnClose"].tolist() == pytest.approx([90.9, 89.1, 87.3])


def test_resample_preserves_adjusted_and_market_close_series():
    index = pd.date_range("2024-01-01", periods=7, freq="D")
    raw = pd.DataFrame(
        {
            "Open": range(100, 107),
            "High": range(101, 108),
            "Low": range(99, 106),
            "Close": range(100, 107),
            "Adj Close": [x * 0.9 for x in range(100, 107)],
            "TotalReturnClose": [x * 0.9 for x in range(100, 107)],
            "Volume": [1] * 7,
        },
        index=index,
    )

    weekly = resample_ohlc(prepare_technical_prices(raw), "W-FRI", completed_periods_only=False)

    assert "MarketClose" in weekly.columns
    assert "TotalReturnClose" in weekly.columns
    assert weekly.iloc[0]["MarketClose"] == 104
    assert weekly.iloc[0]["Close"] == pytest.approx(93.6)
