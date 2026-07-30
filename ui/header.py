from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from config.theme import MUTED, GREEN, RED
from data.yahoo import download_close_batch
from core.metrics import safe_pct_change

def fmt_change(value: float) -> str:
    if pd.isna(value):
        return "N/D"
    return f"{value:+.2f}%"

def render_top_bar() -> None:
    now = datetime.now(ZoneInfo("Europe/Rome"))
    bar_col, action_col = st.columns([9, 1], vertical_alignment="center")
    with bar_col:
        st.markdown(
            f"<div class='top-terminal-bar'>"
            f"<span>CYCLICAL GLOBAL MACRO TERMINAL</span>"
            f"<span>{now.strftime('%A %d %B %Y // %H:%M CET')}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with action_col:
        if st.button("🔄", key="clear_data_cache", help="Clear cached data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    strip_universe = {
        "S&P": "^GSPC",
        "NASDAQ": "^IXIC",
        "DAX": "^GDAXI",
        "MIB": "FTSEMIB.MI",
        "VIX": "^VIX",
        "US10Y": "^TNX",
        "DXY": "DX-Y.NYB",
        "GOLD": "GC=F",
        "WTI": "CL=F",
        "BTC": "BTC-USD",
    }

    close = download_close_batch(tuple(strip_universe.values()), period="1mo")
    items = []

    for name, ticker in strip_universe.items():
        if ticker not in close.columns or close[ticker].dropna().empty:
            items.append(f"<span>{name} <b style='color:{MUTED}'>N/D</b></span>")
            continue

        series = close[ticker].dropna()
        last = float(series.iloc[-1])
        change = safe_pct_change(series, 1)
        color = GREEN if change >= 0 else RED
        items.append(
            f"<span>{name} {last:,.2f} "
            f"<b style='color:{color}'>{fmt_change(change)}</b></span>"
        )

    st.markdown(
        f"<div class='ticker-strip'>{''.join(items)}</div>",
        unsafe_allow_html=True,
    )
