"""Raw provider data -> `MacroSeriesReading`.

The only place that converts a FRED or NY Fed raw response into the app's
provider-agnostic shape. Pillar logic (`macro/growth.py` etc.) never sees a
raw provider payload — only what this module returns.
"""

from __future__ import annotations

import pandas as pd

from macro.metadata import build_data_metadata, unavailable_metadata
from macro.models import MacroSeriesReading

_PERIODS_PER_YEAR = {"DAILY": 252, "WEEKLY": 52, "MONTHLY": 12, "QUARTERLY": 4}


def _reference_period(observation_date: pd.Timestamp, frequency: str) -> str:
    if frequency == "MONTHLY":
        return observation_date.strftime("%B %Y")
    if frequency == "QUARTERLY":
        quarter = (observation_date.month - 1) // 3 + 1
        return f"Q{quarter} {observation_date.year}"
    return observation_date.strftime("%Y-%m-%d")


def _latest_previous_yoy_mom(
    observations: pd.DataFrame, frequency: str
) -> tuple[float | None, float | None, float | None, float | None, pd.Timestamp | None]:
    clean = observations.dropna(subset=["value"]).sort_values("date")
    if clean.empty:
        return None, None, None, None, None

    latest_row = clean.iloc[-1]
    latest_value = float(latest_row["value"])
    observation_date = latest_row["date"]

    previous_value = float(clean.iloc[-2]["value"]) if len(clean) >= 2 else None
    mom_pct = (
        (latest_value - previous_value) / abs(previous_value)
        if previous_value not in (None, 0)
        else None
    )

    periods_back = _PERIODS_PER_YEAR.get(frequency)
    yoy_pct = None
    if periods_back is not None and len(clean) > periods_back:
        year_ago_value = float(clean.iloc[-1 - periods_back]["value"])
        if year_ago_value != 0:
            yoy_pct = (latest_value - year_ago_value) / abs(year_ago_value)

    return latest_value, previous_value, yoy_pct, mom_pct, observation_date


def normalize_fred_reading(
    *,
    canonical_id: str,
    series_id: str,
    label: str,
    unit: str,
    frequency: str,
    observations: pd.DataFrame,
    series_info: dict | None = None,
) -> MacroSeriesReading:
    latest_value, previous_value, yoy_pct, mom_pct, observation_date = _latest_previous_yoy_mom(
        observations, frequency
    )
    source_url = f"https://fred.stlouisfed.org/series/{series_id}"

    if latest_value is None or observation_date is None:
        metadata = unavailable_metadata(
            provider="FRED",
            provider_series_id=series_id,
            canonical_series_name=label,
            frequency=frequency,
            unit=unit,
            source_url=source_url,
            unavailable_reason="FRED returned no observations for this series.",
        )
        return MacroSeriesReading(canonical_id, label, None, None, None, None, metadata)

    series_info = series_info or {}
    release_date = pd.to_datetime(series_info.get("last_updated"), utc=True, errors="coerce")
    release_date = None if pd.isna(release_date) else release_date

    metadata = build_data_metadata(
        provider="FRED",
        provider_series_id=series_id,
        canonical_series_name=label,
        observation_date=observation_date,
        reference_period=_reference_period(observation_date, frequency),
        release_date=release_date,
        frequency=frequency,
        unit=unit,
        source_url=source_url,
    )
    return MacroSeriesReading(canonical_id, label, latest_value, previous_value, yoy_pct, mom_pct, metadata)


def normalize_ny_fed_reading(
    *,
    canonical_id: str,
    rate_type: str,
    label: str,
    unit: str,
    frequency: str,
    observations: pd.DataFrame,
) -> MacroSeriesReading:
    latest_value, previous_value, yoy_pct, mom_pct, observation_date = _latest_previous_yoy_mom(
        observations, frequency
    )
    source_url = "https://markets.newyorkfed.org/api"

    if latest_value is None or observation_date is None:
        metadata = unavailable_metadata(
            provider="NY_FED",
            provider_series_id=rate_type.upper(),
            canonical_series_name=label,
            frequency=frequency,
            unit=unit,
            source_url=source_url,
            unavailable_reason="NY Fed returned no observations for this rate.",
        )
        return MacroSeriesReading(canonical_id, label, None, None, None, None, metadata)

    metadata = build_data_metadata(
        provider="NY_FED",
        provider_series_id=rate_type.upper(),
        canonical_series_name=label,
        observation_date=observation_date,
        reference_period=_reference_period(observation_date, frequency),
        release_date=observation_date,  # NY Fed publishes same-day
        frequency=frequency,
        unit=unit,
        source_url=source_url,
    )
    return MacroSeriesReading(canonical_id, label, latest_value, previous_value, yoy_pct, mom_pct, metadata)
