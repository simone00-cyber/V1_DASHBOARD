from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TechnicalSettings:
    swing_window: int = 5
    lookback: int = 252
    zone_tolerance_pct: float = 1.0
    proximity_pct: float = 2.0
    breakout_buffer_pct: float = 0.3
    breakout_confirmations: int = 1
    rsi_period: int = 14
    ma_periods: tuple[int, ...] = (20, 50, 200)
    pattern_tolerance_pct: float = 3.0
    timeframe: str = "DAILY"


@dataclass(frozen=True)
class TechnicalSnapshot:
    ticker: str
    last: float
    data_date: Any
    support_low: float | None
    support_high: float | None
    resistance_low: float | None
    resistance_high: float | None
    distance_support_pct: float | None
    distance_resistance_pct: float | None
    rsi: float | None
    state: str
    setups: tuple[str, ...]
    patterns: tuple[str, ...]
    diagnostics: dict[str, Any]


TIMEFRAME_RULES: dict[str, str | None] = {"DAILY": None, "WEEKLY": "W-FRI", "MONTHLY": "ME"}


def resample_technical_frame(frame: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    label = str(timeframe).upper()
    if label not in TIMEFRAME_RULES:
        raise ValueError(f"Unsupported technical timeframe: {timeframe}")
    clean = frame.sort_index().copy()
    rule = TIMEFRAME_RULES[label]
    if rule is None:
        return clean
    aggregation = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in clean.columns:
        aggregation["Volume"] = "sum"
    return clean.resample(rule).agg(aggregation).dropna(subset=["Open", "High", "Low", "Close"])


def parse_ma_periods(value: str | Iterable[int], maximum: int = 8) -> tuple[int, ...]:
    raw = value.replace(";", ",").split(",") if isinstance(value, str) else list(value)
    periods: list[int] = []
    for item in raw:
        try:
            period = int(str(item).strip())
        except (TypeError, ValueError):
            continue
        if period > 1 and period not in periods:
            periods.append(period)
    return tuple(sorted(periods[:maximum]))


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    period = max(2, int(period))
    delta = close.astype(float).diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)
    avg_gain = gains.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = losses.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.where(avg_loss.ne(0.0), 100.0).clip(0.0, 100.0)


