"""Historical signal reconstruction for the documented cyclical matrix.

No proprietary price level, stop or Investitore Disciplinato rule is used.
Signals are generated on completed weekly bars and are executable only after
that bar has closed.
"""
from __future__ import annotations
from typing import Dict, List
import pandas as pd
from analysis.cyclical.states import phase_series
from analysis.security_signal import build_signal_history
from analysis.signals.models import DocumentedSignal


def build_documented_signal_history(frames: Dict[str, pd.DataFrame]) -> List[DocumentedSignal]:
    raw_events = build_signal_history(frames)
    if "WEEKLY" not in frames:
        return []
    weekly = frames["WEEKLY"].dropna(subset=["Composite", "Close"]).copy()
    phases = phase_series(weekly["Composite"].astype(float))
    signals: List[DocumentedSignal] = []
    for event in raw_events:
        if event.date not in weekly.index:
            continue
        signals.append(DocumentedSignal(
            date=event.date,
            action=event.action,
            rating=event.rating,
            price=float(weekly.at[event.date, "MarketClose"] if "MarketClose" in weekly.columns else weekly.at[event.date, "Close"]),
            quarterly_direction=event.quarterly_direction,
            monthly_direction=event.monthly_direction,
            weekly_turn=event.weekly_turn,
            weekly_composite=event.weekly_composite,
            weekly_phase=str(phases.loc[event.date]),
        ))
    return signals
