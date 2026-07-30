from __future__ import annotations
from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True)
class ResearchReport:
    enriched_trades: pd.DataFrame
    setup_summary: pd.DataFrame
    composite_summary: pd.DataFrame
    holding_summary: pd.DataFrame
    heatmap_average: pd.DataFrame
    heatmap_win_rate: pd.DataFrame
    heatmap_count: pd.DataFrame
    hypotheses: pd.DataFrame
    drawdown_episodes: pd.DataFrame
    drawdown_trades: pd.DataFrame
    loss_attribution_setup: pd.DataFrame
    loss_attribution_monthly: pd.DataFrame
    loss_attribution_rating: pd.DataFrame
    loss_attribution_composite: pd.DataFrame
