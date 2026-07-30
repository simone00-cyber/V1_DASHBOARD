"""Week-by-week reconstruction of the documented cyclical decision matrix.

The engine does not execute trades. It exposes the higher-timeframe inputs,
the weekly condition, the matrix instruction and whether that instruction is a
new transition or a persistent state. Combinations absent from the published
12-case table are explicitly left undefined.
"""
from __future__ import annotations
from typing import Dict, List
import numpy as np
import pandas as pd

from caruso_analysis import STRATEGY_MATRIX
from analysis.cyclical.states import direction_series, phase_series, turn_series
from analysis.matrix.models import MatrixDecision


def _asof(target_index: pd.DatetimeIndex, source: pd.Series) -> pd.Series:
    clean = source.dropna().sort_index()
    if clean.empty:
        return pd.Series(index=target_index, dtype="object")
    left = pd.DataFrame({"date": pd.DatetimeIndex(target_index)}).sort_values("date")
    right = pd.DataFrame({"date": clean.index, "value": clean.values}).sort_values("date")
    merged = pd.merge_asof(left, right, on="date", direction="backward")
    return pd.Series(merged["value"].values, index=target_index)


def _decision_type(instruction: str) -> str:
    return {
        "BUY": "ENTRY / BULLISH DIRECTION",
        "SELL SHORT": "ENTRY / BEARISH DIRECTION",
        "TAKE PROFIT": "POSITION MANAGEMENT",
    }.get(instruction, "UNDEFINED BY PUBLIC MATRIX")


def _explanation(q: str, m: str, w: str, instruction: str, rating: int) -> str:
    if instruction == "NOT DEFINED":
        return (
            f"Quarterly={q}, Monthly={m}, Weekly={w}. This combination is not "
            "one of the 12 cases encoded from the public matrix; no decision is inferred."
        )
    return (
        f"Public matrix case: Quarterly={q}, Monthly={m}, Weekly={w} "
        f"-> {instruction}, rating {rating}/4."
    )


def build_matrix_timeline(frames: Dict[str, pd.DataFrame]) -> List[MatrixDecision]:
    required = {"WEEKLY", "MONTHLY", "QUARTERLY"}
    if not required.issubset(frames):
        return []

    weekly = frames["WEEKLY"].dropna(subset=["Composite", "Close"]).copy()
    monthly = frames["MONTHLY"].dropna(subset=["Composite"]).copy()
    quarterly = frames["QUARTERLY"].dropna(subset=["Composite"]).copy()
    if len(weekly) < 3 or len(monthly) < 2 or len(quarterly) < 2:
        return []

    q_aligned = _asof(weekly.index, direction_series(quarterly["Composite"].astype(float)))
    m_aligned = _asof(weekly.index, direction_series(monthly["Composite"].astype(float)))
    w_turns = turn_series(weekly["Composite"].astype(float))
    w_phases = phase_series(weekly["Composite"].astype(float))

    rows: List[MatrixDecision] = []
    previous_instruction = None
    stability = 0
    for date in weekly.index:
        q = q_aligned.loc[date]
        m = m_aligned.loc[date]
        if pd.isna(q) or pd.isna(m):
            continue
        q, m, w = str(q), str(m), str(w_turns.loc[date])
        matrix_value = STRATEGY_MATRIX.get((q, m, w))
        if matrix_value is None:
            instruction, rating = "NOT DEFINED", 0
        else:
            instruction, rating = matrix_value

        is_new = instruction != previous_instruction
        stability = 1 if is_new else stability + 1
        rows.append(MatrixDecision(
            date=pd.Timestamp(date),
            price=float(weekly.at[date, "Close"]),
            quarterly_direction=q,
            monthly_direction=m,
            weekly_turn=w,
            weekly_phase=str(w_phases.loc[date]),
            weekly_composite=float(weekly.at[date, "Composite"]),
            instruction=instruction,
            rating=int(rating),
            decision_type=_decision_type(instruction),
            is_new_event=is_new,
            stability_weeks=stability,
            explanation=_explanation(q, m, w, instruction, int(rating)),
            provenance="DOCUMENTED 12-CASE MATRIX" if matrix_value else "NOT SPECIFIED IN PUBLIC MATRIX",
        ))
        previous_instruction = instruction
    return rows


def matrix_timeline_frame(decisions: List[MatrixDecision]) -> pd.DataFrame:
    return pd.DataFrame([{
        "DATE": d.date,
        "PRICE": d.price,
        "QUARTERLY": d.quarterly_direction,
        "MONTHLY": d.monthly_direction,
        "WEEKLY TURN": d.weekly_turn,
        "WEEKLY PHASE": d.weekly_phase,
        "COMPOSITE": d.weekly_composite,
        "INSTRUCTION": d.instruction,
        "RATING": d.rating,
        "TYPE": d.decision_type,
        "NEW EVENT": d.is_new_event,
        "STABILITY WEEKS": d.stability_weeks,
        "WHY": d.explanation,
        "PROVENANCE": d.provenance,
    } for d in decisions])
