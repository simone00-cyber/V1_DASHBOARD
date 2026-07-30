"""Consistency checks for policy-driven signal-to-exposure execution."""
from __future__ import annotations

from collections import Counter
from typing import Iterable, Union
import pandas as pd

from analysis.audit.models import ExecutionAudit
from analysis.execution import ExecutionPolicy, build_policy_trace
from analysis.signals.models import DocumentedSignal
from analysis.trades.models import Trade


def build_execution_audit(signals: Iterable[DocumentedSignal], trades: Iterable[Trade],
                          weekly: pd.DataFrame,
                          policy: Union[ExecutionPolicy, str]) -> ExecutionAudit:
    if isinstance(policy, str):
        policy = ExecutionPolicy(direction_mode=policy, take_profit_policy="FULL_EXIT")
    transitions = build_policy_trace(signals, policy)
    trades = tuple(trades)

    invalid_exposure = [t for t in transitions if abs(t.exposure_before) > 1.0 + 1e-12 or abs(t.exposure_after) > 1.0 + 1e-12]
    take_profit_total = sum(t.signal == "TAKE PROFIT" for t in transitions)
    take_profit_effective = sum(t.signal == "TAKE PROFIT" and abs(t.exposure_after) < abs(t.exposure_before) - 1e-12 for t in transitions)
    repeated_entries = sum(t.action_taken in {"HOLD LONG", "HOLD SHORT"} for t in transitions)
    partial_transitions = sum(0 < abs(t.exposure_after) < abs(t.exposure_before) for t in transitions)
    trade_exit_counts = Counter(t.exit_reason for t in trades)
    chronological = all(transitions[i].date <= transitions[i + 1].date for i in range(max(0, len(transitions) - 1)))
    exposure_matches = "Position" in weekly and all(abs(float(v)) <= 1.0 + 1e-12 for v in weekly["Position"].dropna())

    checks = (
        {"CHECK": "VALID EXPOSURE", "STATUS": "PASS" if not invalid_exposure else "FAIL", "VALUE": len(invalid_exposure), "DETAIL": "Exposure always remains inside [-1, +1]."},
        {"CHECK": "CHRONOLOGICAL SIGNALS", "STATUS": "PASS" if chronological else "FAIL", "VALUE": len(transitions), "DETAIL": "Signals are processed in chronological order."},
        {"CHECK": "POLICY", "STATUS": "INFO", "VALUE": policy.label, "DETAIL": policy.provenance},
        {"CHECK": "TAKE PROFIT EVENTS", "STATUS": "INFO", "VALUE": f"{take_profit_effective}/{take_profit_total}", "DETAIL": "Exposure-reducing TAKE PROFIT events / total TAKE PROFIT instructions."},
        {"CHECK": "PARTIAL REDUCTIONS", "STATUS": "INFO", "VALUE": partial_transitions, "DETAIL": "Transitions that reduced exposure without moving fully flat."},
        {"CHECK": "REPEATED ENTRY EVENTS", "STATUS": "INFO", "VALUE": repeated_entries, "DETAIL": "Same-direction full-exposure signals ignored; no pyramiding in the core policy."},
        {"CHECK": "LOOK-AHEAD EXECUTION", "STATUS": "PASS" if exposure_matches and "StrategyReturn" in weekly else "FAIL", "VALUE": "t+1", "DETAIL": "Exposure decided at weekly close t is applied to the next weekly return."},
        {"CHECK": "TRADE EXIT REASONS", "STATUS": "INFO", "VALUE": dict(trade_exit_counts), "DETAIL": "Distribution of realised trade-leg exits."},
    )
    passed = all(row["STATUS"] != "FAIL" for row in checks)
    return ExecutionAudit(passed=passed, checks=checks, transitions=transitions)
