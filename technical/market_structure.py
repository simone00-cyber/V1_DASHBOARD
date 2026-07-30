from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from technical.engine import TechnicalSettings, TechnicalSnapshot, _swing_points, calculate_atr


@dataclass(frozen=True)
class SwingStructure:
    sequence: str
    higher_highs: int
    higher_lows: int
    lower_highs: int
    lower_lows: int
    swing_count: int


def classify_swing_structure(frame: pd.DataFrame, settings: TechnicalSettings, lookback_swings: int = 4) -> SwingStructure:
    """Classify the most recent swing sequence as HH/HL, LH/LL, or mixed/transitional."""
    highs = _swing_points(frame["High"], settings.swing_window, "high").tail(lookback_swings)
    lows = _swing_points(frame["Low"], settings.swing_window, "low").tail(lookback_swings)
    higher_highs = int((highs.diff() > 0).sum()) if len(highs) > 1 else 0
    lower_highs = int((highs.diff() < 0).sum()) if len(highs) > 1 else 0
    higher_lows = int((lows.diff() > 0).sum()) if len(lows) > 1 else 0
    lower_lows = int((lows.diff() < 0).sum()) if len(lows) > 1 else 0

    up_votes = higher_highs + higher_lows
    down_votes = lower_highs + lower_lows
    if up_votes >= 2 and up_votes > down_votes:
        sequence = "HIGHER HIGHS / HIGHER LOWS"
    elif down_votes >= 2 and down_votes > up_votes:
        sequence = "LOWER HIGHS / LOWER LOWS"
    else:
        sequence = "MIXED / TRANSITIONAL"

    return SwingStructure(
        sequence=sequence,
        higher_highs=higher_highs,
        higher_lows=higher_lows,
        lower_highs=lower_highs,
        lower_lows=lower_lows,
        swing_count=len(highs) + len(lows),
    )


