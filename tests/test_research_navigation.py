from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from caruso_analysis import (
    RESAMPLE_RULES,
    calculate_composite_momentum,
    prepare_technical_prices,
    resample_ohlc,
    summarize_timeframe,
)
from technical.assessment import build_technical_assessment
from technical.engine import TechnicalSettings
from ui.research_panels import _navigate_to_build_strategy, _navigate_to_compare_sector


def _synthetic_daily(n: int = 2600) -> pd.DataFrame:
    idx = pd.date_range("2015-01-01", periods=n, freq="B")
    x = np.arange(n)
    close = 100 + 0.02 * x + 5 * np.sin(x / 40)
    close_s = pd.Series(close, index=idx)
    return pd.DataFrame(
        {
            "Open": close_s.shift(1).fillna(close_s.iloc[0]),
            "High": close_s + 1.0,
            "Low": close_s - 1.0,
            "Close": close_s,
            "Volume": 1_000_000,
        },
        index=idx,
    )


def _fake_cyclical_analysis(ticker: str, period: str):
    daily_raw = _synthetic_daily().rename(columns={"Volume": "Volume"})
    daily_raw["Adj Close"] = daily_raw["Close"]
    daily = prepare_technical_prices(daily_raw)
    frames: dict = {}
    summaries: dict = {}
    for timeframe, rule in RESAMPLE_RULES.items():
        ohlc = resample_ohlc(daily, rule)
        calculated = calculate_composite_momentum(ohlc)
        frames[timeframe] = calculated
        summaries[timeframe] = summarize_timeframe(timeframe, calculated)
    return daily, daily_raw, frames, summaries, {}


def _install_fake_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("views.research._daily_prices", lambda ticker: _synthetic_daily())
    monkeypatch.setattr("views.research.load_cyclical_analysis", _fake_cyclical_analysis)


def _research_script() -> None:
    from views.research import render_research

    render_research(ticker_override="AAA", embedded=True)


def _sample_assessment():
    x = np.arange(400)
    close = 100 + 0.06 * x + 3 * np.sin(x / 10)
    idx = pd.date_range("2023-01-01", periods=len(close), freq="B")
    close_s = pd.Series(close, index=idx)
    frame = pd.DataFrame(
        {
            "Open": close_s.shift(1).fillna(close_s.iloc[0]),
            "High": close_s + 1.0,
            "Low": close_s - 1.0,
            "Close": close_s,
            "Volume": 1000,
        },
        index=idx,
    )
    return build_technical_assessment("AAPL", frame, TechnicalSettings())


# --- Direct navigation-action tests (session_state + st.switch_page wiring) ---


def test_build_strategy_prefills_prompt_and_switches_page_when_registered():
    st.session_state.clear()
    st.session_state["_pages"] = {"AI Strategy Lab": "AI_PAGE"}
    assessment = _sample_assessment()
    with patch("streamlit.switch_page") as mock_switch:
        _navigate_to_build_strategy("AAPL", "Apple Inc.", assessment)
    assert "AAPL" in st.session_state["pending_ai_message"]
    assert "Apple Inc." in st.session_state["pending_ai_message"]
    mock_switch.assert_called_once_with("AI_PAGE")


def test_build_strategy_sets_prompt_without_crashing_when_page_unregistered():
    st.session_state.clear()
    assessment = _sample_assessment()
    with patch("streamlit.switch_page") as mock_switch:
        _navigate_to_build_strategy("AAPL", "Apple Inc.", assessment)
    assert "AAPL" in st.session_state["pending_ai_message"]
    mock_switch.assert_not_called()


def test_compare_with_sector_switches_page_when_registered():
    st.session_state.clear()
    st.session_state["_pages"] = {"Opportunities": "OPPS_PAGE"}
    with patch("streamlit.switch_page") as mock_switch:
        _navigate_to_compare_sector()
    mock_switch.assert_called_once_with("OPPS_PAGE")


def test_compare_with_sector_is_a_no_op_without_crashing_when_page_unregistered():
    st.session_state.clear()
    with patch("streamlit.switch_page") as mock_switch:
        _navigate_to_compare_sector()
    mock_switch.assert_not_called()


# --- AppTest end-to-end smoke tests for the redesigned Research workspace ---


def test_research_page_renders_all_sections_without_error(monkeypatch):
    _install_fake_data(monkeypatch)
    at = AppTest.from_function(_research_script)
    at.run()

    assert not at.exception
    body = "\n".join(m.value for m in at.markdown)
    assert "RESEARCH SUMMARY" in body
    assert "MARKET STRUCTURE" in body
    assert "KEY LEVELS" in body
    assert "DEVELOPING PATTERNS" in body
    assert "MOMENTUM" in body
    assert "MULTI-TIMEFRAME ALIGNMENT" in body
    assert "CYCLICAL POSITION" in body

    # The chart is the primary read: it must render above every text panel.
    assert len(at.get("plotly_chart")) >= 1

    # Hero header metrics (Ticker / Price / Trend / Risk / Regime).
    metric_labels = {m.label for m in at.metric}
    assert {"TICKER", "PRICE", "TREND", "RISK", "REGIME"}.issubset(metric_labels)

    # Executive summary's seven glanceable facts.
    for label in ("Overall View", "Confidence", "Best Setup", "Current Risk", "Key Trigger", "Invalidation", "Recommended Action"):
        assert label in body


def test_research_page_shows_recommended_action(monkeypatch):
    _install_fake_data(monkeypatch)
    at = AppTest.from_function(_research_script)
    at.run()

    assert not at.exception
    body = "\n".join(m.value for m in at.markdown)
    assert "Recommended Action" in body


def test_build_strategy_button_prefills_ai_prompt_without_navigating(monkeypatch):
    _install_fake_data(monkeypatch)
    at = AppTest.from_function(_research_script)
    at.run()
    assert not at.exception

    button = next(b for b in at.button if b.key == "research_build_strategy")
    button.click().run()

    assert not at.exception
    # No "_pages" registry is present in this isolated AppTest run, so the button
    # must set the prefilled prompt without attempting to navigate (and without crashing).
    assert "AAA" in at.session_state["pending_ai_message"]


def test_compare_with_sector_button_does_not_crash_without_pages_registry(monkeypatch):
    _install_fake_data(monkeypatch)
    at = AppTest.from_function(_research_script)
    at.run()
    assert not at.exception

    button = next(b for b in at.button if b.key == "research_compare_sector")
    button.click().run()

    assert not at.exception
