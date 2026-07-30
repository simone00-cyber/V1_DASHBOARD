from __future__ import annotations

import warnings

import pandas as pd

from data.providers.common import clean_numeric, parse_tabular_series


def test_clean_numeric_european_format() -> None:
    assert clean_numeric("1.234,56") == 1234.56
    assert clean_numeric("3,1728%") == 3.1728


def test_parse_iso_csv_without_format_warning() -> None:
    text = "TIME_PERIOD,OBS_VALUE\n2026-07-23,2.50\n2026-07-24,2.55\n"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        series = parse_tabular_series(text)
    assert len(series) == 2
    assert series.iloc[-1] == 2.55
    assert not any("Could not infer format" in str(item.message) for item in caught)


def test_parse_german_date_csv() -> None:
    text = "Date;Yield\n23.07.2026;2,50\n24.07.2026;2,55\n"
    series = parse_tabular_series(text)
    assert isinstance(series.index, pd.DatetimeIndex)
    assert series.iloc[-1] == 2.55

from data.providers.marketwatch_rates import parse_marketwatch_quote


def test_parse_marketwatch_bg_quote() -> None:
    html = '''
    <bg-quote class="value">3.182</bg-quote>
    <bg-quote class="change--point--q">0.010</bg-quote>
    '''
    value, change = parse_marketwatch_quote(html)
    assert value == 3.182
    assert change == 0.010


def test_ecb_country_long_term_10y_parser_contract(monkeypatch):
    from data.providers import official_rates

    csv = "TIME_PERIOD,OBS_VALUE\n2026-06,3.90\n2026-07,3.98\n"

    class Response:
        text = csv
        def raise_for_status(self):
            return None

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(official_rates, "build_http_session", lambda: Session())
    series = official_rates.fetch_ecb_country_long_term_10y("IT")
    assert len(series) == 2
    assert float(series.iloc[-1]) == 3.98
