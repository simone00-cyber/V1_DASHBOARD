from __future__ import annotations

from typing import Any

import streamlit as st
from dotenv import load_dotenv

from core.ai.market_intelligence import (
    MarketIntelligenceError,
    ask_market_intelligence,
    generate_daily_briefing,
)
from core.ai.providers.base import AIProviderConfigurationError
from core.ai.providers.gemini import GeminiProvider


PROVIDER_KEY = "market_intel_provider"
MESSAGES_KEY = "market_intel_messages"

# (label, kind) — "ask" round-trips through the assistant; "strategy" hands
# off to the (unmodified) AI Strategy Lab instead of answering here.
_SUGGESTIONS: list[tuple[str, str]] = [
    ("Why is the market mixed today?", "ask"),
    ("What's driving the current regime?", "ask"),
    ("Which opportunities are emerging?", "ask"),
    ("Turn this into a trading strategy", "strategy"),
]


def _switch_to(name: str) -> None:
    page = st.session_state.get("_pages", {}).get(name)
    if page is not None:
        st.switch_page(page)


def _get_provider() -> GeminiProvider | None:
    if PROVIDER_KEY not in st.session_state:
        load_dotenv()
        try:
            # A higher temperature than the Strategy Lab's provider: this
            # mode writes connected macro narrative prose, not deterministic
            # strategy-operation JSON, and benefits from more varied phrasing.
            st.session_state[PROVIDER_KEY] = GeminiProvider(temperature=0.4)
        except AIProviderConfigurationError:
            st.session_state[PROVIDER_KEY] = None

    return st.session_state[PROVIDER_KEY]


def render_market_intelligence_panel(
    market_context: dict[str, Any],
    fallback_briefing: str,
) -> None:
    """
    Render the unified AI assistant, in Market Intelligence mode, as the
    dominant surface of the Command Center — not a sidebar chat attached to
    a dashboard.

    On first load it proactively opens with a synthesized briefing (LLM
    generated when available, a deterministic fallback otherwise — the page
    must never look broken or empty on open). The user can then keep talking
    to the same assistant, or hand off into the AI Strategy Lab.

    Uses the same GeminiProvider as the AI Strategy Lab, unmodified. Never
    touches AIStrategySession, StrategyParser, ResearchProject or the DSL.
    """

    st.markdown(
        "<div class='cio-persona'>Chief Investment Strategist</div>",
        unsafe_allow_html=True,
    )

    st.session_state.setdefault(MESSAGES_KEY, [])
    messages: list[dict[str, str]] = st.session_state[MESSAGES_KEY]

    if not messages:
        messages.append(
            {
                "role": "assistant",
                "content": _opening_briefing(market_context, fallback_briefing),
            }
        )

    with st.container(height=380, border=False):
        for message in messages[-8:]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    _render_suggestions(market_context)

    question = st.chat_input("Ask your strategist anything…", key="market_intel_chat_input")
    if question:
        _handle_question(market_context, question)
        st.rerun()


def _opening_briefing(market_context: dict[str, Any], fallback_briefing: str) -> str:
    provider = _get_provider()

    if provider is None:
        return fallback_briefing

    try:
        with st.spinner("Preparing this morning's briefing…"):
            return generate_daily_briefing(provider, context=market_context)
    except MarketIntelligenceError:
        return fallback_briefing


def _render_suggestions(market_context: dict[str, Any]) -> None:
    columns = st.columns(len(_SUGGESTIONS))

    for column, (label, kind) in zip(columns, _SUGGESTIONS):
        with column:
            if st.button(label, key=f"mi_suggestion_{label}", use_container_width=True):
                if kind == "strategy":
                    st.session_state["pending_ai_message"] = (
                        "I want to turn today's market view into a trading strategy."
                    )
                    _switch_to("AI Strategy Lab")
                else:
                    _handle_question(market_context, label)
                    st.rerun()


def _handle_question(market_context: dict[str, Any], question: str) -> None:
    messages: list[dict[str, str]] = st.session_state[MESSAGES_KEY]
    messages.append({"role": "user", "content": question})

    provider = _get_provider()

    if provider is None:
        messages.append(
            {
                "role": "assistant",
                "content": (
                    "Market Intelligence isn't configured — GEMINI_API_KEY is "
                    "missing."
                ),
            }
        )
        return

    history = [
        {"role": message["role"], "content": message["content"]}
        for message in messages[:-1]
    ]

    try:
        with st.spinner("Analyzing market context…"):
            answer = ask_market_intelligence(
                provider,
                context=market_context,
                history=history,
                question=question,
            )
    except MarketIntelligenceError as exc:
        answer = f"I couldn't process that request: {exc}"

    messages.append({"role": "assistant", "content": answer})
