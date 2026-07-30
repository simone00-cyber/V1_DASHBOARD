from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.theme import BG, PANEL, PANEL_2, ORANGE, GREEN, RED, TEXT, MUTED, GRID, BORDER_SOFT
from shipping.providers.hormuz_strait_monitor import (
    API_URL,
    SOURCE_NAME,
    SOURCE_SITE,
    HormuzMonitorError,
    HormuzMonitorSnapshot,
    fetch_dashboard,
    validate_payload,
)


@st.cache_data(ttl=600, show_spinner=False)
def _live_snapshot() -> HormuzMonitorSnapshot:
    return fetch_dashboard()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any) -> str:
    try:
        return f"{int(round(float(value))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "N/D"


def _money_b(value: Any) -> str:
    return f"${_num(value):.2f}B"


def _compact(value: Any) -> str:
    number = _num(value)
    if abs(number) >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f}B"
    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if abs(number) >= 1_000:
        return f"{number / 1_000:.1f}K"
    return f"{number:.0f}"


def _date(value: Any, date_only: bool = False) -> str:
    if not value:
        return "N/D"
    try:
        dt = pd.to_datetime(value, utc=True)
        return dt.strftime("%d %b %Y") if date_only else dt.strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return str(value)


def _records(value: Any) -> list[dict[str, Any]]:
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def _status_color(value: str) -> str:
    normalized = (value or "").upper()
    if normalized in {"OPEN", "NORMAL", "LOW", "DE-ESCALATION"}:
        return GREEN
    if normalized in {"RESTRICTED", "PARTIAL", "HIGH", "ELEVATED", "TALKS_PROPOSED", "DIPLOMATIC"}:
        return ORANGE
    return RED


