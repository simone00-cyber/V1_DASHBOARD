from __future__ import annotations

import pandas as pd

from macro import config
from macro.growth import build_growth_pillar
from macro.inflation import build_inflation_pillar
from macro.liquidity import build_liquidity_pillar
from macro.metadata import build_data_metadata, unavailable_metadata
from macro.models import MacroSeriesReading


def _available(canonical_id, *, value=100.0, yoy=0.02, frequency="MONTHLY"):
    metadata = build_data_metadata(
        provider="FRED", provider_series_id=canonical_id, canonical_series_name=canonical_id,
        observation_date=pd.Timestamp("2026-07-01", tz="UTC"), frequency=frequency, unit="", source_url="",
        retrieval_timestamp=pd.Timestamp("2026-07-05", tz="UTC"),
    )
    return MacroSeriesReading(canonical_id, canonical_id, value, value * 0.98, yoy, None, metadata)


def _unavailable(canonical_id, *, frequency="MONTHLY"):
    metadata = unavailable_metadata(
        provider="FRED", provider_series_id=canonical_id, canonical_series_name=canonical_id,
        frequency=frequency, unit="", source_url="",
    )
    return MacroSeriesReading(canonical_id, canonical_id, None, None, None, None, metadata)


def test_growth_pillar_partially_available_degrades_gracefully_not_a_crash(monkeypatch):
    readings = {
        "US_PAYROLLS": _available("US_PAYROLLS", yoy=0.02),
        "US_INDUSTRIAL_PRODUCTION": _unavailable("US_INDUSTRIAL_PRODUCTION"),
        "US_RETAIL_SALES": _unavailable("US_RETAIL_SALES"),
        "US_REAL_GDP": _unavailable("US_REAL_GDP", frequency="QUARTERLY"),
        "US_LEADING_INDEX": _unavailable("US_LEADING_INDEX"),
    }
    monkeypatch.setattr("macro.growth.resolve_series", lambda canonical_id, session=None: readings[canonical_id])

    pillar = build_growth_pillar()

    assert pillar.direction in {"EXPANDING", "MODERATING", "CONTRACTING"}
    assert pillar.confidence.score < 100
    assert any(r.canonical_id == "US_PAYROLLS" and r.available for r in pillar.readings)


def test_growth_pillar_fully_unavailable_is_unknown_not_a_crash(monkeypatch):
    readings = {series_id: _unavailable(series_id, frequency="QUARTERLY" if series_id == "US_REAL_GDP" else "MONTHLY") for series_id in
                ("US_PAYROLLS", "US_INDUSTRIAL_PRODUCTION", "US_RETAIL_SALES", "US_REAL_GDP", "US_LEADING_INDEX")}
    monkeypatch.setattr("macro.growth.resolve_series", lambda canonical_id, session=None: readings[canonical_id])

    pillar = build_growth_pillar()

    assert pillar.direction == "UNKNOWN"
    assert pillar.confidence.label in {"LOW", "VERY LOW"}
    assert pillar.confidence.score < config.CONFIDENCE_LABEL_BANDS["MODERATE"]


def test_growth_conflicting_signals_reduce_confidence_versus_agreement(monkeypatch):
    agreeing = {
        "US_PAYROLLS": _available("US_PAYROLLS", yoy=0.02),
        "US_INDUSTRIAL_PRODUCTION": _available("US_INDUSTRIAL_PRODUCTION", yoy=0.03),
        "US_RETAIL_SALES": _available("US_RETAIL_SALES", yoy=0.01),
        "US_REAL_GDP": _available("US_REAL_GDP", yoy=0.02, frequency="QUARTERLY"),
        "US_LEADING_INDEX": _available("US_LEADING_INDEX", yoy=0.01),
    }
    conflicting = {
        "US_PAYROLLS": _available("US_PAYROLLS", yoy=0.05),
        "US_INDUSTRIAL_PRODUCTION": _available("US_INDUSTRIAL_PRODUCTION", yoy=-0.05),
        "US_RETAIL_SALES": _available("US_RETAIL_SALES", yoy=0.04),
        "US_REAL_GDP": _available("US_REAL_GDP", yoy=-0.03, frequency="QUARTERLY"),
        "US_LEADING_INDEX": _available("US_LEADING_INDEX", yoy=-0.02),
    }

    monkeypatch.setattr("macro.growth.resolve_series", lambda canonical_id, session=None: agreeing[canonical_id])
    agreeing_pillar = build_growth_pillar()
    monkeypatch.setattr("macro.growth.resolve_series", lambda canonical_id, session=None: conflicting[canonical_id])
    conflicting_pillar = build_growth_pillar()

    assert conflicting_pillar.confidence.score < agreeing_pillar.confidence.score


