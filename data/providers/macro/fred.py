"""FRED (Federal Reserve Economic Data, St. Louis Fed) raw provider.

Free API, requires a personal API key (instant signup, no cost:
https://fred.stlouisfed.org/docs/api/api_key.html). Reachability and error
shape were verified live during planning (unauthenticated request returned
the documented "api_key is not set" 400 response).

Only this module parses FRED's JSON. Everything returned here is raw
(FRED's own observation dates/values) — `macro/normalization.py` converts it
into the app's provider-agnostic `MacroSeriesReading`.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

from data.providers.common import build_http_session

FRED_API_BASE = "https://api.stlouisfed.org/fred"


class FredConfigurationError(RuntimeError):
    """Raised when FRED_API_KEY is not configured."""


class FredUnavailableError(RuntimeError):
    """Raised when a FRED request fails (network, HTTP error, bad payload)."""


def _api_key() -> str:
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        raise FredConfigurationError(
            "FRED_API_KEY is not configured. Get a free key at "
            "https://fred.stlouisfed.org/docs/api/api_key.html and set it in .env."
        )
    return key


def _get(session: Any, path: str, params: dict[str, Any], timeout: int = 20) -> dict:
    query = {**params, "file_type": "json"}
    try:
        response = session.get(f"{FRED_API_BASE}/{path}", params=query, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise FredUnavailableError(f"FRED request to '{path}' failed: {exc}") from exc


def fetch_observations(
    series_id: str,
    *,
    api_key: str | None = None,
    session: Any = None,
    start: str | None = None,
) -> pd.DataFrame:
    """Raw observations for one series, oldest first. Columns: date, value
    (NaN where FRED reports '.' — no data for that period)."""
    key = api_key or _api_key()
    session = session or build_http_session()
    params = {"series_id": series_id, "api_key": key, "sort_order": "asc"}
    if start:
        params["observation_start"] = start
    payload = _get(session, "series/observations", params)
    observations = payload.get("observations", [])
    if not observations:
        return pd.DataFrame(columns=["date", "value"])
    frame = pd.DataFrame(observations)
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    return frame[["date", "value"]].dropna(subset=["date"])


def fetch_series_info(series_id: str, *, api_key: str | None = None, session: Any = None) -> dict:
    """Series-level metadata: title, units, frequency, last_updated (ISO)."""
    key = api_key or _api_key()
    session = session or build_http_session()
    payload = _get(session, "series", {"series_id": series_id, "api_key": key})
    seriess = payload.get("seriess", [])
    return seriess[0] if seriess else {}


def fetch_releases(*, api_key: str | None = None, session: Any = None) -> list[dict]:
    """All FRED releases (id + name) — used to resolve a release id by name
    at runtime instead of hardcoding numeric ids that could drift."""
    key = api_key or _api_key()
    session = session or build_http_session()
    payload = _get(session, "releases", {"api_key": key})
    return payload.get("releases", [])


def fetch_release_dates(
    release_id: str,
    *,
    api_key: str | None = None,
    session: Any = None,
    include_future: bool = True,
) -> pd.DataFrame:
    """Past, and (only when FRED has actually published one) scheduled-future
    dates for one release. Never fabricates a date FRED doesn't return."""
    key = api_key or _api_key()
    session = session or build_http_session()
    params = {
        "release_id": release_id,
        "api_key": key,
        "include_release_dates_with_no_data": "true" if include_future else "false",
        "sort_order": "asc",
    }
    payload = _get(session, "release/dates", params)
    dates = payload.get("release_dates", [])
    if not dates:
        return pd.DataFrame(columns=["release_id", "date"])
    frame = pd.DataFrame(dates)
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    return frame.dropna(subset=["date"])
