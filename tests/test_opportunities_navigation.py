from unittest.mock import patch

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from screener.engine import ScreenerResult, sort_by_methodology
from ui.opportunity_cards import _build_strategy, _open_in_research


def _fixture_rows() -> pd.DataFrame:
    rows = pd.DataFrame(
        [
            {
                "Ticker": "AAA", "Company": "AlphaCo", "Sector": "Tech",
                "Last": 100.0, "1D %": 1.0, "1W %": 2.0, "1M %": 8.0, "1Y %": 20.0,
                "RS 1W %": 0.5, "RS 1M %": 1.2, "RS 3M %": 3.2, "RS 6M %": 4.0, "RS 1Y %": 6.0,
                "RS Ratio 1Y": 105.0, "Benchmark": "^NDX",
                "Quarterly CM": 60.0, "Monthly CM": 55.0, "Weekly CM": 40.0,
                "Quarterly Trend": "UP", "Monthly Trend": "UP", "Weekly Turn": "SVOLTA UP",
                "Matrix Action": "BUY", "Rating": 4, "Rating Visual": "****",
                "Screening Status": "BUY", "Methodology Note": "SEGNALE PRESENTE NELL'ULTIMA BARRA SETTIMANALE",
                "Data Date": pd.Timestamp("2026-07-24"),
            },
            {
                "Ticker": "BBB", "Company": "BetaCo", "Sector": "Banks",
                "Last": 40.0, "1D %": -0.5, "1W %": -1.0, "1M %": -6.0, "1Y %": -10.0,
                "RS 1W %": -0.2, "RS 1M %": -2.0, "RS 3M %": -3.0, "RS 6M %": -4.0, "RS 1Y %": -8.0,
                "RS Ratio 1Y": 92.0, "Benchmark": "^NDX",
                "Quarterly CM": -50.0, "Monthly CM": -45.0, "Weekly CM": -30.0,
                "Quarterly Trend": "DOWN", "Monthly Trend": "DOWN", "Weekly Turn": "SVOLTA DOWN",
                "Matrix Action": "SELL SHORT", "Rating": 4, "Rating Visual": "****",
                "Screening Status": "SELL SHORT", "Methodology Note": "SEGNALE PRESENTE NELL'ULTIMA BARRA SETTIMANALE",
                "Data Date": pd.Timestamp("2026-07-24"),
            },
            {
                "Ticker": "CCC", "Company": "GammaCo", "Sector": "Energy",
                "Last": 60.0, "1D %": 0.1, "1W %": 0.3, "1M %": 1.0, "1Y %": 5.0,
                "RS 1W %": 0.1, "RS 1M %": 0.2, "RS 3M %": 0.4, "RS 6M %": 0.6, "RS 1Y %": 1.0,
                "RS Ratio 1Y": 100.5, "Benchmark": "^NDX",
                "Quarterly CM": 5.0, "Monthly CM": 5.0, "Weekly CM": 2.0,
                "Quarterly Trend": "UP", "Monthly Trend": "UP", "Weekly Turn": "FLAT",
                "Matrix Action": "NESSUNA NUOVA GIUNTURA", "Rating": 0, "Rating Visual": "-",
                "Screening Status": "NO NEW JUNCTION", "Methodology Note": "Il CM settimanale non ha invertito pendenza nell'ultima barra.",
                "Data Date": pd.Timestamp("2026-07-24"),
            },
        ]
    )
    return sort_by_methodology(rows)


def _install_fake_screen(monkeypatch: pytest.MonkeyPatch) -> pd.DataFrame:
    rows = _fixture_rows()
    result = ScreenerResult(rows=rows, failures=pd.DataFrame(columns=["Ticker", "Reason"]))

    def _fake_run_screen(name: str):
        return result, "unit-test fixture", len(rows)

    monkeypatch.setattr("views.screener._run_screen", _fake_run_screen)
    return rows


