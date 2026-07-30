"""Execution and money-management policies.

The public signal engine is kept unchanged. These policies only define how a
portfolio exposure reacts to BUY, SELL SHORT and TAKE PROFIT instructions.
"""
from __future__ import annotations

from dataclasses import dataclass

VALID_TAKE_PROFIT_POLICIES = {"SIGNAL_ONLY", "FULL_EXIT", "PARTIAL_EXIT"}
VALID_DIRECTION_MODES = {"LONG_ONLY", "LONG_SHORT"}


@dataclass(frozen=True)
class ExecutionPolicy:
    """Transparent execution convention applied after signal generation.

    SIGNAL_ONLY does not change exposure on TAKE PROFIT because the source
    material does not publish a universal liquidation percentage.
    FULL_EXIT is a research scenario that maps TAKE PROFIT to flat.
    PARTIAL_EXIT is a parameterised research scenario.
    """

    direction_mode: str = "LONG_ONLY"
    take_profit_policy: str = "SIGNAL_ONLY"
    partial_exit_fraction: float = 0.50
    repeat_take_profit: bool = False

    def __post_init__(self) -> None:
        if self.direction_mode not in VALID_DIRECTION_MODES:
            raise ValueError("direction_mode must be LONG_ONLY or LONG_SHORT")
        if self.take_profit_policy not in VALID_TAKE_PROFIT_POLICIES:
            raise ValueError("take_profit_policy must be SIGNAL_ONLY, FULL_EXIT or PARTIAL_EXIT")
        if not 0.0 < float(self.partial_exit_fraction) <= 1.0:
            raise ValueError("partial_exit_fraction must be in (0, 1]")

    @property
    def label(self) -> str:
        if self.take_profit_policy == "SIGNAL_ONLY":
            tp = "TP signal only"
        elif self.take_profit_policy == "FULL_EXIT":
            tp = "TP full exit scenario"
        else:
            tp = f"TP partial exit {self.partial_exit_fraction:.0%}"
        direction = "Long only" if self.direction_mode == "LONG_ONLY" else "Long / Short"
        return f"{direction} | {tp}"

    @property
    def provenance(self) -> str:
        if self.take_profit_policy == "SIGNAL_ONLY":
            return "DOCUMENTED MEANING / NO UNDISCLOSED SIZE ASSUMPTION"
        return "RESEARCH EXECUTION SCENARIO"
