from __future__ import annotations

import pandas as pd

from macro.metadata import build_data_metadata, unavailable_metadata


def test_observation_release_and_retrieval_dates_stay_distinct():
    observation_date = pd.Timestamp("2026-06-01", tz="UTC")
    release_date = pd.Timestamp("2026-07-03", tz="UTC")
    retrieval_timestamp = pd.Timestamp("2026-07-05", tz="UTC")

    metadata = build_data_metadata(
        provider="FRED",
        provider_series_id="CPIAUCSL",
        canonical_series_name="US CPI",
        observation_date=observation_date,
        release_date=release_date,
        retrieval_timestamp=retrieval_timestamp,
        frequency="MONTHLY",
        unit="Index",
        source_url="https://example.com",
    )

    assert metadata.observation_date == observation_date
    assert metadata.release_date == release_date
    assert metadata.retrieval_timestamp == retrieval_timestamp
    assert len({metadata.observation_date, metadata.release_date, metadata.retrieval_timestamp}) == 3


def test_current_within_expected_lag():
    observation_date = pd.Timestamp("2026-07-01", tz="UTC")
    retrieval = observation_date + pd.Timedelta(days=10)  # well within the 45-day monthly lag
    metadata = build_data_metadata(
        provider="FRED", provider_series_id="X", canonical_series_name="X",
        observation_date=observation_date, frequency="MONTHLY", unit="", source_url="",
        retrieval_timestamp=retrieval,
    )
    assert metadata.freshness_status == "CURRENT"
    assert metadata.freshness_score == 100
    assert metadata.stale is False


def test_aging_between_1x_and_2x_expected_lag():
    observation_date = pd.Timestamp("2026-01-01", tz="UTC")
    retrieval = observation_date + pd.Timedelta(days=60)  # 45 (1x) < 60 < 90 (2x)
    metadata = build_data_metadata(
        provider="FRED", provider_series_id="X", canonical_series_name="X",
        observation_date=observation_date, frequency="MONTHLY", unit="", source_url="",
        retrieval_timestamp=retrieval,
    )
    assert metadata.freshness_status == "AGING"
    assert 40 <= metadata.freshness_score < 100
    assert metadata.stale is False


def test_stale_monthly_data_beyond_2x_expected_lag():
    observation_date = pd.Timestamp("2025-01-01", tz="UTC")
    retrieval = observation_date + pd.Timedelta(days=200)  # well beyond 90 days (2x monthly lag)
    metadata = build_data_metadata(
        provider="FRED", provider_series_id="X", canonical_series_name="X",
        observation_date=observation_date, frequency="MONTHLY", unit="", source_url="",
        retrieval_timestamp=retrieval,
    )
    assert metadata.freshness_status == "STALE"
    assert metadata.stale is True


def test_stale_quarterly_data_uses_its_own_wider_expected_lag():
    observation_date = pd.Timestamp("2025-01-01", tz="UTC")
    retrieval = observation_date + pd.Timedelta(days=110)  # just over the 100-day quarterly lag
    metadata = build_data_metadata(
        provider="FRED", provider_series_id="GDPC1", canonical_series_name="Real GDP",
        observation_date=observation_date, frequency="QUARTERLY", unit="", source_url="",
        retrieval_timestamp=retrieval,
    )
    # 110 days is just over the 100-day expected lag but well under 200 (2x) -> AGING, not STALE.
    assert metadata.freshness_status == "AGING"


def test_unavailable_metadata_has_no_observation_date_and_is_marked_stale():
    metadata = unavailable_metadata(
        provider="FRED", provider_series_id="X", canonical_series_name="X",
        frequency="MONTHLY", unit="", source_url="", unavailable_reason="no key",
    )
    assert metadata.observation_date is None
    assert metadata.availability_status == "UNAVAILABLE"
    assert metadata.stale is True
    assert metadata.freshness_score is None
    assert metadata.unavailable_reason == "no key"


def test_release_date_anchors_freshness_when_available_instead_of_observation_date():
    observation_date = pd.Timestamp("2026-01-01", tz="UTC")
    release_date = pd.Timestamp("2026-07-01", tz="UTC")  # a late/revised release
    retrieval = release_date + pd.Timedelta(days=5)
    metadata = build_data_metadata(
        provider="FRED", provider_series_id="X", canonical_series_name="X",
        observation_date=observation_date, release_date=release_date, frequency="MONTHLY", unit="", source_url="",
        retrieval_timestamp=retrieval,
    )
    # If freshness were (incorrectly) anchored to observation_date, this would show as very STALE.
    assert metadata.freshness_status == "CURRENT"
