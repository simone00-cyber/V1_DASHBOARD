from typing import Dict, List
import numpy as np
import pandas as pd

def safe_pct_change(series: pd.Series, sessions: int) -> float:
    clean = series.dropna()
    if len(clean) <= sessions:
        return np.nan
    return (float(clean.iloc[-1]) / float(clean.iloc[-1 - sessions]) - 1.0) * 100.0

def build_market_table(close: pd.DataFrame, universe: Dict[str, str]) -> pd.DataFrame:
    rows: List[dict] = []

    for name, ticker in universe.items():
        if ticker not in close.columns:
            continue

        series = close[ticker].dropna()
        if len(series) < 2:
            continue

        rows.append(
            {
                "Strumento": name,
                "Ticker": ticker,
                "Ultimo": float(series.iloc[-1]),
                "1D %": safe_pct_change(series, 1),
                "1W %": safe_pct_change(series, 5),
                "1M %": safe_pct_change(series, 21),
                "3M %": safe_pct_change(series, 63),
                "Data": series.index[-1],
            }
        )

    return pd.DataFrame(rows)

def latest_change_bp(series: pd.Series) -> float:
    clean = series.dropna()
    if len(clean) < 2:
        return np.nan
    return (float(clean.iloc[-1]) - float(clean.iloc[-2])) * 100.0

def normalized_frame(frame: pd.DataFrame) -> pd.DataFrame:
    clean = frame.ffill().dropna(how="all")
    if clean.empty:
        return clean

    result = pd.DataFrame(index=clean.index)
    for column in clean.columns:
        series = clean[column].dropna()
        if series.empty or float(series.iloc[0]) == 0:
            continue
        result[column] = clean[column] / float(series.iloc[0]) * 100.0
    return result

def ratio_series(close: pd.DataFrame, numerator: str, denominator: str) -> pd.Series:
    if numerator not in close.columns or denominator not in close.columns:
        return pd.Series(dtype=float)
    ratio = close[numerator] / close[denominator]
    return ratio.replace([np.inf, -np.inf], np.nan).dropna()
