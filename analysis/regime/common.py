from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd

from config.settings import (
    REGIME_SCORE_MAX,
    REGIME_SCORE_MIN,
    REGIME_STATE_THRESHOLDS,
)
from core.metrics import ratio_series


def series(close: pd.DataFrame, ticker: str) -> pd.Series:
    if ticker not in close.columns:
        return pd.Series(dtype=float)
    return close[ticker].dropna().astype(float)


def last(close: pd.DataFrame, ticker: str) -> Optional[float]:
    data = series(close, ticker)
    return None if data.empty else float(data.iloc[-1])


def return_pct(close: pd.DataFrame, ticker: str, sessions: int) -> Optional[float]:
    data = series(close, ticker)
    if len(data) <= sessions:
        return None
    return float((data.iloc[-1] / data.iloc[-1 - sessions] - 1.0) * 100.0)


def ratio_return(
    close: pd.DataFrame,
    numerator: str,
    denominator: str,
    sessions: int,
) -> Optional[float]:
    ratio = ratio_series(close, numerator, denominator).dropna()
    if len(ratio) <= sessions:
        return None
    return float((ratio.iloc[-1] / ratio.iloc[-1 - sessions] - 1.0) * 100.0)


def yield_change_bps(close: pd.DataFrame, ticker: str, sessions: int) -> Optional[float]:
    """Per gli indici Yahoo ^TNX/^IRX, 0,10 punti indice equivalgono a circa 1 bp."""
    data = series(close, ticker)
    if len(data) <= sessions:
        return None
    return float((data.iloc[-1] - data.iloc[-1 - sessions]) * 10.0)


def moving_average_distance(
    close: pd.DataFrame,
    ticker: str,
    window: int,
) -> Optional[float]:
    data = series(close, ticker)
    if len(data) < window:
        return None
    average = float(data.rolling(window).mean().iloc[-1])
    if average == 0:
        return None
    return float((data.iloc[-1] / average - 1.0) * 100.0)


def safe_mean(values: Iterable[Optional[float]]) -> float:
    clean = [float(v) for v in values if v is not None and not pd.isna(v)]
    return float(np.mean(clean)) if clean else 0.0


def clip_score(value: float) -> float:
    return float(np.clip(value, REGIME_SCORE_MIN, REGIME_SCORE_MAX))


def state_5(score: float) -> str:
    thresholds = REGIME_STATE_THRESHOLDS
    if score >= thresholds["strong_positive"]:
        return "STRONGLY POSITIVE"
    if score >= thresholds["positive"]:
        return "POSITIVE"
    if score <= thresholds["strong_negative"]:
        return "STRONGLY NEGATIVE"
    if score <= thresholds["negative"]:
        return "NEGATIVE"
    return "NEUTRAL"


def count_available(*values: Optional[float]) -> int:
    return sum(value is not None and not pd.isna(value) for value in values)


def weighted_score(pillars, weights: dict[str, float]) -> float:
    usable = [p for p in pillars if p.coverage > 0]
    denominator = sum(weights[p.name] * p.coverage for p in usable)
    if denominator == 0:
        return 0.0
    numerator = sum(p.score * weights[p.name] * p.coverage for p in usable)
    return float(numerator / denominator)


def slice_before(close: pd.DataFrame, sessions: int) -> pd.DataFrame:
    if sessions <= 0 or len(close) <= sessions:
        return close.copy()
    return close.iloc[:-sessions].copy()
