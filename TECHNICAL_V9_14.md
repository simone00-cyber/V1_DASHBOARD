# Technical Analysis v9.14

## Clean support and resistance zones

The price chart now renders support and resistance exclusively as highlighted horizontal zones:

- support zones use a visible green fill;
- resistance zones use a visible red fill;
- the nearest zone is more prominent;
- secondary zones use lower opacity;
- no support/resistance labels, prices, state names or strength scores are drawn over the candles;
- descriptive information remains in the side panel.

This keeps the chart visually clean while preserving the full dynamic-level logic, including broken and flipped levels, in the analysis engine and side diagnostics.
