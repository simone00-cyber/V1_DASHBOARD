from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from fundamentals.engine import INSUFFICIENT_DATA_MESSAGE
from fundamentals.models import FundamentalAnalysis, StatementSeries
from fundamentals.provenance import methodology_coverage
from ui.components import band_color, fmt_money, fmt_pct, stars


def render_business_quality_panel(fundamental: FundamentalAnalysis) -> None:
    st.markdown("<div class='terminal-subheader'>BUSINESS QUALITY</div>", unsafe_allow_html=True)
    if not fundamental.sufficient or fundamental.quality is None:
        st.info(fundamental.insufficiency_reason or INSUFFICIENT_DATA_MESSAGE)
        return

    quality = fundamental.quality
    for label, score, reason in (
        ("Business Quality", quality.business_quality, quality.business_quality_reason),
        ("Financial Strength", quality.financial_strength, quality.financial_strength_reason),
        ("Growth Quality", quality.growth_quality, quality.growth_quality_reason),
        ("Profitability", quality.profitability, quality.profitability_reason),
        ("Capital Allocation", quality.capital_allocation, quality.capital_allocation_reason),
    ):
        display = f"{stars(score)} ({score}/100)" if score is not None else "N/A"
        st.markdown(
            f"<div class='star-row'><span class='star-label'>{html.escape(label)}</span>"
            f"<span class='stars'>{html.escape(display)}</span></div>",
            unsafe_allow_html=True,
        )
        if score is not None:
            st.caption(reason)


def render_fundamental_narrative_panel(fundamental: FundamentalAnalysis) -> None:
    st.markdown("<div class='terminal-subheader'>AI FUNDAMENTAL REPORT</div>", unsafe_allow_html=True)

    if not fundamental.sufficient or fundamental.narrative is None:
        st.info(fundamental.insufficiency_reason or INSUFFICIENT_DATA_MESSAGE)
        return

    narrative = fundamental.narrative

    def _chip_list(items: tuple[str, ...], limit: int = 2) -> str:
        return "".join(f"<li>{html.escape(item)}</li>" for item in items[:limit])

    cols = st.columns(2)
    with cols[0]:
        st.markdown("**Opportunities**", unsafe_allow_html=True)
        if narrative.opportunities:
            st.markdown(f"<ul class='evidence-list'>{_chip_list(narrative.opportunities)}</ul>", unsafe_allow_html=True)
        else:
            st.caption("None identified from the available data.")
    with cols[1]:
        st.markdown("**Risks**", unsafe_allow_html=True)
        if narrative.risks:
            st.markdown(f"<ul class='evidence-list'>{_chip_list(narrative.risks)}</ul>", unsafe_allow_html=True)
        else:
            st.caption("None identified from the available data.")

    with st.expander("Full narrative detail (what improved, what deteriorated, strengths, weaknesses)", expanded=False):
        detail_cols = st.columns(2)
        with detail_cols[0]:
            st.markdown("**What improved**")
            _bullet_or_caption(narrative.improved)
            st.markdown("**Strengths**")
            _bullet_or_caption(narrative.strengths)
        with detail_cols[1]:
            st.markdown("**What deteriorated**")
            _bullet_or_caption(narrative.deteriorated)
            st.markdown("**Weaknesses**")
            _bullet_or_caption(narrative.weaknesses)


def _bullet_or_caption(items: tuple[str, ...]) -> None:
    if not items:
        st.caption("None identified from the available data.")
        return
    st.markdown(
        "<ul class='evidence-list'>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>",
        unsafe_allow_html=True,
    )


def _range_position(value: float, low: float, high: float) -> float:
    if high <= low:
        return 50.0
    return max(0.0, min(100.0, (value - low) / (high - low) * 100.0))


