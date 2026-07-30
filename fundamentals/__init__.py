"""Deterministic Fundamental Analysis engine.

Peer of `technical/` and `analysis/cyclical/`: pure Python/pandas, no LLM
involved anywhere in this package. Every rating, valuation and narrative
sentence is derived from data returned by a `FundamentalDataProvider`
(`data/providers/fundamentals/`) — never invented, never silently
defaulted. See `fundamentals/provenance.py` for the explicit coverage table.
"""
