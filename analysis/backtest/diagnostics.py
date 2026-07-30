from __future__ import annotations
import pandas as pd
from analysis.trades.models import Trade


def build_trade_diagnostics(trades: list[Trade]) -> pd.DataFrame:
    rows = []
    for trade in trades:
        rows.append({
            "SIDE": trade.side,
            "ENTRY DATE": trade.entry_date,
            "EXIT DATE": trade.exit_date,
            "ENTRY RATING": trade.entry_rating,
            "QUARTERLY": trade.entry_quarterly,
            "MONTHLY": trade.entry_monthly,
            "WEEKLY PHASE": trade.entry_weekly_phase,
            "ENTRY CM": trade.entry_weekly_composite,
            "BARS": trade.bars_held,
            "SIZE": trade.size,
            "GROSS RETURN": trade.gross_return,
            "NET RETURN": trade.net_return,
            "PNL CONTRIBUTION": trade.net_return * trade.size,
            "EXIT REASON": trade.exit_reason,
        })
    return pd.DataFrame(rows)
