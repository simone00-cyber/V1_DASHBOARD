from __future__ import annotations

from typing import Any

from core.ai.providers.base import AIProvider


class SessionLLMAdapter:
    """
    Adapts the provider interface to the interface currently expected
    by AIStrategySession.

    This is intentionally small and can be removed when AIStrategySession
    natively supports separate system and user prompts.
    """

    SYSTEM_INSTRUCTION = (
        "You are the AI engine of a quantitative strategy research "
        "platform. Follow every instruction contained in the supplied "
        "prompt. Return one valid JSON object only."
    )

    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def generate_json(
        self,
        prompt: str,
    ) -> dict[str, Any]:
        if not isinstance(prompt, str):
            raise TypeError("Prompt must be a string.")

        normalized_prompt = prompt.strip()

        if not normalized_prompt:
            raise ValueError("Prompt cannot be empty.")

        return self.provider.generate(
            system_prompt=self.SYSTEM_INSTRUCTION,
            user_prompt=normalized_prompt,
        )