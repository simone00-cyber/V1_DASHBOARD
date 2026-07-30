from __future__ import annotations

import streamlit as st

from fundamentals.opportunities import build_opportunity_rows
from fundamentals.scan import FundamentalScanResult, clear_fundamental_cache, run_fundamental_scan
from screener.universes import load_universe
from ui.fundamental_opportunity_cards import render_fundamental_rankings, render_fundamental_scan_header


@st.cache_data(ttl=86400, show_spinner=False)
def _constituents(name: str):
    return load_universe(name)


def render_fundamental_opportunities(universe: str) -> None:
    st.markdown("<div class='section-eyebrow'>WHERE FUNDAMENTALS ARE STRONGEST</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Fundamental Opportunities</div>", unsafe_allow_html=True)
    st.caption(
        "Independent of the Technical/Cyclical screen: this scans Yahoo Finance fundamentals per company "
        "(no bulk endpoint exists for this data), so it is cache-backed and manually refreshed rather than "
        "always-on. Cached results are shown immediately; only expired or missing companies are re-downloaded."
    )

    constituents, source = _constituents(universe)
    tickers = constituents["Ticker"].dropna().astype(str).tolist()

    controls = st.columns([1.6, 1.2, 2.2])
    refresh = controls[0].button("REFRESH FUNDAMENTAL ANALYSIS", type="primary", width="stretch")
    force_full = controls[1].toggle(
        "FORCE FULL RE-DOWNLOAD", value=False,
        help="Ignore the 24-hour cache and re-fetch every company in this universe from Yahoo Finance.",
    )
    controls[2].caption(
        "Company fundamentals change only after earnings releases, so results are cached for 24 hours "
        "per company. Previously scanned companies stay available while a refresh is running."
    )

    state_key = f"fundamental_scan::{universe}"
    scan: FundamentalScanResult | None = st.session_state.get(state_key)

    if refresh:
        if force_full:
            clear_fundamental_cache()
        progress_placeholder = st.empty()

        def _on_progress(done: int, total: int) -> None:
            progress_placeholder.progress(
                done / total if total else 1.0,
                text=f"Scanned {done}/{total} companies...",
            )

        with st.spinner(f"Running fundamental scan across {len(tickers)} companies from {source}..."):
            scan = run_fundamental_scan(tickers, on_progress=_on_progress)
        progress_placeholder.empty()
        st.session_state[state_key] = scan

    render_fundamental_scan_header(scan)
    rows = build_opportunity_rows(scan) if scan is not None else []
    render_fundamental_rankings(rows)
