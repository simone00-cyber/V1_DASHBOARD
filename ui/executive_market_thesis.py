"""Renders the shared `ExecutiveMarketThesis` at two verbosity levels:
`render_executive_thesis_full` (Market Intelligence — the source of truth)
and `render_executive_thesis_summary` (Command Center — a condensed slice of
the *same* object). Neither function recomputes anything analytical.
"""

from __future__ import annotations

import html

import streamlit as st

from macro.models import ExecutiveMarketThesis
from ui.components import band_color
from ui.macro_panels import render_confidence_breakdown

_DIRECTIONAL_BAND = {"RISK-ON": "Good", "MIXED": "Fair", "RISK-OFF": "Poor"}


def _badge(directional_view: str) -> str:
    color = band_color(_DIRECTIONAL_BAND.get(directional_view, "Fair"))
    chip_class = {"RISK-ON": "is-good", "MIXED": "is-warning", "RISK-OFF": "is-critical"}.get(directional_view, "is-neutral")
    return f"<div class='conviction-badge {chip_class}'>{html.escape(directional_view)}</div>"


def _bullets(items: tuple[str, ...], limit: int | None = None) -> str:
    shown = items[:limit] if limit else items
    return "<ul class='evidence-list'>" + "".join(f"<li>{html.escape(item)}</li>" for item in shown) + "</ul>"


def render_executive_thesis_full(thesis: ExecutiveMarketThesis) -> None:
    st.markdown("<div class='terminal-subheader'>EXECUTIVE MARKET THESIS</div>", unsafe_allow_html=True)
    st.markdown(_badge(thesis.directional_view), unsafe_allow_html=True)
    st.markdown(f"<div class='thesis-headline'>{html.escape(thesis.headline)}</div>", unsafe_allow_html=True)
    render_confidence_breakdown(thesis.confidence)
    st.caption(f"Freshness: {thesis.freshness_summary}")

    st.markdown("<div class='terminal-subheader'>WHAT CHANGED</div>", unsafe_allow_html=True)
    st.markdown(_bullets(thesis.what_changed), unsafe_allow_html=True)

    st.markdown("<div class='terminal-subheader'>WHY IT MATTERS</div>", unsafe_allow_html=True)
    st.markdown(_bullets(thesis.why_it_matters), unsafe_allow_html=True)

    cols = st.columns(2)
    with cols[0]:
        st.markdown("**Top Opportunities**")
        st.markdown(_bullets(thesis.top_opportunities), unsafe_allow_html=True)
    with cols[1]:
        st.markdown("**Major Risks**")
        st.markdown(_bullets(thesis.major_risks), unsafe_allow_html=True)


def render_executive_thesis_summary(thesis: ExecutiveMarketThesis) -> None:
    """Command Center's condensed view of the exact same thesis object."""
    st.markdown("<div class='terminal-subheader'>EXECUTIVE MARKET THESIS</div>", unsafe_allow_html=True)
    st.markdown(_badge(thesis.directional_view), unsafe_allow_html=True)
    st.markdown(f"<div class='thesis-headline'>{html.escape(thesis.headline)}</div>", unsafe_allow_html=True)

    confidence_color = band_color({"HIGH": "Good", "MODERATE": "Fair", "LOW": "Poor", "VERY LOW": "Poor"}.get(thesis.confidence.label, "Fair"))
    st.markdown(
        f"<span class='status-chip' style='color:{confidence_color};border-color:{confidence_color}'>"
        f"CONFIDENCE: {html.escape(thesis.confidence.label)}</span>",
        unsafe_allow_html=True,
    )

    cols = st.columns(2)
    with cols[0]:
        st.markdown("**Top Opportunities**")
        st.markdown(_bullets(thesis.top_opportunities, limit=3), unsafe_allow_html=True)
    with cols[1]:
        st.markdown("**Major Risks**")
        st.markdown(_bullets(thesis.major_risks, limit=3), unsafe_allow_html=True)

    st.markdown("**Suggested Research**")
    st.markdown(_bullets(thesis.what_changed, limit=2), unsafe_allow_html=True)

    pages = st.session_state.get("_pages", {})
    if "Macro & Rates" in pages:
        st.page_link(pages["Macro & Rates"], label="Open Market Intelligence →", icon=":material/insights:")
