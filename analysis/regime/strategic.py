from __future__ import annotations

from typing import List, Tuple

import pandas as pd

from config.settings import STRATEGIC_WEIGHTS
from core.metrics import ratio_series
from .common import (
    clip_score,
    count_available,
    last,
    moving_average_distance,
    ratio_return,
    return_pct,
    series,
    state_5,
    weighted_score,
    yield_change_bps,
)
from .models import RegimePillar


def strategic_equity(close: pd.DataFrame) -> RegimePillar:
    spy_6m = return_pct(close, "SPY", 126)
    qqq_6m = return_pct(close, "QQQ", 126)
    acwi_6m = return_pct(close, "ACWI", 126)
    spy_ma200 = moving_average_distance(close, "SPY", 200)
    acwi_ma200 = moving_average_distance(close, "ACWI", 200)

    score = 0.0
    score += 0.55 if (spy_6m or 0) > 5 else -0.55 if (spy_6m or 0) < -5 else 0.0
    score += 0.45 if (qqq_6m or 0) > 5 else -0.45 if (qqq_6m or 0) < -5 else 0.0
    score += 0.40 if (acwi_6m or 0) > 3 else -0.40 if (acwi_6m or 0) < -3 else 0.0
    if spy_ma200 is not None:
        score += 0.35 if spy_ma200 > 0 else -0.35
    if acwi_ma200 is not None:
        score += 0.25 if acwi_ma200 > 0 else -0.25
    score = clip_score(score)

    values = (spy_6m, qqq_6m, acwi_6m, spy_ma200, acwi_ma200)
    details = (
        f"SPY 6M {spy_6m:+.2f}% | QQQ 6M {qqq_6m:+.2f}% | "
        f"ACWI 6M {acwi_6m:+.2f}% | SPY vs MM200 {spy_ma200:+.2f}%"
        if None not in values[:4]
        else "Dati equity strutturali parziali"
    )
    return RegimePillar("EQUITY", score, state_5(score), details, count_available(*values), 5)


def strategic_volatility(close: pd.DataFrame) -> RegimePillar:
    vix = series(close, "^VIX")
    if vix.empty:
        return RegimePillar("VOLATILITY", 0.0, "NEUTRAL", "VIX non disponibile", 0, 3)

    level = float(vix.iloc[-1])
    ma63 = float(vix.rolling(63).mean().iloc[-1]) if len(vix) >= 63 else None
    percentile = float((vix.tail(252) <= level).mean() * 100.0) if len(vix) >= 20 else None

    score = 0.0
    score += 0.80 if level < 17 else 0.25 if level < 22 else -0.75 if level < 30 else -1.50
    if ma63 is not None:
        score += 0.55 if level < ma63 else -0.55
    if percentile is not None:
        score += 0.35 if percentile < 40 else -0.35 if percentile > 70 else 0.0
    score = clip_score(score)

    details = f"VIX {level:.2f}"
    if ma63 is not None:
        details += f" | MM63 {ma63:.2f}"
    if percentile is not None:
        details += f" | percentile 1Y {percentile:.0f}"
    return RegimePillar("VOLATILITY", score, state_5(score), details, count_available(level, ma63, percentile), 3)


def strategic_credit(close: pd.DataFrame) -> RegimePillar:
    ratio_6m = ratio_return(close, "HYG", "LQD", 126)
    ratio_ma200 = None
    ratio = ratio_series(close, "HYG", "LQD").dropna()
    if len(ratio) >= 200:
        ratio_ma200 = float((ratio.iloc[-1] / ratio.rolling(200).mean().iloc[-1] - 1.0) * 100.0)
    hyg_6m = return_pct(close, "HYG", 126)

    score = 0.0
    score += 0.85 if (ratio_6m or 0) > 1.5 else -0.85 if (ratio_6m or 0) < -1.5 else 0.0
    if ratio_ma200 is not None:
        score += 0.65 if ratio_ma200 > 0 else -0.65
    if hyg_6m is not None:
        score += 0.35 if hyg_6m > 0 else -0.35
    score = clip_score(score)

    values = (ratio_6m, ratio_ma200, hyg_6m)
    details = (
        f"HYG/LQD 6M {ratio_6m:+.2f}% | vs MM200 {ratio_ma200:+.2f}% | HYG 6M {hyg_6m:+.2f}%"
        if None not in values
        else "Dati credito strutturali parziali"
    )
    return RegimePillar("CREDIT", score, state_5(score), details, count_available(*values), 3)


