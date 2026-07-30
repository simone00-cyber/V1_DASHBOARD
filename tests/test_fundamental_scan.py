from __future__ import annotations

import fundamentals.scan as scan_module
from fundamentals.models import FundamentalAnalysis


def _fake_analysis(ticker: str) -> FundamentalAnalysis:
    if ticker == "BADTICK":
        raise RuntimeError("boom")
    return FundamentalAnalysis(
        ticker=ticker, sufficient=True, insufficiency_reason=None,
        metrics=None, quality=None, valuation=None, rating=None, narrative=None, raw=None,
    )


def test_run_fundamental_scan_aggregates_results_and_failures(monkeypatch):
    monkeypatch.setattr(scan_module, "build_fundamental_analysis", lambda ticker, provider: _fake_analysis(ticker))
    scan_module._cached_fundamental_analysis.clear()

    result = scan_module.run_fundamental_scan(["SCANAAA", "SCANBBB", "BADTICK"])

    assert {row.ticker for row in result.rows} == {"SCANAAA", "SCANBBB"}
    assert result.failures == (("BADTICK", "boom"),)
    assert result.universe_size == 3
    assert result.coverage == 2
    assert result.data_source == "Yahoo Finance (yfinance)"


def test_run_fundamental_scan_deduplicates_and_normalizes_tickers(monkeypatch):
    monkeypatch.setattr(scan_module, "build_fundamental_analysis", lambda ticker, provider: _fake_analysis(ticker))
    scan_module._cached_fundamental_analysis.clear()

    result = scan_module.run_fundamental_scan(["dupe", "DUPE", " dupe "])

    assert result.universe_size == 1
    assert [row.ticker for row in result.rows] == ["DUPE"]


def test_run_fundamental_scan_reports_progress(monkeypatch):
    monkeypatch.setattr(scan_module, "build_fundamental_analysis", lambda ticker, provider: _fake_analysis(ticker))
    scan_module._cached_fundamental_analysis.clear()

    calls: list[tuple[int, int]] = []
    scan_module.run_fundamental_scan(
        ["PROGA", "PROGB"], on_progress=lambda done, total: calls.append((done, total))
    )

    assert len(calls) == 2
    assert calls[-1] == (2, 2)


def test_clear_fundamental_cache_does_not_raise():
    scan_module.clear_fundamental_cache()
