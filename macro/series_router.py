"""Provider routing: primary/fallback resolution per canonical series.

`resolve_series(canonical_id)` is the ONLY function pillar code calls for
data — it never talks to `data/providers/macro/*` directly. Adding a new
provider for an existing or new concept means editing
`macro/config.py::SERIES_REGISTRY` and this module's `_fetch_from_source`
dispatch — pillar/thesis logic never changes.

Values from different providers are never blended into one number. A
fallback is only ever used when the registry marks it `fallback_equivalent`
(the same real-world concept, e.g. two sources of the same SOFR print) — a
series with no equivalent fallback simply becomes UNAVAILABLE, never
silently substituted with an unrelated market proxy.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from data.providers.macro.fred import (
    FredConfigurationError,
    FredUnavailableError,
    fetch_observations,
    fetch_series_info,
)
from data.providers.macro.ny_fed import NyFedUnavailableError, fetch_reference_rate
from macro import config
from macro.metadata import unavailable_metadata
from macro.models import MacroSeriesReading
from macro.normalization import normalize_fred_reading, normalize_ny_fed_reading

_PROVIDER_ERRORS = (FredConfigurationError, FredUnavailableError, NyFedUnavailableError)


def _label_unit_frequency(source: dict) -> tuple[str, str, str]:
    provider = source["provider"]
    if provider == "FRED":
        catalog_entry = next(
            (info for info in config.FRED_SERIES.values() if info["series_id"] == source["series_id"]),
            None,
        )
        if catalog_entry:
            return catalog_entry["name"], catalog_entry["unit"], catalog_entry["frequency"]
        return source["series_id"], "", "DAILY"
    if provider == "NY_FED":
        info = config.NY_FED_SERIES[source["rate_type"]]
        return info["name"], info["unit"], info["frequency"]
    raise ValueError(f"Unknown provider: {provider}")


def _fetch_from_source(canonical_id: str, source: dict, *, session: Any = None) -> MacroSeriesReading:
    label, unit, frequency = _label_unit_frequency(source)
    if source["provider"] == "FRED":
        observations = fetch_observations(source["series_id"], session=session)
        info = fetch_series_info(source["series_id"], session=session)
        return normalize_fred_reading(
            canonical_id=canonical_id,
            series_id=source["series_id"],
            label=label,
            unit=unit,
            frequency=frequency,
            observations=observations,
            series_info=info,
        )
    if source["provider"] == "NY_FED":
        observations = fetch_reference_rate(source["rate_type"], session=session)
        return normalize_ny_fed_reading(
            canonical_id=canonical_id,
            rate_type=source["rate_type"],
            label=label,
            unit=unit,
            frequency=frequency,
            observations=observations,
        )
    raise ValueError(f"Unknown provider: {source['provider']}")


def resolve_series(canonical_id: str, *, session: Any = None) -> MacroSeriesReading:
    route = config.SERIES_REGISTRY.get(canonical_id)
    if route is None:
        raise KeyError(f"Unknown canonical series id: {canonical_id!r}")

    primary_error: str | None = None
    try:
        reading = _fetch_from_source(canonical_id, route["primary"], session=session)
        if reading.available:
            return reading
        primary_error = reading.metadata.unavailable_reason
    except _PROVIDER_ERRORS as exc:
        primary_error = str(exc)

    if route["fallback"] is not None and route["fallback_equivalent"] and route["on_failure"] == "USE_FALLBACK":
        try:
            fallback_reading = _fetch_from_source(canonical_id, route["fallback"], session=session)
            if fallback_reading.available:
                # Provenance is preserved: the fallback's own provider/source_url
                # stay intact, only availability_status is downgraded so the
                # substitution is visible everywhere this value is shown.
                degraded_metadata = dataclasses.replace(
                    fallback_reading.metadata, availability_status="DEGRADED (FALLBACK)"
                )
                return dataclasses.replace(fallback_reading, metadata=degraded_metadata)
        except _PROVIDER_ERRORS:
            pass

    label, unit, frequency = _label_unit_frequency(route["primary"])
    primary_source_id = route["primary"].get("series_id") or route["primary"].get("rate_type", "")
    metadata = unavailable_metadata(
        provider=route["primary"]["provider"],
        provider_series_id=primary_source_id,
        canonical_series_name=label,
        frequency=frequency,
        unit=unit,
        source_url="",
        unavailable_reason=primary_error or "No equivalent fallback is configured for this series.",
    )
    return MacroSeriesReading(canonical_id, label, None, None, None, None, metadata)