def calculate_atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder-style Average True Range, used for the volatility-regime read."""
    period = max(2, int(period))
    high, low, close = frame["High"].astype(float), frame["Low"].astype(float), frame["Close"].astype(float)
    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return true_range.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def add_moving_averages(frame: pd.DataFrame, periods: Iterable[int]) -> pd.DataFrame:
    result = frame.copy()
    for period in parse_ma_periods(periods):
        result[f"MA{period}"] = result["Close"].rolling(period, min_periods=period).mean()
    return result


def _swing_points(series: pd.Series, window: int, mode: str) -> pd.Series:
    window = max(2, int(window))
    rolling = series.rolling(window * 2 + 1, center=True, min_periods=window * 2 + 1)
    mask = series.eq(rolling.max()) if mode == "high" else series.eq(rolling.min())
    return series[mask].dropna()


def _cluster_levels(points: pd.Series, tolerance_pct: float, initial_role: str) -> list[dict[str, Any]]:
    if points.empty:
        return []
    clusters: list[dict[str, Any]] = []
    for date, raw_value in points.sort_index().items():
        value = float(raw_value)
        match = next((c for c in clusters if abs(value / c["center"] - 1.0) * 100 <= tolerance_pct), None)
        if match is None:
            clusters.append({"values": [value], "dates": [date], "center": value})
        else:
            match["values"].append(value)
            match["dates"].append(date)
            match["center"] = float(np.mean(match["values"]))
    output: list[dict[str, Any]] = []
    for cluster in clusters:
        values = cluster["values"]
        center = float(np.mean(values))
        half_width = max(center * tolerance_pct / 200.0, float(np.std(values)) if len(values) > 1 else 0.0)
        output.append({
            "center": center,
            "low": center - half_width,
            "high": center + half_width,
            "touches": len(values),
            "first_date": min(cluster["dates"]),
            "last_date": max(cluster["dates"]),
            "initial_role": initial_role,
        })
    return output


def _confirmed_break_index(close: pd.Series, level: float, direction: str, buffer_pct: float, confirmations: int) -> Any | None:
    threshold = level * (1 + buffer_pct / 100) if direction == "above" else level * (1 - buffer_pct / 100)
    condition = close > threshold if direction == "above" else close < threshold
    run = condition.rolling(max(1, int(confirmations))).sum()
    matches = run[run >= max(1, int(confirmations))]
    return matches.index[0] if not matches.empty else None


def _classify_level(zone: dict[str, Any], close: pd.Series, low: pd.Series, high: pd.Series, settings: TechnicalSettings) -> dict[str, Any]:
    result = dict(zone)
    origin = zone["first_date"]
    c = close.loc[close.index >= origin]
    lo = low.reindex(c.index)
    hi = high.reindex(c.index)
    initial = zone["initial_role"]
    result.update({"role": initial, "state": "ACTIVE", "break_date": None, "retest_date": None})

    if initial == "RESISTANCE":
        break_date = _confirmed_break_index(c, zone["high"], "above", settings.breakout_buffer_pct, settings.breakout_confirmations)
        if break_date is not None:
            result.update({"state": "BROKEN", "break_date": break_date})
            post = c.loc[c.index > break_date]
            post_low = lo.reindex(post.index)
            retest = post[(post_low <= zone["high"] * (1 + settings.proximity_pct / 100)) & (post >= zone["center"])]
            if not retest.empty:
                result.update({"role": "SUPPORT", "state": "FLIPPED", "retest_date": retest.index[0]})
                if c.iloc[-1] < zone["low"] * (1 - settings.breakout_buffer_pct / 100):
                    result.update({"role": "RESISTANCE", "state": "FAILED FLIP"})
    else:
        break_date = _confirmed_break_index(c, zone["low"], "below", settings.breakout_buffer_pct, settings.breakout_confirmations)
        if break_date is not None:
            result.update({"state": "BROKEN", "break_date": break_date})
            post = c.loc[c.index > break_date]
            post_high = hi.reindex(post.index)
            retest = post[(post_high >= zone["low"] * (1 - settings.proximity_pct / 100)) & (post <= zone["center"])]
            if not retest.empty:
                result.update({"role": "RESISTANCE", "state": "FLIPPED", "retest_date": retest.index[0]})
                if c.iloc[-1] > zone["high"] * (1 + settings.breakout_buffer_pct / 100):
                    result.update({"role": "SUPPORT", "state": "FAILED FLIP"})

    age = max(1, len(close.loc[close.index >= origin]))
    recency = max(0.0, 1.0 - len(close.loc[close.index > zone["last_date"]]) / age)
    result["strength"] = int(round(np.clip(35 + zone["touches"] * 10 + recency * 20 + (10 if result["state"] == "FLIPPED" else 0), 0, 100)))
    return result


def find_support_resistance(frame: pd.DataFrame, settings: TechnicalSettings) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    recent = frame.tail(settings.lookback).copy()
    close = recent["Close"].dropna()
    last = float(close.iloc[-1])
    raw = _cluster_levels(_swing_points(recent["Low"], settings.swing_window, "low"), settings.zone_tolerance_pct, "SUPPORT")
    raw += _cluster_levels(_swing_points(recent["High"], settings.swing_window, "high"), settings.zone_tolerance_pct, "RESISTANCE")
    classified = [_classify_level(z, close, recent["Low"], recent["High"], settings) for z in raw]
    supports = [z for z in classified if z["role"] == "SUPPORT" and z["center"] <= last * 1.04]
    resistances = [z for z in classified if z["role"] == "RESISTANCE" and z["center"] >= last * 0.96]
    supports.sort(key=lambda z: (abs(last - z["center"]), -z["strength"], -z["touches"]))
    resistances.sort(key=lambda z: (abs(last - z["center"]), -z["strength"], -z["touches"]))
    return supports, resistances


@dataclass(frozen=True)
class FibonacciLevels:
    """Retracement levels for the single most recent dominant swing leg.

    Uses the classic 38.2/50/61.8 midpoints of the retracement bands Caruso's own
    technical glossary documents (33-38%, 50%, 62-66%). This is geometry over swing
    points that already exist elsewhere in the engine — no new time-series indicator.
    """

    direction: str
    swing_start: tuple[Any, float]
    swing_end: tuple[Any, float]
    levels: dict[str, float]


_FIB_RATIOS: dict[str, float] = {"38.2%": 0.382, "50.0%": 0.5, "61.8%": 0.618}


def compute_fibonacci_levels(frame: pd.DataFrame, settings: TechnicalSettings) -> FibonacciLevels | None:
    recent = frame.tail(min(settings.lookback, 260))
    highs = _swing_points(recent["High"], settings.swing_window, "high")
    lows = _swing_points(recent["Low"], settings.swing_window, "low")
    if highs.empty or lows.empty:
        return None
    high_date, high_value = highs.index[-1], float(highs.iloc[-1])
    low_date, low_value = lows.index[-1], float(lows.iloc[-1])
    if high_value <= low_value:
        return None
    span = high_value - low_value
    if high_date > low_date:
        direction = "RETRACEMENT OF UPSWING"
        levels = {label: round(high_value - span * ratio, 4) for label, ratio in _FIB_RATIOS.items()}
        swing_start, swing_end = (low_date, low_value), (high_date, high_value)
    else:
        direction = "RETRACEMENT OF DOWNSWING"
        levels = {label: round(low_value + span * ratio, 4) for label, ratio in _FIB_RATIOS.items()}
        swing_start, swing_end = (high_date, high_value), (low_date, low_value)
    return FibonacciLevels(direction=direction, swing_start=swing_start, swing_end=swing_end, levels=levels)


def _distance_pct(price: float, level: float | None) -> float | None:
    return None if level in (None, 0) else (price / float(level) - 1.0) * 100.0


def _confirmed_break(close: pd.Series, level: float, direction: str, buffer_pct: float, confirmations: int) -> bool:
    return _confirmed_break_index(close.tail(max(20, confirmations + 2)), level, direction, buffer_pct, confirmations) is not None


def _ma_events(frame: pd.DataFrame, periods: tuple[int, ...]) -> list[str]:
    events: list[str] = []
    periods = parse_ma_periods(periods)
    if len(frame) < 3:
        return events
    close = frame["Close"]
    for period in periods:
        ma = close.rolling(period, min_periods=period).mean()
        if ma.dropna().empty:
            continue
        events.append(f"Price {'above' if close.iloc[-1] > ma.iloc[-1] else 'below'} MA{period}")
    for fast, slow in zip(periods, periods[1:]):
        fast_ma = close.rolling(fast, min_periods=fast).mean()
        slow_ma = close.rolling(slow, min_periods=slow).mean()
        if fast_ma.iloc[-2:].isna().any() or slow_ma.iloc[-2:].isna().any():
            continue
        previous, current = fast_ma.iloc[-2] - slow_ma.iloc[-2], fast_ma.iloc[-1] - slow_ma.iloc[-1]
        if previous <= 0 < current:
            events.append(f"Bullish MA crossover: MA{fast} above MA{slow}")
        elif previous >= 0 > current:
            events.append(f"Bearish MA crossover: MA{fast} below MA{slow}")
    return events


def detect_rsi_divergence(frame: pd.DataFrame, rsi: pd.Series, swing_window: int = 5, max_separation: int = 80) -> str | None:
    recent = frame.tail(max(120, max_separation + 20))
    aligned = rsi.reindex(recent.index)
    lows = _swing_points(recent["Low"], swing_window, "low")
    highs = _swing_points(recent["High"], swing_window, "high")
    if len(lows) >= 2:
        d1, d2 = lows.index[-2], lows.index[-1]
        if pd.notna(aligned.get(d1)) and pd.notna(aligned.get(d2)) and lows.iloc[-1] < lows.iloc[-2] and aligned[d2] > aligned[d1]:
            return "Potential bullish RSI divergence"
    if len(highs) >= 2:
        d1, d2 = highs.index[-2], highs.index[-1]
        if pd.notna(aligned.get(d1)) and pd.notna(aligned.get(d2)) and highs.iloc[-1] > highs.iloc[-2] and aligned[d2] < aligned[d1]:
            return "Potential bearish RSI divergence"
    return None


def _slope(values: pd.Series) -> float:
    clean = values.dropna().astype(float)
    return 0.0 if len(clean) < 3 else float(np.polyfit(np.arange(len(clean), dtype=float), clean.to_numpy(), 1)[0])


def _similarity(a: float, b: float) -> float:
    return float(np.clip(1 - abs(a - b) / max(abs(a), abs(b), 1e-9), 0, 1))


def _pattern_status(frame: pd.DataFrame, direction: str, trigger: float | None, end: Any) -> str:
    if trigger is None:
        return "DEVELOPING"
    after = frame.loc[frame.index >= end, "Close"].dropna()
    if after.empty:
        return "DEVELOPING"
    confirmed = (after > trigger).any() if direction == "BULLISH" else (after < trigger).any()
    if not confirmed:
        return "DEVELOPING"
    later = after.iloc[1:]
    if not later.empty and ((direction == "BULLISH" and later.min() <= trigger * 1.01) or (direction == "BEARISH" and later.max() >= trigger * 0.99)):
        return "RETESTED"
    return "CONFIRMED"


def _volume_trend_bias(frame: pd.DataFrame, start: Any, end: Any) -> float:
    """Small confidence adjustment (-8..+8) from the volume trend during formation.

    Volume contracting into a consolidation is the textbook constructive read
    (buyers/sellers exhausting into the base before the next impulse); volume
    expanding erratically through the same window is treated as a mild penalty.
    Returns 0 when no Volume column is available rather than guessing.
    """
    if "Volume" not in frame.columns:
        return 0.0
    window = frame.loc[start:end, "Volume"].dropna()
    if len(window) < 5:
        return 0.0
    half = len(window) // 2
    first_half, second_half = float(window.iloc[:half].mean()), float(window.iloc[half:].mean())
    if first_half <= 0:
        return 0.0
    change = (second_half / first_half) - 1.0
    return float(np.clip(-change * 20.0, -8.0, 8.0))


def _breakout_volume_confirms(frame: pd.DataFrame, lookback: int = 20) -> bool:
    """True when the most recent bars show volume expansion versus the prior baseline."""
    if "Volume" not in frame.columns:
        return False
    volume = frame["Volume"].dropna().tail(lookback)
    if len(volume) < 5:
        return False
    recent_avg = volume.tail(3).mean()
    baseline_avg = volume.iloc[:-3].mean() if len(volume) > 3 else volume.mean()
    return bool(baseline_avg > 0 and recent_avg > baseline_avg * 1.2)


def _expected_breakout_zone(trigger: float | None, buffer_pct: float) -> tuple[float, float] | None:
    """A band around the documented trigger level, sized with the same buffer used to confirm breaks."""
    if trigger is None:
        return None
    band = abs(trigger) * buffer_pct / 100.0
    return (round(trigger - band, 4), round(trigger + band, 4))


def _completion_pct(anchors: list[tuple[Any, float]], trigger: float | None, direction: str, last_close: float) -> float | None:
    """How far price has already travelled from the pattern's furthest extreme toward its trigger, as a %.

    This is a distance-travelled proxy, not a projected time-to-completion — it is
    only defined for patterns with a directional trigger (NEUTRAL patterns return
    None since there is no breakout level yet to measure progress against).
    """
    if trigger is None or direction not in ("BULLISH", "BEARISH"):
        return None
    values = [v for _, v in anchors]
    if direction == "BULLISH":
        base = min(values)
        total, progressed = trigger - base, last_close - base
    else:
        base = max(values)
        total, progressed = base - trigger, base - last_close
    if total <= 0:
        return None
    return float(np.clip(progressed / total * 100.0, 0.0, 100.0))


def _fit_r2(points: pd.Series) -> float:
    """Goodness-of-fit of a straight trendline through swing points — gates geometric patterns
    (triangles/wedges/channels/rectangles) so a scattered set of swings isn't drawn as a clean line."""
    values = points.astype(float).to_numpy()
    if len(values) < 3:
        return 0.0
    x = np.arange(len(values), dtype=float)
    slope, intercept = np.polyfit(x, values, 1)
    fitted = slope * x + intercept
    ss_res = float(np.sum((values - fitted) ** 2))
    ss_tot = float(np.sum((values - values.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot else 1.0


def _record(name: str, category: str, direction: str, anchors: list[tuple[Any, float]], *, frame: pd.DataFrame,
            confidence: float, trigger: float | None = None, upper: list[tuple[Any, float]] | None = None,
            lower: list[tuple[Any, float]] | None = None, highlight_start: Any | None = None,
            highlight_end: Any | None = None, notes: str = "", settings: TechnicalSettings | None = None,
            volume_bias: float = 0.0) -> dict[str, Any]:
    dates = [p[0] for p in anchors]
    start, end = min(dates), max(dates)
    values = [v for _, v in anchors]
    invalidation: float | None = None
    if direction == "BULLISH":
        invalidation = min(values)
    elif direction == "BEARISH":
        invalidation = max(values)
    buffer_pct = settings.breakout_buffer_pct if settings is not None else 0.3
    last_close = float(frame["Close"].iloc[-1])
    return {
        "name": name,
        "category": category,
        "direction": direction,
        "confidence": int(round(np.clip(confidence + volume_bias, 0, 100))),
        "status": _pattern_status(frame, direction, trigger, end),
        "trigger": trigger,
        "invalidation": invalidation,
        "completion_pct": _completion_pct(anchors, trigger, direction, last_close),
        "expected_breakout_zone": _expected_breakout_zone(trigger, buffer_pct),
        "start": start,
        "end": end,
        "highlight_start": highlight_start or start,
        "highlight_end": highlight_end or end,
        "anchors": anchors,
        "upper": upper or [],
        "lower": lower or [],
        "notes": notes,
    }


def _suppress_overlaps(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only the highest-confidence pattern among candidates whose anchor ranges
    substantially overlap, even across different names/categories — avoids reporting
    multiple overlapping patterns over the same swing set unless clearly distinct."""
    ordered = sorted(details, key=lambda d: -d["confidence"])
    kept: list[dict[str, Any]] = []
    for candidate in ordered:
        c_start, c_end = candidate["start"], candidate["end"]
        candidate_span = (c_end - c_start) or pd.Timedelta(days=1)
        overlaps = False
        for k in kept:
            latest_start = max(c_start, k["start"])
            earliest_end = min(c_end, k["end"])
            if latest_start > earliest_end:
                continue
            k_span = (k["end"] - k["start"]) or pd.Timedelta(days=1)
            # Compare against the SMALLER of the two spans so a small pattern fully
            # contained inside a larger, lower-confidence one is still caught —
            # measuring only against the candidate's own span would miss that case.
            if (earliest_end - latest_start) >= min(candidate_span, k_span) * 0.6:
                overlaps = True
                break
        if not overlaps:
            kept.append(candidate)
    return kept


def detect_pattern_details(frame: pd.DataFrame, settings: TechnicalSettings) -> list[dict[str, Any]]:
    """Precision-first heuristic recognition. Candidates require visual review and are
    never trading signals. False positives are treated as far worse than false
    negatives: geometric formations require a clean trendline fit (see `_fit_r2`) and
    double/triple extremes require a genuine intervening retracement, not just two
    adjacent noisy bars."""
    recent = frame.tail(min(settings.lookback, 260)).copy()
    highs = _swing_points(recent["High"], settings.swing_window, "high")
    lows = _swing_points(recent["Low"], settings.swing_window, "low")
    details: list[dict[str, Any]] = []
    tol = settings.pattern_tolerance_pct / 100.0

    # Double/triple formations — require both comparable extremes AND a genuine
    # intervening retracement (otherwise two adjacent bars of one high would qualify).
    for points, label, direction, category in ((highs, "top", "BEARISH", "REVERSAL"), (lows, "bottom", "BULLISH", "REVERSAL")):
        if len(points) >= 2:
            pts = points.tail(2); a, b = map(float, pts.values)
            similarity = _similarity(a, b)
            between = recent.loc[pts.index[0]:pts.index[1]]
            pivot = float(between["Low"].min() if label == "top" else between["High"].max())
            retrace_pct = abs(a - pivot) / max(abs(a), 1e-9)
            if similarity >= 1 - tol and retrace_pct >= tol:
                details.append(_record(f"Potential double {label}", category, direction, list(zip(pts.index, pts.astype(float))), frame=recent,
                                       confidence=55 + similarity * 35, trigger=pivot, notes="Two comparable swing extremes with a genuine intervening retracement.",
                                       settings=settings))
        if len(points) >= 3:
            pts = points.tail(3); vals = pts.astype(float)
            dispersion = float(vals.std() / max(vals.mean(), 1e-9))
            span = recent.loc[pts.index[0]:pts.index[-1]]
            pivot = float(span["Low"].min() if label == "top" else span["High"].max())
            retrace_pct = abs(float(vals.mean()) - pivot) / max(abs(float(vals.mean())), 1e-9)
            if dispersion <= tol and retrace_pct >= tol:
                details.append(_record(f"Potential triple {label}", category, direction, list(zip(pts.index, vals)), frame=recent,
                                       confidence=65 + max(0, 1 - dispersion / max(tol, 1e-9)) * 25, trigger=pivot,
                                       notes="Three comparable swing extremes with a genuine intervening retracement.", settings=settings))

    # Head and shoulders and inverse head and shoulders.
    if len(highs) >= 3:
        hp = highs.tail(3); left, head, right = map(float, hp.values)
        shoulder_similarity = _similarity(left, right)
        prominence = head / max(left, right) - 1
        if shoulder_similarity >= 1 - tol * 1.6 and prominence >= max(0.02, tol * 0.7):
            between1 = recent.loc[hp.index[0]:hp.index[1], "Low"].idxmin(); between2 = recent.loc[hp.index[1]:hp.index[2], "Low"].idxmin()
            n1, n2 = float(recent.at[between1, "Low"]), float(recent.at[between2, "Low"])
            neckline = (n1 + n2) / 2
            anchors = [(hp.index[0], left), (between1, n1), (hp.index[1], head), (between2, n2), (hp.index[2], right)]
            details.append(_record("Potential head and shoulders", "REVERSAL", "BEARISH", anchors, frame=recent,
                                   confidence=55 + shoulder_similarity * 25 + min(prominence / 0.15, 1) * 15, trigger=neckline,
                                   lower=[(between1, n1), (between2, n2)], notes="Head above two comparable shoulders; neckline shown.", settings=settings))
    if len(lows) >= 3:
        lp = lows.tail(3); left, head, right = map(float, lp.values)
        shoulder_similarity = _similarity(left, right)
        prominence = min(left, right) / max(head, 1e-9) - 1
        if shoulder_similarity >= 1 - tol * 1.6 and prominence >= max(0.02, tol * 0.7):
            between1 = recent.loc[lp.index[0]:lp.index[1], "High"].idxmax(); between2 = recent.loc[lp.index[1]:lp.index[2], "High"].idxmax()
            n1, n2 = float(recent.at[between1, "High"]), float(recent.at[between2, "High"])
            neckline = (n1 + n2) / 2
            anchors = [(lp.index[0], left), (between1, n1), (lp.index[1], head), (between2, n2), (lp.index[2], right)]
            details.append(_record("Potential inverse head and shoulders", "REVERSAL", "BULLISH", anchors, frame=recent,
                                   confidence=55 + shoulder_similarity * 25 + min(prominence / 0.15, 1) * 15, trigger=neckline,
                                   upper=[(between1, n1), (between2, n2)], notes="Head below two comparable shoulders; neckline shown.", settings=settings))

    # Triangles, wedges, channels, rectangles and broadening formations — gated on a
    # clean trendline fit through the swing points (`_fit_r2`) so noisy, scattered
    # swings are never drawn as a clean geometric formation.
    if len(highs) >= 3 and len(lows) >= 3:
        hp, lp = highs.tail(4), lows.tail(4)
        fit_quality = min(_fit_r2(hp), _fit_r2(lp))
        if fit_quality >= 0.5:
            hs, ls = _slope(hp), _slope(lp)
            avg = float(recent["Close"].mean()); flat = avg * 0.002
            hpts, lpts = [(d, float(v)) for d, v in hp.items()], [(d, float(v)) for d, v in lp.items()]
            narrowing = (float(hp.iloc[-1] - lp.iloc[-1]) < float(hp.iloc[0] - lp.iloc[0]))
            volume_bias = _volume_trend_bias(recent, min(hp.index[0], lp.index[0]), recent.index[-1])
            if abs(hs) <= flat and ls > flat:
                details.append(_record("Potential ascending triangle", "CONTINUATION", "BULLISH", hpts + lpts, frame=recent, confidence=78, trigger=float(hp.mean()), upper=hpts, lower=lpts, settings=settings, volume_bias=volume_bias))
            elif hs < -flat and abs(ls) <= flat:
                details.append(_record("Potential descending triangle", "CONTINUATION", "BEARISH", hpts + lpts, frame=recent, confidence=78, trigger=float(lp.mean()), upper=hpts, lower=lpts, settings=settings, volume_bias=volume_bias))
            elif hs < -flat and ls > flat and narrowing:
                details.append(_record("Potential symmetrical triangle / pennant", "COMPRESSION", "NEUTRAL", hpts + lpts, frame=recent, confidence=74, upper=hpts, lower=lpts, settings=settings, volume_bias=volume_bias))
            elif hs > flat and ls > flat and narrowing:
                details.append(_record("Potential rising wedge", "COMPRESSION", "BEARISH", hpts + lpts, frame=recent, confidence=72, trigger=float(lp.iloc[-1]), upper=hpts, lower=lpts, settings=settings, volume_bias=volume_bias))
            elif hs < -flat and ls < -flat and narrowing:
                details.append(_record("Potential falling wedge", "COMPRESSION", "BULLISH", hpts + lpts, frame=recent, confidence=72, trigger=float(hp.iloc[-1]), upper=hpts, lower=lpts, settings=settings, volume_bias=volume_bias))
            elif hs > flat and ls < -flat:
                details.append(_record("Potential broadening formation", "VOLATILITY", "NEUTRAL", hpts + lpts, frame=recent, confidence=70, upper=hpts, lower=lpts, settings=settings))
            elif abs(hs) <= flat and abs(ls) <= flat:
                details.append(_record("Potential rectangle", "CONSOLIDATION", "NEUTRAL", hpts + lpts, frame=recent, confidence=76, upper=hpts, lower=lpts, settings=settings, volume_bias=volume_bias))
            elif hs > flat and ls > flat and abs(hs - ls) <= max(abs(hs), abs(ls)) * 0.3:
                details.append(_record("Potential ascending channel", "TREND", "BULLISH", hpts + lpts, frame=recent, confidence=68, upper=hpts, lower=lpts, settings=settings))
            elif hs < -flat and ls < -flat and abs(hs - ls) <= max(abs(hs), abs(ls)) * 0.3:
                details.append(_record("Potential descending channel", "TREND", "BEARISH", hpts + lpts, frame=recent, confidence=68, upper=hpts, lower=lpts, settings=settings))

    # Flags.
    if len(recent) >= 45:
        impulse = recent["Close"].iloc[-30] / recent["Close"].iloc[-45] - 1
        consolidation = recent.tail(15)
        consolidation_return = consolidation["Close"].iloc[-1] / consolidation["Close"].iloc[0] - 1
        range_pct = consolidation["High"].max() / consolidation["Low"].min() - 1
        flag_volume_bias = _volume_trend_bias(recent, recent.index[-45], recent.index[-1])
        if impulse > 0.12 and -0.10 < consolidation_return < 0.03 and range_pct < 0.18:
            anchors = [(recent.index[-45], float(recent["Close"].iloc[-45])), (recent.index[-30], float(recent["Close"].iloc[-30]))]
            details.append(_record("Potential bullish flag", "CONTINUATION", "BULLISH", anchors, frame=recent,
                                   confidence=60 + min(impulse / 0.30, 1) * 25, trigger=float(consolidation["High"].max()),
                                   highlight_start=consolidation.index[0], highlight_end=consolidation.index[-1],
                                   settings=settings, volume_bias=flag_volume_bias))
        elif impulse < -0.12 and -0.03 < consolidation_return < 0.10 and range_pct < 0.18:
            anchors = [(recent.index[-45], float(recent["Close"].iloc[-45])), (recent.index[-30], float(recent["Close"].iloc[-30]))]
            details.append(_record("Potential bearish flag", "CONTINUATION", "BEARISH", anchors, frame=recent,
                                   confidence=60 + min(abs(impulse) / 0.30, 1) * 25, trigger=float(consolidation["Low"].min()),
                                   highlight_start=consolidation.index[0], highlight_end=consolidation.index[-1],
                                   settings=settings, volume_bias=flag_volume_bias))

    # Cup and handle.
    if len(recent) >= 100:
        window = recent["Close"].tail(100)
        left, middle, right, handle = window.iloc[:25], window.iloc[25:75], window.iloc[60:90], window.iloc[85:]
        left_high, trough, right_high = float(left.max()), float(middle.min()), float(right.max())
        depth = 1 - trough / left_high if left_high else 0
        recovered = abs(right_high / left_high - 1) <= tol * 1.5
        handle_pullback = 1 - float(handle.min()) / right_high if right_high else 0
        if 0.10 <= depth <= 0.45 and recovered and 0 <= handle_pullback <= 0.12:
            anchors = [(left.idxmax(), left_high), (middle.idxmin(), trough), (right.idxmax(), right_high), (handle.idxmin(), float(handle.min()))]
            details.append(_record("Potential cup and handle", "CONTINUATION", "BULLISH", anchors, frame=recent,
                                   confidence=70 + min(depth / 0.35, 1) * 15, trigger=max(left_high, right_high),
                                   highlight_start=handle.index[0], highlight_end=handle.index[-1],
                                   settings=settings, volume_bias=_volume_trend_bias(recent, handle.index[0], handle.index[-1])))

    # Rounded formations through quadratic curvature.
    if len(recent) >= 80:
        window = recent["Close"].tail(80).astype(float)
        x = np.linspace(-1, 1, len(window)); coef = np.polyfit(x, window.to_numpy(), 2)
        fitted = np.polyval(coef, x); ss_res = float(np.sum((window.to_numpy() - fitted) ** 2)); ss_tot = float(np.sum((window.to_numpy() - window.mean()) ** 2))
        fit = 1 - ss_res / ss_tot if ss_tot else 0
        if fit > 0.55 and abs(coef[0]) > window.mean() * 0.02:
            direction = "BULLISH" if coef[0] > 0 else "BEARISH"
            label = "Potential rounded bottom" if coef[0] > 0 else "Potential rounded top"
            anchors = [(window.index[0], float(window.iloc[0])), (window.idxmin() if coef[0] > 0 else window.idxmax(), float(window.min() if coef[0] > 0 else window.max())), (window.index[-1], float(window.iloc[-1]))]
            details.append(_record(label, "REVERSAL", direction, anchors, frame=recent, confidence=55 + fit * 35, settings=settings))

    # Keep the strongest candidate of each name, suppress overlapping candidates across
    # categories, then surface DEVELOPING setups first (the point is catching what's
    # forming, not re-announcing what has already played out).
    unique: dict[str, dict[str, Any]] = {}
    for item in details:
        if item["name"] not in unique or item["confidence"] > unique[item["name"]]["confidence"]:
            unique[item["name"]] = item
    deduped = _suppress_overlaps(list(unique.values()))
    status_rank = {"DEVELOPING": 0, "CONFIRMED": 1, "RETESTED": 2}
    return sorted(deduped, key=lambda x: (status_rank.get(x["status"], 3), -x["confidence"], x["name"]))


def detect_patterns(frame: pd.DataFrame, settings: TechnicalSettings) -> list[str]:
    return [item["name"] for item in detect_pattern_details(frame, settings)]


@dataclass(frozen=True)
class PatternReliability:
    sample_size: int
    favorable_rate: float | None
    median_forward_return_pct: float | None
    horizon_bars: int
    note: str


def estimate_pattern_reliability(
    frame: pd.DataFrame,
    settings: TechnicalSettings,
    pattern_name: str,
    direction: str,
    horizon_bars: int = 20,
    step: int = 10,
    min_samples: int = 5,
) -> PatternReliability:
    """Honest, per-ticker empirical check: replay detection at earlier points in this
    ticker's own history and report what happened next. Deliberately does not use
    cross-ticker or industry statistics, and reports "insufficient history" rather
    than a number when the sample is too small to mean anything.
    """
    close = frame["Close"].dropna()
    forward_returns: list[float] = []
    min_start = settings.lookback + 10
    last_usable = len(frame) - horizon_bars
    for cut in range(min_start, max(min_start, last_usable), step):
        window = frame.iloc[:cut]
        try:
            candidates = detect_pattern_details(window, settings)
        except Exception:
            continue
        match = next((d for d in candidates if d["name"] == pattern_name and d["status"] != "DEVELOPING"), None)
        if match is None or cut - 1 + horizon_bars >= len(close):
            continue
        entry_price = float(close.iloc[cut - 1])
        exit_price = float(close.iloc[cut - 1 + horizon_bars])
        if entry_price:
            forward_returns.append((exit_price / entry_price - 1.0) * 100.0)

    sample_size = len(forward_returns)
    if sample_size < min_samples:
        return PatternReliability(sample_size, None, None, horizon_bars, "insufficient history on this ticker")

    favorable = [r for r in forward_returns if (r > 0) == (direction == "BULLISH")]
    favorable_rate = len(favorable) / sample_size
    median_return = float(np.median(forward_returns))
    return PatternReliability(sample_size, favorable_rate, median_return, horizon_bars, "")


def analyse_technical(ticker: str, frame: pd.DataFrame, settings: TechnicalSettings) -> TechnicalSnapshot:
    if frame.empty or "Close" not in frame or len(frame.dropna(subset=["Close"])) < 30:
        raise ValueError("Insufficient price history for technical analysis")
    frame = frame.sort_index().copy(); close = frame["Close"].dropna(); last = float(close.iloc[-1])
    supports, resistances = find_support_resistance(frame, settings)
    support, resistance = (supports[0] if supports else None), (resistances[0] if resistances else None)
    rsi_series = calculate_rsi(close, settings.rsi_period)
    rsi_value = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else None
    setups: list[str] = []
    ds = _distance_pct(last, support["center"] if support else None); dr = _distance_pct(last, resistance["center"] if resistance else None)

    if support:
        if support["state"] == "FLIPPED": setups.append("Flipped support confirmed")
        if support["low"] <= last <= support["high"]: setups.append("In support area")
        elif ds is not None and 0 <= ds <= settings.proximity_pct: setups.append("Approaching support")
        if _confirmed_break(close, support["low"], "below", settings.breakout_buffer_pct, settings.breakout_confirmations):
            setups.append("Support breakdown")
            if _breakout_volume_confirms(frame): setups.append("Breakdown confirmed by rising volume")
    if resistance:
        if resistance["state"] == "FLIPPED": setups.append("Flipped resistance confirmed")
        if resistance["low"] <= last <= resistance["high"]: setups.append("In resistance area")
        elif dr is not None and -settings.proximity_pct <= dr <= 0: setups.append("Approaching resistance")
        if _confirmed_break(close, resistance["high"], "above", settings.breakout_buffer_pct, settings.breakout_confirmations):
            setups.append("Resistance breakout")
            if _breakout_volume_confirms(frame): setups.append("Breakout confirmed by rising volume")

    setups.extend(_ma_events(frame, settings.ma_periods))
    if rsi_value is not None:
        if rsi_value >= 70: setups.append(f"RSI overbought ({rsi_value:.1f})")
        elif rsi_value <= 30: setups.append(f"RSI oversold ({rsi_value:.1f})")
    divergence = detect_rsi_divergence(frame, rsi_series, settings.swing_window)
    if divergence: setups.append(divergence)
    pattern_details = detect_pattern_details(frame, settings)
    patterns = [f"{p['name']} [{p['status']}, {p['confidence']}%]" for p in pattern_details]
    setups.extend([p["name"] for p in pattern_details])

    priority = ["Resistance breakout", "Support breakdown", "Flipped support confirmed", "Flipped resistance confirmed", "In support area", "In resistance area", "Approaching support", "Approaching resistance"]
    state = next((item for item in priority if item in setups), "No active level event")
    return TechnicalSnapshot(
        ticker=ticker, last=last, data_date=close.index[-1],
        support_low=support["low"] if support else None, support_high=support["high"] if support else None,
        resistance_low=resistance["low"] if resistance else None, resistance_high=resistance["high"] if resistance else None,
        distance_support_pct=ds, distance_resistance_pct=dr, rsi=rsi_value, state=state,
        setups=tuple(dict.fromkeys(setups)), patterns=tuple(patterns),
        diagnostics={
            "supports": supports[:5],
            "resistances": resistances[:5],
            "pattern_details": pattern_details,
            "atr": calculate_atr(frame, 14).reindex(close.index),
        },
    )


def scan_universe(constituents: pd.DataFrame, data: dict[str, pd.DataFrame], settings: TechnicalSettings) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []; failures: list[dict[str, str]] = []
    meta = constituents.drop_duplicates("Ticker").set_index("Ticker")
    for ticker in constituents["Ticker"].drop_duplicates():
        frame = data.get(ticker)
        if frame is not None and not frame.empty: frame = resample_technical_frame(frame, settings.timeframe)
        if frame is None or frame.empty:
            failures.append({"Ticker": ticker, "Reason": "No price data"}); continue
        try:
            snap = analyse_technical(ticker, frame, settings)
            details = snap.diagnostics.get("pattern_details", [])
            rows.append({
                "Ticker": ticker,
                "Company": str(meta.loc[ticker, "Company"]) if ticker in meta.index else ticker,
                "Sector": str(meta.loc[ticker, "Sector"]) if ticker in meta.index else "Unclassified",
                "Last": snap.last, "Technical State": snap.state, "Setups": " | ".join(snap.setups),
                "Setup Count": len(snap.setups), "Patterns": " | ".join(snap.patterns) if snap.patterns else "—",
                "Best Pattern": details[0]["name"] if details else "—",
                "Pattern Confidence": details[0]["confidence"] if details else np.nan,
                "Pattern Status": details[0]["status"] if details else "—",
                "Support Low": snap.support_low, "Support High": snap.support_high,
                "Distance Support %": snap.distance_support_pct,
                "Resistance Low": snap.resistance_low, "Resistance High": snap.resistance_high,
                "Distance Resistance %": snap.distance_resistance_pct, "RSI": snap.rsi, "Data Date": snap.data_date,
            })
        except Exception as exc:
            failures.append({"Ticker": ticker, "Reason": str(exc)})
    return pd.DataFrame(rows), pd.DataFrame(failures)
