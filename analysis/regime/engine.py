from __future__ import annotations

from typing import Dict

import pandas as pd

from .common import slice_before
from .daily import compute_daily_layer
from .models import RegimeLayer
from .strategic import compute_strategic_layer
from .tactical import compute_tactical_score, tactical_diagnosis


def build_market_regime(close: pd.DataFrame) -> Dict[str, RegimeLayer]:
    strategic_score, strategic_diag, strategic_pillars = compute_strategic_layer(close)
    strategic_previous = slice_before(close, 21)
    strategic_prev_score, strategic_prev_diag, _ = compute_strategic_layer(strategic_previous)

    tactical_score, tactical_pillars = compute_tactical_score(close)
    tactical_previous = slice_before(close, 5)
    tactical_prev_score, _ = compute_tactical_score(tactical_previous)
    tactical_diag = tactical_diagnosis(tactical_score, tactical_prev_score)
    tactical_previous_2 = slice_before(close, 10)
    tactical_prev_prev_score, _ = compute_tactical_score(tactical_previous_2)
    tactical_prev_diag = tactical_diagnosis(tactical_prev_score, tactical_prev_prev_score)

    daily_score, daily_diag, daily_pillars = compute_daily_layer(close)
    daily_previous = slice_before(close, 1)
    daily_prev_score, daily_prev_diag, _ = compute_daily_layer(daily_previous)

    return {
        "STRATEGIC": RegimeLayer(
            "STRATEGIC", "STRUCTURAL BACKDROP", "3-6 MESI",
            strategic_diag, strategic_score, strategic_prev_diag,
            strategic_prev_score, strategic_pillars,
        ),
        "TACTICAL": RegimeLayer(
            "TACTICAL", "TACTICAL DIRECTION", "1-4 SETTIMANE",
            tactical_diag, tactical_score, tactical_prev_diag,
            tactical_prev_score, tactical_pillars,
        ),
        "DAILY": RegimeLayer(
            "DAILY", "TODAY'S TONE", "ULTIMA SEDUTA",
            daily_diag, daily_score, daily_prev_diag,
            daily_prev_score, daily_pillars,
        ),
    }
