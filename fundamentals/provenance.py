"""Methodological provenance for the Fundamental Analysis engine.

Follows the exact convention of `analysis/cyclical/provenance.py`: every
component is tagged with where it actually comes from, so nothing is
presented as more rigorous than it is. Unlike the Cyclical engine (which
replicates a published third-party formula), the fundamental rating and
valuation models here are this software's own construction — that is stated
plainly rather than implied.
"""

from fundamentals.models import MethodologyStatus


def methodology_coverage() -> tuple[MethodologyStatus, ...]:
    return (
        MethodologyStatus(
            component="Revenue, margins, growth, liquidity, leverage, per-share metrics",
            status="DERIVED METRIC",
            source="Yahoo Finance (yfinance) income statement / balance sheet / cash flow statement",
            note="Computed directly from the statement line items Yahoo publishes. A line item Yahoo does not "
            "publish is left blank — never estimated or defaulted.",
        ),
        MethodologyStatus(
            component="Valuation multiples (P/E, EV/EBITDA, P/S, P/B, PEG, dividend yield)",
            status="DIRECT FROM PROVIDER",
            source="Yahoo Finance (yfinance) quote summary (`Ticker.info`)",
            note="Passed through unmodified. Yahoo's analyst recommendation/target-price fields are never read.",
        ),
        MethodologyStatus(
            component="Business Quality / Financial Strength / Growth Quality / Profitability / Capital Allocation scores",
            status="DERIVED MODEL",
            source="fundamentals/quality.py",
            note="Each 0-100 score is a transparent scaling of already-computed metrics against named thresholds "
            "in fundamentals/config.py — not a published third-party methodology. An axis is left unscored, "
            "with a stated reason, when its inputs are unavailable.",
        ),
        MethodologyStatus(
            component="Bear / Base / Bull fair value",
            status="DERIVED MODEL",
            source="fundamentals/valuation.py — Gordon-growth earnings-power and FCF-power methods",
            note="A declared, sector-agnostic heuristic (fair multiple = 1 / (required return - growth)), not a "
            "sector-calibrated model — Yahoo Finance alone does not provide a reliable sector P/E baseline "
            "without a paid data provider. Assumptions actually used are always shown alongside the result.",
        ),
        MethodologyStatus(
            component="Overall Fundamental Rating and Buy/Hold/Sell recommendation",
            status="DERIVED MODEL",
            source="fundamentals/rating.py",
            note="Overall score is the unweighted mean of the quality axes that could be computed. The "
            "recommendation is one small, fully-documented lookup over (rating band, valuation band) — no "
            "hidden weighting, no analyst input.",
        ),
        MethodologyStatus(
            component="AI Fundamental Report narrative (improved/deteriorated/strengths/weaknesses/risks/thesis)",
            status="DERIVED MODEL",
            source="fundamentals/narrative.py",
            note="Deterministic sentence templates over already-computed numbers — no LLM call is involved at "
            "any point in this narrative. Every sentence cites the exact figures it is based on.",
        ),
        MethodologyStatus(
            component="Sector-relative valuation benchmarking",
            status="NOT AVAILABLE",
            source="Would require a paid fundamentals provider with sector index constituents/multiples",
            note="Not implemented in this iteration — yfinance does not reliably expose sector-level valuation "
            "baselines.",
        ),
    )
