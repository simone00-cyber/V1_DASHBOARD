from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from core.ai.research_project import ResearchProject


ValidationSeverity = Literal["error", "warning", "info"]


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: ValidationSeverity
    section: str
    field: str | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StrategyHealth:
    issues: list[ValidationIssue] = field(default_factory=list)
    completion_score: int = 0
    is_valid: bool = False
    is_ready_for_review: bool = False
    can_be_approved: bool = False

    @property
    def errors(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == "error"
        ]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == "warning"
        ]

    @property
    def infos(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == "info"
        ]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "issues": [
                issue.to_dict()
                for issue in self.issues
            ],
            "completion_score": self.completion_score,
            "is_valid": self.is_valid,
            "is_ready_for_review": self.is_ready_for_review,
            "can_be_approved": self.can_be_approved,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
        }


class StrategyValidator:
    ALLOWED_TIMEFRAMES = {
        "1m",
        "2m",
        "5m",
        "15m",
        "30m",
        "60m",
        "90m",
        "1h",
        "4h",
        "1d",
        "5d",
        "1wk",
        "1mo",
        "3mo",
    }

    ALLOWED_EXECUTION_MODES = {
        "same_bar_close",
        "next_bar_open",
    }

    ALLOWED_ORDER_TYPES = {
        "market",
        "limit",
        "stop",
        "stop_limit",
    }

    ALLOWED_POSITION_SIZING_METHODS = {
        "percentage_of_equity",
        "fixed_cash",
        "fixed_quantity",
        "risk_per_trade",
        "volatility_target",
    }

    def validate(
        self,
        project: ResearchProject,
    ) -> StrategyHealth:
        issues: list[ValidationIssue] = []

        self._validate_instrument(project, issues)
        self._validate_direction(project, issues)
        self._validate_entry(project, issues)
        self._validate_exit(project, issues)
        self._validate_risk(project, issues)
        self._validate_execution(project, issues)
        self._validate_metadata(project, issues)

        completion_score = self._calculate_completion_score(project)

        has_errors = any(
            issue.severity == "error"
            for issue in issues
        )

        is_ready_for_review = (
            not has_errors
            and completion_score == 100
        )

        return StrategyHealth(
            issues=issues,
            completion_score=completion_score,
            is_valid=not has_errors,
            is_ready_for_review=is_ready_for_review,
            can_be_approved=is_ready_for_review,
        )

    def apply_project_status(
        self,
        project: ResearchProject,
    ) -> StrategyHealth:
        health = self.validate(project)

        if project.status == "archived":
            return health

        if project.is_approved and not health.can_be_approved:
            project.revoke_approval()
            return health

        if health.is_ready_for_review:
            project.mark_ready_for_review()
        else:
            project.status = "strategy_incomplete"
            project.touch()

        return health

    def _validate_instrument(
        self,
        project: ResearchProject,
        issues: list[ValidationIssue],
    ) -> None:
        instrument = project.strategy.get("instrument", {})

        ticker = str(instrument.get("ticker", "")).strip()

        if not ticker:
            issues.append(
                ValidationIssue(
                    code="instrument.ticker_missing",
                    message="The strategy requires a ticker.",
                    severity="error",
                    section="instrument",
                    field="ticker",
                    suggestion="Enter a valid Yahoo Finance ticker.",
                )
            )

        timeframe = str(
            instrument.get("timeframe", "")
        ).strip().lower()

        if timeframe not in self.ALLOWED_TIMEFRAMES:
            issues.append(
                ValidationIssue(
                    code="instrument.timeframe_invalid",
                    message=f"Unsupported timeframe: {timeframe!r}.",
                    severity="error",
                    section="instrument",
                    field="timeframe",
                    suggestion="Select one of the supported timeframes.",
                )
            )

        start_date = instrument.get("start_date")
        end_date = instrument.get("end_date")

        if (
            start_date is not None
            and end_date is not None
            and str(start_date) >= str(end_date)
        ):
            issues.append(
                ValidationIssue(
                    code="instrument.date_range_invalid",
                    message="The start date must be earlier than the end date.",
                    severity="error",
                    section="instrument",
                    field="start_date",
                )
            )

        if start_date is None:
            issues.append(
                ValidationIssue(
                    code="instrument.start_date_missing",
                    message="No explicit backtest start date has been defined.",
                    severity="warning",
                    section="instrument",
                    field="start_date",
                    suggestion=(
                        "Define a start date to make the research period "
                        "fully reproducible."
                    ),
                )
            )

    def _validate_direction(
        self,
        project: ResearchProject,
        issues: list[ValidationIssue],
    ) -> None:
        direction = project.strategy.get("direction", {})

        long_enabled = bool(direction.get("long_enabled", False))
        short_enabled = bool(direction.get("short_enabled", False))

        if not long_enabled and not short_enabled:
            issues.append(
                ValidationIssue(
                    code="direction.none_enabled",
                    message="At least one trading direction must be enabled.",
                    severity="error",
                    section="direction",
                )
            )

    def _validate_entry(
        self,
        project: ResearchProject,
        issues: list[ValidationIssue],
    ) -> None:
        direction = project.strategy.get("direction", {})
        entry = project.strategy.get("entry", {})

        long_enabled = bool(direction.get("long_enabled", False))
        short_enabled = bool(direction.get("short_enabled", False))

        long_rules = entry.get("long", [])
        short_rules = entry.get("short", [])

        if not isinstance(long_rules, list):
            issues.append(
                ValidationIssue(
                    code="entry.long_invalid",
                    message="Long entry rules must be a list.",
                    severity="error",
                    section="entry",
                    field="long",
                )
            )
        elif long_enabled and not long_rules:
            issues.append(
                ValidationIssue(
                    code="entry.long_missing",
                    message="Long trading is enabled but no long entry rule exists.",
                    severity="error",
                    section="entry",
                    field="long",
                    suggestion="Define at least one long entry condition.",
                )
            )

        if not isinstance(short_rules, list):
            issues.append(
                ValidationIssue(
                    code="entry.short_invalid",
                    message="Short entry rules must be a list.",
                    severity="error",
                    section="entry",
                    field="short",
                )
            )
        elif short_enabled and not short_rules:
            issues.append(
                ValidationIssue(
                    code="entry.short_missing",
                    message="Short trading is enabled but no short entry rule exists.",
                    severity="error",
                    section="entry",
                    field="short",
                    suggestion="Define at least one short entry condition.",
                )
            )

    def _validate_exit(
        self,
        project: ResearchProject,
        issues: list[ValidationIssue],
    ) -> None:
        direction = project.strategy.get("direction", {})
        exit_rules = project.strategy.get("exit", {})
        risk = project.strategy.get("risk", {})

        long_enabled = bool(direction.get("long_enabled", False))
        short_enabled = bool(direction.get("short_enabled", False))

        long_rules = exit_rules.get("long", [])
        short_rules = exit_rules.get("short", [])

        has_risk_exit = any(
            risk.get(field_name) is not None
            for field_name in {
                "stop_loss",
                "take_profit",
                "trailing_stop",
                "maximum_holding_bars",
            }
        )

        if long_enabled and not long_rules and not has_risk_exit:
            issues.append(
                ValidationIssue(
                    code="exit.long_missing",
                    message=(
                        "Long trading is enabled but no long exit rule "
                        "or protective exit exists."
                    ),
                    severity="error",
                    section="exit",
                    field="long",
                    suggestion=(
                        "Define an exit condition, stop loss, take profit, "
                        "trailing stop or time exit."
                    ),
                )
            )

        if short_enabled and not short_rules and not has_risk_exit:
            issues.append(
                ValidationIssue(
                    code="exit.short_missing",
                    message=(
                        "Short trading is enabled but no short exit rule "
                        "or protective exit exists."
                    ),
                    severity="error",
                    section="exit",
                    field="short",
                )
            )

    def _validate_risk(
        self,
        project: ResearchProject,
        issues: list[ValidationIssue],
    ) -> None:
        risk = project.strategy.get("risk", {})

        initial_capital = risk.get("initial_capital")

        if not self._is_positive_number(initial_capital):
            issues.append(
                ValidationIssue(
                    code="risk.initial_capital_invalid",
                    message="Initial capital must be greater than zero.",
                    severity="error",
                    section="risk",
                    field="initial_capital",
                )
            )

        method = str(
            risk.get("position_sizing_method", "")
        ).strip()

        if method not in self.ALLOWED_POSITION_SIZING_METHODS:
            issues.append(
                ValidationIssue(
                    code="risk.position_sizing_method_invalid",
                    message=f"Unsupported position sizing method: {method!r}.",
                    severity="error",
                    section="risk",
                    field="position_sizing_method",
                )
            )

        position_size = risk.get("position_size")

        if not self._is_positive_number(position_size):
            issues.append(
                ValidationIssue(
                    code="risk.position_size_invalid",
                    message="Position size must be greater than zero.",
                    severity="error",
                    section="risk",
                    field="position_size",
                )
            )
        elif (
            method == "percentage_of_equity"
            and float(position_size) > 100.0
        ):
            issues.append(
                ValidationIssue(
                    code="risk.position_size_exceeds_equity",
                    message=(
                        "Percentage-of-equity position size cannot exceed 100%."
                    ),
                    severity="error",
                    section="risk",
                    field="position_size",
                )
            )

        maximum_open_positions = risk.get("maximum_open_positions")

        if not isinstance(maximum_open_positions, int):
            issues.append(
                ValidationIssue(
                    code="risk.maximum_open_positions_invalid",
                    message="Maximum open positions must be an integer.",
                    severity="error",
                    section="risk",
                    field="maximum_open_positions",
                )
            )
        elif maximum_open_positions < 1:
            issues.append(
                ValidationIssue(
                    code="risk.maximum_open_positions_invalid",
                    message="Maximum open positions must be at least one.",
                    severity="error",
                    section="risk",
                    field="maximum_open_positions",
                )
            )

        for field_name in {
            "stop_loss",
            "take_profit",
            "trailing_stop",
        }:
            value = risk.get(field_name)

            if value is not None and not self._is_positive_number(value):
                issues.append(
                    ValidationIssue(
                        code=f"risk.{field_name}_invalid",
                        message=f"{field_name.replace('_', ' ').title()} "
                        "must be greater than zero.",
                        severity="error",
                        section="risk",
                        field=field_name,
                    )
                )

        maximum_holding_bars = risk.get("maximum_holding_bars")

        if (
            maximum_holding_bars is not None
            and (
                not isinstance(maximum_holding_bars, int)
                or maximum_holding_bars < 1
            )
        ):
            issues.append(
                ValidationIssue(
                    code="risk.maximum_holding_bars_invalid",
                    message=(
                        "Maximum holding bars must be a positive integer."
                    ),
                    severity="error",
                    section="risk",
                    field="maximum_holding_bars",
                )
            )

        if not any(
            risk.get(field_name) is not None
            for field_name in {
                "stop_loss",
                "take_profit",
                "trailing_stop",
                "maximum_holding_bars",
            }
        ):
            issues.append(
                ValidationIssue(
                    code="risk.no_protective_exit",
                    message="No protective or time-based exit has been configured.",
                    severity="warning",
                    section="risk",
                    suggestion=(
                        "Consider adding a stop loss, trailing stop, "
                        "take profit or maximum holding period."
                    ),
                )
            )

    def _validate_execution(
        self,
        project: ResearchProject,
        issues: list[ValidationIssue],
    ) -> None:
        execution = project.strategy.get("execution", {})

        order_type = str(
            execution.get("order_type", "")
        ).strip()

        if order_type not in self.ALLOWED_ORDER_TYPES:
            issues.append(
                ValidationIssue(
                    code="execution.order_type_invalid",
                    message=f"Unsupported order type: {order_type!r}.",
                    severity="error",
                    section="execution",
                    field="order_type",
                )
            )

        signal_execution = str(
            execution.get("signal_execution", "")
        ).strip()

        if signal_execution not in self.ALLOWED_EXECUTION_MODES:
            issues.append(
                ValidationIssue(
                    code="execution.signal_execution_invalid",
                    message=(
                        f"Unsupported execution mode: {signal_execution!r}."
                    ),
                    severity="error",
                    section="execution",
                    field="signal_execution",
                )
            )

        for field_name in {
            "commission_value",
            "slippage_value",
            "spread",
        }:
            value = execution.get(field_name)

            if not self._is_non_negative_number(value):
                issues.append(
                    ValidationIssue(
                        code=f"execution.{field_name}_invalid",
                        message=(
                            f"{field_name.replace('_', ' ').title()} "
                            "cannot be negative."
                        ),
                        severity="error",
                        section="execution",
                        field=field_name,
                    )
                )

        commission = execution.get("commission_value", 0.0)
        slippage = execution.get("slippage_value", 0.0)

        if float(commission or 0.0) == 0.0:
            issues.append(
                ValidationIssue(
                    code="execution.zero_commission",
                    message="The backtest assumes zero commission costs.",
                    severity="warning",
                    section="execution",
                    field="commission_value",
                )
            )

        if float(slippage or 0.0) == 0.0:
            issues.append(
                ValidationIssue(
                    code="execution.zero_slippage",
                    message="The backtest assumes zero slippage.",
                    severity="warning",
                    section="execution",
                    field="slippage_value",
                )
            )

    def _validate_metadata(
        self,
        project: ResearchProject,
        issues: list[ValidationIssue],
    ) -> None:
        metadata = project.strategy.get("metadata", {})

        name = str(metadata.get("name", "")).strip()
        description = str(metadata.get("description", "")).strip()

        if not name:
            issues.append(
                ValidationIssue(
                    code="metadata.name_missing",
                    message="The strategy has no explicit name.",
                    severity="info",
                    section="metadata",
                    field="name",
                )
            )

        if not description:
            issues.append(
                ValidationIssue(
                    code="metadata.description_missing",
                    message="The strategy has no research description.",
                    severity="info",
                    section="metadata",
                    field="description",
                )
            )

    def _calculate_completion_score(
        self,
        project: ResearchProject,
    ) -> int:
        strategy = project.strategy

        instrument = strategy.get("instrument", {})
        direction = strategy.get("direction", {})
        entry = strategy.get("entry", {})
        exit_rules = strategy.get("exit", {})
        risk = strategy.get("risk", {})
        execution = strategy.get("execution", {})

        score = 0

        if str(instrument.get("ticker", "")).strip():
            score += 20

        if (
            str(instrument.get("timeframe", "")).strip().lower()
            in self.ALLOWED_TIMEFRAMES
        ):
            score += 10

        long_enabled = bool(direction.get("long_enabled", False))
        short_enabled = bool(direction.get("short_enabled", False))

        if long_enabled or short_enabled:
            score += 10

        entry_complete = (
            (not long_enabled or bool(entry.get("long", [])))
            and
            (not short_enabled or bool(entry.get("short", [])))
        )

        if entry_complete:
            score += 20

        has_protective_exit = any(
            risk.get(field_name) is not None
            for field_name in {
                "stop_loss",
                "take_profit",
                "trailing_stop",
                "maximum_holding_bars",
            }
        )

        exit_complete = (
            (
                not long_enabled
                or bool(exit_rules.get("long", []))
                or has_protective_exit
            )
            and
            (
                not short_enabled
                or bool(exit_rules.get("short", []))
                or has_protective_exit
            )
        )

        if exit_complete:
            score += 20

        if (
            self._is_positive_number(risk.get("initial_capital"))
            and self._is_positive_number(risk.get("position_size"))
        ):
            score += 10

        if (
            str(execution.get("order_type", ""))
            in self.ALLOWED_ORDER_TYPES
            and str(execution.get("signal_execution", ""))
            in self.ALLOWED_EXECUTION_MODES
        ):
            score += 10

        return min(score, 100)

    @staticmethod
    def _is_positive_number(value: Any) -> bool:
        if isinstance(value, bool):
            return False

        try:
            return float(value) > 0.0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _is_non_negative_number(value: Any) -> bool:
        if isinstance(value, bool):
            return False

        try:
            return float(value) >= 0.0
        except (TypeError, ValueError):
            return False