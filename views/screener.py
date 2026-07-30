from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from screener.engine import (
    PERFORMANCE_WINDOWS,
    RELATIVE_STRENGTH_WINDOWS,
    ScreenerResult,
    analyse_universe,
    build_sector_performance,
    download_universe_ohlc,
    sort_by_methodology,
)
from screener.opportunities import (
    annotate_conviction,
    build_opportunity_funnel,
    build_snapshot,
    classify_sector_group,
    select_top_opportunities,
)
from screener.relative_strength import (
    RS_LAB_WINDOWS,
    build_relative_strength_lab,
    build_sector_composites,
)
from screener.universes import UNIVERSES, load_universe
from ui.opportunity_cards import (
    render_leaders_laggards,
    render_opportunity_funnel,
    render_sector_leadership,
    render_snapshot,
    render_top_opportunities,
)


SCREEN_PERIOD = "max"


@st.cache_data(ttl=86400, show_spinner=False)
def _constituents(name: str) -> tuple[pd.DataFrame, str]:
    return load_universe(name)


@st.cache_data(ttl=3600, show_spinner=False)
def _run_screen(name: str) -> tuple[ScreenerResult, str, int]:
    constituents, source = _constituents(name)
    benchmark = UNIVERSES[name].benchmark_ticker
    result = analyse_universe(constituents, period=SCREEN_PERIOD, benchmark_ticker=benchmark)
    return result, source, len(constituents)


