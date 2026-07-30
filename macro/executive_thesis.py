"""The Executive Market Thesis — the single object Command Center and Market
Intelligence both render (at different verbosity). Combines the existing
regime engine (`analysis/regime/*`, untouched) with the new
Growth/Inflation/Liquidity pillars and the Cross-Asset Confirmation layer.

`directional_view` (conviction) and `confidence` (evidence quality) are
computed independently and must never be merged into one number.
"""

from __future__ import annotations

import itertools

import pandas as pd

from macro.confidence import compute_confidence
from macro.models import CrossAssetSnapshot, ExecutiveMarketThesis, MacroPillar

# Maps each pillar's direction label to a -1/0/+1 directional contribution.
# Elevated inflation and tightening liquidity are headwinds (negative), the
# same convention a macro strategist would use.
_PILLAR_DIRECTIONAL_SCORE: dict[str, dict[str, int]] = {
    "GROWTH": {"EXPANDING": 1, "MODERATING": 0, "CONTRACTING": -1, "UNKNOWN": 0},
    "INFLATION": {"CONTAINED": 1, "MODERATE": 0, "ELEVATED": -1, "UNKNOWN": 0},
    "LIQUIDITY": {"EXPANDING": 1, "STABLE": 0, "TIGHTENING": -1, "UNKNOWN": 0},
}

_OPPORTUNITY_BY_PILLAR_DIRECTION: dict[tuple[str, str], str] = {
    ("GROWTH", "EXPANDING"): "Expanding growth data (payrolls, industrial production) may support cyclical and credit-sensitive sectors.",
    ("LIQUIDITY", "EXPANDING"): "Expanding Fed balance-sheet liquidity is typically a tailwind for risk assets broadly.",
    ("INFLATION", "CONTAINED"): "Contained inflation reduces the pressure for further policy tightening.",
}
_RISK_BY_PILLAR_DIRECTION: dict[tuple[str, str], str] = {
    ("GROWTH", "CONTRACTING"): "Contracting growth data raises recession risk and pressures cyclical earnings.",
    ("INFLATION", "ELEVATED"): "Elevated inflation keeps the door open to further policy tightening — a headwind for duration and valuations.",
    ("LIQUIDITY", "TIGHTENING"): "Tightening liquidity conditions have historically preceded stress in the most leveraged, most rate-sensitive assets.",
}


def _pillar_score(pillar: MacroPillar) -> int:
    return _PILLAR_DIRECTIONAL_SCORE.get(pillar.name, {}).get(pillar.direction, 0)


def _directional_view(regime_results: dict, pillars: tuple[MacroPillar, ...]) -> str:
    tactical = regime_results.get("TACTICAL")
    regime_score = tactical.score if tactical is not None else 0.0
    pillar_score = sum(_pillar_score(p) for p in pillars)
    combined = (regime_score * 2.0) + pillar_score
    if combined >= 1.0:
        return "RISK-ON"
    if combined <= -1.0:
        return "RISK-OFF"
    return "MIXED"


def _headline(directional_view: str, confidence_label: str) -> str:
    phrase = {
        "RISK-ON": "The cross-asset read is constructive",
        "RISK-OFF": "The cross-asset read is defensive",
        "MIXED": "The cross-asset read is mixed",
    }[directional_view]
    return f"{phrase}, with {confidence_label.lower()} confidence in the underlying data."


def _what_changed(regime_results: dict, pillars: tuple[MacroPillar, ...]) -> tuple[str, ...]:
    items: list[str] = []
    tactical = regime_results.get("TACTICAL")
    if tactical is not None and tactical.diagnosis != tactical.previous_diagnosis:
        items.append(f"Tactical market regime shifted from {tactical.previous_diagnosis} to {tactical.diagnosis}.")
    for pillar in pillars:
        if pillar.direction != "UNKNOWN":
            items.append(pillar.summary)
    return tuple(items) if items else ("No significant change detected since the last observation.",)


