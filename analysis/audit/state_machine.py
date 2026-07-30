"""Backward-compatible access to the policy-driven execution state machine."""
from __future__ import annotations

from typing import Iterable, Tuple

from analysis.audit.models import ExecutionTransition
from analysis.execution import ExecutionPolicy, build_policy_trace
from analysis.signals.models import DocumentedSignal

VALID_MODES = {"LONG_ONLY", "LONG_SHORT"}
VALID_STATES = {"FLAT", "LONG", "SHORT"}


def transition_for_signal(state: str, signal: DocumentedSignal, mode: str) -> ExecutionTransition:
    """Compatibility helper using the former full-exit TAKE PROFIT convention."""
    exposure = {"FLAT": 0.0, "LONG": 1.0, "SHORT": -1.0}.get(state)
    if exposure is None:
        raise ValueError(f"invalid execution state: {state}")
    # Build a synthetic trace starting from the requested state by prepending an
    # opening signal when necessary. This helper is retained for existing tests.
    policy = ExecutionPolicy(direction_mode=mode, take_profit_policy="FULL_EXIT")
    if state == "FLAT":
        return build_policy_trace([signal], policy)[0]
    seed_action = "BUY" if state == "LONG" else "SELL SHORT"
    seed = DocumentedSignal(
        date=signal.date - __import__('pandas').Timedelta(days=7), action=seed_action,
        rating=0, price=signal.price, quarterly_direction="", monthly_direction="",
        weekly_turn="", weekly_composite=0.0, weekly_phase="",
    )
    return build_policy_trace([seed, signal], policy)[-1]


def build_execution_trace(signals: Iterable[DocumentedSignal], mode: str,
                          take_profit_policy: str = "FULL_EXIT",
                          partial_exit_fraction: float = 0.50) -> Tuple[ExecutionTransition, ...]:
    policy = ExecutionPolicy(
        direction_mode=mode,
        take_profit_policy=take_profit_policy,
        partial_exit_fraction=partial_exit_fraction,
    )
    return build_policy_trace(signals, policy)
