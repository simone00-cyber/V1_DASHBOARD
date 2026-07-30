from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


CONVICTION_TIERS: list[str] = [
    "High Conviction",
    "Emerging",
    "Watchlist",
    "Deteriorating",
    "Avoid",
]

_TREND_PHRASE = {"UP": "up", "DOWN": "down"}

_TURN_PHRASE = {
    "SVOLTA UP": "just turned higher",
    "SVOLTA DOWN": "just turned lower",
    "PROSEGUE UP": "continuing higher",
    "PROSEGUE DOWN": "continuing lower",
    "FLAT": "flat",
}


def classify_conviction(action: str, rating: int) -> str:
    """Group a Matrix Action + published Reward/Risk rating into a research-priority tier.

    This only relabels the existing public matrix output for navigation purposes;
    it does not introduce a new score or alter the underlying methodology.
    """
    if action == "BUY":
        return "High Conviction" if rating >= 3 else "Emerging"
    if action == "NESSUNA NUOVA GIUNTURA":
        return "Watchlist"
    if action == "TAKE PROFIT":
        return "Deteriorating"
    if action == "SELL SHORT":
        return "Avoid"
    return "Watchlist"


def annotate_conviction(rows: pd.DataFrame) -> pd.DataFrame:
    """Attach a 'Conviction Tier' column derived from Matrix Action and Rating."""
    result = rows.copy()
    if result.empty:
        result["Conviction Tier"] = pd.Series(dtype=str)
        return result
    result["Conviction Tier"] = [
        classify_conviction(str(action), int(rating))
        for action, rating in zip(result["Matrix Action"], result["Rating"])
    ]
    return result


def build_opportunity_funnel(annotated_rows: pd.DataFrame) -> pd.DataFrame:
    """Count securities per research-priority tier, in funnel order."""
    if annotated_rows.empty or "Conviction Tier" not in annotated_rows:
        return pd.DataFrame(columns=["Tier", "Count", "Share %"])

    counts = annotated_rows["Conviction Tier"].value_counts().reindex(CONVICTION_TIERS, fill_value=0)
    total = int(counts.sum())
    frame = counts.rename_axis("Tier").reset_index(name="Count")
    frame["Share %"] = (frame["Count"] / total * 100.0).round(1) if total else 0.0
    return frame


def select_top_opportunities(rows: pd.DataFrame, limit: int = 6) -> pd.DataFrame:
    """Highest-conviction BUY signals, in existing methodology order (no new score)."""
    if rows.empty or "Matrix Action" not in rows:
        return rows.iloc[0:0].copy()
    buys = rows[rows["Matrix Action"] == "BUY"].copy()
    if buys.empty:
        return buys
    if "Order" in buys:
        buys = buys.sort_values("Order")
    return buys.head(limit).reset_index(drop=True)


def build_regime_label(row: pd.Series) -> str:
    quarterly = str(row.get("Quarterly Trend", ""))
    monthly = str(row.get("Monthly Trend", ""))
    turn = str(row.get("Weekly Turn", ""))
    turn_short = turn.replace("SVOLTA", "TURN").replace("PROSEGUE", "CONT.")
    return f"Q {quarterly} · M {monthly} · W {turn_short}"


def build_reason(row: pd.Series) -> str:
    quarterly = str(row.get("Quarterly Trend", ""))
    monthly = str(row.get("Monthly Trend", ""))
    turn = str(row.get("Weekly Turn", ""))
    quarterly_phrase = _TREND_PHRASE.get(quarterly, quarterly.lower())
    monthly_phrase = _TREND_PHRASE.get(monthly, monthly.lower())
    turn_phrase = _TURN_PHRASE.get(turn, turn.lower())
    rating = int(row.get("Rating", 0) or 0)
    return (
        f"Quarterly trend {quarterly_phrase}, monthly trend {monthly_phrase}, "
        f"weekly composite {turn_phrase} — Reward/Risk {rating}/4."
    )


