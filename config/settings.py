"""Configurazione applicativa centralizzata.

Le soglie del Market Regime sono parametri del modello proprietario della
Dashboard e non appartengono alla metodologia ciclica documentale.
"""
from __future__ import annotations

from pathlib import Path

APP_NAME = "Cyclical Global Macro Terminal"
TIMEZONE = "Europe/Rome"

CACHE_TTL_SECONDS = 600
SECURITY_CACHE_TTL_SECONDS = 900
YAHOO_BATCH_TIMEOUT_SECONDS = 15
YAHOO_SINGLE_TIMEOUT_SECONDS = 12
YAHOO_RETRY_COUNT = 2
YAHOO_RETRY_SLEEP_SECONDS = 0.35


LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_FILE = LOG_DIR / "terminal.log"

REGIME_SCORE_MIN = -2.0
REGIME_SCORE_MAX = 2.0
REGIME_STATE_THRESHOLDS = {
    "strong_positive": 1.20,
    "positive": 0.35,
    "negative": -0.35,
    "strong_negative": -1.20,
}

STRATEGIC_WEIGHTS = {
    "EQUITY": 1.35,
    "VOLATILITY": 1.00,
    "CREDIT": 1.30,
    "RATES": 0.90,
    "MACRO": 0.75,
}
TACTICAL_WEIGHTS = {
    "EQUITY": 1.30,
    "VOLATILITY": 1.10,
    "CREDIT": 1.35,
    "RATES": 0.85,
    "MACRO": 0.75,
}
DAILY_WEIGHTS = {
    "EQUITY": 1.40,
    "VOLATILITY": 1.25,
    "CREDIT": 1.25,
    "RATES": 0.65,
    "MACRO": 0.70,
}

TACTICAL_IMPROVING_DELTA = 0.35
TACTICAL_DETERIORATING_DELTA = -0.35
DAILY_RISK_ON_THRESHOLD = 0.45
DAILY_RISK_OFF_THRESHOLD = -0.45
