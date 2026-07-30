"""Shared cross-page navigation actions.

Every page that shows a ticker card/panel needs the same three jumps (open a
ticker in Research, hand a ticker off to the AI Strategy Lab, jump to
Opportunities/sector comparison). Previously duplicated per-file
(`ui/opportunity_cards.py`, `ui/research_panels.py`); centralised here so a
third and fourth copy (the new fundamental cards/panels) don't re-duplicate it
again. All of them read the `_pages` registry `app.py` publishes in
`st.session_state` and no-op if a destination isn't registered.
"""

from __future__ import annotations

import streamlit as st


def navigate_to_research(ticker: str) -> None:
    """Point the Research Workspace at `ticker` and navigate there."""
    pages = st.session_state.get("_pages", {})
    st.session_state["workspace_ticker"] = ticker
    st.session_state["workspace_loading"] = True
    if "Research Workspace" in pages:
        st.switch_page(pages["Research Workspace"])


def navigate_to_build_strategy(prompt: str) -> None:
    """Prefill the AI Strategy Lab prompt and navigate there."""
    pages = st.session_state.get("_pages", {})
    st.session_state["pending_ai_message"] = prompt
    if "AI Strategy Lab" in pages:
        st.switch_page(pages["AI Strategy Lab"])


def navigate_to_opportunities() -> None:
    """Navigate to the Opportunities page (sector leadership / rankings)."""
    pages = st.session_state.get("_pages", {})
    if "Opportunities" in pages:
        st.switch_page(pages["Opportunities"])
