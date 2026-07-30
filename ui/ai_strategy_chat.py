from __future__ import annotations

from typing import Any

import streamlit as st
from dotenv import load_dotenv

from core.ai.ai_session import AIStrategySession
from core.ai.prompt_manager import PromptManager
from core.ai.providers.gemini import GeminiProvider
from core.ai.providers.session_adapter import SessionLLMAdapter


SESSION_KEY = "ai_strategy_session"

# Collapses the fine-grained ConversationState machine into the five stages a
# researcher actually cares about. Multiple internal states can map to one
# stage (e.g. every pre-validation state is still "Define").
_STEPPER_STAGES = [
    ("define", "Define", {"new", "asking_ticker", "asking_goal", "building_strategy"}),
    ("validate", "Validate", {"validating"}),
    ("review", "Review", {"ready_for_review"}),
    ("approve", "Approve", {"approved"}),
    ("backtest", "Backtest", {"backtest_running", "completed"}),
]

_RESPONSE_TYPE_CHIP = {
    "error": ("is-critical", "⛔"),
    "approval_required": ("is-warning", "⏳"),
    "ready_for_review": ("is-good", "✅"),
    "validation": ("is-info", "🧪"),
    "question": ("is-info", "❔"),
    "clarification": ("is-info", "❔"),
    "strategy_update": ("is-info", "🛠️"),
    "information": ("is-neutral", "ℹ️"),
}

_SEVERITY_CHIP = {
    "error": ("is-critical", "⛔"),
    "warning": ("is-warning", "⚠️"),
    "info": ("is-info", "ℹ️"),
}


def create_ai_strategy_session() -> AIStrategySession:
    """
    Create the complete AI research session.

    Environment variables are loaded before GeminiProvider is created.
    """

    load_dotenv()

    provider = GeminiProvider()
    llm_client = SessionLLMAdapter(provider)
    prompt_manager = PromptManager()

    return AIStrategySession(
        prompt_provider=prompt_manager,
        llm_client=llm_client,
    )


def get_ai_strategy_session() -> AIStrategySession:
    """
    Return the current Streamlit user session, creating it when needed.
    """

    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = create_ai_strategy_session()

    session = st.session_state[SESSION_KEY]

    if not isinstance(session, AIStrategySession):
        session = create_ai_strategy_session()
        st.session_state[SESSION_KEY] = session

    return session


def reset_ai_strategy_session() -> None:
    """
    Remove the current AI session and create a clean research project.
    """

    st.session_state.pop(SESSION_KEY, None)


def render_ai_strategy_lab() -> None:
    """
    Render the complete AI Strategy Research Lab.
    """

    session = get_ai_strategy_session()

    pending_message = st.session_state.pop("pending_ai_message", None)
    if pending_message:
        with st.spinner("Gemini sta analizzando la richiesta…"):
            session.process_user_message(pending_message)

    _render_header()
    _render_stepper(session)

    chat_column, project_column = st.columns(
        [1.65, 1],
        gap="large",
    )

    with chat_column:
        _render_chat_panel(session)

    with project_column:
        _render_project_panel(session)


