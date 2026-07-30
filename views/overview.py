from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from config.universe import EQUITY_INDICES, REGIME_UNIVERSE
from data.yahoo import download_close_batch
from core.metrics import build_market_table, normalized_frame
from charts.common import create_line_chart, create_bar_chart
from analysis.regime import build_market_regime
from views.regime import regime_color, render_market_regime
from ui.market_intelligence_panel import render_market_intelligence_panel


def _compute_reading(table: pd.DataFrame) -> dict[str, Any]:
    ranked = table.dropna(subset=["1D %"]).sort_values("1D %", ascending=False)
    leader = ranked.iloc[0] if not ranked.empty else None
    laggard = ranked.iloc[-1] if not ranked.empty else None
    indexed = table.set_index("Strumento")
    vix = indexed.loc["VIX"] if "VIX" in indexed.index else None
    positive = int((ranked["1D %"] > 0).sum()) if not ranked.empty else 0
    total = len(ranked)

    return {
        "leader": leader,
        "laggard": laggard,
        "vix": vix,
        "positive": positive,
        "total": total,
    }


_STATE_ORDINAL = {
    "STRONGLY POSITIVE": 2,
    "POSITIVE": 1,
    "NEUTRAL": 0,
    "NEGATIVE": -1,
    "STRONGLY NEGATIVE": -2,
}

# Internal pillar name -> plain-language investor label. These labels, and
# the sentences built from them below, are the ONLY things ever shown to the
# user — the pillar name itself, the per-horizon breakdown and every other
# model concept stay internal.
_ASSET_CLASS_LABELS = {
    "EQUITY": "equities",
    "RATES": "interest rates",
    "CREDIT": "credit",
    "MACRO": "commodities and the dollar",
    "VOLATILITY": "volatility",
}


def _pillar(layer, name: str):
    if layer is None:
        return None
    for pillar in layer.pillars:
        if pillar.name == name:
            return pillar
    return None


def _asset_class_read(regime_results: dict[str, Any], pillar_name: str) -> dict[str, float] | None:
    """
    Collapse the (internal) multi-horizon pillar states for one asset class
    into a single conviction score and a same-vs-earlier delta, without
    exposing which internal horizons were used.
    """

    ordered_values = []
    for key in ("STRATEGIC", "TACTICAL", "DAILY"):
        pillar = _pillar(regime_results.get(key), pillar_name)
        if pillar is not None:
            ordered_values.append(_STATE_ORDINAL.get(pillar.state, 0))

    if not ordered_values:
        return None

    return {
        "avg": sum(ordered_values) / len(ordered_values),
        "spread": max(ordered_values) - min(ordered_values),
        "trend": ordered_values[-1] - ordered_values[0] if len(ordered_values) >= 2 else 0,
    }


def _equity_sentence(read: dict[str, float]) -> str:
    if read["spread"] >= 3:
        if read["trend"] > 0:
            return (
                "Equity leadership looks like it is repairing after a rougher "
                "stretch, even though the broader trend has not fully caught "
                "up yet."
            )
        return (
            "Equity leadership is cracking after a strong run, even though "
            "the broader trend is not yet broken."
        )
    if read["avg"] >= 1.2:
        return "Equity markets are in a broad, well-supported uptrend."
    if read["avg"] >= 0.4:
        return "Equity markets are drifting higher without strong conviction behind the move."
    if read["avg"] <= -1.2:
        return "Equity markets are under clear, broadening pressure."
    if read["avg"] <= -0.4:
        return "Equity markets are soft, though not yet showing a disorderly decline."
    return "Equity markets are essentially rangebound, lacking a clear catalyst either way."


