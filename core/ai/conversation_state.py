from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ConversationState(str, Enum):
    NEW = "new"
    ASKING_TICKER = "asking_ticker"
    ASKING_GOAL = "asking_goal"
    BUILDING_STRATEGY = "building_strategy"
    VALIDATING = "validating"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    BACKTEST_RUNNING = "backtest_running"
    COMPLETED = "completed"
    ERROR = "error"


ALLOWED_TRANSITIONS: dict[ConversationState, set[ConversationState]] = {
    ConversationState.NEW: {
        ConversationState.ASKING_TICKER,
        ConversationState.ERROR,
    },
    ConversationState.ASKING_TICKER: {
        ConversationState.ASKING_GOAL,
        ConversationState.ERROR,
    },
    ConversationState.ASKING_GOAL: {
        ConversationState.BUILDING_STRATEGY,
        ConversationState.ERROR,
    },
    ConversationState.BUILDING_STRATEGY: {
        ConversationState.VALIDATING,
        ConversationState.ASKING_GOAL,
        ConversationState.ERROR,
    },
    ConversationState.VALIDATING: {
        ConversationState.BUILDING_STRATEGY,
        ConversationState.READY_FOR_REVIEW,
        ConversationState.ERROR,
    },
    ConversationState.READY_FOR_REVIEW: {
        ConversationState.BUILDING_STRATEGY,
        ConversationState.APPROVED,
        ConversationState.ERROR,
    },
    ConversationState.APPROVED: {
        ConversationState.BUILDING_STRATEGY,
        ConversationState.BACKTEST_RUNNING,
        ConversationState.ERROR,
    },
    ConversationState.BACKTEST_RUNNING: {
        ConversationState.COMPLETED,
        ConversationState.ERROR,
    },
    ConversationState.COMPLETED: {
        ConversationState.BUILDING_STRATEGY,
        ConversationState.BACKTEST_RUNNING,
        ConversationState.ERROR,
    },
    ConversationState.ERROR: {
        ConversationState.NEW,
        ConversationState.ASKING_TICKER,
        ConversationState.BUILDING_STRATEGY,
    },
}


@dataclass(slots=True)
class StateTransition:
    previous_state: ConversationState
    new_state: ConversationState
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous_state": self.previous_state.value,
            "new_state": self.new_state.value,
            "reason": self.reason,
        }


class ConversationStateMachine:
    def __init__(
        self,
        initial_state: ConversationState = ConversationState.NEW,
    ) -> None:
        self._state = initial_state
        self._history: list[StateTransition] = []

    @property
    def state(self) -> ConversationState:
        return self._state

    @property
    def history(self) -> list[StateTransition]:
        return list(self._history)

    def can_transition_to(
        self,
        new_state: ConversationState,
    ) -> bool:
        if new_state == self._state:
            return True

        return new_state in ALLOWED_TRANSITIONS[self._state]

    def transition_to(
        self,
        new_state: ConversationState,
        reason: str | None = None,
    ) -> StateTransition:
        if not self.can_transition_to(new_state):
            raise ValueError(
                "Invalid conversation state transition: "
                f"{self._state.value!r} -> {new_state.value!r}"
            )

        transition = StateTransition(
            previous_state=self._state,
            new_state=new_state,
            reason=reason,
        )

        self._state = new_state
        self._history.append(transition)

        return transition

    def reset(self) -> None:
        self._state = ConversationState.NEW
        self._history.clear()

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self._state.value,
            "history": [
                transition.to_dict()
                for transition in self._history
            ],
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "ConversationStateMachine":
        raw_state = str(
            data.get("state", ConversationState.NEW.value)
        )

        try:
            state = ConversationState(raw_state)
        except ValueError as exc:
            raise ValueError(
                f"Unsupported conversation state: {raw_state!r}"
            ) from exc

        machine = cls(initial_state=state)

        raw_history = data.get("history", [])

        if not isinstance(raw_history, list):
            raise ValueError("Conversation state history must be a list.")

        restored_history: list[StateTransition] = []

        for item in raw_history:
            if not isinstance(item, dict):
                continue

            try:
                previous_state = ConversationState(
                    str(item.get("previous_state"))
                )
                new_state = ConversationState(
                    str(item.get("new_state"))
                )
            except ValueError as exc:
                raise ValueError(
                    "Invalid state transition in serialized history."
                ) from exc

            restored_history.append(
                StateTransition(
                    previous_state=previous_state,
                    new_state=new_state,
                    reason=(
                        str(item["reason"])
                        if item.get("reason") is not None
                        else None
                    ),
                )
            )

        machine._history = restored_history
        return machine