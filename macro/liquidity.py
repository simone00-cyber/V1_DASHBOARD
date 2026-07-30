"""Liquidity pillar: SOFR/EFFR reference rates (NY Fed, keyless) and Fed
balance-sheet aggregates — Total Assets, Reserve Balances, ON RRP (FRED)."""

from __future__ import annotations

from typing import Any

from macro import config
from macro.confidence import compute_confidence
from macro.models import MacroPillar, MacroSeriesReading
from macro.series_router import resolve_series

SERIES_IDS: tuple[str, ...] = (
    "LIQUIDITY_SOFR",
    "LIQUIDITY_EFFR",
    "FED_TOTAL_ASSETS",
    "FED_RESERVE_BALANCES",
    "FED_ON_RRP",
)

_DIRECTION_LABEL = {
    "TIGHTENING": "Liquidity conditions are tightening",
    "STABLE": "Liquidity conditions are stable",
    "EXPANDING": "Liquidity conditions are expanding",
    "UNKNOWN": "Liquidity read is unavailable",
}


def _direction(readings: tuple[MacroSeriesReading, ...]) -> str:
    # Direction is driven by the Fed balance-sheet trend, not by SOFR/EFFR
    # levels (a short-term rate level isn't a coherent "growth" signal).
    balance_sheet = next((r for r in readings if r.canonical_id == "FED_TOTAL_ASSETS"), None)
    if balance_sheet is None or not balance_sheet.available or balance_sheet.yoy_change_pct is None:
        return "UNKNOWN"
    yoy_pct = balance_sheet.yoy_change_pct * 100.0
    if yoy_pct <= config.LIQUIDITY_TIGHTENING_BALANCE_SHEET_YOY:
        return "TIGHTENING"
    if yoy_pct >= config.LIQUIDITY_EXPANDING_BALANCE_SHEET_YOY:
        return "EXPANDING"
    return "STABLE"


def _summary(direction: str, readings: tuple[MacroSeriesReading, ...]) -> str:
    sofr = next((r for r in readings if r.canonical_id == "LIQUIDITY_SOFR"), None)
    balance_sheet = next((r for r in readings if r.canonical_id == "FED_TOTAL_ASSETS"), None)
    bits: list[str] = []
    if sofr is not None and sofr.available and sofr.value is not None:
        bits.append(f"SOFR {sofr.value:.2f}%")
    if balance_sheet is not None and balance_sheet.available and balance_sheet.yoy_change_pct is not None:
        bits.append(f"Fed balance sheet {balance_sheet.yoy_change_pct:+.1%} YoY")
    detail = "; ".join(bits) if bits else "insufficient data to characterize the trend"
    return f"{_DIRECTION_LABEL[direction]} ({detail})."


def build_liquidity_pillar(*, session: Any = None) -> MacroPillar:
    readings = tuple(resolve_series(series_id, session=session) for series_id in SERIES_IDS)
    direction = _direction(readings)
    summary = _summary(direction, readings)
    confidence = compute_confidence(pillar_name="LIQUIDITY", readings=readings)
    return MacroPillar(name="LIQUIDITY", direction=direction, summary=summary, readings=readings, confidence=confidence)
