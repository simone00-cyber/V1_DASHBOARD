from __future__ import annotations
import pandas as pd
from analysis.research import build_research_report
from analysis.research.confidence import confidence_label, research_score
from analysis.trades.models import Trade


def _trade(entry, exit_, ret, cm, q="UP", m="UP", phase="UP", rating=4, bars=4, side="LONG"):
    entry = pd.Timestamp(entry)
    exit_ = pd.Timestamp(exit_)
    return Trade(
        side=side,
        entry_date=entry,
        entry_price=100.0,
        exit_date=exit_,
        exit_price=100.0 * (1.0 + ret),
        exit_reason="TAKE PROFIT",
        entry_rating=rating,
        entry_quarterly=q,
        entry_monthly=m,
        entry_weekly_phase=phase,
        entry_weekly_composite=cm,
        bars_held=bars,
        gross_return=ret,
        net_return=ret - 0.001,
    )


def test_confidence_thresholds():
    assert confidence_label(5) == "LOW"
    assert confidence_label(30) == "MEDIUM"
    assert confidence_label(100) == "HIGH"


def test_research_report_groups_and_excursions():
    idx = pd.date_range("2020-01-03", periods=20, freq="W-FRI")
    weekly = pd.DataFrame({"Close": [100 + i for i in range(20)]}, index=idx)
    trades = [
        _trade(idx[0], idx[4], 0.04, -60, bars=4),
        _trade(idx[5], idx[10], -0.03, 25, q="DOWN", m="DOWN", phase="DOWN", rating=2, bars=5),
    ]
    report = build_research_report(trades, weekly)
    assert len(report.enriched_trades) == 2
    assert "MFE" in report.enriched_trades.columns
    assert "MAE" in report.enriched_trades.columns
    assert report.setup_summary["TRADES"].sum() == 2
    assert report.composite_summary["TRADES"].sum() == 2
    assert int(report.heatmap_count.to_numpy().sum()) == 2


def test_hypothesis_requires_minimum_samples():
    idx = pd.date_range("2020-01-03", periods=30, freq="W-FRI")
    weekly = pd.DataFrame({"Close": [100.0] * 30}, index=idx)
    trades = [_trade(idx[0], idx[1], 0.01, -10)]
    report = build_research_report(trades, weekly)
    assert set(report.hypotheses["STATUS"]) == {"INSUFFICIENT SAMPLE"}


def test_research_score_is_bounded():
    assert research_score(500, 0.10, 3.0) == 5
    assert 1 <= research_score(0, -0.10, 0.5) <= 5


def test_drawdown_analysis_identifies_episode_and_loss_attribution():
    idx = pd.date_range("2021-01-01", periods=8, freq="W-FRI")
    equity = [1.00, 1.10, 1.04, 0.99, 1.02, 1.10, 1.12, 1.08]
    weekly = pd.DataFrame({
        "Close": [100, 105, 101, 96, 98, 106, 108, 104],
        "Equity": equity,
    }, index=idx)
    weekly["Drawdown"] = weekly["Equity"] / weekly["Equity"].cummax() - 1.0
    trades = [
        _trade(idx[1], idx[3], -0.08, 20, q="UP", m="DOWN", phase="ADVANCING", rating=2, bars=2),
        _trade(idx[3], idx[5], 0.04, -55, q="UP", m="UP", phase="UP", rating=4, bars=2),
    ]
    report = build_research_report(trades, weekly)
    assert not report.drawdown_episodes.empty
    worst = report.drawdown_episodes.iloc[0]
    assert worst["MAX DRAWDOWN"] < -0.09
    assert worst["OVERLAPPING TRADES"] >= 1
    assert not report.drawdown_trades.empty
    assert not report.loss_attribution_setup.empty
    assert abs(report.loss_attribution_setup["LOSS SHARE"].sum() - 1.0) < 1e-9
    assert {"TOTAL_LOSS", "AVG_LOSS", "WORST_TRADE"}.issubset(report.loss_attribution_setup.columns)