def _rates_sentence(read: dict[str, float]) -> str:
    if read["avg"] >= 1.2:
        return "Bond yields have fallen meaningfully, easing financial conditions for risk assets."
    if read["avg"] >= 0.4:
        return "Bond yields have drifted lower, a modest tailwind for equity valuations."
    if read["avg"] <= -1.2:
        return "Bond yields have risen sharply, tightening financial conditions and pressuring valuations."
    if read["avg"] <= -0.4:
        return "Bond yields have been creeping higher, a headwind worth watching for duration-sensitive names."
    return "Bond yields have been broadly stable, offering neither a tailwind nor a headwind."


def _credit_sentence(read: dict[str, float]) -> str:
    if read["avg"] >= 1.2:
        return "Credit spreads have tightened, confirming the risk-on tone visible in equities."
    if read["avg"] >= 0.4:
        return "Credit markets are modestly supportive of the equity move."
    if read["avg"] <= -1.2:
        return "Credit spreads have widened materially — fixed income is not fully endorsing the equity move."
    if read["avg"] <= -0.4:
        return "Credit markets are showing early signs of caution, a mild divergence from equities."
    return "Credit markets are quiet, offering no strong read either way."


def _macro_sentence(read: dict[str, float]) -> str:
    if read["avg"] >= 1.2:
        return (
            "Industrial commodities are outperforming gold while the dollar softens — a "
            "combination consistent with a reflationary, growth-friendly backdrop."
        )
    if read["avg"] >= 0.4:
        return "There are tentative signs of a growth-friendly commodity and currency mix."
    if read["avg"] <= -1.2:
        return (
            "Gold is outperforming industrial commodities while the dollar firms — a "
            "classic defensive, growth-scare combination."
        )
    if read["avg"] <= -0.4:
        return "Commodity and currency markets are leaning cautious."
    return "Commodity and currency markets are giving a neutral read."


def _volatility_sentence(read: dict[str, float]) -> str:
    if read["avg"] >= 1.2:
        return "Volatility remains historically contained, supporting risk-taking."
    if read["avg"] >= 0.4:
        return "Volatility is on the low side."
    if read["avg"] <= -1.2:
        return "Volatility has picked up sharply, signaling elevated investor anxiety."
    if read["avg"] <= -0.4:
        return "Volatility has been creeping higher."
    return "Volatility is unremarkable."


_ASSET_CLASS_SENTENCE_BUILDERS = {
    "EQUITY": _equity_sentence,
    "RATES": _rates_sentence,
    "CREDIT": _credit_sentence,
    "MACRO": _macro_sentence,
    "VOLATILITY": _volatility_sentence,
}

_CONNECTORS = ["", "Meanwhile, ", "At the same time, ", "In parallel, "]


def _implication(regime_results: dict[str, Any], reading: dict[str, Any]) -> str:
    tactical = regime_results.get("TACTICAL")
    diagnosis = tactical.diagnosis.upper() if tactical else ""
    positive, total = reading["positive"], reading["total"]
    breadth_negative = bool(total) and positive <= total * 0.3
    breadth_positive = bool(total) and positive >= total * 0.7

    if "DETERIORAT" in diagnosis or (breadth_negative and "IMPROV" not in diagnosis):
        return (
            "A portfolio manager would likely lean toward defensive or quality "
            "positioning here, and hold off on adding cyclical risk until the "
            "picture above stabilizes."
        )
    if "IMPROV" in diagnosis and breadth_positive:
        return (
            "A portfolio manager could reasonably maintain, or selectively add "
            "to, existing risk exposure while this alignment holds."
        )
    return (
        "A portfolio manager would likely favor selective, idea-specific "
        "exposure over broad directional bets until the picture above "
        "clarifies."
    )


