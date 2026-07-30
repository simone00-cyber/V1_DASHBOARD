from core.ai.research_project import ResearchProject
from core.ai.strategy_validator import StrategyValidator


def build_complete_project() -> ResearchProject:
    project = ResearchProject()
    project.set_ticker("AAPL")

    project.strategy["instrument"]["start_date"] = "2015-01-01"
    project.strategy["instrument"]["end_date"] = "2025-12-31"

    project.strategy["entry"]["long"] = [
        {
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
    ]

    project.strategy["exit"]["long"] = [
        {
            "type": "condition",
            "left": {
                "kind": "indicator",
                "name": "RSI",
                "parameters": {
                    "period": 14,
                },
            },
            "operator": ">",
            "right": {
                "kind": "constant",
                "value": 70,
            },
        }
    ]

    project.strategy["risk"]["stop_loss"] = 5.0
    project.strategy["execution"]["commission_value"] = 0.1
    project.strategy["execution"]["slippage_value"] = 0.05

    return project


def test_empty_project_is_not_valid() -> None:
    validator = StrategyValidator()
    project = ResearchProject()

    health = validator.validate(project)

    assert health.is_valid is False
    assert health.is_ready_for_review is False
    assert health.can_be_approved is False
    assert health.completion_score < 100
    assert health.error_count >= 1


def test_missing_ticker_is_blocking() -> None:
    validator = StrategyValidator()
    project = ResearchProject()

    project.strategy["entry"]["long"] = [
        {"type": "condition"}
    ]
    project.strategy["exit"]["long"] = [
        {"type": "condition"}
    ]

    health = validator.validate(project)

    codes = {
        issue.code
        for issue in health.errors
    }

    assert "instrument.ticker_missing" in codes


def test_long_entry_is_required_when_long_is_enabled() -> None:
    validator = StrategyValidator()
    project = ResearchProject()
    project.set_ticker("AAPL")
    project.strategy["exit"]["long"] = [
        {"type": "condition"}
    ]

    health = validator.validate(project)

    codes = {
        issue.code
        for issue in health.errors
    }

    assert "entry.long_missing" in codes


def test_exit_can_be_satisfied_by_stop_loss() -> None:
    validator = StrategyValidator()
    project = ResearchProject()
    project.set_ticker("AAPL")

    project.strategy["entry"]["long"] = [
        {"type": "condition"}
    ]
    project.strategy["risk"]["stop_loss"] = 5.0

    health = validator.validate(project)

    codes = {
        issue.code
        for issue in health.errors
    }

    assert "exit.long_missing" not in codes


def test_short_rules_are_required_when_short_is_enabled() -> None:
    validator = StrategyValidator()
    project = build_complete_project()

    project.strategy["direction"]["short_enabled"] = True

    health = validator.validate(project)

    codes = {
        issue.code
        for issue in health.errors
    }

    assert "entry.short_missing" in codes
    assert "exit.short_missing" not in codes


def test_invalid_position_size_is_blocking() -> None:
    validator = StrategyValidator()
    project = build_complete_project()

    project.strategy["risk"]["position_size"] = 150.0

    health = validator.validate(project)

    codes = {
        issue.code
        for issue in health.errors
    }

    assert "risk.position_size_exceeds_equity" in codes


def test_zero_costs_generate_warnings() -> None:
    validator = StrategyValidator()
    project = build_complete_project()

    project.strategy["execution"]["commission_value"] = 0.0
    project.strategy["execution"]["slippage_value"] = 0.0

    health = validator.validate(project)

    codes = {
        issue.code
        for issue in health.warnings
    }

    assert "execution.zero_commission" in codes
    assert "execution.zero_slippage" in codes


def test_complete_project_is_ready_for_review() -> None:
    validator = StrategyValidator()
    project = build_complete_project()

    health = validator.validate(project)

    assert health.error_count == 0
    assert health.is_valid is True
    assert health.completion_score == 100
    assert health.is_ready_for_review is True
    assert health.can_be_approved is True


def test_apply_project_status_marks_ready_for_review() -> None:
    validator = StrategyValidator()
    project = build_complete_project()

    health = validator.apply_project_status(project)

    assert health.is_ready_for_review is True
    assert project.status == "ready_for_review"


def test_apply_project_status_marks_incomplete_project() -> None:
    validator = StrategyValidator()
    project = ResearchProject()

    validator.apply_project_status(project)

    assert project.status == "strategy_incomplete"


def test_strategy_health_serialization() -> None:
    validator = StrategyValidator()
    project = ResearchProject()

    health = validator.validate(project)
    payload = health.to_dict()

    assert "issues" in payload
    assert "completion_score" in payload
    assert "error_count" in payload
    assert isinstance(payload["issues"], list)