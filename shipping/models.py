"""Data models for normalized AIS information."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class VesselRecord:
    mmsi: str
    latitude: float | None = None
    longitude: float | None = None
    name: str | None = None
    imo: str | None = None
    call_sign: str | None = None
    ship_type_code: int | None = None
    category: str = "Other"
    destination: str | None = None
    eta: str | None = None
    speed_knots: float | None = None
    course: float | None = None
    heading: float | None = None
    navigational_status: str | None = None
    draught_m: float | None = None
    length_m: float | None = None
    width_m: float | None = None
    last_message_type: str | None = None
    last_update: datetime | None = None

    def update(self, **values: Any) -> None:
        for key, value in values.items():
            if value is not None and hasattr(self, key):
                setattr(self, key, value)
        self.last_update = values.get("last_update") or datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if self.last_update is not None:
            result["last_update"] = self.last_update.isoformat()
        return result
