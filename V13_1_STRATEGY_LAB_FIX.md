# V13.1 Strategy Lab

This build makes the two backtesting engines explicit and independently selectable:

- Technical Strategy Lab: universal technical rule builder, execution and risk controls, trade explorer, parameter search, walk-forward analysis, Monte Carlo and complete report export.
- Cyclical Strategy Lab: documented public cyclical matrix, configurable execution policy, complete strategy definition, trade inspector, Monte Carlo robustness, audit, research diagnostics and matrix explorer.

The main Strategy Lab header now displays `RESEARCH & BACKTESTING LAB // V13.1` so the active build can be verified immediately.

The heterogeneous metric tables are normalized before Streamlit rendering to prevent PyArrow serialization failures.
