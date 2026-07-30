"""Central configuration for the macro analytics package.

Every threshold, series mapping, provider-routing rule and confidence weight
used anywhere in `macro/` is named here — nothing is inline/magic. Mirrors
the convention already used by `fundamentals/config.py`.
"""
from __future__ import annotations

from datetime import timedelta

# --- Freshness: expected publication lag per frequency ----------------------
# How long after the observation/release we still consider data "current."
# Used by macro/metadata.py::build_data_metadata to score freshness.
FRESHNESS_EXPECTED_LAG: dict[str, timedelta] = {
    "REALTIME": timedelta(hours=1),
    "DAILY": timedelta(hours=30),
    "WEEKLY": timedelta(days=10),
    "MONTHLY": timedelta(days=45),
    "QUARTERLY": timedelta(days=100),
    "DEFAULT": timedelta(days=45),
}

# --- FRED series catalog -----------------------------------------------------
# canonical_id -> FRED series id + display metadata. This is the ONLY place
# FRED series ids are named; pillar/thesis code never references a raw id.
FRED_SERIES: dict[str, dict] = {
    "US_PAYROLLS": {"series_id": "PAYEMS", "name": "US Nonfarm Payrolls", "unit": "Thousands", "frequency": "MONTHLY"},
    "US_INDUSTRIAL_PRODUCTION": {"series_id": "INDPRO", "name": "US Industrial Production Index", "unit": "Index (2017=100)", "frequency": "MONTHLY"},
    "US_RETAIL_SALES": {"series_id": "RSAFS", "name": "US Retail Sales", "unit": "$ Millions", "frequency": "MONTHLY"},
    "US_REAL_GDP": {"series_id": "GDPC1", "name": "US Real GDP", "unit": "$ Billions (chained)", "frequency": "QUARTERLY"},
    "US_LEADING_INDEX": {"series_id": "USSLIND", "name": "US Leading Index", "unit": "Index", "frequency": "MONTHLY"},
    "US_UNEMPLOYMENT_RATE": {"series_id": "UNRATE", "name": "US Unemployment Rate", "unit": "%", "frequency": "MONTHLY"},
    "US_CPI_HEADLINE": {"series_id": "CPIAUCSL", "name": "US CPI (Headline, SA)", "unit": "Index (1982-84=100)", "frequency": "MONTHLY"},
    "US_CPI_CORE": {"series_id": "CPILFESL", "name": "US CPI (Core, SA)", "unit": "Index (1982-84=100)", "frequency": "MONTHLY"},
    "US_PCE_HEADLINE": {"series_id": "PCEPI", "name": "US PCE Price Index (Headline)", "unit": "Index (2017=100)", "frequency": "MONTHLY"},
    "US_PCE_CORE": {"series_id": "PCEPILFE", "name": "US PCE Price Index (Core)", "unit": "Index (2017=100)", "frequency": "MONTHLY"},
    "US_BREAKEVEN_5Y": {"series_id": "T5YIE", "name": "US 5Y Breakeven Inflation Rate", "unit": "%", "frequency": "DAILY"},
    "US_BREAKEVEN_10Y": {"series_id": "T10YIE", "name": "US 10Y Breakeven Inflation Rate", "unit": "%", "frequency": "DAILY"},
    "FED_TOTAL_ASSETS": {"series_id": "WALCL", "name": "Federal Reserve Total Assets", "unit": "$ Millions", "frequency": "WEEKLY"},
    "FED_RESERVE_BALANCES": {"series_id": "WRESBAL", "name": "Reserve Balances with Federal Reserve Banks", "unit": "$ Billions", "frequency": "WEEKLY"},
    "FED_ON_RRP": {"series_id": "RRPONTSYD", "name": "Overnight Reverse Repurchase Agreements", "unit": "$ Billions", "frequency": "DAILY"},
}

# --- NY Fed series catalog (keyless) -----------------------------------------
NY_FED_SERIES: dict[str, dict] = {
    "SOFR": {"rate_type": "sofr", "name": "Secured Overnight Financing Rate", "unit": "%", "frequency": "DAILY"},
    "EFFR": {"rate_type": "effr", "name": "Effective Federal Funds Rate", "unit": "%", "frequency": "DAILY"},
}

# --- Provider routing: primary/fallback per canonical series -----------------
# fallback_equivalent=True means the fallback measures the same real-world
# concept (safe to substitute, e.g. two SOFR sources). False means the
# fallback is NOT analytically equivalent and must therefore never be
# silently substituted — the series is exposed as UNAVAILABLE instead
# (macro/series_router.py enforces this).
SERIES_REGISTRY: dict[str, dict] = {
    canonical_id: {
        "primary": {"provider": "FRED", "series_id": info["series_id"]},
        "fallback": None,
        "fallback_equivalent": False,
        "on_failure": "UNAVAILABLE",
    }
    for canonical_id, info in FRED_SERIES.items()
}
SERIES_REGISTRY["LIQUIDITY_SOFR"] = {
    "primary": {"provider": "NY_FED", "rate_type": "SOFR"},
    "fallback": {"provider": "FRED", "series_id": "SOFR"},
    "fallback_equivalent": True,  # FRED mirrors the same NY Fed SOFR print
    "on_failure": "USE_FALLBACK",
}
SERIES_REGISTRY["LIQUIDITY_EFFR"] = {
    "primary": {"provider": "NY_FED", "rate_type": "EFFR"},
    "fallback": {"provider": "FRED", "series_id": "EFFR"},
    "fallback_equivalent": True,
    "on_failure": "USE_FALLBACK",
}

