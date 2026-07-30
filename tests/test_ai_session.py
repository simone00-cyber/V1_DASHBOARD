from __future__ import annotations

from typing import Any

import pytest

from core.ai.ai_session import AIStrategySession
from core.ai.context_builder import AIContext
from core.ai.conversation_state import ConversationState


class FakePromptProvider:
    def __init__(self) -> None:
        self.received_context: AIContext | None = None

    def build_prompt(self, context: AIContext) -> str:
        self.received_context = context
        return "TEST PROMPT"


class FakeLLMClient:
    def __init__(
        self,
        response: dict[str, Any],
    ) -> None:
        self.response = response
        self.received_prompt: str | None = None

    def generate_json(
        self,
        prompt: str,
    ) -> dict[str, Any]:
        self.received_prompt = prompt
        return self.response


def ticker_update_response() -> dict[str, Any]:
    return {
        "protocol_version": "1.0",
        "response_type": "strategy_update",
        "message": "AAPL was added to the research project.",
        "tone": "success",
        "next_state": "asking_goal",
        "question": None,
        "options": [],
        "operations": [
            {
                "operation": "set",
                "path": "/instrument/ticker",
                "value": "AAPL",
                "reason": "The user selected AAPL.",
            }
        ],
        "validation_messages": [],
        "requires_user_input": False,
        "requires_approval": False,
        "strategy_changed": True,
        "metadata": {},
    }


def clarification_response() -> dict[str, Any]:
    return {
        "protocol_version": "1.0",
        "response_type": "clarification",
        "message": "The requested setup is ambiguous.",
        "tone": "informative",
        "next_state": "asking_ticker",
        "question": "Which ticker would you like to test?",
        "options": [],
        "operations": [],
        "validation_messages": [],
        "requires_user_input": True,
        "requires_approval": False,
        "strategy_changed": False,
        "metadata": {},
    }


def build_complete_session() -> AIStrategySession:
    session = AIStrategySession(
        prompt_provider=FakePromptProvider(),
        llm_client=FakeLLMClient(
            clarification_response()
        ),
    )

    session.project.set_ticker("AAPL")

    session.project.strategy["instrument"][
        "start_date"
    ] = "2015-01-01"
    session.project.strategy["instrument"][
        "end_date"
    ] = "2025-12-31"

    session.project.strategy["entry"]["long"] = [
        {
            "type": "condition",
            "left": {
                "kind": "price",
                "field": "close",
            },
            "operator": ">",
            "right": {
                "kind": "indicator",
                "name": "EMA",
                "parameters": {
                    "period": 200,
                },
            },
        }
    ]

    session.project.strategy["exit"]["long"] = [
        {
            "type": "condition",
            "left": {
                "kind": "indicator",
                "name": "RSI",
                "parameters": {
                    "period": 14,
                },
            },
            "operator": ">",
            "right": {
                "kind": "constant",
                "value": 70,
            },
        }
    ]

    session.project.strategy["risk"]["stop_loss"] = 5.0
    session.project.strategy["execution"][
        "commission_value"
    ] = 0.1
    session.project.strategy["execution"][
        "slippage_value"
    ] = 0.05

    session.state_machine.transition_to(
        ConversationState.ASKING_TICKER
    )
    session.state_machine.transition_to(
        ConversationState.ASKING_GOAL
    )
    session.state_machine.transition_to(
        ConversationState.BUILDING_STRATEGY
    )
    session.state_machine.transition_to(
        ConversationState.VALIDATING
    )
    session.state_machine.transition_to(
        ConversationState.READY_FOR_REVIEW
    )

    return session


def test_session_rejects_empty_user_message() -> None:
    session = AIStrategySession(
        prompt_provider=FakePromptProvider(),
        llm_client=FakeLLMClient(
            clarification_response()
        ),
    )

    with pytest.raises(ValueError):
        session.process_user_message("   ")


def test_first_message_starts_ticker_flow() -> None:
    prompt_provider = FakePromptProvider()
    llm_client = FakeLLMClient(
        clarification_response()
    )

    session = AIStrategySession(
        prompt_provider=prompt_provider,
        llm_client=llm_client,
    )

    result = session.process_user_message(
        "I want to create a strategy."
    )

    assert result.success is True
    assert session.state == ConversationState.ASKING_TICKER
    assert (
        prompt_provider.received_context
        is not None
    )
    assert (
        prompt_provider.received_context.conversation_state
        == "asking_ticker"
    )
    assert llm_client.received_prompt == "TEST PROMPT"


def test_strategy_update_is_applied() -> None:
    session = AIStrategySession(
        prompt_provider=FakePromptProvider(),
        llm_client=FakeLLMClient(
            ticker_update_response()
        ),
    )

    result = session.process_user_message("AAPL")

    assert result.success is True
    assert session.project.ticker == "AAPL"
    assert session.state == ConversationState.ASKING_GOAL
    assert result.parse_result is not None
    assert result.parse_result.strategy_changed is True


