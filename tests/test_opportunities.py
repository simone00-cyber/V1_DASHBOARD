import pandas as pd

from screener.engine import build_sector_performance
from screener.opportunities import (
    CONVICTION_TIERS,
    annotate_conviction,
    build_opportunity_funnel,
    build_reason,
    build_regime_label,
    build_risk,
    build_snapshot,
    classify_conviction,
    classify_sector_group,
    select_top_opportunities,
)


def _sample_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Ticker": "AAA", "Company": "AlphaCo", "Sector": "Tech",
                "Matrix Action": "BUY", "Rating": 4,
                "Quarterly Trend": "UP", "Monthly Trend": "UP", "Weekly Turn": "SVOLTA UP",
                "Last": 100.0, "1M %": 8.0, "RS 3M %": 3.2, "Weekly CM": 40, "Order": 1,
            },
            {
                "Ticker": "BBB", "Company": "BetaCo", "Sector": "Tech",
                "Matrix Action": "BUY", "Rating": 1,
                "Quarterly Trend": "DOWN", "Monthly Trend": "DOWN", "Weekly Turn": "SVOLTA UP",
                "Last": 50.0, "1M %": -2.0, "RS 3M %": -1.0, "Weekly CM": 10, "Order": 2,
            },
            {
                "Ticker": "CCC", "Company": "GammaCo", "Sector": "Banks",
                "Matrix Action": "SELL SHORT", "Rating": 4,
                "Quarterly Trend": "DOWN", "Monthly Trend": "DOWN", "Weekly Turn": "SVOLTA DOWN",
                "Last": 20.0, "1M %": -10.0, "RS 3M %": -8.0, "Weekly CM": -40, "Order": 3,
            },
            {
                "Ticker": "DDD", "Company": "DeltaCo", "Sector": "Banks",
                "Matrix Action": "NESSUNA NUOVA GIUNTURA", "Rating": 0,
                "Quarterly Trend": "UP", "Monthly Trend": "UP", "Weekly Turn": "FLAT",
                "Last": 30.0, "1M %": 1.0, "RS 3M %": 0.5, "Weekly CM": 5, "Order": 4,
            },
            {
                "Ticker": "EEE", "Company": "EpsilonCo", "Sector": "Energy",
                "Matrix Action": "TAKE PROFIT", "Rating": 3,
                "Quarterly Trend": "UP", "Monthly Trend": "DOWN", "Weekly Turn": "PROSEGUE DOWN",
                "Last": 60.0, "1M %": -4.0, "RS 3M %": -2.0, "Weekly CM": -12, "Order": 5,
            },
        ]
    )


def test_classify_conviction_covers_every_matrix_action():
    assert classify_conviction("BUY", 4) == "High Conviction"
    assert classify_conviction("BUY", 3) == "High Conviction"
    assert classify_conviction("BUY", 2) == "Emerging"
    assert classify_conviction("BUY", 1) == "Emerging"
    assert classify_conviction("NESSUNA NUOVA GIUNTURA", 0) == "Watchlist"
    assert classify_conviction("TAKE PROFIT", 3) == "Deteriorating"
    assert classify_conviction("SELL SHORT", 4) == "Avoid"


def test_annotate_conviction_adds_expected_tier_per_row():
    annotated = annotate_conviction(_sample_rows())
    tiers = dict(zip(annotated["Ticker"], annotated["Conviction Tier"]))
    assert tiers == {
        "AAA": "High Conviction",
        "BBB": "Emerging",
        "CCC": "Avoid",
        "DDD": "Watchlist",
        "EEE": "Deteriorating",
    }


def test_annotate_conviction_handles_empty_frame():
    empty = pd.DataFrame(columns=["Matrix Action", "Rating"])
    annotated = annotate_conviction(empty)
    assert "Conviction Tier" in annotated.columns
    assert annotated.empty


def test_build_opportunity_funnel_counts_every_tier_in_order():
    annotated = annotate_conviction(_sample_rows())
    funnel = build_opportunity_funnel(annotated)
    assert list(funnel["Tier"]) == CONVICTION_TIERS
    counts = dict(zip(funnel["Tier"], funnel["Count"]))
    assert counts == {
        "High Conviction": 1,
        "Emerging": 1,
        "Watchlist": 1,
        "Deteriorating": 1,
        "Avoid": 1,
    }
    assert funnel["Share %"].sum() == 100.0


def test_select_top_opportunities_only_returns_buy_rows_in_methodology_order():
    annotated = annotate_conviction(_sample_rows())
    top = select_top_opportunities(annotated, limit=6)
    assert list(top["Ticker"]) == ["AAA", "BBB"]
    assert set(top["Matrix Action"]) == {"BUY"}


def test_select_top_opportunities_respects_limit():
    annotated = annotate_conviction(_sample_rows())
    top = select_top_opportunities(annotated, limit=1)
    assert list(top["Ticker"]) == ["AAA"]


def test_select_top_opportunities_empty_when_no_buy_signals():
    rows = _sample_rows()
    rows["Matrix Action"] = "SELL SHORT"
    top = select_top_opportunities(rows, limit=6)
    assert top.empty


def test_classify_sector_group_labels_leading_lagging_neutral():
    sectors = pd.DataFrame(
        [
            {"Sector": "Tech", "Performance": 5.0},
            {"Sector": "Utilities", "Performance": 0.0},
            {"Sector": "Banks", "Performance": -5.0},
        ]
    )
    grouped = classify_sector_group(sectors)
    groups = dict(zip(grouped["Sector"], grouped["Group"]))
    assert groups == {"Tech": "LEADING", "Utilities": "NEUTRAL", "Banks": "LAGGING"}


def test_build_reason_and_risk_are_derived_from_matrix_fields_only():
    row = _sample_rows().iloc[0]
    reason = build_reason(row)
    assert "up" in reason.lower()
    assert "4/4" in reason
    risk = build_risk(row)
    assert "weekly downturn" in risk.lower()


def test_build_regime_label_summarises_trend_and_turn():
    row = _sample_rows().iloc[0]
    label = build_regime_label(row)
    assert label == "Q UP · M UP · W TURN UP"


def test_build_snapshot_identifies_leading_and_lagging_sector():
    rows = _sample_rows()
    annotated = annotate_conviction(rows)
    sectors = classify_sector_group(build_sector_performance(rows, "1M %"))
    snapshot = build_snapshot(annotated, sectors, "1M %", "1 MONTH")

    assert snapshot is not None
    assert snapshot.leading_sector == "Tech"
    assert snapshot.lagging_sector == "Banks"
    assert snapshot.high_conviction_count == 1
    assert snapshot.top_ticker == "AAA"
    assert "Tech" in snapshot.interpretation
    assert "Banks" in snapshot.interpretation


def test_build_snapshot_returns_none_when_no_sector_data():
    rows = _sample_rows()
    annotated = annotate_conviction(rows)
    empty_sectors = pd.DataFrame(columns=["Sector", "Performance"])
    assert build_snapshot(annotated, empty_sectors, "1M %", "1 MONTH") is None
