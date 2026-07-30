from __future__ import annotations

import pandas as pd

from macro.models import ConfidenceAssessment, ExecutiveMarketThesis
from views.overview import _build_market_context, _thesis_fallback_text


def _thesis(**overrides) -> ExecutiveMarketThesis:
    base = dict(
        headline="The cross-asset read is constructive, with moderate confidence in the underlying data.",
        directional_view="RISK-ON",
        confidence=ConfidenceAssessment(score=65, label="MODERATE", breakdown={}, notes=()),
        what_changed=("Tactical market regime shifted from IMPROVING to DETERIORATING.",),
        why_it_matters=("Expanding liquidity is typically a tailwind for risk assets broadly.",),
        cross_asset_implications=("EQUITIES: Equity tactical pillar: POSITIVE.",),
        top_opportunities=("Expanding growth data may support cyclical sectors.",),
        major_risks=("Elevated inflation keeps the door open to further tightening.",),
        freshness_summary="Growth: CURRENT; Inflation: CURRENT; Liquidity: CURRENT",
        generated_at=pd.Timestamp.now(tz="UTC"),
    )
    base.update(overrides)
    return ExecutiveMarketThesis(**base)


# Command Center's AI-chat fallback text is now derived directly from the
# shared Executive Market Thesis (Macro & Rates is the source of truth) —
# these tests replace the old asset-class-sentence-builder tests that
# exercised `_fallback_briefing_text`, which no longer exists.


def test_thesis_fallback_text_includes_headline_and_all_sections():
    text = _thesis_fallback_text(_thesis())
    assert "constructive" in text
    assert "**What Changed**" in text
    assert "**Top Opportunities**" in text
    assert "**Major Risks**" in text
    assert "Tactical market regime shifted" in text


def test_thesis_fallback_text_omits_empty_sections():
    text = _thesis_fallback_text(_thesis(what_changed=(), top_opportunities=(), major_risks=()))
    assert "**What Changed**" not in text
    assert "**Top Opportunities**" not in text
    assert "**Major Risks**" not in text


def test_build_market_context_carries_thesis_fields_and_breadth():
    table = pd.DataFrame(
        [
            {"Strumento": "S&P 500", "Ultimo": 5000.0, "1D %": 1.2},
            {"Strumento": "VIX", "Ultimo": 15.0, "1D %": -2.0},
        ]
    )
    reading = {"positive": 1, "total": 2}
    context = _build_market_context(table, reading, _thesis())

    assert context["breadth"] == {"positive": 1, "total": 2}
    assert context["equity_indices"]["S&P 500"]["last"] == 5000.0
    assert context["executive_thesis"]["directional_view"] == "RISK-ON"
    assert context["executive_thesis"]["confidence"] == "MODERATE"
    assert "Tactical market regime shifted" in context["executive_thesis"]["what_changed"][0]