def render_valuation_panel(fundamental: FundamentalAnalysis) -> None:
    st.markdown("<div class='terminal-subheader'>VALUATION</div>", unsafe_allow_html=True)

    if not fundamental.sufficient or fundamental.valuation is None:
        st.info(fundamental.insufficiency_reason or INSUFFICIENT_DATA_MESSAGE)
        return

    valuation = fundamental.valuation
    if not valuation.methods or valuation.base_fair_value is None:
        st.info(
            f"{INSUFFICIENT_DATA_MESSAGE} Neither the earnings-power nor the FCF-power valuation method could "
            "be computed for this ticker (EPS and free cash flow are both negative or unavailable)."
        )
        return

    bear = valuation.bear_fair_value if valuation.bear_fair_value is not None else valuation.base_fair_value
    base = valuation.base_fair_value
    bull = valuation.bull_fair_value if valuation.bull_fair_value is not None else valuation.base_fair_value
    price = valuation.current_price

    low, high = min(bear, base, bull), max(bear, base, bull)
    if price is not None:
        low, high = min(low, price), max(high, price)
    padding = max((high - low) * 0.10, high * 0.01, 0.01)
    low, high = low - padding, high + padding

    ticks = "".join(
        f"<div class='valuation-range-marker' style='left:{_range_position(value, low, high):.1f}%'></div>"
        for value in (bear, base, bull)
    )
    price_tick = ""
    if price is not None:
        price_tick = (
            f"<div class='valuation-range-marker is-price' style='left:{_range_position(price, low, high):.1f}%'>"
            f"<span class='marker-tag'>PRICE</span></div>"
        )

    st.markdown(
        "<div class='valuation-range'>"
        f"<div class='valuation-range-track'>{ticks}{price_tick}</div>"
        "<div class='valuation-range-labels'><span>BEAR</span><span>BASE</span><span>BULL</span></div>"
        "<div class='valuation-range-values'>"
        f"<span>{fmt_money(bear)}</span><span>{fmt_money(base)}</span><span>{fmt_money(bull)}</span>"
        "</div></div>",
        unsafe_allow_html=True,
    )
    st.caption("Fair value is shown as a range, never a single precise number — bear/base/bull, with the current price plotted on the same scale.")

    band_c = band_color(valuation.valuation_band)
    cols = st.columns(3)
    cols[0].metric("CURRENT PRICE", fmt_money(price))
    cols[1].metric("MARGIN OF SAFETY", fmt_pct(valuation.margin_of_safety))
    cols[2].markdown(
        f"<div style='padding-top:1.6rem'><span class='status-chip' style='color:{band_c};border-color:{band_c}'>"
        f"{html.escape(valuation.valuation_band.upper())}</span></div>",
        unsafe_allow_html=True,
    )

    with st.expander("Valuation methods & assumptions", expanded=False):
        for method in valuation.methods:
            st.markdown(f"**{html.escape(method.label)}**")
            table = pd.DataFrame([{"Bear": method.bear, "Base": method.base, "Bull": method.bull}]).round(2)
            st.dataframe(table, width="stretch", hide_index=True)
            for assumption in method.assumptions:
                st.caption(f"• {assumption}")


_INCOME_ROWS = ("Revenue", "Gross Profit", "Operating Income", "EBITDA", "Net Income")
_BALANCE_ROWS = ("Total Assets", "Total Liabilities", "Total Equity", "Cash & Equivalents", "Total Debt", "Net Debt")
_CASHFLOW_ROWS = ("Operating Cash Flow", "Capital Expenditure", "Free Cash Flow")


def _statement_frame(series: StatementSeries, group: str) -> pd.DataFrame:
    if group == "income":
        rows = {
            "Revenue": series.revenue,
            "Gross Profit": series.gross_profit,
            "Operating Income": series.operating_income,
            "EBITDA": series.ebitda,
            "Net Income": series.net_income,
        }
    elif group == "balance":
        rows = {
            "Total Assets": series.total_assets,
            "Total Liabilities": series.total_liabilities,
            "Total Equity": series.total_equity,
            "Cash & Equivalents": series.cash_and_equivalents,
            "Total Debt": series.total_debt,
            "Net Debt": series.net_debt,
        }
    else:
        rows = {
            "Operating Cash Flow": series.operating_cash_flow,
            "Capital Expenditure": series.capital_expenditure,
            "Free Cash Flow": series.free_cash_flow,
        }

    if all(row.dropna().empty for row in rows.values()):
        return pd.DataFrame()

    frame = pd.DataFrame(rows).T
    frame = frame[sorted(frame.columns, reverse=True)]
    frame.columns = [pd.Timestamp(col).strftime("%Y-%m-%d") for col in frame.columns]
    formatter = lambda v: f"{v:,.0f}" if pd.notna(v) else "—"
    return frame.apply(lambda col: col.map(formatter))


