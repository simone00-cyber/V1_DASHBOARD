from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from analysis.macro import build_macro_comment
from charts.common import create_line_chart, create_yield_curve_chart
from config.universe import (
    BOND_PRICE_PROXIES,
    COMMODITY_UNIVERSE,
    CREDIT_UNIVERSE,
    CRYPTO_UNIVERSE,
    FX_UNIVERSE,
)
from core.metrics import build_market_table, normalized_frame, ratio_series
from data.macro_live import (
    MacroQuote,
    build_global_rates_snapshot,
    load_ecb_aaa_curve,
    load_live_market_quotes,
)
from data.yahoo import download_close_batch, resolve_rate_series
from ui.tables import style_market_table


def _fragment(*, run_every: str):
    fragment = getattr(st, "fragment", None)
    if fragment is None:
        return lambda function: function
    return fragment(run_every=run_every)


@st.cache_data(ttl=55, show_spinner=False)
def _cached_global_rates() -> dict[str, MacroQuote]:
    return build_global_rates_snapshot()


@st.cache_data(ttl=55, show_spinner=False)
def _cached_live_conditions() -> dict[str, MacroQuote]:
    return load_live_market_quotes()


@st.cache_data(ttl=21600, show_spinner=False)
def _cached_ecb_curve() -> pd.DataFrame:
    return load_ecb_aaa_curve()


def _format_value(quote: MacroQuote) -> str:
    if not quote.is_available:
        return "N/D"
    if quote.unit == "%":
        return f"{float(quote.value):.3f}%"
    if quote.unit == "bp":
        return f"{float(quote.value):.0f} bp"
    if quote.label == "VIX":
        return f"{float(quote.value):.2f}"
    return f"{float(quote.value):,.2f}"


def _format_change(quote: MacroQuote) -> str:
    if quote.change is None or not pd.notna(quote.change):
        return ""
    if quote.unit in {"%", "bp"}:
        return f"{float(quote.change):+.1f} bp"
    return f"{float(quote.change):+.2f}"


def _format_timestamp(quote: MacroQuote) -> str:
    if quote.as_of is None:
        return "No timestamp"
    return quote.as_of.strftime("%d %b %Y %H:%M UTC")


def _series_selector(
    label: str,
    options: list[str],
    *,
    default: list[str] | None = None,
    key: str,
    help_text: str | None = None,
) -> list[str]:
    """Render a compact series selector and always return valid columns.

    The selector controls only chart visibility. It never changes the source
    data or the calculations shown elsewhere on the page.
    """
    available = list(dict.fromkeys(str(option) for option in options if str(option)))
    if not available:
        return []
    selected_default = [item for item in (default or available) if item in available]
    if not selected_default:
        selected_default = available[: min(4, len(available))]
    return st.multiselect(
        label,
        options=available,
        default=selected_default,
        key=key,
        help=help_text,
    )


def _selected_frame(frame: pd.DataFrame, selected: list[str]) -> pd.DataFrame:
    columns = [column for column in selected if column in frame.columns]
    return frame[columns].copy() if columns else pd.DataFrame(index=frame.index)


