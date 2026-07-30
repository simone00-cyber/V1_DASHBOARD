"""Multi-timeframe hierarchy based on the documented CM interaction logic."""

from __future__ import annotations

from typing import Dict

from analysis.cyclical.models import CycleState, HierarchyAssessment


def _is_rising(state: CycleState) -> bool:
    return state.direction == "UP"


def _is_falling(state: CycleState) -> bool:
    return state.direction == "DOWN"


def assess_hierarchy(states: Dict[str, CycleState]) -> HierarchyAssessment:
    required = {"QUARTERLY", "MONTHLY", "WEEKLY"}
    missing = required.difference(states)
    if missing:
        raise ValueError(f"Timeframe mancanti: {sorted(missing)}")

    annual = states.get("YEARLY")
    quarterly = states["QUARTERLY"]
    monthly = states["MONTHLY"]
    weekly = states["WEEKLY"]

    notes = []
    if _is_rising(quarterly) and _is_rising(monthly):
        if _is_rising(weekly):
            alignment = "FULL BULLISH ALIGNMENT"
            tactical = "MOMENTUM RIALZISTA ALLINEATO"
            trigger = "Nessun nuovo trigger richiesto: monitorare i successivi flessi settimanali."
        else:
            alignment = "BULLISH HIGHER-TIMEFRAME ALIGNMENT"
            tactical = "CORREZIONE SETTIMANALE IN CONTESTO RIALZISTA"
            trigger = "BUY documentale alla prossima SVOLTA UP settimanale, se trimestrale e mensile restano UP."
            notes.append("Il trend secondario settimanale governa il timing di esecuzione.")
    elif _is_falling(quarterly) and _is_falling(monthly):
        if _is_falling(weekly):
            alignment = "FULL BEARISH ALIGNMENT"
            tactical = "MOMENTUM RIBASSISTA ALLINEATO"
            trigger = "Nessun nuovo trigger richiesto: monitorare i successivi flessi settimanali."
        else:
            alignment = "BEARISH HIGHER-TIMEFRAME ALIGNMENT"
            tactical = "RIMBALZO SETTIMANALE IN CONTESTO RIBASSISTA"
            trigger = "SELL SHORT documentale alla prossima SVOLTA DOWN settimanale, se trimestrale e mensile restano DOWN."
            notes.append("Il trend secondario settimanale governa il timing di esecuzione.")
    else:
        alignment = "MIXED / NON-SYNCHRONIZED"
        tactical = "TIMEFRAME SUPERIORI NON ALLINEATI"
        if weekly.turn == "SVOLTA UP":
            trigger = "La matrice documentale valuta la svolta UP in base alla combinazione trimestrale/mensile corrente."
        elif weekly.turn == "SVOLTA DOWN":
            trigger = "La matrice documentale valuta la svolta DOWN in base alla combinazione trimestrale/mensile corrente."
        else:
            trigger = "Attendere una nuova svolta settimanale; il rating dipenderà dall'allineamento dei timeframe superiori."
        notes.append("La metodologia distingue i modelli di inversione sincronizzati e non sincronizzati.")

    if annual is None:
        notes.append("Timeframe annuale non disponibile: storico insufficiente dopo il warm-up del Composite Momentum.")
    elif annual.direction != quarterly.direction:
        notes.append("Annuale e trimestrale non sono allineati: il contesto strutturale è in transizione o divergenza.")

    return HierarchyAssessment(
        annual_phase=annual.phase if annual is not None else "N/D",
        quarterly_phase=quarterly.phase,
        monthly_phase=monthly.phase,
        weekly_phase=weekly.phase,
        quarterly_direction=quarterly.direction,
        monthly_direction=monthly.direction,
        weekly_direction=weekly.direction,
        alignment=alignment,
        tactical_condition=tactical,
        documented_trigger=trigger,
        notes=tuple(notes),
    )
