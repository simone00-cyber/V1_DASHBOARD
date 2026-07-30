"""Normalized live/official macro-data service.

This module is intentionally an orchestration layer. Remote parsing lives in
`data.providers`; the Streamlit view consumes only MacroQuote objects and clean
DataFrames. No UI code and no HTML/CSV parsing is performed here.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.logging_config import get_logger
from data.investing_rates import fetch_investing_rate
from data.providers.common import as_utc_timestamp, latest_change, quote_status
from data.providers.marketwatch_rates import fetch_marketwatch_rate
from data.providers.official_rates import (
    fetch_bundesbank_bund_10y,
    fetch_ecb_aaa_10y,
    fetch_ecb_aaa_curve,
    fetch_ecb_country_long_term_10y,
)
from data.providers.yahoo_macro import download_intraday_close

logger = get_logger(__name__)

YAHOO_LIVE_TICKERS: dict[str, str] = {
    "US 10Y": "^TNX",
    "DXY": "DX-Y.NYB",
    "VIX": "^VIX",
    "BRENT": "BZ=F",
    "GOLD": "GC=F",
}


@dataclass(frozen=True)
class MacroQuote:
    label: str
    value: float | None
    change: float | None
    unit: str
    as_of: pd.Timestamp | None
    source: str
    frequency: str
    status: str
    note: str = ""

    @property
    def is_available(self) -> bool:
        return self.value is not None and np.isfinite(self.value)



def unavailable_quote(
    label: str,
    *,
    unit: str,
    source: str,
    frequency: str,
    note: str = "",
) -> MacroQuote:
    return MacroQuote(label, None, None, unit, None, source, frequency, "UNAVAILABLE", note)



def load_live_market_quotes() -> dict[str, MacroQuote]:
    close = download_intraday_close(YAHOO_LIVE_TICKERS.values())
    output: dict[str, MacroQuote] = {}

    for label, ticker in YAHOO_LIVE_TICKERS.items():
        series = close[ticker].dropna() if ticker in close.columns else pd.Series(dtype=float)
        unit = "%" if label == "US 10Y" else ""
        if series.empty:
            output[label] = unavailable_quote(
                label,
                unit=unit,
                source="Yahoo Finance",
                frequency="INTRADAY",
                note=ticker,
            )
            continue

        value, raw_change, as_of = latest_change(series)
        # ^TNX is quoted in percentage points. UI convention is basis-point change.
        change = raw_change * 100.0 if label == "US 10Y" and raw_change is not None else raw_change
        output[label] = MacroQuote(
            label=label,
            value=value,
            change=change,
            unit=unit,
            as_of=as_of,
            source="Yahoo Finance",
            frequency="INTRADAY",
            status=quote_status(as_of, 6.0),
            note=ticker,
        )
    return output



def _load_investing_quote(label: str, *, unit: str) -> MacroQuote:
    result = fetch_investing_rate(label)
    if not result.available:
        return unavailable_quote(
            label,
            unit=unit,
            source="Investing.com",
            frequency="INTRADAY",
            note=result.note,
        )

    change = result.change
    if unit == "%" and change is not None:
        change *= 100.0
    return MacroQuote(
        label=label,
        value=float(result.value),
        change=float(change) if change is not None else None,
        unit=unit,
        as_of=as_utc_timestamp(result.as_of),
        source="Investing.com",
        frequency="INTRADAY",
        status=quote_status(as_utc_timestamp(result.as_of), 8.0),
        note=result.url,
    )



def load_bund_10y() -> MacroQuote:
    """Load the exact Bund yield, then an explicitly labelled official proxy."""
    series = fetch_bundesbank_bund_10y()
    value, change, as_of = latest_change(series, multiplier=100.0)
    if value is not None:
        return MacroQuote(
            label="BUND 10Y",
            value=value,
            change=change,
            unit="%",
            as_of=as_of,
            source="Deutsche Bundesbank",
            frequency="DAILY",
            status=quote_status(as_of, 96.0),
            note="Official current 10-year federal bond yield; change in basis points",
        )

    proxy = fetch_ecb_aaa_10y()
    proxy_value, proxy_change, proxy_as_of = latest_change(proxy, multiplier=100.0)
    if proxy_value is not None:
        return MacroQuote(
            label="BUND 10Y",
            value=proxy_value,
            change=proxy_change,
            unit="%",
            as_of=proxy_as_of,
            source="ECB Data Portal",
            frequency="DAILY",
            status=quote_status(proxy_as_of, 96.0),
            note="Euro-area AAA 10Y spot-rate proxy; not the exact on-the-run Bund",
        )

    return unavailable_quote(
        "BUND 10Y",
        unit="%",
        source="Deutsche Bundesbank / ECB",
        frequency="DAILY",
        note="Exact Bund and official AAA proxy unavailable",
    )



def _load_marketwatch_quote(label: str) -> MacroQuote:
    result = fetch_marketwatch_rate(label)
    if not result.available:
        return unavailable_quote(
            label,
            unit="%",
            source="MarketWatch",
            frequency="DELAYED",
            note=result.note,
        )
    change = float(result.change) * 100.0 if result.change is not None else None
    return MacroQuote(
        label=label,
        value=float(result.value),
        change=change,
        unit="%",
        as_of=as_utc_timestamp(result.as_of),
        source="MarketWatch",
        frequency="DELAYED",
        status=quote_status(as_utc_timestamp(result.as_of), 24.0),
        note=result.url,
    )


def load_european_rates() -> dict[str, MacroQuote]:
    bund = _load_investing_quote("BUND 10Y", unit="%")
    if not bund.is_available:
        bund = _load_marketwatch_quote("BUND 10Y")
    if not bund.is_available:
        bund = load_bund_10y()

    italy = _load_investing_quote("ITALY 10Y", unit="%")
    if not italy.is_available:
        italy = _load_marketwatch_quote("ITALY 10Y")
    if not italy.is_available:
        official_italy = fetch_ecb_country_long_term_10y("IT")
        value, change, as_of = latest_change(official_italy, multiplier=100.0)
        if value is not None:
            italy = MacroQuote(
                label="ITALY 10Y",
                value=value,
                change=change,
                unit="%",
                as_of=as_of,
                source="ECB Data Portal / Banca d'Italia",
                frequency="MONTHLY",
                status=quote_status(as_of, 24.0 * 45.0),
                note=(
                    "Official harmonised 10-year benchmark yield; monthly fallback "
                    "used because intraday public quote providers were unavailable"
                ),
            )

    direct_spread = _load_investing_quote("BTP-BUND 10Y", unit="bp")

    if italy.is_available and bund.is_available:
        value = (float(italy.value) - float(bund.value)) * 100.0
        change = (
            float(italy.change) - float(bund.change)
            if italy.change is not None and bund.change is not None
            else None
        )
        timestamps = [item for item in (italy.as_of, bund.as_of) if item is not None]
        as_of = min(timestamps) if timestamps else None
        status = "STALE" if "STALE" in {italy.status, bund.status} else "OK"
        spread = MacroQuote(
            label="BTP-BUND 10Y",
            value=value,
            change=change,
            unit="bp",
            as_of=as_of,
            source=f"Calculated: {italy.source} Italy 10Y - {bund.source} Bund 10Y",
            frequency="INTRADAY" if italy.frequency == bund.frequency == "INTRADAY" else "MIXED",
            status=status,
            note="Same-maturity sovereign-yield differential",
        )
    elif direct_spread.is_available:
        spread = direct_spread
    else:
        spread = unavailable_quote(
            "BTP-BUND 10Y",
            unit="bp",
            source="Investing.com / calculated / ECB fallback",
            frequency="MIXED",
        )

    return {"BUND 10Y": bund, "ITALY 10Y": italy, "BTP-BUND 10Y": spread}



def build_global_rates_snapshot() -> dict[str, MacroQuote]:
    live = load_live_market_quotes()
    europe = load_european_rates()
    us10 = live.get("US 10Y") or unavailable_quote(
        "US 10Y", unit="%", source="Yahoo Finance", frequency="INTRADAY"
    )
    bund = europe["BUND 10Y"]

    if us10.is_available and bund.is_available:
        value = (float(us10.value) - float(bund.value)) * 100.0
        change = (
            float(us10.change) - float(bund.change)
            if us10.change is not None and bund.change is not None
            else None
        )
        timestamps = [item for item in (us10.as_of, bund.as_of) if item is not None]
        as_of = min(timestamps) if timestamps else None
        us_de = MacroQuote(
            label="US-DE 10Y",
            value=value,
            change=change,
            unit="bp",
            as_of=as_of,
            source=f"Calculated: {us10.source} US 10Y - {bund.source} Bund 10Y",
            frequency=us10.frequency if us10.frequency == bund.frequency else "MIXED",
            status="STALE" if "STALE" in {us10.status, bund.status} else "OK",
            note="Cross-market 10-year yield differential",
        )
    else:
        us_de = unavailable_quote(
            "US-DE 10Y", unit="bp", source="Calculated", frequency="MIXED"
        )

    return {
        "US 10Y": us10,
        "BUND 10Y": bund,
        "ITALY 10Y": europe["ITALY 10Y"],
        "BTP-BUND 10Y": europe["BTP-BUND 10Y"],
        "US-DE 10Y": us_de,
    }



def load_ecb_aaa_curve() -> pd.DataFrame:
    return fetch_ecb_aaa_curve()
