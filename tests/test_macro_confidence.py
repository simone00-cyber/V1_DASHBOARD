from __future__ import annotations

import pandas as pd

from macro import config
from macro.confidence import compute_confidence
from macro.metadata import build_data_metadata, unavailable_metadata
from macro.models import MacroSeriesReading


def _reading(canonical_id, *, value=100.0, yoy=0.02, availability="AVAILABLE", revised=False):
    if availability == "UNAVAILABLE":
        metadata = unavailable_metadata(
            provider="FRED", provider_series_id=canonical_id, canonical_series_name=canonical_id,
            frequency="MONTHLY", unit="", source_url="",
        )
        return MacroSeriesReading(canonical_id, canonical_id, None, None, None, None, metadata)
    metadata = build_data_metadata(
        provider="FRED", provider_series_id=canonical_id, canonical_series_name=canonical_id,
        observation_date=pd.Timestamp("2026-07-01", tz="UTC"), frequency="MONTHLY", unit="", source_url="",
        retrieval_timestamp=pd.Timestamp("2026-07-05", tz="UTC"), revised=revised, availability_status=availability,
    )
    return MacroSeriesReading(canonical_id, canonical_id, value, value * 0.98, yoy, None, metadata)


def test_full_coverage_and_agreement_yields_high_confidence():
    readings = tuple(_reading(f"S{i}", yoy=0.02) for i in range(4))
    assessment = compute_confidence(pillar_name=None, readings=readings)
    assert assessment.score >= 75
    assert assessment.label == "HIGH"


def test_zero_coverage_yields_a_low_confidence_band():
    # Total unavailability still gets "benefit of doubt" on the components
    # that measure *bad* evidence (internal conflict, revision risk) since
    # there is nothing to conflict with or be revised — so this lands at
    # LOW, not the absolute VERY LOW floor, which is reserved for cases with
    # some positively bad evidence rather than just an absence of data.
    readings = tuple(_reading(f"S{i}", availability="UNAVAILABLE") for i in range(4))
    assessment = compute_confidence(pillar_name=None, readings=readings)
    assert assessment.score < config.CONFIDENCE_LABEL_BANDS["MODERATE"]
    assert assessment.label in {"LOW", "VERY LOW"}
    assert assessment.breakdown["coverage"] == 0.0
    assert assessment.breakdown["freshness"] == 0.0


def test_conflicting_directions_score_lower_than_agreeing_directions():
    agreeing = tuple(_reading(f"S{i}", yoy=0.02) for i in range(4))
    conflicting = (
        _reading("S0", yoy=0.02), _reading("S1", yoy=-0.02),
        _reading("S2", yoy=0.02), _reading("S3", yoy=-0.02),
    )
    agree_score = compute_confidence(pillar_name=None, readings=agreeing).score
    conflict_score = compute_confidence(pillar_name=None, readings=conflicting).score
    assert conflict_score < agree_score


def test_missing_critical_series_caps_score_and_explains_why():
    readings = (_reading("US_INDUSTRIAL_PRODUCTION", yoy=0.02), _reading("US_RETAIL_SALES", yoy=0.02))
    # US_PAYROLLS (GROWTH's critical series) is entirely absent from this tuple.
    assessment = compute_confidence(pillar_name="GROWTH", readings=readings)
    assert assessment.score <= config.CRITICAL_SERIES_MISSING_CAP
    assert any("capped" in note.lower() for note in assessment.notes)


def test_no_critical_series_defined_for_pillar_applies_no_cap():
    readings = tuple(_reading(f"S{i}") for i in range(3))
    assessment = compute_confidence(pillar_name="NOT_A_PILLAR", readings=readings)
    assert not any("capped" in note.lower() for note in assessment.notes)


def test_degraded_fallback_readings_reduce_confidence():
    clean = tuple(_reading(f"S{i}") for i in range(3))
    degraded = tuple(_reading(f"S{i}", availability="DEGRADED (FALLBACK)") for i in range(3))
    clean_score = compute_confidence(pillar_name=None, readings=clean).score
    degraded_score = compute_confidence(pillar_name=None, readings=degraded).score
    assert degraded_score < clean_score


def test_revised_readings_reduce_confidence():
    clean = tuple(_reading(f"S{i}", revised=False) for i in range(3))
    revised = tuple(_reading(f"S{i}", revised=True) for i in range(3))
    clean_score = compute_confidence(pillar_name=None, readings=clean).score
    revised_score = compute_confidence(pillar_name=None, readings=revised).score
    assert revised_score < clean_score


def test_cross_asset_confirmation_raises_thesis_level_confidence():
    readings = tuple(_reading(f"S{i}") for i in range(3))
    low = compute_confidence(pillar_name=None, readings=readings, cross_asset_confirmation=20.0)
    high = compute_confidence(pillar_name=None, readings=readings, cross_asset_confirmation=100.0)
    assert high.score > low.score


def test_directional_conviction_is_never_part_of_the_confidence_breakdown():
    readings = tuple(_reading(f"S{i}") for i in range(3))
    assessment = compute_confidence(pillar_name=None, readings=readings)
    assert set(assessment.breakdown) == set(config.CONFIDENCE_WEIGHTS)
    assert "directional_view" not in assessment.breakdown
    assert "conviction" not in assessment.breakdown
