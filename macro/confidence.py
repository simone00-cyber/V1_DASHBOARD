"""Confidence methodology — evidence quality, never directional conviction.

`compute_confidence` combines named, weighted components (weights declared in
`macro/config.py::CONFIDENCE_WEIGHTS`) into one 0-100 score with a full,
always-inspectable breakdown — never an unexplained number. `directional_view`
(conviction) is computed entirely separately (`macro/executive_thesis.py`)
and must never be folded into this score.
"""

from __future__ import annotations

from macro import config
from macro.models import ConfidenceAssessment, MacroSeriesReading


def _coverage_component(readings: tuple[MacroSeriesReading, ...]) -> float:
    if not readings:
        return 0.0
    available = sum(1 for r in readings if r.available)
    return 100.0 * available / len(readings)


def _freshness_component(readings: tuple[MacroSeriesReading, ...]) -> float:
    scores = [r.metadata.freshness_score for r in readings if r.available and r.metadata.freshness_score is not None]
    return sum(scores) / len(scores) if scores else 0.0


def _provider_degradation_component(readings: tuple[MacroSeriesReading, ...]) -> float:
    available = [r for r in readings if r.available]
    if not available:
        return 0.0
    degraded = sum(1 for r in available if r.metadata.availability_status == "DEGRADED (FALLBACK)")
    return 100.0 * (1 - degraded / len(available))


def _internal_conflict_component(readings: tuple[MacroSeriesReading, ...]) -> float:
    """Do the available series agree in direction (sign of YoY change)?
    Full agreement scores 100; an even split scores 0."""
    directions = [
        (1 if r.yoy_change_pct > 0 else -1 if r.yoy_change_pct < 0 else 0)
        for r in readings
        if r.available and r.yoy_change_pct is not None
    ]
    if len(directions) < 2:
        return 100.0  # nothing to conflict with
    positive = sum(1 for d in directions if d > 0)
    negative = sum(1 for d in directions if d < 0)
    total = positive + negative
    if total == 0:
        return 100.0
    agreement = max(positive, negative) / total
    return 100.0 * (2 * agreement - 1)


def _revision_risk_component(readings: tuple[MacroSeriesReading, ...]) -> float:
    available = [r for r in readings if r.available]
    if not available:
        return 100.0
    revised = sum(1 for r in available if r.metadata.revised)
    return 100.0 * (1 - revised / len(available))


def _missing_critical_series(pillar_name: str, readings: tuple[MacroSeriesReading, ...]) -> list[str]:
    critical_ids = config.PILLAR_CRITICAL_SERIES.get(pillar_name, ())
    available_ids = {r.canonical_id for r in readings if r.available}
    return [cid for cid in critical_ids if cid not in available_ids]


def _label_for(score_int: int) -> str:
    bands = config.CONFIDENCE_LABEL_BANDS
    if score_int >= bands["HIGH"]:
        return "HIGH"
    if score_int >= bands["MODERATE"]:
        return "MODERATE"
    if score_int >= bands["LOW"]:
        return "LOW"
    return "VERY LOW"


def compute_confidence(
    *,
    pillar_name: str | None,
    readings: tuple[MacroSeriesReading, ...],
    cross_asset_confirmation: float | None = None,
) -> ConfidenceAssessment:
    """`cross_asset_confirmation` (0-100) is only meaningful once more than
    one pillar/asset-class exists to compare against — pass `None` at pillar
    level; the thesis-level caller supplies the real value."""

    components = {
        "coverage": _coverage_component(readings),
        "freshness": _freshness_component(readings),
        "provider_degradation": _provider_degradation_component(readings),
        "internal_conflict": _internal_conflict_component(readings),
        "revision_risk": _revision_risk_component(readings),
        "cross_asset_confirmation": cross_asset_confirmation if cross_asset_confirmation is not None else 100.0,
    }

    score = sum(components[name] * weight for name, weight in config.CONFIDENCE_WEIGHTS.items())
    score = max(0.0, min(100.0, score))

    notes: list[str] = []
    if pillar_name is not None:
        missing_critical = _missing_critical_series(pillar_name, readings)
        if missing_critical:
            score = min(score, float(config.CRITICAL_SERIES_MISSING_CAP))
            notes.append(
                f"Confidence capped at {config.CRITICAL_SERIES_MISSING_CAP}: "
                f"critical series unavailable ({', '.join(missing_critical)})."
            )

    degraded = [r.canonical_id for r in readings if r.available and r.metadata.availability_status == "DEGRADED (FALLBACK)"]
    if degraded:
        notes.append(f"Running on fallback provider for: {', '.join(degraded)}.")
    unavailable = [r.canonical_id for r in readings if not r.available]
    if unavailable:
        notes.append(f"Unavailable: {', '.join(unavailable)}.")

    score_int = int(round(score))
    return ConfidenceAssessment(score=score_int, label=_label_for(score_int), breakdown=components, notes=tuple(notes))
