from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.ai.context_builder import AIContext


class PromptManagerError(RuntimeError):
    """Raised when a prompt cannot be loaded or composed safely."""


@dataclass(slots=True)
class PromptManagerConfig:
    prompts_directory: Path | None = None
    include_conversation_prompt: bool = True
    include_validation_prompt: bool = True
    include_review_prompt: bool = True
    pretty_json: bool = True

    def __post_init__(self) -> None:
        if self.prompts_directory is None:
            self.prompts_directory = (
                Path(__file__).resolve().parent / "prompts"
            )

        self.prompts_directory = Path(self.prompts_directory)


class PromptManager:
    """
    Loads prompt instructions from Markdown files and composes the final
    stateless prompt sent to the language model.

    Prompt text must never be hardcoded in the Python implementation.
    """

    REQUIRED_PROMPTS = {
        "system.md",
        "conversation.md",
        "validation.md",
        "review.md",
    }

    def __init__(
        self,
        config: PromptManagerConfig | None = None,
    ) -> None:
        self.config = config or PromptManagerConfig()
        self.prompts_directory = self.config.prompts_directory

        if self.prompts_directory is None:
            raise PromptManagerError(
                "The prompts directory has not been configured."
            )

        self.states_directory = self.prompts_directory / "states"
        self._cache: dict[Path, str] = {}

    def build_prompt(self, context: AIContext) -> str:
        """
        Compose the complete prompt expected by AIStrategySession.
        """

        sections: list[str] = [
            self._build_section(
                title="SYSTEM INSTRUCTIONS",
                content=self.load_prompt("system.md"),
            ),
            self._build_section(
                title="CURRENT WORKFLOW STATE",
                content=self.load_state_prompt(
                    context.conversation_state
                ),
            ),
        ]

        if self.config.include_conversation_prompt:
            sections.append(
                self._build_section(
                    title="CONVERSATION RULES",
                    content=self.load_prompt("conversation.md"),
                )
            )

        if self.config.include_validation_prompt:
            sections.append(
                self._build_section(
                    title="VALIDATION RULES",
                    content=self.load_prompt("validation.md"),
                )
            )

        if (
            self.config.include_review_prompt
            and context.conversation_state
            in {
                "ready_for_review",
                "approved",
            }
        ):
            sections.append(
                self._build_section(
                    title="REVIEW AND APPROVAL RULES",
                    content=self.load_prompt("review.md"),
                )
            )

        sections.append(
            self._build_section(
                title="RUNTIME CONTEXT",
                content=self._serialize_context(context),
            )
        )

        sections.append(
            self._build_section(
                title="RESPONSE REQUIREMENT",
                content=(
                    "Return one valid JSON object only. "
                    "The JSON must conform to the LLM protocol included "
                    "in the system instructions. Do not return Markdown, "
                    "code fences, explanations or text outside the JSON."
                ),
            )
        )

        prompt = "\n\n".join(
            section
            for section in sections
            if section.strip()
        ).strip()

        if not prompt:
            raise PromptManagerError(
                "The composed prompt is empty."
            )

        return prompt

    def load_prompt(self, filename: str) -> str:
        normalized_filename = filename.strip()

        if not normalized_filename:
            raise PromptManagerError(
                "Prompt filename cannot be empty."
            )

        if Path(normalized_filename).name != normalized_filename:
            raise PromptManagerError(
                "Prompt filename must not contain directory traversal."
            )

        path = self.prompts_directory / normalized_filename
        return self._read_prompt_file(path)

    def load_state_prompt(self, state: str) -> str:
        normalized_state = state.strip().lower()

        if not normalized_state:
            raise PromptManagerError(
                "Conversation state cannot be empty."
            )

        if not all(
            character.isalnum() or character == "_"
            for character in normalized_state
        ):
            raise PromptManagerError(
                f"Unsupported conversation state: {state!r}."
            )

        path = self.states_directory / f"{normalized_state}.md"
        return self._read_prompt_file(path)

    def validate_prompt_files(self) -> list[str]:
        """
        Return the list of missing required prompt files.
        """

        missing: list[str] = []

        for filename in sorted(self.REQUIRED_PROMPTS):
            path = self.prompts_directory / filename

            if not path.is_file():
                missing.append(filename)

        return missing

    def clear_cache(self) -> None:
        self._cache.clear()

    def _read_prompt_file(self, path: Path) -> str:
        resolved_path = path.resolve()
        resolved_root = self.prompts_directory.resolve()

        try:
            resolved_path.relative_to(resolved_root)
        except ValueError as exc:
            raise PromptManagerError(
                "Prompt path is outside the configured prompt directory."
            ) from exc

        if resolved_path in self._cache:
            return self._cache[resolved_path]

        if not resolved_path.is_file():
            raise PromptManagerError(
                f"Prompt file not found: {resolved_path}"
            )

        try:
            content = resolved_path.read_text(
                encoding="utf-8"
            ).strip()
        except OSError as exc:
            raise PromptManagerError(
                f"Unable to read prompt file: {resolved_path}"
            ) from exc

        if not content:
            raise PromptManagerError(
                f"Prompt file is empty: {resolved_path}"
            )

        self._cache[resolved_path] = content
        return content

    def _serialize_context(
        self,
        context: AIContext,
    ) -> str:
        payload: dict[str, Any] = context.to_dict()

        try:
            return json.dumps(
                payload,
                ensure_ascii=False,
                indent=2 if self.config.pretty_json else None,
                sort_keys=True,
                default=str,
            )
        except (TypeError, ValueError) as exc:
            raise PromptManagerError(
                "The AI context could not be serialized to JSON."
            ) from exc

    @staticmethod
    def _build_section(
        title: str,
        content: str,
    ) -> str:
        normalized_title = title.strip()
        normalized_content = content.strip()

        if not normalized_title:
            raise PromptManagerError(
                "Prompt section title cannot be empty."
            )

        if not normalized_content:
            raise PromptManagerError(
                f"Prompt section {normalized_title!r} is empty."
            )

        return (
            f"===== {normalized_title} =====\n"
            f"{normalized_content}"
        )