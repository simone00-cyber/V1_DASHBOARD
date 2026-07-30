"""Raw, provider-specific macro data fetchers.

Each module here knows about exactly one external source's request/response
shape and returns plain DataFrames/dicts of *raw* values — never a
`MacroSeriesReading`. Normalization into the app's shared, provider-agnostic
shape happens in `macro/normalization.py`. This isolation is what lets a
future ECB/Treasury/BLS/BEA provider be added without touching any pillar or
thesis logic (see `macro/config.py::SERIES_REGISTRY`).
"""
