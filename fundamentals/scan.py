"""Threaded, cache-backed fundamentals scan for the Opportunities page.

Deliberately separate from the fast, always-on Technical/Cyclical screener
(`screener/engine.py`): fetching fundamentals is one Yahoo Finance network
call per ticker per statement (no bulk endpoint exists), so this is an
explicit, cache-backed, manually-refreshed subsystem — confirmed with the
user as the required architecture so the existing screen never has to wait
on it.

`_cached_fundamental_analysis` is cached per-ticker with a 24h TTL via
`st.cache_data`, which is already keyed per-argument — "only re-download
expired tickers" falls out of that for free: a scan simply calls the cached
function for every requested ticker, and Streamlit only re-fetches the ones
whose entry is missing or older than the TTL.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

import pandas as pd
import streamlit as st

from data.providers.fundamentals.yfinance_provider import YFinanceFundamentalsProvider
from fundamentals.engine import build_fundamental_analysis
from fundamentals.models import FundamentalAnalysis

SCAN_CACHE_TTL_SECONDS = 86400
DEFAULT_MAX_WORKERS = 8


@st.cache_data(ttl=SCAN_CACHE_TTL_SECONDS, show_spinner=False, max_entries=512)
def _cached_fundamental_analysis(ticker: str) -> FundamentalAnalysis:
    return build_fundamental_analysis(ticker, YFinanceFundamentalsProvider())


@dataclass(frozen=True)
class FundamentalScanResult:
    rows: tuple[FundamentalAnalysis, ...]
    failures: tuple[tuple[str, str], ...]
    last_updated: pd.Timestamp
    coverage: int
    universe_size: int
    data_source: str = "Yahoo Finance (yfinance)"


def run_fundamental_scan(
    tickers: list[str],
    *,
    max_workers: int = DEFAULT_MAX_WORKERS,
    on_progress: Callable[[int, int], None] | None = None,
) -> FundamentalScanResult:
    clean = list(dict.fromkeys(ticker.strip().upper() for ticker in tickers if ticker and ticker.strip()))
    total = len(clean)
    results: dict[str, FundamentalAnalysis] = {}
    failures: list[tuple[str, str]] = []
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_cached_fundamental_analysis, ticker): ticker for ticker in clean}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                results[ticker] = future.result()
            except Exception as exc:
                failures.append((ticker, str(exc)))
            completed += 1
            if on_progress is not None:
                on_progress(completed, total)

    rows = tuple(results[ticker] for ticker in clean if ticker in results)
    coverage = sum(1 for row in rows if row.sufficient)
    return FundamentalScanResult(
        rows=rows,
        failures=tuple(failures),
        last_updated=pd.Timestamp.utcnow(),
        coverage=coverage,
        universe_size=total,
    )


def clear_fundamental_cache() -> None:
    """Used by the "Refresh Fundamental Analysis" button to force re-download."""
    _cached_fundamental_analysis.clear()