def _linear_fit_r2(values: pd.Series) -> float:
    arr = values.dropna().astype(float).to_numpy()
    if len(arr) < 3:
        return 0.0
    x = np.arange(len(arr), dtype=float)
    slope, intercept = np.polyfit(x, arr, 1)
    fitted = slope * x + intercept
    ss_res = float(np.sum((arr - fitted) ** 2))
    ss_tot = float(np.sum((arr - arr.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot else 1.0


def _ma_alignment(frame: pd.DataFrame, periods: tuple[int, ...]) -> tuple[str, float]:
    """Checks whether price and moving averages are stacked in trend order
    (price > fast MA > ... > slow MA for an uptrend, or the mirror for a downtrend)."""
    if len(periods) < 2:
        return "INSUFFICIENT MA CONFIG", 0.0
    ordered = sorted(periods)
    close = frame["Close"]
    values = [float(close.iloc[-1])]
    for period in ordered:
        ma = close.rolling(period, min_periods=period).mean()
        if ma.dropna().empty:
            return "INSUFFICIENT HISTORY", 0.0
        values.append(float(ma.iloc[-1]))
    pairs = list(zip(values, values[1:]))
    bullish_pairs = sum(1 for a, b in pairs if a >= b)
    bearish_pairs = sum(1 for a, b in pairs if a <= b)
    if bullish_pairs == len(pairs):
        return "BULLISH STACK", 100.0
    if bearish_pairs == len(pairs):
        return "BEARISH STACK", 100.0
    fraction = max(bullish_pairs, bearish_pairs) / len(pairs)
    return "MIXED", float(np.clip((fraction - 0.5) * 200.0, 0.0, 100.0))


@dataclass(frozen=True)
class TrendQuality:
    score: int
    label: str
    ma_alignment: str
    swing_structure: SwingStructure
    components: dict[str, float]


def assess_trend_quality(frame: pd.DataFrame, settings: TechnicalSettings) -> TrendQuality:
    """Blends moving-average stacking, swing-sequence consistency and how cleanly
    price fits a straight line into a single 0-100 trend-quality read. This measures
    the QUALITY of the trend (is it clean and persistent, or choppy and uncertain),
    not its direction."""
    swing = classify_swing_structure(frame, settings)
    total_votes = swing.higher_highs + swing.higher_lows + swing.lower_highs + swing.lower_lows
    consistency = 0.0
    if total_votes:
        consistency = max(swing.higher_highs + swing.higher_lows, swing.lower_highs + swing.lower_lows) / total_votes * 100.0

    ma_label, ma_strength = _ma_alignment(frame, settings.ma_periods)

    window = frame["Close"].tail(max(60, settings.swing_window * 12))
    fit_quality = _linear_fit_r2(window) * 100.0 if len(window.dropna()) >= 10 else 0.0

    score = float(np.clip(0.4 * ma_strength + 0.35 * consistency + 0.25 * fit_quality, 0, 100))
    if score >= 70:
        label = "STRONG"
    elif score >= 45:
        label = "MODERATE"
    elif score >= 20:
        label = "WEAK"
    else:
        label = "NO CLEAR TREND"

    return TrendQuality(
        score=int(round(score)),
        label=label,
        ma_alignment=ma_label,
        swing_structure=swing,
        components={
            "ma_alignment": round(ma_strength, 1),
            "swing_consistency": round(consistency, 1),
            "linear_fit": round(fit_quality, 1),
        },
    )


def classify_volatility_regime(frame: pd.DataFrame, period: int = 14, lookback: int = 252) -> tuple[str, float | None, float]:
    """Volatility regime via percentile rank of rolling ATR% over the lookback window.
    Returns (regime, percentile, current ATR%)."""
    atr = calculate_atr(frame, period)
    atr_pct = (atr / frame["Close"]) * 100.0
    clean = atr_pct.dropna()
    if clean.empty:
        return "UNKNOWN", None, float("nan")
    current = float(clean.iloc[-1])
    recent = clean.tail(lookback)
    if len(recent) < period * 2:
        return "UNKNOWN", None, current
    percentile = float((recent <= current).mean() * 100.0)
    if percentile <= 25:
        regime = "CONTRACTING"
    elif percentile >= 75:
        regime = "EXPANDING"
    else:
        regime = "NORMAL"
    return regime, percentile, current


@dataclass(frozen=True)
class RiskRead:
    level: str
    atr_pct: float
    volatility_regime: str
    volatility_percentile: float | None
    distance_to_invalidation_pct: float | None


def assess_risk(frame: pd.DataFrame, invalidation: float | None, period: int = 14) -> RiskRead:
    """Risk level from realised volatility (ATR%) plus how close price already sits
    to the nearest invalidation level — the same volatility regime and distance the
    Market Structure and Developing Patterns panels reference elsewhere."""
    regime, percentile, atr_pct = classify_volatility_regime(frame, period)
    last_close = float(frame["Close"].dropna().iloc[-1])
    distance = abs(last_close / invalidation - 1.0) * 100.0 if invalidation else None

    level = "MODERATE"
    if regime == "EXPANDING" or (distance is not None and distance < 2.0):
        level = "ELEVATED"
    elif regime == "CONTRACTING" and (distance is None or distance > 5.0):
        level = "LOW"

    return RiskRead(
        level=level,
        atr_pct=round(atr_pct, 2) if pd.notna(atr_pct) else float("nan"),
        volatility_regime=regime,
        volatility_percentile=round(percentile, 1) if percentile is not None else None,
        distance_to_invalidation_pct=round(distance, 2) if distance is not None else None,
    )


@dataclass(frozen=True)
class StructureRatings:
    """Five 0-100 scores for the star-rating summary row: Trend, Momentum, Structure,
    Volatility and Risk. Each is a direct re-expression of an already-computed read
    (trend_quality.score, RSI distance from neutral, the volatility regime, the risk
    level) — no new indicator, just a compact visual scale over existing numbers."""

    trend: int
    momentum: int
    structure: int
    volatility: int
    risk: int


_VOLATILITY_SCORE = {"CONTRACTING": 80, "NORMAL": 55, "EXPANDING": 25, "UNKNOWN": 50}
_RISK_SCORE = {"LOW": 85, "MODERATE": 55, "ELEVATED": 25}


def build_structure_ratings(trend_quality: TrendQuality, risk_read: RiskRead, snapshot: TechnicalSnapshot) -> StructureRatings:
    if snapshot.rsi is None:
        momentum = 50.0
    else:
        momentum = float(np.clip(abs(snapshot.rsi - 50.0) * 2.0, 0.0, 100.0))
    has_divergence = any("divergence" in setup.lower() for setup in snapshot.setups)
    if has_divergence:
        momentum = max(0.0, momentum - 25.0)

    return StructureRatings(
        trend=int(round(trend_quality.score)),
        momentum=int(round(momentum)),
        structure=int(round(trend_quality.components.get("swing_consistency", 50.0))),
        volatility=int(round(_VOLATILITY_SCORE.get(risk_read.volatility_regime, 50))),
        risk=int(round(_RISK_SCORE.get(risk_read.level, 50))),
    )
