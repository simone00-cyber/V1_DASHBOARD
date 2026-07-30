from __future__ import annotations

from types import SimpleNamespace

from analysis.combined_thesis import (
    INSUFFICIENT,
    build_combined_thesis,
    derive_cyclical_verdict,
    derive_technical_verdict,
)


def test_high_conviction_buy_when_all_three_agree():
    thesis = build_combined_thesis("BUY", "BUY", "BUY")
    assert thesis.overall_label == "High Conviction Buy"


def test_high_conviction_sell_when_all_three_agree():
    thesis = build_combined_thesis("SELL", "SELL", "SELL")
    assert thesis.overall_label == "High Conviction Sell / Avoid"


def test_excellent_company_poor_timing_example_from_spec():
    thesis = build_combined_thesis("BUY", "SELL", "SELL")
    assert thesis.overall_label == "Excellent Company, Poor Timing — Wait"
    assert "Wait" in thesis.explanation or "wait" in thesis.explanation.lower()


def test_weak_company_strong_momentum_is_the_mirror_case():
    thesis = build_combined_thesis("SELL", "BUY", "BUY")
    assert thesis.overall_label == "Weak Company, Strong Momentum — Caution"


def test_majority_buy_without_unanimity():
    thesis = build_combined_thesis("BUY", "BUY", "HOLD")
    assert thesis.overall_label == "Buy"


def test_majority_sell_without_unanimity():
    thesis = build_combined_thesis("SELL", "SELL", "HOLD")
    assert thesis.overall_label == "Sell / Avoid"


def test_mixed_signals_fall_back_to_hold():
    thesis = build_combined_thesis("HOLD", "BUY", "SELL")
    assert thesis.overall_label == "Hold / Mixed Signals"


def test_insufficient_data_short_circuits_the_combination():
    thesis = build_combined_thesis(INSUFFICIENT, "BUY", "BUY")
    assert thesis.overall_label == "Partial View — Data Insufficient"


def test_derive_technical_verdict_from_direction():
    assert derive_technical_verdict(SimpleNamespace(direction="UPTREND")) == "BUY"
    assert derive_technical_verdict(
        SimpleNamespace(direction="DOWNTREND (EARLY / NOT YET CONFIRMED BY SWING STRUCTURE)")
    ) == "SELL"
    assert derive_technical_verdict(SimpleNamespace(direction="RANGE-BOUND / NO CLEAR DIRECTION")) == "HOLD"


def test_derive_cyclical_verdict_from_signal_state():
    assert derive_cyclical_verdict(None) == INSUFFICIENT
    assert derive_cyclical_verdict(SimpleNamespace(current_position="LONG")) == "BUY"
    assert derive_cyclical_verdict(SimpleNamespace(current_position="SHORT")) == "SELL"
    assert derive_cyclical_verdict(SimpleNamespace(current_position="NEUTRAL")) == "HOLD"