def _render_quote_card(quote: MacroQuote) -> None:
    status_class = quote.status.lower()
    change = _format_change(quote)
    st.markdown(
        f"""
        <div class="macro-live-card">
            <div class="macro-live-card-top">
                <span class="macro-live-label">{quote.label}</span>
                <span class="macro-live-badge {status_class}">{quote.frequency}</span>
            </div>
            <div class="macro-live-value">{_format_value(quote)}</div>
            <div class="macro-live-change">{change or '&nbsp;'}</div>
            <div class="macro-live-time">{_format_timestamp(quote)}</div>
            <div class="macro-live-source">{quote.source}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _macro_css() -> None:
    st.markdown(
        """
        <style>
        .macro-live-card {
            border: 1px solid #303030;
            border-top: 3px solid #f2a900;
            background: linear-gradient(180deg, #111 0%, #090909 100%);
            padding: 13px 14px 11px 14px;
            min-height: 150px;
        }
        .macro-live-card-top { display:flex; justify-content:space-between; gap:8px; align-items:center; }
        .macro-live-label { color:#f2a900; font-size:.78rem; font-weight:800; letter-spacing:.08em; }
        .macro-live-badge { border:1px solid #555; padding:2px 5px; font-size:.58rem; letter-spacing:.06em; color:#cfcfcf; }
        .macro-live-badge.intraday { border-color:#00d26a; color:#00d26a; }
        .macro-live-badge.daily, .macro-live-badge.mixed { border-color:#f2a900; color:#f2a900; }
        .macro-live-badge.stale, .macro-live-badge.unavailable { border-color:#ff4b4b; color:#ff4b4b; }
        .macro-live-value { color:#fff; font-size:1.75rem; font-weight:850; margin-top:12px; line-height:1; }
        .macro-live-change { color:#bdbdbd; font-size:.78rem; margin-top:8px; min-height:18px; }
        .macro-live-time { color:#858585; font-size:.63rem; margin-top:7px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .macro-live-source { color:#606060; font-size:.58rem; margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .macro-refresh-line { color:#737373; font-size:.68rem; margin-top:5px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


@_fragment(run_every="60s")
def render_live_rates_monitor() -> None:
    rates = _cached_global_rates()
    cols = st.columns(4)
    for col, key in zip(cols, ("US 10Y", "BUND 10Y", "BTP-BUND 10Y", "US-DE 10Y")):
        with col:
            _render_quote_card(rates[key])
    st.markdown(
        f"<div class='macro-refresh-line'>Auto-refresh every 60 seconds while this page is open · "
        f"Last page refresh: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}</div>",
        unsafe_allow_html=True,
    )


@_fragment(run_every="60s")
def render_live_financial_conditions() -> None:
    quotes = _cached_live_conditions()
    st.markdown("<div class='terminal-subheader'>LIVE FINANCIAL CONDITIONS</div>", unsafe_allow_html=True)
    cols = st.columns(4)
    for col, key in zip(cols, ("DXY", "VIX", "BRENT", "GOLD")):
        with col:
            _render_quote_card(quotes[key])


def _rates_comment(rates: dict[str, MacroQuote]) -> str:
    comments: list[str] = []
    us10 = rates.get("US 10Y")
    spread = rates.get("BTP-BUND 10Y")
    us_de = rates.get("US-DE 10Y")
    if us10 and us10.is_available and us10.change is not None:
        direction = "rising" if us10.change > 0 else "falling" if us10.change < 0 else "stable"
        comments.append(f"US 10Y yields are {direction} on the latest intraday observation ({us10.change:+.1f} bp).")
    if spread and spread.is_available:
        if spread.change is None:
            comments.append(f"The BTP-Bund spread is {spread.value:.0f} bp.")
        else:
            risk = "widening" if spread.change > 0 else "tightening" if spread.change < 0 else "unchanged"
            comments.append(f"Italian sovereign risk is {risk}; the spread is {spread.value:.0f} bp ({spread.change:+.1f} bp).")
    if us_de and us_de.is_available:
        comments.append(f"The US-Germany 10Y differential is {us_de.value:.0f} bp.")
    return " ".join(comments) or "Rates interpretation is unavailable until the underlying market quotes are loaded."


def _render_european_rates_snapshot(rates: dict[str, MacroQuote]) -> None:
    import plotly.graph_objects as go
    from charts.common import apply_terminal_layout

    labels: list[str] = []
    values: list[float] = []
    for key in ("BUND 10Y", "ITALY 10Y"):
        quote = rates.get(key)
        if quote and quote.is_available:
            labels.append(key)
            values.append(float(quote.value))
    if not values:
        st.warning("European sovereign rates are temporarily unavailable from the configured providers.")
        return
    fig = go.Figure(go.Bar(x=labels, y=values, text=[f"{value:.3f}%" for value in values], textposition="outside"))
    fig.update_layout(title="EUROPEAN 10Y SOVEREIGN YIELDS", yaxis_title="Yield %", showlegend=False)
    st.plotly_chart(apply_terminal_layout(fig, 440), width="stretch", key="macro_european_snapshot")


def render_rates_section() -> None:
    st.markdown("<div class='terminal-subheader'>GLOBAL RATES MONITOR</div>", unsafe_allow_html=True)
    render_live_rates_monitor()

    rates_snapshot = _cached_global_rates()
    st.markdown(f"<div class='report-box'>{_rates_comment(rates_snapshot)}</div>", unsafe_allow_html=True)

    us_rates, symbols = resolve_rate_series(period="2y")
    euro_curve = _cached_ecb_curve()

    us_available = [
        label for label in ("US 13W", "US 2Y", "US 5Y", "US 10Y", "US 30Y")
        if label in us_rates.columns and not us_rates[label].dropna().empty
    ] if not us_rates.empty else []
    euro_available = [
        str(column) for column in euro_curve.columns
        if not euro_curve[column].dropna().empty
    ] if not euro_curve.empty else []

    # First show the two headline curves with stable default maturities.
    # The controls below affect only the historical comparison charts.
    st.markdown("<div class='terminal-subheader'>HEADLINE YIELD CURVES</div>", unsafe_allow_html=True)
    headline_us = [item for item in ("US 2Y", "US 5Y", "US 10Y", "US 30Y") if item in us_available]
    headline_euro = [item for item in ("2Y", "5Y", "10Y", "30Y") if item in euro_available]

    curve_left, curve_right = st.columns(2)
    with curve_left:
        if us_rates.empty or not headline_us:
            st.info("US Treasury curve data are unavailable.")
        else:
            st.plotly_chart(
                create_yield_curve_chart(_selected_frame(us_rates, headline_us)),
                width="stretch",
                key="macro_us_curve_headline",
            )

    with curve_right:
        if euro_curve.empty or not headline_euro:
            st.info("Euro-area AAA curve data are unavailable.")
        else:
            latest = _selected_frame(euro_curve.ffill(), headline_euro).iloc[-1]
            previous = _selected_frame(euro_curve.ffill(), headline_euro).iloc[-6] if len(euro_curve) >= 6 else latest
            curve = pd.DataFrame({"Current": latest, "5 sessions ago": previous})
            import plotly.graph_objects as go
            from charts.common import apply_terminal_layout

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=curve.index, y=curve["Current"], mode="lines+markers", name="Current"))
            fig.add_trace(
                go.Scatter(
                    x=curve.index,
                    y=curve["5 sessions ago"],
                    mode="lines+markers",
                    name="5 sessions ago",
                    line=dict(dash="dash"),
                )
            )
            fig.update_layout(title="EURO AREA AAA YIELD CURVE", yaxis_title="Yield %")
            st.plotly_chart(apply_terminal_layout(fig, 440), width="stretch", key="macro_euro_curve_headline")

    # Controls belong immediately above the charts they modify.
    st.markdown("<div class='terminal-subheader'>CUSTOM YIELD HISTORY</div>", unsafe_allow_html=True)
    control_left, control_right = st.columns(2)
    with control_left:
        selected_us = _series_selector(
            "US TREASURY MATURITIES",
            us_available,
            default=["US 5Y", "US 10Y", "US 30Y"],
            key="macro_selected_us_yields",
            help_text="Choose which Treasury maturities appear in the historical comparison.",
        )
    with control_right:
        euro_defaults = [item for item in ("2Y", "5Y", "10Y", "30Y") if item in euro_available]
        selected_euro = _series_selector(
            "EURO AAA MATURITIES",
            euro_available,
            default=euro_defaults or euro_available[:4],
            key="macro_selected_euro_yields",
            help_text="Choose which official ECB AAA spot maturities appear in the historical comparison.",
        )

    history_left, history_right = st.columns(2)
    with history_left:
        if not us_rates.empty and selected_us:
            st.plotly_chart(
                create_line_chart(
                    _selected_frame(us_rates, selected_us),
                    "US TREASURY YIELDS // HISTORY",
                    "Yield %",
                    400,
                ),
                width="stretch",
                key="macro_us_rates_history",
            )
        else:
            st.info("Select at least one US Treasury maturity.")

    with history_right:
        if not euro_curve.empty and selected_euro:
            st.plotly_chart(
                create_line_chart(
                    _selected_frame(euro_curve, selected_euro),
                    "EURO AAA YIELDS // HISTORY",
                    "Yield %",
                    400,
                ),
                width="stretch",
                key="macro_euro_rates_history",
            )
        else:
            st.info("Select at least one euro-area maturity.")

    if symbols:
        visible_symbols = {label: ticker for label, ticker in symbols.items() if label in selected_us}
        symbol_text = ", ".join(f"{label}: {ticker}" for label, ticker in visible_symbols.items())
        if symbol_text:
            st.caption(f"Visible US history symbols: {symbol_text}. Euro history: official ECB daily AAA spot rates.")


def render_bond_proxies() -> None:
    st.markdown("<div class='terminal-subheader'>SOVEREIGN BOND PRICE PROXIES</div>", unsafe_allow_html=True)
    close = download_close_batch(tuple(BOND_PRICE_PROXIES.values()), period="1y")
    table = build_market_table(close, BOND_PRICE_PROXIES)
    if table.empty:
        st.warning("Proxy obbligazionari non disponibili.")
        return
    reverse = {ticker: name for name, ticker in BOND_PRICE_PROXIES.items()}
    renamed = close.rename(columns=reverse)
    available = [name for name in BOND_PRICE_PROXIES if name in renamed.columns]
    selected = _series_selector(
        "VISIBLE BOND PROXIES",
        available,
        default=available,
        key="macro_selected_bond_proxies",
        help_text="Show or hide individual bond-price and futures proxies.",
    )
    left, right = st.columns([1.7, 1])
    with left:
        if selected:
            st.plotly_chart(
                create_line_chart(
                    normalized_frame(_selected_frame(renamed, selected)),
                    "BOND PRICES / FUTURES // BASE 100",
                    "Base 100",
                    420,
                ),
                width="stretch",
                key="macro_bond_proxies_chart",
            )
        else:
            st.info("Select at least one bond proxy to display the chart.")
    with right:
        visible_table = table[table["Strumento"].isin(selected)] if selected and "Strumento" in table.columns else table.iloc[0:0]
        st.dataframe(style_market_table(visible_table), width="stretch", hide_index=True, height=420)
    st.caption("These are price/futures proxies and are not used to calculate the BTP-Bund yield spread.")


def render_global_macro() -> None:
    _macro_css()
    st.markdown("<div class='section-eyebrow'>MARKET ANALYSIS</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Macro & Rates</div>", unsafe_allow_html=True)
    st.caption(
        "Market prices refresh automatically while the page is open. Official macro and yield-curve series retain their native publication frequency."
    )

    with st.sidebar:
        st.markdown("<div class='terminal-subheader'>MACRO DATA</div>", unsafe_allow_html=True)
        if st.button("REFRESH MACRO DATA", width="stretch"):
            _cached_global_rates.clear()
            _cached_live_conditions.clear()
            _cached_ecb_curve.clear()
            st.rerun()
        st.caption("INTRADAY: Yahoo market data · DAILY: official source · STALE: older than expected")

    render_rates_section()
    render_live_financial_conditions()
    render_bond_proxies()

    macro_tickers = tuple(
        list(FX_UNIVERSE.values())
        + list(COMMODITY_UNIVERSE.values())
        + list(CRYPTO_UNIVERSE.values())
        + list(CREDIT_UNIVERSE.values())
    )
    with st.spinner("Updating macro assets..."):
        close = download_close_batch(macro_tickers, period="1y")

    fx_table = build_market_table(close, FX_UNIVERSE)
    commodity_table = build_market_table(close, COMMODITY_UNIVERSE)
    crypto_table = build_market_table(close, CRYPTO_UNIVERSE)
    credit_table = build_market_table(close, CREDIT_UNIVERSE)
    tabs = st.tabs(["FX", "COMMODITIES", "CRYPTO", "CREDIT"])

    with tabs[0]:
        if fx_table.empty:
            st.warning("Dati FX non disponibili.")
        else:
            reverse = {ticker: name for name, ticker in FX_UNIVERSE.items()}
            renamed = close.rename(columns=reverse)
            available = [name for name in FX_UNIVERSE if name in renamed.columns]
            selected = _series_selector(
                "VISIBLE FX SERIES",
                available,
                default=available,
                key="macro_selected_fx",
                help_text="Choose which currency series appear in the chart and table.",
            )
            left, right = st.columns([1.6, 1])
            with left:
                if selected:
                    st.plotly_chart(
                        create_line_chart(
                            normalized_frame(_selected_frame(renamed, selected)),
                            "FX PERFORMANCE // BASE 100",
                            "Base 100",
                            450,
                        ),
                        width="stretch",
                        key="macro_fx",
                    )
                else:
                    st.info("Select at least one FX series to display the chart.")
            with right:
                visible_table = fx_table[fx_table["Strumento"].isin(selected)] if selected else fx_table.iloc[0:0]
                st.dataframe(style_market_table(visible_table), width="stretch", hide_index=True, height=450)

    with tabs[1]:
        if commodity_table.empty:
            st.warning("Dati commodity non disponibili.")
        else:
            reverse = {ticker: name for name, ticker in COMMODITY_UNIVERSE.items()}
            renamed = close.rename(columns=reverse)
            available = [name for name in COMMODITY_UNIVERSE if name in renamed.columns]
            selected = _series_selector(
                "VISIBLE COMMODITIES",
                available,
                default=available,
                key="macro_selected_commodities",
                help_text="Choose which commodity series appear in the chart and table.",
            )
            left, right = st.columns([1.6, 1])
            with left:
                if selected:
                    st.plotly_chart(
                        create_line_chart(
                            normalized_frame(_selected_frame(renamed, selected)),
                            "COMMODITIES // BASE 100",
                            "Base 100",
                            450,
                        ),
                        width="stretch",
                        key="macro_commodities",
                    )
                else:
                    st.info("Select at least one commodity to display the chart.")
            with right:
                visible_table = commodity_table[commodity_table["Strumento"].isin(selected)] if selected else commodity_table.iloc[0:0]
                st.dataframe(style_market_table(visible_table), width="stretch", hide_index=True, height=450)

    with tabs[2]:
        if crypto_table.empty:
            st.warning("Dati crypto non disponibili.")
        else:
            reverse = {ticker: name for name, ticker in CRYPTO_UNIVERSE.items()}
            renamed = close.rename(columns=reverse)
            available = [name for name in CRYPTO_UNIVERSE if name in renamed.columns]
            selected = _series_selector(
                "VISIBLE CRYPTO SERIES",
                available,
                default=available,
                key="macro_selected_crypto",
                help_text="Choose which crypto series appear in the chart and table.",
            )
            if selected:
                st.plotly_chart(
                    create_line_chart(
                        normalized_frame(_selected_frame(renamed, selected)),
                        "CRYPTO // BASE 100",
                        "Base 100",
                        450,
                    ),
                    width="stretch",
                    key="macro_crypto",
                )
            else:
                st.info("Select at least one crypto series to display the chart.")
            visible_table = crypto_table[crypto_table["Strumento"].isin(selected)] if selected else crypto_table.iloc[0:0]
            st.dataframe(style_market_table(visible_table), width="stretch", hide_index=True)

    with tabs[3]:
        if credit_table.empty:
            st.warning("Dati credit proxy non disponibili.")
        else:
            ratios = pd.DataFrame({
                "HYG/LQD": ratio_series(close, "HYG", "LQD"),
                "HYG/TLT": ratio_series(close, "HYG", "TLT"),
            }).dropna(how="all")
            available_ratios = list(ratios.columns)
            selected_ratios = _series_selector(
                "VISIBLE CREDIT RATIOS",
                available_ratios,
                default=available_ratios,
                key="macro_selected_credit_ratios",
                help_text="Choose which credit-risk ratios appear in the chart.",
            )
            left, right = st.columns([1.5, 1])
            with left:
                if selected_ratios:
                    st.plotly_chart(
                        create_line_chart(
                            normalized_frame(_selected_frame(ratios, selected_ratios)),
                            "CREDIT RISK RATIOS // BASE 100",
                            "Base 100",
                            450,
                        ),
                        width="stretch",
                        key="macro_credit",
                    )
                else:
                    st.info("Select at least one credit ratio to display the chart.")
            with right:
                st.dataframe(style_market_table(credit_table), width="stretch", hide_index=True, height=450)

    rates, _ = resolve_rate_series(period="6mo")
    comment = build_macro_comment(rates, fx_table, commodity_table, close)
    st.markdown("<div class='terminal-subheader'>MACRO STRATEGIST COMMENT</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='report-box'>{comment}</div>", unsafe_allow_html=True)

    st.markdown("<div class='terminal-subheader'>DATA PROVENANCE</div>", unsafe_allow_html=True)
    st.caption(
        "US Treasury yields, DXY, VIX, Brent and Gold: Yahoo Finance market data. "
        "Bund 10Y and Italy 10Y: Investing.com public sovereign-yield pages, with the Deutsche Bundesbank official daily Bund series as fallback. "
        "BTP-Bund and US-Germany differentials are calculated from matching 10-year yields; the direct Investing.com spread is used only as fallback. "
        "Euro AAA curve: ECB Data Portal. No ETF or bond-future prices are used as substitutes for sovereign yields."
    )
