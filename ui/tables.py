import numpy as np
import pandas as pd
from config.theme import PANEL, TEXT, GREEN, RED

def style_market_table(table: pd.DataFrame):
    display = table.copy()
    if "Data" in display.columns:
        display["Data"] = pd.to_datetime(display["Data"]).dt.strftime("%d/%m/%Y")

    formatters = {
        "Ultimo": "{:,.4f}",
        "1D %": "{:+.2f}%",
        "1W %": "{:+.2f}%",
        "1M %": "{:+.2f}%",
        "3M %": "{:+.2f}%",
    }

    existing_formatters = {key: value for key, value in formatters.items() if key in display.columns}
    styled = display.style.format(existing_formatters, na_rep="N/D")

    change_columns = [column for column in ["1D %", "1W %", "1M %", "3M %"] if column in display.columns]
    if change_columns:
        styled = styled.map(
            lambda value: (
                f"color:{GREEN};font-weight:700"
                if isinstance(value, (int, float, np.floating)) and value >= 0
                else f"color:{RED};font-weight:700"
            ),
            subset=change_columns,
        )

    return styled.set_properties(
        **{
            "background-color": PANEL,
            "color": TEXT,
            "border-color": "#333",
        }
    )
