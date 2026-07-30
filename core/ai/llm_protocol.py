from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal, TypeAlias

from core.ai.conversation_state import ConversationState


class LLMResponseType(str, Enum):
    QUESTION = "question"
    CLARIFICATION = "clarification"
    STRATEGY_UPDATE = "strategy_update"
    VALIDATION = "validation"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVAL_REQUIRED = "approval_required"
    INFORMATION = "information"
    ERROR = "error"


class StrategyOperationType(str, Enum):
    SET = "set"
    REPLACE = "replace"
    APPEND = "append"
    REMOVE = "remove"
    CLEAR = "clear"


MessageTone = Literal[
    "neutral",
    "informative",
    "warning",
    "success",
]

OptionValue: TypeAlias = str | int | float | bool | None


@dataclass(slots=True)
class ResponseOption:
    label: str
    value: OptionValue
    description: str | None = None
    recommended: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.label = self.label.strip()

        if not self.label:
            raise ValueError("Response option label cannot be empty.")

        if self.description is not None:
            self.description = self.description.strip() or None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResponseOption":
        metadata = data.get("metadata", {})

        if not isinstance(metadata, dict):
            metadata = {}

        return cls(
            label=str(data.get("label", "")),
            value=data.get("value"),
            description=(
                str(data["description"])
                if data.get("description") is not None
                else None
            ),
            recommended=bool(data.get("recommended", False)),
            metadata=metadata,
        )


