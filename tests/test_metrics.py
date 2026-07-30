import numpy as np
import pandas as pd

from core.metrics import normalized_frame, ratio_series, safe_pct_change


def test_safe_pct_change_short_series_returns_nan():
    data = pd.Series([100.0])
    assert np.isnan(safe_pct_change(data, 1))


def test_normalized_frame_base_100():
    frame = pd.DataFrame({"A": [10.0, 11.0], "B": [20.0, 18.0]})
    result = normalized_frame(frame)
    assert result.iloc[0].tolist() == [100.0, 100.0]


def test_ratio_series_handles_columns():
    frame = pd.DataFrame({"A": [2.0, 4.0], "B": [1.0, 2.0]})
    ratio = ratio_series(frame, "A", "B")
    assert ratio.tolist() == [2.0, 2.0]