def _inject_styles() -> None:
    st.markdown(
        f"""
        <style>
        .hmi-kicker{{font-size:.72rem;color:{MUTED};letter-spacing:.16em;font-weight:800;margin-bottom:4px}}
        .hmi-title{{font-size:1.65rem;font-weight:900;letter-spacing:.035em;color:{TEXT};line-height:1.15}}
        .hmi-sub{{font-size:.86rem;color:{MUTED};margin-top:5px}}
        .hmi-card{{background:linear-gradient(180deg,{PANEL_2} 0%,{PANEL} 100%);border:1px solid {BORDER_SOFT};border-radius:8px;padding:15px 17px;height:100%}}
        .hmi-card-accent{{border-top:2px solid {ORANGE}}}
        .hmi-label{{font-size:.68rem;color:{MUTED};letter-spacing:.12em;font-weight:800;text-transform:uppercase}}
        .hmi-value{{font-size:1.62rem;color:{TEXT};font-weight:900;line-height:1.15;margin-top:6px}}
        .hmi-detail{{font-size:.78rem;color:{MUTED};margin-top:5px;line-height:1.35}}
        .hmi-section{{font-size:.78rem;color:{ORANGE};letter-spacing:.14em;font-weight:900;border-bottom:1px solid {BORDER_SOFT};padding-bottom:7px;margin:22px 0 12px}}
        .hmi-badge{{display:inline-block;padding:3px 7px;border:1px solid currentColor;border-radius:6px;font-size:.66rem;font-weight:900;letter-spacing:.09em}}
        .hmi-news{{border-left:2px solid {GRID};padding:8px 12px;margin-bottom:9px;background:{PANEL}}}
        .hmi-news a{{color:{TEXT};text-decoration:none;font-weight:800}}
        .hmi-news a:hover{{color:{ORANGE}}}
        .hmi-news-meta{{font-size:.69rem;color:{MUTED};margin-top:4px}}
        .hmi-source{{font-size:.72rem;color:{MUTED};border-top:1px solid {BORDER_SOFT};padding-top:10px;margin-top:18px}}
        div[data-testid="stMetric"]{{background:{PANEL};border:1px solid {BORDER_SOFT};padding:10px 12px}}
        div[data-testid="stMetricLabel"]{{letter-spacing:.08em;text-transform:uppercase}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _card(label: str, value: str, detail: str = "", accent: bool = False, color: str | None = None) -> None:
    cls = "hmi-card hmi-card-accent" if accent else "hmi-card"
    value_style = f"color:{color};" if color else ""
    st.markdown(
        f"<div class='{cls}'><div class='hmi-label'>{html.escape(label)}</div>"
        f"<div class='hmi-value' style='{value_style}'>{html.escape(value)}</div>"
        f"<div class='hmi-detail'>{html.escape(detail)}</div></div>",
        unsafe_allow_html=True,
    )


def _line_chart(values: list[Any], title: str, suffix: str = "", baseline: float | None = None) -> go.Figure:
    series = [_num(x) for x in values]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(1, len(series) + 1)), y=series, mode="lines+markers",
        line={"width": 2, "color": ORANGE}, marker={"size": 5, "color": ORANGE},
        hovertemplate=f"%{{y:,.2f}}{suffix}<extra></extra>",
    ))
    if baseline is not None:
        fig.add_hline(y=baseline, line_dash="dot", line_color="#66717e", annotation_text="Baseline")
    fig.update_layout(
        title={"text": title, "font": {"size": 13}}, template="plotly_dark", height=285,
        margin={"l": 15, "r": 15, "t": 45, "b": 15}, paper_bgcolor=PANEL, plot_bgcolor=PANEL,
        xaxis={"showgrid": False, "title": ""}, yaxis={"gridcolor": GRID, "ticksuffix": suffix},
        showlegend=False,
    )
    return fig


def _gauge(value: float, title: str) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value, number={"suffix": "%", "font": {"size": 36}},
        title={"text": title, "font": {"size": 12}},
        gauge={
            "axis": {"range": [0, 100]}, "bar": {"color": ORANGE},
            "steps": [
                {"range": [0, 25], "color": "#3a1515"},
                {"range": [25, 60], "color": "#3a2d10"},
                {"range": [60, 100], "color": "#15331f"},
            ],
        },
    ))
    fig.update_layout(template="plotly_dark", height=285, margin={"l": 25, "r": 25, "t": 45, "b": 10}, paper_bgcolor=PANEL)
    return fig


def _load_upload(file: Any) -> HormuzMonitorSnapshot:
    payload = json.load(file)
    data, source_ts = validate_payload(payload)
    return HormuzMonitorSnapshot(data=data, fetched_at_utc=datetime.now(timezone.utc).isoformat(), source_timestamp=source_ts, source_url="uploaded JSON")


def _overview(data: dict[str, Any]) -> None:
    status = data.get("straitStatus", {})
    ships = data.get("shipCount", {})
    throughput = data.get("throughput", {})
    stranded = data.get("strandedVessels", {})
    insurance = data.get("insurance", {})
    tanker = data.get("tankerRates", {})
    oil = data.get("oilPrice", {})

    color = _status_color(str(status.get("status", "")))
    left, right = st.columns([1.4, 1])
    with left:
        st.markdown(
            f"<div class='hmi-card' style='border-left:6px solid {color};padding:20px'>"
            f"<div class='hmi-label'>STRAIT STATUS</div>"
            f"<div class='hmi-value' style='font-size:2.4rem;color:{color}'>{html.escape(str(status.get('status','N/D')))}</div>"
            f"<div class='hmi-detail'>Since {_date(status.get('since'), True)}</div>"
            f"<div style='color:#d6dbe0;font-size:.88rem;line-height:1.55;margin-top:12px'>{html.escape(str(status.get('description','')))}</div></div>",
            unsafe_allow_html=True,
        )
    with right:
        st.plotly_chart(_gauge(_num(ships.get("percentOfNormal")), "TRANSITS VS NORMAL"), width="stretch", key="hmi_gauge")

    cols = st.columns(6)
    with cols[0]: _card("24H TRANSITS", _int(ships.get("last24h")), f"Normal {_int(ships.get('normalDaily'))}/day", True)
    with cols[1]: _card("DWT THROUGHPUT", _compact(throughput.get("todayDWT")), f"{_num(throughput.get('percentOfNormal')):.1f}% of normal")
    with cols[2]: _card("VESSELS WAITING", _int(stranded.get("total")), f"{_int(stranded.get('changeToday'))} today")
    with cols[3]: _card("WAR RISK", str(insurance.get("level", "N/D")), f"{_num(insurance.get('warRiskPercent')):.2f}% premium", color=_status_color(str(insurance.get("level", ""))))
    with cols[4]: _card("VLCC TD3C", f"{_int(tanker.get('currentRate'))} {tanker.get('unit','WS')}", f"{_num(tanker.get('changePercent')):+.0f}% vs pre-crisis")
    with cols[5]: _card("BRENT", f"${_num(oil.get('brentPrice')):.2f}", f"{_num(oil.get('changePercent24h')):+.2f}% / 24h")

    st.markdown("<div class='hmi-section'>MARKET PULSE</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, .8])
    with c1:
        st.plotly_chart(_line_chart(_records([]) or throughput.get("last7Days", []), "DAILY THROUGHPUT — LAST 7 OBSERVATIONS", " DWT", _num(throughput.get("averageDWT"))), width="stretch", key="hmi_dwt")
    with c2:
        st.plotly_chart(_line_chart(oil.get("sparkline", []), "BRENT — RECENT OBSERVATIONS", ""), width="stretch", key="hmi_brent")
    with c3:
        st.plotly_chart(_line_chart(tanker.get("trend", []), f"{tanker.get('vesselType','VLCC')} {tanker.get('route','')} — SPOT RATE", f" {tanker.get('unit','WS')}"), width="stretch", key="hmi_vlcc")

    st.markdown("<div class='hmi-section'>VESSEL QUEUE COMPOSITION</div>", unsafe_allow_html=True)
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("TANKERS", _int(stranded.get("tankers")))
    q2.metric("BULK CARRIERS", _int(stranded.get("bulk")))
    q3.metric("OTHER VESSELS", _int(stranded.get("other")))
    q4.metric("TOTAL WAITING", _int(stranded.get("total")), delta=f"+{_int(stranded.get('changeToday'))} today")


def _risk_and_diplomacy(data: dict[str, Any]) -> None:
    insurance = data.get("insurance", {})
    diplomacy = data.get("diplomacy", {})
    status = str(diplomacy.get("status", "N/D"))

    st.markdown("<div class='hmi-section'>INSURANCE & TRANSIT RISK</div>", unsafe_allow_html=True)
    cols = st.columns(4)
    cols[0].metric("RISK LEVEL", insurance.get("level", "N/D"))
    cols[1].metric("WAR-RISK PREMIUM", f"{_num(insurance.get('warRiskPercent')):.2f}%")
    cols[2].metric("NORMAL PREMIUM", f"{_num(insurance.get('normalPercent')):.2f}%")
    cols[3].metric("PREMIUM MULTIPLE", f"{_num(insurance.get('multiplier')):.1f}x")

    st.markdown("<div class='hmi-section'>DIPLOMACY MONITOR</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='hmi-card' style='border-left:5px solid {_status_color(status)}'>"
        f"<span class='hmi-badge' style='color:{_status_color(status)}'>{html.escape(status.replace('_',' '))}</span>"
        f"<div style='font-size:1.15rem;font-weight:900;color:#f4f6f8;margin-top:10px'>{html.escape(str(diplomacy.get('headline','N/D')))}</div>"
        f"<div class='hmi-detail'>{_date(diplomacy.get('date'), True)}</div>"
        f"<div style='color:#ccd2d8;line-height:1.55;margin-top:12px'>{html.escape(str(diplomacy.get('summary','')))}</div></div>",
        unsafe_allow_html=True,
    )
    parties = diplomacy.get("parties", [])
    if isinstance(parties, list) and parties:
        st.caption("PARTIES: " + "  •  ".join(str(x) for x in parties))


def _trade_impact(data: dict[str, Any]) -> None:
    impact = data.get("globalTradeImpact", {})
    lng = impact.get("lngImpact", {})
    supply = impact.get("supplyChainImpact", {})

    cols = st.columns(5)
    cols[0].metric("WORLD OIL AT RISK", f"{_num(impact.get('percentOfWorldOilAtRisk')):.0f}%")
    cols[1].metric("DAILY COST", _money_b(impact.get("estimatedDailyCostBillions")))
    cols[2].metric("WORLD LNG AT RISK", f"{_num(lng.get('percentOfWorldLngAtRisk')):.0f}%")
    cols[3].metric("SHIPPING RATES", f"+{_num(supply.get('shippingRateIncreasePercent')):.0f}%")
    cols[4].metric("CPI IMPACT", f"+{_num(supply.get('consumerPriceImpactPercent')):.1f}%")

    st.markdown("<div class='hmi-section'>REGIONAL EXPOSURE</div>", unsafe_allow_html=True)
    regions = pd.DataFrame(_records(impact.get("affectedRegions")))
    if not regions.empty:
        regions["oilDependencyPercent"] = pd.to_numeric(regions.get("oilDependencyPercent"), errors="coerce")
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=regions["oilDependencyPercent"], y=regions["name"], orientation="h",
            text=regions["oilDependencyPercent"].map(lambda x: f"{x:.0f}%"), textposition="outside",
            marker_color=ORANGE, customdata=regions[["severity", "description"]].to_numpy(),
            hovertemplate="<b>%{y}</b><br>Dependency: %{x:.0f}%<br>Severity: %{customdata[0]}<br>%{customdata[1]}<extra></extra>",
        ))
        fig.update_layout(template="plotly_dark", height=390, margin={"l": 15, "r": 30, "t": 10, "b": 20}, paper_bgcolor=PANEL, plot_bgcolor=PANEL, xaxis={"range": [0, 100], "ticksuffix": "%", "gridcolor": GRID}, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width="stretch", key="hmi_regions")
        display = regions.rename(columns={"name":"REGION","severity":"SEVERITY","oilDependencyPercent":"OIL DEPENDENCY %","description":"INTELLIGENCE NOTE"})
        st.dataframe(display, width="stretch", hide_index=True)

    st.markdown("<div class='hmi-section'>LNG & SUPPLY CHAIN</div>", unsafe_allow_html=True)
    left, right = st.columns([1, 1])
    with left:
        _card("LNG DAILY COST", _money_b(lng.get("estimatedLngDailyCostBillions")), str(lng.get("description", "")), True)
        top = lng.get("topAffectedImporters", [])
        if isinstance(top, list): st.caption("TOP IMPORTERS AT RISK: " + "  •  ".join(map(str, top)))
    with right:
        _card("STRATEGIC RESERVE BUFFER", f"{_int(supply.get('sprStatusDays'))} DAYS", "Estimated SPR buffer at stated release assumptions", True)
    disruptions = supply.get("keyDisruptions", [])
    if isinstance(disruptions, list):
        for item in disruptions:
            st.markdown(f"• {html.escape(str(item))}")


def _routes(data: dict[str, Any]) -> None:
    impact = data.get("globalTradeImpact", {})
    routes = pd.DataFrame(_records(impact.get("alternativeRoutes")))
    if routes.empty:
        st.info("Alternative-route data non disponibile.")
        return
    routes["additionalDays"] = pd.to_numeric(routes.get("additionalDays"), errors="coerce")
    routes["additionalCostPerVessel"] = pd.to_numeric(routes.get("additionalCostPerVessel"), errors="coerce")

    st.caption("Cost values are reported by the source in USD thousands per vessel.")
    for _, row in routes.iterrows():
        left, mid, right = st.columns([1.1, .35, 2.55])
        with left:
            st.markdown(f"**{row.get('name','N/D')}**")
        with mid:
            days = _num(row.get("additionalDays"))
            cost = _num(row.get("additionalCostPerVessel"))
            st.markdown(f"`+{days:.0f}d`  `${cost:,.0f}k`")
        with right:
            st.write(row.get("currentUsageStatus", ""))
        st.divider()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=routes["name"], y=routes["additionalCostPerVessel"], marker_color=ORANGE,
        text=routes["additionalCostPerVessel"].map(lambda x: f"${x:,.0f}k"), textposition="outside",
        customdata=routes[["additionalDays", "currentUsageStatus"]].to_numpy(),
        hovertemplate="<b>%{x}</b><br>Cost: $%{y:,.0f}k<br>Extra days: %{customdata[0]:.0f}<br>%{customdata[1]}<extra></extra>",
    ))
    fig.update_layout(template="plotly_dark", height=390, margin={"l": 15, "r": 15, "t": 20, "b": 80}, paper_bgcolor=PANEL, plot_bgcolor=PANEL, yaxis_title="Additional cost (USD thousands)", yaxis={"gridcolor":GRID})
    st.plotly_chart(fig, width="stretch", key="hmi_routes")


def _timeline(data: dict[str, Any]) -> None:
    timeline = data.get("crisisTimeline", {})
    events = pd.DataFrame(_records(timeline.get("events")))
    if events.empty:
        st.info("Timeline non disponibile.")
        return
    events["date"] = pd.to_datetime(events["date"], errors="coerce")
    types = sorted(events["type"].dropna().astype(str).unique())
    selected = st.multiselect("EVENT TYPE", types, default=types)
    if selected:
        events = events[events["type"].isin(selected)]
    events = events.sort_values("date", ascending=False)
    for _, row in events.iterrows():
        color = _status_color(str(row.get("type", "")))
        st.markdown(
            f"<div class='hmi-card' style='border-left:4px solid {color};margin-bottom:9px'>"
            f"<span class='hmi-badge' style='color:{color}'>{html.escape(str(row.get('type','')))}</span>"
            f"<span style='float:right;color:#8b949e;font-size:.76rem'>{_date(row.get('date'), True)}</span>"
            f"<div style='font-size:1rem;font-weight:900;margin-top:9px;color:#f4f6f8'>{html.escape(str(row.get('title','')))}</div>"
            f"<div class='hmi-detail'>{html.escape(str(row.get('description','')))}</div></div>", unsafe_allow_html=True,
        )


def _news(data: dict[str, Any]) -> None:
    news = _records(data.get("news"))
    if not news:
        st.info("News feed non disponibile.")
        return
    st.caption("External headlines supplied by the source endpoint. Open the original publisher for verification.")
    for item in news:
        url = html.escape(str(item.get("url", "#")), quote=True)
        title = html.escape(str(item.get("title", "Untitled")))
        source = html.escape(str(item.get("source", "Unknown")))
        description = html.escape(str(item.get("description", "")))
        published = _date(item.get("publishedAt"))
        st.markdown(
            f"<div class='hmi-news'><a href='{url}' target='_blank'>{title}</a>"
            f"<div class='hmi-news-meta'>{source}  •  {published}</div>"
            f"<div class='hmi-detail'>{description}</div></div>", unsafe_allow_html=True,
        )


def render_shipping() -> None:
    _inject_styles()
    st.markdown("<div class='hmi-kicker'>CYCLICAL GLOBAL MACRO TERMINAL / GEOPOLITICAL RISK</div>", unsafe_allow_html=True)
    st.markdown("<div class='hmi-title'>HORMUZ MARITIME INTELLIGENCE</div>", unsafe_allow_html=True)
    st.markdown("<div class='hmi-sub'>Shipping throughput, energy pricing, war-risk insurance, global trade exposure and event monitoring.</div>", unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("<div class='terminal-subheader'>HORMUZ FEED</div>", unsafe_allow_html=True)
        uploaded = st.file_uploader("Optional API snapshot", type=["json"], help="Upload a saved /api/dashboard response for offline use.")
        if st.button("REFRESH LIVE FEED", width="stretch"):
            _live_snapshot.clear()
            st.rerun()

    try:
        snapshot = _load_upload(uploaded) if uploaded is not None else _live_snapshot()
    except (HormuzMonitorError, ValueError, json.JSONDecodeError) as exc:
        st.error(str(exc))
        st.info("The live provider is unavailable. Upload a previously saved /api/dashboard JSON response to continue in offline mode.")
        return

    data = snapshot.data
    source_ts = snapshot.source_timestamp or data.get("lastUpdated")
    now = pd.Timestamp.now(tz="UTC")
    age_text = "N/D"
    stale = False
    if source_ts:
        try:
            age = now - pd.to_datetime(source_ts, utc=True)
            age_hours = max(age.total_seconds() / 3600, 0)
            age_text = f"{age_hours:.1f}h"
            stale = age_hours > 6
        except Exception:
            pass

    top = st.columns([1, 1, 1, 1.4])
    top[0].metric("FEED", "LIVE API" if uploaded is None else "OFFLINE SNAPSHOT")
    top[1].metric("SOURCE", SOURCE_NAME)
    top[2].metric("DATA AGE", age_text, delta="STALE" if stale else "CURRENT", delta_color="inverse" if stale else "normal")
    top[3].metric("LAST SOURCE UPDATE", _date(source_ts))

    tabs = st.tabs(["OVERVIEW", "RISK & DIPLOMACY", "GLOBAL TRADE", "ALTERNATIVE ROUTES", "CRISIS TIMELINE", "NEWS", "DATA AUDIT"])
    with tabs[0]: _overview(data)
    with tabs[1]: _risk_and_diplomacy(data)
    with tabs[2]: _trade_impact(data)
    with tabs[3]: _routes(data)
    with tabs[4]: _timeline(data)
    with tabs[5]: _news(data)
    with tabs[6]:
        st.markdown("<div class='hmi-section'>PROVENANCE & RAW PAYLOAD</div>", unsafe_allow_html=True)
        audit = {
            "provider": SOURCE_NAME,
            "api_url": API_URL,
            "source_site": SOURCE_SITE,
            "source_timestamp": source_ts,
            "terminal_fetch_timestamp": snapshot.fetched_at_utc,
            "mode": "uploaded" if uploaded is not None else "live",
            "top_level_fields": sorted(data.keys()),
        }
        st.json(audit, expanded=True)
        st.download_button("DOWNLOAD CURRENT SNAPSHOT", data=json.dumps({"success": True, "data": data, "timestamp": source_ts}, indent=2, ensure_ascii=False), file_name="hormuz_dashboard_snapshot.json", mime="application/json")
        st.json(data, expanded=False)

    st.markdown(
        f"<div class='hmi-source'>Source: <a href='{SOURCE_SITE}' target='_blank'>{SOURCE_NAME}</a> · API: {API_URL} · "
        "Public-source estimates for situational awareness only. Not for navigation, safety-of-life decisions, or as a sole basis for trading.</div>",
        unsafe_allow_html=True,
    )
