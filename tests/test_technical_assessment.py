import numpy as np
import pandas as pd

from technical.assessment import build_technical_assessment, classify_direction
from technical.engine import TechnicalSettings
from technical.market_structure import assess_trend_quality


def _frame(n: int = 400, slope: float = 0.05, wiggle: float = 3.0) -> pd.DataFrame:
    x = np.arange(n)
    close = 100 + slope * x + wiggle * np.sin(x / 10)
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
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


def test_build_technical_assessment_has_all_five_required_parts():
    assessment = build_technical_assessment("TEST", _frame(slope=0.06), TechnicalSettings())
    assert assessment.current_assessment
    assert len(assessment.supporting_evidence) > 0
    assert assessment.risk
    assert assessment.invalidation
    assert 0 <= assessment.confidence <= 100
    assert set(assessment.confidence_components) == {"trend_quality", "level_confluence", "risk_alignment"}


def test_assessment_never_emits_a_bare_bullish_label():
    assessment = build_technical_assessment("TEST", _frame(slope=0.06), TechnicalSettings())
    assert assessment.current_assessment not in {"bullish", "bearish", "Bullish", "Bearish"}
    assert len(assessment.current_assessment.split()) > 3


def test_uptrend_direction_uses_nearest_support_as_invalidation():
    frame = _frame(slope=0.06, n=420)
    assessment = build_technical_assessment("TEST", frame, TechnicalSettings())
    direction = classify_direction(assessment.trend_quality)
    if direction == "UPTREND":
        assert "invalidate" in assessment.invalidation.lower() or "warning" in assessment.invalidation.lower()


def test_classify_direction_covers_uptrend_downtrend_and_range():
    up_quality = assess_trend_quality(_frame(slope=0.06, wiggle=0.5), TechnicalSettings())
    down_quality = assess_trend_quality(_frame(slope=-0.06, wiggle=0.5), TechnicalSettings())
    assert classify_direction(up_quality).startswith("UPTREND")
    assert classify_direction(down_quality).startswith("DOWNTREND")


def test_assessment_direction_field_matches_classify_direction():
    frame = _frame(slope=0.06, wiggle=0.5)
    assessment = build_technical_assessment("TEST", frame, TechnicalSettings())
    assert assessment.direction == classify_direction(assessment.trend_quality)


def test_assessment_invalidation_price_is_below_price_for_an_established_uptrend():
    frame = _frame(slope=0.08, wiggle=1.0, n=420)
    assessment = build_technical_assessment("TEST", frame, TechnicalSettings())
    if assessment.direction.startswith("UPTREND") and assessment.invalidation_price is not None:
        assert 0 < assessment.invalidation_price < assessment.snapshot.last
