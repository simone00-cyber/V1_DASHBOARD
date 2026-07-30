import streamlit as st

def render_methodology() -> None:
    st.markdown("<div class='terminal-header'>METHODOLOGY // DATA AND MODEL BOUNDARIES</div>", unsafe_allow_html=True)
    st.markdown(
        """
### Security Report

La sezione sul singolo titolo usa esclusivamente la parte formalizzata nei paper:

- KEY
- XTL
- Composite Momentum
- livelli 0, ±50 e ±80
- direzione annuale, trimestrale, mensile e settimanale
- flessi settimanali
- matrice operativa multi-timeframe

Non vengono replicate formule proprietarie che non compaiono integralmente nei documenti.

### Global Macro

Global Macro e Market Regime sono moduli aggiuntivi della dashboard. Utilizzano dati Yahoo Finance e non fanno parte della tecnica documentale di Francesco Caruso.

### Bond data

- `^TNX`, `^FVX`, `^IRX`, `^TYX` e gli eventuali ticker 2Y disponibili sono trattati come indici di rendimento.
- futures Treasury ed ETF BTP/Bund sono strumenti di **prezzo**, non rendimenti.
- il terminale non calcola lo spread BTP-Bund da ETF, perché sarebbe metodologicamente errato.

### Uso

Il progetto ha finalità didattiche e di ricerca. I dati possono essere ritardati, incompleti o temporaneamente indisponibili.
        """
    )
