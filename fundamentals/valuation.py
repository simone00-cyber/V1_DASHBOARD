"""Bear/Base/Bull fair value from two independent, fully transparent methods.

Both methods use the same Gordon-growth form (fair multiple = 1 / (required
return - growth)) applied to a normalized per-share earnings-power figure —
one on EPS, one on free cash flow. Neither pretends to be sector-calibrated;
every assumption actually used is attached to the result for display. A
method that cannot be computed (negative/missing EPS or FCF) is simply
omitted from the composite rather than guessed.
"""

from __future__ import annotations

import pandas as pd

from fundamentals import config
from fundamentals.models import FinancialMetricsHistory, ValuationEstimate, ValuationMethodResult


def _fair_multiple(growth: float) -> float | None:
    # The true mathematical constraint is growth < required return (the
    # Gordon-growth denominator). MAX_USABLE_GROWTH is a separate, more
    # conservative ceiling used to clamp growth *assumptions* elsewhere —
    # it must not also gate this check, or a clamped assumption sitting
    # exactly at that ceiling would be rejected here.
    if growth >= config.REQUIRED_RETURN:
        return None
    return 1.0 / (config.REQUIRED_RETURN - growth)


def _recent_positive_average(series: pd.Series, lookback: int = 3) -> float | None:
    clean = series.dropna()
    if clean.empty:
        return None
    window = clean.iloc[-min(lookback, len(clean)):]
    average = float(window.mean())
    return average if average > 0 else None


def _historical_cagr(series: pd.Series) -> float | None:
    clean = series.dropna()
    if len(clean) < 2:
        return None
    first, last = float(clean.iloc[0]), float(clean.iloc[-1])
    years = len(clean) - 1
    if first <= 0 or last <= 0 or years <= 0:
        return None
    return (last / first) ** (1.0 / years) - 1.0


def _earnings_power_value(metrics: FinancialMetricsHistory) -> ValuationMethodResult | None:
    normalized_eps = _recent_positive_average(metrics.annual.eps_diluted)
    if normalized_eps is None:
        return None

    bear_pe = _fair_multiple(config.EARNINGS_GROWTH_BEAR)
    base_pe = _fair_multiple(config.EARNINGS_GROWTH_BASE)
    bull_pe = _fair_multiple(config.EARNINGS_GROWTH_BULL)
    if base_pe is None:
        return None

    assumptions = (
        f"Normalized diluted EPS: {normalized_eps:.2f} (average of the most recent positive annual periods).",
        f"Required return: {config.REQUIRED_RETURN:.0%}.",
        f"Perpetual growth bear/base/bull: {config.EARNINGS_GROWTH_BEAR:.0%} / "
        f"{config.EARNINGS_GROWTH_BASE:.0%} / {config.EARNINGS_GROWTH_BULL:.0%} "
        "(fair P/E = 1 / (required return - growth)).",
    )
    return ValuationMethodResult(
        label="Earnings Power Value",
        bear=normalized_eps * bear_pe if bear_pe else None,
        base=normalized_eps * base_pe,
        bull=normalized_eps * bull_pe if bull_pe else None,
        assumptions=assumptions,
    )


def _fcf_power_value(metrics: FinancialMetricsHistory) -> ValuationMethodResult | None:
    if not metrics.shares_outstanding:
        return None
    normalized_fcf = _recent_positive_average(metrics.annual.free_cash_flow)
    if normalized_fcf is None:
        return None
    fcf_per_share = normalized_fcf / metrics.shares_outstanding

    historical_growth = _historical_cagr(metrics.annual.free_cash_flow)
    # The upper clamp can never exceed MAX_USABLE_GROWTH: a Gordon-growth
    # multiple is undefined once growth reaches the required return, so
    # FCF_GROWTH_MAX alone isn't sufficient — both ceilings must apply.
    usable_growth_ceiling = min(config.FCF_GROWTH_MAX, config.MAX_USABLE_GROWTH)
    if historical_growth is None:
        base_growth = config.EARNINGS_GROWTH_BASE
        growth_source = "no usable multi-year FCF history — fell back to the earnings base-growth assumption"
    else:
        base_growth = min(max(historical_growth, config.FCF_GROWTH_MIN), usable_growth_ceiling)
        growth_source = f"the company's own historical FCF CAGR ({historical_growth:+.1%}, clamped)"

    bear_growth = min(max(base_growth - config.FCF_GROWTH_SPREAD, config.FCF_GROWTH_MIN), config.MAX_USABLE_GROWTH)
    bull_growth = min(max(base_growth + config.FCF_GROWTH_SPREAD, config.FCF_GROWTH_MIN), config.MAX_USABLE_GROWTH)

    base_multiple = _fair_multiple(base_growth)
    if base_multiple is None:
        return None
    bear_multiple = _fair_multiple(bear_growth)
    bull_multiple = _fair_multiple(bull_growth)

    assumptions = (
        f"Normalized FCF/share: {fcf_per_share:.2f} (average of the most recent positive annual periods).",
        f"Required return: {config.REQUIRED_RETURN:.0%}.",
        f"Base growth anchored to {growth_source}: {base_growth:+.1%} "
        f"(bear {bear_growth:+.1%} / bull {bull_growth:+.1%}).",
    )
    return ValuationMethodResult(
        label="FCF Power Value",
        bear=fcf_per_share * bear_multiple if bear_multiple else None,
        base=fcf_per_share * base_multiple,
        bull=fcf_per_share * bull_multiple if bull_multiple else None,
        assumptions=assumptions,
    )


def build_valuation_estimate(metrics: FinancialMetricsHistory) -> ValuationEstimate:
    methods = tuple(
        method
        for method in (_earnings_power_value(metrics), _fcf_power_value(metrics))
        if method is not None
    )

    def _composite(attr: str) -> float | None:
        values = [getattr(method, attr) for method in methods if getattr(method, attr) is not None]
        return sum(values) / len(values) if values else None

    bear_fv = _composite("bear")
    base_fv = _composite("base")
    bull_fv = _composite("bull")

    price = metrics.current_price
    margin_of_safety = None
    upside_pct = None
    if base_fv and base_fv > 0:
        if price is not None:
            margin_of_safety = (base_fv - price) / base_fv
            upside_pct = (base_fv - price) / price if price else None

    return ValuationEstimate(
        current_price=price,
        methods=methods,
        bear_fair_value=bear_fv,
        base_fair_value=base_fv,
        bull_fair_value=bull_fv,
        composite_fair_value=base_fv,
        margin_of_safety=margin_of_safety,
        upside_pct=upside_pct,
        valuation_band="Insufficient Data",
    )
