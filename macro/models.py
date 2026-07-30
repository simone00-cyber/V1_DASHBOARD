from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from macro.metadata import DataMetadata


@dataclass(frozen=True)
class MacroSeriesReading:
    """One normalized data point. Analytics never see a raw provider
    response — only this. `metadata` carries full provenance/freshness."""

    canonical_id: str
    label: str
    value: float | None
    previous_value: float | None
    yoy_change_pct: float | None
    mom_change_pct: float | None
    metadata: DataMetadata

    @property
    def available(self) -> bool:
        return self.value is not None and self.metadata.availability_status != "UNAVAILABLE"


@dataclass(frozen=True)
class ConfidenceAssessment:
    """Evidence-quality score — deliberately NOT a directional signal. See
    `macro/confidence.py` for the documented weighting methodology."""

    score: int  # 0-100
    label: str  # HIGH / MODERATE / LOW / VERY LOW
    breakdown: dict[str, float]  # component name -> component score (0-100)
    notes: tuple[str, ...]


@dataclass(frozen=True)
class MacroPillar:
    """Shared shape for the Growth, Inflation and Liquidity pillars — same
    reuse pattern as `analysis/regime/models.py::RegimePillar`."""

    name: str  # "GROWTH" / "INFLATION" / "LIQUIDITY"
    direction: str  # e.g. EXPANDING / DECELERATING / CONTRACTING / UNKNOWN
    summary: str
    readings: tuple[MacroSeriesReading, ...]
    confidence: ConfidenceAssessment


@dataclass(frozen=True)
class CrossAssetItem:
    asset_class: str
    verdict: str
    what_changed: str
    confirms_regime: bool | None  # True=confirms, False=diverges, None=insufficient data


@dataclass(frozen=True)
class CrossAssetSnapshot:
    items: tuple[CrossAssetItem, ...]
    agreement_ratio: float | None


@dataclass(frozen=True)
class CalendarEvent:
    release_name: str
    country_region: str
    scheduled_date: pd.Timestamp | None
    scheduled_time: str | None  # never inferred — None when the provider gives only a date
    reference_period: str | None
    importance: str  # HIGH / MEDIUM
    affected_pillar: str
    current_relevance: str
    source: str


@dataclass(frozen=True)
class MethodologyStatus:
    """Same coverage-table convention as `fundamentals/models.py` and
    `analysis/cyclical/models.py` — each package keeps its own copy of this
    tiny shape rather than sharing a cross-package base type."""

    component: str
    status: str
    source: str
    note: str


@dataclass(frozen=True)
class ExecutiveMarketThesis:
    """The single object both Command Center and Market Intelligence render
    — at different verbosity, never with separate analytical logic."""

    headline: str
    directional_view: str  # RISK-ON / RISK-OFF / MIXED — conviction
    confidence: ConfidenceAssessment  # evidence quality — kept separate from conviction
    what_changed: tuple[str, ...]
    why_it_matters: tuple[str, ...]
    cross_asset_implications: tuple[str, ...]
    top_opportunities: tuple[str, ...]  # asset-class level, never individual stock picks
    major_risks: tuple[str, ...]
    freshness_summary: str
    generated_at: pd.Timestamp
