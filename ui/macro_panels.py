from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from macro.metadata import DataMetadata
from macro.models import CalendarEvent, ConfidenceAssessment, CrossAssetSnapshot, MacroPillar, MacroSeriesReading
from ui.components import band_color, stat_row

_DIRECTION_BAND = {
    "EXPANDING": "Good",
    "CONTAINED": "Good",
    "MODERATING": "Fair",
    "MODERATE": "Fair",
    "STABLE": "Fair",
    "CONTRACTING": "Poor",
    "ELEVATED": "Poor",
    "TIGHTENING": "Poor",
    "UNKNOWN": "Insufficient Data",
}

_CONFIDENCE_BAND = {"HIGH": "Good", "MODERATE": "Fair", "LOW": "Poor", "VERY LOW": "Poor"}


def _freshness_chip(metadata: DataMetadata) -> str:
    chip_class = {
        "CURRENT": "is-good",
        "AGING": "is-warning",
        "STALE": "is-critical",
        "UNKNOWN": "is-neutral",
    }.get(metadata.freshness_status, "is-neutral")
    return f"<span class='status-chip {chip_class}'>{html.escape(metadata.freshness_status)}</span>"


def render_data_metadata_caption(metadata: DataMetadata) -> None:
    if metadata.availability_status == "UNAVAILABLE":
        st.caption(f"Unavailable — {metadata.unavailable_reason or 'no data returned by the provider.'}")
        return
    age_text = f"{metadata.data_age.days}d old" if metadata.data_age is not None else "age unknown"
    provenance = f"{metadata.provider} ({metadata.provider_series_id})"
    availability_note = " · DEGRADED (FALLBACK)" if metadata.availability_status == "DEGRADED (FALLBACK)" else ""
    st.caption(f"{provenance} · {metadata.frequency.title()} · {age_text}{availability_note}")


def render_confidence_breakdown(confidence: ConfidenceAssessment) -> None:
    band_c = band_color(_CONFIDENCE_BAND.get(confidence.label, "Fair"))
    st.markdown(
        f"<span class='status-chip' style='color:{band_c};border-color:{band_c}'>"
        f"CONFIDENCE: {html.escape(confidence.label)} ({confidence.score}/100)</span>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Evidence quality, not directional conviction — a weighted combination of data coverage, freshness, "
        "provider degradation, internal agreement, revision risk and cross-asset confirmation."
    )
    with st.expander("Confidence methodology breakdown", expanded=False):
        table = pd.DataFrame(
            [{"Component": name.replace("_", " ").title(), "Score": round(score, 1)} for name, score in confidence.breakdown.items()]
        )
        st.dataframe(table, width="stretch", hide_index=True)
        if confidence.notes:
            for note in confidence.notes:
                st.caption(f"• {note}")


def _reading_row(reading: MacroSeriesReading) -> dict:
    if not reading.available:
        return {
            "Series": reading.label,
            "Value": "N/A",
            "YoY": "N/A",
            "Status": reading.metadata.availability_status,
        }
    value_text = f"{reading.value:,.2f} {reading.metadata.unit}".strip()
    yoy_text = f"{reading.yoy_change_pct:+.1%}" if reading.yoy_change_pct is not None else "N/A"
    return {
        "Series": reading.label,
        "Value": value_text,
        "YoY": yoy_text,
        "Status": reading.metadata.availability_status,
    }


def render_pillar_summary_tile(pillar: MacroPillar) -> None:
    """One compact tile for the 'Current Macro Regime' row."""
    band_c = band_color(_DIRECTION_BAND.get(pillar.direction, "Fair"))
    st.markdown(
        f"<div class='opp-card-metric' style='border-color:{band_c}'>"
        f"<span class='opp-card-metric-label'>{html.escape(pillar.name.title())}</span>"
        f"<span class='opp-card-metric-value' style='color:{band_c};font-size:1.0rem'>{html.escape(pillar.direction)}</span>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_pillar_deep_dive(title: str, pillar: MacroPillar) -> None:
    st.markdown(f"<div class='terminal-subheader'>{html.escape(title)}</div>", unsafe_allow_html=True)
    band_c = band_color(_DIRECTION_BAND.get(pillar.direction, "Fair"))
    st.markdown(
        f"<div class='insight-banner' style='border-left-color:{band_c}'>{html.escape(pillar.summary)}</div>",
        unsafe_allow_html=True,
    )
    render_confidence_breakdown(pillar.confidence)

    st.markdown("<b>Underlying series</b>", unsafe_allow_html=True)
    rows = [_reading_row(reading) for reading in pillar.readings]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    with st.expander("Provenance & freshness detail", expanded=False):
        for reading in pillar.readings:
            st.markdown(f"**{html.escape(reading.label)}**")
            render_data_metadata_caption(reading.metadata)


def render_cross_asset_panel(cross_asset: CrossAssetSnapshot) -> None:
    st.markdown("<div class='terminal-subheader'>CROSS-ASSET CONFIRMATION</div>", unsafe_allow_html=True)
    if cross_asset.agreement_ratio is not None:
        st.caption(f"{cross_asset.agreement_ratio:.0%} of cross-asset signals confirm the prevailing regime read.")
    else:
        st.caption("Regime signal is not strong enough to test cross-asset confirmation against right now.")

    cols = st.columns(len(cross_asset.items))
    for col, item in zip(cols, cross_asset.items):
        if item.confirms_regime is True:
            chip_class, chip_text = "is-good", "CONFIRMS"
        elif item.confirms_regime is False:
            chip_class, chip_text = "is-critical", "DIVERGES"
        else:
            chip_class, chip_text = "is-neutral", "N/A"
        with col:
            st.markdown(
                f"<div class='opp-card-metric'>"
                f"<span class='opp-card-metric-label'>{html.escape(item.asset_class)}</span>"
                f"<span class='opp-card-metric-value' style='font-size:.85rem'>{html.escape(item.verdict)}</span>"
                f"</div><span class='status-chip {chip_class}' style='margin-top:.3rem'>{chip_text}</span>",
                unsafe_allow_html=True,
            )
            st.caption(item.what_changed)


_IMPORTANCE_COLOR = {"HIGH": "is-critical", "MEDIUM": "is-warning"}


def render_calendar_panel(events: tuple[CalendarEvent, ...]) -> None:
    from macro.config import CALENDAR_SCOPE_NOTE

    st.caption(CALENDAR_SCOPE_NOTE)
    if not events:
        st.info("No scheduled release dates are currently published for the covered series (or FRED_API_KEY is not configured).")
        return
    rows = [
        {
            "Release": event.release_name,
            "Region": event.country_region,
            "Date": event.scheduled_date.strftime("%d %b %Y") if event.scheduled_date is not None else "N/A",
            "Time": event.scheduled_time or "Not published",
            "Importance": event.importance,
            "Pillar": event.affected_pillar.title(),
            "Relevance": event.current_relevance,
            "Source": event.source,
        }
        for event in events
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
