from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from core.ai.llm_protocol import (
    LLMResponse,
    StrategyOperation,
    StrategyOperationType,
)
from core.ai.research_project import ResearchProject


class StrategyOperationError(ValueError):
    """Raised when a strategy operation cannot be applied safely."""


@dataclass(slots=True)
class AppliedOperation:
    operation: StrategyOperationType
    path: str
    previous_value: Any = None
    new_value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation.value,
            "path": self.path,
            "previous_value": self.previous_value,
            "new_value": self.new_value,
        }


@dataclass
class StrategyParseResult:
    success: bool
    strategy_changed: bool
    applied_operations: list[AppliedOperation] = field(
        default_factory=list
    )
    errors: list[str] = field(default_factory=list)
    resulting_strategy: dict[str, Any] | None = None

    @property
    def operation_count(self) -> int:
        return len(self.applied_operations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "strategy_changed": self.strategy_changed,
            "applied_operations": [
                operation.to_dict()
                for operation in self.applied_operations
            ],
            "errors": list(self.errors),
            "resulting_strategy": self.resulting_strategy,
            "operation_count": self.operation_count,
        }


class StrategyParser:
    """
    Applies structured LLM operations to a ResearchProject strategy.

    All operations are applied to a deep copy first. The project is changed
    only when every operation succeeds, preventing partial strategy updates.
    """

    PROTECTED_PATHS = {
        "/schema_version",
    }

    ALLOWED_ROOT_SECTIONS = {
        "instrument",
        "direction",
        "entry",
        "exit",
        "risk",
        "execution",
        "metadata",
    }

    def apply_response(
        self,
        project: ResearchProject,
        response: LLMResponse,
    ) -> StrategyParseResult:
        if not response.strategy_changed:
            return StrategyParseResult(
                success=True,
                strategy_changed=False,
                resulting_strategy=deepcopy(project.strategy),
            )

        if not response.operations:
            return StrategyParseResult(
                success=False,
                strategy_changed=False,
                errors=[
                    "The response is marked as strategy_changed but "
                    "contains no operations."
                ],
                resulting_strategy=deepcopy(project.strategy),
            )

        return self.apply_operations(
            project=project,
            operations=response.operations,
        )

    def apply_operations(
        self,
        project: ResearchProject,
        operations: list[StrategyOperation],
    ) -> StrategyParseResult:
        if not operations:
            return StrategyParseResult(
                success=True,
                strategy_changed=False,
                resulting_strategy=deepcopy(project.strategy),
            )

        working_strategy = deepcopy(project.strategy)
        applied_operations: list[AppliedOperation] = []

        try:
            for operation in operations:
                applied = self._apply_operation(
                    strategy=working_strategy,
                    operation=operation,
                )
                applied_operations.append(applied)

            self._validate_strategy_root(working_strategy)

        except (StrategyOperationError, TypeError, ValueError) as exc:
            return StrategyParseResult(
                success=False,
                strategy_changed=False,
                applied_operations=[],
                errors=[str(exc)],
                resulting_strategy=deepcopy(project.strategy),
            )

        project.strategy = working_strategy
        project.mark_strategy_changed()

        return StrategyParseResult(
            success=True,
            strategy_changed=True,
            applied_operations=applied_operations,
            resulting_strategy=deepcopy(project.strategy),
        )

    def _apply_operation(
        self,
        strategy: dict[str, Any],
        operation: StrategyOperation,
    ) -> AppliedOperation:
        self._validate_operation_path(operation.path)

        tokens = self._parse_json_pointer(operation.path)

        if not tokens:
            raise StrategyOperationError(
                "Operations on the strategy root are not allowed."
            )

        parent, final_token = self._resolve_parent(
            document=strategy,
            tokens=tokens,
            create_missing=(
                operation.operation == StrategyOperationType.SET
            ),
        )

        if operation.operation == StrategyOperationType.SET:
            return self._set_value(
                parent=parent,
                token=final_token,
                value=deepcopy(operation.value),
                path=operation.path,
            )

        if operation.operation == StrategyOperationType.REPLACE:
            return self._replace_value(
                parent=parent,
                token=final_token,
                value=deepcopy(operation.value),
                path=operation.path,
            )

        if operation.operation == StrategyOperationType.APPEND:
            return self._append_value(
                parent=parent,
                token=final_token,
                value=deepcopy(operation.value),
                path=operation.path,
            )

        if operation.operation == StrategyOperationType.REMOVE:
            return self._remove_value(
                parent=parent,
                token=final_token,
                path=operation.path,
            )

        if operation.operation == StrategyOperationType.CLEAR:
            return self._clear_value(
                parent=parent,
                token=final_token,
                path=operation.path,
            )

        raise StrategyOperationError(
            f"Unsupported operation: {operation.operation.value!r}."
        )

    def _set_value(
        self,
        parent: Any,
        token: str,
        value: Any,
        path: str,
    ) -> AppliedOperation:
        if isinstance(parent, dict):
            previous = deepcopy(parent.get(token))
            parent[token] = value

            return AppliedOperation(
                operation=StrategyOperationType.SET,
                path=path,
                previous_value=previous,
                new_value=deepcopy(value),
            )

        if isinstance(parent, list):
            index = self._parse_list_index(
                token=token,
                length=len(parent),
                allow_end=True,
            )

            if index == len(parent):
                parent.append(value)
                previous = None
            else:
                previous = deepcopy(parent[index])
                parent[index] = value

            return AppliedOperation(
                operation=StrategyOperationType.SET,
                path=path,
                previous_value=previous,
                new_value=deepcopy(value),
            )

        raise StrategyOperationError(
            f"Cannot set value at {path!r}: parent is not a container."
        )

    def _replace_value(
        self,
        parent: Any,
        token: str,
        value: Any,
        path: str,
    ) -> AppliedOperation:
        if isinstance(parent, dict):
            if token not in parent:
                raise StrategyOperationError(
                    f"Cannot replace missing path {path!r}."
                )

            previous = deepcopy(parent[token])
            parent[token] = value

            return AppliedOperation(
                operation=StrategyOperationType.REPLACE,
                path=path,
                previous_value=previous,
                new_value=deepcopy(value),
            )

        if isinstance(parent, list):
            index = self._parse_list_index(
                token=token,
                length=len(parent),
                allow_end=False,
            )

            previous = deepcopy(parent[index])
            parent[index] = value

            return AppliedOperation(
                operation=StrategyOperationType.REPLACE,
                path=path,
                previous_value=previous,
                new_value=deepcopy(value),
            )

        raise StrategyOperationError(
            f"Cannot replace value at {path!r}: parent is not a container."
        )

    def _append_value(
        self,
        parent: Any,
        token: str,
        value: Any,
        path: str,
    ) -> AppliedOperation:
        target = self._get_existing_value(
            parent=parent,
            token=token,
            path=path,
        )

        if not isinstance(target, list):
            raise StrategyOperationError(
                f"Cannot append to {path!r}: target is not a list."
            )

        previous = deepcopy(target)
        target.append(value)

        return AppliedOperation(
            operation=StrategyOperationType.APPEND,
            path=path,
            previous_value=previous,
            new_value=deepcopy(target),
        )

    def _remove_value(
        self,
        parent: Any,
        token: str,
        path: str,
    ) -> AppliedOperation:
        if isinstance(parent, dict):
            if token not in parent:
                raise StrategyOperationError(
                    f"Cannot remove missing path {path!r}."
                )

            previous = deepcopy(parent[token])
            del parent[token]

            return AppliedOperation(
                operation=StrategyOperationType.REMOVE,
                path=path,
                previous_value=previous,
                new_value=None,
            )

        if isinstance(parent, list):
            index = self._parse_list_index(
                token=token,
                length=len(parent),
                allow_end=False,
            )

            previous = deepcopy(parent[index])
            del parent[index]

            return AppliedOperation(
                operation=StrategyOperationType.REMOVE,
                path=path,
                previous_value=previous,
                new_value=None,
            )

        raise StrategyOperationError(
            f"Cannot remove value at {path!r}: parent is not a container."
        )

    def _clear_value(
        self,
        parent: Any,
        token: str,
        path: str,
    ) -> AppliedOperation:
        target = self._get_existing_value(
            parent=parent,
            token=token,
            path=path,
        )

        previous = deepcopy(target)

        if isinstance(target, list):
            target.clear()
            new_value: Any = []
        elif isinstance(target, dict):
            target.clear()
            new_value = {}
        else:
            raise StrategyOperationError(
                f"Cannot clear {path!r}: target must be a list or dictionary."
            )

        return AppliedOperation(
            operation=StrategyOperationType.CLEAR,
            path=path,
            previous_value=previous,
            new_value=new_value,
        )

    def _resolve_parent(
        self,
        document: Any,
        tokens: list[str],
        create_missing: bool,
    ) -> tuple[Any, str]:
        current = document

        for token in tokens[:-1]:
            if isinstance(current, dict):
                if token not in current:
                    if create_missing:
                        current[token] = {}
                    else:
                        raise StrategyOperationError(
                            f"Path component {token!r} does not exist."
                        )

                current = current[token]
                continue

            if isinstance(current, list):
                index = self._parse_list_index(
                    token=token,
                    length=len(current),
                    allow_end=False,
                )
                current = current[index]
                continue

            raise StrategyOperationError(
                f"Cannot traverse path component {token!r}: "
                "encountered a non-container value."
            )

        return current, tokens[-1]

    def _get_existing_value(
        self,
        parent: Any,
        token: str,
        path: str,
    ) -> Any:
        if isinstance(parent, dict):
            if token not in parent:
                raise StrategyOperationError(
                    f"Path {path!r} does not exist."
                )
            return parent[token]

        if isinstance(parent, list):
            index = self._parse_list_index(
                token=token,
                length=len(parent),
                allow_end=False,
            )
            return parent[index]

        raise StrategyOperationError(
            f"Path {path!r} does not reference a container value."
        )

    def _validate_operation_path(self, path: str) -> None:
        if path in self.PROTECTED_PATHS:
            raise StrategyOperationError(
                f"Path {path!r} is protected and cannot be modified."
            )

        tokens = self._parse_json_pointer(path)

        if not tokens:
            raise StrategyOperationError(
                "The strategy root cannot be modified directly."
            )

        root_section = tokens[0]

        if root_section not in self.ALLOWED_ROOT_SECTIONS:
            raise StrategyOperationError(
                f"Unsupported strategy root section: {root_section!r}."
            )

    def _validate_strategy_root(
        self,
        strategy: dict[str, Any],
    ) -> None:
        if not isinstance(strategy, dict):
            raise StrategyOperationError(
                "The resulting strategy must be a dictionary."
            )

        required_sections = self.ALLOWED_ROOT_SECTIONS | {
            "schema_version",
        }

        missing = required_sections - set(strategy)

        if missing:
            missing_text = ", ".join(sorted(missing))
            raise StrategyOperationError(
                f"The resulting strategy is missing required sections: "
                f"{missing_text}."
            )

        for section in self.ALLOWED_ROOT_SECTIONS:
            if not isinstance(strategy[section], dict):
                raise StrategyOperationError(
                    f"Strategy section {section!r} must remain a dictionary."
                )

    @staticmethod
    def _parse_json_pointer(path: str) -> list[str]:
        if not isinstance(path, str) or not path.startswith("/"):
            raise StrategyOperationError(
                "Strategy paths must use JSON Pointer syntax."
            )

        if path == "/":
            return []

        raw_tokens = path[1:].split("/")

        return [
            token.replace("~1", "/").replace("~0", "~")
            for token in raw_tokens
        ]

    @staticmethod
    def _parse_list_index(
        token: str,
        length: int,
        allow_end: bool,
    ) -> int:
        if token == "-" and allow_end:
            return length

        try:
            index = int(token)
        except ValueError as exc:
            raise StrategyOperationError(
                f"Invalid list index: {token!r}."
            ) from exc

        upper_bound = length if allow_end else length - 1

        if index < 0 or index > upper_bound:
            raise StrategyOperationError(
                f"List index {index} is outside the allowed range."
            )

        return index