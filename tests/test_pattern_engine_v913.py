import numpy as np
import pandas as pd

from technical.engine import TechnicalSettings, analyse_technical, detect_pattern_details


def _ohlc(close: np.ndarray) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(close), freq="B")
    close_s = pd.Series(close, index=idx)
    return pd.DataFrame({
        "Open": close_s.shift(1).fillna(close_s.iloc[0]),
        "High": close_s + 1.0,
        "Low": close_s - 1.0,
        "Close": close_s,
        "Volume": 1000,
    }, index=idx)


def test_pattern_details_have_confidence_and_lifecycle():
    x = np.arange(180)
    close = 100 + 0.04 * x + 5 * np.sin(x / 8)
    details = detect_pattern_details(_ohlc(close), TechnicalSettings(swing_window=3, pattern_tolerance_pct=5))
    for detail in details:
        assert 0 <= detail["confidence"] <= 100
        assert detail["status"] in {"DEVELOPING", "CONFIRMED", "RETESTED"}
        assert detail["category"]
        assert detail["direction"]


def test_snapshot_exposes_dynamic_level_diagnostics():
    x = np.arange(420)
    close = 100 + np.sin(x / 10) * 6 + x * 0.02
    snap = analyse_technical("TEST", _ohlc(close), TechnicalSettings(swing_window=4))
    for group in ("supports", "resistances"):
        for zone in snap.diagnostics[group]:
            assert zone["role"] in {"SUPPORT", "RESISTANCE"}
            assert zone["state"] in {"ACTIVE", "BROKEN", "FLIPPED", "FAILED FLIP"}
            assert 0 <= zone["strength"] <= 100