def strategic_rates(close: pd.DataFrame) -> RegimePillar:
    ten = last(close, "^TNX")
    bill = last(close, "^IRX")
    move_3m = yield_change_bps(close, "^TNX", 63)
    curve = (ten - bill) * 10.0 if ten is not None and bill is not None else None

    score = 0.0
    if move_3m is not None:
        score += 0.70 if move_3m <= -20 else 0.25 if move_3m < 10 else -0.60 if move_3m < 30 else -1.10
    if curve is not None:
        score += 0.45 if curve > 25 else -0.65 if curve < -50 else -0.20 if curve < 0 else 0.15
    if ten is not None:
        score += 0.25 if ten < 35 else -0.25 if ten > 45 else 0.0
    score = clip_score(score)

    details = (
        f"US10Y {ten / 10:.2f}% | 3M {move_3m:+.1f} bp | 10Y-13W {curve:+.1f} bp"
        if None not in (ten, move_3m, curve)
        else "Dati tassi strutturali parziali"
    )
    return RegimePillar("RATES", score, state_5(score), details, count_available(ten, move_3m, curve), 3)


def strategic_macro(close: pd.DataFrame) -> RegimePillar:
    copper_gold_6m = ratio_return(close, "HG=F", "GC=F", 126)
    dxy_6m = return_pct(close, "DX-Y.NYB", 126)

    score = 0.0
    score += 0.90 if (copper_gold_6m or 0) > 5 else -0.90 if (copper_gold_6m or 0) < -5 else 0.0
    score += 0.55 if (dxy_6m or 0) < -3 else -0.55 if (dxy_6m or 0) > 3 else 0.0
    score = clip_score(score)

    details = (
        f"Copper/Gold 6M {copper_gold_6m:+.2f}% | DXY 6M {dxy_6m:+.2f}%"
        if None not in (copper_gold_6m, dxy_6m)
        else "Dati macro strutturali parziali"
    )
    return RegimePillar("MACRO", score, state_5(score), details, count_available(copper_gold_6m, dxy_6m), 2)


def strategic_diagnosis(score: float, pillars: List[RegimePillar]) -> str:
    values = {pillar.name: pillar.score for pillar in pillars}
    rates = values.get("RATES", 0.0)
    credit = values.get("CREDIT", 0.0)
    volatility = values.get("VOLATILITY", 0.0)

    if score >= 0.60:
        return "CONSTRUCTIVE — RATES-CONSTRAINED" if rates <= -0.50 else "CONSTRUCTIVE"
    if score <= -0.60:
        if credit <= -0.60 or volatility <= -0.80:
            return "DEFENSIVE — FINANCIAL STRESS"
        return "DEFENSIVE"
    if rates <= -0.70 and credit >= 0:
        return "NEUTRAL — RATES HEADWIND"
    return "NEUTRAL / TRANSITION"


def compute_strategic_layer(close: pd.DataFrame) -> Tuple[float, str, List[RegimePillar]]:
    pillars = [
        strategic_equity(close),
        strategic_volatility(close),
        strategic_credit(close),
        strategic_rates(close),
        strategic_macro(close),
    ]
    score = weighted_score(pillars, STRATEGIC_WEIGHTS)
    return score, strategic_diagnosis(score, pillars), pillars
