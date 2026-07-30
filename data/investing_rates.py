from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
import json
import re
from typing import Any

import pandas as pd
import requests

from core.logging_config import get_logger

logger = get_logger(__name__)

INVESTING_BASE = "https://www.investing.com/rates-bonds"
INVESTING_INSTRUMENTS = {
    "BUND 10Y": "germany-10-year-bond-yield",
    "ITALY 10Y": "italy-10-year-bond-yield",
    "BTP-BUND 10Y": "de-10y-vs-it-10y",
}


@dataclass(frozen=True)
class InvestingRate:
    label: str
    value: float | None
    change: float | None
    as_of: pd.Timestamp | None
    url: str
    fetched_at: pd.Timestamp
    note: str = ""

    @property
    def available(self) -> bool:
        return self.value is not None and pd.notna(self.value)


def _number(value: Any) -> float | None:
    if value is None:
        return None
    text = unescape(str(value)).strip().replace("\u00a0", "").replace("%", "")
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("−", "-")
    if not text or text.lower() in {"n/a", "na", "nan", "-", "--"}:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    text = re.sub(r"[^0-9+\-.]", "", text)
    try:
        return float(text)
    except ValueError:
        return None


def _first_match(html: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.I | re.S)
        if match:
            return match.group(1)
    return None


def _walk_json(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_json(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)


def _parse_embedded_json(html: str) -> tuple[float | None, float | None]:
    """Best-effort parser for Next.js/JSON payloads embedded in the page."""
    scripts = re.findall(
        r"<script[^>]+type=[\"']application/(?:ld\+json|json)[\"'][^>]*>(.*?)</script>",
        html,
        flags=re.I | re.S,
    )
    scripts += re.findall(r"<script[^>]+id=[\"']__NEXT_DATA__[\"'][^>]*>(.*?)</script>", html, flags=re.I | re.S)
    for raw in scripts:
        try:
            payload = json.loads(unescape(raw).strip())
        except Exception:
            continue
        for node in _walk_json(payload):
            lowered = {str(k).lower(): v for k, v in node.items()}
            value = None
            for key in ("last", "last_close", "lastclose", "price", "value"):
                if key in lowered:
                    value = _number(lowered[key])
                    if value is not None:
                        break
            if value is None:
                continue
            change = None
            for key in ("change", "change_value", "changevalue"):
                if key in lowered:
                    change = _number(lowered[key])
                    break
            return value, change
    return None, None


def parse_investing_quote(html: str, *, is_spread: bool = False) -> tuple[float | None, float | None]:
    value_text = _first_match(
        html,
        (
            r'data-test=["\']instrument-price-last["\'][^>]*>(.*?)</',
            r'data-test=["\']instrument-header-details["\'][\s\S]{0,1500}?data-test=["\']instrument-price-last["\'][^>]*>(.*?)</',
            r'"last_close"\s*:\s*["\']?([0-9.,+-]+)',
            r'"last"\s*:\s*["\']?([0-9.,+-]+)',
        ),
    )
    change_text = _first_match(
        html,
        (
            r'data-test=["\']instrument-price-change["\'][^>]*>(.*?)</',
            r'"change"\s*:\s*["\']?([0-9.,+-]+)',
        ),
    )
    value = _number(value_text)
    change = _number(change_text)
    if value is None:
        value, json_change = _parse_embedded_json(html)
        if change is None:
            change = json_change

    # Investing commonly displays sovereign spreads in percentage points.
    # The terminal standardises them to basis points.
    if is_spread and value is not None and abs(value) < 20:
        value *= 100.0
        if change is not None:
            change *= 100.0
    return value, change


def fetch_investing_rate(label: str, *, timeout: int = 20) -> InvestingRate:
    slug = INVESTING_INSTRUMENTS[label]
    url = f"{INVESTING_BASE}/{slug}"
    fetched_at = pd.Timestamp(datetime.now(timezone.utc))
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,it;q=0.7",
        "Cache-Control": "no-cache",
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        value, change = parse_investing_quote(response.text, is_spread=label == "BTP-BUND 10Y")
        if value is None:
            raise ValueError("Current quote not found in Investing page")
        response_time = response.headers.get("Date")
        as_of = pd.to_datetime(response_time, utc=True, errors="coerce") if response_time else fetched_at
        if pd.isna(as_of):
            as_of = fetched_at
        return InvestingRate(label, value, change, as_of, url, fetched_at, "Public Investing.com quote page")
    except Exception as exc:
        logger.warning("Investing rate fetch failed for %s: %s", label, exc)
        return InvestingRate(label, None, None, None, url, fetched_at, str(exc))
