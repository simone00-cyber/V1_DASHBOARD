"""
caruso_analysis.py

Analisi multi-timeframe basata esclusivamente sulle regole pubblicate nei
documenti forniti dall'utente sulla metodologia ciclica di Francesco Caruso.

Cosa replica:
- KEY
- XTL
- Composite Momentum
- lettura dei livelli 0, +/-50, +/-80
- direzione del Composite Momentum su annuale, trimestrale, mensile e settimanale
- "giunture" settimanali come flesso della pendenza
- matrice operativa a 12 casi pubblicata nella metodologia

Cosa NON replica:
- Investitore Disciplinato (ID), perché nei paper forniti sono descritte
  caratteristiche e modalità d'uso, ma non è pubblicata la formula completa.
- Fear/Complacency Index, perché non è disponibile una formula completa
  implementabile nei materiali forniti.
- giudizi discrezionali o dati macro non formalizzati nei paper.

Uso:
    pip install yfinance pandas numpy matplotlib
    python caruso_analysis.py ENI.MI
    python caruso_analysis.py AAPL --period 15y --plot
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Strutture dati
# ---------------------------------------------------------------------------

@dataclass
class TimeframeResult:
    timeframe: str
    date: pd.Timestamp
    close: float
    composite: float
    previous_composite: float
    direction: str
    position: str
    excess: str
    turn: str


# ---------------------------------------------------------------------------
# Medie mobili usate nelle formule pubblicate
# ---------------------------------------------------------------------------

def weighted_moving_average(series: pd.Series, period: int) -> pd.Series:
    """
    Media mobile ponderata lineare.

    Il dato più recente riceve peso 'period', il più vecchio peso 1.
    È la traduzione naturale di WeightedAverage[n] / Mov(..., n, W).
    """
    if period <= 0:
        raise ValueError("Il periodo della WMA deve essere positivo.")

    weights = np.arange(1, period + 1, dtype=float)
    denominator = weights.sum()

    return series.rolling(period).apply(
        lambda values: np.dot(values, weights) / denominator,
        raw=True,
    )


def exponential_moving_average(series: pd.Series, period: int) -> pd.Series:
    """
    EMA standard con alpha = 2 / (period + 1).

    adjust=False rende il calcolo ricorsivo, coerente con l'uso operativo
    normalmente associato a ExponentialAverage / Mov(..., E).
    """
    if period <= 0:
        raise ValueError("Il periodo della EMA deve essere positivo.")

    return series.ewm(span=period, adjust=False, min_periods=period).mean()


# ---------------------------------------------------------------------------
# KEY, XTL e Composite Momentum
# ---------------------------------------------------------------------------

def calculate_key(close: pd.Series) -> pd.Series:
    """
    Traduzione della formula KEY pubblicata nei paper.

    Formula di base:
        k = 4
        MOM = (WMA4(close) - WMA12(close)) / WMA4(close) * 100

    Le variazioni positive e negative del MOM vengono normalizzate sulla
    somma assoluta delle variazioni degli ultimi 5 periodi; il risultato
    finale è smussato con EMA a 3 periodi.
    """
    k = 4

    media_1 = weighted_moving_average(close, k)
    media_2 = weighted_moving_average(close, k * 3)

    mom = (media_1 - media_2) / media_1 * 100.0
    diff_mom = mom.diff()

    temp_1 = diff_mom.where(diff_mom > 0.0, 0.0)
    temp_2 = diff_mom.where(diff_mom < 0.0, 0.0)

    sum_temp_1 = temp_1.rolling(5).sum()
    sum_temp_2 = temp_2.rolling(5).sum()
    abs_sum_diff = diff_mom.abs().rolling(5).sum()

    # La formula pubblicata aggiorna ricorsivamente la somma precedente:
    # old_sum - old_sum/5 + current_value.
    numerator_up = sum_temp_1.shift(1) - sum_temp_1.shift(1) / 5.0 + temp_1
    numerator_down = sum_temp_2.shift(1) - sum_temp_2.shift(1) / 5.0 + temp_2
    denominator = (
        abs_sum_diff.shift(1)
        - abs_sum_diff.shift(1) / 5.0
        + diff_mom.abs()
    )

    denominator = denominator.replace(0.0, np.nan)

    aa = numerator_up / denominator * 100.0
    bb = numerator_down / denominator * 100.0
    cc = aa - bb.abs()

    return exponential_moving_average(cc, 3).rename("KEY")


def stochastic_5_3(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> pd.Series:
    """
    Stocastico 5,3 usato per XTL.

    I paper indicano Stochastic[5,3](close) / Stoch(5,3), ma non dettagliano
    internamente la convenzione della piattaforma. Qui viene usata la
    convenzione standard:
        raw %K = 100 * (Close - LowestLow5) / (HighestHigh5 - LowestLow5)
        Stochastic(5,3) = SMA3(raw %K)

    Il valore resta in scala 0..100 prima della trasformazione XTL.
    """
    highest_high = high.rolling(5).max()
    lowest_low = low.rolling(5).min()
    price_range = (highest_high - lowest_low).replace(0.0, np.nan)

    raw_k = (close - lowest_low) / price_range * 100.0
    return raw_k.rolling(3).mean()


def calculate_xtl(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> pd.Series:
    """
    Formula pubblicata:
        stoco = Stochastic[5,3](close)
        XTL = WeightedAverage[3](stoco) * 2 - 100
    """
    stoco = stochastic_5_3(high, low, close)
    xtl = weighted_moving_average(stoco, 3) * 2.0 - 100.0
    return xtl.rename("XTL")


def calculate_composite_momentum(data: pd.DataFrame) -> pd.DataFrame:
    """
    Calcola KEY, XTL e Composite Momentum.

    Formula pubblicata:
        Composite = WMA2((2 * KEY + XTL) / 3)
    """
    required = {"High", "Low", "Close"}
    missing = required.difference(data.columns)

    if missing:
        raise ValueError(f"Colonne mancanti: {sorted(missing)}")

    result = data.copy()
    result["KEY"] = calculate_key(result["Close"])
    result["XTL"] = calculate_xtl(
        result["High"],
        result["Low"],
        result["Close"],
    )
    result["Composite"] = weighted_moving_average(
        (2.0 * result["KEY"] + result["XTL"]) / 3.0,
        2,
    )

    return result


# ---------------------------------------------------------------------------
# Costruzione dei timeframe
# ---------------------------------------------------------------------------

RESAMPLE_RULES = {
    "WEEKLY": "W-FRI",
    "MONTHLY": "ME",
    "QUARTERLY": "QE",
    "YEARLY": "YE",
}


def prepare_technical_prices(daily_data: pd.DataFrame) -> pd.DataFrame:
    """Build a dividend/split-adjusted OHLC series for the signal engine.

    The raw traded prices are retained in ``MarketOpen/High/Low/Close`` for
    charts and displayed execution levels. Technical OHLC values are adjusted
    with the same factor used by Yahoo Finance for ``Adj Close``. This avoids
    interpreting an ex-dividend gap as a genuine bearish price move.

    This is an explicit framework convention; the public source documents do
    not specify whether adjusted or unadjusted prices were used.
    """
    required = {"Open", "High", "Low", "Close"}
    missing = required.difference(daily_data.columns)
    if missing:
        raise ValueError(f"Colonne mancanti: {sorted(missing)}")

    result = daily_data.copy()
    for column in ("Open", "High", "Low", "Close"):
        result[f"Market{column}"] = result[column]

    adjusted_close = (
        result["Adj Close"]
        if "Adj Close" in result.columns
        else result.get("TotalReturnClose", result["Close"])
    )
    factor = (adjusted_close / result["Close"]).replace([np.inf, -np.inf], np.nan)
    factor = factor.where(factor > 0).ffill().bfill().fillna(1.0)

    for column in ("Open", "High", "Low", "Close"):
        result[column] = result[f"Market{column}"] * factor

    result["TotalReturnClose"] = adjusted_close
    result["AdjustmentFactor"] = factor
    return result


def resample_ohlc(
    daily_data: pd.DataFrame,
    rule: str,
    completed_periods_only: bool = True,
) -> pd.DataFrame:
    """
    Converte i dati giornalieri in OHLC settimanali, mensili, trimestrali
    o annuali.

    Per evitare segnali costruiti su periodi ancora aperti, per default
    elimina l'ultima barra se il periodo non è completato.
    """
    aggregation = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
    }
    # Volume is not required by KEY, XTL or Composite Momentum. Some Yahoo
    # Finance batch responses omit it for individual tickers, so aggregate it
    # only when it is actually available instead of failing the whole symbol.
    if "Volume" in daily_data.columns:
        aggregation["Volume"] = "sum"
    if "Adj Close" in daily_data.columns:
        aggregation["Adj Close"] = "last"
    if "TotalReturnClose" in daily_data.columns:
        aggregation["TotalReturnClose"] = "last"
    for column, method in {
        "MarketOpen": "first",
        "MarketHigh": "max",
        "MarketLow": "min",
        "MarketClose": "last",
        "AdjustmentFactor": "last",
    }.items():
        if column in daily_data.columns:
            aggregation[column] = method

    aggregated = daily_data.resample(rule).agg(aggregation)

    aggregated = aggregated.dropna(subset=["Open", "High", "Low", "Close"])

    if completed_periods_only and len(aggregated) > 0:
        now = pd.Timestamp.now(tz=aggregated.index.tz)

        last_label = aggregated.index[-1]
        period_complete = last_label.normalize() <= now.normalize()

        if not period_complete:
            aggregated = aggregated.iloc[:-1]

    return aggregated


# ---------------------------------------------------------------------------
# Interpretazione del Composite Momentum
# ---------------------------------------------------------------------------

def classify_position(value: float) -> str:
    if value >= 80:
        return "ESTREMO POSITIVO (> +80)"
    if value >= 50:
        return "ECCESSO POSITIVO (+50 / +80)"
    if value > 0:
        return "POSITIVO (0 / +50)"
    if value == 0:
        return "LINEA ZERO"
    if value > -50:
        return "NEGATIVO (-50 / 0)"
    if value > -80:
        return "ECCESSO NEGATIVO (-80 / -50)"
    return "ESTREMO NEGATIVO (< -80)"


def classify_excess(value: float) -> str:
    if value >= 80:
        return "RARO ECCESSO POSITIVO"
    if value >= 50:
        return "IPERCOMPRATO / ECCESSO POSITIVO"
    if value <= -80:
        return "RARO ECCESSO NEGATIVO"
    if value <= -50:
        return "IPERVENDUTO / ECCESSO NEGATIVO"
    return "NESSUN ECCESSO"


def slope_direction(current: float, previous: float) -> str:
    if current > previous:
        return "UP"
    if current < previous:
        return "DOWN"
    return "FLAT"


def latest_turn(composite: pd.Series) -> str:
    """
    Individua il flesso più recente della pendenza del CM.

    SVOLTA UP:
        pendenza precedente <= 0 e pendenza attuale > 0

    SVOLTA DOWN:
        pendenza precedente >= 0 e pendenza attuale < 0
    """
    clean = composite.dropna()

    if len(clean) < 3:
        return "NON DETERMINABILE"

    previous_slope = clean.iloc[-2] - clean.iloc[-3]
    current_slope = clean.iloc[-1] - clean.iloc[-2]

    if previous_slope <= 0 and current_slope > 0:
        return "SVOLTA UP"
    if previous_slope >= 0 and current_slope < 0:
        return "SVOLTA DOWN"
    if current_slope > 0:
        return "PROSEGUE UP"
    if current_slope < 0:
        return "PROSEGUE DOWN"
    return "FLAT"


def summarize_timeframe(
    timeframe: str,
    calculated: pd.DataFrame,
) -> TimeframeResult:
    clean = calculated.dropna(subset=["Composite"])

    if len(clean) < 3:
        raise ValueError(
            f"Dati insufficienti per il timeframe {timeframe}. "
            "Scaricare una serie storica più lunga."
        )

    latest = clean.iloc[-1]
    previous = clean.iloc[-2]

    current_cm = float(latest["Composite"])
    previous_cm = float(previous["Composite"])

    return TimeframeResult(
        timeframe=timeframe,
        date=clean.index[-1],
        close=float(latest["Close"]),
        composite=current_cm,
        previous_composite=previous_cm,
        direction=slope_direction(current_cm, previous_cm),
        position=classify_position(current_cm),
        excess=classify_excess(current_cm),
        turn=latest_turn(clean["Composite"]),
    )


# ---------------------------------------------------------------------------
# Matrice operativa pubblicata nei paper
# ---------------------------------------------------------------------------

STRATEGY_MATRIX: Dict[Tuple[str, str, str], Tuple[str, int]] = {
    ("UP", "UP", "SVOLTA UP"): ("BUY", 4),
    ("UP", "DOWN", "SVOLTA UP"): ("BUY", 2),
    ("UP", "DOWN", "SVOLTA DOWN"): ("SELL SHORT", 2),
    ("UP", "UP", "SVOLTA DOWN"): ("SELL SHORT", 1),
    ("UP", "DOWN", "PROSEGUE DOWN"): ("TAKE PROFIT", 3),
    ("UP", "UP", "PROSEGUE DOWN"): ("TAKE PROFIT", 2),
    ("DOWN", "UP", "SVOLTA UP"): ("BUY", 3),
    ("DOWN", "DOWN", "SVOLTA UP"): ("BUY", 1),
    ("DOWN", "DOWN", "SVOLTA DOWN"): ("SELL SHORT", 4),
    ("DOWN", "UP", "SVOLTA DOWN"): ("SELL SHORT", 2),
    ("DOWN", "DOWN", "PROSEGUE DOWN"): ("TAKE PROFIT", 4),
    ("DOWN", "UP", "PROSEGUE DOWN"): ("TAKE PROFIT", 3),
}


def strategy_from_matrix(
    quarterly_direction: str,
    monthly_direction: str,
    weekly_turn: str,
) -> Tuple[str, int, str]:
    """
    Applica la tabella dei 12 casi.

    La tabella originale distingue una giuntura settimanale UP/DOWN.
    Quando non c'è una nuova svolta nell'ultima barra, il programma non
    inventa un nuovo segnale: restituisce una lettura di mantenimento.
    """
    key = (quarterly_direction, monthly_direction, weekly_turn)

    if key in STRATEGY_MATRIX:
        action, rating = STRATEGY_MATRIX[key]
        return action, rating, "SEGNALE PRESENTE NELL'ULTIMA BARRA SETTIMANALE"

    return (
        "NESSUNA NUOVA GIUNTURA",
        0,
        "Il CM settimanale non ha invertito pendenza nell'ultima barra.",
    )


# ---------------------------------------------------------------------------
# Download e analisi completa
# ---------------------------------------------------------------------------

def download_prices(ticker: str, period: str) -> pd.DataFrame:
    """
    Scarica dati OHLC con yfinance.

    yfinance è usato solo come sorgente dati. La tecnica di analisi resta
    esclusivamente quella formalizzata nei paper.
    """
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError(
            "yfinance non è installato. Esegui: pip install yfinance"
        ) from exc

    data = yf.download(
        ticker,
        period=period,
        interval="1d",
        auto_adjust=False,
        progress=False,
        group_by="column",
    )

    if data.empty:
        raise ValueError(
            f"Nessun dato trovato per '{ticker}'. "
            "Controlla il simbolo usato da Yahoo Finance."
        )

    # yfinance può restituire colonne MultiIndex anche per un solo ticker.
    if isinstance(data.columns, pd.MultiIndex):
        if ticker in data.columns.get_level_values(-1):
            data = data.xs(ticker, axis=1, level=-1)
        else:
            data.columns = data.columns.get_level_values(0)

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [column for column in required if column not in data.columns]

    if missing:
        raise ValueError(f"Dati scaricati senza colonne richieste: {missing}")

    columns = required + (["Adj Close"] if "Adj Close" in data.columns else [])
    result = data[columns].dropna(subset=["Open", "High", "Low", "Close"]).copy()
    # TotalReturnClose is the dividend- and split-adjusted economic series.
    # ``prepare_technical_prices`` uses it to construct adjusted OHLC values for
    # the signal engine while preserving raw traded prices for display.
    result["TotalReturnClose"] = (
        result["Adj Close"] if "Adj Close" in result.columns else result["Close"]
    )
    return result


def analyze_ticker(
    ticker: str,
    period: str = "max",
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, TimeframeResult]]:
    daily = prepare_technical_prices(download_prices(ticker, period))

    calculated_frames: Dict[str, pd.DataFrame] = {}
    summaries: Dict[str, TimeframeResult] = {}

    for timeframe, rule in RESAMPLE_RULES.items():
        ohlc = resample_ohlc(daily, rule)
        calculated = calculate_composite_momentum(ohlc)

        calculated_frames[timeframe] = calculated
        summaries[timeframe] = summarize_timeframe(timeframe, calculated)

    return calculated_frames, summaries


# ---------------------------------------------------------------------------
# Report testuale
# ---------------------------------------------------------------------------

def print_report(
    ticker: str,
    summaries: Dict[str, TimeframeResult],
) -> None:
    quarterly = summaries["QUARTERLY"]
    monthly = summaries["MONTHLY"]
    weekly = summaries["WEEKLY"]
    yearly = summaries["YEARLY"]

    action, rating, note = strategy_from_matrix(
        quarterly.direction,
        monthly.direction,
        weekly.turn,
    )

    print()
    print("=" * 78)
    print(f"ANALISI CICLICA - {ticker.upper()}")
    print("Composite Momentum secondo le formule pubblicate nei paper")
    print("=" * 78)

    for name in ("YEARLY", "QUARTERLY", "MONTHLY", "WEEKLY"):
        result = summaries[name]

        print(f"\n{name}")
        print(f"  Data barra:       {result.date.date()}")
        print(f"  Chiusura:         {result.close:.4f}")
        print(f"  Composite:        {result.composite:.2f}")
        print(f"  Composite prec.:  {result.previous_composite:.2f}")
        print(f"  Direzione:        {result.direction}")
        print(f"  Posizione:        {result.position}")
        print(f"  Eccesso:          {result.excess}")
        print(f"  Flesso:           {result.turn}")

    print("\n" + "-" * 78)
    print("LETTURA OPERATIVA DELLA MATRICE PUBBLICATA")
    print("-" * 78)
    print(f"  CM annuale:       {yearly.direction}")
    print(f"  CM trimestrale:   {quarterly.direction}")
    print(f"  CM mensile:       {monthly.direction}")
    print(f"  CM settimanale:   {weekly.turn}")
    print(f"  Azione:           {action}")
    print(f"  Reward/Risk:      {'●' * rating if rating else 'N/D'}")
    print(f"  Nota:             {note}")

    print("\nLIMITI DOCUMENTALI")
    print(
        "  Il report non include l'Investitore Disciplinato (ID), perché la sua "
        "formula completa non è presente nei paper forniti."
    )
    print(
        "  Il risultato replica la parte formalizzabile e pubblicata del "
        "Composite Momentum e della matrice multi-timeframe."
    )
    print("=" * 78)


# ---------------------------------------------------------------------------
# Grafici facoltativi
# ---------------------------------------------------------------------------

def plot_results(
    ticker: str,
    calculated_frames: Dict[str, pd.DataFrame],
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "matplotlib non è installato. Esegui: pip install matplotlib"
        ) from exc

    for timeframe in ("QUARTERLY", "MONTHLY", "WEEKLY"):
        frame = calculated_frames[timeframe].dropna(subset=["Composite"])

        figure, axis = plt.subplots(figsize=(12, 5))
        axis.plot(frame.index, frame["Composite"], label="Composite Momentum")
        axis.axhline(80, linewidth=1)
        axis.axhline(50, linewidth=1)
        axis.axhline(0, linewidth=1)
        axis.axhline(-50, linewidth=1)
        axis.axhline(-80, linewidth=1)
        axis.set_title(f"{ticker.upper()} - Composite Momentum {timeframe}")
        axis.set_ylabel("Composite Momentum")
        axis.set_ylim(-105, 105)
        axis.grid(True, alpha=0.3)
        axis.legend()
        figure.tight_layout()

    plt.show()


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analisi del Composite Momentum multi-timeframe basata sulle "
            "formule pubblicate nei paper di Francesco Caruso."
        )
    )

    parser.add_argument(
        "ticker",
        help="Ticker Yahoo Finance, per esempio ENI.MI, ISP.MI, AAPL.",
    )
    parser.add_argument(
        "--period",
        default="max",
        help="Storico da scaricare: 10y, 15y, 20y, max. Default: max.",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Mostra i grafici trimestrale, mensile e settimanale.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    try:
        frames, summaries = analyze_ticker(args.ticker, args.period)
        print_report(args.ticker, summaries)

        if args.plot:
            plot_results(args.ticker, frames)

    except Exception as error:
        raise SystemExit(f"Errore: {error}") from error


if __name__ == "__main__":
    main()
