from __future__ import annotations

import streamlit as st


def render_global_navigation() -> None:
    pages = st.session_state.get("_pages", {})

    if not pages:
        return

    cols = st.columns(
        [1.7, 1.4, 1.3, 1.3, 1.2],
        gap="small",
        vertical_alignment="center",
    )

    with cols[0]:
        if st.button(
            "CYCLICAL",
            key="nav_home",
            use_container_width=True,
            type="primary",
        ):
            st.switch_page(pages["Command Center"])

    with cols[1]:
        if st.button(
            "Market",
            key="nav_market",
            use_container_width=True,
        ):
            st.switch_page(pages["Macro & Rates"])

    with cols[2]:
        if st.button(
            "Opportunities",
            key="nav_opportunities",
            use_container_width=True,
        ):
            st.switch_page(pages["Opportunities"])

    with cols[3]:
        if st.button(
            "Research",
            key="nav_research",
            use_container_width=True,
        ):
            st.switch_page(pages["Research Workspace"])

    with cols[4]:
        if st.button(
            "AI Labs",
            key="nav_ai",
            use_container_width=True,
        ):
            st.switch_page(pages["AI Strategy Lab"])