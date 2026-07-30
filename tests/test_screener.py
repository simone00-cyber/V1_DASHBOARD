import pandas as pd

from screener.engine import build_sector_ranking, sort_by_methodology
from screener.universes import UNIVERSES, fallback_universe, normalize_ticker


def test_ftse_mib_fallback_has_sector_metadata():
    frame = fallback_universe("FTSE MIB")
    assert len(frame) >= 30
    assert {"Company", "Ticker", "Sector"}.issubset(frame.columns)
    assert frame["Ticker"].is_unique
    assert "STM.MI" in set(frame["Ticker"])


def test_universe_ticker_normalisation_is_market_specific():
    assert normalize_ticker("TSLA", UNIVERSES["NASDAQ 100"]) == "TSLA"
    assert normalize_ticker("BRK.B", UNIVERSES["S&P 500"]) == "BRK-B"
    assert normalize_ticker("A2A", UNIVERSES["FTSE MIB"]) == "A2A.MI"
    assert normalize_ticker("A2A-MI.MI", UNIVERSES["FTSE MIB"]) == "A2A.MI"
    assert normalize_ticker("SAP", UNIVERSES["DAX 40"]) == "SAP.DE"


def test_sector_ranking_uses_price_performance_only():
    rows = pd.DataFrame(
        [
            {"Ticker": "AAA", "Sector": "Tech", "1M %": 30.0},
            {"Ticker": "BBB", "Sector": "Tech", "1M %": 10.0},
            {"Ticker": "CCC", "Sector": "Banks", "1M %": -50.0},
        ]
    )
    ranking = build_sector_ranking(rows, "1M %")
    assert ranking.iloc[0]["Sector"] == "Tech"
    assert ranking.iloc[0]["Performance"] == 20.0
    assert ranking.iloc[-1]["Sector"] == "Banks"
    assert ranking.iloc[-1]["Performance"] == -50.0


def test_methodology_sort_has_no_weighted_score():
    rows = pd.DataFrame(
        [
            {
                "Ticker": "SELL",
                "Matrix Action": "SELL SHORT",
                "Rating": 4,
                "Quarterly Trend": "DOWN",
                "Monthly Trend": "DOWN",
                "Quarterly CM": 90,
                "Monthly CM": 90,
                "Weekly CM": 90,
            },
            {
                "Ticker": "BUY2",
                "Matrix Action": "BUY",
                "Rating": 2,
                "Quarterly Trend": "UP",
                "Monthly Trend": "DOWN",
                "Quarterly CM": 20,
                "Monthly CM": 10,
                "Weekly CM": 5,
            },
            {
                "Ticker": "BUY4",
                "Matrix Action": "BUY",
                "Rating": 4,
                "Quarterly Trend": "UP",
                "Monthly Trend": "UP",
                "Quarterly CM": 10,
                "Monthly CM": 10,
                "Weekly CM": 10,
            },
        ]
    )
    ranked = sort_by_methodology(rows)
    assert list(ranked["Ticker"]) == ["BUY4", "BUY2", "SELL"]
    assert "Opportunity Score" not in ranked.columns