def _fmt_table(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    numeric = [
        "Last",
        "1D %",
        "1W %",
        "1M %",
        "1Y %",
        "Quarterly CM",
        "Monthly CM",
        "Weekly CM",
        "Performance",
        "Median",
        "Best",
        "Worst",
        "RS 1W %",
        "RS 1M %",
        "RS 3M %",
        "RS 6M %",
        "RS 1Y %",
        "RS Ratio 1Y",
    ]
    for column in numeric:
        if column in result:
            result[column] = pd.to_numeric(result[column], errors="coerce").round(2)
    return result


def _methodology_columns() -> list[str]:
    return [
        "Order",
        "Ticker",
        "Company",
        "Sector",
        "Matrix Action",
        "Rating Visual",
        "Rating",
        "Quarterly Trend",
        "Monthly Trend",
        "Weekly Turn",
        "Quarterly CM",
        "Monthly CM",
        "Weekly CM",
        "Last",
        "Data Date",
    ]


def _action_badge_counts(rows: pd.DataFrame) -> dict[str, int]:
    return {
        "BUY": int((rows["Matrix Action"] == "BUY").sum()),
        "TAKE PROFIT": int((rows["Matrix Action"] == "TAKE PROFIT").sum()),
        "SELL SHORT": int((rows["Matrix Action"] == "SELL SHORT").sum()),
        "NO NEW JUNCTION": int((rows["Matrix Action"] == "NESSUNA NUOVA GIUNTURA").sum()),
    }


def _render_methodology_screener(rows: pd.DataFrame, universe_size: int) -> None:
    counts = _action_badge_counts(rows)
    cards = st.columns(6)
    cards[0].metric("CONSTITUENTS", universe_size)
    cards[1].metric("ANALYSED", len(rows))
    cards[2].metric("BUY", counts["BUY"])
    cards[3].metric("TAKE PROFIT", counts["TAKE PROFIT"])
    cards[4].metric("SELL SHORT", counts["SELL SHORT"])
    cards[5].metric("NO NEW JUNCTION", counts["NO NEW JUNCTION"])

    st.caption(
        "Signals and Reward/Risk ratings are generated directly from the implemented public "
        "quarterly/monthly/weekly matrix. No synthetic score or weighted ranking is used."
    )

    controls = st.columns([1.3, 1.15, 1.25, 1.2, 1])
    search = controls[0].text_input("SEARCH TICKER / COMPANY", value="", placeholder="e.g. AAPL, Eni")
    sectors = ["ALL"] + sorted(rows["Sector"].dropna().astype(str).unique())
    sector = controls[1].selectbox("SECTOR", sectors, key="method_sector")

    actions = ["BUY", "TAKE PROFIT", "SELL SHORT", "NESSUNA NUOVA GIUNTURA"]
    selected_actions = controls[2].multiselect(
        "MATRIX ACTION",
        actions,
        default=actions,
        format_func=lambda value: "NO NEW JUNCTION" if value == "NESSUNA NUOVA GIUNTURA" else value,
    )
    min_rating = controls[3].selectbox("MIN REWARD/RISK", [0, 1, 2, 3, 4], index=0)
    only_latest_signal = controls[4].toggle("SIGNALS ONLY", value=False)

    filtered = rows.copy()
    if search.strip():
        needle = search.strip().lower()
        mask = (
            filtered["Ticker"].astype(str).str.lower().str.contains(needle, regex=False)
            | filtered["Company"].astype(str).str.lower().str.contains(needle, regex=False)
        )
        filtered = filtered[mask]
    if sector != "ALL":
        filtered = filtered[filtered["Sector"].astype(str) == sector]
    if selected_actions:
        filtered = filtered[filtered["Matrix Action"].isin(selected_actions)]
    filtered = filtered[filtered["Rating"] >= min_rating]
    if only_latest_signal:
        filtered = filtered[filtered["Matrix Action"] != "NESSUNA NUOVA GIUNTURA"]

    filtered = sort_by_methodology(filtered)
    st.caption(f"{len(filtered)} securities match the active methodology filters.")
    st.dataframe(
        _fmt_table(filtered[_methodology_columns()]),
        width="stretch",
        hide_index=True,
        height=690,
        column_config={
            "Rating Visual": st.column_config.TextColumn("R/R"),
            "Rating": st.column_config.NumberColumn("R/R Level", format="%d"),
            "Matrix Action": st.column_config.TextColumn("Action"),
        },
    )
    st.download_button(
        "DOWNLOAD METHODOLOGY SCREEN",
        filtered.to_csv(index=False).encode("utf-8"),
        file_name="methodology_screener.csv",
        mime="text/csv",
        width="content",
    )


BENCHMARK_PRESETS: dict[str, str] = {
    "SELECTED INDEX": "",
    "NASDAQ 100": "^NDX",
    "S&P 500": "^GSPC",
    "FTSE MIB": "FTSEMIB.MI",
    "DAX 40": "^GDAXI",
    "EURO STOXX 50": "^STOXX50E",
    "RUSSELL 2000": "^RUT",
    "MSCI WORLD ETF": "URTH",
    "CUSTOM": "",
}


def _parse_custom_tickers(value: str) -> list[str]:
    tokens = value.replace(";", ",").replace("\n", ",").split(",")
    return list(dict.fromkeys(token.strip().upper() for token in tokens if token.strip()))


@st.cache_data(ttl=3600, show_spinner=False)
def _relative_lab_prices(tickers: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    return download_universe_ohlc(list(tickers), period="max", chunk_size=20)


def _line_chart(frame: pd.DataFrame, title: str, y_title: str) -> go.Figure:
    fig = go.Figure()
    for column in frame.columns:
        width = 3.2 if column.startswith("BENCHMARK:") else 2.0
        dash = "dash" if column.startswith("SECTOR:") else "solid"
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[column],
                mode="lines",
                name=column,
                line={"width": width, "dash": dash},
                hovertemplate=f"{column}<br>%{{x|%d %b %Y}}<br>%{{y:.2f}}<extra></extra>",
            )
        )
    fig.update_layout(
        template="plotly_dark",
        title=title,
        height=590,
        margin=dict(l=10, r=15, t=55, b=15),
        xaxis_title="",
        yaxis_title=y_title,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.add_hline(y=100, line_dash="dot", opacity=0.45)
    return fig


def _render_relative_strength(rows: pd.DataFrame, universe: str, initial_ticker: str | None = None) -> None:
    constituents, _ = _constituents(universe)
    universe_tickers = constituents["Ticker"].dropna().astype(str).tolist()
    ticker_labels = {
        str(row["Ticker"]): f"{row['Ticker']} — {row['Company']}"
        for _, row in constituents.iterrows()
    }

    st.markdown("<div class='terminal-subheader'>RELATIVE STRENGTH LAB</div>", unsafe_allow_html=True)
    st.caption(
        "Interactive benchmark laboratory. Relative Strength is a framework comparison tool and does not alter "
        "the public cyclical Matrix signals shown in the Screener."
    )

    top = st.columns([1.2, 1.0, 1.05, 1.65])
    benchmark_choice = top[0].selectbox(
        "BENCHMARK",
        list(BENCHMARK_PRESETS),
        index=0,
        key="rs_lab_benchmark_choice",
    )
    custom_benchmark = top[1].text_input(
        "CUSTOM BENCHMARK",
        value="",
        placeholder="e.g. QQQ, SPY, BTC-USD",
        disabled=benchmark_choice != "CUSTOM",
        key="rs_lab_custom_benchmark",
    ).strip().upper()
    selected_window = top[2].selectbox(
        "ANALYSIS WINDOW",
        list(RS_LAB_WINDOWS),
        index=3,
        key="rs_lab_window",
    )
    top[3].markdown(
        "<div class='small-note'><br>All series use adjusted prices and are rebased to 100 at the common start date. "
        "A rising RS ratio means outperformance versus the benchmark.</div>",
        unsafe_allow_html=True,
    )

    if benchmark_choice == "SELECTED INDEX":
        benchmark = UNIVERSES[universe].benchmark_ticker
    elif benchmark_choice == "CUSTOM":
        benchmark = custom_benchmark
    else:
        benchmark = BENCHMARK_PRESETS[benchmark_choice]

    default_tickers = universe_tickers[: min(5, len(universe_tickers))]
    initial_ticker = initial_ticker.strip().upper() if initial_ticker else None
    if initial_ticker and initial_ticker in universe_tickers:
        default_tickers = [initial_ticker] + [ticker for ticker in default_tickers if ticker != initial_ticker]
    selected_tickers = st.multiselect(
        "SECURITIES TO BENCHMARK",
        options=universe_tickers,
        default=default_tickers,
        format_func=lambda ticker: ticker_labels.get(ticker, ticker),
        key="rs_lab_securities",
    )
    custom_value = st.text_input(
        "ADD CUSTOM YAHOO TICKERS",
        value="",
        placeholder="ASML.AS, SHEL, TTE.PA, BTC-USD",
        help="Separate symbols with commas. Use Yahoo Finance ticker syntax.",
        key="rs_lab_custom_tickers",
    )
    custom_tickers = list(_parse_custom_tickers(custom_value))
    if initial_ticker and initial_ticker not in universe_tickers and initial_ticker not in custom_tickers:
        custom_tickers.insert(0, initial_ticker)
    selected_tickers = list(dict.fromkeys(selected_tickers + custom_tickers))

    sector_choices = sorted(constituents["Sector"].dropna().astype(str).unique())
    selected_sectors = st.multiselect(
        "OPTIONAL EQUAL-WEIGHT SECTOR COMPOSITES",
        sector_choices,
        default=[],
        max_selections=4,
        key="rs_lab_sectors",
    )

    if not benchmark:
        st.info("Enter a valid custom benchmark ticker.")
        return
    if not selected_tickers and not selected_sectors:
        st.info("Select at least one security or sector composite.")
        return

    sector_members = constituents.loc[
        constituents["Sector"].astype(str).isin(selected_sectors), "Ticker"
    ].dropna().astype(str).tolist()
    requested = tuple(dict.fromkeys([benchmark] + selected_tickers + sector_members))

    try:
        with st.spinner("Building Relative Strength Lab..."):
            price_frames = _relative_lab_prices(requested)
    except Exception as exc:
        st.error(f"Relative Strength Lab unavailable: {exc}")
        return

    periods = RS_LAB_WINDOWS[selected_window]
    sector_composites = build_sector_composites(
        price_frames,
        constituents,
        selected_sectors,
        periods,
    )
    lab = build_relative_strength_lab(
        price_frames=price_frames,
        benchmark_ticker=benchmark,
        comparison_tickers=selected_tickers,
        periods=periods,
        sector_composites=sector_composites,
    )
    if lab.normalized.empty:
        missing = sorted(set(requested) - set(price_frames))
        st.error("Not enough common price history to build the comparison.")
        if missing:
            st.caption(f"Unavailable tickers: {', '.join(missing)}")
        return

    normalized = lab.normalized.rename(columns={benchmark: f"BENCHMARK: {benchmark}"})
    stats = lab.statistics.copy()
    metadata = rows.set_index("Ticker") if not rows.empty else pd.DataFrame()
    if not stats.empty and not metadata.empty:
        stats = stats.join(
            metadata[["Company", "Sector", "Matrix Action", "Rating Visual"]],
            on="Ticker",
            how="left",
        )

    leaders = int((stats["Excess Return pp"] > 0).sum()) if not stats.empty else 0
    laggards = int((stats["Excess Return pp"] < 0).sum()) if not stats.empty else 0
    cards = st.columns(6)
    cards[0].metric("BENCHMARK", benchmark)
    cards[1].metric("WINDOW", selected_window)
    cards[2].metric("SECURITIES", len(selected_tickers))
    cards[3].metric("OUTPERFORMERS", leaders)
    cards[4].metric("UNDERPERFORMERS", laggards)
    if not stats.empty:
        leader = stats.iloc[0]
        cards[5].metric("LEADER", str(leader["Ticker"]), f"{leader['Excess Return pp']:+.2f} pp")
    else:
        cards[5].metric("LEADER", "N/A")

    chart_col, list_col = st.columns([2.15, 0.85])
    with chart_col:
        st.plotly_chart(
            _line_chart(normalized, "NORMALIZED PERFORMANCE", "Indexed performance (start = 100)"),
            width="stretch",
            key="rs_lab_normalized_chart",
        )
    with list_col:
        st.markdown("<div class='terminal-subheader'>LEADER BOARD</div>", unsafe_allow_html=True)
        if stats.empty:
            st.info("No security statistics available.")
        else:
            status_filter = st.radio(
                "RELATIVE STATUS",
                ["ALL", "OUTPERFORM", "UNDERPERFORM"],
                index=0,
                horizontal=True,
                key="rs_lab_status_filter",
            )
            sector_filter_options = ["ALL"] + sorted(stats["Sector"].dropna().astype(str).unique()) if "Sector" in stats else ["ALL"]
            sector_filter = st.selectbox("SECTOR", sector_filter_options, key="rs_lab_sector_filter")
            action_options = ["ALL"] + sorted(stats["Matrix Action"].dropna().astype(str).unique()) if "Matrix Action" in stats else ["ALL"]
            action_filter = st.selectbox("MATRIX ACTION", action_options, key="rs_lab_action_filter")
            min_excess = st.number_input("MIN EXCESS (PP)", value=-100.0, step=1.0, key="rs_lab_min_excess")

            filtered = stats[stats["Excess Return pp"] >= min_excess].copy()
            if status_filter == "OUTPERFORM":
                filtered = filtered[filtered["Excess Return pp"] > 0]
            elif status_filter == "UNDERPERFORM":
                filtered = filtered[filtered["Excess Return pp"] < 0]
            if sector_filter != "ALL" and "Sector" in filtered:
                filtered = filtered[filtered["Sector"].astype(str) == sector_filter]
            if action_filter != "ALL" and "Matrix Action" in filtered:
                filtered = filtered[filtered["Matrix Action"].astype(str) == action_filter]

            filtered.insert(0, "Rank", range(1, len(filtered) + 1))
            display_cols = [c for c in ["Rank", "Ticker", "Excess Return pp", "Matrix Action", "Rating Visual"] if c in filtered]
            st.dataframe(
                _fmt_table(filtered[display_cols]),
                width="stretch",
                hide_index=True,
                height=455,
                column_config={
                    "Excess Return pp": st.column_config.NumberColumn("EXCESS", format="%+.2f pp"),
                    "Rating Visual": st.column_config.TextColumn("R/R"),
                },
            )

    detail_tabs = st.tabs(["RS RATIO", "STATISTICS", "LEADER ROTATION", "RS HEATMAP"])
    with detail_tabs[0]:
        if lab.relative_ratio.empty:
            st.info("Relative-ratio series unavailable.")
        else:
            st.plotly_chart(
                _line_chart(lab.relative_ratio, "RELATIVE STRENGTH RATIO", "RS ratio (start = 100)"),
                width="stretch",
                key="rs_lab_ratio_chart",
            )
    with detail_tabs[1]:
        if stats.empty:
            st.info("Statistics unavailable.")
        else:
            focus = st.selectbox("FOCUS SECURITY", stats["Ticker"].tolist(), key="rs_lab_focus")
            focus_row = stats.loc[stats["Ticker"] == focus].iloc[0]
            focus_cards = st.columns(6)
            focus_cards[0].metric("RETURN", f"{focus_row['Return %']:+.2f}%")
            focus_cards[1].metric("BENCHMARK", f"{focus_row['Benchmark %']:+.2f}%")
            focus_cards[2].metric("EXCESS", f"{focus_row['Excess Return pp']:+.2f} pp")
            focus_cards[3].metric("VOLATILITY", f"{focus_row['Volatility %']:.2f}%")
            focus_cards[4].metric("CORRELATION", f"{focus_row['Correlation']:.2f}")
            focus_cards[5].metric("BETA", f"{focus_row['Beta']:.2f}")
            st.dataframe(_fmt_table(stats), width="stretch", hide_index=True, height=430)
    with detail_tabs[2]:
        if lab.monthly_leaders.empty:
            st.info("Leader rotation requires more monthly observations.")
        else:
            current = lab.monthly_leaders.iloc[-1]
            previous = lab.monthly_leaders.iloc[-2] if len(lab.monthly_leaders) > 1 else current
            rotation_cards = st.columns(4)
            rotation_cards[0].metric("CURRENT LEADER", current["Leader"], f"{current['Leader Excess pp']:+.2f} pp")
            rotation_cards[1].metric("PRIOR LEADER", previous["Leader"], f"{previous['Leader Excess pp']:+.2f} pp")
            rotation_cards[2].metric("CURRENT LAGGARD", current["Laggard"], f"{current['Laggard Excess pp']:+.2f} pp")
            rotation_cards[3].metric("ROTATION", "YES" if current["Leader"] != previous["Leader"] else "NO")
            st.dataframe(_fmt_table(lab.monthly_leaders.iloc[::-1]), width="stretch", hide_index=True, height=420)
    with detail_tabs[3]:
        if lab.heatmap.empty:
            st.info("Heatmap unavailable.")
        else:
            heatmap = lab.heatmap.copy()
            fig = go.Figure(
                data=go.Heatmap(
                    z=heatmap.values,
                    x=heatmap.columns,
                    y=heatmap.index,
                    zmid=0,
                    colorscale="RdYlGn",
                    colorbar={"title": "Excess pp"},
                    text=np.round(heatmap.values, 1),
                    texttemplate="%{text:+.1f}",
                    hovertemplate="%{y}<br>%{x}: %{z:+.2f} pp<extra></extra>",
                )
            )
            fig.update_layout(template="plotly_dark", height=max(420, 34 * len(heatmap)), margin=dict(l=10, r=10, t=25, b=10))
            st.plotly_chart(fig, width="stretch", key="rs_lab_heatmap")

    export = stats.to_csv(index=False).encode("utf-8") if not stats.empty else b""
    st.download_button(
        "DOWNLOAD RS LAB STATISTICS",
        export,
        file_name=f"relative_strength_lab_{universe.lower().replace(' ', '_')}.csv",
        mime="text/csv",
        disabled=stats.empty,
        width="content",
    )


def render_relative_strength_lab(*, initial_ticker: str | None = None) -> None:
    """Render the complete Relative Strength Lab as a reusable workspace module."""
    header = st.columns([1.35, 0.8, 2.0])
    universe = header[0].selectbox("INDEX UNIVERSE", list(UNIVERSES), index=0, key="workspace_rs_universe")
    refresh = header[1].button("REFRESH RS DATA", width="stretch", key="workspace_rs_refresh")
    header[2].caption("The full laboratory is preserved: benchmark selection, multiple securities, sector composites, ratio, statistics, rotation and heatmap.")
    if refresh:
        _run_screen.clear()
        _constituents.clear()
    try:
        with st.spinner(f"Loading {universe} Relative Strength universe..."):
            result, source, universe_size = _run_screen(universe)
    except Exception as exc:
        st.error(f"Relative Strength Lab unavailable: {exc}")
        return
    st.caption(f"Universe source: {source} | Analysed: {len(result.rows)}/{universe_size}")
    _render_relative_strength(result.rows, universe, initial_ticker=initial_ticker)

def render_market_screener() -> None:
    st.markdown("<div class='section-eyebrow'>WHERE OPPORTUNITY IS CONCENTRATING</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Opportunities</div>", unsafe_allow_html=True)
    st.caption(
        "Signals follow the implemented public cyclical matrix; sector leadership and leaders/laggards "
        "use adjusted-price performance over the selected window."
    )

    controls = st.columns([1.25, 1, 2.75])
    universe = controls[0].selectbox("INDEX UNIVERSE", list(UNIVERSES), index=0)
    refresh = controls[1].button("REFRESH", type="primary", width="stretch")
    controls[2].markdown(
        "<div class='small-note'><br>Price history is managed internally for indicator calculation and is not a user setting. "
        "Results are cached for one hour.</div>",
        unsafe_allow_html=True,
    )

    if refresh:
        _run_screen.clear()
        _constituents.clear()

    try:
        loading = st.empty()
        with loading.container():
            st.markdown("### MARKET SCREENER IS LOADING")
            progress = st.progress(12, text=f"Loading {universe} constituents...")
            progress.progress(32, text="Downloading and validating adjusted price histories...")
            progress.progress(58, text="Computing quarterly, monthly and weekly Composite Momentum...")
            result, source, universe_size = _run_screen(universe)
            progress.progress(82, text="Applying the public Matrix and Reward/Risk ratings...")
            progress.progress(100, text="Building the opportunity workspace...")
        loading.empty()
    except Exception as exc:
        loading.empty()
        st.error(f"Screener unavailable: {exc}")
        return

    rows = result.rows
    if rows.empty:
        st.error("No securities could be analysed.")
        if not result.failures.empty:
            st.dataframe(result.failures, width="stretch", hide_index=True)
        return

    st.caption(
        f"Universe source: {source} | Analysed: {len(rows)}/{universe_size} | "
        f"Updated: {pd.Timestamp.utcnow().strftime('%d %b %Y, %H:%M UTC')}"
    )

    window_controls = st.columns([1.2, 3.8])
    window_label = window_controls[0].selectbox(
        "PERFORMANCE WINDOW",
        list(PERFORMANCE_WINDOWS),
        index=2,
        key="opportunities_window",
    )
    performance_column = PERFORMANCE_WINDOWS[window_label][0]
    window_controls[1].markdown(
        "<div class='small-note'><br>Sector Leadership and Leaders/Laggards use this window. "
        "Top Opportunities and the Opportunity Funnel follow the public matrix directly and are window-independent.</div>",
        unsafe_allow_html=True,
    )

    annotated = annotate_conviction(rows)
    sectors = classify_sector_group(build_sector_performance(rows, performance_column))
    snapshot = build_snapshot(annotated, sectors, performance_column, window_label)

    # --- Above the fold: snapshot, top opportunities, sector leadership ---
    render_snapshot(snapshot)
    render_top_opportunities(select_top_opportunities(annotated, limit=6))
    render_sector_leadership(sectors, window_label)

    # --- Leaders / laggards and the research funnel ---
    performance_rows = rows.dropna(subset=[performance_column])
    render_leaders_laggards(
        performance_rows.nlargest(10, performance_column),
        performance_rows.nsmallest(10, performance_column),
        performance_column,
    )
    render_opportunity_funnel(build_opportunity_funnel(annotated), annotated)

    # --- Progressive disclosure: full universe, then methodology/provenance ---
    with st.expander("FULL UNIVERSE — SEARCH, FILTER & EXPORT", expanded=False):
        _render_methodology_screener(rows, universe_size)

    with st.expander("METHODOLOGY, PROVENANCE & DATA AUDIT", expanded=False):
        st.write(
            "The Screener does not use an Opportunity Score, Cyclical Score, weighted average or price-performance rank. "
            "Matrix Action and Reward/Risk Rating are the direct outputs of the implemented public quarterly/monthly/weekly matrix. "
            "The Conviction Tier shown in the Opportunity Funnel only relabels these same outputs for research priority "
            "(BUY with Reward/Risk ≥ 3 is 'High Conviction', BUY with a lower rating is 'Emerging', no new weekly junction "
            "is 'Watchlist', TAKE PROFIT is 'Deteriorating' and SELL SHORT is 'Avoid') — it introduces no new score."
        )
        st.write(
            "Display order is non-numeric and transparent: Matrix Action, published Reward/Risk rating, "
            "quarterly direction, monthly direction and Composite values as tie-breakers."
        )
        st.write(
            "Sector Leadership is the equal-weight mean adjusted-price return of constituents in each sector. "
            "Leaders/Laggards ranks individual securities only by adjusted-price return over the selected window."
        )
        st.write("Adjusted prices are used to neutralise dividends and splits, consistently with the terminal technical engine.")

        if not result.failures.empty:
            st.markdown("<div class='terminal-subheader'>FAILED SECURITIES</div>", unsafe_allow_html=True)
            st.dataframe(result.failures, width="stretch", hide_index=True, height=350)
            st.download_button(
                "DOWNLOAD FAILURE LOG",
                result.failures.to_csv(index=False).encode("utf-8"),
                file_name="screener_failures.csv",
                mime="text/csv",
            )
