from __future__ import annotations

import html

import pandas as pd
import plotly.express as px
import streamlit as st

from config.theme import GREEN, RED, MUTED, ORANGE
from screener.opportunities import (
    OpportunitySnapshot,
    build_reason,
    build_regime_label,
    build_risk,
)


def _open_in_research(ticker: str) -> None:
    """Point the Research Workspace at `ticker` and navigate there if the page is registered."""
    pages = st.session_state.get("_pages", {})
    st.session_state["workspace_ticker"] = ticker
    st.session_state["workspace_loading"] = True
    if "Research Workspace" in pages:
        st.switch_page(pages["Research Workspace"])


def _build_strategy(ticker: str, company: str) -> None:
    """Hand `ticker` off to the AI Strategy Lab as a prefilled prompt and navigate there."""
    pages = st.session_state.get("_pages", {})
    st.session_state["pending_ai_message"] = (
        f"Build a strategy idea around {ticker} ({company}), using its current cyclical matrix signal as context."
    )
    if "AI Strategy Lab" in pages:
        st.switch_page(pages["AI Strategy Lab"])


def render_snapshot(snapshot: OpportunitySnapshot | None) -> None:
    st.markdown("<div class='terminal-subheader'>OPPORTUNITY SNAPSHOT</div>", unsafe_allow_html=True)
    if snapshot is None:
        st.info("Not enough data to build a snapshot for the current universe and window.")
        return

    st.markdown(
        f"<div class='opportunity-insight'>{html.escape(snapshot.interpretation)}</div>",
        unsafe_allow_html=True,
    )

    cards = st.columns(5)
    cards[0].metric("LEADING SECTOR", snapshot.leading_sector, f"{snapshot.leading_sector_perf:+.2f}%")
    cards[1].metric("LAGGING SECTOR", snapshot.lagging_sector, f"{snapshot.lagging_sector_perf:+.2f}%")
    cards[2].metric("SECTOR DISPERSION", f"{snapshot.dispersion:.1f} pp")
    cards[3].metric("BREADTH", f"{snapshot.breadth_positive}/{snapshot.breadth_total}", snapshot.breadth_label.upper())
    cards[4].metric("HIGH CONVICTION", snapshot.high_conviction_count)


def _render_opportunity_card(row: pd.Series) -> None:
    ticker = str(row["Ticker"])
    company = str(row["Company"])
    sector = str(row["Sector"])
    rating = int(row.get("Rating", 0) or 0)
    rs = row.get("RS 3M %")
    rs_text = f"{rs:+.1f}%" if pd.notna(rs) else "N/D"
    weekly_cm = row.get("Weekly CM")
    weekly_text = f"{weekly_cm:+.0f}" if pd.notna(weekly_cm) else "N/D"

    with st.container(border=True):
        st.markdown(
            f"<div class='opp-card-ticker'>{html.escape(ticker)}"
            f"<span class='opp-card-rating'>{'●' * rating}</span></div>"
            f"<div class='opp-card-company'>{html.escape(company)} · {html.escape(sector)}</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div class='opp-card-metrics'>"
            "<div class='opp-card-metric'>"
            "<span class='opp-card-metric-label'>Price</span>"
            f"<span class='opp-card-metric-value'>{row['Last']:,.2f}</span></div>"
            "<div class='opp-card-metric'>"
            "<span class='opp-card-metric-label'>RS 3M</span>"
            f"<span class='opp-card-metric-value'>{html.escape(rs_text)}</span></div>"
            "<div class='opp-card-metric'>"
            "<span class='opp-card-metric-label'>Weekly mom.</span>"
            f"<span class='opp-card-metric-value'>{html.escape(weekly_text)}</span></div>"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            f"<div class='opp-card-regime'>{html.escape(build_regime_label(row))}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='opp-card-reason'><b>Why it ranks:</b> {html.escape(build_reason(row))}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='opp-card-risk'><b>Risk / invalidation:</b> {html.escape(build_risk(row))}</div>",
            unsafe_allow_html=True,
        )

        action_cols = st.columns(2)
        if action_cols[0].button("Open in Research", key=f"opp_research_{ticker}", width="stretch", type="primary"):
            _open_in_research(ticker)
        if action_cols[1].button("Build Strategy", key=f"opp_strategy_{ticker}", width="stretch"):
            _build_strategy(ticker, company)


def render_top_opportunities(rows: pd.DataFrame) -> None:
    st.markdown("<div class='terminal-subheader'>TOP OPPORTUNITIES</div>", unsafe_allow_html=True)
    if rows.empty:
        st.info("No BUY-rated securities currently meet the matrix criteria in this universe.")
        return

    per_row = 3
    for start in range(0, len(rows), per_row):
        chunk = rows.iloc[start : start + per_row]
        cols = st.columns(per_row)
        for col, (_, row) in zip(cols, chunk.iterrows()):
            with col:
                _render_opportunity_card(row)


