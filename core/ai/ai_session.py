from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from core.ai.context_builder import AIContext, ContextBuilder
from core.ai.conversation_state import (
    ConversationState,
    ConversationStateMachine,
)
from core.ai.llm_protocol import (
    LLMResponse,
    LLMResponseType,
)
from core.ai.research_project import ResearchProject
from core.ai.strategy_parser import (
    StrategyParseResult,
    StrategyParser,
)
from core.ai.strategy_validator import (
    StrategyHealth,
    StrategyValidator,
)


class PromptProvider(Protocol):
    """
    Contract that the future PromptManager must implement.
    """

    def build_prompt(self, context: AIContext) -> str:
        ...


class LLMClient(Protocol):
    """
    Contract that GeminiClient or another LLM provider must implement.
    """

    def generate_json(self, prompt: str) -> dict[str, Any]:
        ...


@dataclass
class AISessionResult:
    success: bool
    response: LLMResponse | None
    project: ResearchProject
    health: StrategyHealth
    state: ConversationState
    parse_result: StrategyParseResult | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "response": (
                self.response.to_dict()
                if self.response is not None
                else None
            ),
            "project": self.project.to_dict(),
            "health": self.health.to_dict(),
            "state": self.state.value,
            "parse_result": (
                self.parse_result.to_dict()
                if self.parse_result is not None
                else None
            ),
            "error": self.error,
        }


