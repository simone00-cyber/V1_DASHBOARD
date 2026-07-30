"""Growth pillar: hard economic-activity data from FRED (Nonfarm Payrolls,
Industrial Production, Retail Sales, Real GDP, Leading Index).

ISM Manufacturing PMI is intentionally not used — it is proprietary and not
freely distributed anywhere (see `macro/provenance.py`). Hard activity data
is used instead.
"""

from __future__ import annotations

from typing import Any

from macro import config
from macro.confidence import compute_confidence
from macro.models import MacroPillar, MacroSeriesReading
from macro.series_router import resolve_series

SERIES_IDS: tuple[str, ...] = (
    "US_PAYROLLS",
    "US_INDUSTRIAL_PRODUCTION",
    "US_RETAIL_SALES",
    "US_REAL_GDP",
    "US_LEADING_INDEX",
)

_DIRECTION_LABEL = {
    "EXPANDING": "Growth is expanding",
    "MODERATING": "Growth is moderating",
    "CONTRACTING": "Growth is contracting",
    "UNKNOWN": "Growth read is unavailable",
}


def _direction(readings: tuple[MacroSeriesReading, ...]) -> str:
    yoy_values = [r.yoy_change_pct * 100.0 for r in readings if r.available and r.yoy_change_pct is not None]
    if not yoy_values:
        return "UNKNOWN"
    average = sum(yoy_values) / len(yoy_values)
    if average >= config.GROWTH_EXPANDING_YOY:
        return "EXPANDING"
    if average <= config.GROWTH_CONTRACTING_YOY:
        return "CONTRACTING"
    return "MODERATING"


def _summary(direction: str, readings: tuple[MacroSeriesReading, ...]) -> str:
    payrolls = next((r for r in readings if r.canonical_id == "US_PAYROLLS"), None)
    gdp = next((r for r in readings if r.canonical_id == "US_REAL_GDP"), None)
    bits: list[str] = []
    if payrolls is not None and payrolls.available and payrolls.yoy_change_pct is not None:
        bits.append(f"payrolls {payrolls.yoy_change_pct:+.1%} YoY")
    if gdp is not None and gdp.available and gdp.yoy_change_pct is not None:
        bits.append(f"real GDP {gdp.yoy_change_pct:+.1%} YoY")
    detail = "; ".join(bits) if bits else "insufficient data to characterize the trend"
    return f"{_DIRECTION_LABEL[direction]} ({detail})."


def build_growth_pillar(*, session: Any = None) -> MacroPillar:
    readings = tuple(resolve_series(series_id, session=session) for series_id in SERIES_IDS)
    direction = _direction(readings)
    summary = _summary(direction, readings)
    confidence = compute_confidence(pillar_name="GROWTH", readings=readings)
    return MacroPillar(name="GROWTH", direction=direction, summary=summary, readings=readings, confidence=confidence)