def test_messages_are_added_to_conversation() -> None:
    session = AIStrategySession(
        prompt_provider=FakePromptProvider(),
        llm_client=FakeLLMClient(
            ticker_update_response()
        ),
    )

    session.process_user_message("AAPL")

    assert session.project.conversation.message_count() == 2
    assert (
        session.project.conversation.last_message("user").content
        == "AAPL"
    )
    assert (
        session.project.conversation.last_message(
            "assistant"
        ).content
        == "AAPL was added to the research project."
    )


def test_invalid_llm_payload_returns_failure() -> None:
    session = AIStrategySession(
        prompt_provider=FakePromptProvider(),
        llm_client=FakeLLMClient(
            {
                "response_type": "unsupported",
            }
        ),
    )

    result = session.process_user_message("AAPL")

    assert result.success is False
    assert result.error is not None
    assert session.state == ConversationState.ERROR


def test_parser_failure_does_not_modify_strategy() -> None:
    response = ticker_update_response()

    response["operations"] = [
        {
            "operation": "set",
            "path": "/schema_version",
            "value": "2.0",
        }
    ]

    session = AIStrategySession(
        prompt_provider=FakePromptProvider(),
        llm_client=FakeLLMClient(response),
    )

    result = session.process_user_message("Change schema.")

    assert result.success is False
    assert (
        session.project.strategy["schema_version"]
        == "1.0"
    )
    assert session.state == ConversationState.ERROR


def test_complete_strategy_can_be_approved() -> None:
    session = build_complete_session()

    result = session.approve_strategy()

    assert result.success is True
    assert session.project.is_approved is True
    assert session.state == ConversationState.APPROVED


def test_incomplete_strategy_cannot_be_approved() -> None:
    session = AIStrategySession(
        prompt_provider=FakePromptProvider(),
        llm_client=FakeLLMClient(
            clarification_response()
        ),
    )

    with pytest.raises(ValueError):
        session.approve_strategy()


def test_message_reopens_approved_strategy() -> None:
    session = build_complete_session()
    session.approve_strategy()

    session.llm_client = FakeLLMClient(
        {
            "protocol_version": "1.0",
            "response_type": "information",
            "message": "The strategy was reopened.",
            "tone": "informative",
            "next_state": "building_strategy",
            "question": None,
            "options": [],
            "operations": [],
            "validation_messages": [],
            "requires_user_input": False,
            "requires_approval": False,
            "strategy_changed": False,
            "metadata": {},
        }
    )

    result = session.process_user_message(
        "I want to change the strategy."
    )

    assert result.success is True
    assert session.project.is_approved is False
    assert session.state in {
        ConversationState.BUILDING_STRATEGY,
        ConversationState.READY_FOR_REVIEW,
    }


def test_revoke_approval() -> None:
    session = build_complete_session()
    session.approve_strategy()

    result = session.revoke_approval()

    assert result.success is True
    assert session.project.is_approved is False
    assert (
        session.state
        == ConversationState.BUILDING_STRATEGY
    )


def test_start_new_project_replaces_current_project() -> None:
    session = AIStrategySession(
        prompt_provider=FakePromptProvider(),
        llm_client=FakeLLMClient(
            clarification_response()
        ),
    )

    old_id = session.project.id

    new_project = session.start_new_project(
        name="New Research",
        description="A new research hypothesis.",
    )

    assert new_project.id != old_id
    assert new_project.name == "New Research"
    assert session.state == ConversationState.NEW


def test_reset_creates_empty_project() -> None:
    session = AIStrategySession(
        prompt_provider=FakePromptProvider(),
        llm_client=FakeLLMClient(
            ticker_update_response()
        ),
    )

    session.process_user_message("AAPL")
    session.reset()

    assert session.project.ticker == ""
    assert session.project.conversation.is_empty()
    assert session.state == ConversationState.NEW


def test_export_and_restore_round_trip() -> None:
    prompt_provider = FakePromptProvider()
    llm_client = FakeLLMClient(
        ticker_update_response()
    )

    session = AIStrategySession(
        prompt_provider=prompt_provider,
        llm_client=llm_client,
    )

    session.process_user_message("AAPL")

    payload = session.export_project()

    restored = AIStrategySession.restore(
        payload=payload,
        prompt_provider=prompt_provider,
        llm_client=llm_client,
    )

    assert restored.project.id == session.project.id
    assert restored.project.ticker == "AAPL"
    assert restored.state == session.state
    assert (
        restored.project.conversation.message_count()
        == 2
    )


def test_session_result_serialization() -> None:
    session = AIStrategySession(
        prompt_provider=FakePromptProvider(),
        llm_client=FakeLLMClient(
            ticker_update_response()
        ),
    )

    result = session.process_user_message("AAPL")
    payload = result.to_dict()

    assert payload["success"] is True
    assert payload["state"] == "asking_goal"
    assert (
        payload["project"]["strategy"]["instrument"][
            "ticker"
        ]
        == "AAPL"
    )