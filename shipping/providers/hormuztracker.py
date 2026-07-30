from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

API_URL = "https://www.hormuztracker.com/api/data"


class HormuzTrackerError(RuntimeError):
    """Raised when HormuzTracker data cannot be downloaded or validated."""


@dataclass(frozen=True)
class HormuzSnapshot:
    data: dict[str, Any]
    fetched_at_utc: str
    source_url: str = API_URL

    @property
    def meta(self) -> dict[str, Any]:
        return self.data.get("meta", {}) if isinstance(self.data, dict) else {}

    @property
    def crisis(self) -> dict[str, Any]:
        return self.data.get("crisis", {}) if isinstance(self.data, dict) else {}


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HormuzTrackerError("La risposta principale non e un oggetto JSON.")
    if not isinstance(payload.get("meta"), dict):
        raise HormuzTrackerError("Campo 'meta' assente o non valido.")
    if not isinstance(payload.get("crisis"), dict):
        raise HormuzTrackerError("Campo 'crisis' assente o non valido.")
    return payload


def fetch_hormuz_data(timeout: int = 25) -> HormuzSnapshot:
    try:
        response = requests.get(
            API_URL,
            timeout=timeout,
            headers={
                "User-Agent": "Cyclical-Global-Macro-Terminal/1.0",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        payload = validate_payload(response.json())
    except requests.Timeout as exc:
        raise HormuzTrackerError("Timeout durante il collegamento a HormuzTracker.") from exc
    except requests.RequestException as exc:
        raise HormuzTrackerError(f"Errore HTTP HormuzTracker: {exc}") from exc
    except ValueError as exc:
        raise HormuzTrackerError("HormuzTracker non ha restituito JSON valido.") from exc

    return HormuzSnapshot(
        data=payload,
        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
    )
