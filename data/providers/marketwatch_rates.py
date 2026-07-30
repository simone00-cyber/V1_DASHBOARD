from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
import json
import re
from typing import Any

import pandas as pd

from core.logging_config import get_logger
from data.providers.common import build_http_session, clean_numeric

logger = get_logger(__name__)

MARKETWATCH_INSTRUMENTS: dict[str, str] = {
    "BUND 10Y": "tmbmkde-10y",
    "ITALY 10Y": "tmbmkit-10y",
}


@dataclass(frozen=True)
class MarketWatchRate:
    label: str
    value: float | None
    change: float | None
    as_of: pd.Timestamp | None
    url: str
    note: str = ""

    @property
    def available(self) -> bool:
        return self.value is not None and pd.notna(self.value)


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _extract_json_quote(html: str) -> tuple[float | None, float | None]:
    scripts = re.findall(
        r"<script[^>]+type=[\"']application/(?:ld\+json|json)[\"'][^>]*>(.*?)</script>",
        html,
        flags=re.I | re.S,
    )
    for raw in scripts:
        try:
            payload = json.loads(unescape(raw).strip())
        except Exception:
            continue
        for node in _walk(payload):
            lower = {str(key).lower(): value for key, value in node.items()}
            value = None
            for key in ("yield", "price", "last", "lastprice", "value"):
                if key in lower:
                    value = clean_numeric(lower[key])
                    if value is not None:
                        break
            if value is None:
                continue
            change = None
            for key in ("change", "netchange", "pricechange"):
                if key in lower:
                    change = clean_numeric(lower[key])
                    break
            return value, change
    return None, None


def parse_marketwatch_quote(html: str) -> tuple[float | None, float | None]:
    patterns = (
        r'<bg-quote[^>]+class=["\'][^"\']*value[^"\']*["\'][^>]*>(.*?)</bg-quote>',
        r'<meta[^>]+name=["\']price["\'][^>]+content=["\']([^"\']+)',
        r'"lastPrice"\s*:\s*"?([0-9.,+-]+)',
        r'"price"\s*:\s*"?([0-9.,+-]+)',
        r'Yield\s*</span>\s*<span[^>]*>\s*([0-9.,+-]+)',
    )
    value = None
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.I | re.S)
        if match:
            value = clean_numeric(re.sub(r"<[^>]+>", "", match.group(1)))
            if value is not None:
                break

    change_patterns = (
        r'<bg-quote[^>]+class=["\'][^"\']*change--point[^"\']*["\'][^>]*>(.*?)</bg-quote>',
        r'"priceChange"\s*:\s*"?([0-9.,+-]+)',
        r'"change"\s*:\s*"?([0-9.,+-]+)',
    )
    change = None
    for pattern in change_patterns:
        match = re.search(pattern, html, flags=re.I | re.S)
        if match:
            change = clean_numeric(re.sub(r"<[^>]+>", "", match.group(1)))
            if change is not None:
                break

    if value is None:
        value, json_change = _extract_json_quote(html)
        if change is None:
            change = json_change
    return value, change


def fetch_marketwatch_rate(label: str, timeout: int = 20) -> MarketWatchRate:
    slug = MARKETWATCH_INSTRUMENTS[label]
    url = f"https://www.marketwatch.com/investing/bond/{slug}?countrycode=bx"
    session = build_http_session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        value, change = parse_marketwatch_quote(response.text)
        if value is None:
            raise ValueError("Current yield not found in MarketWatch page")
        response_time = response.headers.get("Date")
        as_of = pd.to_datetime(response_time, utc=True, errors="coerce") if response_time else None
        if as_of is None or pd.isna(as_of):
            as_of = pd.Timestamp(datetime.now(timezone.utc))
        return MarketWatchRate(label, float(value), change, as_of, url, "Delayed market quote")
    except Exception as exc:
        logger.warning("MarketWatch rate fetch failed for %s: %s", label, exc)
        return MarketWatchRate(label, None, None, None, url, str(exc))
