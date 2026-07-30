"""Facade for the deterministic Fundamental Analysis engine.

`build_fundamental_analysis` is the single entry point views/other engines
should call: fetch -> metrics -> quality -> valuation -> rating -> narrative.
No exception crosses this boundary for "not enough data" — the same
convention as `views/security.py::load_analysis` — the view only has to
check `FundamentalAnalysis.sufficient` and render `insufficiency_reason`
when it is `False`.
"""

from __future__ import annotations

import dataclasses

from data.providers.fundamentals.base import FundamentalDataError, FundamentalDataProvider
from fundamentals.metrics import compute_metrics_history, has_minimum_data
from fundamentals.models import FundamentalAnalysis
from fundamentals.narrative import build_fundamental_narrative
from fundamentals.quality import build_quality_scores
from fundamentals.rating import build_fundamental_rating, classify_valuation_band
from fundamentals.valuation import build_valuation_estimate

INSUFFICIENT_DATA_MESSAGE = "Insufficient fundamental data for a reliable analysis."


def build_fundamental_analysis(ticker: str, provider: FundamentalDataProvider) -> FundamentalAnalysis:
    normalized = ticker.strip().upper() if isinstance(ticker, str) else ""

    try:
        bundle = provider.fetch(normalized)
    except FundamentalDataError as exc:
        return FundamentalAnalysis(
            ticker=normalized,
            sufficient=False,
            insufficiency_reason=f"{INSUFFICIENT_DATA_MESSAGE} ({exc})",
            metrics=None,
            quality=None,
            valuation=None,
            rating=None,
            narrative=None,
            raw=None,
        )

    metrics = compute_metrics_history(bundle)
    if not has_minimum_data(metrics.annual):
        return FundamentalAnalysis(
            ticker=normalized,
            sufficient=False,
            insufficiency_reason=(
                f"{INSUFFICIENT_DATA_MESSAGE} Yahoo Finance did not publish enough revenue/net "
                "income history for this ticker."
            ),
            metrics=metrics,
            quality=None,
            valuation=None,
            rating=None,
            narrative=None,
            raw=bundle,
        )

    quality = build_quality_scores(metrics)
    valuation = build_valuation_estimate(metrics)
    valuation = dataclasses.replace(
        valuation, valuation_band=classify_valuation_band(valuation.margin_of_safety)
    )
    rating = build_fundamental_rating(quality, valuation)
    narrative = build_fundamental_narrative(normalized, metrics, quality, valuation, rating)

    return FundamentalAnalysis(
        ticker=normalized,
        sufficient=True,
        insufficiency_reason=None,
        metrics=metrics,
        quality=quality,
        valuation=valuation,
        rating=rating,
        narrative=narrative,
        raw=bundle,
    )
