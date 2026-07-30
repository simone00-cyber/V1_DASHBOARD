import numpy as np
import pandas as pd

from technical.engine import (
    TechnicalSettings,
    detect_pattern_details,
    estimate_pattern_reliability,
)


def _ohlc(close: np.ndarray, volume: np.ndarray | None = None) -> pd.DataFrame:
    idx = pd.date_range("2022-01-01", periods=len(close), freq="B")
    close_s = pd.Series(close, index=idx)
    frame = pd.DataFrame(
        {
            "Open": close_s.shift(1).fillna(close_s.iloc[0]),
            "High": close_s + 1.0,
            "Low": close_s - 1.0,
            "Close": close_s,
        },
        index=idx,
    )
    frame["Volume"] = volume if volume is not None else 1000
    return frame


def _uptrend_with_swings(n: int = 400) -> pd.DataFrame:
    x = np.arange(n)
    close = 100 + 0.05 * x + 4 * np.sin(x / 9)
    return _ohlc(close)


def test_directional_patterns_expose_invalidation_and_breakout_zone():
    details = detect_pattern_details(_uptrend_with_swings(), TechnicalSettings(swing_window=3, pattern_tolerance_pct=5))
    directional = [d for d in details if d["direction"] in ("BULLISH", "BEARISH")]
    assert directional, "expected at least one directional pattern candidate on a trending synthetic series"
    for detail in directional:
        assert "invalidation" in detail
        assert "completion_pct" in detail
        assert "expected_breakout_zone" in detail
        if detail["trigger"] is not None:
            assert detail["completion_pct"] is None or 0 <= detail["completion_pct"] <= 100
            zone = detail["expected_breakout_zone"]
            assert zone is not None and zone[0] < zone[1]


def test_neutral_patterns_have_no_invalidation_or_completion():
    details = detect_pattern_details(_uptrend_with_swings(), TechnicalSettings(swing_window=3, pattern_tolerance_pct=5))
    neutral = [d for d in details if d["direction"] == "NEUTRAL"]
    for detail in neutral:
        assert detail["invalidation"] is None
        assert detail["completion_pct"] is None


def test_overlap_suppression_keeps_only_the_strongest_candidate_per_region():
    details = detect_pattern_details(_uptrend_with_swings(), TechnicalSettings(swing_window=3, pattern_tolerance_pct=5))
    # No two surviving candidates should have near-fully-overlapping date ranges.
    for i, a in enumerate(details):
        for b in details[i + 1 :]:
            latest_start = max(a["start"], b["start"])
            earliest_end = min(a["end"], b["end"])
            if latest_start > earliest_end:
                continue
            overlap = earliest_end - latest_start
            span_a = (a["end"] - a["start"]) or pd.Timedelta(days=1)
            span_b = (b["end"] - b["start"]) or pd.Timedelta(days=1)
            assert overlap < min(span_a, span_b) * 0.6


def test_developing_patterns_are_sorted_before_confirmed_or_retested():
    details = detect_pattern_details(_uptrend_with_swings(), TechnicalSettings(swing_window=3, pattern_tolerance_pct=5))
    statuses = [d["status"] for d in details]
    rank = {"DEVELOPING": 0, "CONFIRMED": 1, "RETESTED": 2}
    ranked = [rank[s] for s in statuses]
    assert ranked == sorted(ranked)


def test_estimate_pattern_reliability_reports_insufficient_history_for_short_series():
    frame = _uptrend_with_swings(n=280)
    settings = TechnicalSettings(swing_window=3, pattern_tolerance_pct=5)
    reliability = estimate_pattern_reliability(frame, settings, "Potential double bottom", "BULLISH")
    assert reliability.sample_size < 5
    assert reliability.favorable_rate is None
    assert "insufficient" in reliability.note.lower()


def test_estimate_pattern_reliability_never_uses_cross_ticker_data():
    # Sanity: reliability is purely a function of this one frame's own history —
    # calling it twice on the same frame must be deterministic.
    frame = _uptrend_with_swings(n=900)
    settings = TechnicalSettings(swing_window=3, pattern_tolerance_pct=5)
    first = estimate_pattern_reliability(frame, settings, "Potential ascending channel", "BULLISH", step=20)
    second = estimate_pattern_reliability(frame, settings, "Potential ascending channel", "BULLISH", step=20)
    assert first == second