def _opportunities_script() -> None:
    from views.screener import render_market_screener

    render_market_screener()


# --- Direct navigation-action tests (session_state + st.switch_page wiring) ---


def test_open_in_research_sets_ticker_and_switches_page_when_registered():
    st.session_state.clear()
    st.session_state["_pages"] = {"Research Workspace": "WORKSPACE_PAGE"}
    with patch("streamlit.switch_page") as mock_switch:
        _open_in_research("AAPL")
    assert st.session_state["workspace_ticker"] == "AAPL"
    assert st.session_state["workspace_loading"] is True
    mock_switch.assert_called_once_with("WORKSPACE_PAGE")


def test_open_in_research_sets_ticker_without_crashing_when_page_unregistered():
    st.session_state.clear()
    with patch("streamlit.switch_page") as mock_switch:
        _open_in_research("AAPL")
    assert st.session_state["workspace_ticker"] == "AAPL"
    mock_switch.assert_not_called()


def test_build_strategy_prefills_prompt_and_switches_page_when_registered():
    st.session_state.clear()
    st.session_state["_pages"] = {"AI Strategy Lab": "AI_PAGE"}
    with patch("streamlit.switch_page") as mock_switch:
        _build_strategy("AAPL", "Apple Inc.")
    assert "AAPL" in st.session_state["pending_ai_message"]
    assert "Apple Inc." in st.session_state["pending_ai_message"]
    mock_switch.assert_called_once_with("AI_PAGE")


def test_build_strategy_sets_prompt_without_crashing_when_page_unregistered():
    st.session_state.clear()
    with patch("streamlit.switch_page") as mock_switch:
        _build_strategy("AAPL", "Apple Inc.")
    assert "AAPL" in st.session_state["pending_ai_message"]
    mock_switch.assert_not_called()


# --- AppTest end-to-end smoke tests for the redesigned page ---


def test_opportunities_page_renders_all_sections_without_error(monkeypatch):
    _install_fake_screen(monkeypatch)
    at = AppTest.from_function(_opportunities_script)
    at.run()

    assert not at.exception
    body = "\n".join(m.value for m in at.markdown)
    assert "Opportunities" in body
    assert "OPPORTUNITY SNAPSHOT" in body
    assert "TOP OPPORTUNITIES" in body
    assert "SECTOR LEADERSHIP" in body
    assert "LEADERS" in body and "LAGGARDS" in body
    assert "OPPORTUNITY FUNNEL" in body


def test_opportunities_page_top_opportunity_card_shows_only_buy_signal(monkeypatch):
    _install_fake_screen(monkeypatch)
    at = AppTest.from_function(_opportunities_script)
    at.run()

    assert not at.exception
    body = "\n".join(m.value for m in at.markdown)
    # AAA is the only BUY signal in the fixture; it must surface as a top opportunity.
    assert "AAA" in body
    # BBB (SELL SHORT) must not be promoted into the Top Opportunities cards.
    research_buttons = {b.key for b in at.button if b.key and b.key.startswith("opp_research_")}
    assert research_buttons == {"opp_research_AAA"}


def test_open_in_research_button_updates_session_state_without_navigating(monkeypatch):
    _install_fake_screen(monkeypatch)
    at = AppTest.from_function(_opportunities_script)
    at.run()
    assert not at.exception

    button = next(b for b in at.button if b.key == "opp_research_AAA")
    button.click().run()

    assert not at.exception
    assert at.session_state["workspace_ticker"] == "AAA"


def test_build_strategy_button_prefills_ai_prompt(monkeypatch):
    _install_fake_screen(monkeypatch)
    at = AppTest.from_function(_opportunities_script)
    at.run()
    assert not at.exception

    button = next(b for b in at.button if b.key == "opp_strategy_AAA")
    button.click().run()

    assert not at.exception
    assert "AAA" in at.session_state["pending_ai_message"]
