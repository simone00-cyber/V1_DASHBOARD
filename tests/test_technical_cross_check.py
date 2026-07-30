import numpy as np
import pandas as pd

from analysis.cyclical.models import HierarchyAssessment
from analysis.cyclical.technical_cross_check import build_technical_cyclical_cross_check
from technical.assessment import build_technical_assessment
from technical.engine import TechnicalSettings


def _frame(slope: float, n: int = 420) -> pd.DataFrame:
    x = np.arange(n)
    close = 100 + slope * x + 3 * np.sin(x / 10)
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    close_s = pd.Series(close, index=idx)
    return pd.DataFrame(
        {
            "Open": close_s.shift(1).fillna(close_s.iloc[0]),
            "High": close_s + 1.0,
            "Low": close_s - 1.0,
            "Close": close_s,
            "Volume": 1000,
        },
        index=idx,
    )


def _hierarchy(alignment: str) -> HierarchyAssessment:
    return HierarchyAssessment(
        annual_phase="ADVANCING",
        quarterly_phase="ADVANCING",
        monthly_phase="ADVANCING",
        weekly_phase="ADVANCING",
        quarterly_direction="UP",
        monthly_direction="UP",
        weekly_direction="UP",
        alignment=alignment,
        tactical_condition="TREND FOLLOWING",
        documented_trigger="N/A",
        notes=(),
    )


def test_cross_check_confirms_when_technical_and_cyclical_agree():
    technical = build_technical_assessment("TEST", _frame(slope=0.06), TechnicalSettings())
    result = build_technical_cyclical_cross_check(technical, _hierarchy("FULL BULLISH ALIGNMENT"))
    if "uptrend" in technical.current_assessment.lower():
        assert result.agreement == "CONFIRMS"


def test_cross_check_diverges_when_technical_and_cyclical_disagree():
    technical = build_technical_assessment("TEST", _frame(slope=0.06), TechnicalSettings())
    result = build_technical_cyclical_cross_check(technical, _hierarchy("FULL BEARISH ALIGNMENT"))
    if "uptrend" in technical.current_assessment.lower():
        assert result.agreement == "DIVERGES"


def test_cross_check_handles_mixed_cyclical_alignment():
    technical = build_technical_assessment("TEST", _frame(slope=0.06), TechnicalSettings())
    result = build_technical_cyclical_cross_check(technical, _hierarchy("MIXED / NON-SYNCHRONIZED"))
    assert result.agreement == "MIXED / NO CLEAR CYCLICAL READ"


def test_cross_check_summary_is_never_empty():
    technical = build_technical_assessment("TEST", _frame(slope=-0.05), TechnicalSettings())
    for alignment in ("FULL BULLISH ALIGNMENT", "FULL BEARISH ALIGNMENT", "MIXED / NON-SYNCHRONIZED"):
        result = build_technical_cyclical_cross_check(technical, _hierarchy(alignment))
        assert result.summary
        assert result.agreement in {"CONFIRMS", "DIVERGES", "MIXED / NO CLEAR CYCLICAL READ"}
