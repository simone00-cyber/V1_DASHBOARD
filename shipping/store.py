"""Thread-safe in-memory store for live AIS vessel snapshots."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
import threading
from typing import Iterable

import pandas as pd

from .models import VesselRecord


class VesselStore:
    def __init__(self, stale_minutes: int = 45) -> None:
        self._lock = threading.RLock()
        self._vessels: dict[str, VesselRecord] = {}
        self._message_count = 0
        self._raw_message_count = 0
        self._unhandled_message_count = 0
        self._last_raw_message_type: str | None = None
        self._last_message_at: datetime | None = None
        self._status = "IDLE"
        self._last_error: str | None = None
        self._stale_minutes = stale_minutes
        self._traffic_history: deque[dict] = deque(maxlen=1440)
        self._last_snapshot_minute: datetime | None = None

    def set_status(self, status: str, error: str | None = None) -> None:
        with self._lock:
            self._status = status
            self._last_error = error

    def record_raw_message(self, message_type: str | None = None, handled: bool = False) -> None:
        """Record every WebSocket payload, including unsupported/control messages."""
        with self._lock:
            self._raw_message_count += 1
            self._last_message_at = datetime.now(timezone.utc)
            self._last_raw_message_type = message_type or "UNKNOWN"
            if not handled:
                self._unhandled_message_count += 1

    def mark_message_handled(self) -> None:
        with self._lock:
            if self._unhandled_message_count > 0:
                self._unhandled_message_count -= 1

    def upsert(self, mmsi: str, **values) -> None:
        with self._lock:
            vessel = self._vessels.setdefault(mmsi, VesselRecord(mmsi=mmsi))
            vessel.update(**values)
            self._message_count += 1
            self._last_message_at = datetime.now(timezone.utc)
            self._capture_snapshot_locked()

    def _capture_snapshot_locked(self) -> None:
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        if self._last_snapshot_minute == now:
            return
        active = self._active_records_locked(now)
        self._traffic_history.append(
            {
                "timestamp": now,
                "active_vessels": len(active),
                "moving_vessels": sum(1 for v in active if (v.speed_knots or 0) >= 1.0),
                "tankers": sum(1 for v in active if v.category in {"Tanker", "Gas carrier"}),
            }
        )
        self._last_snapshot_minute = now

    def _active_records_locked(self, now: datetime | None = None) -> list[VesselRecord]:
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=self._stale_minutes)
        return [
            vessel
            for vessel in self._vessels.values()
            if vessel.last_update is not None
            and vessel.last_update >= cutoff
            and vessel.latitude is not None
            and vessel.longitude is not None
        ]

    def prune(self) -> None:
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
            stale = [mmsi for mmsi, vessel in self._vessels.items() if not vessel.last_update or vessel.last_update < cutoff]
            for mmsi in stale:
                self._vessels.pop(mmsi, None)

    def get(self, mmsi: str) -> VesselRecord | None:
        with self._lock:
            return self._vessels.get(mmsi)

    def dataframe(self) -> pd.DataFrame:
        with self._lock:
            records = [v.to_dict() for v in self._active_records_locked()]
        if not records:
            return pd.DataFrame()
        return pd.DataFrame(records)

    def history_dataframe(self) -> pd.DataFrame:
        with self._lock:
            records = list(self._traffic_history)
        return pd.DataFrame(records)

    def diagnostics(self) -> dict:
        with self._lock:
            return {
                "status": self._status,
                "last_error": self._last_error,
                "message_count": self._message_count,
                "raw_message_count": self._raw_message_count,
                "unhandled_message_count": self._unhandled_message_count,
                "last_raw_message_type": self._last_raw_message_type,
                "last_message_at": self._last_message_at,
                "tracked_vessels": len(self._vessels),
                "active_vessels": len(self._active_records_locked()),
            }
