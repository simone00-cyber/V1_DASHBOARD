import pandas as pd
import streamlit as st
from config.universe import REGIME_UNIVERSE
from config.theme import GREEN, RED, ORANGE, MUTED, TEXT
from data.yahoo import download_close_batch
from analysis.regime import RegimeLayer, build_market_regime, build_regime_comment
from charts.regime import create_regime_radar

def regime_color(label: str) -> str:
    upper = label.upper()
    if any(word in upper for word in ["CONSTRUCTIVE", "IMPROVING", "RISK-ON", "POSITIVE"]):
        return GREEN
    if any(word in upper for word in ["DEFENSIVE", "DETERIORATING", "RISK-OFF", "NEGATIVE"]):
        return RED
    return ORANGE


def render_regime_card(layer: RegimeLayer) -> None:
    color = regime_color(layer.diagnosis)
    delta = layer.score - layer.previous_score
    st.markdown(
        f"<div class='regime-badge' style='color:{color};border-color:{color}'>"
        f"<span style='font-size:0.74rem;color:{MUTED}'>{layer.title} // {layer.horizon}</span><br>"
        f"{layer.diagnosis}<br>"
        f"<span style='font-size:0.86rem;color:{TEXT}'>SCORE {layer.score:+.2f} | Δ {delta:+.2f} | COVERAGE {layer.coverage:.0%}</span><br>"
        f"<span style='font-size:0.72rem;color:{MUTED}'>{layer.previous_diagnosis} → {layer.diagnosis}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

def render_market_regime(show_header: bool = True) -> None:
    if show_header:
        st.markdown(
            "<div class='terminal-header'>MARKET REGIME // STRUCTURAL, TACTICAL & DAILY DIAGNOSIS</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='terminal-subheader'>MARKET REGIME // STRUCTURAL, TACTICAL & DAILY DIAGNOSIS</div>",
            unsafe_allow_html=True,
        )

    with st.spinner("Calcolo del regime strutturale, della direzione tattica e del tono giornaliero..."):
        close = download_close_batch(tuple(REGIME_UNIVERSE.values()), period="2y")

    if close.empty:
        st.error("Dati insufficienti per calcolare il Market Regime.")
        return

    results = build_market_regime(close)

    cards = st.columns(3)
    for column, key in zip(cards, ("STRATEGIC", "TACTICAL", "DAILY")):
        with column:
            render_regime_card(results[key])

    st.markdown("<div class='terminal-subheader'>REGIME TRANSITION</div>", unsafe_allow_html=True)
    transition_rows = [
        {
            "ORIZZONTE": layer.title,
            "PRECEDENTE": layer.previous_diagnosis,
            "ATTUALE": layer.diagnosis,
            "SCORE PRECEDENTE": layer.previous_score,
            "SCORE ATTUALE": layer.score,
            "DELTA": layer.score - layer.previous_score,
        }
        for layer in results.values()
    ]
    transition_table = pd.DataFrame(transition_rows)
    st.dataframe(
        transition_table.style.format(
            {
                "SCORE PRECEDENTE": "{:+.2f}",
                "SCORE ATTUALE": "{:+.2f}",
                "DELTA": "{:+.2f}",
            }
        ),
        width="stretch",
        hide_index=True,
    )

    st.markdown("<div class='terminal-subheader'>REGIME INTERPRETATION</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='report-box'>{build_regime_comment(results)}</div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.05, 1.95])
    with left:
        selected_layer = st.selectbox(
            "Pillar map",
            options=["STRATEGIC", "TACTICAL", "DAILY"],
            format_func=lambda key: results[key].title,
        )
        st.plotly_chart(create_regime_radar(results[selected_layer]), width="stretch")

    with right:
        st.markdown("<div class='terminal-subheader'>PILLAR DIAGNOSTICS</div>", unsafe_allow_html=True)
        rows = []
        for key, layer in results.items():
            for pillar in layer.pillars:
                rows.append(
                    {
                        "ORIZZONTE": layer.title,
                        "PILASTRO": pillar.name,
                        "STATO": pillar.state,
                        "SCORE": pillar.score,
                        "DETTAGLIO": pillar.details,
                    }
                )
        table = pd.DataFrame(rows)
        styled = (
            table.style
            .format({"SCORE": "{:+.2f}"})
            .map(
                lambda value: (
                    f"color:{GREEN};font-weight:700"
                    if "POSITIVE" in str(value)
                    else f"color:{RED};font-weight:700"
                    if "NEGATIVE" in str(value)
                    else f"color:{ORANGE};font-weight:700"
                ),
                subset=["STATO"],
            )
        )
        st.dataframe(styled, width="stretch", hide_index=True, height=470)

    st.markdown("<div class='terminal-subheader'>MODEL LOGIC</div>", unsafe_allow_html=True)
    st.markdown(
        """
- **Structural Backdrop:** trend a 3-6 mesi, posizione rispetto alla MM200, credito strutturale, VIX, curva e tassi.
- **Tactical Direction:** accelerazione/decelerazione a 1-4 settimane e confronto con la rilevazione di una settimana prima.
- **Today's Tone:** movimento dell'ultima seduta su equity, VIX, credito, tassi, dollaro e Copper/Gold.
- Le tre sezioni hanno **classificazioni diverse**: `CONSTRUCTIVE/DEFENSIVE`, `IMPROVING/DETERIORATING`, `RISK-ON/RISK-OFF`.
- La tabella **Regime Transition** mostra esplicitamente il passaggio dallo stato precedente a quello attuale.
- Questo modello macro è separato dalla metodologia documentale del Composite Momentum.
        """
    )
