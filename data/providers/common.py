from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
import re
from typing import Iterable

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def utc_now() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(timezone.utc))


def as_utc_timestamp(value: object) -> pd.Timestamp | None:
    try:
        result = pd.Timestamp(value)
        if pd.isna(result):
            return None
        if result.tzinfo is None:
            return result.tz_localize("UTC")
        return result.tz_convert("UTC")
    except Exception:
        return None


def quote_status(as_of: pd.Timestamp | None, max_age_hours: float) -> str:
    if as_of is None:
        return "UNAVAILABLE"
    age_hours = (utc_now() - as_of).total_seconds() / 3600.0
    return "STALE" if age_hours > max_age_hours else "OK"


def clean_numeric(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("%", "").replace("\u00a0", "").replace("−", "-")
    if not text or text.lower() in {"nan", "na", "n/a", "-", "--", "."}:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    text = re.sub(r"[^0-9+\-.]", "", text)
    try:
        number = float(text)
        return number if np.isfinite(number) else None
    except ValueError:
        return None


def build_http_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": "Cyclical-Terminal/10.3 (+market-research-dashboard)",
            "Accept": (
                "application/vnd.bbk.data+csv,application/vnd.sdmx.data+csv,"
                "text/csv,application/json,text/html;q=0.9,*/*;q=0.8"
            ),
        }
    )
    return session


def _parse_date_series(values: pd.Series) -> pd.Series:
    """Parse common official-data date formats without dateutil warnings."""
    text = values.astype("string").str.strip()
    result = pd.Series(pd.NaT, index=text.index, dtype="datetime64[ns, UTC]")

    formats: tuple[str, ...] = (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y-%m",
        "%Y",
    )
    remaining = result.isna() & text.notna()
    for fmt in formats:
        if not remaining.any():
            break
        parsed = pd.to_datetime(text[remaining], format=fmt, errors="coerce", utc=True)
        valid = parsed.notna()
        if valid.any():
            result.loc[parsed.index[valid]] = parsed.loc[valid]
        remaining = result.isna() & text.notna()

    # Pandas 2 supports format='mixed'; it is explicit and avoids the warning.
    if remaining.any():
        parsed = pd.to_datetime(text[remaining], format="mixed", errors="coerce", utc=True, dayfirst=False)
        result.loc[parsed.index] = parsed
    return result


def parse_tabular_series(text: str) -> pd.Series:
    """Return a date-indexed numeric series from ECB/Bundesbank-style CSV.

    The parser inspects column names and uses deterministic date parsing. It
    never emits the pandas format-inference warning that motivated the refactor.
    """
    attempts: list[pd.DataFrame] = []
    for kwargs in (
        {"sep": None, "engine": "python"},
        {"sep": ";"},
        {"sep": ","},
        {"sep": "\t"},
    ):
        try:
            frame = pd.read_csv(StringIO(text), **kwargs)
            if not frame.empty:
                attempts.append(frame)
        except Exception:
            continue

    date_tokens = ("date", "time_period", "time period", "period")
    value_tokens = ("obs_value", "obs value", "value", "yield", "rate")

    for frame in attempts:
        if frame.shape[1] < 2:
            continue
        columns = list(frame.columns)
        date_col = next(
            (c for c in columns if any(token in str(c).lower() for token in date_tokens)),
            columns[0],
        )
        value_col = next(
            (
                c
                for c in columns
                if c != date_col and any(token in str(c).lower() for token in value_tokens)
            ),
            columns[-1],
        )
        dates = _parse_date_series(frame[date_col])
        values = frame[value_col].map(clean_numeric)
        series = pd.Series(values.to_numpy(dtype=float), index=dates, dtype=float)
        series = series[~series.index.isna()].dropna().sort_index()
        series = series[~series.index.duplicated(keep="last")]
        if not series.empty:
            return series
    return pd.Series(dtype=float)


def latest_change(series: pd.Series, *, multiplier: float = 1.0) -> tuple[float | None, float | None, pd.Timestamp | None]:
    clean = pd.to_numeric(series, errors="coerce").dropna().sort_index()
    if clean.empty:
        return None, None, None
    value = float(clean.iloc[-1])
    change = float((clean.iloc[-1] - clean.iloc[-2]) * multiplier) if len(clean) >= 2 else None
    return value, change, as_utc_timestamp(clean.index[-1])
