from __future__ import annotations

import pandas as pd

import macro.calendar as calendar_module
from macro import config
from macro.calendar import build_upcoming_releases


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, releases_payload, dates_payload_by_release_id):
        self._releases_payload = releases_payload
        self._dates_payload_by_release_id = dates_payload_by_release_id

    def get(self, url, params=None, timeout=None):
        if url.endswith("/releases"):
            return FakeResponse({"releases": self._releases_payload})
        if url.endswith("/release/dates"):
            release_id = params["release_id"]
            return FakeResponse({"release_dates": self._dates_payload_by_release_id.get(release_id, [])})
        raise AssertionError(f"Unexpected URL: {url}")


def test_missing_expected_release_is_omitted_not_invented(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "test-key")
    calendar_module._release_id_cache.clear()
    releases = [{"id": "10", "name": "Consumer Price Index"}]  # only CPI resolvable
    dates = {"10": [{"release_id": "10", "date": (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=5)).strftime("%Y-%m-%d")}]}
    session = FakeSession(releases, dates)

    events = build_upcoming_releases(session=session)

    names = {event.release_name for event in events}
    assert "Consumer Price Index" in names
    assert "Gross Domestic Product" not in names  # not resolvable -> omitted, never guessed


def test_importance_lookup_is_a_documented_truth_table():
    assert config.RELEASE_IMPORTANCE["CPI"] == "HIGH"
    assert config.RELEASE_IMPORTANCE["EMPLOYMENT_SITUATION"] == "HIGH"
    assert config.RELEASE_IMPORTANCE["GDP"] == "HIGH"
    assert config.RELEASE_IMPORTANCE["RETAIL_SALES"] == "MEDIUM"
    assert config.RELEASE_IMPORTANCE["INDUSTRIAL_PRODUCTION"] == "MEDIUM"
    assert config.RELEASE_IMPORTANCE["PCE"] == "MEDIUM"
    assert set(config.RELEASE_IMPORTANCE) == set(config.FRED_RELEASES)


def test_scheduled_time_is_never_inferred(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "test-key")
    calendar_module._release_id_cache.clear()
    releases = [{"id": "10", "name": "Consumer Price Index"}]
    dates = {"10": [{"release_id": "10", "date": (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=5)).strftime("%Y-%m-%d")}]}
    session = FakeSession(releases, dates)

    events = build_upcoming_releases(session=session)

    assert events
    assert all(event.scheduled_time is None for event in events)


def test_no_fred_key_returns_empty_calendar_gracefully(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    calendar_module._release_id_cache.clear()
    events = build_upcoming_releases()
    assert events == ()


def test_events_outside_the_lookback_lookahead_horizon_are_excluded(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "test-key")
    calendar_module._release_id_cache.clear()
    releases = [{"id": "10", "name": "Consumer Price Index"}]
    far_future = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    dates = {"10": [{"release_id": "10", "date": far_future}]}
    session = FakeSession(releases, dates)

    events = build_upcoming_releases(session=session, lookahead_days=60)

    assert events == ()
