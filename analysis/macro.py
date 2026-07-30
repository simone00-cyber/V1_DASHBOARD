from typing import List
import pandas as pd
from core.metrics import latest_change_bp, ratio_series, safe_pct_change

def build_macro_comment(
    rates: pd.DataFrame,
    fx_table: pd.DataFrame,
    commodity_table: pd.DataFrame,
    credit_close: pd.DataFrame,
) -> str:
    sentences: List[str] = []

    if "US 10Y" in rates.columns and len(rates["US 10Y"].dropna()) >= 2:
        s = rates["US 10Y"].dropna()
        change_bp = latest_change_bp(s)
        direction = "in aumento" if change_bp > 0 else "in calo"
        sentences.append(
            f"Il Treasury decennale è {direction} di {abs(change_bp):.1f} punti base nell'ultima seduta, "
            f"con rendimento a {float(s.iloc[-1]):.2f}%."
        )

    dxy = fx_table.loc[fx_table["Strumento"] == "DXY"] if not fx_table.empty else pd.DataFrame()
    if not dxy.empty and pd.notna(dxy.iloc[0]["1M %"]):
        value = float(dxy.iloc[0]["1M %"])
        sentences.append(
            f"Il dollaro mostra una variazione mensile del {value:+.2f}%, "
            + ("segnalando condizioni finanziarie più restrittive." if value > 0 else "riducendo parzialmente la pressione sulle condizioni finanziarie globali.")
        )

    oil = commodity_table.loc[commodity_table["Strumento"] == "WTI"] if not commodity_table.empty else pd.DataFrame()
    copper = commodity_table.loc[commodity_table["Strumento"] == "COPPER"] if not commodity_table.empty else pd.DataFrame()
    if not oil.empty and pd.notna(oil.iloc[0]["1M %"]):
        sentences.append(f"Il WTI registra una performance mensile del {float(oil.iloc[0]['1M %']):+.2f}%.")
    if not copper.empty and pd.notna(copper.iloc[0]["1M %"]):
        sentences.append(f"Il rame, indicatore ciclico industriale, varia del {float(copper.iloc[0]['1M %']):+.2f}% su un mese.")

    hy_ratio = ratio_series(credit_close, "HYG", "LQD")
    if len(hy_ratio) > 21:
        change = safe_pct_change(hy_ratio, 21)
        sentences.append(
            "Il rapporto High Yield/Investment Grade è "
            + (f"in miglioramento del {change:+.2f}% su un mese, coerente con propensione al rischio." if change > 0 else f"in deterioramento del {change:+.2f}% su un mese, coerente con maggiore prudenza sul credito.")
        )

    if not sentences:
        return "Il quadro macro non è determinabile perché alcune serie Yahoo Finance non sono disponibili."

    return " ".join(sentences)
