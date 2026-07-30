"""Overall Fundamental Rating and Buy/Hold/Sell.

The overall score is the unweighted mean of whichever quality axes could be
computed (missing axes are excluded, never treated as zero). The
recommendation is one small, fully-documented lookup over (rating band,
valuation band) — the same rhetorical style as `caruso_analysis.STRATEGY_MATRIX`
and `screener/opportunities.py::classify_conviction`: entirely inspectable,
no hidden weighting.
"""

from __future__ import annotations

from fundamentals import config
from fundamentals.models import FundamentalRating, QualityScores, ValuationEstimate


def classify_rating_band(overall_score: int | None) -> str:
    if overall_score is None:
        return "Insufficient Data"
    if overall_score >= config.RATING_BAND_EXCELLENT:
        return "Excellent"
    if overall_score >= config.RATING_BAND_GOOD:
        return "Good"
    if overall_score >= config.RATING_BAND_FAIR:
        return "Fair"
    if overall_score >= config.RATING_BAND_WEAK:
        return "Weak"
    return "Poor"


def classify_valuation_band(margin_of_safety: float | None) -> str:
    if margin_of_safety is None:
        return "Insufficient Data"
    if margin_of_safety >= config.MARGIN_OF_SAFETY_UNDERVALUED:
        return "Undervalued"
    if margin_of_safety <= config.MARGIN_OF_SAFETY_OVERVALUED:
        return "Overvalued"
    return "Fairly Valued"


def classify_recommendation(rating_band: str, valuation_band: str) -> str:
    """Documented rule, in priority order:

    1. Either band unavailable                                    -> INSUFFICIENT DATA
    2. Quality Excellent/Good AND not Overvalued                  -> BUY
    3. Quality Weak/Poor, OR (Overvalued AND quality <= Fair)      -> SELL
    4. Everything else                                            -> HOLD
    """
    if rating_band == "Insufficient Data" or valuation_band == "Insufficient Data":
        return "INSUFFICIENT DATA"

    strong_quality = rating_band in {"Excellent", "Good"}
    weak_quality = rating_band in {"Weak", "Poor"}

    if strong_quality and valuation_band != "Overvalued":
        return "BUY"
    if weak_quality or (valuation_band == "Overvalued" and rating_band in {"Fair", "Weak", "Poor"}):
        return "SELL"
    return "HOLD"


def build_fundamental_rating(quality: QualityScores, valuation: ValuationEstimate) -> FundamentalRating:
    available = quality.available_scores
    overall_score = round(sum(available) / len(available)) if available else None
    rating_band = classify_rating_band(overall_score)
    recommendation = classify_recommendation(rating_band, valuation.valuation_band)
    return FundamentalRating(
        overall_score=overall_score,
        rating_band=rating_band,
        recommendation=recommendation,
    )
