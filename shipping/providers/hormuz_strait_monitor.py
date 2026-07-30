from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://hormuzstraitmonitor.com/api/dashboard"
SOURCE_NAME = "Hormuz Strait Monitor"
SOURCE_SITE = "https://hormuzstraitmonitor.com/"


class HormuzMonitorError(RuntimeError):
    """Raised when the public Hormuz Strait Monitor feed is unavailable or invalid."""


@dataclass(frozen=True)
class HormuzMonitorSnapshot:
    data: dict[str, Any]
    fetched_at_utc: str
    source_timestamp: str | None
    source_url: str = API_URL


def _session() -> requests.Session:
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.4,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def validate_payload(payload: Any) -> tuple[dict[str, Any], str | None]:
    if not isinstance(payload, dict):
        raise HormuzMonitorError("La risposta API non e un oggetto JSON.")
    if payload.get("success") is not True:
        raise HormuzMonitorError("Il provider ha restituito success=false.")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise HormuzMonitorError("Campo 'data' assente o non valido.")

    required = ("straitStatus", "shipCount", "throughput", "insurance")
    missing = [key for key in required if not isinstance(data.get(key), dict)]
    if missing:
        raise HormuzMonitorError("Payload incompleto. Campi mancanti: " + ", ".join(missing))

    source_timestamp = data.get("lastUpdated") or payload.get("timestamp")
    return data, str(source_timestamp) if source_timestamp else None


def fetch_dashboard(timeout: int = 25) -> HormuzMonitorSnapshot:
    try:
        response = _session().get(
            API_URL,
            timeout=timeout,
            headers={
                "User-Agent": "Cyclical-Global-Macro-Terminal/1.0",
                "Accept": "application/json",
                "Cache-Control": "no-cache",
            },
        )
        response.raise_for_status()
        data, source_timestamp = validate_payload(response.json())
    except requests.Timeout as exc:
        raise HormuzMonitorError("Timeout durante il collegamento a Hormuz Strait Monitor.") from exc
    except requests.RequestException as exc:
        raise HormuzMonitorError(f"Errore HTTP Hormuz Strait Monitor: {exc}") from exc
    except ValueError as exc:
        raise HormuzMonitorError("Il provider non ha restituito JSON valido.") from exc

    return HormuzMonitorSnapshot(
        data=data,
        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
        source_timestamp=source_timestamp,
    )
