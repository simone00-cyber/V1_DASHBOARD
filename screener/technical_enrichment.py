"""Bounded per-card Technical/Cyclical enrichment for Opportunities cards.

A full technical assessment (support/resistance + pattern scan) is heavier
than the matrix lookup that powers the always-fast screener, so this is only
ever computed for the small, bounded set of tickers actually rendered as
cards (Top Opportunities, currently limited to 6) — never for the full
universe table. `screener/engine.py::analyse_universe`/`sort_by_methodology`
are completely untouched by this module.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from analysis.combined_thesis import derive_technical_verdict
from screener.engine import download_universe_ohlc
from technical.assessment import build_technical_assessment, derive_key_trigger
from technical.engine import TechnicalSettings


@dataclass(frozen=True)
class TechnicalCyclicalEnrichment:
    technical_rating: str
    pattern: str
    pattern_status: str
    current_structure: str
    current_risk: str
    next_trigger: str
    thesis: str


@st.cache_data(ttl=3600, show_spinner=False, max_entries=64)
def _card_daily_prices(ticker: str) -> pd.DataFrame:
    data = download_universe_ohlc([ticker], period="max", chunk_size=1)
    return data.get(ticker, pd.DataFrame())


def enrich_ticker(ticker: str, matrix_action: str, rating: int) -> TechnicalCyclicalEnrichment | None:
    """Returns `None` (never raises) when there isn't enough price history to
    build a technical read — the card then simply omits the enrichment."""
    try:
        frame = _card_daily_prices(ticker)
        if frame.empty or len(frame.dropna(subset=["Close"])) < 60:
            return None
        assessment = build_technical_assessment(ticker, frame, TechnicalSettings())
    except Exception:
        return None

    details = assessment.snapshot.diagnostics.get("pattern_details", [])
    developing = [pattern for pattern in details if pattern["status"] == "DEVELOPING"]
    patterns = (developing or details)[:3]
    top_pattern = patterns[0] if patterns else None

    technical_rating = derive_technical_verdict(assessment)
    current_structure = assessment.trend_quality.swing_structure.sequence.title()

    return TechnicalCyclicalEnrichment(
        technical_rating=technical_rating,
        pattern=top_pattern["name"] if top_pattern else "No qualifying setup",
        pattern_status=top_pattern["status"] if top_pattern else "N/A",
        current_structure=current_structure,
        current_risk=assessment.risk_read.level,
        next_trigger=derive_key_trigger(assessment, patterns),
        thesis=(
            f"Technical reads {technical_rating} ({assessment.trend_quality.label.lower()}-quality "
            f"{current_structure.lower()}); cyclical matrix action {matrix_action} with Reward/Risk {rating}/4."
        ),
    )
