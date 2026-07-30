# Global Macro v10.2

## Rates architecture

- US 10Y and the complete US Treasury curve remain the primary global rates reference.
- Bund 10Y and Italy 10Y are loaded from homogeneous Investing.com sovereign-yield pages.
- The official Deutsche Bundesbank Bund 10Y series is retained as fallback.
- BTP-Bund and US-Germany 10Y differentials are calculated from matching 10-year yields.
- The direct Investing.com BTP-Bund quote is used only if one of the two sovereign legs is unavailable.
- ETF and futures prices are never used as substitutes for sovereign yields.

## Page structure

1. Global rates monitor: US 10Y, Bund 10Y, BTP-Bund and US-Germany differential.
2. Deterministic rates interpretation based on the latest changes.
3. US Treasury curve as the main curve chart.
4. European 10Y sovereign snapshot: Germany and Italy.
5. Official ECB AAA euro-area yield curve.
6. Live financial conditions: DXY, VIX, Brent and Gold.

All unavailable data are displayed as N/D rather than estimated or fabricated.
