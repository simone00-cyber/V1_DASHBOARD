from __future__ import annotations
from typing import Any

from enum import Enum

from uuid import uuid4
from dataclasses import dataclass, field as dc_field

class OperandKind(str, Enum):
    PRICE = "price"
    INDICATOR = "indicator"
    CONSTANT = "constant"
    VOLUME = "volume"
    PATTERN = "pattern"
    CYCLICAL = "cyclical"


class ComparisonOperator(str, Enum):
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    EQUAL = "=="
    NOT_EQUAL = "!="
    CROSS_ABOVE = "cross_above"
    CROSS_BELOW = "cross_below"
    BETWEEN = "between"
    OUTSIDE = "outside"
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"


class LogicalOperator(str, Enum):
    ALL = "all"
    ANY = "any"


class RuleDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


class RulePurpose(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"
    FILTER = "filter"


@dataclass(slots=True)
class Operand:
    kind: OperandKind
    field: str | None = None
    name: str | None = None
    value: Any = None
    parameters: dict[str, Any] = dc_field(default_factory=dict)
    timeframe: str | None = None
    offset: int = 0

    def __post_init__(self) -> None:
        if self.offset < 0:
            raise ValueError("Operand offset cannot be negative.")

        if self.kind in {
            OperandKind.PRICE,
            OperandKind.VOLUME,
        } and not self.field:
            raise ValueError(
                f"Operand kind {self.kind.value!r} requires a field."
            )

        if self.kind in {
            OperandKind.INDICATOR,
            OperandKind.PATTERN,
            OperandKind.CYCLICAL,
        } and not self.name:
            raise ValueError(
                f"Operand kind {self.kind.value!r} requires a name."
            )

        if (
            self.kind == OperandKind.CONSTANT
            and self.value is None
        ):
            raise ValueError(
                "A constant operand requires a value."
            )

        if self.timeframe is not None:
            self.timeframe = self.timeframe.strip().lower() or None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "field": self.field,
            "name": self.name,
            "value": self.value,
            "parameters": self.parameters,
            "timeframe": self.timeframe,
            "offset": self.offset,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Operand":
        try:
            kind = OperandKind(str(data.get("kind", "")))
        except ValueError as exc:
            raise ValueError(
                f"Unsupported operand kind: {data.get('kind')!r}"
            ) from exc

        parameters = data.get("parameters", {})

        if not isinstance(parameters, dict):
            raise ValueError(
                "Operand parameters must be a dictionary."
            )

        return cls(
            kind=kind,
            field=(
                str(data["field"])
                if data.get("field") is not None
                else None
            ),
            name=(
                str(data["name"])
                if data.get("name") is not None
                else None
            ),
            value=data.get("value"),
            parameters=parameters,
            timeframe=(
                str(data["timeframe"])
                if data.get("timeframe") is not None
                else None
            ),
            offset=int(data.get("offset", 0)),
        )


@dataclass(slots=True)
class Condition:
    left: Operand
    operator: ComparisonOperator
    right: Operand | None = None
    second_right: Operand | None = None
    lookback_bars: int = 1
    persistence_bars: int = 1
    enabled: bool = True
    condition_id: str = dc_field(
        default_factory=lambda: str(uuid4())
    )
    label: str | None = None

    def __post_init__(self) -> None:
        if self.lookback_bars < 1:
            raise ValueError(
                "lookback_bars must be at least one."
            )

        if self.persistence_bars < 1:
            raise ValueError(
                "persistence_bars must be at least one."
            )

        unary_operators = {
            ComparisonOperator.IS_TRUE,
            ComparisonOperator.IS_FALSE,
        }

        if self.operator not in unary_operators and self.right is None:
            raise ValueError(
                f"Operator {self.operator.value!r} requires "
                "a right operand."
            )

        range_operators = {
            ComparisonOperator.BETWEEN,
            ComparisonOperator.OUTSIDE,
        }

        if (
            self.operator in range_operators
            and self.second_right is None
        ):
            raise ValueError(
                f"Operator {self.operator.value!r} requires "
                "two right operands."
            )

        if self.label is not None:
            self.label = self.label.strip() or None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_type": "condition",
            "condition_id": self.condition_id,
            "label": self.label,
            "left": self.left.to_dict(),
            "operator": self.operator.value,
            "right": (
                self.right.to_dict()
                if self.right is not None
                else None
            ),
            "second_right": (
                self.second_right.to_dict()
                if self.second_right is not None
                else None
            ),
            "lookback_bars": self.lookback_bars,
            "persistence_bars": self.persistence_bars,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Condition":
        left = data.get("left")

        if not isinstance(left, dict):
            raise ValueError(
                "Condition left operand must be a dictionary."
            )

        right = data.get("right")
        second_right = data.get("second_right")

        try:
            operator = ComparisonOperator(
                str(data.get("operator", ""))
            )
        except ValueError as exc:
            raise ValueError(
                f"Unsupported comparison operator: "
                f"{data.get('operator')!r}"
            ) from exc

        return cls(
            condition_id=str(
                data.get("condition_id") or uuid4()
            ),
            label=(
                str(data["label"])
                if data.get("label") is not None
                else None
            ),
            left=Operand.from_dict(left),
            operator=operator,
            right=(
                Operand.from_dict(right)
                if isinstance(right, dict)
                else None
            ),
            second_right=(
                Operand.from_dict(second_right)
                if isinstance(second_right, dict)
                else None
            ),
            lookback_bars=int(
                data.get("lookback_bars", 1)
            ),
            persistence_bars=int(
                data.get("persistence_bars", 1)
            ),
            enabled=bool(data.get("enabled", True)),
        )





@dataclass
class ConditionGroup:
    operator: LogicalOperator
    children: list[Any] = dc_field(default_factory=list)
    group_id: str = dc_field(
        default_factory=lambda: str(uuid4())
    )
    label: str | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.children:
            raise ValueError(
                "A condition group requires at least one child."
            )

        for child in self.children:
            if not isinstance(child, (Condition, ConditionGroup)):
                raise TypeError(
                    "ConditionGroup children must be "
                    "Condition or ConditionGroup."
                )

        if self.label is not None:
            self.label = self.label.strip() or None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_type": "group",
            "group_id": self.group_id,
            "label": self.label,
            "operator": self.operator.value,
            "enabled": self.enabled,
            "children": [
                child.to_dict()
                for child in self.children
            ],
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "ConditionGroup":
        try:
            operator = LogicalOperator(
                str(data.get("operator", ""))
            )
        except ValueError as exc:
            raise ValueError(
                f"Unsupported logical operator: "
                f"{data.get('operator')!r}"
            ) from exc

        raw_children = data.get("children")

        if not isinstance(raw_children, list):
            raise ValueError(
                "Condition group children must be a list."
            )

        children = []
        for item in raw_children:
            if not isinstance(item, dict):
                raise ValueError(
                    "Every condition group child must "
                    "be a dictionary."
                )

            node_type = item.get("node_type")

            if node_type == "condition":
                children.append(
                    Condition.from_dict(item)
                )
            elif node_type == "group":
                children.append(
                    cls.from_dict(item)
                )
            else:
                raise ValueError(
                    f"Unsupported strategy node type: "
                    f"{node_type!r}"
                )

        return cls(
            group_id=str(
                data.get("group_id") or uuid4()
            ),
            label=(
                str(data["label"])
                if data.get("label") is not None
                else None
            ),
            operator=operator,
            enabled=bool(data.get("enabled", True)),
            children=children,
        )


@dataclass(slots=True)
class StrategyRule:
    purpose: RulePurpose
    direction: RuleDirection
    expression: ConditionGroup
    rule_id: str = dc_field(
        default_factory=lambda: str(uuid4())
    )
    name: str | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.name is not None:
            self.name = self.name.strip() or None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "purpose": self.purpose.value,
            "direction": self.direction.value,
            "enabled": self.enabled,
            "expression": self.expression.to_dict(),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "StrategyRule":
        expression = data.get("expression")

        if not isinstance(expression, dict):
            raise ValueError(
                "Strategy rule expression must be a dictionary."
            )

        try:
            purpose = RulePurpose(
                str(data.get("purpose", ""))
            )
            direction = RuleDirection(
                str(data.get("direction", ""))
            )
        except ValueError as exc:
            raise ValueError(
                "Unsupported strategy rule purpose or direction."
            ) from exc

        return cls(
            rule_id=str(
                data.get("rule_id") or uuid4()
            ),
            name=(
                str(data["name"])
                if data.get("name") is not None
                else None
            ),
            purpose=purpose,
            direction=direction,
            enabled=bool(data.get("enabled", True)),
            expression=ConditionGroup.from_dict(
                expression
            ),
        )


def price(
    field: str,
    timeframe: str | None = None,
    offset: int = 0,
) -> Operand:
    return Operand(
        kind=OperandKind.PRICE,
        field=field,
        timeframe=timeframe,
        offset=offset,
    )


def volume(
    field: str = "volume",
    timeframe: str | None = None,
    offset: int = 0,
) -> Operand:
    return Operand(
        kind=OperandKind.VOLUME,
        field=field,
        timeframe=timeframe,
        offset=offset,
    )


def indicator(
    name: str,
    parameters: dict[str, Any],
    timeframe: str | None = None,
    field: str | None = None,
    offset: int = 0,
) -> Operand:
    return Operand(
        kind=OperandKind.INDICATOR,
        name=name.upper(),
        field=field,
        parameters=parameters,
        timeframe=timeframe,
        offset=offset,
    )


def constant(value: Any) -> Operand:
    return Operand(
        kind=OperandKind.CONSTANT,
        value=value,
    )


def pattern(
    name: str,
    parameters: dict[str, Any] | None = None,
    timeframe: str | None = None,
) -> Operand:
    return Operand(
        kind=OperandKind.PATTERN,
        name=name,
        parameters=parameters or {},
        timeframe=timeframe,
    )


def cyclical(
    name: str,
    parameters: dict[str, Any] | None = None,
    timeframe: str | None = None,
) -> Operand:
    return Operand(
        kind=OperandKind.CYCLICAL,
        name=name,
        parameters=parameters or {},
        timeframe=timeframe,
    )