def build_risk(row: pd.Series) -> str:
    action = str(row.get("Matrix Action", ""))
    if action == "BUY":
        return "Invalidated by a fresh weekly downturn (SVOLTA DOWN) against the current trend backdrop."
    if action == "SELL SHORT":
        return "Invalidated by a fresh weekly upturn (SVOLTA UP) against the current trend backdrop."
    if action == "TAKE PROFIT":
        return "Position already extended; a reversal on the quarterly or monthly composite would confirm the exit."
    return "No new weekly junction yet — reassess once the weekly composite turns."


def classify_sector_group(sectors: pd.DataFrame) -> pd.DataFrame:
    """Group equal-weight sector performance into LEADING / NEUTRAL / LAGGING."""
    if sectors.empty or "Performance" not in sectors:
        result = sectors.copy()
        result["Group"] = pd.Series(dtype=str)
        return result
    result = sectors.copy()
    result["Group"] = result["Performance"].apply(
        lambda value: "LEADING" if value > 0 else ("LAGGING" if value < 0 else "NEUTRAL")
    )
    return result


@dataclass(frozen=True)
class OpportunitySnapshot:
    leading_sector: str
    leading_sector_perf: float
    lagging_sector: str
    lagging_sector_perf: float
    dispersion: float
    breadth_positive: int
    breadth_total: int
    breadth_label: str
    high_conviction_count: int
    top_ticker: str | None
    interpretation: str


def _breadth_label(positive: int, total: int) -> str:
    if total == 0:
        return "unclear"
    ratio = positive / total
    if ratio >= 0.65:
        return "broad"
    if ratio <= 0.35:
        return "narrow"
    return "mixed"


def build_snapshot(
    annotated_rows: pd.DataFrame,
    sectors: pd.DataFrame,
    performance_column: str,
    window_label: str,
) -> OpportunitySnapshot | None:
    """Summarise where capital is concentrating right now.

    `annotated_rows` must already carry a 'Conviction Tier' column (see
    `annotate_conviction`). `sectors` must already be ranked best-to-worst
    (see `screener.engine.build_sector_performance`).
    """
    if annotated_rows.empty or sectors.empty:
        return None

    best = sectors.iloc[0]
    worst = sectors.iloc[-1]

    clean = annotated_rows.dropna(subset=[performance_column]) if performance_column in annotated_rows else annotated_rows
    total = int(len(clean))
    positive = int((clean[performance_column] > 0).sum()) if total else 0
    breadth = _breadth_label(positive, total)

    high_conviction = int((annotated_rows["Conviction Tier"] == "High Conviction").sum())

    top = select_top_opportunities(annotated_rows, limit=1)
    top_ticker = str(top.iloc[0]["Ticker"]) if not top.empty else None

    dispersion = float(best["Performance"]) - float(worst["Performance"])

    if high_conviction and top_ticker:
        plural = "s" if high_conviction != 1 else ""
        conviction_clause = f"{high_conviction} high-conviction setup{plural}, led by {top_ticker}"
    elif high_conviction:
        plural = "s" if high_conviction != 1 else ""
        conviction_clause = f"{high_conviction} high-conviction setup{plural}"
    else:
        conviction_clause = "no high-conviction BUY setups"

    interpretation = (
        f"Capital is concentrating in {best['Sector']} ({float(best['Performance']):+.1f}% "
        f"{window_label.lower()}), while {worst['Sector']} lags ({float(worst['Performance']):+.1f}%). "
        f"Breadth is {breadth} — {positive} of {total} constituents are higher over {window_label.lower()} — "
        f"with {conviction_clause}."
    )

    return OpportunitySnapshot(
        leading_sector=str(best["Sector"]),
        leading_sector_perf=float(best["Performance"]),
        lagging_sector=str(worst["Sector"]),
        lagging_sector_perf=float(worst["Performance"]),
        dispersion=dispersion,
        breadth_positive=positive,
        breadth_total=total,
        breadth_label=breadth,
        high_conviction_count=high_conviction,
        top_ticker=top_ticker,
        interpretation=interpretation,
    )
