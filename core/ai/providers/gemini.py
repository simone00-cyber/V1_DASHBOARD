from __future__ import annotations

import json
import os
from typing import Any

from google import genai
from google.genai import types

from core.ai.providers.base import (
    AIProvider,
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderResponseError,
)


class GeminiProvider(AIProvider):
    """
    Google Gemini implementation of the AIProvider interface.

    The rest of the application receives only dictionaries and does
    not depend directly on the Google SDK.
    """

    DEFAULT_MODEL = "gemini-flash-latest"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        client: Any | None = None,
    ) -> None:
        resolved_api_key = api_key or os.getenv("GEMINI_API_KEY")
        resolved_model = (
            model
            or os.getenv("GEMINI_MODEL")
            or self.DEFAULT_MODEL
        )

        if client is None and not resolved_api_key:
            raise AIProviderConfigurationError(
                "GEMINI_API_KEY is not configured."
            )

        if not resolved_model.strip():
            raise AIProviderConfigurationError(
                "Gemini model name cannot be empty."
            )

        if not 0.0 <= temperature <= 2.0:
            raise AIProviderConfigurationError(
                "Gemini temperature must be between 0 and 2."
            )

        self.model = resolved_model.strip()
        self.temperature = temperature
        self._client = (
            client
            if client is not None
            else genai.Client(api_key=resolved_api_key)
        )

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        system_prompt = self._require_prompt(
            system_prompt,
            name="system_prompt",
        )
        user_prompt = self._require_prompt(
            user_prompt,
            name="user_prompt",
        )

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=self.temperature,
                    response_mime_type="application/json",
                ),
            )
        except Exception as exc:
            raise AIProviderError(
                f"Gemini request failed: {exc}"
            ) from exc

        response_text = getattr(response, "text", None)

        if not isinstance(response_text, str):
            raise AIProviderResponseError(
                "Gemini returned no textual response."
            )

        response_text = response_text.strip()

        if not response_text:
            raise AIProviderResponseError(
                "Gemini returned an empty response."
            )

        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise AIProviderResponseError(
                "Gemini returned invalid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise AIProviderResponseError(
                "Gemini response must be a JSON object."
            )

        return payload

    @staticmethod
    def _require_prompt(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string.")

        normalized = value.strip()

        if not normalized:
            raise ValueError(f"{name} cannot be empty.")

        return normalized