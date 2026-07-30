from __future__ import annotations

from typing import Iterable

import pandas as pd
import yfinance as yf

from core.logging_config import get_logger

logger = get_logger(__name__)


def download_intraday_close(
    tickers: Iterable[str],
    *,
    period: str = "5d",
    interval: str = "5m",
) -> pd.DataFrame:
    symbols = list(dict.fromkeys(str(t).strip() for t in tickers if str(t).strip()))
    if not symbols:
        return pd.DataFrame()
    try:
        raw = yf.download(
            tickers=symbols,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            group_by="column",
            threads=True,
            timeout=25,
        )
    except Exception as exc:
        logger.warning("Yahoo macro download failed: %s", exc)
        return pd.DataFrame()

    if raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        level0 = raw.columns.get_level_values(0)
        level1 = raw.columns.get_level_values(1)
        if "Close" in level0:
            close = raw.xs("Close", axis=1, level=0).copy()
        elif "Close" in level1:
            close = raw.xs("Close", axis=1, level=1).copy()
        else:
            return pd.DataFrame()
    else:
        if "Close" not in raw.columns:
            return pd.DataFrame()
        close = raw[["Close"]].copy()
        close.columns = [symbols[0]]

    if isinstance(close, pd.Series):
        close = close.to_frame(symbols[0])
    close.columns = [str(column) for column in close.columns]
    return close.sort_index().dropna(how="all")
