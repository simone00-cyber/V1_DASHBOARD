from time import sleep
from typing import Dict, List, Tuple
import pandas as pd
import streamlit as st
import yfinance as yf
from core.logging_config import get_logger

logger = get_logger(__name__)
from config.universe import RATE_CANDIDATES

def _flatten_download(raw: pd.DataFrame, tickers: List[str]) -> pd.DataFrame:
    """Estrae il Close da un download yfinance mono o multi ticker."""
    if raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            close = raw["Close"].copy()
        elif "Close" in raw.columns.get_level_values(1):
            close = raw.xs("Close", axis=1, level=1).copy()
        else:
            return pd.DataFrame()
    else:
        if "Close" not in raw.columns:
            return pd.DataFrame()
        close = raw[["Close"]].copy()
        close.columns = [tickers[0]]

    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])

    return close.sort_index().dropna(how="all")

@st.cache_data(ttl=60, show_spinner=False, max_entries=64)
def download_close_batch(
    tickers_tuple: Tuple[str, ...],
    period: str = "1y",
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Download multi-ticker con fallback ticker-per-ticker.

    Il fallback evita che un singolo simbolo non disponibile blocchi l'intera
    sezione Global Macro.
    """
    tickers = list(dict.fromkeys(tickers_tuple))
    if not tickers:
        return pd.DataFrame()

    try:
        raw = yf.download(
            tickers=tickers,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            group_by="column",
            threads=True,
            timeout=15,
        )
        close = _flatten_download(raw, tickers)
    except Exception as error:
        logger.exception("Yahoo batch download failed: %s", error)
        close = pd.DataFrame()

    missing = [ticker for ticker in tickers if ticker not in close.columns or close[ticker].dropna().empty]

    for ticker in missing:
        series = None
        for attempt in range(2):
            try:
                raw_single = yf.download(
                    ticker,
                    period=period,
                    interval=interval,
                    auto_adjust=False,
                    progress=False,
                    threads=False,
                    timeout=12,
                )
                extracted = _flatten_download(raw_single, [ticker])
                if ticker in extracted.columns and not extracted[ticker].dropna().empty:
                    series = extracted[ticker]
                    break
            except Exception:
                pass

            if attempt == 0:
                sleep(0.35)

        if series is not None:
            if ticker in close.columns:
                # The batch download already produced this column (typically
                # all-NaN, which is why it was retried) — drop it first so
                # the join below has no overlapping column name.
                close = close.drop(columns=[ticker])
            close = close.join(series.rename(ticker), how="outer") if not close.empty else series.to_frame(ticker)

    return close.sort_index().dropna(how="all")

def resolve_rate_series(period: str = "2y") -> Tuple[pd.DataFrame, Dict[str, str]]:
    """Trova il primo ticker Yahoo funzionante per ogni scadenza Treasury."""
    resolved: Dict[str, pd.Series] = {}
    symbols: Dict[str, str] = {}

    all_candidates = tuple(
        dict.fromkeys(
            ticker
            for candidates in RATE_CANDIDATES.values()
            for ticker in candidates
        )
    )
    downloaded = download_close_batch(all_candidates, period=period)

    for label, candidates in RATE_CANDIDATES.items():
        for ticker in candidates:
            if ticker in downloaded.columns:
                series = downloaded[ticker].dropna()
                if len(series) >= 2:
                    resolved[label] = series
                    symbols[label] = ticker
                    break

    if not resolved:
        return pd.DataFrame(), {}

    return pd.DataFrame(resolved).sort_index(), symbols
