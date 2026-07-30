"""Fundamental engine thresholds and modeling assumptions.

Every number the fundamental engine relies on beyond a raw provider field is
named here, so it can be reviewed/tuned in one place and cited by
`fundamentals/provenance.py`. Nothing analytical is hardcoded inline.
"""
from __future__ import annotations

# --- Data sufficiency -------------------------------------------------------

MIN_ANNUAL_PERIODS_FOR_TREND = 2
MIN_STATEMENT_FIELDS_REQUIRED = ("revenue", "net_income")

# --- Valuation: Gordon-growth (dividend/earnings-discount-model) form -------
# Fair multiple = 1 / (required_return - growth). Applied to normalized
# EPS (earnings-power value) and to FCF per share (FCF-power value).

REQUIRED_RETURN = 0.09  # long-run equity required return assumption

EARNINGS_GROWTH_BEAR = 0.01
EARNINGS_GROWTH_BASE = 0.03
EARNINGS_GROWTH_BULL = 0.05

# FCF "base" growth is anchored to the company's own historical FCF CAGR,
# clamped to this range, then bear/bull are a fixed spread around it.
FCF_GROWTH_MIN = -0.02
FCF_GROWTH_MAX = 0.12
FCF_GROWTH_SPREAD = 0.03

# A Gordon-growth multiple is undefined/explosive as growth approaches the
# required return; refuse to compute above this ceiling instead of returning
# a meaningless huge number.
MAX_USABLE_GROWTH = REQUIRED_RETURN - 0.01

# --- Valuation bands ---------------------------------------------------------

MARGIN_OF_SAFETY_UNDERVALUED = 0.15   # >= +15% => Undervalued
MARGIN_OF_SAFETY_OVERVALUED = -0.15   # <= -15% => Overvalued

# --- Quality axis scoring thresholds (0-100 scores) --------------------------

CURRENT_RATIO_STRONG = 2.0
CURRENT_RATIO_ADEQUATE = 1.0
DEBT_TO_EQUITY_STRONG = 0.5
DEBT_TO_EQUITY_WEAK = 2.0
INTEREST_COVERAGE_STRONG = 8.0
INTEREST_COVERAGE_WEAK = 2.0

ROE_EXCELLENT = 0.20
ROE_WEAK = 0.05
NET_MARGIN_EXCELLENT = 0.15
NET_MARGIN_WEAK = 0.02
GROSS_MARGIN_EXCELLENT = 0.40
GROSS_MARGIN_WEAK = 0.15

# Shared by both revenue-growth and EPS-growth scoring — a single documented
# growth-quality bar rather than a separate threshold per metric.
REVENUE_GROWTH_STRONG = 0.10
REVENUE_GROWTH_WEAK = 0.0

# --- Overall Fundamental Rating ----------------------------------------------
# Overall score is the unweighted mean of the 5 quality axes that could be
# computed (missing axes are excluded, never treated as zero).

RATING_BAND_EXCELLENT = 80
RATING_BAND_GOOD = 65
RATING_BAND_FAIR = 45
RATING_BAND_WEAK = 30
# below RATING_BAND_WEAK => Poor
