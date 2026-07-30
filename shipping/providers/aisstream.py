"""AISStream WebSocket collector.

The collector runs in a daemon thread and keeps credentials server-side. It
normalizes the most useful dynamic and static AIS messages into VesselStore.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import random
import threading
from typing import Any

import websockets

from shipping.classification import (
    classify_ship_type,
    clean_text,
    navigational_status,
    safe_float,
    safe_int,
)
from shipping.chokepoints import Chokepoint
from shipping.store import VesselStore

LOGGER = logging.getLogger(__name__)
AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"


class AISStreamCollector:
    def __init__(self, api_key: str, chokepoint: Chokepoint, store: VesselStore) -> None:
        self.api_key = api_key.strip()
        self.chokepoint = chokepoint
        self.store = store
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._thread_main, name="aisstream-collector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self.store.set_status("STOPPING")

    def _thread_main(self) -> None:
        asyncio.run(self._run_forever())

    async def _run_forever(self) -> None:
        delay = 2.0
        while not self._stop_event.is_set():
            try:
                self.store.set_status("CONNECTING")
                async with websockets.connect(
                    AISSTREAM_URL,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_queue=4096,
                ) as websocket:
                    # Start without message-type filters. AISStream documents these
                    # filters as optional; receiving the complete feed is more robust
                    # for diagnostics and avoids silently excluding message variants.
                    subscription = {
                        "APIKey": self.api_key,
                        "BoundingBoxes": [self.chokepoint.ais_bounding_box],
                    }
                    await websocket.send(json.dumps(subscription))
                    # A successful WebSocket handshake only proves connectivity. The
                    # feed is marked LIVE after the first valid AIS payload arrives.
                    self.store.set_status("CONNECTED / WAITING")
                    delay = 2.0
                    async for raw_message in websocket:
                        if self._stop_event.is_set():
                            break
                        try:
                            payload = json.loads(raw_message)
                            self._handle_message(payload)
                        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                            LOGGER.debug("AIS message ignored: %s", error)
            except Exception as error:  # reconnect loop intentionally broad
                message = f"{type(error).__name__}: {error}"
                LOGGER.warning("AISStream connection error: %s", message)
                self.store.set_status("RECONNECTING", message)
                await asyncio.sleep(delay + random.random())
                delay = min(delay * 2, 60.0)

    def _handle_message(self, payload: dict[str, Any]) -> None:
        message_type = payload.get("MessageType")
        self.store.record_raw_message(message_type=message_type, handled=False)

        # Official AISStream examples use `MetaData`; older/community examples
        # sometimes use `Metadata`. Support both spellings.
        metadata = payload.get("MetaData") or payload.get("Metadata") or {}
        message_container = payload.get("Message") or {}
        body = message_container.get(message_type) or {}
        # StaticDataReport may wrap fields in ReportA / ReportB objects. Merge
        # them without overwriting top-level values already present.
        if isinstance(body, dict):
            merged_body = dict(body)
            for nested_key in ("ReportA", "ReportB"):
                nested = body.get(nested_key)
                if isinstance(nested, dict):
                    for key, value in nested.items():
                        merged_body.setdefault(key, value)
            body = merged_body

        mmsi_value = (
            body.get("UserID")
            or body.get("UserId")
            or metadata.get("MMSI")
            or metadata.get("UserID")
        )
        if mmsi_value is None:
            return
        mmsi = str(mmsi_value)

        existing = self.store.get(mmsi)
        existing_name = existing.name if existing else None
        existing_code = existing.ship_type_code if existing else None

        name = clean_text(
            metadata.get("ShipName")
            or body.get("Name")
            or body.get("ShipName")
            or existing_name
        )
        ship_type_code = safe_int(
            body.get("Type")
            or body.get("ShipType")
            or body.get("TypeAndCargo")
            or existing_code
        )

        latitude = safe_float(body.get("Latitude") if body.get("Latitude") is not None else metadata.get("Latitude"))
        longitude = safe_float(body.get("Longitude") if body.get("Longitude") is not None else metadata.get("Longitude"))
        speed = safe_float(body.get("Sog") if body.get("Sog") is not None else body.get("SpeedOverGround"))
        course = safe_float(body.get("Cog") if body.get("Cog") is not None else body.get("CourseOverGround"))
        heading = safe_float(body.get("TrueHeading") if body.get("TrueHeading") is not None else body.get("Heading"))

        if speed is not None and speed > 102.2:
            speed = None
        if course is not None and course >= 360:
            course = None
        if heading is not None and heading >= 511:
            heading = None
        if latitude is not None and not (-90 <= latitude <= 90):
            latitude = None
        if longitude is not None and not (-180 <= longitude <= 180):
            longitude = None

        dimension = body.get("Dimension") or {}
        length = None
        width = None
        if dimension:
            a = safe_float(dimension.get("A")) or 0.0
            b = safe_float(dimension.get("B")) or 0.0
            c = safe_float(dimension.get("C")) or 0.0
            d = safe_float(dimension.get("D")) or 0.0
            length = a + b if (a + b) > 0 else None
            width = c + d if (c + d) > 0 else None

        eta = body.get("Eta") or body.get("ETA")
        if isinstance(eta, dict):
            eta = "-".join(str(eta.get(k, "")) for k in ("Month", "Day", "Hour", "Minute")).strip("-")

        self.store.mark_message_handled()
        self.store.upsert(
            mmsi,
            latitude=latitude,
            longitude=longitude,
            name=name,
            imo=clean_text(body.get("ImoNumber") or body.get("IMO")),
            call_sign=clean_text(body.get("CallSign")),
            ship_type_code=ship_type_code,
            category=classify_ship_type(ship_type_code, name),
            destination=clean_text(body.get("Destination")),
            eta=clean_text(eta),
            speed_knots=speed,
            course=course,
            heading=heading,
            navigational_status=navigational_status(body.get("NavigationalStatus")),
            draught_m=safe_float(body.get("MaximumStaticDraught") or body.get("Draught")),
            length_m=length,
            width_m=width,
            last_message_type=message_type,
            last_update=datetime.now(timezone.utc),
        )
        self.store.set_status("LIVE")
        if self.store.diagnostics()["message_count"] % 500 == 0:
            self.store.prune()
