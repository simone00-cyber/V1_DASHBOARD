"""The Rates data-quality pass: adapts the existing Rates section's
`MacroQuote` (`data/macro_live.py`, unchanged) into the same `DataMetadata`
envelope every other macro value carries, so the whole Market Intelligence
workspace shares one freshness/provenance standard. `data/macro_live.py`'s
fetch/fallback logic is not rewritten — only its presentation gains the
shared metadata.
"""

from __future__ import annotations

from typing import Any

from macro.metadata import DataMetadata, build_data_metadata, unavailable_metadata

_QUOTE_FREQUENCY_MAP: dict[str, str] = {
    "INTRADAY": "REALTIME",
    "DAILY": "DAILY",
    "DELAYED": "DAILY",
    "MONTHLY": "MONTHLY",
    "MIXED": "DAILY",
}


def metadata_from_macro_quote(quote: Any) -> DataMetadata:
    """`quote` is a `data.macro_live.MacroQuote`. Kept as `Any` here to avoid
    a hard import-time dependency in the other direction."""
    frequency = _QUOTE_FREQUENCY_MAP.get(quote.frequency, "DEFAULT")
    if not quote.is_available or quote.as_of is None:
        return unavailable_metadata(
            provider=quote.source,
            provider_series_id=quote.label,
            canonical_series_name=quote.label,
            frequency=frequency,
            unit=quote.unit or "",
            source_url="",
            unavailable_reason=quote.note or "Quote unavailable from the configured provider(s).",
        )
    return build_data_metadata(
        provider=quote.source,
        provider_series_id=quote.label,
        canonical_series_name=quote.label,
        observation_date=quote.as_of,
        frequency=frequency,
        unit=quote.unit or "",
        source_url="",
    )
