from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.ai.conversation import ConversationMessage
from core.ai.conversation_state import ConversationStateMachine
from core.ai.research_project import ResearchProject
from core.ai.strategy_validator import StrategyHealth, StrategyValidator


@dataclass(slots=True)
class ContextBuilderConfig:
    max_history_messages: int = 8
    include_system_messages: bool = False
    include_validation_issues: bool = True
    include_project_metadata: bool = True

    def __post_init__(self) -> None:
        if self.max_history_messages < 0:
            raise ValueError(
                "max_history_messages cannot be negative."
            )


@dataclass
class AIContext:
    protocol_version: str
    conversation_state: str
    project: dict[str, Any]
    strategy: dict[str, Any]
    validation: dict[str, Any]
    conversation_history: list[dict[str, Any]]
    user_message: str
    instructions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "conversation_state": self.conversation_state,
            "project": self.project,
            "strategy": self.strategy,
            "validation": self.validation,
            "conversation_history": self.conversation_history,
            "user_message": self.user_message,
            "instructions": self.instructions,
        }


class ContextBuilder:
    """
    Builds the controlled context sent to an LLM.

    The builder is the only component responsible for reading the complete
    ResearchProject and reducing it to the information required by the model.
    """

    def __init__(
        self,
        validator: StrategyValidator | None = None,
        config: ContextBuilderConfig | None = None,
    ) -> None:
        self.validator = validator or StrategyValidator()
        self.config = config or ContextBuilderConfig()

    def build(
        self,
        project: ResearchProject,
        state_machine: ConversationStateMachine,
        user_message: str,
    ) -> AIContext:
        normalized_message = user_message.strip()

        if not normalized_message:
            raise ValueError("User message cannot be empty.")

        health = self.validator.validate(project)

        return AIContext(
            protocol_version="1.0",
            conversation_state=state_machine.state.value,
            project=self._build_project_context(project),
            strategy=self._build_strategy_context(project),
            validation=self._build_validation_context(health),
            conversation_history=self._build_history_context(project),
            user_message=normalized_message,
            instructions=self._build_runtime_instructions(),
        )

    def _build_project_context(
        self,
        project: ResearchProject,
    ) -> dict[str, Any]:
        if not self.config.include_project_metadata:
            return {
                "id": project.id,
            }

        return {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "ticker": project.ticker,
            "timeframe": project.timeframe,
            "strategy_version": project.strategy_version,
            "approved_strategy_version": (
                project.approved_strategy_version
            ),
            "is_approved": project.is_approved,
        }

    @staticmethod
    def _build_strategy_context(
        project: ResearchProject,
    ) -> dict[str, Any]:
        return project.to_dict()["strategy"]

    def _build_validation_context(
        self,
        health: StrategyHealth,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "completion_score": health.completion_score,
            "is_valid": health.is_valid,
            "is_ready_for_review": health.is_ready_for_review,
            "can_be_approved": health.can_be_approved,
            "error_count": health.error_count,
            "warning_count": health.warning_count,
        }

        if self.config.include_validation_issues:
            payload["issues"] = [
                issue.to_dict()
                for issue in health.issues
            ]
        else:
            payload["issues"] = []

        return payload

    def _build_history_context(
        self,
        project: ResearchProject,
    ) -> list[dict[str, Any]]:
        messages = project.conversation.messages

        if not self.config.include_system_messages:
            messages = [
                message
                for message in messages
                if message.role != "system"
            ]

        if self.config.max_history_messages == 0:
            selected_messages: list[ConversationMessage] = []
        else:
            selected_messages = messages[
                -self.config.max_history_messages:
            ]

        return [
            {
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at,
                "metadata": message.metadata,
            }
            for message in selected_messages
        ]

    @staticmethod
    def _build_runtime_instructions() -> dict[str, Any]:
        return {
            "response_format": "llm_protocol_json",
            "natural_language_output_allowed": False,
            "strategy_updates_must_use_operations": True,
            "must_request_clarification_when_ambiguous": True,
            "must_not_execute_backtest": True,
            "must_not_assume_missing_parameters": True,
            "must_not_modify_protected_paths": [
                "/schema_version",
            ],
        }