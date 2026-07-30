from __future__ import annotations

from analysis.regime.models import RegimeLayer, RegimePillar
from views.overview import _fallback_briefing_text

_BANNED_WORDS = [
    "structural", "structurally",
    "tactical", "tactically",
    "score", "confidence", "pillar", "regime", "coverage",
]


def _pillar(name: str, state: str) -> RegimePillar:
    return RegimePillar(
        name=name,
        score=0.0,
        state=state,
        details=f"{name} detail",
        available_inputs=3,
        expected_inputs=3,
    )


def _layer(key: str, diagnosis: str, previous_diagnosis: str, pillar_states: dict[str, str]) -> RegimeLayer:
    return RegimeLayer(
        key=key,
        title=key.title(),
        horizon="n/a",
        diagnosis=diagnosis,
        score=0.0,
        previous_diagnosis=previous_diagnosis,
        previous_score=0.0,
        pillars=[_pillar(name, state) for name, state in pillar_states.items()],
    )


def _regime_results(strategic: dict[str, str], tactical: dict[str, str], daily: dict[str, str]) -> dict:
    return {
        "STRATEGIC": _layer("STRATEGIC", "CONSTRUCTIVE", "NEUTRAL / TRANSITION", strategic),
        "TACTICAL": _layer("TACTICAL", "STABLE / MIXED", "IMPROVING", tactical),
        "DAILY": _layer("DAILY", "MIXED", "RISK-ON", daily),
    }


def _reading(positive: int = 8, total: int = 16) -> dict:
    return {"leader": None, "laggard": None, "vix": None, "positive": positive, "total": total}


def _uniform_states(state: str) -> dict[str, str]:
    return {
        "EQUITY": state,
        "RATES": state,
        "CREDIT": state,
        "MACRO": state,
        "VOLATILITY": state,
    }


def test_briefing_never_exposes_internal_model_vocabulary() -> None:
    regime_results = _regime_results(
        _uniform_states("POSITIVE"),
        _uniform_states("NEUTRAL"),
        _uniform_states("NEGATIVE"),
    )

    text = _fallback_briefing_text(_reading(), regime_results).lower()

    for banned in _BANNED_WORDS:
        assert banned not in text, f"leaked internal vocabulary: {banned!r}"


def test_briefing_contains_the_three_required_closing_sections() -> None:
    regime_results = _regime_results(
        _uniform_states("POSITIVE"),
        _uniform_states("POSITIVE"),
        _uniform_states("POSITIVE"),
    )

    text = _fallback_briefing_text(_reading(), regime_results)

    assert "**Portfolio Implications**" in text
    assert "**Key Risks**" in text
    assert "**Questions Worth Investigating**" in text
    # Order matters: implications, then risks, then questions.
    assert (
        text.index("**Portfolio Implications**")
        < text.index("**Key Risks**")
        < text.index("**Questions Worth Investigating**")
    )


def test_rising_yields_are_described_as_a_headwind_not_a_tailwind() -> None:
    # RATES pillar STRONGLY NEGATIVE == yields rising sharply in the real
    # engine's sign convention (see analysis/regime/strategic.py). The
    # briefing must never flip this into tailwind language.
    regime_results = _regime_results(
        {**_uniform_states("NEUTRAL"), "RATES": "STRONGLY NEGATIVE"},
        {**_uniform_states("NEUTRAL"), "RATES": "STRONGLY NEGATIVE"},
        {**_uniform_states("NEUTRAL"), "RATES": "STRONGLY NEGATIVE"},
    )

    text = _fallback_briefing_text(_reading(), regime_results).lower()

    assert "risen" in text or "tightening financial conditions" in text
    assert "fallen meaningfully" not in text


def test_falling_yields_are_described_as_supportive() -> None:
    regime_results = _regime_results(
        {**_uniform_states("NEUTRAL"), "RATES": "STRONGLY POSITIVE"},
        {**_uniform_states("NEUTRAL"), "RATES": "STRONGLY POSITIVE"},
        {**_uniform_states("NEUTRAL"), "RATES": "STRONGLY POSITIVE"},
    )

    text = _fallback_briefing_text(_reading(), regime_results).lower()

    assert "fallen meaningfully" in text or "eas" in text


def test_no_regime_data_returns_a_graceful_message() -> None:
    text = _fallback_briefing_text(_reading(), {})

    assert text
    assert "don't have" in text.lower()


def test_narrative_sentences_join_grammatically() -> None:
    regime_results = _regime_results(
        {"EQUITY": "STRONGLY POSITIVE", "RATES": "STRONGLY NEGATIVE", "CREDIT": "STRONGLY POSITIVE", "MACRO": "NEUTRAL", "VOLATILITY": "STRONGLY NEGATIVE"},
        {"EQUITY": "STRONGLY POSITIVE", "RATES": "STRONGLY NEGATIVE", "CREDIT": "STRONGLY POSITIVE", "MACRO": "NEUTRAL", "VOLATILITY": "STRONGLY NEGATIVE"},
        {"EQUITY": "STRONGLY POSITIVE", "RATES": "STRONGLY NEGATIVE", "CREDIT": "STRONGLY POSITIVE", "MACRO": "NEUTRAL", "VOLATILITY": "STRONGLY NEGATIVE"},
    )

    text = _fallback_briefing_text(_reading(), regime_results)
    narrative = text.split("\n\n")[0]

    # No connector should be immediately followed by a capitalized word
    # (that pattern is the "Meanwhile, Equity leadership..." bug).
    for connector in ("Meanwhile, ", "At the same time, ", "In parallel, "):
        if connector in narrative:
            after = narrative.split(connector, 1)[1]
            assert after[0].islower(), f"'{connector}' is followed by a capitalized word"
