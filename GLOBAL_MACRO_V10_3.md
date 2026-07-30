# Global Macro v10.3 — Provider Refactor

The macro data layer was rebuilt around normalized providers:

- `data/providers/yahoo_macro.py`: intraday market closes.
- `data/providers/official_rates.py`: Bundesbank and ECB official series.
- `data/providers/common.py`: HTTP retries, deterministic date parsing, numeric normalization.
- `data/macro_live.py`: orchestration and spread calculations only.

The pandas date-format warning is removed by explicit multi-format parsing. No remote HTML/CSV parsing is performed in the Streamlit view.
