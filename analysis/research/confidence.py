from __future__ import annotations


def confidence_label(sample_size: int) -> str:
    """Simple sample-size label. This is a research convention, not a source rule."""
    if sample_size >= 100:
        return "HIGH"
    if sample_size >= 30:
        return "MEDIUM"
    return "LOW"


def research_score(sample_size: int, expectancy: float, profit_factor: float) -> int:
    """Transparent 1-5 descriptive score, not a trading signal."""
    score = 1
    if sample_size >= 10:
        score += 1
    if sample_size >= 30:
        score += 1
    if expectancy > 0:
        score += 1
    if profit_factor > 1.25:
        score += 1
    return min(score, 5)
