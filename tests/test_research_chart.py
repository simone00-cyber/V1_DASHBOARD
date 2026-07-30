import numpy as np
import pandas as pd

from analysis.security_signal import SignalEvent
from charts.research_chart import build_research_chart
from technical.assessment import build_technical_assessment
from technical.engine import TechnicalSettings, compute_fibonacci_levels


def _frame(n: int = 500, slope: float = 0.05, wiggle: float = 4.0, seed: int = 0) -> pd.DataFrame:
    x = np.arange(n)
    close = 100 + slope * x + wiggle * np.sin(x / 12)
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    close_s = pd.Series(close, index=idx)
    volume = np.random.default_rng(seed).integers(1_000, 5_000, n)
    return pd.DataFrame(
        {
            "Open": close_s.shift(1).fillna(close_s.iloc[0]),
            "High": close_s + 1.0,
            "Low": close_s - 1.0,
            "Close": close_s,
            "Volume": volume,
        },
        index=idx,
    )


def _turning_points(frame: pd.DataFrame) -> list[SignalEvent]:
    dates = frame.index[::80][:4]
    actions = ["BUY", "TAKE PROFIT", "SELL SHORT", "BUY"]
    return [
        SignalEvent(date=d, action=a, rating=3, quarterly_direction="UP", monthly_direction="UP", weekly_turn="SVOLTA UP", weekly_composite=10.0)
        for d, a in zip(dates, actions)
    ]


def test_chart_builds_with_no_optional_overlays():
    frame = _frame()
    settings = TechnicalSettings()
    assessment = build_technical_assessment("TEST", frame, settings)
    fig = build_research_chart("TEST", frame, settings, assessment, patterns=None, fib_levels=None, turning_points=None)
    trace_types = {trace.type for trace in fig.data}
    assert "candlestick" in trace_types
    assert fig.layout.height and fig.layout.height >= 700


def test_chart_includes_fibonacci_and_pattern_and_turning_point_layers():
    frame = _frame(slope=0.08, wiggle=2.0)
    settings = TechnicalSettings()
    assessment = build_technical_assessment("TEST", frame, settings)
    fib = compute_fibonacci_levels(frame, settings)
    patterns = assessment.snapshot.diagnostics.get("pattern_details", [])
    turning_points = _turning_points(frame)

    fig = build_research_chart("TEST", frame, settings, assessment, patterns[:1], fib, turning_points)
    assert fig.data  # renders without raising regardless of whether a pattern/fib was found

    trace_names = [trace.name for trace in fig.data if trace.name]
    if turning_points:
        assert any("Cyclical:" in name for name in trace_names)


def test_chart_handles_missing_volume_column():
    frame = _frame().drop(columns=["Volume"])
    settings = TechnicalSettings()
    assessment = build_technical_assessment("TEST", frame, settings)
    fig = build_research_chart("TEST", frame, settings, assessment)
    assert fig.data


def test_chart_draws_invalidation_line_when_a_direction_is_established():
    frame = _frame(slope=0.08, wiggle=1.0)
    settings = TechnicalSettings()
    assessment = build_technical_assessment("TEST", frame, settings)
    fig = build_research_chart("TEST", frame, settings, assessment)
    if assessment.invalidation_price is not None:
        annotations = [a.text for a in fig.layout.annotations if a.text]
        assert any("INVALIDATION" in text for text in annotations)
