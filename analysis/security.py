from typing import Dict, List

from caruso_analysis import TimeframeResult
from config.universe import TIMEFRAME_LABELS
from analysis.security_signal import TacticalSignalState
from analysis.cyclical.models import CycleState, HierarchyAssessment


def direction_word(direction: str) -> str:
    return {"UP": "crescente", "DOWN": "decrescente", "FLAT": "laterale"}.get(
        direction, direction.lower()
    )


def describe_timeframe(label: str, result: TimeframeResult, state: CycleState) -> str:
    movement = result.composite - result.previous_composite
    magnitude = abs(movement)

    if magnitude >= 20:
        pace = "con una variazione marcata"
    elif magnitude >= 8:
        pace = "con una variazione significativa"
    elif magnitude >= 2:
        pace = "con una variazione moderata"
    else:
        pace = "con una variazione contenuta"

    if result.composite >= 50:
        zone = "Il momentum è in area di eccesso positivo; l'eccesso non costituisce da solo un segnale di vendita."
    elif result.composite <= -50:
        zone = "Il momentum è in area di eccesso negativo; l'ipervenduto non equivale automaticamente a un acquisto."
    elif result.composite > 0:
        zone = "Il Composite Momentum resta nella metà positiva della scala."
    else:
        zone = "Il Composite Momentum resta nella metà negativa della scala."

    return (
        f"Sul timeframe **{label.lower()}**, il Composite Momentum quota **{result.composite:.1f}**, "
        f"rispetto a **{result.previous_composite:.1f}** della rilevazione precedente. "
        f"La pendenza è **{direction_word(result.direction)}**, {pace}. "
        f"La posizione ciclica documentale è **{state.phase}** ed è attiva da "
        f"**{state.state_age} periodi** (dal {state.phase_start.strftime('%d/%m/%Y')}). "
        f"{zone} La lettura del flesso è **{result.turn.lower()}**."
    )


def build_security_report(
    ticker: str,
    summaries: Dict[str, TimeframeResult],
    signal_state: TacticalSignalState,
    cycle_states: Dict[str, CycleState],
    hierarchy: HierarchyAssessment,
) -> str:
    parts: List[str] = []
    yearly = summaries.get("YEARLY")

    if yearly:
        state = cycle_states["YEARLY"]
        parts.append(
            f"Il quadro strutturale di **{ticker.upper()}** presenta un Composite Momentum annuale "
            f"**{direction_word(yearly.direction)}**, in posizione ciclica **{state.phase}**, a "
            f"**{yearly.composite:.1f}**. L'annuale definisce il contesto di fondo e non costituisce "
            "autonomamente un timing operativo."
        )

    for key in ("QUARTERLY", "MONTHLY", "WEEKLY"):
        if key in summaries and key in cycle_states:
            parts.append(describe_timeframe(TIMEFRAME_LABELS[key], summaries[key], cycle_states[key]))

    parts.append(
        f"La gerarchia multi-timeframe è classificata come **{hierarchy.alignment.lower()}**. "
        f"La condizione tattica corrente è **{hierarchy.tactical_condition.lower()}**. "
        f"**Trigger documentale:** {hierarchy.documented_trigger}"
    )

    if signal_state.status == "WAITING FOR BULLISH TRIGGER":
        parts.append(
            "Il trimestrale e il mensile restano rialzisti, mentre il settimanale è in correzione. "
            "La configurazione è di attesa: il trigger BUY richiede una nuova svolta rialzista "
            "settimanale con i timeframe superiori ancora UP."
        )
    elif signal_state.status == "WAITING FOR BEARISH TRIGGER":
        parts.append(
            "Il trimestrale e il mensile restano ribassisti, mentre il settimanale è in rimbalzo. "
            "Il trigger SELL SHORT richiede una nuova svolta ribassista settimanale."
        )
    elif signal_state.status == "NEW SIGNAL":
        parts.append(
            f"L'ultima barra settimanale ha generato un nuovo evento della matrice pubblicata: "
            f"**{signal_state.latest_event}**, rating **{'●' * signal_state.rating}**."
        )
    elif signal_state.status == "RISK REDUCTION / TAKE PROFIT":
        parts.append(
            "La matrice pubblicata assegna all'ultima barra una indicazione di "
            "**TAKE PROFIT / riduzione del rischio**."
        )
    elif signal_state.current_position in {"LONG", "SHORT"}:
        parts.append(
            f"Lo stato tattico derivato resta **{signal_state.position_label}**. Non è comparso "
            "un nuovo evento nell'ultima barra settimanale."
        )
    else:
        parts.append("Non è presente un nuovo evento della matrice sull'ultima barra settimanale.")

    parts.append(
        "L'Investitore Disciplinato non è calcolato: la formula proprietaria dei livelli "
        "Long/Neutral/Short non è pubblicata nei materiali disponibili."
    )
    return "\n\n".join(parts)
