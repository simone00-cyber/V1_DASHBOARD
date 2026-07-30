from typing import Dict, Tuple
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from config.theme import GREEN, RED, ORANGE, BLUE, MUTED
from config.universe import TIMEFRAME_LABELS
from charts.common import apply_terminal_layout
from analysis.security import build_security_report
from analysis.security_signal import build_tactical_signal_state
from analysis.cyclical import build_cyclical_engine, methodology_coverage
from caruso_analysis import RESAMPLE_RULES, TimeframeResult, calculate_composite_momentum, download_prices, prepare_technical_prices, resample_ohlc, summarize_timeframe

@st.cache_data(ttl=3600, show_spinner=False, max_entries=32)
def load_analysis(
    ticker: str,
    period: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, pd.DataFrame], Dict[str, TimeframeResult], Dict[str, str]]:
    daily_raw = download_prices(ticker, period)
    daily = prepare_technical_prices(daily_raw)
    frames: Dict[str, pd.DataFrame] = {}
    summaries: Dict[str, TimeframeResult] = {}
    errors: Dict[str, str] = {}

    for timeframe, rule in RESAMPLE_RULES.items():
        try:
            ohlc = resample_ohlc(daily, rule)
            calculated = calculate_composite_momentum(ohlc)
            frames[timeframe] = calculated
            summaries[timeframe] = summarize_timeframe(timeframe, calculated)
        except Exception as error:
            errors[timeframe] = str(error)

    return daily,daily_raw, frames, summaries, errors

def create_price_chart(daily: pd.DataFrame, ticker: str, years: int) -> go.Figure:
    cutoff = daily.index.max() - pd.DateOffset(years=years)
    frame = daily.loc[daily.index >= cutoff]

    fig = go.Figure(
        go.Candlestick(
            x=frame.index,
            open=frame["Open"],
            high=frame["High"],
            low=frame["Low"],
            close=frame["Close"],
            name="Prezzo",
            increasing_line_color=GREEN,
            decreasing_line_color=RED,
        )
    )
    fig.update_layout(title=f"{ticker.upper()} // PRICE ACTION", xaxis_rangeslider_visible=False, yaxis_title="Prezzo")
    return apply_terminal_layout(fig, 520)

def create_composite_chart(frame: pd.DataFrame, ticker: str, timeframe: str) -> go.Figure:
    clean = frame.dropna(subset=["Composite"]).copy()
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(x=clean.index, y=clean["MarketClose"] if "MarketClose" in clean.columns else clean["Close"], name="Chiusura di mercato", line=dict(width=1.4, color=BLUE)),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=clean.index, y=clean["Composite"], name="Composite Momentum", line=dict(width=2.2, color=ORANGE)),
        secondary_y=True,
    )

    for level, dash, color in [(80, "dot", RED), (50, "dash", ORANGE), (0, "solid", MUTED), (-50, "dash", ORANGE), (-80, "dot", GREEN)]:
        fig.add_hline(y=level, line_width=1, line_dash=dash, line_color=color, opacity=0.7, secondary_y=True)

    fig.update_yaxes(title_text="Prezzo", secondary_y=False)
    fig.update_yaxes(title_text="Composite Momentum", range=[-105, 105], secondary_y=True)
    fig.update_layout(title=f"{ticker.upper()} // COMPOSITE MOMENTUM // {TIMEFRAME_LABELS[timeframe].upper()}")
    return apply_terminal_layout(fig, 520)

