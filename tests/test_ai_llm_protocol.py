import pytest

from core.ai.conversation_state import ConversationState
from core.ai.llm_protocol import (
    LLMResponse,
    LLMResponseType,
    ResponseOption,
    StrategyOperation,
    StrategyOperationType,
    ValidationMessage,
)


def test_response_option_serialization() -> None:
    option = ResponseOption(
        label="EMA",
        value="ema",
        description="Exponential moving average",
        recommended=True,
    )

    restored = ResponseOption.from_dict(option.to_dict())

    assert restored.label == "EMA"
    assert restored.value == "ema"
    assert restored.recommended is True


def test_strategy_operation_requires_json_pointer_path() -> None:
    with pytest.raises(ValueError):
        StrategyOperation(
            operation=StrategyOperationType.SET,
            path="instrument/ticker",
            value="AAPL",
        )


def test_strategy_operation_requires_value_for_set() -> None:
    with pytest.raises(ValueError):
        StrategyOperation(
            operation=StrategyOperationType.SET,
            path="/instrument/ticker",
        )


def test_strategy_operation_serialization() -> None:
    operation = StrategyOperation(
        operation=StrategyOperationType.SET,
        path="/instrument/ticker",
        value="AAPL",
        reason="The user selected AAPL.",
    )

    restored = StrategyOperation.from_dict(
        operation.to_dict()
    )

    assert restored.operation == StrategyOperationType.SET
    assert restored.path == "/instrument/ticker"
    assert restored.value == "AAPL"


def test_question_response_requires_question() -> None:
    with pytest.raises(ValueError):
        LLMResponse(
            response_type=LLMResponseType.QUESTION,
            message="I need more information.",
            next_state=ConversationState.ASKING_TICKER,
            requires_user_input=True,
        )


def test_question_response_requires_user_input() -> None:
    with pytest.raises(ValueError):
        LLMResponse(
            response_type=LLMResponseType.QUESTION,
            message="Choose a ticker.",
            question="Which ticker do you want to test?",
            next_state=ConversationState.ASKING_TICKER,
            requires_user_input=False,
        )


def test_options_require_question() -> None:
    with pytest.raises(ValueError):
        LLMResponse(
            response_type=LLMResponseType.INFORMATION,
            message="Available options.",
            next_state=ConversationState.BUILDING_STRATEGY,
            options=[
                ResponseOption(
                    label="EMA",
                    value="ema",
                )
            ],
        )


def test_strategy_changed_requires_operations() -> None:
    with pytest.raises(ValueError):
        LLMResponse(
            response_type=LLMResponseType.STRATEGY_UPDATE,
            message="The strategy was updated.",
            next_state=ConversationState.BUILDING_STRATEGY,
            strategy_changed=True,
        )


def test_operations_require_strategy_changed_flag() -> None:
    with pytest.raises(ValueError):
        LLMResponse(
            response_type=LLMResponseType.STRATEGY_UPDATE,
            message="The strategy was updated.",
            next_state=ConversationState.BUILDING_STRATEGY,
            operations=[
                StrategyOperation(
                    operation=StrategyOperationType.SET,
                    path="/instrument/ticker",
                    value="AAPL",
                )
            ],
            strategy_changed=False,
        )


def test_valid_clarification_response() -> None:
    response = LLMResponse(
        response_type=LLMResponseType.CLARIFICATION,
        message="The term trend is ambiguous.",
        question="How would you like to define the trend?",
        options=[
            ResponseOption(
                label="EMA",
                value="ema",
            ),
            ResponseOption(
                label="ADX",
                value="adx",
            ),
        ],
        next_state=ConversationState.BUILDING_STRATEGY,
        requires_user_input=True,
    )

    assert response.requires_user_input is True
    assert len(response.options) == 2


def test_valid_strategy_update_response() -> None:
    response = LLMResponse(
        response_type=LLMResponseType.STRATEGY_UPDATE,
        message="The ticker was added to the strategy.",
        next_state=ConversationState.ASKING_GOAL,
        operations=[
            StrategyOperation(
                operation=StrategyOperationType.SET,
                path="/instrument/ticker",
                value="AAPL",
            )
        ],
        strategy_changed=True,
    )

    assert response.has_operations is True
    assert response.strategy_changed is True


def test_ready_for_review_requires_correct_state() -> None:
    with pytest.raises(ValueError):
        LLMResponse(
            response_type=LLMResponseType.READY_FOR_REVIEW,
            message="The strategy is ready.",
            next_state=ConversationState.BUILDING_STRATEGY,
        )


def test_approval_required_response() -> None:
    response = LLMResponse(
        response_type=LLMResponseType.APPROVAL_REQUIRED,
        message="Review and approve the strategy.",
        next_state=ConversationState.READY_FOR_REVIEW,
        requires_approval=True,
    )

    assert response.requires_approval is True


def test_error_response_requires_warning_tone() -> None:
    with pytest.raises(ValueError):
        LLMResponse(
            response_type=LLMResponseType.ERROR,
            message="The model response could not be parsed.",
            next_state=ConversationState.ERROR,
            tone="neutral",
        )


def test_validation_message_serialization() -> None:
    message = ValidationMessage(
        code="entry.missing",
        message="The strategy has no entry rule.",
        severity="error",
        section="entry",
    )

    restored = ValidationMessage.from_dict(
        message.to_dict()
    )

    assert restored.code == "entry.missing"
    assert restored.severity == "error"


def test_llm_response_serialization_round_trip() -> None:
    response = LLMResponse(
        response_type=LLMResponseType.STRATEGY_UPDATE,
        message="The strategy was updated.",
        tone="success",
        next_state=ConversationState.BUILDING_STRATEGY,
        operations=[
            StrategyOperation(
                operation=StrategyOperationType.SET,
                path="/instrument/ticker",
                value="ENI.MI",
            )
        ],
        validation_messages=[
            ValidationMessage(
                code="exit.missing",
                message="An exit rule is still required.",
                severity="warning",
                section="exit",
            )
        ],
        strategy_changed=True,
        metadata={
            "model": "gemini-2.5-flash",
        },
    )

    restored = LLMResponse.from_dict(
        response.to_dict()
    )

    assert restored.response_type == LLMResponseType.STRATEGY_UPDATE
    assert restored.next_state == ConversationState.BUILDING_STRATEGY
    assert restored.operations[0].value == "ENI.MI"
    assert restored.validation_messages[0].code == "exit.missing"
    assert restored.metadata["model"] == "gemini-2.5-flash"


def test_llm_response_detects_validation_errors() -> None:
    response = LLMResponse(
        response_type=LLMResponseType.VALIDATION,
        message="The strategy contains validation errors.",
        next_state=ConversationState.BUILDING_STRATEGY,
        tone="warning",
        validation_messages=[
            ValidationMessage(
                code="entry.missing",
                message="Entry is missing.",
                severity="error",
            )
        ],
    )

    assert response.has_errors is True