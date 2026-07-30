"""Trade-ledger construction from policy-driven exposure transitions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional
import pandas as pd

from analysis.execution import ExecutionPolicy, build_policy_trace
from analysis.signals.models import DocumentedSignal
from analysis.trades.models import Trade


@dataclass
class _Lot:
    entry: DocumentedSignal
    side: str
    size: float


def _close_lot(lot: _Lot, exit_signal: DocumentedSignal, close_size: float,
               bars_held: int, cost_bps: float,
               entry_valuation_price: float | None = None,
               exit_valuation_price: float | None = None) -> Trade:
    entry_value = float(entry_valuation_price if entry_valuation_price is not None else lot.entry.price)
    exit_value = float(exit_valuation_price if exit_valuation_price is not None else exit_signal.price)
    gross = exit_value / entry_value - 1.0
    if lot.side == "SHORT":
        gross = entry_value / exit_value - 1.0
    # Return is reported per unit of closed exposure. Size is retained as a
    # separate field so contribution analysis remains transparent.
    net = gross - 2.0 * cost_bps / 10000.0
    return Trade(
        side=lot.side,
        entry_date=lot.entry.date,
        entry_price=lot.entry.price,
        exit_date=exit_signal.date,
        exit_price=exit_signal.price,
        exit_reason=exit_signal.action,
        entry_rating=lot.entry.rating,
        entry_quarterly=lot.entry.quarterly_direction,
        entry_monthly=lot.entry.monthly_direction,
        entry_weekly_phase=lot.entry.weekly_phase,
        entry_weekly_composite=lot.entry.weekly_composite,
        bars_held=bars_held,
        gross_return=gross,
        net_return=net,
        size=float(close_size),
    )


def run_trade_engine(signals: Iterable[DocumentedSignal], weekly_index: pd.DatetimeIndex,
                     mode: str = "LONG_ONLY", cost_bps: float = 0.0,
                     close_open_trade: bool = False,
                     final_price: Optional[float] = None,
                     take_profit_policy: str = "FULL_EXIT",
                     partial_exit_fraction: float = 0.50,
                     valuation_prices: Optional[pd.Series] = None) -> List[Trade]:
    """Transform signals into a realised trade ledger.

    Partial exits create separate trade legs and preserve the remaining lot.
    """
    ordered = sorted(signals, key=lambda item: item.date)
    signal_by_date = {signal.date: signal for signal in ordered}
    location = {pd.Timestamp(date): i for i, date in enumerate(weekly_index)}
    policy = ExecutionPolicy(mode, take_profit_policy, partial_exit_fraction)
    transitions = build_policy_trace(ordered, policy)
    valuation = valuation_prices.sort_index() if valuation_prices is not None else None

    def valuation_at(date: pd.Timestamp, fallback: float) -> float:
        if valuation is None or valuation.empty:
            return float(fallback)
        date = pd.Timestamp(date)
        if date in valuation.index and pd.notna(valuation.loc[date]):
            return float(valuation.loc[date])
        prior = valuation.loc[valuation.index <= date].dropna()
        return float(prior.iloc[-1]) if not prior.empty else float(fallback)
    lots: List[_Lot] = []
    trades: List[Trade] = []

    def current_exposure() -> float:
        return sum((1.0 if lot.side == "LONG" else -1.0) * lot.size for lot in lots)

    for transition in transitions:
        signal = signal_by_date[transition.date]
        before = current_exposure()
        target = transition.exposure_after

        # Close exposure first, including reversals and partial monetisation.
        if before > target + 1e-12 and before > 0:
            amount = min(before - target, before) if target >= 0 else before
            remaining = amount
            for lot in list(lots):
                if lot.side != "LONG" or remaining <= 1e-12:
                    continue
                close_size = min(lot.size, remaining)
                bars = max(0, location.get(signal.date, 0) - location.get(lot.entry.date, 0))
                trades.append(_close_lot(lot, signal, close_size, bars, cost_bps, valuation_at(lot.entry.date, lot.entry.price), valuation_at(signal.date, signal.price)))
                lot.size -= close_size
                remaining -= close_size
                if lot.size <= 1e-12:
                    lots.remove(lot)
        elif before < target - 1e-12 and before < 0:
            amount = min(target - before, abs(before)) if target <= 0 else abs(before)
            remaining = amount
            for lot in list(lots):
                if lot.side != "SHORT" or remaining <= 1e-12:
                    continue
                close_size = min(lot.size, remaining)
                bars = max(0, location.get(signal.date, 0) - location.get(lot.entry.date, 0))
                trades.append(_close_lot(lot, signal, close_size, bars, cost_bps, valuation_at(lot.entry.date, lot.entry.price), valuation_at(signal.date, signal.price)))
                lot.size -= close_size
                remaining -= close_size
                if lot.size <= 1e-12:
                    lots.remove(lot)

        after_close = current_exposure()
        if target > after_close + 1e-12:
            lots.append(_Lot(signal, "LONG", target - after_close))
        elif target < after_close - 1e-12:
            lots.append(_Lot(signal, "SHORT", after_close - target))

    if close_open_trade and lots and final_price is not None and len(weekly_index):
        synthetic = DocumentedSignal(
            date=pd.Timestamp(weekly_index[-1]), action="END OF TEST", rating=0,
            price=float(final_price), quarterly_direction="", monthly_direction="",
            weekly_turn="", weekly_composite=0.0, weekly_phase="",
        )
        for lot in list(lots):
            bars = max(0, len(weekly_index) - 1 - location.get(lot.entry.date, 0))
            trades.append(_close_lot(lot, synthetic, lot.size, bars, cost_bps, valuation_at(lot.entry.date, lot.entry.price), valuation_at(synthetic.date, synthetic.price)))
    return trades
