from __future__ import annotations

import pytest

from fundamentals import config
from fundamentals.rating import classify_rating_band, classify_recommendation, classify_valuation_band


def test_classify_rating_band_boundaries():
    assert classify_rating_band(None) == "Insufficient Data"
    assert classify_rating_band(config.RATING_BAND_EXCELLENT) == "Excellent"
    assert classify_rating_band(config.RATING_BAND_GOOD) == "Good"
    assert classify_rating_band(config.RATING_BAND_FAIR) == "Fair"
    assert classify_rating_band(config.RATING_BAND_WEAK) == "Weak"
    assert classify_rating_band(config.RATING_BAND_WEAK - 1) == "Poor"


def test_classify_valuation_band_boundaries():
    assert classify_valuation_band(None) == "Insufficient Data"
    assert classify_valuation_band(config.MARGIN_OF_SAFETY_UNDERVALUED) == "Undervalued"
    assert classify_valuation_band(config.MARGIN_OF_SAFETY_OVERVALUED) == "Overvalued"
    assert classify_valuation_band(0.0) == "Fairly Valued"


@pytest.mark.parametrize(
    "rating_band,valuation_band,expected",
    [
        ("Insufficient Data", "Undervalued", "INSUFFICIENT DATA"),
        ("Excellent", "Insufficient Data", "INSUFFICIENT DATA"),
        ("Excellent", "Undervalued", "BUY"),
        ("Excellent", "Fairly Valued", "BUY"),
        ("Excellent", "Overvalued", "HOLD"),
        ("Good", "Undervalued", "BUY"),
        ("Good", "Fairly Valued", "BUY"),
        ("Good", "Overvalued", "HOLD"),
        ("Fair", "Undervalued", "HOLD"),
        ("Fair", "Fairly Valued", "HOLD"),
        ("Fair", "Overvalued", "SELL"),
        ("Weak", "Undervalued", "SELL"),
        ("Weak", "Fairly Valued", "SELL"),
        ("Weak", "Overvalued", "SELL"),
        ("Poor", "Undervalued", "SELL"),
        ("Poor", "Fairly Valued", "SELL"),
        ("Poor", "Overvalued", "SELL"),
    ],
)
def test_classify_recommendation_full_truth_table(rating_band, valuation_band, expected):
    assert classify_recommendation(rating_band, valuation_band) == expected
