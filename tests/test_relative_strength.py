from __future__ import annotations

import pandas as pd

from screener.engine import _relative_ratio_index, _relative_return, build_relative_strength_ranking
from screener.universes import UNIVERSES


def test_universe_benchmarks_are_configured():
    assert UNIVERSES["NASDAQ 100"].benchmark_ticker == "^NDX"
    assert UNIVERSES["S&P 500"].benchmark_ticker == "^GSPC"
    assert UNIVERSES["FTSE MIB"].benchmark_ticker == "FTSEMIB.MI"
    assert UNIVERSES["DAX 40"].benchmark_ticker == "^GDAXI"


def test_relative_return_is_excess_return_in_percentage_points():
    stock = pd.Series([100.0, 110.0], index=pd.date_range("2026-01-01", periods=2))
    benchmark = pd.Series([100.0, 105.0], index=stock.index)
    assert round(_relative_return(stock, benchmark, 1), 6) == 5.0


def test_relative_ratio_index_is_normalized_to_100():
    stock = pd.Series([100.0, 120.0], index=pd.date_range("2026-01-01", periods=2))
    benchmark = pd.Series([100.0, 110.0], index=stock.index)
    assert round(_relative_ratio_index(stock, benchmark, 1), 6) == round((1.2 / 1.1) * 100.0, 6)


def test_relative_strength_ranking_orders_highest_first():
    rows = pd.DataFrame({
        "Ticker": ["A", "B", "C"],
        "RS 1M %": [-2.0, 4.0, 0.0],
    })
    ranked = build_relative_strength_ranking(rows, "RS 1M %")
    assert ranked["Ticker"].tolist() == ["B", "C", "A"]
    assert ranked["RS Signal"].tolist() == ["OUTPERFORM", "IN LINE", "UNDERPERFORM"]
