from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from data.providers.fundamentals.models import RawFundamentalsBundle


@dataclass(frozen=True)
class StatementSeries:
    """Per-period computed metrics for one cadence (annual or quarterly).

    Every field is a `pd.Series` indexed by period-end date, oldest first.
    A metric that could not be computed for a given period is `NaN` at that
    position — never dropped, never filled with 0 or an estimate.
    """

    revenue: pd.Series
    gross_profit: pd.Series
    operating_income: pd.Series
    net_income: pd.Series
    ebitda: pd.Series
    eps_diluted: pd.Series
    operating_cash_flow: pd.Series
    capital_expenditure: pd.Series
    free_cash_flow: pd.Series
    total_assets: pd.Series
    total_liabilities: pd.Series
    total_equity: pd.Series
    current_assets: pd.Series
    current_liabilities: pd.Series
    cash_and_equivalents: pd.Series
    total_debt: pd.Series
    interest_expense: pd.Series

    # Derived (ratios/growth), same index convention as above.
    gross_margin: pd.Series
    operating_margin: pd.Series
    net_margin: pd.Series
    revenue_growth: pd.Series
    eps_growth: pd.Series
    net_debt: pd.Series
    current_ratio: pd.Series
    debt_to_equity: pd.Series
    interest_coverage: pd.Series
    roe: pd.Series
    roa: pd.Series


@dataclass(frozen=True)
class FinancialMetricsHistory:
    ticker: str
    annual: StatementSeries
    quarterly: StatementSeries
    # Latest-snapshot figures and valuation multiples, sourced from the
    # provider's quote/summary fields (`info`) — raw numeric fields only,
    # never Yahoo's analyst recommendation/target-price fields.
    current_price: Optional[float] = None
    market_cap: Optional[float] = None
    enterprise_value: Optional[float] = None
    shares_outstanding: Optional[float] = None
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    peg_ratio: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    price_to_sales: Optional[float] = None
    price_to_book: Optional[float] = None
    dividend_yield: Optional[float] = None


@dataclass(frozen=True)
class QualityScores:
    """Five 0-100 axis scores. `None` (with a stated reason) when the
    required inputs are missing — never guessed."""

    business_quality: Optional[int]
    business_quality_reason: str
    financial_strength: Optional[int]
    financial_strength_reason: str
    growth_quality: Optional[int]
    growth_quality_reason: str
    profitability: Optional[int]
    profitability_reason: str
    capital_allocation: Optional[int]
    capital_allocation_reason: str

    @property
    def available_scores(self) -> tuple[int, ...]:
        return tuple(
            score
            for score in (
                self.business_quality,
                self.financial_strength,
                self.growth_quality,
                self.profitability,
                self.capital_allocation,
            )
            if score is not None
        )


@dataclass(frozen=True)
class ValuationMethodResult:
    label: str
    bear: Optional[float]
    base: Optional[float]
    bull: Optional[float]
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class ValuationEstimate:
    current_price: Optional[float]
    methods: tuple[ValuationMethodResult, ...]
    bear_fair_value: Optional[float]
    base_fair_value: Optional[float]
    bull_fair_value: Optional[float]
    composite_fair_value: Optional[float]
    margin_of_safety: Optional[float]
    upside_pct: Optional[float]
    valuation_band: str


@dataclass(frozen=True)
class FundamentalRating:
    overall_score: Optional[int]
    rating_band: str
    recommendation: str


@dataclass(frozen=True)
class FundamentalNarrative:
    improved: tuple[str, ...]
    deteriorated: tuple[str, ...]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    risks: tuple[str, ...]
    opportunities: tuple[str, ...]
    thesis: str


@dataclass(frozen=True)
class MethodologyStatus:
    component: str
    status: str
    source: str
    note: str


@dataclass(frozen=True)
class FundamentalAnalysis:
    """The single object the UI consumes for the Fundamental Analysis section.

    When `sufficient` is `False`, every analytical field is `None` and the
    view must render `insufficiency_reason` (e.g. "Insufficient fundamental
    data for a reliable analysis.") instead of guessing. `raw` is always
    populated when available so the underlying statements can still be
    inspected even if the derived rating/valuation could not be computed.
    """

    ticker: str
    sufficient: bool
    insufficiency_reason: Optional[str]
    metrics: Optional[FinancialMetricsHistory]
    quality: Optional[QualityScores]
    valuation: Optional[ValuationEstimate]
    rating: Optional[FundamentalRating]
    narrative: Optional[FundamentalNarrative]
    raw: Optional[RawFundamentalsBundle]
