from core.ai.conversation_state import ConversationState
from core.ai.llm_protocol import (
    LLMResponse,
    LLMResponseType,
    StrategyOperation,
    StrategyOperationType,
)
from core.ai.research_project import ResearchProject
from core.ai.strategy_parser import StrategyParser


def make_update_response(
    operations: list[StrategyOperation],
) -> LLMResponse:
    return LLMResponse(
        response_type=LLMResponseType.STRATEGY_UPDATE,
        message="The strategy was updated.",
        next_state=ConversationState.BUILDING_STRATEGY,
        operations=operations,
        strategy_changed=True,
    )


def test_response_without_changes_does_not_modify_project() -> None:
    parser = StrategyParser()
    project = ResearchProject()

    response = LLMResponse(
        response_type=LLMResponseType.INFORMATION,
        message="No strategy change is required.",
        next_state=ConversationState.ASKING_TICKER,
    )

    original_version = project.strategy_version
    result = parser.apply_response(project, response)

    assert result.success is True
    assert result.strategy_changed is False
    assert project.strategy_version == original_version


def test_set_ticker_operation() -> None:
    parser = StrategyParser()
    project = ResearchProject()

    response = make_update_response(
        [
            StrategyOperation(
                operation=StrategyOperationType.SET,
                path="/instrument/ticker",
                value="AAPL",
            )
        ]
    )

    result = parser.apply_response(project, response)

    assert result.success is True
    assert result.strategy_changed is True
    assert result.operation_count == 1
    assert project.ticker == "AAPL"
    assert project.status == "strategy_incomplete"


def test_multiple_operations_increment_version_once() -> None:
    parser = StrategyParser()
    project = ResearchProject()

    initial_version = project.strategy_version

    response = make_update_response(
        [
            StrategyOperation(
                operation=StrategyOperationType.SET,
                path="/instrument/ticker",
                value="ENI.MI",
            ),
            StrategyOperation(
                operation=StrategyOperationType.SET,
                path="/instrument/timeframe",
                value="1wk",
            ),
        ]
    )

    result = parser.apply_response(project, response)

    assert result.success is True
    assert project.ticker == "ENI.MI"
    assert project.timeframe == "1wk"
    assert project.strategy_version == initial_version + 1


