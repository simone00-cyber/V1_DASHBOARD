"""Methodological provenance for the macro analytics package. Same coverage-
table convention as `fundamentals/provenance.py` and
`analysis/cyclical/provenance.py` — every component is tagged with where it
actually comes from, so nothing is presented as more rigorous than it is."""

from macro import config
from macro.models import MethodologyStatus


def methodology_coverage() -> tuple[MethodologyStatus, ...]:
    rows = [
        MethodologyStatus(
            component="Growth (Payrolls, Industrial Production, Retail Sales, Real GDP, Leading Index)",
            status="DIRECT FROM PROVIDER",
            source="FRED (St. Louis Fed), mirroring BLS/BEA",
            note="Passed through unmodified; YoY/MoM deltas are the only derived arithmetic.",
        ),
        MethodologyStatus(
            component="ISM Manufacturing PMI",
            status="NOT AVAILABLE",
            source="ISM (proprietary)",
            note="Not freely distributed anywhere; the Growth pillar uses hard activity data instead.",
        ),
        MethodologyStatus(
            component="Inflation (CPI, Core CPI, PCE, Core PCE, 5Y/10Y breakeven)",
            status="DIRECT FROM PROVIDER",
            source="FRED (St. Louis Fed), mirroring BLS/BEA/Treasury (TIPS breakevens)",
            note="Passed through unmodified.",
        ),
        MethodologyStatus(
            component="Liquidity — SOFR / EFFR",
            status="DIRECT FROM PROVIDER",
            source="New York Fed Markets API (no key required)",
            note="Same-day official reference rates.",
        ),
        MethodologyStatus(
            component="Liquidity — Fed balance sheet, reserve balances, ON RRP",
            status="DIRECT FROM PROVIDER",
            source="FRED (St. Louis Fed), mirroring the Federal Reserve H.4.1/H.6 releases",
            note="Passed through unmodified.",
        ),
        MethodologyStatus(
            component="Growth / Inflation / Liquidity pillar direction labels",
            status="DERIVED MODEL",
            source="macro/growth.py, macro/inflation.py, macro/liquidity.py",
            note="A transparent YoY-threshold rule over already-fetched values (thresholds named in macro/config.py) — not a published third-party methodology.",
        ),
        MethodologyStatus(
            component="Confidence score (evidence quality)",
            status="DERIVED MODEL",
            source="macro/confidence.py",
            note="A documented, weighted combination of coverage/freshness/provider-degradation/internal-conflict/revision-risk/cross-asset-confirmation — never a directional signal.",
        ),
        MethodologyStatus(
            component="Cross-Asset Confirmation — Equities/Credit",
            status="DERIVED METRIC",
            source="analysis/regime/* (unchanged) tactical pillar states",
            note="Reused as-is from the existing regime engine, not recomputed.",
        ),
        MethodologyStatus(
            component="Cross-Asset Confirmation — FX/Commodities/Crypto",
            status="DERIVED METRIC",
            source="macro/cross_asset.py — 1-month return over already-fetched close prices",
            note="A simple, transparent momentum read, not a proprietary indicator.",
        ),
        MethodologyStatus(
            component="Upcoming Macro Releases",
            status="DIRECT FROM PROVIDER",
            source="FRED release calendar (mirrors BLS/BEA)",
            note=config.CALENDAR_SCOPE_NOTE,
        ),
    ]
    for provider, reason in config.PROVIDERS_NOT_IMPLEMENTED.items():
        rows.append(
            MethodologyStatus(component=f"Provider: {provider}", status="NOT IMPLEMENTED", source=provider, note=reason)
        )
    return tuple(rows)
