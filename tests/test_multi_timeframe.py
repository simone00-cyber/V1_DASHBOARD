import numpy as np
import pandas as pd

from technical.engine import TechnicalSettings
from technical.multi_timeframe import build_multi_timeframe_alignment


def _long_trending_frame(n: int = 900, slope: float = 0.05) -> pd.DataFrame:
    x = np.arange(n)
    close = 100 + slope * x + 3 * np.sin(x / 10)
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    close_s = pd.Series(close, index=idx)
    return pd.DataFrame(
        {
            "Open": close_s.shift(1).fillna(close_s.iloc[0]),
            "High": close_s + 1.0,
            "Low": close_s - 1.0,
            "Close": close_s,
            "Volume": 1000,
        },
        index=idx,
    )


def test_aligned_bullish_across_all_timeframes():
    frame = _long_trending_frame(slope=0.05)
    alignment = build_multi_timeframe_alignment(frame, TechnicalSettings())
    assert alignment.agreement == "ALIGNED BULLISH"
    assert {r.timeframe for r in alignment.reads} == {"DAILY", "WEEKLY", "MONTHLY"}


def test_dominant_timeframe_prefers_higher_timeframe_when_directional():
    frame = _long_trending_frame(slope=0.05)
    alignment = build_multi_timeframe_alignment(frame, TechnicalSettings())
    # Monthly is checked first in _TIMEFRAME_ORDER; with a clean multi-year uptrend it
    # should be directional and therefore dominate over Weekly/Daily.
    assert alignment.dominant_timeframe == "MONTHLY"


def test_insufficient_history_reports_gracefully():
    frame = _long_trending_frame(n=40)
    alignment = build_multi_timeframe_alignment(frame, TechnicalSettings())
    assert alignment.agreement in {"INSUFFICIENT DATA", "MOSTLY RANGE-BOUND"}


def test_summary_mentions_every_available_timeframe():
    frame = _long_trending_frame(slope=0.05)
    alignment = build_multi_timeframe_alignment(frame, TechnicalSettings())
    for read in alignment.reads:
        assert read.timeframe.title() in alignment.summary
