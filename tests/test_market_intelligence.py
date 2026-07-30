from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from core.ai.market_intelligence import (
    MarketIntelligenceError,
    ask_market_intelligence,
    generate_daily_briefing,
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
            {"model": model, "contents": contents, "config": config}
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
        self.models = FakeModels(response_text=response_text, error=error)


def _provider(**kwargs: Any) -> GeminiProvider:
    return GeminiProvider(client=FakeClient(**kwargs))


def test_ask_market_intelligence_returns_answer() -> None:
    provider = _provider(response_text='{"answer": "Markets are mixed today."}')

    answer = ask_market_intelligence(
        provider,
        context={"regime": "TACTICAL: IMPROVING"},
        history=[],
        question="Why is the market mixed today?",
    )

    assert answer == "Markets are mixed today."


def test_ask_market_intelligence_sends_context_and_question() -> None:
    provider = _provider(response_text='{"answer": "ok"}')

    ask_market_intelligence(
        provider,
        context={"vix": 18.2},
        history=[{"role": "user", "content": "hello"}],
        question="What should I monitor next?",
    )

    call = provider._client.models.calls[0]
    assert "What should I monitor next?" in call["contents"]
    assert "18.2" in call["contents"]


def test_empty_question_is_rejected() -> None:
    provider = _provider(response_text='{"answer": "ok"}')

    with pytest.raises(ValueError):
        ask_market_intelligence(
            provider,
            context={},
            history=[],
            question="   ",
        )


def test_missing_answer_field_raises_market_intelligence_error() -> None:
    provider = _provider(response_text='{"unexpected": "value"}')

    with pytest.raises(MarketIntelligenceError):
        ask_market_intelligence(
            provider,
            context={},
            history=[],
            question="Why is the market mixed today?",
        )


def test_blank_answer_field_raises_market_intelligence_error() -> None:
    provider = _provider(response_text='{"answer": "   "}')

    with pytest.raises(MarketIntelligenceError):
        ask_market_intelligence(
            provider,
            context={},
            history=[],
            question="Why is the market mixed today?",
        )


def test_provider_error_is_wrapped() -> None:
    provider = _provider(error=RuntimeError("network unavailable"))

    with pytest.raises(MarketIntelligenceError, match="Gemini request failed"):
        ask_market_intelligence(
            provider,
            context={},
            history=[],
            question="Why is the market mixed today?",
        )


def test_history_is_truncated_to_last_six_messages() -> None:
    provider = _provider(response_text='{"answer": "ok"}')
    history = [
        {"role": "user", "content": f"message {index}"}
        for index in range(10)
    ]

    ask_market_intelligence(
        provider,
        context={},
        history=history,
        question="What should I monitor next?",
    )

    call = provider._client.models.calls[0]
    assert "message 0" not in call["contents"]
    assert "message 9" in call["contents"]


def test_generate_daily_briefing_returns_answer() -> None:
    provider = _provider(
        response_text='{"answer": "The tactical regime is stable to mixed today."}'
    )

    briefing = generate_daily_briefing(
        provider,
        context={"regime": {"TACTICAL": {"diagnosis": "STABLE / MIXED"}}},
    )

    assert briefing == "The tactical regime is stable to mixed today."


def test_generate_daily_briefing_sends_context_only() -> None:
    provider = _provider(response_text='{"answer": "ok"}')

    generate_daily_briefing(provider, context={"vix": 18.2})

    call = provider._client.models.calls[0]
    assert "18.2" in call["contents"]
    assert "proactive briefing" in call["contents"].lower()


def test_generate_daily_briefing_wraps_provider_error() -> None:
    provider = _provider(error=RuntimeError("network unavailable"))

    with pytest.raises(MarketIntelligenceError, match="Gemini request failed"):
        generate_daily_briefing(provider, context={})


def test_daily_briefing_and_qa_use_different_system_prompts() -> None:
    provider = _provider(response_text='{"answer": "ok"}')

    generate_daily_briefing(provider, context={})
    ask_market_intelligence(provider, context={}, history=[], question="Hi?")

    briefing_config = provider._client.models.calls[0]["config"]
    qa_config = provider._client.models.calls[1]["config"]

    assert (
        briefing_config.system_instruction
        != qa_config.system_instruction
    )
