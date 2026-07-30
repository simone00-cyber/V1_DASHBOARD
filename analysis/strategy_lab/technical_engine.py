from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import math
import numpy as np
import pandas as pd


@dataclass
class TechnicalTrade:
    trade_id: int
    side: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    quantity: float
    gross_return: float
    net_return: float
    pnl: float
    bars_held: int
    entry_reason: str
    exit_reason: str
    mfe: float
    mae: float
    initial_stop: float | None = None
    initial_target: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TechnicalBacktestResult:
    frame: pd.DataFrame
    trades: list[TechnicalTrade]
    metrics: dict[str, float]
    specification: dict[str, Any]


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _atr(data: pd.DataFrame, period: int) -> pd.Series:
    previous = data["Close"].shift(1)
    tr = pd.concat([
        data["High"] - data["Low"],
        (data["High"] - previous).abs(),
        (data["Low"] - previous).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def _adx(data: pd.DataFrame, period: int) -> pd.Series:
    up = data["High"].diff()
    down = -data["Low"].diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    atr = _atr(data, period)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def build_indicator(data: pd.DataFrame, name: str, period: int = 14, secondary: int = 26) -> pd.Series:
    name = name.upper()
    close = data["Close"].astype(float)
    if name in data.columns:
        return data[name].astype(float)
    if name == "PRICE" or name == "CLOSE":
        return close
    if name == "SMA":
        return close.rolling(period).mean()
    if name == "EMA":
        return close.ewm(span=period, adjust=False, min_periods=period).mean()
    if name == "RSI":
        return _rsi(close, period)
    if name == "ROC":
        return close.pct_change(period) * 100
    if name == "ATR":
        return _atr(data, period)
    if name == "ADX":
        return _adx(data, period)
    if name == "VOLUME SMA":
        return data["Volume"].astype(float).rolling(period).mean()
    if name == "VOLUME":
        return data["Volume"].astype(float)
    if name == "HIGHEST HIGH":
        return data["High"].astype(float).rolling(period).max().shift(1)
    if name == "LOWEST LOW":
        return data["Low"].astype(float).rolling(period).min().shift(1)
    if name == "MACD":
        fast = close.ewm(span=period, adjust=False, min_periods=period).mean()
        slow = close.ewm(span=secondary, adjust=False, min_periods=secondary).mean()
        return fast - slow
    if name == "MACD SIGNAL":
        fast = close.ewm(span=period, adjust=False, min_periods=period).mean()
        slow = close.ewm(span=secondary, adjust=False, min_periods=secondary).mean()
        return (fast - slow).ewm(span=9, adjust=False, min_periods=9).mean()
    if name == "BOLLINGER UPPER":
        mean = close.rolling(period).mean()
        return mean + secondary * close.rolling(period).std(ddof=0)
    if name == "BOLLINGER LOWER":
        mean = close.rolling(period).mean()
        return mean - secondary * close.rolling(period).std(ddof=0)
    if name == "STOCHASTIC":
        low = data["Low"].rolling(period).min()
        high = data["High"].rolling(period).max()
        return 100 * (close - low) / (high - low).replace(0, np.nan)
    raise ValueError(f"Unsupported indicator: {name}")


def _operand(data: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    if spec.get("kind") == "constant":
        return pd.Series(float(spec.get("value", 0.0)), index=data.index)
    return build_indicator(
        data,
        str(spec.get("name", "Close")),
        int(spec.get("period", 14)),
        int(spec.get("secondary", 26)),
    ) * float(spec.get("multiplier", 1.0))


def evaluate_rule(data: pd.DataFrame, rule: dict[str, Any]) -> pd.Series:
    left = _operand(data, rule["left"])
    right = _operand(data, rule["right"])
    op = rule.get("operator", ">")
    if op == ">":
        out = left > right
    elif op == "<":
        out = left < right
    elif op == ">=":
        out = left >= right
    elif op == "<=":
        out = left <= right
    elif op == "crosses above":
        out = (left > right) & (left.shift(1) <= right.shift(1))
    elif op == "crosses below":
        out = (left < right) & (left.shift(1) >= right.shift(1))
    else:
        raise ValueError(f"Unsupported operator: {op}")
    persistence = max(1, int(rule.get("persistence", 1)))
    if persistence > 1:
        out = out.rolling(persistence).sum().eq(persistence)
    return out.fillna(False)


def combine_rules(data: pd.DataFrame, rules: list[dict[str, Any]], logic: str = "AND") -> pd.Series:
    enabled = [r for r in rules if r.get("enabled", True)]
    if not enabled:
        return pd.Series(False, index=data.index)
    conditions = [evaluate_rule(data, r) for r in enabled]
    result = conditions[0].copy()
    for condition in conditions[1:]:
        result = result & condition if logic.upper() == "AND" else result | condition
    return result.fillna(False)


def _metrics(frame: pd.DataFrame, trades: list[TechnicalTrade], bars_per_year: int) -> dict[str, float]:
    equity = frame["Equity"].dropna()
    returns = frame["StrategyReturn"].dropna()
    if equity.empty:
        return {}
    years = max(len(equity) / bars_per_year, 1 / bars_per_year)
    total = float(equity.iloc[-1] - 1)
    cagr = float(equity.iloc[-1] ** (1 / years) - 1) if equity.iloc[-1] > 0 else -1.0
    vol = float(returns.std(ddof=1) * math.sqrt(bars_per_year)) if len(returns) > 1 else 0.0
    sharpe = float(returns.mean() / returns.std(ddof=1) * math.sqrt(bars_per_year)) if returns.std(ddof=1) > 0 else 0.0
    downside = returns[returns < 0].std(ddof=1)
    sortino = float(returns.mean() / downside * math.sqrt(bars_per_year)) if downside and downside > 0 else 0.0
    dd = equity / equity.cummax() - 1
    max_dd = float(dd.min())
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0
    values = np.array([t.net_return for t in trades], dtype=float)
    wins = values[values > 0]
    losses = values[values < 0]
    pf = float(wins.sum() / abs(losses.sum())) if len(losses) and abs(losses.sum()) > 0 else (float("inf") if len(wins) else 0.0)
    return {
        "Total Return": total, "CAGR": cagr, "Annualized Volatility": vol,
        "Sharpe": sharpe, "Sortino": sortino, "Calmar": calmar,
        "Max Drawdown": max_dd, "Trades": float(len(trades)),
        "Win Rate": float((values > 0).mean()) if len(values) else 0.0,
        "Profit Factor": pf, "Expectancy": float(values.mean()) if len(values) else 0.0,
        "Average Trade": float(values.mean()) if len(values) else 0.0,
        "Average Bars Held": float(np.mean([t.bars_held for t in trades])) if trades else 0.0,
        "Exposure": float(frame["Position"].abs().mean()),
    }


def run_technical_backtest(data: pd.DataFrame, specification: dict[str, Any]) -> TechnicalBacktestResult:
    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(data.columns):
        raise ValueError(f"OHLCV columns required: {sorted(required)}")
    frame = data.sort_index().dropna(subset=["Open", "High", "Low", "Close"]).copy()
    entry_long = combine_rules(frame, specification.get("entry_long", []), specification.get("entry_logic", "AND"))
    exit_long = combine_rules(frame, specification.get("exit_long", []), specification.get("exit_logic", "OR"))
    allow_short = bool(specification.get("allow_short", False))
    entry_short = combine_rules(frame, specification.get("entry_short", []), specification.get("entry_short_logic", "AND")) if allow_short else pd.Series(False, index=frame.index)
    exit_short = combine_rules(frame, specification.get("exit_short", []), specification.get("exit_short_logic", "OR")) if allow_short else pd.Series(False, index=frame.index)

    initial_capital = float(specification.get("initial_capital", 100000.0))
    position_fraction = float(specification.get("position_fraction", 1.0))
    commission_bps = float(specification.get("commission_bps", 0.0))
    slippage_bps = float(specification.get("slippage_bps", 0.0))
    stop_loss = float(specification.get("stop_loss_pct", 0.0)) / 100
    take_profit = float(specification.get("take_profit_pct", 0.0)) / 100
    trailing = float(specification.get("trailing_stop_pct", 0.0)) / 100
    max_bars = int(specification.get("max_bars", 0))
    execution = specification.get("execution", "Next open")
    trade_on_close = execution == "Signal close"

    cash = initial_capital
    qty = 0.0
    side = 0
    entry_price = 0.0
    entry_date = None
    entry_bar = 0
    initial_stop = None
    initial_target = None
    highest = -np.inf
    lowest = np.inf
    trades: list[TechnicalTrade] = []
    equity_values: list[float] = []
    position_values: list[float] = []
    strategy_returns: list[float] = []
    pending_side = 0
    pending_exit = False
    pending_reason = ""
    entry_reason = ""
    previous_equity = initial_capital

    for i, (date, row) in enumerate(frame.iterrows()):
        open_price, high, low, close = map(float, (row.Open, row.High, row.Low, row.Close))
        if pending_exit and side != 0:
            raw_exit = open_price if not trade_on_close else close
            exit_price = raw_exit * (1 - side * slippage_bps / 10000)
            gross = side * (exit_price / entry_price - 1)
            costs = 2 * commission_bps / 10000
            net = gross - costs
            cash += qty * side * (exit_price - entry_price) - abs(qty * entry_price) * costs
            segment = frame.iloc[entry_bar:i + 1]
            mfe = float(((segment.High.max() / entry_price - 1) if side == 1 else (1 - segment.Low.min() / entry_price)))
            mae = float(((segment.Low.min() / entry_price - 1) if side == 1 else (1 - segment.High.max() / entry_price)))
            trades.append(TechnicalTrade(len(trades)+1, "LONG" if side == 1 else "SHORT", entry_date, date, entry_price, exit_price, qty, gross, net, net * abs(qty * entry_price), i-entry_bar, entry_reason, pending_reason, mfe, mae, initial_stop, initial_target))
            qty = 0; side = 0; pending_exit = False
        if pending_side and side == 0:
            raw_entry = open_price if not trade_on_close else close
            side = pending_side
            entry_price = raw_entry * (1 + side * slippage_bps / 10000)
            capital = cash * position_fraction
            qty = capital / entry_price
            cash -= abs(qty * entry_price) * commission_bps / 10000
            entry_date = date; entry_bar = i
            highest = high; lowest = low
            initial_stop = entry_price * (1 - side * stop_loss) if stop_loss else None
            initial_target = entry_price * (1 + side * take_profit) if take_profit else None
            pending_side = 0

        exit_now = False; reason = ""
        if side != 0:
            highest = max(highest, high); lowest = min(lowest, low)
            stop_price = None
            if stop_loss:
                stop_price = entry_price * (1 - side * stop_loss)
            if trailing:
                trail_price = highest * (1 - trailing) if side == 1 else lowest * (1 + trailing)
                stop_price = max(stop_price or -np.inf, trail_price) if side == 1 else min(stop_price or np.inf, trail_price)
            target_price = entry_price * (1 + side * take_profit) if take_profit else None
            if side == 1 and stop_price is not None and low <= stop_price:
                exit_now = True; reason = "STOP / TRAILING"; fill = min(open_price, stop_price)
            elif side == -1 and stop_price is not None and high >= stop_price:
                exit_now = True; reason = "STOP / TRAILING"; fill = max(open_price, stop_price)
            elif side == 1 and target_price is not None and high >= target_price:
                exit_now = True; reason = "TAKE PROFIT"; fill = max(open_price, target_price)
            elif side == -1 and target_price is not None and low <= target_price:
                exit_now = True; reason = "TAKE PROFIT"; fill = min(open_price, target_price)
            elif max_bars and i - entry_bar >= max_bars:
                exit_now = True; reason = "TIME EXIT"; fill = close
            elif side == 1 and bool(exit_long.iloc[i]):
                exit_now = True; reason = "LONG EXIT RULE"; fill = close
            elif side == -1 and bool(exit_short.iloc[i]):
                exit_now = True; reason = "SHORT EXIT RULE"; fill = close
            if exit_now:
                exit_price = float(fill) * (1 - side * slippage_bps / 10000)
                gross = side * (exit_price / entry_price - 1)
                costs = 2 * commission_bps / 10000
                net = gross - costs
                cash += qty * side * (exit_price - entry_price) - abs(qty * entry_price) * commission_bps / 10000
                segment = frame.iloc[entry_bar:i + 1]
                mfe = float(((segment.High.max() / entry_price - 1) if side == 1 else (1 - segment.Low.min() / entry_price)))
                mae = float(((segment.Low.min() / entry_price - 1) if side == 1 else (1 - segment.High.max() / entry_price)))
                trades.append(TechnicalTrade(len(trades)+1, "LONG" if side == 1 else "SHORT", entry_date, date, entry_price, exit_price, qty, gross, net, net * abs(qty * entry_price), i-entry_bar, entry_reason, reason, mfe, mae, initial_stop, initial_target))
                qty = 0; side = 0

        if side == 0 and not exit_now:
            if bool(entry_long.iloc[i]):
                pending_side = 1; entry_reason = " AND/OR ".join([_rule_text(r) for r in specification.get("entry_long", []) if r.get("enabled", True)])
            elif allow_short and bool(entry_short.iloc[i]):
                pending_side = -1; entry_reason = " AND/OR ".join([_rule_text(r) for r in specification.get("entry_short", []) if r.get("enabled", True)])

        mark = cash + (qty * side * (close - entry_price) if side else 0.0)
        equity_values.append(mark / initial_capital)
        position_values.append(side * position_fraction if side else 0.0)
        strategy_returns.append(mark / previous_equity - 1 if previous_equity else 0.0)
        previous_equity = mark

    if side != 0 and specification.get("close_open_trade", True):
        date = frame.index[-1]; close = float(frame.Close.iloc[-1])
        exit_price = close * (1 - side * slippage_bps / 10000)
        gross = side * (exit_price / entry_price - 1); costs = 2 * commission_bps / 10000; net = gross - costs
        segment = frame.iloc[entry_bar:]
        mfe = float(((segment.High.max() / entry_price - 1) if side == 1 else (1 - segment.Low.min() / entry_price)))
        mae = float(((segment.Low.min() / entry_price - 1) if side == 1 else (1 - segment.High.max() / entry_price)))
        trades.append(TechnicalTrade(len(trades)+1, "LONG" if side == 1 else "SHORT", entry_date, date, entry_price, exit_price, qty, gross, net, net * abs(qty * entry_price), len(frame)-1-entry_bar, entry_reason, "END OF TEST", mfe, mae, initial_stop, initial_target))

    frame["EntryLong"] = entry_long; frame["ExitLong"] = exit_long
    frame["EntryShort"] = entry_short; frame["ExitShort"] = exit_short
    frame["Position"] = position_values
    frame["StrategyReturn"] = strategy_returns
    frame["Equity"] = equity_values
    frame["BenchmarkEquity"] = (1 + frame.Close.pct_change().fillna(0)).cumprod()
    frame["Drawdown"] = frame.Equity / frame.Equity.cummax() - 1
    bars_per_year = int(specification.get("bars_per_year", 252))
    return TechnicalBacktestResult(frame, trades, _metrics(frame, trades, bars_per_year), specification)


def _rule_text(rule: dict[str, Any]) -> str:
    def label(operand: dict[str, Any]) -> str:
        if operand.get("kind") == "constant":
            return str(operand.get("value", 0))
        name = operand.get("name", "Close")
        period = operand.get("period")
        multiplier = float(operand.get("multiplier", 1.0))
        base = f"{name}({period})" if name not in {"Close", "Open", "High", "Low", "Volume"} else name
        return f"{multiplier:g} × {base}" if multiplier != 1 else base
    return f"{label(rule['left'])} {rule.get('operator', '>')} {label(rule['right'])}"
