import pytest

from core.ai.context_builder import (
    AIContext,
    ContextBuilder,
    ContextBuilderConfig,
)
from core.ai.conversation_state import (
    ConversationState,
    ConversationStateMachine,
)
from core.ai.research_project import ResearchProject


def build_project() -> ResearchProject:
    project = ResearchProject(
        name="AAPL Trend Research",
        description="Research on a trend-following strategy.",
    )

    project.set_ticker("AAPL")
    project.strategy["instrument"]["start_date"] = "2015-01-01"
    project.strategy["instrument"]["end_date"] = "2025-12-31"

    project.strategy["entry"]["long"] = [
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

    project.strategy["exit"]["long"] = [
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

    project.strategy["risk"]["stop_loss"] = 5.0
    project.strategy["execution"]["commission_value"] = 0.1
    project.strategy["execution"]["slippage_value"] = 0.05

    return project


def test_context_builder_rejects_empty_user_message() -> None:
    builder = ContextBuilder()
    project = ResearchProject()
    machine = ConversationStateMachine()

    with pytest.raises(ValueError):
        builder.build(
            project=project,
            state_machine=machine,
            user_message="   ",
        )


def test_context_contains_current_state() -> None:
    builder = ContextBuilder()
    project = ResearchProject()
    machine = ConversationStateMachine(
        initial_state=ConversationState.ASKING_TICKER
    )

    context = builder.build(
        project=project,
        state_machine=machine,
        user_message="AAPL",
    )

    assert context.conversation_state == "asking_ticker"


def test_context_contains_strategy() -> None:
    builder = ContextBuilder()
    project = build_project()
    machine = ConversationStateMachine(
        initial_state=ConversationState.BUILDING_STRATEGY
    )

    context = builder.build(
        project=project,
        state_machine=machine,
        user_message="Add an ATR trailing stop.",
    )

    assert context.strategy["instrument"]["ticker"] == "AAPL"
    assert context.strategy["entry"]["long"]
    assert context.strategy["exit"]["long"]


def test_context_contains_validation_health() -> None:
    builder = ContextBuilder()
    project = build_project()
    machine = ConversationStateMachine(
        initial_state=ConversationState.VALIDATING
    )

    context = builder.build(
        project=project,
        state_machine=machine,
        user_message="Validate the strategy.",
    )

    assert context.validation["completion_score"] == 100
    assert context.validation["is_valid"] is True
    assert context.validation["is_ready_for_review"] is True


def test_history_is_limited_to_latest_messages() -> None:
    config = ContextBuilderConfig(
        max_history_messages=2,
    )
    builder = ContextBuilder(config=config)

    project = ResearchProject()
    project.conversation.add_user_message("Message 1")
    project.conversation.add_assistant_message("Message 2")
    project.conversation.add_user_message("Message 3")

    machine = ConversationStateMachine()

    context = builder.build(
        project=project,
        state_machine=machine,
        user_message="Message 4",
    )

    assert len(context.conversation_history) == 2
    assert (
        context.conversation_history[0]["content"]
        == "Message 2"
    )
    assert (
        context.conversation_history[1]["content"]
        == "Message 3"
    )


def test_system_messages_are_excluded_by_default() -> None:
    builder = ContextBuilder()
    project = ResearchProject()

    project.conversation.add_system_message("System prompt")
    project.conversation.add_user_message("Create a strategy.")

    context = builder.build(
        project=project,
        state_machine=ConversationStateMachine(),
        user_message="Continue.",
    )

    roles = [
        message["role"]
        for message in context.conversation_history
    ]

    assert "system" not in roles
    assert roles == ["user"]


def test_system_messages_can_be_included() -> None:
    config = ContextBuilderConfig(
        include_system_messages=True,
    )
    builder = ContextBuilder(config=config)
    project = ResearchProject()

    project.conversation.add_system_message("System prompt")
    project.conversation.add_user_message("Create a strategy.")

    context = builder.build(
        project=project,
        state_machine=ConversationStateMachine(),
        user_message="Continue.",
    )

    roles = [
        message["role"]
        for message in context.conversation_history
    ]

    assert roles == ["system", "user"]


def test_zero_history_limit_returns_empty_history() -> None:
    config = ContextBuilderConfig(
        max_history_messages=0,
    )
    builder = ContextBuilder(config=config)
    project = ResearchProject()

    project.conversation.add_user_message("Message 1")

    context = builder.build(
        project=project,
        state_machine=ConversationStateMachine(),
        user_message="Message 2",
    )

    assert context.conversation_history == []


def test_validation_issues_can_be_excluded() -> None:
    config = ContextBuilderConfig(
        include_validation_issues=False,
    )
    builder = ContextBuilder(config=config)

    context = builder.build(
        project=ResearchProject(),
        state_machine=ConversationStateMachine(),
        user_message="Create a strategy.",
    )

    assert context.validation["issues"] == []
    assert context.validation["error_count"] >= 1


def test_project_metadata_can_be_minimized() -> None:
    config = ContextBuilderConfig(
        include_project_metadata=False,
    )
    builder = ContextBuilder(config=config)
    project = build_project()

    context = builder.build(
        project=project,
        state_machine=ConversationStateMachine(),
        user_message="Continue.",
    )

    assert context.project == {
        "id": project.id,
    }


def test_runtime_instructions_are_present() -> None:
    builder = ContextBuilder()

    context = builder.build(
        project=ResearchProject(),
        state_machine=ConversationStateMachine(),
        user_message="Create a strategy.",
    )

    assert (
        context.instructions["response_format"]
        == "llm_protocol_json"
    )
    assert (
        context.instructions["must_not_execute_backtest"]
        is True
    )
    assert (
        context.instructions[
            "must_request_clarification_when_ambiguous"
        ]
        is True
    )


def test_context_serialization() -> None:
    context = AIContext(
        protocol_version="1.0",
        conversation_state="new",
        project={"id": "project-1"},
        strategy={"instrument": {}},
        validation={"is_valid": False},
        conversation_history=[],
        user_message="Create a strategy.",
        instructions={"response_format": "json"},
    )

    payload = context.to_dict()

    assert payload["protocol_version"] == "1.0"
    assert payload["conversation_state"] == "new"
    assert payload["user_message"] == "Create a strategy."


def test_negative_history_limit_is_rejected() -> None:
    with pytest.raises(ValueError):
        ContextBuilderConfig(
            max_history_messages=-1
        )