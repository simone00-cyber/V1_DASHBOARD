import pytest

from core.ai.strategy_dsl import (
    ComparisonOperator,
    Condition,
    ConditionGroup,
    LogicalOperator,
    Operand,
    OperandKind,
    RuleDirection,
    RulePurpose,
    StrategyRule,
    constant,
    cyclical,
    indicator,
    pattern,
    price,
    volume,
)


def test_price_operand_requires_field() -> None:
    with pytest.raises(ValueError):
        Operand(
            kind=OperandKind.PRICE,
        )


def test_indicator_operand_requires_name() -> None:
    with pytest.raises(ValueError):
        Operand(
            kind=OperandKind.INDICATOR,
        )


def test_constant_operand_requires_value() -> None:
    with pytest.raises(ValueError):
        Operand(
            kind=OperandKind.CONSTANT,
        )


def test_operand_helpers() -> None:
    close = price("close", timeframe="1d")
    ema = indicator(
        "ema",
        {"period": 200},
        timeframe="1d",
    )
    fixed = constant(30)
    traded_volume = volume()

    assert close.kind == OperandKind.PRICE
    assert ema.name == "EMA"
    assert ema.parameters["period"] == 200
    assert fixed.value == 30
    assert traded_volume.kind == OperandKind.VOLUME


def test_binary_condition_requires_right_operand() -> None:
    with pytest.raises(ValueError):
        Condition(
            left=price("close"),
            operator=ComparisonOperator.GREATER_THAN,
        )


def test_unary_condition_does_not_require_right_operand() -> None:
    condition = Condition(
        left=pattern("bull_flag"),
        operator=ComparisonOperator.IS_TRUE,
    )

    assert condition.right is None


def test_between_requires_two_right_operands() -> None:
    with pytest.raises(ValueError):
        Condition(
            left=indicator("RSI", {"period": 14}),
            operator=ComparisonOperator.BETWEEN,
            right=constant(30),
        )


def test_condition_serialization_round_trip() -> None:
    condition = Condition(
        label="RSI recovery",
        left=indicator("RSI", {"period": 14}),
        operator=ComparisonOperator.CROSS_ABOVE,
        right=constant(30),
        lookback_bars=3,
    )

    restored = Condition.from_dict(
        condition.to_dict()
    )

    assert restored.condition_id == condition.condition_id
    assert restored.label == "RSI recovery"
    assert (
        restored.operator
        == ComparisonOperator.CROSS_ABOVE
    )
    assert restored.right is not None
    assert restored.right.value == 30


def test_condition_group_requires_children() -> None:
    with pytest.raises(ValueError):
        ConditionGroup(
            operator=LogicalOperator.ALL,
            children=[],
        )


def test_nested_condition_group_serialization() -> None:
    trend = Condition(
        left=price("close"),
        operator=ComparisonOperator.GREATER_THAN,
        right=indicator("EMA", {"period": 200}),
    )

    momentum = Condition(
        left=indicator("RSI", {"period": 14}),
        operator=ComparisonOperator.CROSS_ABOVE,
        right=constant(30),
    )

    volume_confirmation = Condition(
        left=volume(),
        operator=ComparisonOperator.GREATER_THAN,
        right=indicator(
            "SMA",
            {
                "period": 20,
                "source": "volume",
            },
        ),
    )

    nested = ConditionGroup(
        operator=LogicalOperator.ANY,
        children=[
            momentum,
            volume_confirmation,
        ],
    )

    root = ConditionGroup(
        operator=LogicalOperator.ALL,
        children=[
            trend,
            nested,
        ],
    )

    restored = ConditionGroup.from_dict(
        root.to_dict()
    )

    assert restored.operator == LogicalOperator.ALL
    assert len(restored.children) == 2
    assert isinstance(
        restored.children[1],
        ConditionGroup,
    )


def test_strategy_rule_serialization() -> None:
    expression = ConditionGroup(
        operator=LogicalOperator.ALL,
        children=[
            Condition(
                left=price("close"),
                operator=ComparisonOperator.GREATER_THAN,
                right=indicator(
                    "EMA",
                    {"period": 200},
                ),
            )
        ],
    )

    rule = StrategyRule(
        name="Long trend entry",
        purpose=RulePurpose.ENTRY,
        direction=RuleDirection.LONG,
        expression=expression,
    )

    restored = StrategyRule.from_dict(
        rule.to_dict()
    )

    assert restored.rule_id == rule.rule_id
    assert restored.purpose == RulePurpose.ENTRY
    assert restored.direction == RuleDirection.LONG
    assert restored.name == "Long trend entry"


def test_pattern_operand() -> None:
    operand = pattern(
        "bull_flag",
        {"minimum_bars": 5},
        timeframe="1d",
    )

    assert operand.kind == OperandKind.PATTERN
    assert operand.name == "bull_flag"
    assert operand.parameters["minimum_bars"] == 5


def test_cyclical_operand() -> None:
    operand = cyclical(
        "matrix_state",
        {"state": "buy"},
        timeframe="1wk",
    )

    assert operand.kind == OperandKind.CYCLICAL
    assert operand.name == "matrix_state"
    assert operand.parameters["state"] == "buy"


def test_negative_operand_offset_is_rejected() -> None:
    with pytest.raises(ValueError):
        price(
            field="close",
            offset=-1,
        )


def test_invalid_strategy_node_type_is_rejected() -> None:
    with pytest.raises(ValueError):
        ConditionGroup.from_dict(
            {
                "operator": "all",
                "children": [
                    {
                        "node_type": "unknown",
                    }
                ],
            }
        )