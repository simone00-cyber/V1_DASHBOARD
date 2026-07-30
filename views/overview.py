from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from charts.common import create_bar_chart, create_line_chart
from config.universe import EQUITY_INDICES
from core.metrics import build_market_table, normalized_frame
from data.yahoo import download_close_batch
from macro.models import ExecutiveMarketThesis
from ui.executive_market_thesis import render_executive_thesis_summary
from ui.market_intelligence_panel import render_market_intelligence_panel
from views.macro import build_thesis_bundle
from views.regime import regime_color, render_market_regime


def _compute_reading(table: pd.DataFrame) -> dict[str, Any]:
    ranked = table.dropna(subset=["1D %"]).sort_values("1D %", ascending=False)
    leader = ranked.iloc[0] if not ranked.empty else None
    laggard = ranked.iloc[-1] if not ranked.empty else None
    indexed = table.set_index("Strumento")
    vix = indexed.loc["VIX"] if "VIX" in indexed.index else None
    positive = int((ranked["1D %"] > 0).sum()) if not ranked.empty else 0
    total = len(ranked)

    return {
        "leader": leader,
        "laggard": laggard,
        "vix": vix,
        "positive": positive,
        "total": total,
    }


def _build_market_context(table: pd.DataFrame, reading: dict[str, Any], thesis: ExecutiveMarketThesis) -> dict[str, Any]:
    """Grounding context for the AI chat's follow-up Q&A — built from the
    equity table plus the shared Executive Market Thesis. Macro & Rates is
    the source of truth for the analytical content; nothing here
    recomputes it."""
    indexed = table.set_index("Strumento")
    index_rows = {}
    for name, row in indexed.iterrows():
        change = row["1D %"]
        index_rows[str(name)] = {
            "last": float(row["Ultimo"]),
            "change_1d_pct": None if pd.isna(change) else float(change),
        }

    return {
        "equity_indices": index_rows,
        "breadth": {"positive": reading["positive"], "total": reading["total"]},
        "executive_thesis": {
            "headline": thesis.headline,
            "directional_view": thesis.directional_view,
            "confidence": thesis.confidence.label,
            "what_changed": list(thesis.what_changed),
            "why_it_matters": list(thesis.why_it_matters),
            "top_opportunities": list(thesis.top_opportunities),
            "major_risks": list(thesis.major_risks),
        },
    }


def _thesis_fallback_text(thesis: ExecutiveMarketThesis) -> str:
    """Deterministic stand-in for `generate_daily_briefing` when the LLM is
    unavailable — built directly from the shared Executive Market Thesis
    (Macro & Rates is the source of truth; this recomputes nothing)."""
    sections = [thesis.headline]
    if thesis.what_changed:
        sections.append("**What Changed**\n" + "\n".join(f"- {item}" for item in thesis.what_changed))
    if thesis.top_opportunities:
        sections.append("**Top Opportunities**\n" + "\n".join(f"- {item}" for item in thesis.top_opportunities))
    if thesis.major_risks:
        sections.append("**Major Risks**\n" + "\n".join(f"- {item}" for item in thesis.major_risks))
    return "\n\n".join(sections)


def _render_status_line(table: pd.DataFrame, tactical) -> None:
    parts: list[str] = []

    if tactical is not None:
        color = regime_color(tactical.diagnosis)
        parts.append(
            f"<span class='status-dot' style='background:{color}'></span>"
            f"<b>{tactical.title}</b>&nbsp;{tactical.diagnosis}"
            f"<span class='status-muted'> · {tactical.coverage:.0%} confidence</span>"
        )
    else:
        parts.append("<span class='status-muted'>Regime unavailable</span>")

    indexed = table.set_index("Strumento")
    for name in ["S&P 500", "NASDAQ", "VIX"]:
        if name in indexed.index:
            row = indexed.loc[name]
            css_class = "tick-up" if row["1D %"] >= 0 else "tick-down"
            parts.append(f"<span class='{css_class}'>{name} {row['1D %']:+.2f}%</span>")

    st.markdown(
        f"<div class='status-line'>{' &nbsp;·&nbsp; '.join(parts)}</div>",
        unsafe_allow_html=True,
    )


def render_global_overview() -> None:
    with st.spinner("Loading market data…"):
        close = download_close_batch(tuple(EQUITY_INDICES.values()), period="6mo")

    table = build_market_table(close, EQUITY_INDICES)
    if table.empty:
        st.error("Yahoo Finance non ha restituito dati per gli indici.")
        return

    with st.spinner("Building today's market thesis..."):
        regime_results, growth, inflation, liquidity, cross_asset, thesis = build_thesis_bundle()

    reading = _compute_reading(table)
    tactical = regime_results.get("TACTICAL")

    _render_status_line(table, tactical)

    _, center, _ = st.columns([1, 5, 1])
    with center:
        render_executive_thesis_summary(thesis)

        st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
        st.markdown("<div class='terminal-subheader'>ASK A FOLLOW-UP</div>", unsafe_allow_html=True)
        market_context = _build_market_context(table, reading, thesis)
        fallback_briefing = _thesis_fallback_text(thesis)
        render_market_intelligence_panel(market_context, fallback_briefing)

        st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)
        links = st.columns(3)
        pages = st.session_state.get("_pages", {})
        with links[0]:
            if "Macro & Rates" in pages:
                st.page_link(pages["Macro & Rates"], label="Macro & Rates", icon=":material/show_chart:")
        with links[1]:
            if "Opportunities" in pages:
                st.page_link(pages["Opportunities"], label="Opportunities", icon=":material/search:")
        with links[2]:
            if "Research Workspace" in pages:
                st.page_link(pages["Research Workspace"], label="Research Workspace", icon=":material/science:")

    with st.expander("Detailed market data & regime analytics", expanded=False):
        card_names = ["S&P 500", "NASDAQ", "FTSE MIB", "DAX", "NIKKEI 225", "VIX", "KOSPI"]
        indexed = table.set_index("Strumento")
        cols = st.columns(7)
        for col, name in zip(cols, card_names):
            if name not in indexed.index:
                col.metric(name, "N/D")
                continue
            row = indexed.loc[name]
            col.metric(name, f"{row['Ultimo']:,.2f}", f"{row['1D %']:+.2f}%")

        left, right = st.columns([2.1, 1])
        with left:
            st.markdown("<div class='terminal-subheader'>RELATIVE PERFORMANCE</div>", unsafe_allow_html=True)
            reverse = {ticker: name for name, ticker in EQUITY_INDICES.items()}
            renamed = close.rename(columns=reverse)
            defaults = [name for name in ["S&P 500", "NASDAQ", "EURO STOXX 50", "FTSE MIB", "DAX", "NIKKEI 225", "KOSPI"] if name in renamed.columns]
            selected = st.multiselect("Indici", options=list(renamed.columns), default=defaults, label_visibility="collapsed", key="overview_indices")
            if selected:
                st.plotly_chart(create_line_chart(normalized_frame(renamed[selected]), "GLOBAL EQUITY // BASE 100", "Base 100", 510), width="stretch")
        with right:
            st.markdown("<div class='terminal-subheader'>1D PERFORMANCE</div>", unsafe_allow_html=True)
            st.plotly_chart(create_bar_chart(table, "1D %", "LEADERS / LAGGARDS"), width="stretch")

        st.divider()
        render_market_regime(show_header=False)
