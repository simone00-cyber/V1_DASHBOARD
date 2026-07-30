"""Stateful tactical signal engine for the documented cyclical matrix.

The module separates:
- the *event* generated on the latest completed weekly bar;
- the *active tactical position* inherited from the most recent matrix event;
- the conditions that would change the current state.

It does not add indicators beyond the documented Composite Momentum framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from caruso_analysis import STRATEGY_MATRIX


@dataclass(frozen=True)
class SignalEvent:
    date: pd.Timestamp
    action: str
    rating: int
    quarterly_direction: str
    monthly_direction: str
    weekly_turn: str
    weekly_composite: float


@dataclass(frozen=True)
class TacticalSignalState:
    current_position: str
    position_label: str
    signal_date: Optional[pd.Timestamp]
    signal_age_weeks: Optional[int]
    rating: int
    latest_event: str
    latest_event_date: pd.Timestamp
    status: str
    primary_trend: str
    intermediate_trend: str
    weekly_phase: str
    entry_trigger: str
    next_trigger: str
    invalidation_condition: str
    history: Tuple[SignalEvent, ...]


def _direction(series: pd.Series) -> pd.Series:
    diff = series.diff()
    return pd.Series(
        np.select([diff > 0, diff < 0], ["UP", "DOWN"], default="FLAT"),
        index=series.index,
        dtype="object",
    )


def _turn(series: pd.Series) -> pd.Series:
    slope = series.diff()
    previous_slope = slope.shift(1)

    result = pd.Series("FLAT", index=series.index, dtype="object")
    result.loc[(previous_slope <= 0) & (slope > 0)] = "SVOLTA UP"
    result.loc[(previous_slope >= 0) & (slope < 0)] = "SVOLTA DOWN"
    result.loc[(result == "FLAT") & (slope > 0)] = "PROSEGUE UP"
    result.loc[(result == "FLAT") & (slope < 0)] = "PROSEGUE DOWN"
    return result


def _asof_values(
    target_index: pd.DatetimeIndex,
    source: pd.Series,
) -> pd.Series:
    """Align the latest available completed higher-timeframe value to each week."""
    clean = source.dropna().sort_index()
    if clean.empty:
        return pd.Series(index=target_index, dtype="object")

    left = pd.DataFrame({"date": pd.DatetimeIndex(target_index)}).sort_values("date")
    right = pd.DataFrame({"date": clean.index, "value": clean.values}).sort_values("date")
    aligned = pd.merge_asof(left, right, on="date", direction="backward")
    return pd.Series(aligned["value"].values, index=target_index)


def build_signal_history(frames: Dict[str, pd.DataFrame]) -> List[SignalEvent]:
    """Reconstruct all documented matrix events on completed weekly bars."""
    required = {"WEEKLY", "MONTHLY", "QUARTERLY"}
    if not required.issubset(frames):
        return []

    weekly = frames["WEEKLY"].dropna(subset=["Composite"]).copy()
    monthly = frames["MONTHLY"].dropna(subset=["Composite"]).copy()
    quarterly = frames["QUARTERLY"].dropna(subset=["Composite"]).copy()

    if len(weekly) < 3 or len(monthly) < 2 or len(quarterly) < 2:
        return []

    weekly_turn = _turn(weekly["Composite"])
    monthly_direction = _direction(monthly["Composite"])
    quarterly_direction = _direction(quarterly["Composite"])

    aligned_monthly = _asof_values(weekly.index, monthly_direction)
    aligned_quarterly = _asof_values(weekly.index, quarterly_direction)

    events: List[SignalEvent] = []
    for date in weekly.index:
        q_direction = aligned_quarterly.loc[date]
        m_direction = aligned_monthly.loc[date]
        w_turn = weekly_turn.loc[date]

        if pd.isna(q_direction) or pd.isna(m_direction):
            continue

        matrix_key = (str(q_direction), str(m_direction), str(w_turn))
        if matrix_key not in STRATEGY_MATRIX:
            continue

        action, rating = STRATEGY_MATRIX[matrix_key]
        events.append(
            SignalEvent(
                date=pd.Timestamp(date),
                action=action,
                rating=rating,
                quarterly_direction=str(q_direction),
                monthly_direction=str(m_direction),
                weekly_turn=str(w_turn),
                weekly_composite=float(weekly.loc[date, "Composite"]),
            )
        )

    return events


def _position_from_action(action: str) -> str:
    if action == "BUY":
        return "LONG"
    if action == "SELL SHORT":
        return "SHORT"
    if action == "TAKE PROFIT":
        return "NEUTRAL"
    return "NEUTRAL"


def _weekly_phase(turn: str, q_direction: str, m_direction: str) -> str:
    if q_direction == "UP" and m_direction == "UP" and turn == "PROSEGUE DOWN":
        return "CORREZIONE SETTIMANALE IN TREND RIALZISTA"
    if q_direction == "DOWN" and m_direction == "DOWN" and turn == "PROSEGUE UP":
        return "RIMBALZO SETTIMANALE IN TREND RIBASSISTA"
    if turn == "SVOLTA UP":
        return "NUOVO FLESSO RIALZISTA"
    if turn == "SVOLTA DOWN":
        return "NUOVO FLESSO RIBASSISTA"
    if turn == "PROSEGUE UP":
        return "MOMENTUM SETTIMANALE IN PROSECUZIONE RIALZISTA"
    if turn == "PROSEGUE DOWN":
        return "MOMENTUM SETTIMANALE IN PROSECUZIONE RIBASSISTA"
    return "MOMENTUM SETTIMANALE LATERALE"


def _next_trigger(position: str, q_direction: str, m_direction: str, weekly_turn: str) -> Tuple[str, str, str]:
    """Return entry trigger, next trigger and invalidation condition."""
    if q_direction == "UP" and m_direction == "UP" and weekly_turn == "PROSEGUE DOWN":
        return (
            "NON CONFERMATO",
            "BUY se il Composite Momentum settimanale genera una nuova SVOLTA UP, mentre trimestrale e mensile restano UP.",
            "Il setup rialzista perde qualità se il mensile o il trimestrale passano DOWN prima della svolta settimanale.",
        )

    if q_direction == "DOWN" and m_direction == "DOWN" and weekly_turn == "PROSEGUE UP":
        return (
            "NON CONFERMATO",
            "SELL SHORT se il Composite Momentum settimanale genera una nuova SVOLTA DOWN, mentre trimestrale e mensile restano DOWN.",
            "Il setup ribassista perde qualità se il mensile o il trimestrale passano UP prima della svolta settimanale.",
        )

    if position == "LONG":
        return (
            "POSIZIONE LONG ATTIVA",
            "Monitorare una SVOLTA DOWN settimanale o una configurazione TAKE PROFIT prevista dalla matrice.",
            "La posizione viene rivalutata quando compare un evento SELL SHORT o TAKE PROFIT nella matrice documentale.",
        )

    if position == "SHORT":
        return (
            "POSIZIONE SHORT ATTIVA",
            "Monitorare una SVOLTA UP settimanale o una configurazione TAKE PROFIT prevista dalla matrice.",
            "La posizione viene rivalutata quando compare un evento BUY o TAKE PROFIT nella matrice documentale.",
        )

    if q_direction == "UP":
        return (
            "IN ATTESA",
            "Attendere una SVOLTA UP settimanale; il rating dipenderà dall'allineamento mensile al momento del trigger.",
            "Un passaggio del trimestrale a DOWN modifica il contesto primario.",
        )

    if q_direction == "DOWN":
        return (
            "IN ATTESA",
            "Attendere una SVOLTA DOWN settimanale; il rating dipenderà dall'allineamento mensile al momento del trigger.",
            "Un passaggio del trimestrale a UP modifica il contesto primario.",
        )

    return (
        "IN ATTESA",
        "Attendere un nuovo flesso settimanale con direzioni superiori determinabili.",
        "Dati insufficienti o quadro laterale.",
    )


def build_tactical_signal_state(
    frames: Dict[str, pd.DataFrame],
    summaries: Dict[str, object],
) -> TacticalSignalState:
    """Build the active signal state and the latest weekly event."""
    weekly_summary = summaries.get("WEEKLY")
    monthly_summary = summaries.get("MONTHLY")
    quarterly_summary = summaries.get("QUARTERLY")

    if not all([weekly_summary, monthly_summary, quarterly_summary]):
        latest_date = pd.Timestamp.now().normalize()
        return TacticalSignalState(
            current_position="NEUTRAL",
            position_label="QUADRO INCOMPLETO",
            signal_date=None,
            signal_age_weeks=None,
            rating=0,
            latest_event="DATI INSUFFICIENTI",
            latest_event_date=latest_date,
            status="NON DETERMINABILE",
            primary_trend="N/D",
            intermediate_trend="N/D",
            weekly_phase="N/D",
            entry_trigger="NON DETERMINABILE",
            next_trigger="Sono necessari trimestrale, mensile e settimanale.",
            invalidation_condition="N/D",
            history=tuple(),
        )

    history = build_signal_history(frames)
    latest_week_date = pd.Timestamp(weekly_summary.date)

    active_event: Optional[SignalEvent] = history[-1] if history else None
    current_position = _position_from_action(active_event.action) if active_event else "NEUTRAL"
    signal_date = active_event.date if active_event else None
    age = max(0, int((latest_week_date - signal_date).days // 7)) if signal_date is not None else None
    rating = active_event.rating if active_event else 0

    events_on_latest_bar = [event for event in history if event.date == latest_week_date]
    latest_bar_event = events_on_latest_bar[-1] if events_on_latest_bar else None
    latest_event = latest_bar_event.action if latest_bar_event else "NO NEW SIGNAL"

    q_direction = str(quarterly_summary.direction)
    m_direction = str(monthly_summary.direction)
    w_turn = str(weekly_summary.turn)
    weekly_phase = _weekly_phase(w_turn, q_direction, m_direction)

    if latest_bar_event and latest_bar_event.action in {"BUY", "SELL SHORT"}:
        status = "NEW SIGNAL"
    elif latest_bar_event and latest_bar_event.action == "TAKE PROFIT":
        status = "RISK REDUCTION / TAKE PROFIT"
    elif current_position in {"LONG", "SHORT"}:
        status = "ACTIVE / NO NEW EVENT"
    elif q_direction == "UP" and m_direction == "UP" and w_turn == "PROSEGUE DOWN":
        status = "WAITING FOR BULLISH TRIGGER"
    elif q_direction == "DOWN" and m_direction == "DOWN" and w_turn == "PROSEGUE UP":
        status = "WAITING FOR BEARISH TRIGGER"
    else:
        status = "NEUTRAL / MONITORING"

    entry_trigger, next_trigger, invalidation = _next_trigger(
        current_position,
        q_direction,
        m_direction,
        w_turn,
    )

    position_label = {
        "LONG": "LONG ATTIVO",
        "SHORT": "SHORT ATTIVO",
        "NEUTRAL": "NEUTRALE / ATTESA",
    }[current_position]

    return TacticalSignalState(
        current_position=current_position,
        position_label=position_label,
        signal_date=signal_date,
        signal_age_weeks=age,
        rating=rating,
        latest_event=latest_event,
        latest_event_date=latest_week_date,
        status=status,
        primary_trend=q_direction,
        intermediate_trend=m_direction,
        weekly_phase=weekly_phase,
        entry_trigger=entry_trigger,
        next_trigger=next_trigger,
        invalidation_condition=invalidation,
        history=tuple(history),
    )