def _fallback_briefing_text(reading: dict[str, Any], regime_results: dict[str, Any]) -> str:
    """
    Deterministic stand-in for generate_daily_briefing when the LLM is
    unavailable. Ranks asset classes by conviction and only narrates the
    two to four that stand out, in plain investment language — the
    underlying multi-horizon pillar model is never named or exposed.
    """

    if not regime_results:
        return (
            "I don't have a reliable cross-asset read at the moment, so I'd "
            "treat any single day's price action with extra caution until "
            "data quality improves."
        )

    reads = {
        name: _asset_class_read(regime_results, name)
        for name in _ASSET_CLASS_LABELS
    }
    reads = {name: read for name, read in reads.items() if read is not None}

    if not reads:
        return (
            "I don't have enough cross-asset data to build today's narrative "
            "with confidence."
        )

    ranked = sorted(reads.items(), key=lambda item: abs(item[1]["avg"]), reverse=True)
    themes = [(name, read) for name, read in ranked if abs(read["avg"]) >= 0.3][:4] or ranked[:2]

    narrative_sentences = []
    for index, (name, read) in enumerate(themes):
        sentence = _ASSET_CLASS_SENTENCE_BUILDERS[name](read)
        connector = _CONNECTORS[index % len(_CONNECTORS)]
        if connector:
            sentence = sentence[0].lower() + sentence[1:]
        narrative_sentences.append(connector + sentence)

    narrative = " ".join(narrative_sentences)

    weakest_two = sorted(reads.items(), key=lambda item: item[1]["avg"])[:2]
    risk_bits = []
    for name, read in weakest_two:
        label = _ASSET_CLASS_LABELS[name]
        if read["avg"] < 0:
            risk_bits.append(f"a further deterioration in {label}")
        else:
            risk_bits.append(f"a reversal in {label}")
    risks_text = (
        "Keep an eye on " + " and ".join(risk_bits) + " — either would call today's "
        "reading into question."
        if risk_bits
        else "No single asset class stands out as an immediate risk to this reading."
    )

    strongest = ranked[0][0] if ranked else None
    weakest = weakest_two[0][0] if weakest_two else None
    questions = []
    if strongest is not None:
        questions.append(f"Is the current strength in {_ASSET_CLASS_LABELS[strongest]} durable, or dependent on conditions elsewhere not deteriorating?")
    if weakest is not None and weakest != strongest:
        questions.append(f"Does the softness in {_ASSET_CLASS_LABELS[weakest]} confirm the broader picture, or is it an early warning being missed?")
    questions.append("Which asset class would need to shift for this interpretation to change?")
    questions_text = "\n".join(f"- {question}" for question in questions[:4])

    return (
        f"{narrative}\n\n"
        f"**Portfolio Implications**\n{_implication(regime_results, reading)}\n\n"
        f"**Key Risks**\n{risks_text}\n\n"
        f"**Questions Worth Investigating**\n{questions_text}"
    )


def _build_market_context(
    table: pd.DataFrame,
    reading: dict[str, Any],
    regime_results: dict[str, Any],
) -> dict[str, Any]:
    indexed = table.set_index("Strumento")
    index_rows = {}
    for name, row in indexed.iterrows():
        change = row["1D %"]
        index_rows[str(name)] = {
            "last": float(row["Ultimo"]),
            "change_1d_pct": None if pd.isna(change) else float(change),
        }

    regime_summary = {}
    for key, layer in regime_results.items():
        regime_summary[key] = {
            "title": layer.title,
            "horizon": layer.horizon,
            "diagnosis": layer.diagnosis,
            "previous_diagnosis": layer.previous_diagnosis,
            "score": layer.score,
            "previous_score": layer.previous_score,
            "confidence": round(layer.coverage, 2),
            "pillars": [
                {"name": pillar.name, "state": pillar.state, "details": pillar.details}
                for pillar in layer.pillars
            ],
        }

    return {
        "equity_indices": index_rows,
        "breadth": {"positive": reading["positive"], "total": reading["total"]},
        "regime": regime_summary,
    }