def _latest_and_change(series: pd.Series) -> tuple[float | None, float | None]:
    clean = series.dropna()
    if clean.empty:
        return None, None
    latest = float(clean.iloc[-1])
    if len(clean) < 2:
        return latest, None
    previous = float(clean.iloc[-2])
    change = (latest - previous) / abs(previous) if previous != 0 else None
    return latest, change


def render_financial_statements_panel(fundamental: FundamentalAnalysis) -> None:
    st.markdown("<div class='terminal-subheader'>FINANCIAL STATEMENTS</div>", unsafe_allow_html=True)

    if not fundamental.sufficient or fundamental.metrics is None:
        st.info(fundamental.insufficiency_reason or INSUFFICIENT_DATA_MESSAGE)
        return

    metrics = fundamental.metrics
    annual = metrics.annual

    st.caption("Grouped and normalized from the underlying statements — noisy raw accounting line items are hidden by default.")

    revenue, revenue_chg = _latest_and_change(annual.revenue)
    net_income, net_income_chg = _latest_and_change(annual.net_income)
    eps, eps_chg = _latest_and_change(annual.eps_diluted)
    fcf, fcf_chg = _latest_and_change(annual.free_cash_flow)
    net_debt, net_debt_chg = _latest_and_change(annual.net_debt)
    current_ratio, current_ratio_chg = _latest_and_change(annual.current_ratio)

    kpi_cols = st.columns(6)
    kpi_cols[0].metric("REVENUE", fmt_money(revenue), fmt_pct(revenue_chg) if revenue_chg is not None else None)
    kpi_cols[1].metric("NET INCOME", fmt_money(net_income), fmt_pct(net_income_chg) if net_income_chg is not None else None)
    kpi_cols[2].metric("DILUTED EPS", f"{eps:,.2f}" if eps is not None else "N/A", fmt_pct(eps_chg) if eps_chg is not None else None)
    kpi_cols[3].metric("FREE CASH FLOW", fmt_money(fcf), fmt_pct(fcf_chg) if fcf_chg is not None else None)
    kpi_cols[4].metric("NET DEBT", fmt_money(net_debt), fmt_pct(net_debt_chg) if net_debt_chg is not None else None, delta_color="inverse")
    kpi_cols[5].metric("CURRENT RATIO", f"{current_ratio:.2f}" if current_ratio is not None else "N/A", fmt_pct(current_ratio_chg) if current_ratio_chg is not None else None)

    cadence = st.radio("PERIOD", ["ANNUAL", "QUARTERLY"], horizontal=True, key="fund_stmt_cadence")
    series = metrics.annual if cadence == "ANNUAL" else metrics.quarterly

    tabs = st.tabs(["INCOME STATEMENT", "BALANCE SHEET", "CASH FLOW"])
    for tab, group in zip(tabs, ("income", "balance", "cashflow")):
        with tab:
            frame = _statement_frame(series, group)
            if frame.empty:
                st.info(f"Yahoo Finance did not publish enough {cadence.lower()} data for this group.")
            else:
                st.dataframe(frame, width="stretch")

    raw = fundamental.raw
    if raw is not None:
        with st.expander("View raw statements as reported by Yahoo Finance", expanded=False):
            pairs = (
                ("INCOME STATEMENT", raw.income_stmt, raw.quarterly_income_stmt),
                ("BALANCE SHEET", raw.balance_sheet, raw.quarterly_balance_sheet),
                ("CASH FLOW", raw.cashflow, raw.quarterly_cashflow),
            )
            raw_tabs = st.tabs([label for label, _, _ in pairs])
            for raw_tab, (label, annual_frame, quarterly_frame) in zip(raw_tabs, pairs):
                with raw_tab:
                    raw_cadence = st.radio("PERIOD", ["ANNUAL", "QUARTERLY"], horizontal=True, key=f"fund_raw_stmt_{label}")
                    raw_frame = annual_frame if raw_cadence == "ANNUAL" else quarterly_frame
                    if raw_frame is None or raw_frame.empty:
                        st.info(f"Yahoo Finance did not publish {raw_cadence.lower()} {label.lower()} data for this ticker.")
                        continue
                    display = raw_frame.copy()
                    display.columns = [
                        pd.Timestamp(col).strftime("%Y-%m-%d") if not isinstance(col, str) else col
                        for col in display.columns
                    ]
                    st.dataframe(display, width="stretch")


