"""Presentation-only context for the Cyclical Position panel.

Neither function here changes the Composite Momentum matrix, the U/A/D/T phase
classification, or any other documented rule — they only relabel/contextualise
`CycleState` objects that `analysis.cyclical.engine.build_cyclical_engine` already
produces, for a compact visual read.

`DOCUMENTED_CYCLE_BARS` is a direct citation, not a derived statistic: it restates
the trough-to-trough cycle-length ranges published in "La Metodologia Ciclica"
(Francesco Caruso) — Short Term (weekly CM) 2.5-4 months, Medium Term (monthly CM)
9-24 months — converted to an approximate bar count on each timeframe. It is shown
next to `state_age` purely as historical context ("here is the typical range"), never
as a prediction of when the current phase will end.
"""

from __future__ import annotations

from analysis.cyclical.models import CycleState

# (low, high) bars, trough-to-trough, per the documented Short/Medium Term cycle
# lengths. Quarterly (Long Term, 30-60 months) is included for completeness but is
# rarely the tactically relevant read for a single-security chart.
DOCUMENTED_CYCLE_BARS: dict[str, tuple[int, int]] = {
    "WEEKLY": (10, 17),
    "MONTHLY": (9, 24),
    "QUARTERLY": (10, 20),
}

_TIMEFRAME_DOMINANCE_ORDER = ["QUARTERLY", "MONTHLY", "WEEKLY"]


def dominant_cyclical_timeframe(cycle_states: dict[str, CycleState]) -> str | None:
    """The highest timeframe currently showing a directional (non-NEUTRAL) phase.

    Mirrors the same higher-timeframe-dominates convention already used by
    `technical.multi_timeframe.build_multi_timeframe_alignment` — a higher timeframe
    sets the primary context, a lower one provides tactical timing.
    """
    for timeframe in _TIMEFRAME_DOMINANCE_ORDER:
        state = cycle_states.get(timeframe)
        if state is not None and state.phase != "NEUTRAL":
            return timeframe
    return next(iter(cycle_states), None)
