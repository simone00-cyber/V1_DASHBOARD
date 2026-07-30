from __future__ import annotations

import re
from typing import Any

import streamlit as st


def _key_part(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "_", text)
    return text.strip("_") or "all"


def render_plotly(
    figure: Any,
    *,
    page: str,
    chart: str,
    ticker: str = "",
    timeframe: str = "",
    context: str = "",
    width: str = "stretch",
    **kwargs: Any,
) -> None:
    """Render a Plotly chart with a stable, explicit Streamlit element key."""
    key = "plotly__" + "__".join(
        _key_part(part)
        for part in (page, chart, ticker, timeframe, context)
    )
    st.plotly_chart(figure, width=width, key=key, **kwargs)
