"""Lifecycle helpers for the live AIS service."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

from .chokepoints import CHOKEPOINTS, Chokepoint
from .providers import AISStreamCollector
from .store import VesselStore


@dataclass
class AISService:
    store: VesselStore
    collector: AISStreamCollector | None
    api_key_configured: bool
    chokepoint: Chokepoint


def resolve_api_key() -> str | None:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env", override=False)
    value = os.getenv("AISSTREAM_API_KEY")
    return value.strip() if value and value.strip() else None


def build_service(chokepoint_name: str = "Strait of Hormuz") -> AISService:
    chokepoint = CHOKEPOINTS[chokepoint_name]
    store = VesselStore(stale_minutes=45)
    api_key = resolve_api_key()
    collector = AISStreamCollector(api_key, chokepoint, store) if api_key else None
    if collector:
        collector.start()
    else:
        store.set_status("NO API KEY")
    return AISService(store=store, collector=collector, api_key_configured=bool(api_key), chokepoint=chokepoint)


# Streamlit wraps this factory with st.cache_resource in the page. Keeping the
# factory framework-agnostic makes it testable outside Streamlit.
def get_ais_service(chokepoint_name: str = "Strait of Hormuz") -> AISService:
    return build_service(chokepoint_name)
