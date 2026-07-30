from __future__ import annotations

import pandas as pd

from core.logging_config import get_logger
from data.providers.common import build_http_session, parse_tabular_series

logger = get_logger(__name__)

BUNDESBANK_BUND10_CSV = (
    "https://api.statistiken.bundesbank.de/rest/data/BBSSY/"
    "D.REN.EUR.A630.000000WT1010.A"
)
ECB_DATA_API = "https://data-api.ecb.europa.eu/service/data"


def fetch_bundesbank_bund_10y(timeout: int = 20) -> pd.Series:
    """Fetch the official daily yield of the current German 10-year Bund.

    Bundesbank uses a vendor-specific CSV media type. We request it explicitly
    and constrain the response to recent observations to keep the payload small.
    """
    session = build_http_session()
    headers = {
        "Accept": "application/vnd.bbk.data+csv",
        "Accept-Language": "en",
    }
    try:
        response = session.get(
            BUNDESBANK_BUND10_CSV,
            params={"format": "csv", "lang": "en", "lastNObservations": 15},
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        series = parse_tabular_series(response.text)
        if series.empty:
            raise ValueError("Bundesbank CSV returned no parseable observations")
        return series
    except Exception as exc:
        logger.warning("Bundesbank Bund 10Y fetch failed: %s", exc)
        return pd.Series(dtype=float)


def fetch_ecb_aaa_10y(days: int = 30, timeout: int = 20) -> pd.Series:
    """Daily euro-area AAA 10-year spot rate, used only as an explicit proxy."""
    start = (pd.Timestamp.utcnow() - pd.Timedelta(days=days)).date().isoformat()
    key = "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y"
    url = f"{ECB_DATA_API}/YC/{key}"
    session = build_http_session()
    try:
        response = session.get(
            url,
            params={"format": "csvdata", "startPeriod": start},
            timeout=timeout,
        )
        response.raise_for_status()
        return parse_tabular_series(response.text)
    except Exception as exc:
        logger.warning("ECB AAA 10Y proxy fetch failed: %s", exc)
        return pd.Series(dtype=float)


def fetch_ecb_aaa_curve(days: int = 550, timeout: int = 20) -> pd.DataFrame:
    maturities = {"2Y": "SR_2Y", "5Y": "SR_5Y", "10Y": "SR_10Y", "30Y": "SR_30Y"}
    start = (pd.Timestamp.utcnow() - pd.Timedelta(days=days)).date().isoformat()
    output: dict[str, pd.Series] = {}
    session = build_http_session()

    for label, maturity in maturities.items():
        key = f"B.U2.EUR.4F.G_N_A.SV_C_YM.{maturity}"
        url = f"{ECB_DATA_API}/YC/{key}"
        try:
            response = session.get(
                url,
                params={"format": "csvdata", "startPeriod": start},
                timeout=timeout,
            )
            response.raise_for_status()
            series = parse_tabular_series(response.text)
            if not series.empty:
                output[label] = series
        except Exception as exc:
            logger.warning("ECB curve fetch failed for %s: %s", label, exc)

    return pd.DataFrame(output).sort_index() if output else pd.DataFrame()


def fetch_ecb_country_long_term_10y(country_code: str, timeout: int = 20) -> pd.Series:
    """Official harmonised long-term government-bond yield (10Y benchmark).

    The ECB IRS dataset is monthly. It is used only as a transparent fallback
    when delayed/intraday public quote pages are unavailable.
    """
    code = str(country_code).strip().upper()
    key = f"M.{code}.L.L40.CI.0000.EUR.N.Z"
    url = f"{ECB_DATA_API}/IRS/{key}"
    session = build_http_session()
    try:
        response = session.get(
            url,
            params={"format": "csvdata", "lastNObservations": 6},
            timeout=timeout,
        )
        response.raise_for_status()
        series = parse_tabular_series(response.text)
        if series.empty:
            raise ValueError(f"ECB IRS returned no observations for {code}")
        return series
    except Exception as exc:
        logger.warning("ECB country 10Y fetch failed for %s: %s", code, exc)
        return pd.Series(dtype=float)
