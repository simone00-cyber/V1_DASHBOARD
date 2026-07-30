from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.regime.models import RegimeLayer, RegimePillar
from macro.cross_asset import build_cross_asset_snapshot


def _pillar(name: str, state: str) -> RegimePillar:
    return RegimePillar(name=name, score=0.0, state=state, details="", available_inputs=3, expected_inputs=3)


def _regime_results(tactical_score: float, equity_state: str, credit_state: str) -> dict:
    tactical = RegimeLayer(
        key="TACTICAL", title="Tactical", horizon="n/a", diagnosis="MIXED", score=tactical_score,
        previous_diagnosis="MIXED", previous_score=0.0,
        pillars=[_pillar("EQUITY", equity_state), _pillar("CREDIT", credit_state)],
    )
    return {"TACTICAL": tactical}


def _close_with_trend(tickers_and_returns: dict[str, float], periods: int = 40) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=periods, freq="B")
    data = {}
    for ticker, total_return in tickers_and_returns.items():
        daily = (1 + total_return) ** (1 / (periods - 1))
        data[ticker] = 100.0 * daily ** np.arange(periods)
    return pd.DataFrame(data, index=idx)


def test_risk_on_regime_with_confirming_assets():
    regime_results = _regime_results(tactical_score=1.0, equity_state="POSITIVE", credit_state="POSITIVE")
    close = _close_with_trend({"DX-Y.NYB": -0.05, "HG=F": 0.10, "GC=F": 0.0, "BTC-USD": 0.10})

    snapshot = build_cross_asset_snapshot(regime_results, close)

    by_class = {item.asset_class: item for item in snapshot.items}
    assert by_class["EQUITIES"].confirms_regime is True
    assert by_class["CREDIT"].confirms_regime is True
    assert by_class["FX (DXY)"].confirms_regime is True  # dollar weakening confirms risk-on
    assert by_class["CRYPTO (Bitcoin)"].confirms_regime is True
    assert snapshot.agreement_ratio == 1.0


def test_neutral_regime_score_yields_no_confirmation_calls():
    regime_results = _regime_results(tactical_score=0.05, equity_state="NEUTRAL", credit_state="NEUTRAL")
    close = _close_with_trend({"DX-Y.NYB": 0.02, "HG=F": 0.01, "GC=F": 0.0, "BTC-USD": -0.02})

    snapshot = build_cross_asset_snapshot(regime_results, close)

    assert all(item.confirms_regime is None for item in snapshot.items)
    assert snapshot.agreement_ratio is None


def test_missing_ticker_data_is_reported_as_unavailable_not_fabricated():
    regime_results = _regime_results(tactical_score=1.0, equity_state="POSITIVE", credit_state="POSITIVE")
    close = pd.DataFrame(index=pd.date_range("2026-01-01", periods=5, freq="B"))  # no columns at all

    snapshot = build_cross_asset_snapshot(regime_results, close)

    fx_item = next(item for item in snapshot.items if item.asset_class.startswith("FX"))
    assert fx_item.verdict == "N/A"
    assert "unavailable" in fx_item.what_changed.lower()
    assert fx_item.confirms_regime is None


def test_diverging_asset_is_reported_as_diverges():
    # Risk-on regime, but the dollar is strengthening (a divergence).
    regime_results = _regime_results(tactical_score=1.0, equity_state="POSITIVE", credit_state="POSITIVE")
    close = _close_with_trend({"DX-Y.NYB": 0.08, "HG=F": 0.10, "GC=F": 0.0, "BTC-USD": 0.10})

    snapshot = build_cross_asset_snapshot(regime_results, close)

    fx_item = next(item for item in snapshot.items if item.asset_class.startswith("FX"))
    assert fx_item.confirms_regime is False