def test_inflation_direction_thresholds(monkeypatch):
    high_inflation = {
        "US_CPI_HEADLINE": _available("US_CPI_HEADLINE", yoy=0.05),
        "US_CPI_CORE": _available("US_CPI_CORE", yoy=0.04),
        "US_PCE_HEADLINE": _available("US_PCE_HEADLINE", yoy=0.04),
        "US_PCE_CORE": _available("US_PCE_CORE", yoy=0.04),
        "US_BREAKEVEN_5Y": _available("US_BREAKEVEN_5Y", value=2.5, yoy=None, frequency="DAILY"),
        "US_BREAKEVEN_10Y": _available("US_BREAKEVEN_10Y", value=2.4, yoy=None, frequency="DAILY"),
    }
    monkeypatch.setattr("macro.inflation.resolve_series", lambda canonical_id, session=None: high_inflation[canonical_id])
    pillar = build_inflation_pillar()
    assert pillar.direction == "ELEVATED"

    low_inflation = {**high_inflation}
    for key in ("US_CPI_HEADLINE", "US_CPI_CORE", "US_PCE_HEADLINE", "US_PCE_CORE"):
        low_inflation[key] = _available(key, yoy=0.01)
    monkeypatch.setattr("macro.inflation.resolve_series", lambda canonical_id, session=None: low_inflation[canonical_id])
    pillar = build_inflation_pillar()
    assert pillar.direction == "CONTAINED"


def test_liquidity_direction_is_driven_by_balance_sheet_not_sofr_level(monkeypatch):
    # SOFR/EFFR levels alone must never drive the direction — only the Fed
    # balance-sheet YoY trend does.
    readings = {
        "LIQUIDITY_SOFR": _available("LIQUIDITY_SOFR", value=3.65, yoy=None, frequency="DAILY"),
        "LIQUIDITY_EFFR": _available("LIQUIDITY_EFFR", value=3.63, yoy=None, frequency="DAILY"),
        "FED_TOTAL_ASSETS": _available("FED_TOTAL_ASSETS", yoy=-0.05, frequency="WEEKLY"),
        "FED_RESERVE_BALANCES": _unavailable("FED_RESERVE_BALANCES", frequency="WEEKLY"),
        "FED_ON_RRP": _unavailable("FED_ON_RRP", frequency="DAILY"),
    }
    monkeypatch.setattr("macro.liquidity.resolve_series", lambda canonical_id, session=None: readings[canonical_id])

    pillar = build_liquidity_pillar()

    assert pillar.direction == "TIGHTENING"
    assert "SOFR" in pillar.summary


def test_liquidity_unknown_direction_when_balance_sheet_missing_even_if_sofr_available(monkeypatch):
    readings = {
        "LIQUIDITY_SOFR": _available("LIQUIDITY_SOFR", value=3.65, yoy=None, frequency="DAILY"),
        "LIQUIDITY_EFFR": _unavailable("LIQUIDITY_EFFR", frequency="DAILY"),
        "FED_TOTAL_ASSETS": _unavailable("FED_TOTAL_ASSETS", frequency="WEEKLY"),
        "FED_RESERVE_BALANCES": _unavailable("FED_RESERVE_BALANCES", frequency="WEEKLY"),
        "FED_ON_RRP": _unavailable("FED_ON_RRP", frequency="DAILY"),
    }
    monkeypatch.setattr("macro.liquidity.resolve_series", lambda canonical_id, session=None: readings[canonical_id])

    pillar = build_liquidity_pillar()

    assert pillar.direction == "UNKNOWN"
    assert pillar.readings[0].available  # SOFR is still shown even though direction is unknown