def test_append_entry_rule() -> None:
    parser = StrategyParser()
    project = ResearchProject()

    rule = {
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

    response = make_update_response(
        [
            StrategyOperation(
                operation=StrategyOperationType.APPEND,
                path="/entry/long",
                value=rule,
            )
        ]
    )

    result = parser.apply_response(project, response)

    assert result.success is True
    assert project.strategy["entry"]["long"] == [rule]


def test_replace_existing_value() -> None:
    parser = StrategyParser()
    project = ResearchProject()

    response = make_update_response(
        [
            StrategyOperation(
                operation=StrategyOperationType.REPLACE,
                path="/risk/initial_capital",
                value=50_000.0,
            )
        ]
    )

    result = parser.apply_response(project, response)

    assert result.success is True
    assert project.strategy["risk"]["initial_capital"] == 50_000.0
    assert (
        result.applied_operations[0].previous_value
        == 100_000.0
    )


def test_replace_missing_value_fails() -> None:
    parser = StrategyParser()
    project = ResearchProject()

    response = make_update_response(
        [
            StrategyOperation(
                operation=StrategyOperationType.REPLACE,
                path="/metadata/unknown_field",
                value="value",
            )
        ]
    )

    original_strategy = project.to_dict()["strategy"]
    result = parser.apply_response(project, response)

    assert result.success is False
    assert result.strategy_changed is False
    assert project.strategy == original_strategy


def test_remove_list_item() -> None:
    parser = StrategyParser()
    project = ResearchProject()

    project.strategy["entry"]["long"] = [
        {"name": "rule-1"},
        {"name": "rule-2"},
    ]

    response = make_update_response(
        [
            StrategyOperation(
                operation=StrategyOperationType.REMOVE,
                path="/entry/long/0",
            )
        ]
    )

    result = parser.apply_response(project, response)

    assert result.success is True
    assert project.strategy["entry"]["long"] == [
        {"name": "rule-2"}
    ]


def test_clear_entry_rules() -> None:
    parser = StrategyParser()
    project = ResearchProject()

    project.strategy["entry"]["long"] = [
        {"name": "rule-1"},
        {"name": "rule-2"},
    ]

    response = make_update_response(
        [
            StrategyOperation(
                operation=StrategyOperationType.CLEAR,
                path="/entry/long",
            )
        ]
    )

    result = parser.apply_response(project, response)

    assert result.success is True
    assert project.strategy["entry"]["long"] == []


def test_append_to_non_list_fails() -> None:
    parser = StrategyParser()
    project = ResearchProject()

    response = make_update_response(
        [
            StrategyOperation(
                operation=StrategyOperationType.APPEND,
                path="/instrument/ticker",
                value="AAPL",
            )
        ]
    )

    result = parser.apply_response(project, response)

    assert result.success is False
    assert project.ticker == ""


def test_protected_schema_version_cannot_be_modified() -> None:
    parser = StrategyParser()
    project = ResearchProject()

    response = make_update_response(
        [
            StrategyOperation(
                operation=StrategyOperationType.SET,
                path="/schema_version",
                value="2.0",
            )
        ]
    )

    result = parser.apply_response(project, response)

    assert result.success is False
    assert project.strategy["schema_version"] == "1.0"


def test_unsupported_root_section_is_rejected() -> None:
    parser = StrategyParser()
    project = ResearchProject()

    response = make_update_response(
        [
            StrategyOperation(
                operation=StrategyOperationType.SET,
                path="/unknown/value",
                value=True,
            )
        ]
    )

    result = parser.apply_response(project, response)

    assert result.success is False
    assert "Unsupported strategy root section" in result.errors[0]


def test_operations_are_atomic() -> None:
    parser = StrategyParser()
    project = ResearchProject()

    initial_version = project.strategy_version

    response = make_update_response(
        [
            StrategyOperation(
                operation=StrategyOperationType.SET,
                path="/instrument/ticker",
                value="AAPL",
            ),
            StrategyOperation(
                operation=StrategyOperationType.REPLACE,
                path="/metadata/missing_field",
                value="invalid",
            ),
        ]
    )

    result = parser.apply_response(project, response)

    assert result.success is False
    assert project.ticker == ""
    assert project.strategy_version == initial_version


def test_set_can_create_new_metadata_field() -> None:
    parser = StrategyParser()
    project = ResearchProject()

    response = make_update_response(
        [
            StrategyOperation(
                operation=StrategyOperationType.SET,
                path="/metadata/research_hypothesis",
                value="Momentum persists after a breakout.",
            )
        ]
    )

    result = parser.apply_response(project, response)

    assert result.success is True
    assert (
        project.strategy["metadata"]["research_hypothesis"]
        == "Momentum persists after a breakout."
    )


def test_set_list_item_using_dash_appends() -> None:
    parser = StrategyParser()
    project = ResearchProject()

    response = make_update_response(
        [
            StrategyOperation(
                operation=StrategyOperationType.SET,
                path="/entry/long/-",
                value={"name": "new-rule"},
            )
        ]
    )

    result = parser.apply_response(project, response)

    assert result.success is True
    assert project.strategy["entry"]["long"] == [
        {"name": "new-rule"}
    ]


def test_parse_result_serialization() -> None:
    parser = StrategyParser()
    project = ResearchProject()

    response = make_update_response(
        [
            StrategyOperation(
                operation=StrategyOperationType.SET,
                path="/instrument/ticker",
                value="MSFT",
            )
        ]
    )

    result = parser.apply_response(project, response)
    payload = result.to_dict()

    assert payload["success"] is True
    assert payload["strategy_changed"] is True
    assert payload["operation_count"] == 1
    assert payload["resulting_strategy"]["instrument"]["ticker"] == "MSFT"