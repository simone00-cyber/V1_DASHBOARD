"""Upcoming Macro Releases — explicitly scoped to the official releases
behind the series this workspace actually sources (see
`macro/config.py::CALENDAR_SCOPE_NOTE`). This is not a general/global
economic calendar.

Release ids are resolved by name at runtime against FRED's own release
catalog (`fred/releases`) rather than hardcoded, since numeric release ids
are an internal FRED implementation detail that could drift. A release with
no published future date is simply omitted — never guessed from a typical
cadence.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from data.providers.macro.fred import (
    FredConfigurationError,
    FredUnavailableError,
    fetch_release_dates,
    fetch_releases,
)
from macro import config
from macro.models import CalendarEvent

_release_id_cache: dict[str, str] = {}


def _resolve_release_ids(release_names: list[str], *, session: Any = None) -> dict[str, str]:
    """Resolves every requested release name in one pass over one fetched
    `fred/releases` listing — not one fetch per name."""
    missing = [name for name in release_names if name not in _release_id_cache]
    if missing:
        releases = fetch_releases(session=session)
        by_name = {str(release.get("name", "")).strip().lower(): str(release.get("id")) for release in releases}
        for name in missing:
            release_id = by_name.get(name.strip().lower())
            if release_id is not None:
                _release_id_cache[name] = release_id
    return {name: _release_id_cache[name] for name in release_names if name in _release_id_cache}


def build_upcoming_releases(
    *, session: Any = None, lookback_days: int = 14, lookahead_days: int = 60
) -> tuple[CalendarEvent, ...]:
    now = pd.Timestamp.now(tz="UTC")
    horizon_start = now - pd.Timedelta(days=lookback_days)
    horizon_end = now + pd.Timedelta(days=lookahead_days)

    events: list[CalendarEvent] = []
    try:
        release_ids = _resolve_release_ids([info["name"] for info in config.FRED_RELEASES.values()], session=session)
        for canonical_release_id, info in config.FRED_RELEASES.items():
            release_id = release_ids.get(info["name"])
            if release_id is None:
                continue
            dates = fetch_release_dates(release_id, session=session)
            if dates.empty:
                continue
            upcoming = dates[(dates["date"] >= horizon_start) & (dates["date"] <= horizon_end)]
            for _, row in upcoming.iterrows():
                scheduled_date = row["date"]
                events.append(
                    CalendarEvent(
                        release_name=info["name"],
                        country_region=info["country"],
                        scheduled_date=scheduled_date,
                        scheduled_time=None,  # FRED gives a date only — never inferred
                        reference_period=None,
                        importance=config.RELEASE_IMPORTANCE.get(canonical_release_id, "MEDIUM"),
                        affected_pillar=info["pillar"],
                        current_relevance=(
                            f"Next scheduled print feeding the {info['pillar'].title()} pillar."
                            if scheduled_date >= now
                            else f"Most recent print behind the current {info['pillar'].title()} pillar read."
                        ),
                        source="FRED (mirrors the official BLS/BEA release calendar)",
                    )
                )
    except (FredConfigurationError, FredUnavailableError):
        return tuple()

    return tuple(sorted(events, key=lambda event: event.scheduled_date))