def _render_header() -> None:
    title_column, action_column = st.columns(
        [5, 1],
        vertical_alignment="center",
    )

    with title_column:
        st.markdown(
            """
            <div class="ai-lab-header">
                <div class="ai-lab-kicker">AI STRATEGY LAB · THE CENTER OF YOUR RESEARCH</div>
                <div class="ai-lab-title">Describe an idea. Get a validated strategy.</div>
                <div class="ai-lab-subtitle">
                    Design, validate and review systematic trading
                    strategies through natural-language research — every
                    change is deterministically checked before it reaches
                    your project.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with action_column:
        if st.button(
            "New project",
            key="ai_strategy_new_project",
            use_container_width=True,
        ):
            reset_ai_strategy_session()
            st.rerun()


def _render_stepper(session: AIStrategySession) -> None:
    state_value = getattr(session.state, "value", str(session.state))

    if state_value == "error":
        st.markdown(
            "<span class='status-chip is-critical'>⛔ The last request could not be "
            "processed — see the conversation below.</span>",
            unsafe_allow_html=True,
        )

    current_index = 0
    for index, (_, _, members) in enumerate(_STEPPER_STAGES):
        if state_value in members:
            current_index = index
            break

    chips = []
    for index, (key, label, _) in enumerate(_STEPPER_STAGES):
        if key == "backtest":
            css_class = "is-locked"
        elif index < current_index:
            css_class = "is-done"
        elif index == current_index:
            css_class = "is-active"
        else:
            css_class = ""

        chips.append(
            f"<div class='workflow-step {css_class}'><span class='dot'></span>{label}</div>"
        )
        if index != len(_STEPPER_STAGES) - 1:
            chips.append("<div class='workflow-arrow'>→</div>")

    st.markdown(
        f"<div class='workflow-stepper'>{''.join(chips)}</div>",
        unsafe_allow_html=True,
    )


def _render_chat_panel(
    session: AIStrategySession,
) -> None:
    st.markdown("### Research conversation")

    messages = _get_conversation_messages(session)

    if not messages:
        with st.chat_message("assistant"):
            st.markdown(
                """
                Ciao. Descrivimi liberamente la strategia che vuoi
                analizzare.

                Puoi partire da un'idea generale, per esempio:

                *“Vorrei una strategia trend following long su azioni
                americane.”*
                """
            )
    else:
        for message in messages:
            _render_message(message)

    user_message = st.chat_input(
        "Descrivi la strategia o rispondi alla domanda dell'assistente…",
        key="ai_strategy_chat_input",
    )

    if user_message:
        with st.spinner(
            "Gemini sta analizzando la richiesta…"
        ):
            result = session.process_user_message(
                user_message
            )

        if result.success:
            st.rerun()

        st.error(
            result.error
            or "La richiesta non è stata elaborata."
        )


def _render_message(
    message: dict[str, Any],
) -> None:
    role = str(
        message.get("role", "assistant")
    ).lower()

    if role not in {"user", "assistant"}:
        role = "assistant"

    content = (
        message.get("content")
        or message.get("message")
        or message.get("text")
        or ""
    )

    with st.chat_message(role):
        st.markdown(str(content))

        metadata = message.get("metadata")

        if (
            role == "assistant"
            and isinstance(metadata, dict)
            and metadata
        ):
            response_type = metadata.get(
                "response_type"
            )

            if response_type:
                css_class, icon = _RESPONSE_TYPE_CHIP.get(
                    response_type,
                    ("is-neutral", "•"),
                )
                st.markdown(
                    f"<span class='status-chip {css_class}'>{icon} "
                    f"{response_type.replace('_', ' ')}</span>",
                    unsafe_allow_html=True,
                )


def _render_project_panel(
    session: AIStrategySession,
) -> None:
    project_payload = session.project.to_dict()
    health_payload = session.health.to_dict()
    strategy_payload = project_payload.get("strategy") or {}

    name = project_payload.get("name", "Untitled Research Project")
    st.markdown(f"#### {name}")

    _render_strategy_badges(strategy_payload)

    completion_score = int(health_payload.get("completion_score", 0) or 0)
    st.progress(
        min(max(completion_score, 0), 100) / 100,
        text=f"Completeness — {completion_score}%",
    )

    ticker = project_payload.get("ticker") or strategy_payload.get("instrument", {}).get("ticker")
    if ticker:
        if st.button(
            f"Open {ticker} in Research Workspace →",
            key="ai_strategy_open_workspace",
            use_container_width=True,
        ):
            st.session_state["workspace_ticker"] = ticker
            _switch_to("Research Workspace")

    with st.popover("📋  Strategy details", use_container_width=True):
        _render_project_metrics(session=session, health_payload=health_payload)
        st.markdown("##### Rules & risk")
        _render_strategy_summary(strategy_payload)
        st.markdown("##### Validation")
        _render_validation_issues(health_payload)
        st.markdown("##### Backtest")
        _render_backtest_section(session)
        with st.expander("Advanced — raw project data", expanded=False):
            st.json(project_payload)


def _switch_to(name: str) -> None:
    page = st.session_state.get("_pages", {}).get(name)
    if page is not None:
        st.switch_page(page)


def _render_strategy_badges(strategy: dict[str, Any]) -> None:
    instrument = (strategy or {}).get("instrument", {}) or {}
    direction = (strategy or {}).get("direction", {}) or {}

    ticker = str(instrument.get("ticker") or "—").upper()
    timeframe = str(instrument.get("timeframe") or "—")

    badges = [f"<span class='badge'>{ticker}</span>", f"<span class='badge'>{timeframe}</span>"]
    if direction.get("long_enabled"):
        badges.append("<span class='badge is-long'>LONG</span>")
    if direction.get("short_enabled"):
        badges.append("<span class='badge is-short'>SHORT</span>")
    st.markdown(" ".join(badges), unsafe_allow_html=True)


def _render_strategy_summary(strategy: dict[str, Any]) -> None:
    if not strategy:
        st.info("La strategia non è ancora stata definita.")
        return

    entry = strategy.get("entry", {}) or {}
    exit_rules = strategy.get("exit", {}) or {}
    risk = strategy.get("risk", {}) or {}
    execution = strategy.get("execution", {}) or {}

    cols = st.columns(4)
    cols[0].metric("Long entry rules", len(entry.get("long", []) or []))
    cols[1].metric("Short entry rules", len(entry.get("short", []) or []))
    cols[2].metric("Long exit rules", len(exit_rules.get("long", []) or []))
    cols[3].metric("Short exit rules", len(exit_rules.get("short", []) or []))

    risk_bits = []
    if risk.get("initial_capital"):
        risk_bits.append(f"Capital: {risk['initial_capital']:,.0f}")
    if risk.get("position_sizing_method"):
        size = risk.get("position_size")
        risk_bits.append(
            f"Sizing: {risk['position_sizing_method']}"
            + (f" ({size})" if size is not None else "")
        )
    for field_name, label in (
        ("stop_loss", "Stop loss"),
        ("take_profit", "Take profit"),
        ("trailing_stop", "Trailing stop"),
        ("maximum_holding_bars", "Max holding bars"),
    ):
        if risk.get(field_name) is not None:
            risk_bits.append(f"{label}: {risk[field_name]}")

    if risk_bits:
        st.caption(" · ".join(risk_bits))

    execution_bits = []
    if execution.get("order_type"):
        execution_bits.append(f"Order: {execution['order_type']}")
    if execution.get("signal_execution"):
        execution_bits.append(f"Timing: {execution['signal_execution']}")
    if execution.get("commission_value") is not None:
        execution_bits.append(f"Commission: {execution['commission_value']}")
    if execution.get("slippage_value") is not None:
        execution_bits.append(f"Slippage: {execution['slippage_value']}")

    if execution_bits:
        st.caption(" · ".join(execution_bits))


def _render_validation_issues(health_payload: dict[str, Any]) -> None:
    completion_score = int(health_payload.get("completion_score", 0) or 0)
    st.progress(
        min(max(completion_score, 0), 100) / 100,
        text=f"Strategy completeness — {completion_score}%",
    )

    issues = health_payload.get("issues") or []
    if not issues:
        st.markdown(
            "<span class='status-chip is-good'>✅ No open validation issues</span>",
            unsafe_allow_html=True,
        )
        return

    severity_order = {"error": 0, "warning": 1, "info": 2}
    ordered_issues = sorted(
        issues,
        key=lambda issue: severity_order.get(issue.get("severity", "info"), 3),
    )

    for issue in ordered_issues:
        severity = issue.get("severity", "info")
        css_class, icon = _SEVERITY_CHIP.get(severity, ("is-neutral", "•"))
        message = issue.get("message", "")
        suggestion = issue.get("suggestion")
        line = f"<div class='status-chip {css_class}'>{icon} {message}</div>"
        st.markdown(line, unsafe_allow_html=True)
        if suggestion:
            st.caption(suggestion)


def _render_backtest_section(session: AIStrategySession) -> None:
    if session.project.is_approved:
        st.button(
            "Run backtest",
            key="ai_strategy_run_backtest",
            use_container_width=True,
            disabled=True,
        )
        st.caption(
            "The strategy is approved. Backtest execution isn't wired into "
            "this workspace yet — it's the next step on the roadmap."
        )
    else:
        st.markdown(
            "<span class='status-chip is-neutral'>🔒 Locked</span>",
            unsafe_allow_html=True,
        )
        st.caption("Approve the strategy in the conversation to unlock backtesting.")


def _render_project_metrics(
    *,
    session: AIStrategySession,
    health_payload: dict[str, Any],
) -> None:
    state_value = getattr(
        session.state,
        "value",
        str(session.state),
    )

    is_ready = bool(
        health_payload.get(
            "is_ready_for_review",
            False,
        )
    )

    can_be_approved = bool(
        health_payload.get(
            "can_be_approved",
            False,
        )
    )

    metric_one, metric_two, metric_three = st.columns(3)

    metric_one.metric(
        "State",
        state_value.replace("_", " ").title(),
    )

    metric_two.metric(
        "Review",
        "Ready" if is_ready else "Draft",
    )

    metric_three.metric(
        "Approval",
        "Available" if can_be_approved else "Blocked",
    )


def _get_conversation_messages(
    session: AIStrategySession,
) -> list[dict[str, Any]]:
    """
    Normalize the Conversation representation for the UI.

    This avoids coupling the Streamlit page to the internal Conversation
    implementation.
    """

    conversation = session.project.conversation

    if hasattr(conversation, "to_dict"):
        payload = conversation.to_dict()
    else:
        payload = conversation

    if isinstance(payload, list):
        raw_messages = payload
    elif isinstance(payload, dict):
        raw_messages = (
            payload.get("messages")
            or payload.get("conversation")
            or payload.get("items")
            or []
        )
    else:
        raw_messages = []

    normalized_messages: list[dict[str, Any]] = []

    for raw_message in raw_messages:
        if isinstance(raw_message, dict):
            normalized_messages.append(
                raw_message
            )
            continue

        role = getattr(
            raw_message,
            "role",
            "assistant",
        )

        content = (
            getattr(raw_message, "content", None)
            or getattr(raw_message, "message", None)
            or getattr(raw_message, "text", None)
            or ""
        )

        metadata = getattr(
            raw_message,
            "metadata",
            {},
        )

        normalized_messages.append(
            {
                "role": (
                    getattr(role, "value", role)
                ),
                "content": content,
                "metadata": metadata,
            }
        )

    return normalized_messages
