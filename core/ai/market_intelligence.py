from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.ai.providers.base import AIProviderError
from core.ai.providers.gemini import GeminiProvider

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_QA_PROMPT_PATH = _PROMPTS_DIR / "market_intelligence.md"
_BRIEFING_PROMPT_PATH = _PROMPTS_DIR / "daily_briefing.md"


class MarketIntelligenceError(RuntimeError):
    """Raised when the market intelligence assistant cannot produce an answer."""


def _load_prompt(path: Path) -> str:
    content = path.read_text(encoding="utf-8").strip()

    if not content:
        raise MarketIntelligenceError(f"Prompt file is empty: {path.name}")

    return content


def _generate_answer(
    provider: GeminiProvider,
    *,
    system_prompt: str,
    user_prompt: str,
) -> str:
    try:
        raw_response = provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    except AIProviderError as exc:
        raise MarketIntelligenceError(str(exc)) from exc

    answer = raw_response.get("answer")

    if not isinstance(answer, str) or not answer.strip():
        raise MarketIntelligenceError(
            "The assistant returned an empty or invalid answer."
        )

    return answer.strip()


def ask_market_intelligence(
    provider: GeminiProvider,
    *,
    context: dict[str, Any],
    history: list[dict[str, str]],
    question: str,
) -> str:
    """
    Answer a free-text market question, grounded only in the supplied context.

    Reuses the existing GeminiProvider exactly as built for the AI Strategy
    Lab. The only difference is the prompt: this mode returns a single
    conversational "answer" field instead of the strategy-operations JSON
    protocol, so it never touches AIStrategySession, StrategyParser or the
    strategy DSL.
    """

    normalized_question = question.strip()

    if not normalized_question:
        raise ValueError("Question cannot be empty.")

    user_payload = {
        "market_context": context,
        "conversation_history": history[-6:],
        "question": normalized_question,
    }
    user_prompt = (
        "Respond to the question using only the market context below. "
        'Return one JSON object: {"answer": "<plain text response>"}. '
        "No markdown, no code fences, no extra fields.\n\n"
        + json.dumps(user_payload, ensure_ascii=False, default=str)
    )

    return _generate_answer(
        provider,
        system_prompt=_load_prompt(_QA_PROMPT_PATH),
        user_prompt=user_prompt,
    )


def generate_daily_briefing(
    provider: GeminiProvider,
    *,
    context: dict[str, Any],
) -> str:
    """
    Proactively synthesize today's market context into a short CIO-style
    briefing, delivered as the assistant's opening message before the user
    asks anything. Grounded only in the supplied context — same provider,
    same JSON contract as ask_market_intelligence, different framing.
    """

    user_payload = {"market_context": context}
    user_prompt = (
        "Write today's proactive briefing using only the market context "
        'below. Return one JSON object: {"answer": "<plain text briefing>"}. '
        "No markdown, no code fences, no extra fields.\n\n"
        + json.dumps(user_payload, ensure_ascii=False, default=str)
    )

    return _generate_answer(
        provider,
        system_prompt=_load_prompt(_BRIEFING_PROMPT_PATH),
        user_prompt=user_prompt,
    )
