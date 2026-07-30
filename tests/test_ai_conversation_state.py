import pytest

from core.ai.conversation_state import (
    ConversationState,
    ConversationStateMachine,
)


def test_default_state_is_new() -> None:
    machine = ConversationStateMachine()

    assert machine.state == ConversationState.NEW
    assert machine.history == []


def test_valid_transition_is_recorded() -> None:
    machine = ConversationStateMachine()

    transition = machine.transition_to(
        ConversationState.ASKING_TICKER,
        reason="A new research session was started.",
    )

    assert machine.state == ConversationState.ASKING_TICKER
    assert transition.previous_state == ConversationState.NEW
    assert transition.new_state == ConversationState.ASKING_TICKER
    assert transition.reason == "A new research session was started."
    assert len(machine.history) == 1


def test_same_state_transition_is_allowed() -> None:
    machine = ConversationStateMachine()

    machine.transition_to(ConversationState.NEW)

    assert machine.state == ConversationState.NEW
    assert len(machine.history) == 1


def test_invalid_transition_raises_error() -> None:
    machine = ConversationStateMachine()

    with pytest.raises(ValueError):
        machine.transition_to(
            ConversationState.BACKTEST_RUNNING
        )


def test_full_strategy_design_flow() -> None:
    machine = ConversationStateMachine()

    machine.transition_to(ConversationState.ASKING_TICKER)
    machine.transition_to(ConversationState.ASKING_GOAL)
    machine.transition_to(ConversationState.BUILDING_STRATEGY)
    machine.transition_to(ConversationState.VALIDATING)
    machine.transition_to(ConversationState.READY_FOR_REVIEW)
    machine.transition_to(ConversationState.APPROVED)
    machine.transition_to(ConversationState.BACKTEST_RUNNING)
    machine.transition_to(ConversationState.COMPLETED)

    assert machine.state == ConversationState.COMPLETED
    assert len(machine.history) == 8


def test_ready_for_review_can_return_to_building() -> None:
    machine = ConversationStateMachine(
        initial_state=ConversationState.READY_FOR_REVIEW
    )

    machine.transition_to(
        ConversationState.BUILDING_STRATEGY,
        reason="The user requested a strategy change.",
    )

    assert machine.state == ConversationState.BUILDING_STRATEGY


def test_reset_clears_state_and_history() -> None:
    machine = ConversationStateMachine()

    machine.transition_to(ConversationState.ASKING_TICKER)
    machine.transition_to(ConversationState.ASKING_GOAL)

    machine.reset()

    assert machine.state == ConversationState.NEW
    assert machine.history == []


def test_serialization_round_trip() -> None:
    machine = ConversationStateMachine()

    machine.transition_to(
        ConversationState.ASKING_TICKER,
        reason="Start",
    )
    machine.transition_to(
        ConversationState.ASKING_GOAL,
        reason="Ticker received",
    )

    restored = ConversationStateMachine.from_dict(
        machine.to_dict()
    )

    assert restored.state == ConversationState.ASKING_GOAL
    assert len(restored.history) == 2
    assert restored.history[0].reason == "Start"
    assert restored.history[1].reason == "Ticker received"


def test_invalid_serialized_state_raises_error() -> None:
    with pytest.raises(ValueError):
        ConversationStateMachine.from_dict(
            {
                "state": "unsupported_state",
                "history": [],
            }
        )