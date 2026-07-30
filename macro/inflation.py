"""Inflation pillar: CPI, Core CPI, PCE, Core PCE (the Fed's preferred
gauge) and 5Y/10Y TIPS breakeven inflation expectations, from FRED."""

from __future__ import annotations

from typing import Any

from macro import config
from macro.confidence import compute_confidence
from macro.models import MacroPillar, MacroSeriesReading
from macro.series_router import resolve_series

SERIES_IDS: tuple[str, ...] = (
    "US_CPI_HEADLINE",
    "US_CPI_CORE",
    "US_PCE_HEADLINE",
    "US_PCE_CORE",
    "US_BREAKEVEN_5Y",
    "US_BREAKEVEN_10Y",
)
# Breakevens are already a rate/level (not YoY-comparable in the same sense as
# a price index), so only the price-index series drive the direction read.
_YOY_DRIVEN_IDS = ("US_CPI_HEADLINE", "US_CPI_CORE", "US_PCE_HEADLINE", "US_PCE_CORE")

_DIRECTION_LABEL = {
    "ELEVATED": "Inflation is running elevated",
    "MODERATE": "Inflation is moderate",
    "CONTAINED": "Inflation is contained",
    "UNKNOWN": "Inflation read is unavailable",
}


def _direction(readings: tuple[MacroSeriesReading, ...]) -> str:
    yoy_values = [
        r.yoy_change_pct * 100.0
        for r in readings
        if r.canonical_id in _YOY_DRIVEN_IDS and r.available and r.yoy_change_pct is not None
    ]
    if not yoy_values:
        return "UNKNOWN"
    average = sum(yoy_values) / len(yoy_values)
    if average >= config.INFLATION_HIGH_YOY:
        return "ELEVATED"
    if average <= config.INFLATION_LOW_YOY:
        return "CONTAINED"
    return "MODERATE"


def _summary(direction: str, readings: tuple[MacroSeriesReading, ...]) -> str:
    cpi = next((r for r in readings if r.canonical_id == "US_CPI_HEADLINE"), None)
    core_pce = next((r for r in readings if r.canonical_id == "US_PCE_CORE"), None)
    bits: list[str] = []
    if cpi is not None and cpi.available and cpi.yoy_change_pct is not None:
        bits.append(f"CPI {cpi.yoy_change_pct:+.1%} YoY")
    if core_pce is not None and core_pce.available and core_pce.yoy_change_pct is not None:
        bits.append(f"core PCE {core_pce.yoy_change_pct:+.1%} YoY")
    detail = "; ".join(bits) if bits else "insufficient data to characterize the trend"
    return f"{_DIRECTION_LABEL[direction]} ({detail})."


def build_inflation_pillar(*, session: Any = None) -> MacroPillar:
    readings = tuple(resolve_series(series_id, session=session) for series_id in SERIES_IDS)
    direction = _direction(readings)
    summary = _summary(direction, readings)
    confidence = compute_confidence(pillar_name="INFLATION", readings=readings)
    return MacroPillar(name="INFLATION", direction=direction, summary=summary, readings=readings, confidence=confidence)
