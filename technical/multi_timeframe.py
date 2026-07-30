from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import pandas as pd

from technical.assessment import classify_direction
from technical.engine import TechnicalSettings, resample_technical_frame
from technical.market_structure import TrendQuality, assess_trend_quality

_TIMEFRAME_ORDER = ["MONTHLY", "WEEKLY", "DAILY"]

# The daily-tuned MA periods (e.g. 20/50/200) don't fit weekly/monthly bar counts —
# MA200 on monthly data would need 200 months of history. Each timeframe gets its own
# proportionally-scaled periods and a shorter swing window so it can actually be
# assessed with the same amount of underlying daily history.
_TIMEFRAME_ADJUSTMENTS: dict[str, dict[str, object]] = {
    "WEEKLY": {"ma_periods": (10, 20, 40), "swing_window": 4},
    "MONTHLY": {"ma_periods": (6, 12, 24), "swing_window": 3},
}


def _settings_for_timeframe(settings: TechnicalSettings, timeframe: str) -> TechnicalSettings:
    adjustments = _TIMEFRAME_ADJUSTMENTS.get(timeframe)
    return dataclasses.replace(settings, **adjustments) if adjustments else settings


@dataclass(frozen=True)
class TimeframeRead:
    timeframe: str
    direction: str
    trend_quality: TrendQuality


@dataclass(frozen=True)
class MultiTimeframeAlignment:
    reads: tuple[TimeframeRead, ...]
    dominant_timeframe: str
    agreement: str
    summary: str


def build_multi_timeframe_alignment(daily_frame: pd.DataFrame, settings: TechnicalSettings) -> MultiTimeframeAlignment:
    """Combine Daily/Weekly/Monthly technical reads into an explicit alignment call:
    do the timeframes reinforce each other or conflict, and which one dominates?

    Per Caruso's documented cyclical hierarchy convention (a higher timeframe sets the
    primary trend context, a lower timeframe provides tactical timing), the highest
    timeframe showing a clear, non-range-bound direction is treated as dominant. This
    is a technical-engine-only synthesis built on `technical/market_structure.py`; it
    does not reuse or alter the Cyclical Composite Momentum matrix in any way.
    """
    reads: list[TimeframeRead] = []
    for timeframe in _TIMEFRAME_ORDER:
        resampled = resample_technical_frame(daily_frame, timeframe)
        tf_settings = _settings_for_timeframe(settings, timeframe)
        if len(resampled.dropna(subset=["Close"])) < max(tf_settings.ma_periods, default=30):
            continue
        quality = assess_trend_quality(resampled, tf_settings)
        reads.append(TimeframeRead(timeframe, classify_direction(quality), quality))

    if not reads:
        return MultiTimeframeAlignment((), "N/A", "INSUFFICIENT DATA", "Not enough history to assess multiple timeframes.")

    directional = [r for r in reads if not r.direction.startswith("RANGE")]
    bullish = [r for r in directional if r.direction.startswith("UPTREND")]
    bearish = [r for r in directional if r.direction.startswith("DOWNTREND")]
    dominant = directional[0] if directional else reads[0]

    if directional and len(bullish) == len(directional):
        agreement = "ALIGNED BULLISH"
    elif directional and len(bearish) == len(directional):
        agreement = "ALIGNED BEARISH"
    elif bullish and bearish:
        agreement = "CONFLICTED"
    else:
        agreement = "MOSTLY RANGE-BOUND"

    labels = [f"{r.timeframe.title()}: {r.direction.split(' (')[0].title()}" for r in reads]
    timeframe_names = ", ".join(r.timeframe.title() for r in reads)
    if agreement == "ALIGNED BULLISH":
        summary = f"All available timeframes ({timeframe_names}) confirm an uptrend — {dominant.timeframe.title()} sets the dominant context."
    elif agreement == "ALIGNED BEARISH":
        summary = f"All available timeframes ({timeframe_names}) confirm a downtrend — {dominant.timeframe.title()} sets the dominant context."
    elif agreement == "CONFLICTED":
        summary = f"Timeframes disagree ({'; '.join(labels)}) — {dominant.timeframe.title()} dominates until the lower timeframes catch up or the higher timeframe breaks."
    else:
        summary = f"No timeframe currently shows a clean directional trend ({'; '.join(labels)})."

    return MultiTimeframeAlignment(tuple(reads), dominant.timeframe, agreement, summary)
