from __future__ import annotations
import numpy as np
import pandas as pd
from .confidence import confidence_label, research_score


def profit_factor(values: pd.Series) -> float:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    gains = clean[clean > 0].sum()
    losses = -clean[clean < 0].sum()
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def summarize_group(frame: pd.DataFrame) -> dict:
    returns = pd.to_numeric(frame["NET RETURN"], errors="coerce").dropna()
    count = int(len(returns))
    avg = float(returns.mean()) if count else 0.0
    pf = profit_factor(returns)
    return {
        "TRADES": count,
        "WIN RATE": float((returns > 0).mean()) if count else 0.0,
        "AVG RETURN": avg,
        "MEDIAN RETURN": float(returns.median()) if count else 0.0,
        "PROFIT FACTOR": pf,
        "AVG BARS": float(pd.to_numeric(frame["BARS"], errors="coerce").mean()) if count else 0.0,
        "CONFIDENCE": confidence_label(count),
        "RESEARCH SCORE": research_score(count, avg, pf),
    }