# Providers evaluated for this sprint but not implemented — kept visible in
# the provenance table rather than silently absent. See macro/provenance.py.
PROVIDERS_NOT_IMPLEMENTED: dict[str, str] = {
    "ECB (SDW)": "Already used for the Rates section's Euro AAA curve; not yet routed into the new canonical series registry.",
    "US Treasury Fiscal Data": "Endpoint shape not verified this sprint (a probed endpoint 404'd); Rates already has a working Yahoo-based yield curve, so not required.",
    "BLS": "FRED mirrors BLS's CPI/employment series faithfully with one integration instead of two; a direct BLS integration would only matter for series FRED doesn't mirror.",
    "BEA": "Same reasoning as BLS — FRED mirrors BEA's GDP/PCE series (GDPC1, PCEPI).",
    "OECD": "Not evaluated this sprint.",
    "World Bank": "Not evaluated this sprint — annual-frequency international data, lower priority than the US high-frequency series implemented here.",
}

# --- Pillar direction thresholds ---------------------------------------------
# YoY % change bands used to label a pillar's direction. Documented, not a
# black box — same spirit as analysis/regime/common.py::state_5.
GROWTH_EXPANDING_YOY = 1.5
GROWTH_CONTRACTING_YOY = -0.5
INFLATION_HIGH_YOY = 3.0
INFLATION_LOW_YOY = 1.5
LIQUIDITY_TIGHTENING_BALANCE_SHEET_YOY = -3.0
LIQUIDITY_EXPANDING_BALANCE_SHEET_YOY = 3.0

# Critical series per pillar: if any of these is UNAVAILABLE, pillar
# confidence is capped at CRITICAL_SERIES_MISSING_CAP regardless of other
# components (macro/confidence.py).
PILLAR_CRITICAL_SERIES: dict[str, tuple[str, ...]] = {
    "GROWTH": ("US_PAYROLLS",),
    "INFLATION": ("US_CPI_HEADLINE",),
    "LIQUIDITY": ("LIQUIDITY_SOFR",),
}
CRITICAL_SERIES_MISSING_CAP = 40

# --- Confidence methodology weights (must sum to 1.0) ------------------------
CONFIDENCE_WEIGHTS: dict[str, float] = {
    "coverage": 0.30,
    "freshness": 0.25,
    "provider_degradation": 0.15,
    "internal_conflict": 0.15,
    "revision_risk": 0.05,
    "cross_asset_confirmation": 0.10,
}
CONFIDENCE_LABEL_BANDS: dict[str, int] = {
    "HIGH": 75,
    "MODERATE": 50,
    "LOW": 25,
    # below LOW -> "VERY LOW"
}

# --- Calendar ------------------------------------------------------------
# canonical release id -> which series it publishes + a documented importance
# rule (not inferred from market reaction). Scope is explicit: only the
# releases behind the series this workspace actually sources.
FRED_RELEASES: dict[str, dict] = {
    "EMPLOYMENT_SITUATION": {"name": "Employment Situation", "series": ("US_PAYROLLS", "US_UNEMPLOYMENT_RATE"), "country": "US", "pillar": "GROWTH"},
    "CPI": {"name": "Consumer Price Index", "series": ("US_CPI_HEADLINE", "US_CPI_CORE"), "country": "US", "pillar": "INFLATION"},
    "GDP": {"name": "Gross Domestic Product", "series": ("US_REAL_GDP",), "country": "US", "pillar": "GROWTH"},
    "PCE": {"name": "Personal Income and Outlays", "series": ("US_PCE_HEADLINE", "US_PCE_CORE"), "country": "US", "pillar": "INFLATION"},
    "INDUSTRIAL_PRODUCTION": {"name": "Industrial Production and Capacity Utilization", "series": ("US_INDUSTRIAL_PRODUCTION",), "country": "US", "pillar": "GROWTH"},
    "RETAIL_SALES": {"name": "Advance Monthly Sales for Retail and Food Services", "series": ("US_RETAIL_SALES",), "country": "US", "pillar": "GROWTH"},
}
RELEASE_IMPORTANCE: dict[str, str] = {
    "EMPLOYMENT_SITUATION": "HIGH",
    "CPI": "HIGH",
    "GDP": "HIGH",
    "PCE": "MEDIUM",
    "INDUSTRIAL_PRODUCTION": "MEDIUM",
    "RETAIL_SALES": "MEDIUM",
}
CALENDAR_SCOPE_NOTE = (
    "Limited to the releases this workspace sources from the US (CPI, Employment Situation, "
    "GDP, PCE, Retail Sales, Industrial Production) — not a complete global economic calendar."
)