def render_summary_table(summaries: Dict[str, TimeframeResult]) -> None:
    rows = []
    for key in ("YEARLY", "QUARTERLY", "MONTHLY", "WEEKLY"):
        if key not in summaries:
            continue
        item = summaries[key]
        rows.append(
            {
                "TIMEFRAME": TIMEFRAME_LABELS[key].upper(),
                "DATA": item.date.strftime("%d/%m/%Y"),
                "COMPOSITE": round(item.composite, 2),
                "PRECEDENTE": round(item.previous_composite, 2),
                "DIREZIONE": item.direction,
                "ZONA": item.position,
                "FLESSO": item.turn,
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

def render_security_report(*, ticker_override: str | None = None, embedded: bool = False) -> None:
    if not embedded:
        st.markdown("<div class='terminal-header'>SECURITY REPORT // CYCLICAL ANALYSIS</div>", unsafe_allow_html=True)
    st.caption("Signal engine and Active Position: adjusted OHLC (dividends/splits neutralised). Price chart and displayed levels: actual market OHLC.")

    controls = st.columns([1.2, 1, 1, 1])
    if ticker_override:
        ticker = ticker_override.strip().upper()
        controls[0].metric("WORKSPACE TICKER", ticker)
    else:
        ticker = controls[0].text_input("Ticker Yahoo Finance", value="ENI.MI").strip().upper()
    period = controls[1].selectbox("Storico", ["max", "20y", "15y", "10y"], index=0, key=f"security_period_{'workspace' if embedded else 'page'}")
    chart_years = controls[2].slider("Anni grafico", 1, 15, 5, key=f"security_chart_years_{'workspace' if embedded else 'page'}")
    controls[3].markdown("<br>", unsafe_allow_html=True)
    controls[3].button("GENERATE REPORT", type="primary", width="stretch", key=f"security_generate_{'workspace' if embedded else 'page'}")

    if not ticker:
        st.info("Inserisci un ticker.")
        return

    try:
        with st.spinner(f"Analisi di {ticker} in corso..."):
            daily,daily_raw, frames, summaries, errors = load_analysis(ticker, period)
    except Exception as error:
        st.error(f"Impossibile completare l'analisi: {error}")
        return

    if not summaries:
        st.error("Nessun timeframe dispone di dati sufficienti.")
        return

    signal_state = build_tactical_signal_state(frames, summaries)
    try:
        cycle_states, hierarchy = build_cyclical_engine(frames)
    except ValueError as error:
        st.error(f"Gerarchia ciclica non disponibile: {error}")
        if errors:
            with st.expander("TIMEFRAME NON DISPONIBILI"):
                for timeframe, message in errors.items():
                    st.write(f"**{TIMEFRAME_LABELS[timeframe]}:** {message}")
        return

    report = build_security_report(ticker, summaries, signal_state, cycle_states, hierarchy)
    latest_close = float(daily_raw["Close"].iloc[-1])
    previous_close = float(daily_raw["Close"].iloc[-2])
    daily_change = (latest_close / previous_close - 1.0) * 100.0
    weekly = summaries.get("WEEKLY")
    monthly = summaries.get("MONTHLY")

    cols = st.columns(4)
    cols[0].metric("LAST PRICE", f"{latest_close:,.2f}", f"{daily_change:+.2f}%")
    cols[1].metric("WEEKLY CM", f"{weekly.composite:.1f}" if weekly else "N/D", weekly.direction if weekly else None)
    cols[2].metric("MONTHLY CM", f"{monthly.composite:.1f}" if monthly else "N/D", monthly.direction if monthly else None)
    cols[3].metric(
        "ACTIVE POSITION",
        signal_state.position_label,
        f"{signal_state.signal_age_weeks} settimane" if signal_state.signal_age_weeks is not None else "N/D",
    )

    signal_color = GREEN if signal_state.current_position == "LONG" else RED if signal_state.current_position == "SHORT" else ORANGE
    signal_date = signal_state.signal_date.strftime("%d/%m/%Y") if signal_state.signal_date is not None else "N/D"
    rating_text = "●" * signal_state.rating if signal_state.rating else "N/D"

    st.markdown("<div class='terminal-subheader'>TACTICAL POSITION & EVENT</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='signal-box' style='border-left-color:{signal_color}'>"
        f"<b style='color:{signal_color};font-size:1.20rem'>{signal_state.position_label}</b><br>"
        f"Status: <b>{signal_state.status}</b><br>"
        f"Signal date: <b>{signal_date}</b> | Age: <b>{signal_state.signal_age_weeks if signal_state.signal_age_weeks is not None else 'N/D'} weeks</b><br>"
        f"Last weekly event: <b>{signal_state.latest_event}</b> | Rating: <b>{rating_text}</b><br>"
        f"<span class='small-note'>{signal_state.weekly_phase}</span></div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='terminal-subheader'>ENTRY CONDITIONS</div>", unsafe_allow_html=True)
    condition_cols = st.columns(4)
    condition_cols[0].metric("PRIMARY TREND", signal_state.primary_trend)
    condition_cols[1].metric("INTERMEDIATE TREND", signal_state.intermediate_trend)
    condition_cols[2].metric("WEEKLY PHASE", signal_state.weekly_phase)
    condition_cols[3].metric("ENTRY TRIGGER", signal_state.entry_trigger)

    st.markdown(
        f"<div class='report-box'><b>NEXT TRIGGER</b><br>{signal_state.next_trigger}"
        f"<br><br><b>INVALIDATION / REASSESSMENT</b><br>{signal_state.invalidation_condition}</div>",
        unsafe_allow_html=True,
    )

    if signal_state.history:
        with st.expander("SIGNAL HISTORY"):
            history_rows = []
            for event in reversed(signal_state.history[-12:]):
                history_rows.append({
                    "DATE": event.date.strftime("%d/%m/%Y"),
                    "EVENT": event.action,
                    "RATING": "●" * event.rating,
                    "QUARTERLY": event.quarterly_direction,
                    "MONTHLY": event.monthly_direction,
                    "WEEKLY": event.weekly_turn,
                    "WEEKLY CM": round(event.weekly_composite, 2),
                })
            st.dataframe(pd.DataFrame(history_rows), width="stretch", hide_index=True)

    st.markdown("<div class='terminal-subheader'>ANALYST COMMENT</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='report-box'>{report.replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)

    st.markdown("<div class='terminal-subheader'>CYCLICAL ENGINE // U-A-D-T MAP</div>", unsafe_allow_html=True)
    phase_rows = []
    for key in ("YEARLY", "QUARTERLY", "MONTHLY", "WEEKLY"):
        if key not in cycle_states:
            continue
        state = cycle_states[key]
        phase_rows.append({
            "TIMEFRAME": TIMEFRAME_LABELS[key].upper(),
            "PHASE": state.phase,
            "DIRECTION": state.direction,
            "COMPOSITE": round(state.composite, 2),
            "SLOPE": round(state.slope, 2),
            "TURN": state.turn,
            "STATE AGE": state.state_age,
            "PHASE START": state.phase_start.strftime("%d/%m/%Y"),
            "EXCESS": state.excess,
        })
    st.dataframe(pd.DataFrame(phase_rows), width="stretch", hide_index=True)

    hierarchy_cols = st.columns(3)
    hierarchy_cols[0].metric("ALIGNMENT", hierarchy.alignment)
    hierarchy_cols[1].metric("TACTICAL CONDITION", hierarchy.tactical_condition)
    hierarchy_cols[2].metric("WEEKLY PHASE", hierarchy.weekly_phase)
    notes_html = "<br>".join(f"• {note}" for note in hierarchy.notes) or "Nessuna nota aggiuntiva."
    st.markdown(
        f"<div class='report-box'><b>DOCUMENTED TRIGGER</b><br>{hierarchy.documented_trigger}"
        f"<br><br><b>HIERARCHY NOTES</b><br>{notes_html}</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='terminal-subheader'>QUANTITATIVE FRAMEWORK</div>", unsafe_allow_html=True)
    render_summary_table(summaries)

    with st.expander("METHODOLOGY COVERAGE / PROVENANCE"):
        coverage_rows = [
            {
                "COMPONENT": item.component,
                "STATUS": item.status,
                "SOURCE": item.source,
                "NOTE": item.note,
            }
            for item in methodology_coverage()
        ]
        st.dataframe(pd.DataFrame(coverage_rows), width="stretch", hide_index=True)

    tabs = st.tabs(["PRICE", "WEEKLY CM", "MONTHLY CM", "QUARTERLY CM"])
    with tabs[0]:
        st.plotly_chart(create_price_chart(daily_raw, ticker, chart_years), width="stretch")
    with tabs[1]:
        if "WEEKLY" in frames:
            st.plotly_chart(create_composite_chart(frames["WEEKLY"], ticker, "WEEKLY"), width="stretch")
    with tabs[2]:
        if "MONTHLY" in frames:
            st.plotly_chart(create_composite_chart(frames["MONTHLY"], ticker, "MONTHLY"), width="stretch")
    with tabs[3]:
        if "QUARTERLY" in frames:
            st.plotly_chart(create_composite_chart(frames["QUARTERLY"], ticker, "QUARTERLY"), width="stretch")

    if errors:
        with st.expander("TIMEFRAME NON DISPONIBILI"):
            for timeframe, message in errors.items():
                st.write(f"**{TIMEFRAME_LABELS[timeframe]}:** {message}")
