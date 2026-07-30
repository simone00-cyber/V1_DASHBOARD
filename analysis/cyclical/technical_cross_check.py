"""Cross-engine comparison between the Technical Analysis read and the Cyclical
(Composite Momentum) hierarchy read for the same security.

This module compares two engines that already exist — it does not feed back into,
weight, or alter either engine's own output, and it introduces no new rule for either
one. It is explicitly a research-workspace synthesis layer, not part of the
documented Caruso methodology.
"""

from __future__ import annotations

from dataclasses import dataclass

from analysis.cyclical.models import HierarchyAssessment
from technical.assessment import TechnicalAssessment


@dataclass(frozen=True)
class CrossCheckRead:
    agreement: str
    summary: str


def _cyclical_direction(hierarchy: HierarchyAssessment) -> str:
    alignment = hierarchy.alignment.upper()
    if "BULLISH" in alignment:
        return "UP"
    if "BEARISH" in alignment:
        return "DOWN"
    return "MIXED"


def _technical_direction(technical: TechnicalAssessment) -> str:
    text = technical.current_assessment.lower()
    if "uptrend" in text:
        return "UP"
    if "downtrend" in text:
        return "DOWN"
    return "MIXED"


def build_technical_cyclical_cross_check(technical: TechnicalAssessment, hierarchy: HierarchyAssessment) -> CrossCheckRead:
    """Agree/diverge read between the two engines, framed as commentary rather than a signal."""
    technical_direction = _technical_direction(technical)
    cyclical_direction = _cyclical_direction(hierarchy)

    if technical_direction == "MIXED" or cyclical_direction == "MIXED":
        return CrossCheckRead(
            agreement="MIXED / NO CLEAR CYCLICAL READ",
            summary=(
                "The technical and cyclical reads cannot be cleanly cross-checked right now "
                f"(technical structure: {technical_direction.lower()}, cyclical hierarchy: {hierarchy.alignment.lower()})."
            ),
        )
    if technical_direction == cyclical_direction:
        return CrossCheckRead(
            agreement="CONFIRMS",
            summary=(
                f"The technical structure ({technical_direction.lower()}) agrees with the cyclical hierarchy "
                f"({hierarchy.alignment.lower()}) — the two engines reinforce each other."
            ),
        )
    return CrossCheckRead(
        agreement="DIVERGES",
        summary=(
            f"The technical structure ({technical_direction.lower()}) conflicts with the cyclical hierarchy "
            f"({hierarchy.alignment.lower()}) — treat this as a caution flag worth resolving before sizing a position."
        ),
    )
