from analysis.cyclical.provenance import methodology_coverage


def test_id_is_explicitly_not_implemented():
    rows = {item.component: item for item in methodology_coverage()}
    assert rows["Investitore Disciplinato"].status == "NOT IMPLEMENTED"
