from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from fundamentals.opportunities import RANKING_FUNCTIONS, RANKING_LABELS, FundamentalOpportunityRow
from fundamentals.scan import FundamentalScanResult
from ui.components import band_color as _band_color
from ui.navigation_actions import navigate_to_build_strategy, navigate_to_research


def render_fundamental_scan_header(scan: FundamentalScanResult | None) -> None:
    st.markdown("<div class='terminal-subheader'>FUNDAMENTAL SCAN STATUS</div>", unsafe_allow_html=True)
    if scan is None:
        st.info("No fundamental scan has been run yet for this universe. Click 'Refresh Fundamental Analysis' below to start one.")
        return

    missing = [ticker for ticker, _ in scan.failures]
    cols = st.columns(5)
    cols[0].metric("LAST UPDATED", scan.last_updated.strftime("%d %b %Y, %H:%M UTC"))
    cols[1].metric("DATA SOURCE", scan.data_source)
    cols[2].metric("COVERAGE", f"{scan.coverage}/{scan.universe_size}")
    cols[3].metric("MISSING COMPANIES", len(missing))
    cols[4].metric("SCANNED", scan.universe_size)

    if missing:
        with st.expander(f"MISSING COMPANIES ({len(missing)})", expanded=False):
            st.dataframe(
                pd.DataFrame(scan.failures, columns=["Ticker", "Reason"]),
                width="stretch",
                hide_index=True,
            )


def _render_fundamental_card(row: FundamentalOpportunityRow, key_prefix: str) -> None:
    rating_color = _band_color(row.rating_band)
    valuation_color = _band_color(row.valuation_band)
    fair_value = f"{row.fair_value:,.2f}" if row.fair_value is not None else "N/A"
    current_price = f"{row.current_price:,.2f}" if row.current_price is not None else "N/A"
    mos = f"{row.margin_of_safety:+.1%}" if row.margin_of_safety is not None else "N/A"
    upside = f"{row.upside_pct:+.1%}" if row.upside_pct is not None else "N/A"

    with st.container(border=True):
        st.markdown(
            f"<div class='opp-card-ticker'>{html.escape(row.ticker)}"
            f"<span style='color:{rating_color};font-weight:800;font-size:.85rem'>{html.escape(row.recommendation)}</span></div>"
            f"<div class='opp-card-company'>{html.escape(row.rating_band)} "
            f"({row.overall_score}/100) &middot; <span style='color:{valuation_color}'>{html.escape(row.valuation_band)}</span></div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div class='opp-card-metrics'>"
            f"<div class='opp-card-metric'><span class='opp-card-metric-label'>Fair Value</span>"
            f"<span class='opp-card-metric-value'>{html.escape(fair_value)}</span></div>"
            f"<div class='opp-card-metric'><span class='opp-card-metric-label'>Price</span>"
            f"<span class='opp-card-metric-value'>{html.escape(current_price)}</span></div>"
            f"<div class='opp-card-metric'><span class='opp-card-metric-label'>Mgn. of Safety</span>"
            f"<span class='opp-card-metric-value'>{html.escape(mos)}</span></div>"
            f"<div class='opp-card-metric'><span class='opp-card-metric-label'>Upside</span>"
            f"<span class='opp-card-metric-value'>{html.escape(upside)}</span></div>"
            "</div>",
            unsafe_allow_html=True,
        )

        axes = [
            ("Business Quality", row.business_quality),
            ("Financial Strength", row.financial_strength),
            ("Growth", row.growth_quality),
            ("Profitability", row.profitability),
        ]
        axes_text = " &middot; ".join(
            f"{label} {score}/100" if score is not None else f"{label} N/A" for label, score in axes
        )
        st.markdown(f"<div class='opp-card-regime'>{html.escape(axes_text)}</div>", unsafe_allow_html=True)

        st.markdown(
            f"<div class='opp-card-reason'><b>Thesis:</b> {html.escape(row.thesis)}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='opp-card-risk'><b>Main risk:</b> {html.escape(row.main_risk)}</div>",
            unsafe_allow_html=True,
        )

        action_cols = st.columns(2)
        if action_cols[0].button("Open in Research", key=f"fund_opp_research_{key_prefix}_{row.ticker}", width="stretch", type="primary"):
            navigate_to_research(row.ticker)
        if action_cols[1].button("Build Strategy", key=f"fund_opp_strategy_{key_prefix}_{row.ticker}", width="stretch"):
            navigate_to_build_strategy(
                f"Build a strategy idea around {row.ticker}, using its fundamental rating "
                f"({row.rating_band}, {row.recommendation}) as context."
            )


def render_fundamental_rankings(rows: list[FundamentalOpportunityRow], *, limit: int = 9) -> None:
    st.markdown("<div class='terminal-subheader'>FUNDAMENTAL OPPORTUNITIES</div>", unsafe_allow_html=True)
    if not rows:
        st.info("No securities with sufficient fundamental data are available yet — run a scan above.")
        return

    tabs = st.tabs(list(RANKING_LABELS))
    for tab, label in zip(tabs, RANKING_LABELS):
        with tab:
            selected = RANKING_FUNCTIONS[label](rows, limit)
            if not selected:
                st.info("No securities qualify for this ranking from the current scan.")
                continue
            per_row = 3
            for start in range(0, len(selected), per_row):
                chunk = selected[start : start + per_row]
                cols = st.columns(per_row)
                for col, row in zip(cols, chunk):
                    with col:
                        _render_fundamental_card(row, key_prefix=label)