def _why_it_matters(pillars: tuple[MacroPillar, ...], cross_asset: CrossAssetSnapshot) -> tuple[str, ...]:
    items: list[str] = []
    for pillar in pillars:
        opportunity = _OPPORTUNITY_BY_PILLAR_DIRECTION.get((pillar.name, pillar.direction))
        risk = _RISK_BY_PILLAR_DIRECTION.get((pillar.name, pillar.direction))
        if opportunity:
            items.append(opportunity)
        if risk:
            items.append(risk)
    diverging = [item.asset_class for item in cross_asset.items if item.confirms_regime is False]
    if diverging:
        items.append(f"{', '.join(diverging)} currently diverge from the broader regime read — worth monitoring for confirmation.")
    return tuple(items) if items else ("No pillar currently stands out enough to materially change the outlook.",)


def _cross_asset_implications(cross_asset: CrossAssetSnapshot) -> tuple[str, ...]:
    lines = [f"{item.asset_class}: {item.what_changed}" for item in cross_asset.items]
    if cross_asset.agreement_ratio is not None:
        lines.append(f"{cross_asset.agreement_ratio:.0%} of cross-asset signals confirm the prevailing regime read.")
    return tuple(lines)


def _top_opportunities(pillars: tuple[MacroPillar, ...]) -> tuple[str, ...]:
    return tuple(
        text
        for (pillar_name, direction), text in _OPPORTUNITY_BY_PILLAR_DIRECTION.items()
        if any(p.name == pillar_name and p.direction == direction for p in pillars)
    ) or ("No standout macro-level opportunity identified from the current data.",)


def _major_risks(pillars: tuple[MacroPillar, ...], cross_asset: CrossAssetSnapshot) -> tuple[str, ...]:
    risks = [
        text
        for (pillar_name, direction), text in _RISK_BY_PILLAR_DIRECTION.items()
        if any(p.name == pillar_name and p.direction == direction for p in pillars)
    ]
    diverging = [item for item in cross_asset.items if item.confirms_regime is False]
    for item in diverging:
        risks.append(f"{item.asset_class} diverges from the broader regime — {item.what_changed}")
    return tuple(risks) if risks else ("No standout macro-level risk identified from the current data.",)


def _freshness_summary(pillars: tuple[MacroPillar, ...]) -> str:
    parts: list[str] = []
    for pillar in pillars:
        statuses = [r.metadata.freshness_status for r in pillar.readings if r.available]
        if not statuses:
            parts.append(f"{pillar.name.title()}: no data available")
            continue
        worst = "STALE" if "STALE" in statuses else "AGING" if "AGING" in statuses else "CURRENT"
        parts.append(f"{pillar.name.title()}: {worst}")
    return "; ".join(parts) if parts else "Freshness unavailable."


def build_executive_market_thesis(
    *,
    regime_results: dict,
    growth: MacroPillar,
    inflation: MacroPillar,
    liquidity: MacroPillar,
    cross_asset: CrossAssetSnapshot,
) -> ExecutiveMarketThesis:
    pillars = (growth, inflation, liquidity)
    directional_view = _directional_view(regime_results, pillars)

    all_readings = tuple(itertools.chain.from_iterable(p.readings for p in pillars))
    cross_asset_confirmation = cross_asset.agreement_ratio * 100.0 if cross_asset.agreement_ratio is not None else None
    confidence = compute_confidence(
        pillar_name=None, readings=all_readings, cross_asset_confirmation=cross_asset_confirmation
    )

    return ExecutiveMarketThesis(
        headline=_headline(directional_view, confidence.label),
        directional_view=directional_view,
        confidence=confidence,
        what_changed=_what_changed(regime_results, pillars),
        why_it_matters=_why_it_matters(pillars, cross_asset),
        cross_asset_implications=_cross_asset_implications(cross_asset),
        top_opportunities=_top_opportunities(pillars),
        major_risks=_major_risks(pillars, cross_asset),
        freshness_summary=_freshness_summary(pillars),
        generated_at=pd.Timestamp.now(tz="UTC"),
    )