def render_key_metrics_panel(fundamental: FundamentalAnalysis) -> None:
    st.markdown("<div class='terminal-subheader'>KEY FINANCIAL METRICS</div>", unsafe_allow_html=True)

    if not fundamental.sufficient or fundamental.metrics is None:
        st.info(fundamental.insufficiency_reason or INSUFFICIENT_DATA_MESSAGE)
        return

    metrics = fundamental.metrics
    annual = metrics.annual

    def _latest(series: pd.Series) -> float | None:
        clean = series.dropna()
        return float(clean.iloc[-1]) if not clean.empty else None

    def _tile(label: str, value: str) -> str:
        return (
            "<div class='opp-card-metric'>"
            f"<span class='opp-card-metric-label'>{html.escape(label)}</span>"
            f"<span class='opp-card-metric-value'>{html.escape(value)}</span></div>"
        )

    def _tile_row(items: list[tuple[str, str]]) -> None:
        st.markdown(f"<div class='opp-card-metrics'>{''.join(_tile(l, v) for l, v in items)}</div>", unsafe_allow_html=True)

    groups: dict[str, list[tuple[str, str]]] = {
        "GROWTH": [
            ("Revenue Growth", fmt_pct(_latest(annual.revenue_growth))),
            ("EPS Growth", fmt_pct(_latest(annual.eps_growth))),
        ],
        "PROFITABILITY": [
            ("Gross Margin", fmt_pct(_latest(annual.gross_margin))),
            ("Operating Margin", fmt_pct(_latest(annual.operating_margin))),
            ("Net Margin", fmt_pct(_latest(annual.net_margin))),
            ("ROE", fmt_pct(_latest(annual.roe))),
        ],
        "FINANCIAL STRENGTH": [
            ("Cash", fmt_money(_latest(annual.cash_and_equivalents))),
            ("Debt", fmt_money(_latest(annual.total_debt))),
            ("Net Debt", fmt_money(_latest(annual.net_debt))),
            ("Current Ratio", f"{_latest(annual.current_ratio):.2f}" if _latest(annual.current_ratio) is not None else "N/A"),
            ("Interest Coverage", f"{_latest(annual.interest_coverage):.1f}x" if _latest(annual.interest_coverage) is not None else "N/A"),
        ],
        "VALUATION": [
            ("Trailing P/E", f"{metrics.trailing_pe:.1f}" if metrics.trailing_pe else "N/A"),
            ("Forward P/E", f"{metrics.forward_pe:.1f}" if metrics.forward_pe else "N/A"),
            ("PEG", f"{metrics.peg_ratio:.2f}" if metrics.peg_ratio else "N/A"),
            ("EV / EBITDA", f"{metrics.ev_to_ebitda:.1f}" if metrics.ev_to_ebitda else "N/A"),
            ("Price / Sales", f"{metrics.price_to_sales:.2f}" if metrics.price_to_sales else "N/A"),
            ("Dividend Yield", fmt_pct(metrics.dividend_yield)),
        ],
    }

    tabs = st.tabs(list(groups))
    for tab, name in zip(tabs, groups):
        with tab:
            _tile_row(groups[name])


def render_fundamental_provenance_panel() -> None:
    st.markdown("<b>Fundamental Analysis</b>", unsafe_allow_html=True)
    rows = [
        {"COMPONENT": item.component, "STATUS": item.status, "SOURCE": item.source, "NOTE": item.note}
        for item in methodology_coverage()
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
