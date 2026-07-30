from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from ui.plotly import render_plotly

from screener.engine import download_universe_ohlc
from screener.universes import UNIVERSES, load_universe
from technical.engine import (
    TechnicalSettings,
    add_moving_averages,
    analyse_technical,
    calculate_rsi,
    parse_ma_periods,
    resample_technical_frame,
    scan_universe,
)


@st.cache_data(ttl=86400, show_spinner=False)
def _technical_constituents(name: str) -> tuple[pd.DataFrame, str]:
    return load_universe(name)


@st.cache_data(ttl=3600, show_spinner=False)
def _technical_prices(name: str) -> tuple[dict[str, pd.DataFrame], str, pd.DataFrame]:
    constituents, source = _technical_constituents(name)
    data = download_universe_ohlc(constituents["Ticker"].tolist(), period="max", chunk_size=20)
    return data, source, constituents


@st.cache_data(ttl=3600, show_spinner=False)
def _custom_prices(tickers: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    if not tickers:
        return {}
    return download_universe_ohlc(list(tickers), period="max", chunk_size=10)


def _parse_custom_tickers(value: str) -> tuple[str, ...]:
    cleaned: list[str] = []
    for item in value.replace(";", ",").replace("\n", ",").split(","):
        ticker = item.strip().upper()
        if ticker and ticker not in cleaned:
            cleaned.append(ticker)
    return tuple(cleaned[:30])


def _merge_custom_securities(
    data: dict[str, pd.DataFrame],
    constituents: pd.DataFrame,
    custom_tickers: tuple[str, ...],
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    if not custom_tickers:
        return data, constituents
    custom_data = _custom_prices(custom_tickers)
    merged_data = dict(data)
    merged_data.update(custom_data)
    existing = set(constituents["Ticker"].astype(str))
    records = [
        {"Company": ticker, "Ticker": ticker, "Sector": "Custom"}
        for ticker in custom_tickers
        if ticker not in existing
    ]
    if records:
        constituents = pd.concat([constituents, pd.DataFrame(records)], ignore_index=True)
    return merged_data, constituents


def _settings_panel() -> TechnicalSettings:
    st.markdown("<div class='terminal-subheader'>TECHNICAL PARAMETERS</div>", unsafe_allow_html=True)
    timeframe = st.segmented_control("CANDLE TIMEFRAME", ["DAILY", "WEEKLY", "MONTHLY"], default="DAILY", width="stretch")
    ma_text = st.text_input("MOVING AVERAGES", value="20, 50, 200", help="Periods are measured in the selected candle timeframe; maximum 8 moving averages.")
    ma_periods = parse_ma_periods(ma_text)
    c1, c2 = st.columns(2)
    swing_window = c1.number_input("SWING WINDOW", min_value=2, max_value=20, value=5, step=1)
    lookback = c2.selectbox("LEVEL LOOKBACK", [60, 126, 252, 504], index=2, format_func=lambda x: f"{x} bars")
    c3, c4 = st.columns(2)
    proximity = c3.number_input("PROXIMITY %", min_value=0.2, max_value=10.0, value=2.0, step=0.1)
    zone_tolerance = c4.number_input("ZONE WIDTH %", min_value=0.2, max_value=5.0, value=1.0, step=0.1)
    c5, c6 = st.columns(2)
    rsi_period = c5.number_input("RSI PERIOD", min_value=2, max_value=100, value=14, step=1)
    pattern_tolerance = c6.number_input("PATTERN TOLERANCE %", min_value=1.0, max_value=10.0, value=3.0, step=0.5)
    c7, c8 = st.columns(2)
    breakout_buffer = c7.number_input("BREAKOUT BUFFER %", min_value=0.0, max_value=5.0, value=0.3, step=0.1)
    confirmations = c8.selectbox("BREAKOUT CLOSES", [1, 2, 3], index=0)
    return TechnicalSettings(
        swing_window=int(swing_window),
        lookback=int(lookback),
        zone_tolerance_pct=float(zone_tolerance),
        proximity_pct=float(proximity),
        breakout_buffer_pct=float(breakout_buffer),
        breakout_confirmations=int(confirmations),
        rsi_period=int(rsi_period),
        ma_periods=ma_periods,
        pattern_tolerance_pct=float(pattern_tolerance),
        timeframe=str(timeframe or "DAILY"),
    )


def _chart_display_frame(frame: pd.DataFrame, settings: TechnicalSettings) -> pd.DataFrame:
    """Return the full resampled history with configured moving averages.

    The initial viewport is handled by Plotly, but the complete history remains
    available for pan, zoom and the range slider.
    """
    return add_moving_averages(frame.copy().sort_index(), settings.ma_periods)


def _initial_visible_bars(timeframe: str) -> int:
    return {"DAILY": 252, "WEEKLY": 156, "MONTHLY": 120}.get(timeframe, 252)


def _price_rsi_chart(ticker: str, frame: pd.DataFrame, settings: TechnicalSettings, snapshot) -> go.Figure:
    """Compact synchronized price, volume and RSI workspace."""
    display = _chart_display_frame(frame, settings)
    rsi = calculate_rsi(display["Close"], settings.rsi_period).reindex(display.index)

    volume = pd.Series(0.0, index=display.index)
    if "Volume" in display.columns:
        volume = (
            pd.to_numeric(display["Volume"], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .clip(lower=0.0)
        )
    has_volume = bool(volume.gt(0).any())

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.012,
        row_heights=[0.69, 0.11, 0.20],
    )

    fig.add_trace(
        go.Candlestick(
            x=display.index,
            open=display["Open"],
            high=display["High"],
            low=display["Low"],
            close=display["Close"],
            name=ticker,
            increasing_line_color="#18d47b",
            decreasing_line_color="#ff4f5e",
            increasing_fillcolor="#18d47b",
            decreasing_fillcolor="#ff4f5e",
            whiskerwidth=0.22,
        ),
        row=1,
        col=1,
    )

    ma_colors = ["#ff5b49", "#00d6b4", "#a95cff", "#f5b642", "#3d8bfd", "#f472b6", "#94a3b8", "#22c55e"]
    for index, period in enumerate(settings.ma_periods):
        column = f"MA{period}"
        if column in display:
            fig.add_trace(
                go.Scatter(
                    x=display.index,
                    y=display[column],
                    mode="lines",
                    name=column,
                    line={"width": 1.45, "color": ma_colors[index % len(ma_colors)]},
                    hovertemplate=f"{column}: %{{y:.2f}}<extra></extra>",
                ),
                row=1,
                col=1,
            )

    supports = snapshot.diagnostics.get("supports", []) or []
    resistances = snapshot.diagnostics.get("resistances", []) or []

    def _valid_zone(zone: dict) -> bool:
        try:
            low = float(zone["low"])
            high = float(zone["high"])
            return np.isfinite(low) and np.isfinite(high) and 0 < low < high
        except (KeyError, TypeError, ValueError):
            return False

    def _add_zone(zone: dict, role: str, nearest: bool) -> None:
        if not _valid_zone(zone):
            return
        origin = pd.to_datetime(zone.get("first_date", display.index[0]), errors="coerce")
        if pd.isna(origin):
            origin = display.index[0]
        color = ("34,197,94" if role == "support" else "239,68,68")
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=max(origin, display.index[0]),
            x1=display.index[-1],
            y0=float(zone["low"]),
            y1=float(zone["high"]),
            fillcolor=f"rgba({color},{0.28 if nearest else 0.13})",
            line={"color": f"rgba({color},{0.92 if nearest else 0.42})", "width": 1.25 if nearest else 0.65},
            layer="below",
        )

    for index, zone in enumerate([z for z in supports if _valid_zone(z)][:4]):
        _add_zone(zone, "support", index == 0)
    for index, zone in enumerate([z for z in resistances if _valid_zone(z)][:4]):
        _add_zone(zone, "resistance", index == 0)

    if has_volume:
        volume_colors = np.where(
            display["Close"].to_numpy() >= display["Open"].to_numpy(),
            "rgba(24,212,123,0.82)",
            "rgba(255,79,94,0.82)",
        )
        fig.add_trace(
            go.Bar(
                x=display.index,
                y=volume,
                name="Volume",
                marker={"color": volume_colors, "line": {"width": 0}},
                opacity=0.92,
                hovertemplate="Volume: %{y:,.0f}<extra></extra>",
                showlegend=False,
            ),
            row=2,
            col=1,
        )
    else:
        fig.add_annotation(
            text="Volume unavailable",
            xref="x2 domain",
            yref="y2 domain",
            x=0.01,
            y=0.52,
            showarrow=False,
            font={"size": 10, "color": "#818a99"},
        )

    fig.add_trace(
        go.Scatter(
            x=display.index,
            y=rsi,
            mode="lines",
            name=f"RSI({settings.rsi_period})",
            line={"width": 1.45, "color": "#338dff"},
            hovertemplate=f"RSI({settings.rsi_period}): %{{y:.1f}}<extra></extra>",
            showlegend=False,
        ),
        row=3,
        col=1,
    )
    fig.add_hrect(y0=70, y1=100, fillcolor="rgba(239,68,68,0.075)", line_width=0, row=3, col=1)
    fig.add_hrect(y0=0, y1=30, fillcolor="rgba(51,141,255,0.075)", line_width=0, row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="rgba(148,163,184,0.62)", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="rgba(148,163,184,0.62)", row=3, col=1)

    visible_bars = _initial_visible_bars(settings.timeframe)
    visible = display.tail(visible_bars) if len(display) > visible_bars else display
    initial_range = [visible.index[0], visible.index[-1]]

    price_low = float(visible["Low"].min())
    price_high = float(visible["High"].max())
    zone_edges: list[float] = []
    for zone in supports[:4] + resistances[:4]:
        if _valid_zone(zone):
            low, high = float(zone["low"]), float(zone["high"])
            if low <= price_high * 1.15 and high >= price_low * 0.85:
                zone_edges.extend([low, high])
    if zone_edges:
        price_low = min(price_low, min(zone_edges))
        price_high = max(price_high, max(zone_edges))
    padding = max((price_high - price_low) * 0.055, price_high * 0.01)

    fig.update_yaxes(
        range=[max(0.01, price_low - padding), price_high + padding],
        fixedrange=False,
        zeroline=False,
        tickformat=",.2f",
        row=1,
        col=1,
    )

    if has_volume:
        visible_volume = volume.reindex(visible.index)
        positive = visible_volume[visible_volume > 0]
        # Robust scaling prevents one split/data anomaly from flattening every bar.
        upper = float(positive.quantile(0.985) * 1.18) if not positive.empty else 1.0
        upper = max(upper, float(positive.median() * 2.0) if not positive.empty else 1.0)
        fig.update_yaxes(
            range=[0, upper],
            fixedrange=False,
            showgrid=False,
            zeroline=False,
            title_text="VOL",
            tickformat="~s",
            nticks=3,
            row=2,
            col=1,
        )
    else:
        fig.update_yaxes(range=[0, 1], showticklabels=False, showgrid=False, row=2, col=1)

    fig.update_yaxes(
        range=[0, 100],
        fixedrange=False,
        zeroline=False,
        title_text=f"RSI({settings.rsi_period})",
        dtick=20,
        row=3,
        col=1,
    )

    for row in (1, 2, 3):
        fig.update_xaxes(
            range=initial_range,
            fixedrange=False,
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikecolor="rgba(148,163,184,0.42)",
            spikethickness=1,
            row=row,
            col=1,
        )
    fig.update_xaxes(matches="x", showticklabels=False, row=1, col=1)
    fig.update_xaxes(matches="x", showticklabels=False, row=2, col=1)
    fig.update_xaxes(matches="x", showticklabels=True, row=3, col=1)
    fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
    fig.update_xaxes(rangeslider_visible=False, row=2, col=1)
    fig.update_xaxes(rangeslider_visible=True, rangeslider_thickness=0.035, row=3, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=720,
        margin=dict(l=8, r=8, t=50, b=4),
        title={"text": f"{ticker} // {settings.timeframe} TECHNICAL WORKSPACE", "x": 0.0, "xanchor": "left"},
        legend={"orientation": "h", "y": 1.025, "x": 0, "font": {"size": 10}, "bgcolor": "rgba(0,0,0,0)"},
        hovermode="x unified",
        dragmode="pan",
        uirevision=f"technical-{ticker}-{settings.timeframe}",
        bargap=0.06,
        plot_bgcolor="#05070a",
        paper_bgcolor="#05070a",
        hoverlabel={"bgcolor": "#10141a", "bordercolor": "#303846", "font": {"color": "#f5f7fa"}},
    )
    return fig


def _technical_event_history(frame: pd.DataFrame, settings: TechnicalSettings, snapshot) -> list[dict[str, object]]:
    """Build a dated, deterministic event timeline from calculated technical data."""
    events: list[dict[str, object]] = []
    frame = frame.sort_index()
    last_date = frame.index[-1]

    def add(date, label: str, category: str, detail: str = "") -> None:
        parsed = pd.to_datetime(date, errors="coerce")
        if pd.isna(parsed):
            parsed = last_date
        events.append({"date": parsed, "label": label, "category": category, "detail": detail})

    for zone in (snapshot.diagnostics.get("supports", []) or []) + (snapshot.diagnostics.get("resistances", []) or []):
        role = str(zone.get("role", zone.get("initial_role", "LEVEL"))).title()
        if zone.get("break_date") is not None:
            add(zone["break_date"], f"{role} break", "LEVEL", f"Zone {float(zone['low']):.2f}-{float(zone['high']):.2f}")
        if zone.get("retest_date") is not None:
            add(zone["retest_date"], f"{role} retest / role flip", "LEVEL", f"Zone {float(zone['low']):.2f}-{float(zone['high']):.2f}")

    close = frame["Close"].astype(float)
    periods = tuple(sorted(settings.ma_periods))
    for fast, slow in zip(periods, periods[1:]):
        fast_ma = close.rolling(fast, min_periods=fast).mean()
        slow_ma = close.rolling(slow, min_periods=slow).mean()
        spread = fast_ma - slow_ma
        bullish = (spread.shift(1) <= 0) & (spread > 0)
        bearish = (spread.shift(1) >= 0) & (spread < 0)
        for date in bullish[bullish].index[-2:]:
            add(date, f"Bullish MA{fast}/MA{slow} crossover", "MOVING AVERAGE")
        for date in bearish[bearish].index[-2:]:
            add(date, f"Bearish MA{fast}/MA{slow} crossover", "MOVING AVERAGE")

    rsi = calculate_rsi(close, settings.rsi_period)
    rsi_events = {
        "RSI entered overbought area": (rsi.shift(1) < 70) & (rsi >= 70),
        "RSI exited overbought area": (rsi.shift(1) >= 70) & (rsi < 70),
        "RSI entered oversold area": (rsi.shift(1) > 30) & (rsi <= 30),
        "RSI exited oversold area": (rsi.shift(1) <= 30) & (rsi > 30),
    }
    for label, mask in rsi_events.items():
        for date in mask[mask].index[-2:]:
            add(date, label, "RSI")

    for pattern in snapshot.diagnostics.get("pattern_details", []) or []:
        add(
            pattern.get("end", last_date),
            f"{pattern.get('name', 'Pattern')} - {pattern.get('status', 'DEVELOPING')}",
            "PATTERN",
            f"Geometric confidence {pattern.get('confidence', 0)}%",
        )

    # Current conditions remain visible but rank behind genuinely dated transitions on the same date.
    for setup in snapshot.setups:
        add(last_date, setup, "CURRENT")

    dedup: dict[tuple[pd.Timestamp, str], dict[str, object]] = {}
    for event in events:
        key = (pd.Timestamp(event["date"]), str(event["label"]))
        dedup[key] = event
    return sorted(dedup.values(), key=lambda item: pd.Timestamp(item["date"]), reverse=True)


def _render_technical_summary(frame: pd.DataFrame, settings: TechnicalSettings, snapshot) -> None:
    events = _technical_event_history(frame, settings, snapshot)
    latest = events[0] if events else None

    st.markdown("<div class='terminal-subheader'>CURRENT TECHNICAL STATE</div>", unsafe_allow_html=True)
    state_cols = st.columns(2)
    state_cols[0].metric("LEVEL STATE", snapshot.state)
    state_cols[1].metric("RSI", f"{snapshot.rsi:.1f}" if snapshot.rsi is not None else "N/D")

    support_text = (
        f"{snapshot.support_low:.2f}-{snapshot.support_high:.2f}"
        if snapshot.support_low is not None and snapshot.support_high is not None
        else "N/D"
    )
    resistance_text = (
        f"{snapshot.resistance_low:.2f}-{snapshot.resistance_high:.2f}"
        if snapshot.resistance_low is not None and snapshot.resistance_high is not None
        else "N/D"
    )
    level_cols = st.columns(2)
    level_cols[0].metric("NEAREST SUPPORT", support_text)
    level_cols[1].metric("NEAREST RESISTANCE", resistance_text)

    st.markdown("<div class='terminal-subheader'>LATEST EVENT</div>", unsafe_allow_html=True)
    if latest:
        st.markdown(f"**{latest['label']}**")
        st.caption(f"{pd.Timestamp(latest['date']).strftime('%d %b %Y')} | {latest['category']}")
        if latest.get("detail"):
            st.write(str(latest["detail"]))
    else:
        st.info("No dated technical event detected.")

    st.markdown("<div class='terminal-subheader'>TECHNICAL STORY</div>", unsafe_allow_html=True)
    ma_states: list[str] = []
    close = frame["Close"].dropna()
    for period in settings.ma_periods:
        ma = close.rolling(period, min_periods=period).mean()
        if not ma.dropna().empty:
            ma_states.append(f"above MA{period}" if close.iloc[-1] > ma.iloc[-1] else f"below MA{period}")
    story = [f"Price is {', '.join(ma_states)}." if ma_states else "Moving-average context is unavailable."]
    if snapshot.support_low is not None:
        story.append(f"Nearest support is {support_text}.")
    if snapshot.resistance_low is not None:
        story.append(f"Nearest resistance is {resistance_text}.")
    if snapshot.rsi is not None:
        rsi_state = "overbought" if snapshot.rsi >= 70 else "oversold" if snapshot.rsi <= 30 else "neutral"
        story.append(f"RSI({settings.rsi_period}) is {rsi_state} at {snapshot.rsi:.1f}.")
    st.write(" ".join(story))

    st.markdown("<div class='terminal-subheader'>RECENT EVENTS</div>", unsafe_allow_html=True)
    for event in events[:4]:
        st.markdown(f"**{pd.Timestamp(event['date']).strftime('%d %b')}** - {event['label']}")

    with st.expander("FULL TECHNICAL EVENT HISTORY"):
        if events:
            history = pd.DataFrame(events)
            history["date"] = pd.to_datetime(history["date"]).dt.strftime("%d %b %Y")
            history = history.rename(columns={"date": "DATE", "label": "EVENT", "category": "CATEGORY", "detail": "DETAIL"})
            st.dataframe(history[["DATE", "CATEGORY", "EVENT", "DETAIL"]], width="stretch", hide_index=True)
        else:
            st.caption("No events available.")

def _pattern_chart(ticker: str, frame: pd.DataFrame, settings: TechnicalSettings, detail: dict) -> go.Figure:
    # Keep the complete available chart visible through the latest bar.
    # The detected structure is highlighted in context rather than isolated.
    visible = frame.copy().sort_index()
    fig = go.Figure(go.Candlestick(
        x=visible.index, open=visible["Open"], high=visible["High"], low=visible["Low"], close=visible["Close"], name=ticker
    ))
    anchors = detail.get("anchors", [])
    if anchors:
        fig.add_trace(go.Scatter(
            x=[item[0] for item in anchors], y=[item[1] for item in anchors], mode="markers+lines",
            name="Pattern anchors", marker={"size": 9, "symbol": "diamond"}, line={"width": 2, "dash": "dot"},
        ))
    for key, label in (("upper", "Upper boundary"), ("lower", "Lower boundary")):
        points = detail.get(key, [])
        if points:
            fig.add_trace(go.Scatter(x=[p[0] for p in points], y=[p[1] for p in points], mode="lines+markers", name=label, line={"width": 2}))
    h0, h1 = detail.get("highlight_start"), detail.get("highlight_end")
    if h0 is not None and h1 is not None:
        fig.add_vrect(x0=h0, x1=h1, opacity=0.14, line_width=1, annotation_text="PATTERN ZONE")
    meta_text = (
        f"{detail.get('name', 'Potential pattern')}<br>"
        f"Confidence {detail.get('confidence', 0)}% · {detail.get('status', 'DEVELOPING')} · "
        f"{detail.get('direction', 'NEUTRAL')}"
    )
    fig.add_annotation(
        x=visible.index[-1], y=float(visible["High"].max()), text=meta_text,
        showarrow=False, xanchor="right", bgcolor="rgba(10,10,10,0.82)", bordercolor="#ff9f00", borderwidth=1,
    )
    visible_bars = _initial_visible_bars(settings.timeframe)
    if len(visible) > visible_bars:
        fig.update_xaxes(range=[visible.index[-visible_bars], visible.index[-1]])
    fig.update_layout(
        template="plotly_dark",
        height=620,
        margin=dict(l=10, r=10, t=48, b=10),
        title=f"{ticker} // {detail.get('name', 'PATTERN')} // {settings.timeframe}",
        xaxis_rangeslider_visible=True,
        legend={"orientation": "h", "y": 1.02, "x": 0},
        dragmode="pan",
        hovermode="x unified",
        uirevision=f"pattern-{ticker}-{settings.timeframe}",
    )
    return fig


def _filter_scan(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows
    st.markdown("<div class='terminal-subheader'>SETUP FILTERS</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1.4, 1.2, 1.1, 1.0])
    sector_options = ["ALL SECTORS"] + sorted(rows["Sector"].dropna().astype(str).unique())
    sector = c1.selectbox("SECTOR", sector_options)
    event_options = [
        "In support area", "Approaching support", "Support breakdown",
        "In resistance area", "Approaching resistance", "Resistance breakout",
        "Bullish MA crossover", "Bearish MA crossover", "RSI overbought", "RSI oversold",
        "Potential bullish RSI divergence", "Potential bearish RSI divergence",
        "Potential double top", "Potential double bottom", "Potential ascending triangle",
        "Potential descending triangle", "Potential symmetrical triangle / pennant",
        "Potential bullish flag", "Potential bearish flag", "Potential cup and handle",
    ]
    selected_events = c2.multiselect("BEHAVIOUR / PATTERN", event_options)
    min_setups = c3.selectbox("MIN SETUPS", [0, 1, 2, 3, 4, 5], index=0)
    search = c4.text_input("TICKER", placeholder="NVDA")

    filtered = rows.copy()
    if sector != "ALL SECTORS":
        filtered = filtered[filtered["Sector"].astype(str) == sector]
    if selected_events:
        mask = pd.Series(True, index=filtered.index)
        for event in selected_events:
            mask &= filtered["Setups"].str.contains(event, case=False, regex=False, na=False)
        filtered = filtered[mask]
    filtered = filtered[filtered["Setup Count"] >= min_setups]
    if search.strip():
        filtered = filtered[filtered["Ticker"].str.contains(search.strip(), case=False, regex=False)]
    return filtered


def _render_event_cards(rows: pd.DataFrame) -> None:
    definitions = [
        ("SUPPORT AREA", "In support area"),
        ("RESISTANCE AREA", "In resistance area"),
        ("BREAKOUTS", "Resistance breakout"),
        ("BREAKDOWNS", "Support breakdown"),
        ("RSI EXTREMES", "RSI over"),
        ("PATTERNS", "Potential"),
    ]
    cards = st.columns(len(definitions))
    for card, (label, token) in zip(cards, definitions):
        count = int(rows["Setups"].str.contains(token, case=False, regex=False, na=False).sum()) if not rows.empty else 0
        card.metric(label, count)


def _format_scan(rows: pd.DataFrame) -> pd.DataFrame:
    result = rows.copy()
    for column in [
        "Last", "Support Low", "Support High", "Distance Support %", "Resistance Low",
        "Resistance High", "Distance Resistance %", "RSI",
    ]:
        if column in result:
            result[column] = pd.to_numeric(result[column], errors="coerce").round(2)
    return result


def _render_single_security(ticker: str, settings: TechnicalSettings, *, context: str) -> None:
    ticker = ticker.strip().upper()
    prices = _custom_prices((ticker,))
    raw = prices.get(ticker)
    if raw is None or raw.empty:
        st.error(f"No usable Yahoo Finance price history found for {ticker}.")
        return

    frame = resample_technical_frame(raw, settings.timeframe)
    snapshot = analyse_technical(ticker, frame, settings)

    cards = st.columns(6)
    cards[0].metric("LAST", f"{snapshot.last:,.2f}")
    cards[1].metric("STATE", snapshot.state)
    cards[2].metric("RSI", f"{snapshot.rsi:.1f}" if snapshot.rsi is not None else "N/D")
    cards[3].metric(
        "SUPPORT DIST.",
        f"{snapshot.distance_support_pct:+.2f}%" if snapshot.distance_support_pct is not None else "N/D",
    )
    cards[4].metric(
        "RESISTANCE DIST.",
        f"{snapshot.distance_resistance_pct:+.2f}%" if snapshot.distance_resistance_pct is not None else "N/D",
    )
    cards[5].metric("ACTIVE SETUPS", len(snapshot.setups))

    chart_col, event_col = st.columns([2.7, 1])
    with chart_col:
        render_plotly(
            _price_rsi_chart(ticker, frame, settings, snapshot),
            page="technical",
            chart="price_rsi",
            ticker=ticker,
            timeframe=settings.timeframe,
            context=context,
            config={"scrollZoom": True, "displaylogo": False, "responsive": True},
        )
        st.caption(
            "Price, volume and RSI share one synchronized time axis. Drag to pan; use the range slider or mouse wheel to zoom."
        )
    with event_col:
        _render_technical_summary(frame, settings, snapshot)


def render_technical_analysis(*, ticker_override: str | None = None, embedded: bool = False) -> None:
    if not embedded:
        st.markdown(
            "<div class='terminal-header'>TECHNICAL ANALYSIS // SCREENER // PATTERN RECOGNITION</div>",
            unsafe_allow_html=True,
        )
    st.caption(
        "Search any Yahoo Finance ticker for direct technical analysis. The separate screener scans a selected "
        "index for support, resistance, breakout and other technical behaviours. No BUY or SELL signal is generated."
    )

    default_ticker = (ticker_override or "AAPL").strip().upper()
    if "technical_analysis_ticker" not in st.session_state or ticker_override:
        st.session_state.technical_analysis_ticker = default_ticker
    if "technical_pattern_ticker" not in st.session_state or ticker_override:
        st.session_state.technical_pattern_ticker = default_ticker

    settings_container = st.expander("TECHNICAL PARAMETERS", expanded=False) if embedded else st.sidebar
    with settings_container:
        settings = _settings_panel()
        if st.button("REFRESH TECHNICAL DATA", width="stretch", key=f"refresh_technical_{'embedded' if embedded else 'page'}"):
            _technical_prices.clear()
            _custom_prices.clear()
            st.cache_data.clear()
            st.rerun()

    technical_views = [
        "TECHNICAL ANALYSIS",
        "TECHNICAL SCREENER",
        "PATTERN ANALYSIS",
        "METHODOLOGY & AUDIT",
    ]
    active_view = st.segmented_control(
        "TECHNICAL MODULE",
        technical_views,
        default=st.session_state.get("technical_active_view", "TECHNICAL ANALYSIS"),
        key="technical_active_view",
        width="stretch",
    ) or "TECHNICAL ANALYSIS"

    # ------------------------------------------------------------------
    # Direct analysis: one default ticker, then any ticker entered by user.
    # ------------------------------------------------------------------
    if active_view == "TECHNICAL ANALYSIS":
        st.markdown("### Security analysis")
        left, right = st.columns([3.2, 1])
        if ticker_override:
            left.info(f"Workspace ticker: {default_ticker}")
            ticker = default_ticker
        else:
            with left.form("direct_technical_ticker_form"):
                requested = st.text_input(
                    "YAHOO FINANCE TICKER",
                    value=st.session_state.technical_analysis_ticker,
                    placeholder="AAPL, TSLA, ENI.MI, ASML.AS, BTC-USD",
                    help="Enter one Yahoo Finance symbol. AAPL is shown by default.",
                )
                submitted = st.form_submit_button("LOAD ANALYSIS", width="stretch")
            if submitted and requested.strip():
                st.session_state.technical_analysis_ticker = requested.strip().upper()
            ticker = st.session_state.technical_analysis_ticker
        right.metric("ACTIVE TICKER", ticker)
        st.markdown(f"# {ticker}")
        _render_single_security(ticker, settings, context="direct_analysis")

    # ------------------------------------------------------------------
    # Index-wide screener: lists are used only to filter and inspect cases.
    # ------------------------------------------------------------------
    elif active_view == "TECHNICAL SCREENER":
        header = st.columns([1.35, 1.65, 0.8])
        universe_name = header[0].selectbox("INDEX UNIVERSE", list(UNIVERSES), key="technical_screen_universe")
        behaviour_options = [
            "ALL BEHAVIOURS",
            "In support area",
            "Approaching support",
            "Support breakdown",
            "In resistance area",
            "Approaching resistance",
            "Resistance breakout",
            "Flipped support confirmed",
            "Flipped resistance confirmed",
            "Bullish MA crossover",
            "Bearish MA crossover",
            "RSI overbought",
            "RSI oversold",
            "Potential bullish RSI divergence",
            "Potential bearish RSI divergence",
            "ANY PATTERN",
        ]
        behaviour = header[1].selectbox("TECHNICAL BEHAVIOUR", behaviour_options, key="technical_behaviour_filter")
        run_scan = header[2].button("RUN SCAN", width="stretch", type="primary")

        scan_key = f"{universe_name}|{settings.timeframe}|{settings}"
        if run_scan or st.session_state.get("technical_scan_key") != scan_key:
            with st.spinner(f"Scanning {universe_name} on {settings.timeframe.lower()} candles..."):
                data, source, constituents = _technical_prices(universe_name)
                rows, failures = scan_universe(constituents, data, settings)
            st.session_state.technical_scan_key = scan_key
            st.session_state.technical_scan_rows = rows
            st.session_state.technical_scan_failures = failures
            st.session_state.technical_scan_source = source
            st.session_state.technical_scan_data = data
            st.session_state.technical_scan_constituents = constituents

        rows = st.session_state.get("technical_scan_rows", pd.DataFrame())
        failures = st.session_state.get("technical_scan_failures", pd.DataFrame())
        source = st.session_state.get("technical_scan_source", "N/D")
        data = st.session_state.get("technical_scan_data", {})
        constituents = st.session_state.get("technical_scan_constituents", pd.DataFrame())

        filtered = rows.copy()
        if not filtered.empty:
            if behaviour == "ANY PATTERN":
                filtered = filtered[filtered["Patterns"].ne("—")]
            elif behaviour != "ALL BEHAVIOURS":
                filtered = filtered[
                    filtered["Setups"].str.contains(behaviour, case=False, regex=False, na=False)
                ]

            controls = st.columns([1.4, 1.2, 1.0])
            sectors = ["ALL SECTORS"] + sorted(filtered["Sector"].dropna().astype(str).unique())
            sector = controls[0].selectbox("SECTOR", sectors, key="technical_screen_sector")
            ticker_filter = controls[1].text_input("TICKER FILTER", placeholder="NVDA", key="technical_screen_ticker_filter")
            min_setups = controls[2].selectbox("MINIMUM SETUPS", [0, 1, 2, 3, 4, 5], key="technical_screen_min_setups")
            if sector != "ALL SECTORS":
                filtered = filtered[filtered["Sector"].astype(str) == sector]
            if ticker_filter.strip():
                filtered = filtered[filtered["Ticker"].str.contains(ticker_filter.strip(), case=False, regex=False)]
            filtered = filtered[filtered["Setup Count"] >= min_setups]

        st.caption(
            f"Constituents: {source} | Prices: Yahoo Finance | Analysed: {len(rows)}/{len(constituents)} | "
            f"Matches: {len(filtered)} | Timeframe: {settings.timeframe}"
        )
        _render_event_cards(rows)

        if filtered.empty:
            st.info("No securities match the selected technical behaviour and filters.")
        else:
            display_columns = [
                "Ticker",
                "Company",
                "Sector",
                "Technical State",
                "Setups",
                "Patterns",
                "Best Pattern",
                "Pattern Confidence",
                "Pattern Status",
                "Last",
                "Distance Support %",
                "Distance Resistance %",
                "RSI",
            ]
            st.dataframe(
                _format_scan(filtered[display_columns]),
                width="stretch",
                hide_index=True,
                height=min(620, 44 + len(filtered) * 35),
            )
            review_ticker = st.selectbox(
                "OPEN A MATCH ON THE CHART",
                filtered["Ticker"].tolist(),
                key="technical_screen_review_ticker",
            )
            raw = data.get(review_ticker)
            if raw is not None and not raw.empty:
                frame = resample_technical_frame(raw, settings.timeframe)
                snapshot = analyse_technical(review_ticker, frame, settings)
                st.markdown(f"## {review_ticker}")
                render_plotly(
                    _price_rsi_chart(review_ticker, frame, settings, snapshot),
                    page="technical",
                    chart="price_rsi",
                    ticker=review_ticker,
                    timeframe=settings.timeframe,
                    context="screen_result",
                    config={"scrollZoom": True, "displaylogo": False, "responsive": True},
                )

            st.download_button(
                "DOWNLOAD FILTERED RESULTS",
                filtered.to_csv(index=False).encode("utf-8"),
                file_name="technical_screener_filtered.csv",
                mime="text/csv",
            )

    # ------------------------------------------------------------------
    # Direct pattern analysis for any ticker, independent of the index scan.
    # ------------------------------------------------------------------
    elif active_view == "PATTERN ANALYSIS":
        st.markdown("### Pattern analysis")
        if ticker_override:
            pattern_ticker = default_ticker
            st.info(f"Pattern analysis synchronized to workspace ticker: {pattern_ticker}")
        else:
            with st.form("direct_pattern_ticker_form"):
                pattern_request = st.text_input(
                    "YAHOO FINANCE TICKER FOR PATTERN ANALYSIS",
                    value=st.session_state.technical_pattern_ticker,
                    placeholder="AAPL, UCG.MI, SAP.DE, BTC-USD",
                )
                pattern_submit = st.form_submit_button("DETECT PATTERNS", width="stretch")
            if pattern_submit and pattern_request.strip():
                st.session_state.technical_pattern_ticker = pattern_request.strip().upper()
            pattern_ticker = st.session_state.technical_pattern_ticker
        st.markdown(f"# {pattern_ticker}")
        prices = _custom_prices((pattern_ticker,))
        raw = prices.get(pattern_ticker)
        if raw is None or raw.empty:
            st.error(f"No usable Yahoo Finance price history found for {pattern_ticker}.")
        else:
            frame = resample_technical_frame(raw, settings.timeframe)
            snapshot = analyse_technical(pattern_ticker, frame, settings)
            details = snapshot.diagnostics.get("pattern_details", [])
            if not details:
                st.info("No potential pattern is detected with the current timeframe and parameters.")
                render_plotly(
                    _price_rsi_chart(pattern_ticker, frame, settings, snapshot),
                    page="technical",
                    chart="price_rsi",
                    ticker=pattern_ticker,
                    timeframe=settings.timeframe,
                    context="pattern_no_match",
                    config={"scrollZoom": True, "displaylogo": False, "responsive": True},
                )
            else:
                names = [str(item.get("name", "Potential pattern")) for item in details]
                pattern_name = st.selectbox("DETECTED PATTERN", names, key="direct_pattern_name")
                detail = next(item for item in details if str(item.get("name", "Potential pattern")) == pattern_name)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("PATTERN", pattern_name.replace("Potential ", ""))
                m2.metric("CONFIDENCE", f"{detail.get('confidence', 0)}%")
                m3.metric("LIFECYCLE", detail.get("status", "DEVELOPING"))
                m4.metric("DIRECTION", detail.get("direction", "NEUTRAL"))
                st.caption(
                    f"{pattern_name} | {settings.timeframe} candles | Full history retained through the latest bar. "
                    f"{detail.get('notes', '')}"
                )
                render_plotly(
                    _pattern_chart(pattern_ticker, frame, settings, detail),
                    page="technical",
                    chart="pattern",
                    ticker=pattern_ticker,
                    timeframe=settings.timeframe,
                    context=pattern_name,
                    config={"scrollZoom": True, "displaylogo": False, "responsive": True},
                )
                st.warning(
                    "Pattern recognition is heuristic. Highlighted anchors explain the detected geometry; the label "
                    "is not a forecast or trading signal."
                )

    else:
        st.markdown("### Transparent rules")
        st.write(
            "Direct analysis accepts any valid Yahoo Finance ticker and is independent of the index universe. The "
            "index universe is used only by the Technical Screener to find securities matching a selected behaviour."
        )
        st.write(
            "Daily, weekly or monthly candles are used consistently for levels, moving averages, RSI, divergences "
            "and pattern detection. The price and RSI panels share one synchronized time axis and retain the full "
            "downloaded history for interactive pan and zoom."
        )
        st.write(
            "Support and resistance are clustered swing zones. Approaching means the latest close lies within the "
            "selected proximity. Breakout and breakdown require the configured number of closes beyond the zone plus "
            "the selected buffer."
        )
        st.write(
            "Pattern detection uses explicit swing geometry, symmetry, slope, curvature and breakout rules. It reports "
            "a transparent confidence score and lifecycle state (developing, confirmed or retested), always as a potential "
            "structure requiring visual review. It does not alter the public cyclical matrix or generate BUY/SELL recommendations."
        )
        latest_failures = st.session_state.get("technical_scan_failures", pd.DataFrame())
        if isinstance(latest_failures, pd.DataFrame) and not latest_failures.empty:
            st.markdown("### Latest screener failures")
            st.dataframe(latest_failures, width="stretch", hide_index=True)

