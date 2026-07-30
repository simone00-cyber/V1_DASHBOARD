"""Exposure state machine separated from the documented signal engine."""
from __future__ import annotations

from typing import Iterable, List, Tuple

from analysis.audit.models import ExecutionTransition
from analysis.execution.policies import ExecutionPolicy
from analysis.signals.models import DocumentedSignal


def _state(exposure: float) -> str:
    if exposure > 1e-12:
        return "LONG" if abs(exposure - 1.0) < 1e-12 else f"LONG {exposure:.0%}"
    if exposure < -1e-12:
        size = abs(exposure)
        return "SHORT" if abs(size - 1.0) < 1e-12 else f"SHORT {size:.0%}"
    return "FLAT"


def target_exposure(current: float, signal: DocumentedSignal, policy: ExecutionPolicy,
                    repeated_take_profit: bool = False) -> tuple[float, str, str]:
    event = signal.action
    if event == "BUY":
        if current >= 1.0 - 1e-12:
            return current, "HOLD LONG", "Repeated BUY ignored; pyramiding is not part of the core policy."
        action = "OPEN LONG" if abs(current) < 1e-12 else ("REVERSE SHORT TO LONG" if current < 0 else "RESTORE LONG EXPOSURE")
        return 1.0, action, "BUY sets the target exposure to a full long position."

    if event == "SELL SHORT":
        if policy.direction_mode == "LONG_SHORT":
            if current <= -1.0 + 1e-12:
                return current, "HOLD SHORT", "Repeated SELL SHORT ignored; pyramiding is not part of the core policy."
            action = "OPEN SHORT" if abs(current) < 1e-12 else ("REVERSE LONG TO SHORT" if current > 0 else "RESTORE SHORT EXPOSURE")
            return -1.0, action, "SELL SHORT sets the target exposure to a full short position."
        if current > 0:
            return 0.0, "CLOSE LONG", "SELL SHORT closes the long; short entry is disabled in Long only mode."
        return current, "REMAIN FLAT", "SELL SHORT cannot open a short in Long only mode."

    if event == "TAKE PROFIT":
        if abs(current) < 1e-12:
            return current, "REMAIN FLAT", "TAKE PROFIT has no open exposure to manage."
        if policy.take_profit_policy == "SIGNAL_ONLY":
            return current, "REGISTER TAKE PROFIT", "Management instruction retained without an undisclosed sizing assumption."
        if repeated_take_profit and not policy.repeat_take_profit:
            return current, "HOLD REDUCED EXPOSURE", "Repeated TAKE PROFIT in the same instruction run is not applied again."
        if policy.take_profit_policy == "FULL_EXIT":
            action = "CLOSE LONG" if current > 0 else "CLOSE SHORT"
            return 0.0, action, "Research scenario: TAKE PROFIT closes the full exposure."
        remaining = abs(current) * (1.0 - policy.partial_exit_fraction)
        target = remaining if current > 0 else -remaining
        if remaining < 1e-12:
            target = 0.0
        return target, f"REDUCE EXPOSURE {policy.partial_exit_fraction:.0%}", "Documented partial monetisation principle; percentage is a configurable research assumption."

    return current, "IGNORE", f"Unknown signal '{event}' ignored."


def build_policy_trace(signals: Iterable[DocumentedSignal], policy: ExecutionPolicy) -> Tuple[ExecutionTransition, ...]:
    exposure = 0.0
    previous_action = None
    rows: List[ExecutionTransition] = []
    for signal in sorted(signals, key=lambda item: item.date):
        before = exposure
        repeated_tp = signal.action == "TAKE PROFIT" and previous_action == "TAKE PROFIT"
        exposure, action, reason = target_exposure(before, signal, policy, repeated_tp)
        opened = None
        closed = None
        if before >= 0 and exposure < 0:
            closed = "LONG" if before > 0 else None
            opened = "SHORT"
        elif before <= 0 and exposure > 0:
            closed = "SHORT" if before < 0 else None
            opened = "LONG"
        elif abs(exposure) > abs(before) + 1e-12:
            opened = "LONG" if exposure > 0 else "SHORT"
        elif abs(exposure) < abs(before) - 1e-12:
            closed = "LONG" if before > 0 else "SHORT"
        rows.append(ExecutionTransition(
            date=signal.date,
            signal=signal.action,
            state_before=_state(before),
            action_taken=action,
            state_after=_state(exposure),
            reason=reason,
            signal_rating=signal.rating,
            signal_price=signal.price,
            opened_side=opened,
            closed_side=closed,
            exposure_before=float(before),
            exposure_after=float(exposure),
        ))
        previous_action = signal.action
    return tuple(rows)
