from __future__ import annotations

import streamlit as st

from core.logging_config import configure_logging
from config.theme import CUSTOM_CSS
from ui.header import render_top_bar
from views.overview import render_global_overview
from views.macro import render_global_macro
from views.shipping import render_shipping
from views.screener import render_market_screener
from views.workspace import render_asset_workspace
from views.strategy_lab import render_strategy_lab
from views.methodology import render_methodology
from ui.navigation import render_global_navigation
configure_logging()

st.set_page_config(
    page_title="Cyclical Global Macro Terminal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

command_page = st.Page(
    render_global_overview, title="Command Center", icon="🎯",
    url_path="command-center", default=True,
)
macro_page = st.Page(
    render_global_macro, title="Macro & Rates", icon="📈", url_path="macro-rates",
)
geo_page = st.Page(
    render_shipping, title="Geopolitical Risk", icon="🚢", url_path="geopolitical-risk",
)
opportunities_page = st.Page(
    render_market_screener, title="Opportunities", icon="🔎", url_path="opportunities",
)
workspace_page = st.Page(
    render_asset_workspace, title="Research Workspace", icon="🔬", url_path="research-workspace",
)
ai_page = st.Page(
    render_strategy_lab, title="AI Strategy Lab", icon="🧠", url_path="ai-strategy-lab",
)
methodology_page = st.Page(
    render_methodology, title="Methodology", icon="📖", url_path="methodology",
)

pg = st.navigation(
    [
        command_page,
        macro_page,
        geo_page,
        opportunities_page,
        workspace_page,
        ai_page,
        methodology_page,
    ],
    position="top",
)

# Shared registry so any page can st.switch_page(...) another destination by
# name without every view needing to import app.py (which would re-run it).
st.session_state["_pages"] = {
    "Command Center": command_page,
    "Macro & Rates": macro_page,
    "Geopolitical Risk": geo_page,
    "Opportunities": opportunities_page,
    "Research Workspace": workspace_page,
    "AI Strategy Lab": ai_page,
    "Methodology": methodology_page,
}


def _render_ambient_ai_bar() -> None:
    prompt = st.chat_input(
        "Ask the AI research assistant to build or refine a strategy…",
        key="ambient_ai_ask",
    )
    if prompt:
        st.session_state["pending_ai_message"] = prompt
        st.switch_page(ai_page)

render_global_navigation()
render_top_bar()

# The AI Strategy Lab has its own chat input, and the Command Center embeds
# its own "Market Intelligence" panel — the generic ambient bar would be
# redundant on both, so it only appears on the remaining destinations.
if pg.url_path not in {ai_page.url_path, command_page.url_path}:
    _render_ambient_ai_bar()

pg.run()