def _render_status_line(table: pd.DataFrame, tactical) -> None:
    parts: list[str] = []

    if tactical is not None:
        color = regime_color(tactical.diagnosis)
        parts.append(
            f"<span class='status-dot' style='background:{color}'></span>"
            f"<b>{tactical.title}</b>&nbsp;{tactical.diagnosis}"
            f"<span class='status-muted'> · {tactical.coverage:.0%} confidence</span>"
        )
    else:
        parts.append("<span class='status-muted'>Regime unavailable</span>")

    indexed = table.set_index("Strumento")
    for name in ["S&P 500", "NASDAQ", "VIX"]:
        if name in indexed.index:
            row = indexed.loc[name]
            css_class = "tick-up" if row["1D %"] >= 0 else "tick-down"
            parts.append(f"<span class='{css_class}'>{name} {row['1D %']:+.2f}%</span>")

    st.markdown(
        f"<div class='status-line'>{' &nbsp;·&nbsp; '.join(parts)}</div>",
        unsafe_allow_html=True,
    )


def render_global_overview() -> None:
    with st.spinner("Loading market data…"):
        close = download_close_batch(tuple(EQUITY_INDICES.values()), period="6mo")
        regime_close = download_close_batch(tuple(REGIME_UNIVERSE.values()), period="2y")

    table = build_market_table(close, EQUITY_INDICES)
    if table.empty:
        st.error("Yahoo Finance non ha restituito dati per gli indici.")
        return

    regime_results = build_market_regime(regime_close) if not regime_close.empty else {}
    reading = _compute_reading(table)
    tactical = regime_results.get("TACTICAL")

    _render_status_line(table, tactical)

    _, center, _ = st.columns([1, 5, 1])
    with center:
        market_context = _build_market_context(table, reading, regime_results)
        fallback_briefing = _fallback_briefing_text(reading, regime_results)
        render_market_intelligence_panel(market_context, fallback_briefing)

        st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)
        links = st.columns(3)
        pages = st.session_state.get("_pages", {})
        with links[0]:
            if "Macro & Rates" in pages:
                st.page_link(pages["Macro & Rates"], label="Macro & Rates", icon=":material/show_chart:")
        with links[1]:
            if "Opportunities" in pages:
                st.page_link(pages["Opportunities"], label="Opportunities", icon=":material/search:")
        with links[2]:
            if "Research Workspace" in pages:
                st.page_link(pages["Research Workspace"], label="Research Workspace", icon=":material/science:")

    with st.expander("Detailed market data & regime analytics", expanded=False):
        card_names = ["S&P 500", "NASDAQ", "FTSE MIB", "DAX", "NIKKEI 225", "VIX", "KOSPI"]
        indexed = table.set_index("Strumento")
        cols = st.columns(7)
        for col, name in zip(cols, card_names):
            if name not in indexed.index:
                col.metric(name, "N/D")
                continue
            row = indexed.loc[name]
            col.metric(name, f"{row['Ultimo']:,.2f}", f"{row['1D %']:+.2f}%")

        left, right = st.columns([2.1, 1])
        with left:
            st.markdown("<div class='terminal-subheader'>RELATIVE PERFORMANCE</div>", unsafe_allow_html=True)
            reverse = {ticker: name for name, ticker in EQUITY_INDICES.items()}
            renamed = close.rename(columns=reverse)
            defaults = [name for name in ["S&P 500", "NASDAQ", "EURO STOXX 50", "FTSE MIB", "DAX", "NIKKEI 225", "KOSPI"] if name in renamed.columns]
            selected = st.multiselect("Indici", options=list(renamed.columns), default=defaults, label_visibility="collapsed", key="overview_indices")
            if selected:
                st.plotly_chart(create_line_chart(normalized_frame(renamed[selected]), "GLOBAL EQUITY // BASE 100", "Base 100", 510), width="stretch")
        with right:
            st.markdown("<div class='terminal-subheader'>1D PERFORMANCE</div>", unsafe_allow_html=True)
            st.plotly_chart(create_bar_chart(table, "1D %", "LEADERS / LAGGARDS"), width="stretch")

        st.divider()
        render_market_regime(show_header=False)