def render_sector_leadership(sectors: pd.DataFrame, window_label: str) -> None:
    st.markdown("<div class='terminal-subheader'>SECTOR LEADERSHIP</div>", unsafe_allow_html=True)
    if sectors.empty or "Group" not in sectors:
        st.info("Sector leadership unavailable for the selected window.")
        return

    leading = int((sectors["Group"] == "LEADING").sum())
    neutral = int((sectors["Group"] == "NEUTRAL").sum())
    lagging = int((sectors["Group"] == "LAGGING").sum())
    st.markdown(
        "<div class='sector-group-row'>"
        f"<span class='status-chip is-good'>{leading} LEADING</span>"
        f"<span class='status-chip is-neutral'>{neutral} NEUTRAL</span>"
        f"<span class='status-chip is-critical'>{lagging} LAGGING</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    chart = sectors.sort_values("Performance", ascending=True)
    color_map = {"LEADING": GREEN, "LAGGING": RED, "NEUTRAL": MUTED}
    fig = px.bar(
        chart,
        x="Performance",
        y="Sector",
        orientation="h",
        text="Performance",
        color="Group",
        color_discrete_map=color_map,
        hover_data=["Stocks", "Median", "Best", "Worst"],
        labels={"Performance": f"{window_label} return (%)", "Sector": ""},
    )
    fig.update_traces(texttemplate="%{text:+.1f}%", textposition="outside")
    fig.update_layout(
        template="plotly_dark",
        height=max(360, 34 * len(chart)),
        margin=dict(l=10, r=45, t=10, b=10),
        showlegend=False,
        xaxis_title=f"Equal-weight {window_label.lower()} performance (%)",
        yaxis_title="",
    )
    st.plotly_chart(fig, width="stretch")

    with st.expander("Sector data table"):
        st.dataframe(sectors.drop(columns=["Group"]), width="stretch", hide_index=True)


def _render_side_panel(title: str, rows: pd.DataFrame, performance_column: str, color: str) -> None:
    st.markdown(
        f"<div class='side-panel-header' style='color:{color};border-color:{color}'>{html.escape(title)}</div>",
        unsafe_allow_html=True,
    )
    if rows.empty:
        st.info("No securities available for the selected filters.")
        return

    with st.container(border=True):
        for _, row in rows.iterrows():
            ticker = str(row["Ticker"])
            perf = row[performance_column]
            row_cols = st.columns([1.2, 2.8, 1.2, 1.3], vertical_alignment="center")
            row_cols[0].markdown(f"**{html.escape(ticker)}**")
            row_cols[1].markdown(
                f"<span class='small-note'>{html.escape(str(row['Company']))} · {html.escape(str(row['Sector']))}</span>",
                unsafe_allow_html=True,
            )
            perf_class = "tick-up" if perf >= 0 else "tick-down"
            row_cols[2].markdown(f"<span class='{perf_class}'>{perf:+.2f}%</span>", unsafe_allow_html=True)
            if row_cols[3].button("Research", key=f"panel_research_{title}_{ticker}", width="stretch"):
                _open_in_research(ticker)


def render_leaders_laggards(top: pd.DataFrame, flop: pd.DataFrame, performance_column: str) -> None:
    st.markdown("<div class='terminal-subheader'>LEADERS &amp; LAGGARDS</div>", unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        _render_side_panel("LEADERS", top, performance_column, GREEN)
    with right:
        _render_side_panel("LAGGARDS", flop, performance_column, RED)


_TIER_COLORS = {
    "High Conviction": GREEN,
    "Emerging": ORANGE,
    "Watchlist": MUTED,
    "Deteriorating": ORANGE,
    "Avoid": RED,
}

_TIER_CAPTIONS = {
    "High Conviction": "BUY signal with Reward/Risk of 3/4 or 4/4 — the strongest matrix reading.",
    "Emerging": "BUY signal with an early-stage Reward/Risk rating of 1/4 or 2/4.",
    "Watchlist": "No new weekly junction — the matrix has not produced a fresh signal.",
    "Deteriorating": "TAKE PROFIT — the matrix flags an extended position, not a new entry.",
    "Avoid": "SELL SHORT — the matrix reading is bearish across timeframes.",
}


def render_opportunity_funnel(funnel: pd.DataFrame, annotated_rows: pd.DataFrame) -> None:
    st.markdown("<div class='terminal-subheader'>OPPORTUNITY FUNNEL</div>", unsafe_allow_html=True)
    if funnel.empty:
        st.info("Opportunity funnel unavailable.")
        return

    tiers = list(funnel["Tier"])
    fig = px.bar(
        funnel,
        x="Count",
        y="Tier",
        orientation="h",
        text="Count",
        color="Tier",
        color_discrete_map=_TIER_COLORS,
        category_orders={"Tier": tiers},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        template="plotly_dark",
        height=280,
        margin=dict(l=10, r=30, t=10, b=10),
        showlegend=False,
        xaxis_title="Securities",
        yaxis_title="",
    )
    st.plotly_chart(fig, width="stretch")

    tabs = st.tabs(tiers)
    for tab, tier in zip(tabs, tiers):
        with tab:
            st.markdown(
                f"<div class='funnel-tier-caption'>{html.escape(_TIER_CAPTIONS.get(tier, ''))}</div>",
                unsafe_allow_html=True,
            )
            subset = annotated_rows[annotated_rows["Conviction Tier"] == tier]
            if subset.empty:
                st.caption("No securities in this tier.")
                continue
            display = subset[["Ticker", "Company", "Sector", "Matrix Action", "Rating Visual", "Last"]]
            st.dataframe(
                display,
                width="stretch",
                hide_index=True,
                height=min(360, 46 + 35 * len(display)),
            )
