from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from technical.engine import TechnicalSettings, TechnicalSnapshot, analyse_technical
from technical.market_structure import RiskRead, TrendQuality, assess_risk, assess_trend_quality


@dataclass(frozen=True)
class TechnicalAssessment:
    """The structured, mandatory read the workspace shows instead of a bare
    "bullish"/"bearish" label: current assessment, the evidence behind it, the risk,
    what would invalidate it, and a confidence score broken into its components."""

    current_assessment: str
    direction: str
    supporting_evidence: tuple[str, ...]
    risk: str
    invalidation: str
    invalidation_price: float | None
    confidence: int
    confidence_components: dict[str, int]
    trend_quality: TrendQuality
    risk_read: RiskRead
    snapshot: TechnicalSnapshot


def classify_direction(trend_quality: TrendQuality) -> str:
    aligned_up = trend_quality.swing_structure.sequence == "HIGHER HIGHS / HIGHER LOWS"
    aligned_down = trend_quality.swing_structure.sequence == "LOWER HIGHS / LOWER LOWS"
    if aligned_up and trend_quality.ma_alignment == "BULLISH STACK":
        return "UPTREND"
    if aligned_down and trend_quality.ma_alignment == "BEARISH STACK":
        return "DOWNTREND"
    if trend_quality.ma_alignment == "BULLISH STACK":
        return "UPTREND (EARLY / NOT YET CONFIRMED BY SWING STRUCTURE)"
    if trend_quality.ma_alignment == "BEARISH STACK":
        return "DOWNTREND (EARLY / NOT YET CONFIRMED BY SWING STRUCTURE)"
    return "RANGE-BOUND / NO CLEAR DIRECTION"


def build_technical_assessment(ticker: str, frame: pd.DataFrame, settings: TechnicalSettings) -> TechnicalAssessment:
    snapshot = analyse_technical(ticker, frame, settings)
    trend_quality = assess_trend_quality(frame, settings)
    direction = classify_direction(trend_quality)

    invalidation_price: float | None = None
    if direction.startswith("UPTREND"):
        invalidation_price = snapshot.support_high or snapshot.support_low
    elif direction.startswith("DOWNTREND"):
        invalidation_price = snapshot.resistance_low or snapshot.resistance_high

    risk_read = assess_risk(frame, invalidation_price)

    evidence: list[str] = [
        f"Swing structure: {trend_quality.swing_structure.sequence.lower()} ({trend_quality.swing_structure.swing_count} recent swings)",
        f"Moving-average alignment: {trend_quality.ma_alignment.lower()}",
    ]
    if snapshot.state != "No active level event":
        evidence.append(f"Latest level event: {snapshot.state.lower()}")
    if snapshot.rsi is not None:
        evidence.append(f"RSI at {snapshot.rsi:.1f}")
    for setup in snapshot.setups:
        if "divergence" in setup.lower() or "volume" in setup.lower():
            evidence.append(setup)

    if direction.startswith("UPTREND"):
        current_assessment = f"{ticker} is in a {trend_quality.label.lower()}-quality uptrend."
        risk_text = f"Volatility is {risk_read.volatility_regime.lower()} (ATR {risk_read.atr_pct:.2f}% of price)."
        invalidation_text = (
            f"A daily close below {invalidation_price:.2f} would break the current higher-lows structure and invalidate this uptrend read."
            if invalidation_price
            else "No confirmed support level to anchor an invalidation price yet — treat any close back below the most recent swing low as a warning."
        )
    elif direction.startswith("DOWNTREND"):
        current_assessment = f"{ticker} is in a {trend_quality.label.lower()}-quality downtrend."
        risk_text = f"Volatility is {risk_read.volatility_regime.lower()} (ATR {risk_read.atr_pct:.2f}% of price)."
        invalidation_text = (
            f"A daily close above {invalidation_price:.2f} would break the current lower-highs structure and invalidate this downtrend read."
            if invalidation_price
            else "No confirmed resistance level to anchor an invalidation price yet — treat any close back above the most recent swing high as a warning."
        )
    else:
        current_assessment = f"{ticker} is range-bound and lacks a clean directional trend right now."
        risk_text = f"Volatility is {risk_read.volatility_regime.lower()} (ATR {risk_read.atr_pct:.2f}% of price); ranges carry false-breakout risk in both directions."
        invalidation_text = "A confirmed break of either the nearest support or resistance zone would end the current range and set the next direction."

    confidence_components = {
        "trend_quality": trend_quality.score,
        "level_confluence": 70 if (snapshot.support_low or snapshot.resistance_low) else 30,
        "risk_alignment": 40 if risk_read.level == "ELEVATED" else 70,
    }
    confidence = int(round(sum(confidence_components.values()) / len(confidence_components)))

    return TechnicalAssessment(
        current_assessment=current_assessment,
        direction=direction,
        supporting_evidence=tuple(dict.fromkeys(evidence)),
        risk=risk_text,
        invalidation=invalidation_text,
        invalidation_price=invalidation_price,
        confidence=confidence,
        confidence_components=confidence_components,
        trend_quality=trend_quality,
        risk_read=risk_read,
        snapshot=snapshot,
    )


def derive_key_trigger(assessment: TechnicalAssessment, patterns: list[dict]) -> str:
    """The single next price level that would confirm the featured setup —
    shared by the Research page executive summary and the Opportunities
    cards so both surfaces describe the same trigger the same way."""
    snapshot = assessment.snapshot
    top_pattern = patterns[0] if patterns else None
    if top_pattern is not None and top_pattern.get("trigger") is not None:
        direction_word = "above" if top_pattern["direction"] == "BULLISH" else "below"
        return f"Break {direction_word} {top_pattern['trigger']:,.2f}"
    if snapshot.resistance_low is not None:
        return f"Break above {snapshot.resistance_low:,.2f}"
    if snapshot.support_low is not None:
        return f"Break below {snapshot.support_low:,.2f}"
    return "No defined level yet"
