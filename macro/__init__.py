"""Deterministic macro analytics: Growth, Inflation, Liquidity, Cross-Asset
Confirmation and the Executive Market Thesis shared by Command Center and
Market Intelligence (`views/macro.py`).

Peer of `fundamentals/` and `technical/`: pure Python, no LLM anywhere in this
package. Every reading traces back to a real value fetched from an official
free provider (FRED, NY Fed) via `data/providers/macro/`, normalized into a
`MacroSeriesReading` with full provenance and freshness metadata
(`macro/metadata.py`). Missing or stale data reduces confidence — it is never
substituted with a proxy or fabricated.
"""
