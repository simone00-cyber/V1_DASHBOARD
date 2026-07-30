from __future__ import annotations
import numpy as np
import pandas as pd
from analysis.trades.models import Trade
from .models import ResearchReport
from .statistics import summarize_group
from .confidence import confidence_label

CM_BINS = [-np.inf, -80, -50, 0, 50, 80, np.inf]
CM_LABELS = ["< -80", "-80 / -50", "-50 / 0", "0 / +50", "+50 / +80", "> +80"]
HOLDING_BINS = [-1, 4, 8, 13, 26, 52, np.inf]
HOLDING_LABELS = ["1-4", "5-8", "9-13", "14-26", "27-52", ">52"]


def _enrich(trades: list[Trade] | tuple[Trade, ...], weekly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for trade in trades:
        path = weekly.loc[(weekly.index >= trade.entry_date) & (weekly.index <= trade.exit_date), "Close"].dropna()
        if path.empty:
            mfe = mae = 0.0
        elif trade.side == "LONG":
            excursions = path / trade.entry_price - 1.0
            mfe, mae = float(excursions.max()), float(excursions.min())
        else:
            excursions = trade.entry_price / path - 1.0
            mfe, mae = float(excursions.max()), float(excursions.min())
        rows.append({
            "SIDE": trade.side,
            "ENTRY DATE": trade.entry_date,
            "EXIT DATE": trade.exit_date,
            "ENTRY RATING": trade.entry_rating,
            "QUARTERLY": trade.entry_quarterly,
            "MONTHLY": trade.entry_monthly,
            "WEEKLY PHASE": trade.entry_weekly_phase,
            "ENTRY CM": trade.entry_weekly_composite,
            "CM ZONE": pd.cut(pd.Series([trade.entry_weekly_composite]), CM_BINS, labels=CM_LABELS, right=False).iloc[0],
            "BARS": trade.bars_held,
            "HOLDING BUCKET": pd.cut(pd.Series([trade.bars_held]), HOLDING_BINS, labels=HOLDING_LABELS).iloc[0],
            "GROSS RETURN": trade.gross_return,
            "NET RETURN": trade.net_return,
            "SIZE": trade.size,
            "PNL CONTRIBUTION": trade.net_return * trade.size,
            "MFE": mfe,
            "MAE": mae,
            "EXIT REASON": trade.exit_reason,
            "SETUP": f"Q {trade.entry_quarterly} | M {trade.entry_monthly} | W {trade.entry_weekly_phase}",
        })
    return pd.DataFrame(rows)


def _group_summary(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    records = []
    grouper = columns[0] if len(columns) == 1 else columns
    for keys, group in frame.groupby(grouper, observed=True, dropna=False):
        keys = (keys,) if len(columns) == 1 else keys
        record = dict(zip(columns, keys))
        record.update(summarize_group(group))
        records.append(record)
    return pd.DataFrame(records).sort_values(["RESEARCH SCORE", "TRADES", "AVG RETURN"], ascending=[False, False, False])


def _heatmap(frame: pd.DataFrame, value: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    if value == "COUNT":
        return pd.pivot_table(frame, index="QUARTERLY", columns="WEEKLY PHASE", values="NET RETURN", aggfunc="count", fill_value=0)
    if value == "WIN RATE":
        working = frame.assign(WIN=(frame["NET RETURN"] > 0).astype(float))
        return pd.pivot_table(working, index="QUARTERLY", columns="WEEKLY PHASE", values="WIN", aggfunc="mean")
    return pd.pivot_table(frame, index="QUARTERLY", columns="WEEKLY PHASE", values="NET RETURN", aggfunc="mean")


def _hypotheses(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    tests = [
        ("H01", "Trades entered with Composite < 0 outperform those entered with Composite >= 0", frame["ENTRY CM"] < 0, frame["ENTRY CM"] >= 0),
        ("H02", "Trades entered with rating >= 4 outperform lower-rated trades", frame["ENTRY RATING"] >= 4, frame["ENTRY RATING"] < 4),
        ("H03", "Trades held more than 13 bars outperform shorter trades", frame["BARS"] > 13, frame["BARS"] <= 13),
    ]
    rows = []
    for code, text, test_mask, control_mask in tests:
        test = frame.loc[test_mask, "NET RETURN"].dropna()
        control = frame.loc[control_mask, "NET RETURN"].dropna()
        test_avg = float(test.mean()) if len(test) else np.nan
        control_avg = float(control.mean()) if len(control) else np.nan
        enough = len(test) >= 10 and len(control) >= 10
        if not enough:
            status = "INSUFFICIENT SAMPLE"
        else:
            status = "SUPPORTED" if test_avg > control_avg else "NOT SUPPORTED"
        rows.append({
            "ID": code,
            "HYPOTHESIS": text,
            "STATUS": status,
            "TEST TRADES": len(test),
            "CONTROL TRADES": len(control),
            "TEST AVG": test_avg,
            "CONTROL AVG": control_avg,
            "DIFFERENCE": test_avg - control_avg if pd.notna(test_avg) and pd.notna(control_avg) else np.nan,
            "CONFIDENCE": confidence_label(min(len(test), len(control))),
        })
    return pd.DataFrame(rows)



def _drawdown_episodes(weekly: pd.DataFrame, enriched: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Identify peak-to-trough drawdown episodes and link overlapping trades.

    Episodes begin on the last equity peak before equity moves below its running
    maximum. They end on the first recovery to that peak, or at the sample end.
    Attribution uses the peak-to-trough window, because that is the interval that
    creates the reported maximum loss.
    """
    required = {"Equity", "Drawdown"}
    if weekly.empty or not required.issubset(weekly.columns):
        return pd.DataFrame(), pd.DataFrame()

    equity = pd.to_numeric(weekly["Equity"], errors="coerce").dropna()
    if equity.empty:
        return pd.DataFrame(), pd.DataFrame()

    running_max = equity.cummax()
    underwater = equity < running_max * (1.0 - 1e-12)
    episodes: list[dict] = []
    links: list[dict] = []
    in_episode = False
    start_pos = 0
    episode_id = 0

    for pos, is_underwater in enumerate(underwater.to_numpy()):
        if is_underwater and not in_episode:
            in_episode = True
            start_pos = max(pos - 1, 0)
        recovered = in_episode and not is_underwater
        is_last = pos == len(equity) - 1
        if in_episode and (recovered or is_last):
            end_pos = pos if recovered else pos
            window = equity.iloc[start_pos:end_pos + 1]
            peak_value = float(equity.iloc[start_pos])
            dd = window / peak_value - 1.0
            trough_date = pd.Timestamp(dd.idxmin())
            trough_value = float(window.loc[trough_date])
            start_date = pd.Timestamp(window.index[0])
            end_date = pd.Timestamp(window.index[-1])
            recovery_date = end_date if recovered else pd.NaT
            episode_id += 1

            overlapping = pd.DataFrame()
            if not enriched.empty:
                entries = pd.to_datetime(enriched["ENTRY DATE"])
                exits = pd.to_datetime(enriched["EXIT DATE"])
                overlapping = enriched.loc[(entries <= trough_date) & (exits >= start_date)].copy()

            losses = pd.to_numeric(overlapping.get("PNL CONTRIBUTION", pd.Series(dtype=float)), errors="coerce")
            loss_sum = float(losses[losses < 0].sum()) if len(losses) else 0.0
            dominant_setup = "N/A"
            if not overlapping.empty:
                by_setup = overlapping.assign(
                    _LOSS=(-pd.to_numeric(overlapping["PNL CONTRIBUTION"], errors="coerce")).clip(lower=0)
                ).groupby("SETUP", observed=True)["_LOSS"].sum().sort_values(ascending=False)
                if not by_setup.empty and float(by_setup.iloc[0]) > 0:
                    dominant_setup = str(by_setup.index[0])

            episodes.append({
                "EPISODE": episode_id,
                "START": start_date,
                "TROUGH": trough_date,
                "RECOVERY": recovery_date,
                "ONGOING": not recovered,
                "MAX DRAWDOWN": float(trough_value / peak_value - 1.0),
                "PEAK EQUITY": peak_value,
                "TROUGH EQUITY": trough_value,
                "WEEKS TO TROUGH": int(max(0, equity.index.get_loc(trough_date) - equity.index.get_loc(start_date))),
                "TOTAL WEEKS": int(max(0, end_pos - start_pos)),
                "OVERLAPPING TRADES": int(len(overlapping)),
                "LOSING TRADE CONTRIBUTION": loss_sum,
                "DOMINANT LOSS SETUP": dominant_setup,
            })

            for _, trade in overlapping.iterrows():
                row = trade.to_dict()
                row.update({
                    "EPISODE": episode_id,
                    "DRAWDOWN START": start_date,
                    "DRAWDOWN TROUGH": trough_date,
                    "EPISODE MAX DRAWDOWN": float(trough_value / peak_value - 1.0),
                })
                links.append(row)

            in_episode = False

    episode_frame = pd.DataFrame(episodes)
    if not episode_frame.empty:
        episode_frame = episode_frame.sort_values("MAX DRAWDOWN").reset_index(drop=True)
        episode_frame["RANK"] = range(1, len(episode_frame) + 1)
    return episode_frame, pd.DataFrame(links)


def _loss_attribution(frame: pd.DataFrame, group_column: str) -> pd.DataFrame:
    """Attribute gross losing-trade contribution by an existing feature."""
    if frame.empty or group_column not in frame.columns:
        return pd.DataFrame()
    working = frame.copy()
    contribution = pd.to_numeric(working["PNL CONTRIBUTION"], errors="coerce").fillna(0.0)
    working["LOSS AMOUNT"] = (-contribution).clip(lower=0.0)
    working = working.loc[working["LOSS AMOUNT"] > 0].copy()
    if working.empty:
        return pd.DataFrame()
    grouped = working.groupby(group_column, observed=True, dropna=False).agg(
        LOSING_TRADES=("LOSS AMOUNT", "size"),
        TOTAL_LOSS=("LOSS AMOUNT", "sum"),
        AVG_LOSS=("LOSS AMOUNT", "mean"),
        WORST_TRADE=("PNL CONTRIBUTION", "min"),
    ).reset_index()
    total = float(grouped["TOTAL_LOSS"].sum())
    grouped["LOSS SHARE"] = grouped["TOTAL_LOSS"] / total if total > 0 else 0.0
    return grouped.sort_values(["LOSS SHARE", "LOSING_TRADES"], ascending=[False, False]).reset_index(drop=True)

def build_research_report(trades: list[Trade] | tuple[Trade, ...], weekly: pd.DataFrame) -> ResearchReport:
    enriched = _enrich(trades, weekly)
    drawdown_episodes, drawdown_trades = _drawdown_episodes(weekly, enriched)
    return ResearchReport(
        enriched_trades=enriched,
        setup_summary=_group_summary(enriched, ["SETUP"]),
        composite_summary=_group_summary(enriched, ["CM ZONE"]),
        holding_summary=_group_summary(enriched, ["HOLDING BUCKET"]),
        heatmap_average=_heatmap(enriched, "AVG"),
        heatmap_win_rate=_heatmap(enriched, "WIN RATE"),
        heatmap_count=_heatmap(enriched, "COUNT"),
        hypotheses=_hypotheses(enriched),
        drawdown_episodes=drawdown_episodes,
        drawdown_trades=drawdown_trades,
        loss_attribution_setup=_loss_attribution(enriched, "SETUP"),
        loss_attribution_monthly=_loss_attribution(enriched, "MONTHLY"),
        loss_attribution_rating=_loss_attribution(enriched, "ENTRY RATING"),
        loss_attribution_composite=_loss_attribution(enriched, "CM ZONE"),
    )
