"""New York Fed Markets API raw provider — reference rates (SOFR, EFFR).

No API key required — fully public, unauthenticated JSON endpoints.
Reachability and response shape for SOFR were verified live during planning
(a real, current SOFR print was returned with zero configuration).

Only this module parses the NY Fed response shape; normalization into
`MacroSeriesReading` happens in `macro/normalization.py`.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from data.providers.common import build_http_session

NY_FED_BASE = "https://markets.newyorkfed.org/api"

_RATE_PATHS = {
    "sofr": "rates/secured/sofr/last/{n}.json",
    "effr": "rates/unsecured/effr/last/{n}.json",
}


class NyFedUnavailableError(RuntimeError):
    """Raised when a NY Fed Markets API request fails."""


def fetch_reference_rate(rate_type: str, *, session: Any = None, count: int = 5, timeout: int = 15) -> pd.DataFrame:
    """Raw recent prints for `rate_type` ('sofr'|'effr'), oldest first.
    Columns: date (effectiveDate), value (percentRate)."""
    key = rate_type.strip().lower()
    if key not in _RATE_PATHS:
        raise ValueError(f"Unsupported NY Fed rate type: {rate_type!r}")
    session = session or build_http_session()
    url = f"{NY_FED_BASE}/{_RATE_PATHS[key].format(n=count)}"
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise NyFedUnavailableError(f"NY Fed request failed for {rate_type}: {exc}") from exc

    rows = payload.get("refRates", [])
    if not rows:
        return pd.DataFrame(columns=["date", "value"])
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["effectiveDate"], utc=True, errors="coerce")
    frame["value"] = pd.to_numeric(frame["percentRate"], errors="coerce")
    return frame[["date", "value"]].dropna(subset=["date"]).sort_values("date")
