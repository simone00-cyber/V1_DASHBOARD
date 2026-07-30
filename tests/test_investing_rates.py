from __future__ import annotations

from data.investing_rates import parse_investing_quote


def test_parse_investing_yield_quote() -> None:
    html = '''
    <div data-test="instrument-price-last">3.1728</div>
    <span data-test="instrument-price-change">-0.0387</span>
    '''
    value, change = parse_investing_quote(html)
    assert value == 3.1728
    assert change == -0.0387


def test_parse_investing_european_number() -> None:
    html = '''
    <div data-test="instrument-price-last">3,1728</div>
    <span data-test="instrument-price-change">+0,0120</span>
    '''
    value, change = parse_investing_quote(html)
    assert value == 3.1728
    assert change == 0.012


def test_parse_spread_converts_percentage_points_to_basis_points() -> None:
    html = '<div data-test="instrument-price-last">1.087</div>'
    value, _ = parse_investing_quote(html, is_spread=True)
    assert value == 108.7
