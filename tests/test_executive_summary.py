from __future__ import annotations

import pytest

from ui.executive_summary import investment_horizon_label, recommended_action_phrase

_KNOWN_LABELS = (
    "High Conviction Buy",
    "Buy",
    "High Conviction Sell / Avoid",
    "Sell / Avoid",
    "Excellent Company, Poor Timing — Wait",
    "Weak Company, Strong Momentum — Caution",
    "Hold / Mixed Signals",
    "Partial View — Data Insufficient",
)


@pytest.mark.parametrize("overall_label", _KNOWN_LABELS)
def test_investment_horizon_label_covers_every_combined_thesis_label(overall_label):
    result = investment_horizon_label(overall_label)
    assert isinstance(result, str)
    assert result


@pytest.mark.parametrize("overall_label", _KNOWN_LABELS)
def test_recommended_action_phrase_covers_every_combined_thesis_label(overall_label):
    result = recommended_action_phrase(overall_label)
    assert isinstance(result, str)
    assert result


def test_investment_horizon_label_specific_mappings():
    assert investment_horizon_label("High Conviction Buy") == "Core Position / Long-Term"
    assert investment_horizon_label("High Conviction Sell / Avoid") == "Avoid"
    assert "Wait" in investment_horizon_label("Excellent Company, Poor Timing — Wait")
    assert "Insufficient" in investment_horizon_label("Partial View — Data Insufficient")


def test_recommended_action_phrase_specific_mappings():
    assert "initiating" in recommended_action_phrase("High Conviction Buy").lower()
    assert "avoid" in recommended_action_phrase("High Conviction Sell / Avoid").lower()
    assert "wait" in recommended_action_phrase("Excellent Company, Poor Timing — Wait").lower()


def test_unknown_label_falls_back_to_a_sensible_default_without_crashing():
    assert investment_horizon_label("Something New") == "No Clear Horizon — Monitor"
    assert recommended_action_phrase("Something New") == "Hold — monitor for a clearer signal"