@dataclass(slots=True)
class StrategyOperation:
    operation: StrategyOperationType
    path: str
    value: Any = None
    reason: str | None = None

    def __post_init__(self) -> None:
        self.path = self.path.strip()

        if not self.path:
            raise ValueError("Strategy operation path cannot be empty.")

        if not self.path.startswith("/"):
            raise ValueError(
                "Strategy operation path must use JSON Pointer syntax "
                "and start with '/'."
            )

        if self.reason is not None:
            self.reason = self.reason.strip() or None

        if (
            self.operation
            in {
                StrategyOperationType.SET,
                StrategyOperationType.REPLACE,
                StrategyOperationType.APPEND,
            }
            and self.value is None
        ):
            raise ValueError(
                f"Operation {self.operation.value!r} requires a value."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation.value,
            "path": self.path,
            "value": self.value,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StrategyOperation":
        raw_operation = str(data.get("operation", "")).strip()

        try:
            operation = StrategyOperationType(raw_operation)
        except ValueError as exc:
            raise ValueError(
                f"Unsupported strategy operation: {raw_operation!r}"
            ) from exc

        return cls(
            operation=operation,
            path=str(data.get("path", "")),
            value=data.get("value"),
            reason=(
                str(data["reason"])
                if data.get("reason") is not None
                else None
            ),
        )


@dataclass(slots=True)
class ValidationMessage:
    code: str
    message: str
    severity: Literal["error", "warning", "info"]
    section: str | None = None
    field: str | None = None

    def __post_init__(self) -> None:
        self.code = self.code.strip()
        self.message = self.message.strip()

        if not self.code:
            raise ValueError("Validation message code cannot be empty.")

        if not self.message:
            raise ValueError("Validation message text cannot be empty.")

        if self.severity not in {"error", "warning", "info"}:
            raise ValueError(
                f"Unsupported validation severity: {self.severity!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationMessage":
        return cls(
            code=str(data.get("code", "")),
            message=str(data.get("message", "")),
            severity=str(data.get("severity", "")),  # type: ignore[arg-type]
            section=(
                str(data["section"])
                if data.get("section") is not None
                else None
            ),
            field=(
                str(data["field"])
                if data.get("field") is not None
                else None
            ),
        )


@dataclass
class LLMResponse:
    response_type: LLMResponseType
    message: str
    next_state: ConversationState
    tone: MessageTone = "neutral"

    question: str | None = None
    options: list[ResponseOption] = field(default_factory=list)
    operations: list[StrategyOperation] = field(default_factory=list)
    validation_messages: list[ValidationMessage] = field(default_factory=list)

    requires_user_input: bool = False
    requires_approval: bool = False
    strategy_changed: bool = False

    metadata: dict[str, Any] = field(default_factory=dict)
    protocol_version: str = "1.0"

    def __post_init__(self) -> None:
        self.message = self.message.strip()

        if not self.message:
            raise ValueError("LLM response message cannot be empty.")

        if self.question is not None:
            self.question = self.question.strip() or None

        if self.tone not in {
            "neutral",
            "informative",
            "warning",
            "success",
        }:
            raise ValueError(f"Unsupported response tone: {self.tone!r}")

        self._validate_semantics()

    @property
    def has_operations(self) -> bool:
        return bool(self.operations)

    @property
    def has_errors(self) -> bool:
        return any(
            item.severity == "error"
            for item in self.validation_messages
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "response_type": self.response_type.value,
            "message": self.message,
            "tone": self.tone,
            "next_state": self.next_state.value,
            "question": self.question,
            "options": [
                option.to_dict()
                for option in self.options
            ],
            "operations": [
                operation.to_dict()
                for operation in self.operations
            ],
            "validation_messages": [
                item.to_dict()
                for item in self.validation_messages
            ],
            "requires_user_input": self.requires_user_input,
            "requires_approval": self.requires_approval,
            "strategy_changed": self.strategy_changed,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLMResponse":
        raw_response_type = str(
            data.get("response_type", "")
        ).strip()

        raw_next_state = str(
            data.get("next_state", "")
        ).strip()

        try:
            response_type = LLMResponseType(raw_response_type)
        except ValueError as exc:
            raise ValueError(
                f"Unsupported LLM response type: {raw_response_type!r}"
            ) from exc

        try:
            next_state = ConversationState(raw_next_state)
        except ValueError as exc:
            raise ValueError(
                f"Unsupported next conversation state: {raw_next_state!r}"
            ) from exc

        raw_options = data.get("options", [])
        raw_operations = data.get("operations", [])
        raw_validation_messages = data.get(
            "validation_messages",
            [],
        )
        metadata = data.get("metadata", {})

        if not isinstance(raw_options, list):
            raise ValueError("LLM response options must be a list.")

        if not isinstance(raw_operations, list):
            raise ValueError("LLM response operations must be a list.")

        if not isinstance(raw_validation_messages, list):
            raise ValueError(
                "LLM validation messages must be a list."
            )

        if not isinstance(metadata, dict):
            metadata = {}

        return cls(
            protocol_version=str(
                data.get("protocol_version", "1.0")
            ),
            response_type=response_type,
            message=str(data.get("message", "")),
            tone=str(data.get("tone", "neutral")),  # type: ignore[arg-type]
            next_state=next_state,
            question=(
                str(data["question"])
                if data.get("question") is not None
                else None
            ),
            options=[
                ResponseOption.from_dict(item)
                for item in raw_options
                if isinstance(item, dict)
            ],
            operations=[
                StrategyOperation.from_dict(item)
                for item in raw_operations
                if isinstance(item, dict)
            ],
            validation_messages=[
                ValidationMessage.from_dict(item)
                for item in raw_validation_messages
                if isinstance(item, dict)
            ],
            requires_user_input=bool(
                data.get("requires_user_input", False)
            ),
            requires_approval=bool(
                data.get("requires_approval", False)
            ),
            strategy_changed=bool(
                data.get("strategy_changed", False)
            ),
            metadata=metadata,
        )

    def _validate_semantics(self) -> None:
        if self.response_type in {
            LLMResponseType.QUESTION,
            LLMResponseType.CLARIFICATION,
        }:
            if not self.question:
                raise ValueError(
                    "Question and clarification responses require "
                    "a question."
                )

            if not self.requires_user_input:
                raise ValueError(
                    "Question and clarification responses must require "
                    "user input."
                )

        if self.options and not self.question:
            raise ValueError(
                "Options cannot be provided without a question."
            )

        if self.strategy_changed and not self.operations:
            raise ValueError(
                "A response marked as strategy_changed must contain "
                "at least one strategy operation."
            )

        if self.operations and not self.strategy_changed:
            raise ValueError(
                "Responses containing strategy operations must set "
                "strategy_changed=True."
            )

        if (
            self.response_type
            == LLMResponseType.APPROVAL_REQUIRED
            and not self.requires_approval
        ):
            raise ValueError(
                "Approval-required responses must set "
                "requires_approval=True."
            )

        if (
            self.response_type
            == LLMResponseType.READY_FOR_REVIEW
            and self.next_state
            != ConversationState.READY_FOR_REVIEW
        ):
            raise ValueError(
                "A ready-for-review response must transition to "
                "READY_FOR_REVIEW."
            )

        if (
            self.response_type == LLMResponseType.ERROR
            and self.tone != "warning"
        ):
            raise ValueError(
                "Error responses must use the warning tone."
            )