class AIStrategySession:
    """
    Coordinates one AI-assisted quantitative research session.

    This class is the only entry point that the future Streamlit page
    should use. The UI must not call Gemini, the parser or the validator
    directly.
    """

    def __init__(
        self,
        prompt_provider: PromptProvider,
        llm_client: LLMClient,
        project: ResearchProject | None = None,
        state_machine: ConversationStateMachine | None = None,
        context_builder: ContextBuilder | None = None,
        parser: StrategyParser | None = None,
        validator: StrategyValidator | None = None,
    ) -> None:
        self.prompt_provider = prompt_provider
        self.llm_client = llm_client

        self.project = project or ResearchProject()
        self.state_machine = (
            state_machine or ConversationStateMachine()
        )

        self.validator = validator or StrategyValidator()
        self.context_builder = context_builder or ContextBuilder(
            validator=self.validator
        )
        self.parser = parser or StrategyParser()

    @property
    def state(self) -> ConversationState:
        return self.state_machine.state

    @property
    def health(self) -> StrategyHealth:
        return self.validator.validate(self.project)

    def start_new_project(
        self,
        name: str = "Untitled Research Project",
        description: str = "",
    ) -> ResearchProject:
        self.project = ResearchProject(
            name=name,
            description=description,
        )
        self.state_machine = ConversationStateMachine()

        return self.project

    def process_user_message(
        self,
        user_message: str,
    ) -> AISessionResult:
        normalized_message = user_message.strip()

        if not normalized_message:
            raise ValueError("User message cannot be empty.")

        self._prepare_session_for_message()

        self.project.conversation.add_user_message(
            normalized_message
        )

        try:
            context = self.context_builder.build(
                project=self.project,
                state_machine=self.state_machine,
                user_message=normalized_message,
            )

            prompt = self.prompt_provider.build_prompt(context)

            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError(
                    "The prompt provider returned an empty prompt."
                )

            raw_response = self.llm_client.generate_json(prompt)

            if not isinstance(raw_response, dict):
                raise TypeError(
                    "The LLM client must return a dictionary."
                )

            response = LLMResponse.from_dict(raw_response)

            parse_result = self.parser.apply_response(
                project=self.project,
                response=response,
            )

            if not parse_result.success:
                return self._build_failure_result(
                    error=(
                        parse_result.errors[0]
                        if parse_result.errors
                        else "The strategy update could not be applied."
                    ),
                    response=response,
                    parse_result=parse_result,
                )

            health = self.validator.apply_project_status(
                self.project
            )

            target_state = self._resolve_target_state(
                response=response,
                health=health,
            )

            self._transition_to(
                target_state,
                reason=(
                    "AI response processed successfully."
                ),
            )

            self.project.conversation.add_assistant_message(
                response.message,
                metadata={
                    "response_type": response.response_type.value,
                    "next_state": self.state.value,
                    "protocol_version": response.protocol_version,
                    "strategy_changed": response.strategy_changed,
                    "requires_user_input": (
                        response.requires_user_input
                    ),
                    "requires_approval": (
                        response.requires_approval
                    ),
                },
            )

            return AISessionResult(
                success=True,
                response=response,
                project=self.project,
                health=health,
                state=self.state,
                parse_result=parse_result,
            )

        except Exception as exc:
            return self._build_failure_result(
                error=str(exc),
            )

    def approve_strategy(self) -> AISessionResult:
        health = self.validator.validate(self.project)

        if not health.can_be_approved:
            raise ValueError(
                "The strategy cannot be approved because it is "
                "incomplete or contains validation errors."
            )

        if self.state != ConversationState.READY_FOR_REVIEW:
            self._transition_to(
                ConversationState.READY_FOR_REVIEW,
                reason="Strategy passed deterministic validation.",
            )

        self.project.approve_strategy()

        self._transition_to(
            ConversationState.APPROVED,
            reason="The user explicitly approved the strategy.",
        )

        response = LLMResponse(
            response_type=LLMResponseType.INFORMATION,
            message="The strategy has been approved.",
            tone="success",
            next_state=ConversationState.APPROVED,
        )

        self.project.conversation.add_assistant_message(
            response.message,
            metadata={
                "response_type": response.response_type.value,
                "next_state": self.state.value,
                "user_approved": True,
            },
        )

        return AISessionResult(
            success=True,
            response=response,
            project=self.project,
            health=health,
            state=self.state,
        )

    def revoke_approval(self) -> AISessionResult:
        if self.project.is_approved:
            self.project.revoke_approval()

        if self.state == ConversationState.APPROVED:
            self._transition_to(
                ConversationState.BUILDING_STRATEGY,
                reason="The user revoked strategy approval.",
            )

        health = self.validator.validate(self.project)

        return AISessionResult(
            success=True,
            response=None,
            project=self.project,
            health=health,
            state=self.state,
        )

    def reset(self) -> None:
        self.start_new_project()

    def export_project(self) -> dict[str, Any]:
        return {
            "session_version": "1.0",
            "project": self.project.to_dict(),
            "state_machine": self.state_machine.to_dict(),
            "health": self.health.to_dict(),
        }

    @classmethod
    def restore(
        cls,
        payload: dict[str, Any],
        prompt_provider: PromptProvider,
        llm_client: LLMClient,
        context_builder: ContextBuilder | None = None,
        parser: StrategyParser | None = None,
        validator: StrategyValidator | None = None,
    ) -> "AIStrategySession":
        raw_project = payload.get("project")
        raw_state_machine = payload.get("state_machine")

        if not isinstance(raw_project, dict):
            raise ValueError(
                "The session payload must contain a project dictionary."
            )

        if not isinstance(raw_state_machine, dict):
            raise ValueError(
                "The session payload must contain a state machine "
                "dictionary."
            )

        project = ResearchProject.from_dict(raw_project)
        state_machine = ConversationStateMachine.from_dict(
            raw_state_machine
        )

        return cls(
            prompt_provider=prompt_provider,
            llm_client=llm_client,
            project=project,
            state_machine=state_machine,
            context_builder=context_builder,
            parser=parser,
            validator=validator,
        )

    def _prepare_session_for_message(self) -> None:
        if self.state == ConversationState.NEW:
            self._transition_to(
                ConversationState.ASKING_TICKER,
                reason="A new strategy design session was started.",
            )

        if self.state == ConversationState.APPROVED:
            self.project.revoke_approval()
            self._transition_to(
                ConversationState.BUILDING_STRATEGY,
                reason=(
                    "A new user message reopened the approved "
                    "strategy for editing."
                ),
            )

        if self.state == ConversationState.COMPLETED:
            self._transition_to(
                ConversationState.BUILDING_STRATEGY,
                reason=(
                    "The user resumed work on a completed "
                    "research project."
                ),
            )

    def _resolve_target_state(
        self,
        response: LLMResponse,
        health: StrategyHealth,
    ) -> ConversationState:
        if health.is_ready_for_review:
            if not response.requires_user_input:
                return ConversationState.READY_FOR_REVIEW

        if (
            response.next_state
            == ConversationState.READY_FOR_REVIEW
            and not health.is_ready_for_review
        ):
            return ConversationState.BUILDING_STRATEGY

        if (
            response.next_state == ConversationState.APPROVED
            and not self.project.is_approved
        ):
            return ConversationState.READY_FOR_REVIEW

        return response.next_state

    def _transition_to(
        self,
        target_state: ConversationState,
        reason: str,
    ) -> None:
        if target_state == self.state:
            self.state_machine.transition_to(
                target_state,
                reason=reason,
            )
            return

        if self.state_machine.can_transition_to(target_state):
            self.state_machine.transition_to(
                target_state,
                reason=reason,
            )
            return

        if (
            target_state == ConversationState.READY_FOR_REVIEW
            and self.state == ConversationState.BUILDING_STRATEGY
        ):
            self.state_machine.transition_to(
                ConversationState.VALIDATING,
                reason="Running deterministic strategy validation.",
            )
            self.state_machine.transition_to(
                ConversationState.READY_FOR_REVIEW,
                reason=reason,
            )
            return

        if (
            target_state == ConversationState.READY_FOR_REVIEW
            and self.state == ConversationState.ASKING_GOAL
        ):
            self.state_machine.transition_to(
                ConversationState.BUILDING_STRATEGY,
                reason="The strategy definition was created.",
            )
            self.state_machine.transition_to(
                ConversationState.VALIDATING,
                reason="Running deterministic strategy validation.",
            )
            self.state_machine.transition_to(
                ConversationState.READY_FOR_REVIEW,
                reason=reason,
            )
            return

        raise ValueError(
            "The requested AI session transition is invalid: "
            f"{self.state.value!r} -> {target_state.value!r}."
        )

    def _build_failure_result(
        self,
        error: str,
        response: LLMResponse | None = None,
        parse_result: StrategyParseResult | None = None,
    ) -> AISessionResult:
        normalized_error = error.strip() or "Unknown AI session error."

        if self.state_machine.can_transition_to(
            ConversationState.ERROR
        ):
            self.state_machine.transition_to(
                ConversationState.ERROR,
                reason=normalized_error,
            )

        self.project.conversation.add_assistant_message(
            "The request could not be processed safely.",
            metadata={
                "response_type": LLMResponseType.ERROR.value,
                "error": normalized_error,
            },
        )

        return AISessionResult(
            success=False,
            response=response,
            project=self.project,
            health=self.validator.validate(self.project),
            state=self.state,
            parse_result=parse_result,
            error=normalized_error,
        )