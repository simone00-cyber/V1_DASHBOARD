# Technical Analysis Lab v9.11

## Changes

- Added an explicit global Yahoo Finance security search at the top of the page.
- Search accepts one or more symbols separated by commas, for example `TSLA, ENI.MI, ASML.AS, BTC-USD`.
- Symbols are validated before being added to the active external-security set.
- Searched securities are available in the screener, Security Lab and Pattern Monitor.
- Added a removable external-security selector used only to manage searched symbols.
- Added a centralized `ui.plotly.render_plotly` renderer with deterministic explicit Streamlit keys.
- All Technical Analysis Lab charts now use unique keys based on page, chart type, ticker, timeframe and context.
- Fixed `StreamlitDuplicateElementId` when the same price/RSI chart appeared in multiple tabs.
