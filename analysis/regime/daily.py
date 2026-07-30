from __future__ import annotations

from typing import List, Tuple

import pandas as pd

from config.settings import DAILY_RISK_OFF_THRESHOLD, DAILY_RISK_ON_THRESHOLD, DAILY_WEIGHTS
from .common import clip_score, count_available, ratio_return, return_pct, safe_mean, state_5, weighted_score, yield_change_bps
from .models import RegimePillar


def daily_pillar(name: str, score: float, details: str, available: int, expected: int) -> RegimePillar:
    score = clip_score(score)
    return RegimePillar(name, score, state_5(score), details, available, expected)


def compute_daily_layer(close: pd.DataFrame) -> Tuple[float, str, List[RegimePillar]]:
    spy = return_pct(close, "SPY", 1)
    qqq = return_pct(close, "QQQ", 1)
    acwi = return_pct(close, "ACWI", 1)
    vix = return_pct(close, "^VIX", 1)
    credit = ratio_return(close, "HYG", "LQD", 1)
    ten = yield_change_bps(close, "^TNX", 1)
    dxy = return_pct(close, "DX-Y.NYB", 1)
    copper_gold = ratio_return(close, "HG=F", "GC=F", 1)

    equity_components = []
    if spy is not None:
        equity_components.append(2 if spy > 0.7 else 1 if spy > 0 else -2 if spy < -0.7 else -1)
    if qqq is not None:
        equity_components.append(2 if qqq > 0.9 else 1 if qqq > 0 else -2 if qqq < -0.9 else -1)
    if acwi is not None:
        equity_components.append(2 if acwi > 0.5 else 1 if acwi > 0 else -2 if acwi < -0.5 else -1)
    equity_score = clip_score(safe_mean(equity_components))

    vol_score = 0 if vix is None else 2 if vix < -8 else 1 if vix < 0 else -2 if vix > 10 else -1
    credit_score = 0 if credit is None else 2 if credit > 0.25 else 1 if credit > 0 else -2 if credit < -0.25 else -1
    rates_score = 0 if ten is None else 1 if ten < -5 else -1 if ten > 5 else 0
    macro_components = []
    if copper_gold is not None:
        macro_components.append(1 if copper_gold > 0 else -1)
    if dxy is not None:
        macro_components.append(1 if dxy < 0 else -1)
    macro_score = clip_score(safe_mean(macro_components))

    pillars = [
        daily_pillar("EQUITY", equity_score, f"SPY {spy:+.2f}% | QQQ {qqq:+.2f}% | ACWI {acwi:+.2f}%" if None not in (spy, qqq, acwi) else "Dati equity giornalieri parziali", count_available(spy, qqq, acwi), 3),
        daily_pillar("VOLATILITY", vol_score, f"VIX {vix:+.2f}%" if vix is not None else "VIX non disponibile", count_available(vix), 1),
        daily_pillar("CREDIT", credit_score, f"HYG/LQD {credit:+.2f}%" if credit is not None else "Credito non disponibile", count_available(credit), 1),
        daily_pillar("RATES", rates_score, f"US10Y {ten:+.1f} bp" if ten is not None else "Tassi non disponibili", count_available(ten), 1),
        daily_pillar("MACRO", macro_score, f"Copper/Gold {copper_gold:+.2f}% | DXY {dxy:+.2f}%" if None not in (copper_gold, dxy) else "Macro giornaliero parziale", count_available(copper_gold, dxy), 2),
    ]

    score = weighted_score(pillars, DAILY_WEIGHTS)
    diagnosis = "RISK-ON" if score >= DAILY_RISK_ON_THRESHOLD else "RISK-OFF" if score <= DAILY_RISK_OFF_THRESHOLD else "MIXED"
    return score, diagnosis, pillars
