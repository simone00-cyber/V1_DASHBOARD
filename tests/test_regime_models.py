from analysis.regime import RegimeLayer, RegimePillar


def test_regime_pillar_constructor_and_coverage():
    pillar = RegimePillar("EQUITY", 1.0, "POSITIVE", "ok", 3, 4)
    assert pillar.name == "EQUITY"
    assert pillar.coverage == 0.75


def test_regime_layer_coverage():
    layer = RegimeLayer(
        "DAILY", "TODAY", "1D", "MIXED", 0.0, "MIXED", 0.0,
        [
            RegimePillar("EQUITY", 0, "NEUTRAL", "", 3, 3),
            RegimePillar("RATES", 0, "NEUTRAL", "", 0, 1),
        ],
    )
    assert layer.coverage == 0.75
