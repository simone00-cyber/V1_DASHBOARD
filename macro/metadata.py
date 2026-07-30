"""The shared per-series metadata & freshness model.

Every macro value the app displays carries exactly one `DataMetadata`
envelope, built here. Freshness is computed per series (never only at panel
level) and later aggregated transparently into pillar- and thesis-level
confidence (`macro/confidence.py`). `observation_date` (what period the value
describes), `release_date` (when the provider actually published it) and
`retrieval_timestamp` (when we fetched it) are always kept distinct.

Generalizes `data/providers/common.py::quote_status`'s staleness check so the
existing Rates section and the new Growth/Inflation/Liquidity pillars share
one freshness standard (see the Rates data-quality pass in the plan).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from macro import config


@dataclass(frozen=True)
class DataMetadata:
    provider: str
    provider_series_id: str
    canonical_series_name: str
    observation_date: pd.Timestamp | None
    reference_period: str | None
    release_date: pd.Timestamp | None
    retrieval_timestamp: pd.Timestamp
    frequency: str
    unit: str
    expected_next_release: pd.Timestamp | None
    data_age: pd.Timedelta | None
    freshness_status: str  # CURRENT / AGING / STALE / UNKNOWN
    freshness_score: int | None  # 0-100, None when UNKNOWN
    stale: bool
    revised: bool
    previous_vintage_available: bool
    source_url: str
    availability_status: str  # AVAILABLE / DEGRADED (FALLBACK) / UNAVAILABLE
    last_successful_update: pd.Timestamp | None
    # The "at least" fields above are the ones required by spec; this one is
    # additive — the human-readable reason behind a non-AVAILABLE status
    # (e.g. "FRED_API_KEY not configured"), so the UI can explain itself
    # instead of just showing a blank/unavailable chip.
    unavailable_reason: str | None = None


def utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def _score_freshness(data_age: pd.Timedelta, frequency: str) -> tuple[str, int]:
    expected = config.FRESHNESS_EXPECTED_LAG.get(frequency, config.FRESHNESS_EXPECTED_LAG["DEFAULT"])
    age_days = data_age.total_seconds() / 86400.0
    expected_days = max(expected.total_seconds() / 86400.0, 0.01)

    if age_days <= expected_days:
        return "CURRENT", 100
    if age_days <= expected_days * 2:
        score = 100 - 60 * (age_days - expected_days) / expected_days
        return "AGING", max(40, int(round(score)))
    overshoot = min(1.0, (age_days - 2 * expected_days) / expected_days)
    score = 40 - 40 * overshoot
    return "STALE", max(0, int(round(score)))


def build_data_metadata(
    *,
    provider: str,
    provider_series_id: str,
    canonical_series_name: str,
    observation_date: pd.Timestamp | None,
    frequency: str,
    unit: str,
    source_url: str,
    reference_period: str | None = None,
    release_date: pd.Timestamp | None = None,
    expected_next_release: pd.Timestamp | None = None,
    revised: bool = False,
    previous_vintage_available: bool = False,
    availability_status: str = "AVAILABLE",
    retrieval_timestamp: pd.Timestamp | None = None,
    unavailable_reason: str | None = None,
) -> DataMetadata:
    retrieval_timestamp = retrieval_timestamp or utc_now()

    if availability_status == "UNAVAILABLE" or observation_date is None:
        return DataMetadata(
            provider=provider,
            provider_series_id=provider_series_id,
            canonical_series_name=canonical_series_name,
            observation_date=None,
            reference_period=reference_period,
            release_date=release_date,
            retrieval_timestamp=retrieval_timestamp,
            frequency=frequency,
            unit=unit,
            expected_next_release=expected_next_release,
            data_age=None,
            freshness_status="UNKNOWN",
            freshness_score=None,
            stale=True,
            revised=revised,
            previous_vintage_available=previous_vintage_available,
            source_url=source_url,
            availability_status="UNAVAILABLE",
            last_successful_update=None,
            unavailable_reason=unavailable_reason,
        )

    anchor = release_date if release_date is not None else observation_date
    data_age = retrieval_timestamp - anchor
    freshness_status, freshness_score = _score_freshness(data_age, frequency)

    return DataMetadata(
        provider=provider,
        provider_series_id=provider_series_id,
        canonical_series_name=canonical_series_name,
        observation_date=observation_date,
        reference_period=reference_period,
        release_date=release_date,
        retrieval_timestamp=retrieval_timestamp,
        frequency=frequency,
        unit=unit,
        expected_next_release=expected_next_release,
        data_age=data_age,
        freshness_status=freshness_status,
        freshness_score=freshness_score,
        stale=freshness_status == "STALE",
        revised=revised,
        previous_vintage_available=previous_vintage_available,
        source_url=source_url,
        availability_status=availability_status,
        last_successful_update=retrieval_timestamp,
    )


def unavailable_metadata(
    *,
    provider: str,
    provider_series_id: str,
    canonical_series_name: str,
    frequency: str,
    unit: str,
    source_url: str,
    unavailable_reason: str | None = None,
) -> DataMetadata:
    return build_data_metadata(
        provider=provider,
        provider_series_id=provider_series_id,
        canonical_series_name=canonical_series_name,
        observation_date=None,
        frequency=frequency,
        unit=unit,
        source_url=source_url,
        availability_status="UNAVAILABLE",
        unavailable_reason=unavailable_reason,
    )
