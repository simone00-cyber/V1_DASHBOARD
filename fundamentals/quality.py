"""Five 0-100 quality axis scores, each built only from metrics already
computed in `fundamentals/metrics.py` — never a new indicator. Any axis whose
required inputs are missing is `None`, with a reason explaining exactly what
was unavailable, instead of a guessed number."""

from __future__ import annotations

import pandas as pd

from fundamentals import config
from fundamentals.models import FinancialMetricsHistory, QualityScores, StatementSeries


def _latest(series: pd.Series) -> float | None:
    clean = series.dropna()
    return float(clean.iloc[-1]) if not clean.empty else None


def _mean_recent(series: pd.Series, lookback: int = 3) -> float | None:
    clean = series.dropna()
    if clean.empty:
        return None
    window = clean.iloc[-min(lookback, len(clean)):]
    return float(window.mean())


def _scale_higher_better(value: float | None, weak: float, strong: float) -> int | None:
    if value is None:
        return None
    if value <= weak:
        return 0
    if value >= strong:
        return 100
    return round((value - weak) / (strong - weak) * 100)


def _scale_lower_better(value: float | None, strong: float, weak: float) -> int | None:
    if value is None:
        return None
    if value <= strong:
        return 100
    if value >= weak:
        return 0
    return round((weak - value) / (weak - strong) * 100)


def _mean_available(scores: list[int | None]) -> int | None:
    available = [score for score in scores if score is not None]
    if not available:
        return None
    return round(sum(available) / len(available))


def _financial_strength(annual: StatementSeries) -> tuple[int | None, str]:
    current_ratio = _latest(annual.current_ratio)
    debt_to_equity = _latest(annual.debt_to_equity)
    interest_coverage = _latest(annual.interest_coverage)

    cr_score = _scale_higher_better(current_ratio, config.CURRENT_RATIO_ADEQUATE, config.CURRENT_RATIO_STRONG)
    de_score = _scale_lower_better(debt_to_equity, config.DEBT_TO_EQUITY_STRONG, config.DEBT_TO_EQUITY_WEAK)
    ic_score = _scale_higher_better(interest_coverage, config.INTEREST_COVERAGE_WEAK, config.INTEREST_COVERAGE_STRONG)

    score = _mean_available([cr_score, de_score, ic_score])
    if score is None:
        return None, "Insufficient balance-sheet data: current ratio, debt/equity and interest coverage are all unavailable."

    parts = []
    if current_ratio is not None:
        parts.append(f"current ratio {current_ratio:.2f}")
    if debt_to_equity is not None:
        parts.append(f"debt/equity {debt_to_equity:.2f}")
    if interest_coverage is not None:
        parts.append(f"interest coverage {interest_coverage:.1f}x")
    return score, "Based on " + ", ".join(parts) + "."


def _business_quality(annual: StatementSeries) -> tuple[int | None, str]:
    gross_margin = _latest(annual.gross_margin)
    gm_score = _scale_higher_better(gross_margin, config.GROSS_MARGIN_WEAK, config.GROSS_MARGIN_EXCELLENT)

    net_income_clean = annual.net_income.dropna()
    consistency_score = None
    if len(net_income_clean) >= 2:
        consistency_score = round(100 * float((net_income_clean > 0).mean()))

    score = _mean_available([gm_score, consistency_score])
    if score is None:
        return None, "Insufficient data: gross margin and multi-year net income history are both unavailable."

    parts = []
    if gross_margin is not None:
        parts.append(f"gross margin {gross_margin:.1%}")
    if consistency_score is not None:
        parts.append(f"profitable in {consistency_score}% of the available annual periods")
    return score, "Based on " + ", ".join(parts) + "."


def _growth_quality(annual: StatementSeries) -> tuple[int | None, str]:
    revenue_growth = _mean_recent(annual.revenue_growth)
    eps_growth = _mean_recent(annual.eps_growth)

    rev_score = _scale_higher_better(revenue_growth, config.REVENUE_GROWTH_WEAK, config.REVENUE_GROWTH_STRONG)
    eps_score = _scale_higher_better(eps_growth, config.REVENUE_GROWTH_WEAK, config.REVENUE_GROWTH_STRONG)

    score = _mean_available([rev_score, eps_score])
    if score is None:
        return None, "Insufficient history: fewer than two annual periods of revenue/EPS are available to measure growth."

    parts = []
    if revenue_growth is not None:
        parts.append(f"average recent revenue growth {revenue_growth:+.1%}")
    if eps_growth is not None:
        parts.append(f"average recent EPS growth {eps_growth:+.1%}")
    return score, "Based on " + ", ".join(parts) + "."


def _profitability(annual: StatementSeries) -> tuple[int | None, str]:
    net_margin = _latest(annual.net_margin)
    roe = _latest(annual.roe)

    nm_score = _scale_higher_better(net_margin, config.NET_MARGIN_WEAK, config.NET_MARGIN_EXCELLENT)
    roe_score = _scale_higher_better(roe, config.ROE_WEAK, config.ROE_EXCELLENT)

    score = _mean_available([nm_score, roe_score])
    if score is None:
        return None, "Insufficient data: net margin and return on equity are both unavailable."

    parts = []
    if net_margin is not None:
        parts.append(f"net margin {net_margin:.1%}")
    if roe is not None:
        parts.append(f"ROE {roe:.1%}")
    return score, "Based on " + ", ".join(parts) + "."


def _capital_allocation(annual: StatementSeries) -> tuple[int | None, str]:
    roe = _latest(annual.roe)
    roe_score = _scale_higher_better(roe, config.ROE_WEAK, config.ROE_EXCELLENT)

    de_clean = annual.debt_to_equity.dropna()
    leverage_delta = None
    leverage_score = None
    if len(de_clean) >= 2:
        leverage_delta = float(de_clean.iloc[-1] - de_clean.iloc[0])
        leverage_score = _scale_lower_better(leverage_delta, -0.05, 0.5)

    score = _mean_available([roe_score, leverage_score])
    if score is None:
        return None, "Insufficient data: return on equity and a multi-year debt/equity trend are both unavailable."

    parts = []
    if roe is not None:
        parts.append(f"current ROE {roe:.1%}")
    if leverage_delta is not None:
        direction = "reduced" if leverage_delta < 0 else "increased"
        parts.append(f"debt/equity {direction} by {abs(leverage_delta):.2f} over the available history")
    return score, "Based on " + ", ".join(parts) + "."


def build_quality_scores(metrics: FinancialMetricsHistory) -> QualityScores:
    annual = metrics.annual
    business_quality, business_quality_reason = _business_quality(annual)
    financial_strength, financial_strength_reason = _financial_strength(annual)
    growth_quality, growth_quality_reason = _growth_quality(annual)
    profitability, profitability_reason = _profitability(annual)
    capital_allocation, capital_allocation_reason = _capital_allocation(annual)

    return QualityScores(
        business_quality=business_quality,
        business_quality_reason=business_quality_reason,
        financial_strength=financial_strength,
        financial_strength_reason=financial_strength_reason,
        growth_quality=growth_quality,
        growth_quality_reason=growth_quality_reason,
        profitability=profitability,
        profitability_reason=profitability_reason,
        capital_allocation=capital_allocation,
        capital_allocation_reason=capital_allocation_reason,
    )
