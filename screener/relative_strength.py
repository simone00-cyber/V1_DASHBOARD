from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd


RS_LAB_WINDOWS: dict[str, int] = {
    "1 MONTH": 21,
    "3 MONTHS": 63,
    "6 MONTHS": 126,
    "1 YEAR": 252,
    "3 YEARS": 756,
    "5 YEARS": 1260,
}

HEATMAP_WINDOWS: dict[str, int] = {
    "1W": 5,
    "1M": 21,
    "3M": 63,
    "6M": 126,
    "1Y": 252,
}


@dataclass(frozen=True)
class RelativeStrengthLabResult:
    normalized: pd.DataFrame
    relative_ratio: pd.DataFrame
    statistics: pd.DataFrame
    heatmap: pd.DataFrame
    monthly_leaders: pd.DataFrame


def _close_series(frame: pd.DataFrame) -> pd.Series:
    if frame.empty or "Close" not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame["Close"], errors="coerce").dropna().sort_index()


def _windowed(series: pd.Series, periods: int) -> pd.Series:
    clean = series.dropna().sort_index()
    if clean.empty:
        return clean
    return clean.iloc[-min(len(clean), periods + 1):]


def _normalise(series: pd.Series) -> pd.Series:
    clean = series.dropna()
    if clean.empty or clean.iloc[0] == 0:
        return pd.Series(dtype=float)
    return clean / clean.iloc[0] * 100.0


def _aligned_prices(
    price_frames: Mapping[str, pd.DataFrame],
    benchmark_ticker: str,
    comparison_tickers: list[str],
    periods: int,
) -> pd.DataFrame:
    requested = [benchmark_ticker] + [ticker for ticker in comparison_tickers if ticker != benchmark_ticker]
    series = {}
    for ticker in requested:
        close = _close_series(price_frames.get(ticker, pd.DataFrame()))
        if not close.empty:
            series[ticker] = close.rename(ticker)
    if benchmark_ticker not in series or len(series) < 2:
        return pd.DataFrame()
    aligned = pd.concat(series.values(), axis=1, join="inner").dropna(how="any")
    if aligned.empty:
        return aligned
    return aligned.iloc[-min(len(aligned), periods + 1):]


def build_sector_composites(
    price_frames: Mapping[str, pd.DataFrame],
    constituents: pd.DataFrame,
    sectors: list[str],
    periods: int,
) -> dict[str, pd.Series]:
    composites: dict[str, pd.Series] = {}
    if constituents.empty or not sectors:
        return composites

    for sector in sectors:
        members = constituents.loc[
            constituents["Sector"].astype(str) == str(sector), "Ticker"
        ].dropna().astype(str).tolist()
        normalized_members: list[pd.Series] = []
        for ticker in members:
            close = _windowed(_close_series(price_frames.get(ticker, pd.DataFrame())), periods)
            normalized = _normalise(close)
            if not normalized.empty:
                normalized_members.append(normalized.rename(ticker))
        if not normalized_members:
            continue
        panel = pd.concat(normalized_members, axis=1).ffill().dropna(how="all")
        if panel.empty:
            continue
        composites[f"SECTOR: {sector}"] = panel.mean(axis=1).rename(f"SECTOR: {sector}")
    return composites


def _annualised_volatility(returns: pd.Series) -> float:
    clean = returns.dropna()
    if len(clean) < 2:
        return np.nan
    return float(clean.std(ddof=1) * np.sqrt(252.0) * 100.0)


def _safe_correlation(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left, right], axis=1).dropna()
    if len(aligned) < 3:
        return np.nan
    return float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))


