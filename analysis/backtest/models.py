from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple
import pandas as pd
from analysis.audit.models import ExecutionAudit
from analysis.signals.models import DocumentedSignal
from analysis.trades.models import Trade


@dataclass(frozen=True)
class BacktestResult:
    signals: Tuple[DocumentedSignal, ...]
    trades: Tuple[Trade, ...]
    weekly: pd.DataFrame
    metrics: dict
    diagnostics: pd.DataFrame
    mode: str
    cost_bps: float
    audit: ExecutionAudit
    take_profit_policy: str = "SIGNAL_ONLY"
    partial_exit_fraction: float = 0.50
    policy_label: str = ""
    policy_provenance: str = ""
    matrix_timeline: pd.DataFrame | None = None
