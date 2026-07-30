from __future__ import annotations

import pandas as pd

from analysis.regime.models import RegimeLayer, RegimePillar
from macro.executive_thesis import build_executive_market_thesis
from macro.models import ConfidenceAssessment, CrossAssetItem, CrossAssetSnapshot, MacroPillar, MacroSeriesReading
from macro.metadata import build_data_metadata


def _confidence(score=80, label="HIGH") -> ConfidenceAssessment:
    return ConfidenceAssessment(score=score, label=label, breakdown={}, notes=())


def _reading(canonical_id: str) -> MacroSeriesReading:
    metadata = build_data_metadata(
        provider="FRED", provider_series_id=canonical_id, canonical_series_name=canonical_id,
        observation_date=pd.Timestamp("2026-07-01", tz="UTC"), frequency="MONTHLY", unit="", source_url="",
        retrieval_timestamp=pd.Timestamp("2026-07-05", tz="UTC"),
    )
    return MacroSeriesReading(canonical_id, canonical_id, 100.0, 98.0, 0.02, 0.01, metadata)


def _pillar(name: str, direction: str) -> MacroPillar:
    return MacroPillar(name=name, direction=direction, summary=f"{name} is {direction.lower()}.", readings=(_reading(name),), confidence=_confidence())


def _regime_results(score: float, diagnosis="STABLE", previous="STABLE") -> dict:
    layer = RegimeLayer(
        key="TACTICAL", title="Tactical", horizon="n/a", diagnosis=diagnosis, score=score,
        previous_diagnosis=previous, previous_score=0.0, pillars=[],
    )
    return {"TACTICAL": layer}


def _empty_cross_asset() -> CrossAssetSnapshot:
    return CrossAssetSnapshot(items=(), agreement_ratio=None)


def test_risk_on_when_regime_and_pillars_are_favorable():
    thesis = build_executive_market_thesis(
        regime_results=_regime_results(1.0),
        growth=_pillar("GROWTH", "EXPANDING"),
        inflation=_pillar("INFLATION", "CONTAINED"),
        liquidity=_pillar("LIQUIDITY", "EXPANDING"),
        cross_asset=_empty_cross_asset(),
    )
    assert thesis.directional_view == "RISK-ON"


def test_risk_off_when_regime_and_pillars_are_unfavorable():
    thesis = build_executive_market_thesis(
        regime_results=_regime_results(-1.0),
        growth=_pillar("GROWTH", "CONTRACTING"),
        inflation=_pillar("INFLATION", "ELEVATED"),
        liquidity=_pillar("LIQUIDITY", "TIGHTENING"),
        cross_asset=_empty_cross_asset(),
    )
    assert thesis.directional_view == "RISK-OFF"


def test_mixed_signals_yield_mixed_view():
    thesis = build_executive_market_thesis(
        regime_results=_regime_results(0.0),
        growth=_pillar("GROWTH", "EXPANDING"),
        inflation=_pillar("INFLATION", "ELEVATED"),
        liquidity=_pillar("LIQUIDITY", "STABLE"),
        cross_asset=_empty_cross_asset(),
    )
    assert thesis.directional_view == "MIXED"


def test_confidence_and_directional_view_are_independent_fields():
    # Two theses can share the exact same confidence inputs while disagreeing
    # completely on direction — proves conviction and evidence quality never merge.
    bullish = build_executive_market_thesis(
        regime_results=_regime_results(1.0), growth=_pillar("GROWTH", "EXPANDING"),
        inflation=_pillar("INFLATION", "CONTAINED"), liquidity=_pillar("LIQUIDITY", "EXPANDING"),
        cross_asset=_empty_cross_asset(),
    )
    bearish = build_executive_market_thesis(
        regime_results=_regime_results(-1.0), growth=_pillar("GROWTH", "CONTRACTING"),
        inflation=_pillar("INFLATION", "ELEVATED"), liquidity=_pillar("LIQUIDITY", "TIGHTENING"),
        cross_asset=_empty_cross_asset(),
    )
    assert bullish.directional_view != bearish.directional_view
    # Both were built from structurally identical readings (same
    # availability/freshness/coverage) — only the pillar direction labels
    # differ, which do not feed into confidence at all. Confidence must
    # therefore come out exactly equal despite the opposite conviction.
    assert bullish.confidence.score == bearish.confidence.score


def test_top_opportunities_and_major_risks_trace_to_pillar_directions():
    thesis = build_executive_market_thesis(
        regime_results=_regime_results(0.5), growth=_pillar("GROWTH", "EXPANDING"),
        inflation=_pillar("INFLATION", "ELEVATED"), liquidity=_pillar("LIQUIDITY", "STABLE"),
        cross_asset=_empty_cross_asset(),
    )
    assert any("expanding growth" in item.lower() for item in thesis.top_opportunities)
    assert any("elevated inflation" in item.lower() for item in thesis.major_risks)


def test_diverging_cross_asset_items_appear_as_risks():
    cross_asset = CrossAssetSnapshot(
        items=(CrossAssetItem(asset_class="CREDIT", verdict="NEGATIVE", what_changed="Spreads widened.", confirms_regime=False),),
        agreement_ratio=0.0,
    )
    thesis = build_executive_market_thesis(
        regime_results=_regime_results(1.0), growth=_pillar("GROWTH", "MODERATING"),
        inflation=_pillar("INFLATION", "MODERATE"), liquidity=_pillar("LIQUIDITY", "STABLE"),
        cross_asset=cross_asset,
    )
    assert any("CREDIT" in risk for risk in thesis.major_risks)


def test_what_changed_reflects_regime_transition():
    thesis = build_executive_market_thesis(
        regime_results=_regime_results(0.5, diagnosis="IMPROVING", previous="DETERIORATING"),
        growth=_pillar("GROWTH", "UNKNOWN"), inflation=_pillar("INFLATION", "UNKNOWN"),
        liquidity=_pillar("LIQUIDITY", "UNKNOWN"), cross_asset=_empty_cross_asset(),
    )
    assert any("DETERIORATING" in item and "IMPROVING" in item for item in thesis.what_changed)


def test_command_center_and_market_intelligence_use_the_identical_thesis_builder():
    """Structural guarantee against duplicated analytical logic: Command
    Center must call the exact same function object Market Intelligence
    does, not a second, separately-maintained narrative builder."""
    import views.macro as macro_view
    import views.overview as overview_view

    assert overview_view.build_thesis_bundle is macro_view.build_thesis_bundle
