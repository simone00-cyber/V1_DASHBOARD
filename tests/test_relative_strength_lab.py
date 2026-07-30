from __future__ import annotations

import numpy as np
import pandas as pd

from screener.relative_strength import (
    build_monthly_leaders,
    build_relative_strength_lab,
    build_sector_composites,
    build_statistics,
)


def _frame(values: list[float], dates: pd.DatetimeIndex) -> pd.DataFrame:
    close = pd.Series(values, index=dates)
    return pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close})


def test_relative_strength_lab_normalizes_and_ranks() -> None:
    dates = pd.bdate_range("2024-01-01", periods=300)
    benchmark = np.linspace(100, 120, len(dates))
    leader = np.linspace(100, 150, len(dates))
    laggard = np.linspace(100, 90, len(dates))
    frames = {
        "BENCH": _frame(benchmark.tolist(), dates),
        "LEAD": _frame(leader.tolist(), dates),
        "LAG": _frame(laggard.tolist(), dates),
    }

    result = build_relative_strength_lab(frames, "BENCH", ["LEAD", "LAG"], 252)

    assert not result.normalized.empty
    assert result.normalized.iloc[0].round(8).eq(100.0).all()
    stats = result.statistics.set_index("Ticker")
    assert stats.loc["LEAD", "Excess Return pp"] > 0
    assert stats.loc["LAG", "Excess Return pp"] < 0
    assert result.relative_ratio["LEAD"].iloc[-1] > 100
    assert result.relative_ratio["LAG"].iloc[-1] < 100


def test_sector_composite_is_equal_weight_normalized() -> None:
    dates = pd.bdate_range("2025-01-01", periods=40)
    frames = {
        "A": _frame(np.linspace(10, 20, len(dates)).tolist(), dates),
        "B": _frame(np.linspace(20, 30, len(dates)).tolist(), dates),
    }
    constituents = pd.DataFrame(
        {"Ticker": ["A", "B"], "Company": ["A Co", "B Co"], "Sector": ["Tech", "Tech"]}
    )
    composites = build_sector_composites(frames, constituents, ["Tech"], 21)
    series = composites["SECTOR: Tech"]
    assert round(float(series.iloc[0]), 8) == 100.0
    assert float(series.iloc[-1]) > 100.0


def test_statistics_and_monthly_leaders() -> None:
    dates = pd.bdate_range("2023-01-02", periods=520)
    aligned = pd.DataFrame(
        {
            "BENCH": np.linspace(100, 120, len(dates)),
            "A": np.linspace(100, 160, len(dates)),
            "B": np.linspace(100, 80, len(dates)),
        },
        index=dates,
    )
    stats = build_statistics(aligned, "BENCH")
    assert stats.iloc[0]["Ticker"] == "A"
    leaders = build_monthly_leaders(aligned, "BENCH", months=6)
    assert not leaders.empty
    assert set(leaders["Leader"]) == {"A"}
