from __future__ import annotations

import pandas as pd
import pytest

from data import yahoo


def _multiindex_frame(columns_and_data: dict[tuple[str, str], list[float]]) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    frame = pd.DataFrame(columns_and_data, index=index)
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    return frame


@pytest.fixture(autouse=True)
def _clear_cache():
    yahoo.download_close_batch.clear()
    yield
    yahoo.download_close_batch.clear()


def test_fallback_replaces_all_nan_column_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Regression test: yfinance's batch call can return a column that exists
    but is entirely NaN for one ticker (e.g. a temporary data gap). The
    single-ticker fallback then re-fetches it — this must replace the NaN
    column rather than crash with "columns overlap but no suffix specified".
    """

    batch_frame = _multiindex_frame(
        {
            ("Close", "GOOD"): [1.0, 2.0, 3.0],
            ("Close", "GC=F"): [float("nan"), float("nan"), float("nan")],
        }
    )

    fallback_frame = pd.DataFrame(
        {"Close": [10.0, 11.0, 12.0]},
        index=pd.date_range("2024-01-01", periods=3, freq="D"),
    )

    calls = {"batch": 0, "single": 0}

    def fake_download(*args, **kwargs):
        if kwargs.get("tickers") is not None:
            calls["batch"] += 1
            return batch_frame
        calls["single"] += 1
        return fallback_frame

    monkeypatch.setattr(yahoo.yf, "download", fake_download)

    result = yahoo.download_close_batch(("GOOD", "GC=F"), period="1mo")

    assert calls["single"] >= 1
    assert "GC=F" in result.columns
    assert "GOOD" in result.columns
    assert result["GC=F"].dropna().tolist() == [10.0, 11.0, 12.0]
    assert result["GOOD"].dropna().tolist() == [1.0, 2.0, 3.0]


def test_empty_ticker_tuple_returns_empty_frame() -> None:
    assert yahoo.download_close_batch(()).empty


def test_deduplicates_repeated_tickers(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_tickers: list[list[str]] = []

    def fake_download(*args, **kwargs):
        seen_tickers.append(kwargs.get("tickers"))
        return _multiindex_frame({("Close", "GOOD"): [1.0, 2.0, 3.0]})

    monkeypatch.setattr(yahoo.yf, "download", fake_download)

    yahoo.download_close_batch(("GOOD", "GOOD", "GOOD"), period="1mo")

    assert seen_tickers[0] == ["GOOD"]
