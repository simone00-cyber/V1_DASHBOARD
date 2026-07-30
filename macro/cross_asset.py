"""Cross-Asset Confirmation: does each asset class confirm or diverge from
the prevailing macro-regime read?

Equity/Credit reuse `analysis/regime/*` (untouched — same TACTICAL layer
Command Center's status line already surfaces). FX/Commodities/Crypto are
simple, transparent 1-month return reads computed directly from
already-fetched close-price data (no new fetch dependency, no proxy dressed
up as something it isn't).
"""

from __future__ import annotations

import pandas as pd

from core.metrics import ratio_series
from macro.models import CrossAssetItem, CrossAssetSnapshot


def _pillar_state(regime_results: dict, layer_key: str, pillar_name: str) -> str | None:
    layer = regime_results.get(layer_key)
    if layer is None:
        return None
    for pillar in layer.pillars:
        if pillar.name == pillar_name:
            return pillar.state
    return None


def _regime_polarity(regime_results: dict) -> int:
    """+1 risk-on bias, -1 risk-off bias, 0 neutral/unavailable — from the
    TACTICAL layer's score, the same layer Command Center's status line
    already surfaces."""
    tactical = regime_results.get("TACTICAL")
    if tactical is None:
        return 0
    if tactical.score > 0.15:
        return 1
    if tactical.score < -0.15:
        return -1
    return 0


def _state_confirmation(state: str | None, polarity: int) -> bool | None:
    if state is None or polarity == 0:
        return None
    is_positive = "POSITIVE" in state
    is_negative = "NEGATIVE" in state
    if not is_positive and not is_negative:
        return None
    return is_positive == (polarity > 0)


def _value_confirmation(value: float | None, polarity: int) -> bool | None:
    if value is None or polarity == 0 or value == 0:
        return None
    return (value > 0) == (polarity > 0)


def _return_1m(close: pd.DataFrame, ticker: str) -> float | None:
    if ticker not in close.columns:
        return None
    series = close[ticker].dropna()
    if len(series) <= 21:
        return None
    return float((series.iloc[-1] / series.iloc[-22] - 1.0) * 100.0)


def _ratio_return_1m(close: pd.DataFrame, numerator: str, denominator: str) -> float | None:
    ratio = ratio_series(close, numerator, denominator).dropna()
    if len(ratio) <= 21:
        return None
    return float((ratio.iloc[-1] / ratio.iloc[-22] - 1.0) * 100.0)


def build_cross_asset_snapshot(regime_results: dict, close: pd.DataFrame) -> CrossAssetSnapshot:
    polarity = _regime_polarity(regime_results)
    items: list[CrossAssetItem] = []

    equity_state = _pillar_state(regime_results, "TACTICAL", "EQUITY")
    items.append(
        CrossAssetItem(
            asset_class="EQUITIES",
            verdict=equity_state or "UNKNOWN",
            what_changed=f"Equity tactical pillar: {equity_state}." if equity_state else "Equity regime pillar unavailable.",
            confirms_regime=_state_confirmation(equity_state, polarity),
        )
    )

    credit_state = _pillar_state(regime_results, "TACTICAL", "CREDIT")
    items.append(
        CrossAssetItem(
            asset_class="CREDIT",
            verdict=credit_state or "UNKNOWN",
            what_changed=f"Credit tactical pillar (HYG/LQD): {credit_state}." if credit_state else "Credit regime pillar unavailable.",
            confirms_regime=_state_confirmation(credit_state, polarity),
        )
    )

    dxy_1m = _return_1m(close, "DX-Y.NYB")
    items.append(
        CrossAssetItem(
            asset_class="FX (DXY)",
            verdict="N/A" if dxy_1m is None else ("DOLLAR STRENGTHENING" if dxy_1m > 0 else "DOLLAR WEAKENING" if dxy_1m < 0 else "FLAT"),
            what_changed=f"DXY {dxy_1m:+.1f}% over 1 month." if dxy_1m is not None else "DXY 1-month return unavailable.",
            # A weakening dollar is the risk-on-consistent direction here.
            confirms_regime=_value_confirmation(-dxy_1m if dxy_1m is not None else None, polarity),
        )
    )

    commodity_1m = _ratio_return_1m(close, "HG=F", "GC=F")
    items.append(
        CrossAssetItem(
            asset_class="COMMODITIES (Copper/Gold)",
            verdict="N/A" if commodity_1m is None else ("GROWTH-LEANING" if commodity_1m > 0 else "DEFENSIVE-LEANING" if commodity_1m < 0 else "FLAT"),
            what_changed=f"Copper/Gold ratio {commodity_1m:+.1f}% over 1 month." if commodity_1m is not None else "Copper/Gold ratio unavailable.",
            confirms_regime=_value_confirmation(commodity_1m, polarity),
        )
    )

    crypto_1m = _return_1m(close, "BTC-USD")
    items.append(
        CrossAssetItem(
            asset_class="CRYPTO (Bitcoin)",
            verdict="N/A" if crypto_1m is None else ("RISK-SEEKING" if crypto_1m > 0 else "RISK-AVERSE" if crypto_1m < 0 else "FLAT"),
            what_changed=f"Bitcoin {crypto_1m:+.1f}% over 1 month." if crypto_1m is not None else "Bitcoin 1-month return unavailable.",
            confirms_regime=_value_confirmation(crypto_1m, polarity),
        )
    )

    confirmations = [item.confirms_regime for item in items if item.confirms_regime is not None]
    agreement_ratio = (sum(1 for c in confirmations if c) / len(confirmations)) if confirmations else None

    return CrossAssetSnapshot(items=tuple(items), agreement_ratio=agreement_ratio)
