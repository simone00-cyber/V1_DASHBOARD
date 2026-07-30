from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from core.ai.providers.base import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderResponseError,
)
from core.ai.providers.gemini import GeminiProvider


class FakeModels:
    def __init__(
        self,
        *,
        response_text: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response_text = response_text
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def generate_content(
        self,
        *,
        model: str,
        contents: str,
        config: Any,
    ) -> Any:
        self.calls.append(
            {
                "model": model,
                "contents": contents,
                "config": config,
            }
        )

        if self.error is not None:
            raise self.error

        return SimpleNamespace(text=self.response_text)


class FakeClient:
    def __init__(
        self,
        *,
        response_text: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.models = FakeModels(
            response_text=response_text,
            error=error,
        )


def test_missing_api_key_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "GEMINI_API_KEY",
        raising=False,
    )

    with pytest.raises(
        AIProviderConfigurationError,
        match="GEMINI_API_KEY",
    ):
        GeminiProvider()


def test_invalid_temperature_is_rejected() -> None:
    with pytest.raises(
        AIProviderConfigurationError,
        match="temperature",
    ):
        GeminiProvider(
            client=FakeClient(),
            temperature=3.0,
        )


def test_generate_returns_dictionary() -> None:
    client = FakeClient(
        response_text=(
            '{"type": "question", '
            '"message": "Qual è il ticker?"}'
        )
    )

    provider = GeminiProvider(
        client=client,
        model="test-model",
    )

    result = provider.generate(
        system_prompt="You are a strategy assistant.",
        user_prompt="Create a strategy.",
    )

    assert result == {
        "type": "question",
        "message": "Qual è il ticker?",
    }

    assert len(client.models.calls) == 1
    assert (
        client.models.calls[0]["model"]
        == "test-model"
    )
    assert (
        client.models.calls[0]["contents"]
        == "Create a strategy."
    )


def test_empty_system_prompt_is_rejected() -> None:
    provider = GeminiProvider(
        client=FakeClient(),
    )

    with pytest.raises(
        ValueError,
        match="system_prompt",
    ):
        provider.generate(
            system_prompt=" ",
            user_prompt="Create a strategy.",
        )


def test_empty_user_prompt_is_rejected() -> None:
    provider = GeminiProvider(
        client=FakeClient(),
    )

    with pytest.raises(
        ValueError,
        match="user_prompt",
    ):
        provider.generate(
            system_prompt="System prompt",
            user_prompt=" ",
        )


def test_invalid_json_is_rejected() -> None:
    provider = GeminiProvider(
        client=FakeClient(
            response_text="not valid json",
        )
    )

    with pytest.raises(
        AIProviderResponseError,
        match="invalid JSON",
    ):
        provider.generate(
            system_prompt="System prompt",
            user_prompt="User prompt",
        )


def test_json_array_is_rejected() -> None:
    provider = GeminiProvider(
        client=FakeClient(
            response_text='["question"]',
        )
    )

    with pytest.raises(
        AIProviderResponseError,
        match="JSON object",
    ):
        provider.generate(
            system_prompt="System prompt",
            user_prompt="User prompt",
        )


def test_empty_response_is_rejected() -> None:
    provider = GeminiProvider(
        client=FakeClient(
            response_text=" ",
        )
    )

    with pytest.raises(
        AIProviderResponseError,
        match="empty response",
    ):
        provider.generate(
            system_prompt="System prompt",
            user_prompt="User prompt",
        )


def test_missing_response_text_is_rejected() -> None:
    provider = GeminiProvider(
        client=FakeClient(
            response_text=None,
        )
    )

    with pytest.raises(
        AIProviderResponseError,
        match="no textual response",
    ):
        provider.generate(
            system_prompt="System prompt",
            user_prompt="User prompt",
        )


def test_sdk_error_is_wrapped() -> None:
    provider = GeminiProvider(
        client=FakeClient(
            error=RuntimeError("network unavailable"),
        )
    )

    with pytest.raises(
        AIProviderError,
        match="Gemini request failed",
    ):
        provider.generate(
            system_prompt="System prompt",
            user_prompt="User prompt",
        )


def test_model_can_be_loaded_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "GEMINI_MODEL",
        "custom-gemini-model",
    )

    provider = GeminiProvider(
        client=FakeClient(),
    )

    assert provider.model == "custom-gemini-model"