def _safe_beta(stock_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    aligned = pd.concat([stock_returns, benchmark_returns], axis=1).dropna()
    if len(aligned) < 3:
        return np.nan
    variance = aligned.iloc[:, 1].var(ddof=1)
    if not np.isfinite(variance) or variance == 0:
        return np.nan
    return float(aligned.iloc[:, 0].cov(aligned.iloc[:, 1]) / variance)


def _period_return(series: pd.Series, periods: int | None = None) -> float:
    clean = series.dropna()
    if periods is not None:
        clean = clean.iloc[-min(len(clean), periods + 1):]
    if len(clean) < 2 or clean.iloc[0] == 0:
        return np.nan
    return float((clean.iloc[-1] / clean.iloc[0] - 1.0) * 100.0)


def build_statistics(aligned: pd.DataFrame, benchmark_ticker: str) -> pd.DataFrame:
    if aligned.empty or benchmark_ticker not in aligned.columns:
        return pd.DataFrame()
    benchmark = aligned[benchmark_ticker]
    benchmark_returns = benchmark.pct_change()
    benchmark_total = _period_return(benchmark)
    rows: list[dict[str, float | str]] = []
    for ticker in aligned.columns:
        if ticker == benchmark_ticker:
            continue
        stock = aligned[ticker]
        stock_returns = stock.pct_change()
        excess_daily = stock_returns - benchmark_returns
        tracking_error = _annualised_volatility(excess_daily)
        excess = _period_return(stock) - benchmark_total
        info_ratio = np.nan
        if np.isfinite(tracking_error) and tracking_error != 0:
            info_ratio = float(excess / tracking_error)
        rows.append(
            {
                "Ticker": ticker,
                "Return %": _period_return(stock),
                "Benchmark %": benchmark_total,
                "Excess Return pp": excess,
                "Volatility %": _annualised_volatility(stock_returns),
                "Correlation": _safe_correlation(stock_returns, benchmark_returns),
                "Beta": _safe_beta(stock_returns, benchmark_returns),
                "Tracking Error %": tracking_error,
                "Information Ratio": info_ratio,
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("Excess Return pp", ascending=False).reset_index(drop=True)


def build_heatmap(
    price_frames: Mapping[str, pd.DataFrame],
    benchmark_ticker: str,
    comparison_tickers: list[str],
) -> pd.DataFrame:
    benchmark = _close_series(price_frames.get(benchmark_ticker, pd.DataFrame()))
    if benchmark.empty:
        return pd.DataFrame()
    rows: list[dict[str, float | str]] = []
    for ticker in comparison_tickers:
        stock = _close_series(price_frames.get(ticker, pd.DataFrame()))
        if stock.empty:
            continue
        record: dict[str, float | str] = {"Ticker": ticker}
        for label, periods in HEATMAP_WINDOWS.items():
            aligned = pd.concat([stock.rename("stock"), benchmark.rename("benchmark")], axis=1).dropna()
            if len(aligned) <= periods:
                record[label] = np.nan
                continue
            stock_return = aligned["stock"].iloc[-1] / aligned["stock"].iloc[-periods - 1] - 1.0
            benchmark_return = aligned["benchmark"].iloc[-1] / aligned["benchmark"].iloc[-periods - 1] - 1.0
            record[label] = float((stock_return - benchmark_return) * 100.0)
        rows.append(record)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("Ticker")


def build_monthly_leaders(aligned: pd.DataFrame, benchmark_ticker: str, months: int = 12) -> pd.DataFrame:
    if aligned.empty or benchmark_ticker not in aligned.columns or len(aligned.columns) < 2:
        return pd.DataFrame()
    monthly = aligned.resample("ME").last().pct_change() * 100.0
    if monthly.empty:
        return pd.DataFrame()
    relative = monthly.drop(columns=[benchmark_ticker]).sub(monthly[benchmark_ticker], axis=0)
    relative = relative.dropna(how="all").tail(months)
    rows: list[dict[str, float | str]] = []
    for date, values in relative.iterrows():
        clean = values.dropna()
        if clean.empty:
            continue
        leader = clean.idxmax()
        laggard = clean.idxmin()
        rows.append(
            {
                "Month": pd.Timestamp(date).strftime("%b %Y"),
                "Leader": str(leader),
                "Leader Excess pp": float(clean.loc[leader]),
                "Laggard": str(laggard),
                "Laggard Excess pp": float(clean.loc[laggard]),
            }
        )
    return pd.DataFrame(rows)


def build_relative_strength_lab(
    price_frames: Mapping[str, pd.DataFrame],
    benchmark_ticker: str,
    comparison_tickers: list[str],
    periods: int,
    sector_composites: Mapping[str, pd.Series] | None = None,
) -> RelativeStrengthLabResult:
    aligned = _aligned_prices(price_frames, benchmark_ticker, comparison_tickers, periods)
    if aligned.empty:
        return RelativeStrengthLabResult(
            normalized=pd.DataFrame(),
            relative_ratio=pd.DataFrame(),
            statistics=pd.DataFrame(),
            heatmap=pd.DataFrame(),
            monthly_leaders=pd.DataFrame(),
        )

    normalized = aligned.apply(_normalise)
    benchmark = aligned[benchmark_ticker]
    ratios: dict[str, pd.Series] = {}
    for ticker in comparison_tickers:
        if ticker not in aligned.columns:
            continue
        ratio = aligned[ticker] / benchmark
        ratios[ticker] = _normalise(ratio).rename(ticker)
    relative_ratio = pd.concat(ratios.values(), axis=1) if ratios else pd.DataFrame(index=aligned.index)

    if sector_composites:
        for name, series in sector_composites.items():
            clean = series.reindex(normalized.index).ffill().dropna()
            if clean.empty:
                continue
            normalized[name] = clean.reindex(normalized.index).ffill()
            benchmark_normalized = normalized[benchmark_ticker].reindex(clean.index).ffill()
            sector_ratio = clean / benchmark_normalized
            relative_ratio[name] = _normalise(sector_ratio).reindex(relative_ratio.index).ffill()

    return RelativeStrengthLabResult(
        normalized=normalized,
        relative_ratio=relative_ratio,
        statistics=build_statistics(aligned, benchmark_ticker),
        heatmap=build_heatmap(price_frames, benchmark_ticker, comparison_tickers),
        monthly_leaders=build_monthly_leaders(aligned, benchmark_ticker),
    )
