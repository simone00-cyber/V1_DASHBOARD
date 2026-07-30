from pathlib import Path

import pytest

from core.ai.context_builder import AIContext
from core.ai.prompt_manager import (
    PromptManager,
    PromptManagerConfig,
    PromptManagerError,
)


def create_prompt_directory(
    root: Path,
) -> Path:
    prompts = root / "prompts"
    states = prompts / "states"

    states.mkdir(parents=True)

    files = {
        prompts / "system.md": "System instructions.",
        prompts / "conversation.md": "Conversation rules.",
        prompts / "validation.md": "Validation rules.",
        prompts / "review.md": "Review rules.",
        states / "new.md": "New state instructions.",
        states / "asking_ticker.md": (
            "Ticker state instructions."
        ),
        states / "ready_for_review.md": (
            "Review state instructions."
        ),
    }

    for path, content in files.items():
        path.write_text(
            content,
            encoding="utf-8",
        )

    return prompts


def build_context(
    state: str = "asking_ticker",
) -> AIContext:
    return AIContext(
        protocol_version="1.0",
        conversation_state=state,
        project={
            "id": "project-1",
            "name": "Research Project",
        },
        strategy={
            "instrument": {
                "ticker": "",
            }
        },
        validation={
            "is_valid": False,
            "issues": [],
        },
        conversation_history=[],
        user_message="AAPL",
        instructions={
            "response_format": "llm_protocol_json",
        },
    )


def test_prompt_manager_loads_prompt(
    tmp_path: Path,
) -> None:
    prompts = create_prompt_directory(tmp_path)

    manager = PromptManager(
        PromptManagerConfig(
            prompts_directory=prompts,
        )
    )

    assert (
        manager.load_prompt("system.md")
        == "System instructions."
    )


def test_prompt_manager_loads_state_prompt(
    tmp_path: Path,
) -> None:
    prompts = create_prompt_directory(tmp_path)

    manager = PromptManager(
        PromptManagerConfig(
            prompts_directory=prompts,
        )
    )

    assert (
        manager.load_state_prompt("asking_ticker")
        == "Ticker state instructions."
    )


def test_missing_prompt_raises_error(
    tmp_path: Path,
) -> None:
    prompts = create_prompt_directory(tmp_path)

    manager = PromptManager(
        PromptManagerConfig(
            prompts_directory=prompts,
        )
    )

    with pytest.raises(PromptManagerError):
        manager.load_prompt("missing.md")


def test_empty_prompt_raises_error(
    tmp_path: Path,
) -> None:
    prompts = create_prompt_directory(tmp_path)
    empty_prompt = prompts / "empty.md"
    empty_prompt.write_text("", encoding="utf-8")

    manager = PromptManager(
        PromptManagerConfig(
            prompts_directory=prompts,
        )
    )

    with pytest.raises(PromptManagerError):
        manager.load_prompt("empty.md")


def test_directory_traversal_is_rejected(
    tmp_path: Path,
) -> None:
    prompts = create_prompt_directory(tmp_path)

    manager = PromptManager(
        PromptManagerConfig(
            prompts_directory=prompts,
        )
    )

    with pytest.raises(PromptManagerError):
        manager.load_prompt("../secret.md")


def test_build_prompt_contains_all_sections(
    tmp_path: Path,
) -> None:
    prompts = create_prompt_directory(tmp_path)

    manager = PromptManager(
        PromptManagerConfig(
            prompts_directory=prompts,
        )
    )

    prompt = manager.build_prompt(
        build_context()
    )

    assert "SYSTEM INSTRUCTIONS" in prompt
    assert "CURRENT WORKFLOW STATE" in prompt
    assert "CONVERSATION RULES" in prompt
    assert "VALIDATION RULES" in prompt
    assert "RUNTIME CONTEXT" in prompt
    assert "RESPONSE REQUIREMENT" in prompt
    assert "Ticker state instructions." in prompt
    assert '"user_message": "AAPL"' in prompt


def test_review_prompt_only_used_during_review(
    tmp_path: Path,
) -> None:
    prompts = create_prompt_directory(tmp_path)

    manager = PromptManager(
        PromptManagerConfig(
            prompts_directory=prompts,
        )
    )

    normal_prompt = manager.build_prompt(
        build_context("asking_ticker")
    )
    review_prompt = manager.build_prompt(
        build_context("ready_for_review")
    )

    assert "REVIEW AND APPROVAL RULES" not in normal_prompt
    assert "REVIEW AND APPROVAL RULES" in review_prompt
    assert "Review rules." in review_prompt


def test_prompt_components_can_be_disabled(
    tmp_path: Path,
) -> None:
    prompts = create_prompt_directory(tmp_path)

    manager = PromptManager(
        PromptManagerConfig(
            prompts_directory=prompts,
            include_conversation_prompt=False,
            include_validation_prompt=False,
        )
    )

    prompt = manager.build_prompt(
        build_context()
    )

    assert "CONVERSATION RULES" not in prompt
    assert "VALIDATION RULES" not in prompt


def test_validate_prompt_files(
    tmp_path: Path,
) -> None:
    prompts = create_prompt_directory(tmp_path)

    manager = PromptManager(
        PromptManagerConfig(
            prompts_directory=prompts,
        )
    )

    assert manager.validate_prompt_files() == []

    (prompts / "review.md").unlink()

    assert manager.validate_prompt_files() == [
        "review.md"
    ]


def test_prompt_cache_can_be_cleared(
    tmp_path: Path,
) -> None:
    prompts = create_prompt_directory(tmp_path)

    manager = PromptManager(
        PromptManagerConfig(
            prompts_directory=prompts,
        )
    )

    first = manager.load_prompt("system.md")

    (prompts / "system.md").write_text(
        "Updated instructions.",
        encoding="utf-8",
    )

    cached = manager.load_prompt("system.md")

    assert cached == first

    manager.clear_cache()

    updated = manager.load_prompt("system.md")

    assert updated == "Updated instructions."


def test_invalid_state_name_is_rejected(
    tmp_path: Path,
) -> None:
    prompts = create_prompt_directory(tmp_path)

    manager = PromptManager(
        PromptManagerConfig(
            prompts_directory=prompts,
        )
    )

    with pytest.raises(PromptManagerError):
        manager.load_state_prompt("../error")


def test_compact_json_configuration(
    tmp_path: Path,
) -> None:
    prompts = create_prompt_directory(tmp_path)

    manager = PromptManager(
        PromptManagerConfig(
            prompts_directory=prompts,
            pretty_json=False,
        )
    )

    prompt = manager.build_prompt(
        build_context()
    )

    assert '"user_message": "AAPL"' in prompt