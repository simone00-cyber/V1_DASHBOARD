from __future__ import annotations

import pandas as pd
import pytest

from data.providers.macro.fred import (
    FredConfigurationError,
    FredUnavailableError,
    fetch_observations,
    fetch_release_dates,
    fetch_releases,
    fetch_series_info,
)
from data.providers.macro.ny_fed import NyFedUnavailableError, fetch_reference_rate


class FakeResponse:
    def __init__(self, payload, *, ok: bool = True):
        self._payload = payload
        self._ok = ok

    def raise_for_status(self):
        if not self._ok:
            raise RuntimeError("HTTP error")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, rules):
        self._rules = rules  # list of (predicate(url) -> bool, outcome)

    def get(self, url, params=None, timeout=None):
        for predicate, outcome in self._rules:
            if predicate(url):
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
        raise AssertionError(f"Unexpected URL requested: {url}")


# --- FRED --------------------------------------------------------------------


def test_fred_missing_api_key_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(FredConfigurationError):
        fetch_observations("CPIAUCSL")


def test_fred_fetch_observations_parses_dates_and_preserves_gaps_as_nan():
    # The raw fetch keeps every observation (including FRED's "." no-data
    # marker as NaN) so gaps stay visible; normalization is what filters
    # NaNs when it needs an actual usable value.
    session = FakeSession(
        [
            (
                lambda u: u.endswith("/series/observations"),
                FakeResponse({"observations": [{"date": "2026-06-01", "value": "310.3"}, {"date": "2026-07-01", "value": "."}]}),
            ),
        ]
    )
    frame = fetch_observations("CPIAUCSL", api_key="test-key", session=session)
    assert len(frame) == 2
    assert frame["value"].iloc[0] == 310.3
    assert pd.isna(frame["value"].iloc[1])  # never fabricated into a number


def test_fred_request_failure_raises_unavailable_error():
    def raise_error(url, params=None, timeout=None):
        raise RuntimeError("connection reset")

    session = type("S", (), {"get": staticmethod(raise_error)})()
    with pytest.raises(FredUnavailableError):
        fetch_observations("CPIAUCSL", api_key="test-key", session=session)


def test_fred_fetch_series_info_returns_empty_dict_when_series_not_found():
    session = FakeSession([(lambda u: u.endswith("/series"), FakeResponse({"seriess": []}))])
    info = fetch_series_info("NOT_A_SERIES", api_key="test-key", session=session)
    assert info == {}


def test_fred_fetch_releases_returns_the_raw_list():
    session = FakeSession([(lambda u: u.endswith("/releases"), FakeResponse({"releases": [{"id": "10", "name": "Consumer Price Index"}]}))])
    releases = fetch_releases(api_key="test-key", session=session)
    assert releases == [{"id": "10", "name": "Consumer Price Index"}]


def test_fred_fetch_release_dates_never_fabricates_a_missing_date():
    session = FakeSession([(lambda u: u.endswith("/release/dates"), FakeResponse({"release_dates": []}))])
    dates = fetch_release_dates("10", api_key="test-key", session=session)
    assert dates.empty


# --- NY Fed --------------------------------------------------------------------


def test_ny_fed_fetch_reference_rate_parses_sofr():
    session = FakeSession(
        [
            (
                lambda u: "sofr" in u,
                FakeResponse({"refRates": [{"effectiveDate": "2026-07-29", "type": "SOFR", "percentRate": 3.65}]}),
            ),
        ]
    )
    frame = fetch_reference_rate("sofr", session=session)
    assert frame["value"].iloc[-1] == pytest.approx(3.65)


def test_ny_fed_unsupported_rate_type_raises_value_error():
    with pytest.raises(ValueError):
        fetch_reference_rate("bogus")


def test_ny_fed_request_failure_raises_unavailable_error():
    def raise_error(url, timeout=None):
        raise RuntimeError("connection reset")

    session = type("S", (), {"get": staticmethod(raise_error)})()
    with pytest.raises(NyFedUnavailableError):
        fetch_reference_rate("sofr", session=session)
