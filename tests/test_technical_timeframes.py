import numpy as np
import pandas as pd

from technical.engine import TechnicalSettings, calculate_rsi, resample_technical_frame


def _frame(periods: int = 120) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=periods, freq="B")
    close = pd.Series(np.linspace(100.0, 130.0, periods), index=index)
    return pd.DataFrame({
        "Open": close - 0.5,
        "High": close + 1.0,
        "Low": close - 1.0,
        "Close": close,
        "Volume": 1000,
    })


def test_resample_technical_frame_supports_all_timeframes():
    frame = _frame()
    daily = resample_technical_frame(frame, "DAILY")
    weekly = resample_technical_frame(frame, "WEEKLY")
    monthly = resample_technical_frame(frame, "MONTHLY")
    assert len(daily) == len(frame)
    assert 20 <= len(weekly) <= 26
    assert 5 <= len(monthly) <= 7
    assert list(weekly.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_rsi_can_be_aligned_to_the_exact_chart_index():
    display = resample_technical_frame(_frame(), "WEEKLY").tail(18)
    rsi = calculate_rsi(display["Close"], 5).reindex(display.index)
    assert rsi.index.equals(display.index)
    assert len(rsi) == len(display)


def test_settings_store_selected_timeframe():
    settings = TechnicalSettings(timeframe="MONTHLY")
    assert settings.timeframe == "MONTHLY"
