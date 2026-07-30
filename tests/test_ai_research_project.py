import pytest

from core.ai.research_project import ResearchProject


def test_project_has_default_strategy_structure() -> None:
    project = ResearchProject()

    assert project.strategy["schema_version"] == "1.0"
    assert "instrument" in project.strategy
    assert "entry" in project.strategy
    assert "exit" in project.strategy
    assert "risk" in project.strategy
    assert "execution" in project.strategy


def test_project_sets_ticker_and_updates_name() -> None:
    project = ResearchProject()

    project.set_ticker(" aapl ")

    assert project.ticker == "AAPL"
    assert project.name == "AAPL Research Project"
    assert project.status == "strategy_incomplete"


def test_project_rejects_empty_ticker() -> None:
    project = ResearchProject()

    with pytest.raises(ValueError):
        project.set_ticker("   ")


def test_project_validates_timeframe() -> None:
    project = ResearchProject()

    project.set_timeframe("1D")

    assert project.timeframe == "1d"

    with pytest.raises(ValueError):
        project.set_timeframe("7h")


def test_strategy_change_revokes_previous_approval() -> None:
    project = ResearchProject()
    project.set_ticker("AAPL")
    project.approve_strategy()

    approved_version = project.strategy_version

    assert project.is_approved is True
    assert project.approved_strategy_version == approved_version

    project.set_timeframe("1wk")

    assert project.is_approved is False
    assert project.approved_strategy_version is None
    assert project.strategy_version == approved_version + 1


def test_project_adds_notes() -> None:
    project = ResearchProject()

    note = project.add_note(
        "Test the strategy during high-volatility regimes."
    )

    assert len(project.notes) == 1
    assert note.content == (
        "Test the strategy during high-volatility regimes."
    )


def test_project_registers_result_ids_without_duplicates() -> None:
    project = ResearchProject()

    project.register_backtest("backtest-001")
    project.register_backtest("backtest-001")
    project.register_optimization("optimization-001")

    assert project.backtest_ids == ["backtest-001"]
    assert project.optimization_ids == ["optimization-001"]


def test_project_serialization_round_trip() -> None:
    project = ResearchProject(
        name="EMA Pullback Research",
        description="Research project for an EMA pullback strategy.",
    )

    project.set_ticker("ENI.MI")
    project.conversation.add_user_message(
        "Create a trend-following pullback strategy."
    )
    project.add_note("Initial research hypothesis.")
    project.register_backtest("bt-001")

    restored = ResearchProject.from_dict(project.to_dict())

    assert restored.id == project.id
    assert restored.name == project.name
    assert restored.ticker == "ENI.MI"
    assert restored.conversation.message_count() == 1
    assert restored.notes[0].content == "Initial research hypothesis."
    assert restored.backtest_ids == ["bt-001"]


def test_project_cannot_be_approved_without_ticker() -> None:
    project = ResearchProject()

    with pytest.raises(ValueError):
        project.approve_strategy()