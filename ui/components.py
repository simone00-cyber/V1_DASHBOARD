"""Small, shared presentation-only helpers used across the Research workspace.

Nothing here computes anything analytical — every function only formats or
colors a value that some engine already produced. Extracted because the same
few helpers (star ratings, compact stat tiles, band-to-color mapping) had
started being copy-pasted identically across `ui/research_panels.py`,
`ui/fundamental_panels.py` and `ui/fundamental_opportunity_cards.py`.
"""

from __future__ import annotations

import html

import streamlit as st

from config.theme import GREEN, MUTED, ORANGE, RED


def stars(score: int, slots: int = 5) -> str:
    filled = max(0, min(slots, round(score / 100 * slots)))
    return "★" * filled + "☆" * (slots - filled)


def stat_row(items: list[tuple[str, str]]) -> None:
    """Compact stat tiles with a small, wrapping value font — unlike st.metric, long
    values (e.g. a sequence label or a price range) are never clipped with an ellipsis."""
    blocks = "".join(
        "<div class='opp-card-metric'>"
        f"<span class='opp-card-metric-label'>{html.escape(label)}</span>"
        f"<span class='opp-card-metric-value' style='font-size:.88rem;white-space:normal;'>{html.escape(value)}</span>"
        "</div>"
        for label, value in items
    )
    st.markdown(f"<div class='opp-card-metrics'>{blocks}</div>", unsafe_allow_html=True)


def band_color(band: str) -> str:
    """Maps rating/valuation/recommendation bands to a semantic color.
    Shared vocabulary across engines: Excellent/Good/Undervalued/BUY are
    "good", Fair/Fairly Valued/HOLD are "neutral-warning", Weak/Poor/
    Overvalued/SELL are "bad"."""
    if band in {"Excellent", "Good", "Undervalued", "BUY"}:
        return GREEN
    if band in {"Fair", "Fairly Valued", "HOLD"}:
        return ORANGE
    if band in {"Weak", "Poor", "Overvalued", "SELL"}:
        return RED
    return MUTED


def confidence_color(confidence: int) -> str:
    if confidence >= 70:
        return GREEN
    if confidence >= 45:
        return ORANGE
    return RED


def direction_color(direction: str) -> str:
    upper = direction.upper()
    if "UP" in upper or "BULLISH" in upper:
        return GREEN
    if "DOWN" in upper or "BEARISH" in upper:
        return RED
    return MUTED


def fmt_money(value: float | None) -> str:
    return f"{value:,.2f}" if value is not None else "N/A"


def fmt_pct(value: float | None) -> str:
    return f"{value:+.1%}" if value is not None else "N/A"
