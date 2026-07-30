from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from caruso_analysis import (
    calculate_composite_momentum,
    resample_ohlc,
    strategy_from_matrix,
    summarize_timeframe,
)


@dataclass(frozen=True)
class ScreenerResult:
    rows: pd.DataFrame
    failures: pd.DataFrame


PERFORMANCE_WINDOWS: dict[str, tuple[str, int]] = {
    "1 DAY": ("1D %", 1),
    "1 WEEK": ("1W %", 5),
    "1 MONTH": ("1M %", 21),
    "1 YEAR": ("1Y %", 252),
}


RELATIVE_STRENGTH_WINDOWS: dict[str, tuple[str, int]] = {
    "1 WEEK": ("RS 1W %", 5),
    "1 MONTH": ("RS 1M %", 21),
    "3 MONTHS": ("RS 3M %", 63),
    "6 MONTHS": ("RS 6M %", 126),
    "1 YEAR": ("RS 1Y %", 252),
}

ACTION_ORDER: dict[str, int] = {
    "BUY": 0,
    "TAKE PROFIT": 1,
    "NESSUNA NUOVA GIUNTURA": 2,
    "SELL SHORT": 3,
}


def _extract_ticker_frame(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        level0 = raw.columns.get_level_values(0)
        level1 = raw.columns.get_level_values(1)
        if ticker in level1:
            frame = raw.xs(ticker, axis=1, level=1).copy()
        elif ticker in level0:
            frame = raw.xs(ticker, axis=1, level=0).copy()
        else:
            return pd.DataFrame()
    else:
        frame = raw.copy()

    required = ["Open", "High", "Low", "Close"]
    if not set(required).issubset(frame.columns):
        return pd.DataFrame()

    optional = [column for column in ["Volume"] if column in frame.columns]
    return frame[required + optional].dropna(subset=required).sort_index()


def download_universe_ohlc(
    tickers: list[str],
    period: str = "max",
    chunk_size: int = 60,
) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    output: dict[str, pd.DataFrame] = {}
    clean = list(dict.fromkeys(ticker for ticker in tickers if ticker))

    for start in range(0, len(clean), chunk_size):
        chunk = clean[start : start + chunk_size]
        try:
            raw = yf.download(
                chunk,
                period=period,
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="column",
                threads=True,
                timeout=25,
            )
        except Exception:
            continue

        for ticker in chunk:
            frame = _extract_ticker_frame(raw, ticker)
            if not frame.empty:
                output[ticker] = frame

    return output


def _return(series: pd.Series, periods: int) -> float:
    clean = series.dropna()
    if len(clean) <= periods:
        return np.nan
    return float((clean.iloc[-1] / clean.iloc[-periods - 1] - 1.0) * 100.0)


def _relative_return(stock: pd.Series, benchmark: pd.Series, periods: int) -> float:
    aligned = pd.concat([stock.rename("stock"), benchmark.rename("benchmark")], axis=1).dropna()
    if len(aligned) <= periods:
        return np.nan
    stock_return = aligned["stock"].iloc[-1] / aligned["stock"].iloc[-periods - 1] - 1.0
    benchmark_return = aligned["benchmark"].iloc[-1] / aligned["benchmark"].iloc[-periods - 1] - 1.0
    return float((stock_return - benchmark_return) * 100.0)


def _relative_ratio_index(stock: pd.Series, benchmark: pd.Series, periods: int = 252) -> float:
    aligned = pd.concat([stock.rename("stock"), benchmark.rename("benchmark")], axis=1).dropna()
    if len(aligned) <= periods:
        return np.nan
    window = aligned.iloc[-(periods + 1):]
    ratio = window["stock"] / window["benchmark"]
    base = ratio.iloc[0]
    if not np.isfinite(base) or base == 0:
        return np.nan
    return float(ratio.iloc[-1] / base * 100.0)


def build_relative_strength_ranking(rows: pd.DataFrame, relative_column: str) -> pd.DataFrame:
    """Rank securities by excess adjusted-price return versus the selected index benchmark."""
    if rows.empty or relative_column not in rows.columns:
        return pd.DataFrame()
    clean = rows.dropna(subset=[relative_column]).copy()
    if clean.empty:
        return pd.DataFrame()
    clean = clean.sort_values(relative_column, ascending=False, kind="stable").reset_index(drop=True)
    clean.insert(0, "RS Rank", range(1, len(clean) + 1))
    clean["RS Signal"] = np.where(clean[relative_column] > 0, "OUTPERFORM", np.where(clean[relative_column] < 0, "UNDERPERFORM", "IN LINE"))
    return clean


def _screening_status(action: str) -> str:
    mapping = {
        "BUY": "BUY",
        "SELL SHORT": "SELL SHORT",
        "TAKE PROFIT": "TAKE PROFIT",
        "NESSUNA NUOVA GIUNTURA": "NO NEW JUNCTION",
    }
    return mapping.get(action, action)


def _matrix_sort_columns(rows: pd.DataFrame) -> pd.DataFrame:
    result = rows.copy()
    result["_Action Order"] = result["Matrix Action"].map(ACTION_ORDER).fillna(99)
    result["_Quarterly Order"] = result["Quarterly Trend"].map({"UP": 0, "DOWN": 1}).fillna(2)
    result["_Monthly Order"] = result["Monthly Trend"].map({"UP": 0, "DOWN": 1}).fillna(2)
    return result


def sort_by_methodology(rows: pd.DataFrame) -> pd.DataFrame:
    """Sort without a synthetic score.

    The hierarchy follows the public matrix output first, then its published
    Reward/Risk rating, followed by quarterly/monthly direction and the
    current Composite readings only as transparent tie-breakers.
    """
    if rows.empty:
        return rows.copy()

    base = rows.drop(columns=["Order"], errors="ignore")
    ranked = _matrix_sort_columns(base)
    ranked = ranked.sort_values(
        [
            "_Action Order",
            "Rating",
            "_Quarterly Order",
            "_Monthly Order",
            "Quarterly CM",
            "Monthly CM",
            "Weekly CM",
        ],
        ascending=[True, False, True, True, False, False, False],
        kind="stable",
    ).drop(columns=["_Action Order", "_Quarterly Order", "_Monthly Order"])
    ranked.insert(0, "Order", range(1, len(ranked) + 1))
    return ranked.reset_index(drop=True)


def analyse_universe(
    constituents: pd.DataFrame,
    period: str = "max",
    benchmark_ticker: str = "",
) -> ScreenerResult:
    requested_tickers = constituents["Ticker"].tolist()
    if benchmark_ticker:
        requested_tickers = requested_tickers + [benchmark_ticker]
    data = download_universe_ohlc(requested_tickers, period=period)
    benchmark_frame = data.get(benchmark_ticker) if benchmark_ticker else None
    benchmark_close = (
        benchmark_frame["Close"].dropna()
        if benchmark_frame is not None and not benchmark_frame.empty
        else pd.Series(dtype=float)
    )
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    meta = constituents.set_index("Ticker")
    for ticker in constituents["Ticker"]:
        frame = data.get(ticker)
        if frame is None or len(frame) < 260:
            failures.append({"Ticker": ticker, "Reason": "Insufficient price history"})
            continue

        try:
            summaries = {}
            for timeframe, rule in (("WEEKLY", "W-FRI"), ("MONTHLY", "ME"), ("QUARTERLY", "QE")):
                calculated = calculate_composite_momentum(resample_ohlc(frame, rule))
                summaries[timeframe] = summarize_timeframe(timeframe, calculated)
            q = summaries["QUARTERLY"]
            m = summaries["MONTHLY"]
            w = summaries["WEEKLY"]
            action, rating, note = strategy_from_matrix(q.direction, m.direction, w.turn)

            company = str(meta.loc[ticker, "Company"])
            sector = str(meta.loc[ticker, "Sector"])
            close = frame["Close"].dropna()

            rows.append(
                {
                    "Ticker": ticker,
                    "Company": company,
                    "Sector": sector,
                    "Last": float(close.iloc[-1]),
                    "1D %": _return(close, 1),
                    "1W %": _return(close, 5),
                    "1M %": _return(close, 21),
                    "1Y %": _return(close, 252),
                    "RS 1W %": _relative_return(close, benchmark_close, 5),
                    "RS 1M %": _relative_return(close, benchmark_close, 21),
                    "RS 3M %": _relative_return(close, benchmark_close, 63),
                    "RS 6M %": _relative_return(close, benchmark_close, 126),
                    "RS 1Y %": _relative_return(close, benchmark_close, 252),
                    "RS Ratio 1Y": _relative_ratio_index(close, benchmark_close, 252),
                    "Benchmark": benchmark_ticker or "N/A",
                    "Quarterly CM": q.composite,
                    "Monthly CM": m.composite,
                    "Weekly CM": w.composite,
                    "Quarterly Trend": q.direction,
                    "Monthly Trend": m.direction,
                    "Weekly Turn": w.turn,
                    "Matrix Action": action,
                    "Rating": rating,
                    "Rating Visual": "●" * rating if rating else "—",
                    "Screening Status": _screening_status(action),
                    "Methodology Note": note,
                    "Data Date": w.date,
                }
            )
        except Exception as exc:
            failures.append({"Ticker": ticker, "Reason": str(exc)})

    result = pd.DataFrame(rows)
    if result.empty:
        return ScreenerResult(result, pd.DataFrame(failures))

    result = sort_by_methodology(result)
    return ScreenerResult(result, pd.DataFrame(failures))


def build_sector_performance(rows: pd.DataFrame, performance_column: str) -> pd.DataFrame:
    """Equal-weight sector ranking based only on adjusted price performance."""
    if rows.empty or performance_column not in rows.columns:
        return pd.DataFrame()

    clean = rows.dropna(subset=[performance_column]).copy()
    if clean.empty:
        return pd.DataFrame()

    grouped = (
        clean.groupby("Sector", dropna=False)
        .agg(
            Stocks=("Ticker", "count"),
            Performance=(performance_column, "mean"),
            Median=(performance_column, "median"),
            Best=(performance_column, "max"),
            Worst=(performance_column, "min"),
        )
        .reset_index()
    )
    grouped["Performance"] = grouped["Performance"].round(2)
    grouped["Median"] = grouped["Median"].round(2)
    grouped["Best"] = grouped["Best"].round(2)
    grouped["Worst"] = grouped["Worst"].round(2)
    grouped = grouped.sort_values("Performance", ascending=False, kind="stable").reset_index(drop=True)
    grouped.insert(0, "Rank", range(1, len(grouped) + 1))
    return grouped


def build_sector_ranking(rows: pd.DataFrame, performance_column: str = "1M %") -> pd.DataFrame:
    """Backward-compatible alias for the price-performance sector ranking."""
    return build_sector_performance(rows, performance_column)
