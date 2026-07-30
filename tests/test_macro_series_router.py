from __future__ import annotations

import pytest

from macro.series_router import resolve_series


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, rules):
        self._rules = rules  # list of (predicate(url) -> bool, outcome-or-Exception)

    def get(self, url, params=None, timeout=None):
        for predicate, outcome in self._rules:
            if predicate(url):
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
        raise AssertionError(f"Unexpected URL requested: {url}")


def _fred_observations(values):
    return FakeResponse({"observations": [{"date": date, "value": value} for date, value in values]})


def _fred_series_info(last_updated="2026-07-29 08:00:00-05"):
    return FakeResponse({"seriess": [{"last_updated": last_updated}]})


def _ny_fed(values, rate_type="SOFR"):
    return FakeResponse({"refRates": [{"effectiveDate": date, "type": rate_type, "percentRate": value} for date, value in values]})


def test_fallback_activation_preserves_provenance_when_primary_fails(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "test-key")
    session = FakeSession(
        [
            (lambda u: "newyorkfed" in u, RuntimeError("NY Fed network down")),
            (lambda u: u.endswith("/series/observations"), _fred_observations([("2026-07-28", "3.64"), ("2026-07-29", "3.65")])),
            (lambda u: u.endswith("/series"), _fred_series_info()),
        ]
    )

    reading = resolve_series("LIQUIDITY_SOFR", session=session)

    assert reading.available
    assert reading.value == pytest.approx(3.65)
    assert reading.metadata.provider == "FRED"
    assert reading.metadata.provider_series_id == "SOFR"
    assert reading.metadata.availability_status == "DEGRADED (FALLBACK)"


def test_no_equivalent_fallback_marks_unavailable_never_substitutes(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "test-key")
    session = FakeSession([(lambda u: u.endswith("/series/observations"), RuntimeError("FRED down"))])

    reading = resolve_series("US_CPI_HEADLINE", session=session)  # CPI has no configured fallback

    assert not reading.available
    assert reading.metadata.availability_status == "UNAVAILABLE"
    assert reading.metadata.unavailable_reason is not None
    assert reading.value is None


def test_one_provider_failing_does_not_affect_an_independent_series(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "test-key")
    session = FakeSession([(lambda u: "newyorkfed" in u, _ny_fed([("2026-07-28", "3.64"), ("2026-07-29", "3.65")]))])

    reading = resolve_series("LIQUIDITY_SOFR", session=session)

    assert reading.available
    assert reading.metadata.provider == "NY_FED"
    assert reading.metadata.availability_status == "AVAILABLE"


def test_unknown_canonical_id_raises_key_error():
    with pytest.raises(KeyError):
        resolve_series("NOT_A_REAL_SERIES")


def test_missing_fred_api_key_degrades_to_unavailable_not_a_crash(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    reading = resolve_series("US_CPI_HEADLINE")
    assert not reading.available
    assert "FRED_API_KEY" in (reading.metadata.unavailable_reason or "")
