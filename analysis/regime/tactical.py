from __future__ import annotations

from typing import List, Optional, Tuple

import pandas as pd

from config.settings import (
    TACTICAL_DETERIORATING_DELTA,
    TACTICAL_IMPROVING_DELTA,
    TACTICAL_WEIGHTS,
)
from .common import (
    clip_score,
    count_available,
    ratio_return,
    return_pct,
    safe_mean,
    series,
    state_5,
    weighted_score,
    yield_change_bps,
)
from .models import RegimePillar


def momentum_acceleration(close: pd.DataFrame, ticker: str, recent: int = 21) -> Optional[float]:
    data = series(close, ticker)
    if len(data) <= recent * 2:
        return None
    current = (data.iloc[-1] / data.iloc[-1 - recent] - 1.0) * 100.0
    previous = (data.iloc[-1 - recent] / data.iloc[-1 - recent * 2] - 1.0) * 100.0
    return float(current - previous)


def tactical_equity(close: pd.DataFrame) -> RegimePillar:
    spy_1m = return_pct(close, "SPY", 21)
    qqq_1m = return_pct(close, "QQQ", 21)
    acwi_1m = return_pct(close, "ACWI", 21)
    acceleration = momentum_acceleration(close, "SPY", 21)
    breadth = safe_mean([spy_1m, qqq_1m, acwi_1m])

    score = 0.0
    score += 0.75 if breadth > 2 else -0.75 if breadth < -2 else breadth / 4.0
    score += 0.65 if (acceleration or 0) > 1.5 else -0.65 if (acceleration or 0) < -1.5 else 0.0
    returns = [v for v in (spy_1m, qqq_1m, acwi_1m) if v is not None]
    if returns and all(v > 0 for v in returns):
        score += 0.30
    elif returns and all(v < 0 for v in returns):
        score -= 0.30
    score = clip_score(score)

    values = (spy_1m, qqq_1m, acwi_1m, acceleration)
    details = (
        f"SPY 1M {spy_1m:+.2f}% | QQQ {qqq_1m:+.2f}% | ACWI {acwi_1m:+.2f}% | accelerazione {acceleration:+.2f} pp"
        if None not in values
        else "Dati equity tattici parziali"
    )
    return RegimePillar("EQUITY", score, state_5(score), details, count_available(*values), 4)


def tactical_volatility(close: pd.DataFrame) -> RegimePillar:
    vix = series(close, "^VIX")
    level = float(vix.iloc[-1]) if not vix.empty else None
    one_month = return_pct(close, "^VIX", 21)
    one_week = return_pct(close, "^VIX", 5)

    score = 0.0
    if level is not None:
        score += 0.50 if level < 18 else -0.50 if level > 23 else 0.0
    if one_month is not None:
        score += 0.75 if one_month < -10 else -0.75 if one_month > 15 else -0.20 if one_month > 0 else 0.20
    if one_week is not None:
        score += 0.50 if one_week < -8 else -0.50 if one_week > 10 else 0.0
    score = clip_score(score)

    details = (
        f"VIX {level:.2f} | 1M {one_month:+.2f}% | 1W {one_week:+.2f}%"
        if None not in (level, one_month, one_week)
        else "Dati volatilità tattici parziali"
    )
    return RegimePillar("VOLATILITY", score, state_5(score), details, count_available(level, one_month, one_week), 3)


def tactical_credit(close: pd.DataFrame) -> RegimePillar:
    ratio_1m = ratio_return(close, "HYG", "LQD", 21)
    ratio_1w = ratio_return(close, "HYG", "LQD", 5)
    hyg_1m = return_pct(close, "HYG", 21)

    score = 0.0
    score += 0.90 if (ratio_1m or 0) > 0.7 else -0.90 if (ratio_1m or 0) < -0.7 else 0.0
    score += 0.55 if (ratio_1w or 0) > 0.25 else -0.55 if (ratio_1w or 0) < -0.25 else 0.0
    if hyg_1m is not None:
        score += 0.30 if hyg_1m > 0 else -0.30
    score = clip_score(score)

    values = (ratio_1m, ratio_1w, hyg_1m)
    details = (
        f"HYG/LQD 1M {ratio_1m:+.2f}% | 1W {ratio_1w:+.2f}% | HYG 1M {hyg_1m:+.2f}%"
        if None not in values
        else "Dati credito tattici parziali"
    )
    return RegimePillar("CREDIT", score, state_5(score), details, count_available(*values), 3)


def tactical_rates(close: pd.DataFrame) -> RegimePillar:
    move_1m = yield_change_bps(close, "^TNX", 21)
    move_1w = yield_change_bps(close, "^TNX", 5)

    score = 0.0
    if move_1m is not None:
        score += 0.80 if move_1m <= -15 else -0.80 if move_1m >= 20 else -0.25 if move_1m > 5 else 0.25 if move_1m < -5 else 0.0
    if move_1w is not None:
        score += 0.45 if move_1w <= -8 else -0.45 if move_1w >= 10 else 0.0
    score = clip_score(score)

    details = (
        f"US10Y 1M {move_1m:+.1f} bp | 1W {move_1w:+.1f} bp"
        if None not in (move_1m, move_1w)
        else "Dati tassi tattici parziali"
    )
    return RegimePillar("RATES", score, state_5(score), details, count_available(move_1m, move_1w), 2)


def tactical_macro(close: pd.DataFrame) -> RegimePillar:
    copper_gold_1m = ratio_return(close, "HG=F", "GC=F", 21)
    dxy_1m = return_pct(close, "DX-Y.NYB", 21)

    score = 0.0
    score += 0.90 if (copper_gold_1m or 0) > 2 else -0.90 if (copper_gold_1m or 0) < -2 else 0.0
    score += 0.55 if (dxy_1m or 0) < -1.5 else -0.55 if (dxy_1m or 0) > 1.5 else 0.0
    score = clip_score(score)

    details = (
        f"Copper/Gold 1M {copper_gold_1m:+.2f}% | DXY 1M {dxy_1m:+.2f}%"
        if None not in (copper_gold_1m, dxy_1m)
        else "Dati macro tattici parziali"
    )
    return RegimePillar("MACRO", score, state_5(score), details, count_available(copper_gold_1m, dxy_1m), 2)


def tactical_diagnosis(score: float, previous_score: float) -> str:
    delta = score - previous_score
    if delta >= TACTICAL_IMPROVING_DELTA:
        return "IMPROVING"
    if delta <= TACTICAL_DETERIORATING_DELTA:
        return "DETERIORATING"
    if score >= 0.60:
        return "STABLE — POSITIVE"
    if score <= -0.60:
        return "STABLE — NEGATIVE"
    return "STABLE / MIXED"


def compute_tactical_score(close: pd.DataFrame) -> Tuple[float, List[RegimePillar]]:
    pillars = [
        tactical_equity(close),
        tactical_volatility(close),
        tactical_credit(close),
        tactical_rates(close),
        tactical_macro(close),
    ]
    return weighted_score(pillars, TACTICAL_WEIGHTS), pillars
