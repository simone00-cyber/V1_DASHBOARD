from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from .models import RegimeLayer


def driver_lines(layer: RegimeLayer) -> Tuple[List[str], List[str]]:
    positive = sorted(
        [pillar for pillar in layer.pillars if pillar.score >= 0.35],
        key=lambda pillar: pillar.score,
        reverse=True,
    )
    negative = sorted(
        [pillar for pillar in layer.pillars if pillar.score <= -0.35],
        key=lambda pillar: pillar.score,
    )
    return (
        [f"{p.name}: {p.state} ({p.score:+.2f})" for p in positive],
        [f"{p.name}: {p.state} ({p.score:+.2f})" for p in negative],
    )


def build_regime_comment(results: Dict[str, RegimeLayer]) -> str:
    strategic = results["STRATEGIC"]
    tactical = results["TACTICAL"]
    daily = results["DAILY"]
    tactical_positive, tactical_negative = driver_lines(tactical)
    strongest = max(tactical.pillars, key=lambda p: p.score)
    weakest = min(tactical.pillars, key=lambda p: p.score)

    parts = [
        f"Il contesto strutturale è **{strategic.diagnosis.lower()}**, "
        f"la direzione tattica è **{tactical.diagnosis.lower()}** e il tono "
        f"dell'ultima seduta è **{daily.diagnosis.lower()}**."
    ]

    if strategic.score > 0.35 and tactical.diagnosis == "DETERIORATING":
        parts.append(
            "Il deterioramento tattico si sviluppa all'interno di un quadro di fondo ancora costruttivo: "
            "la configurazione è coerente con una correzione, non ancora con una rottura strutturale confermata."
        )
    elif strategic.score < -0.35 and tactical.diagnosis == "IMPROVING":
        parts.append(
            "Il miglioramento tattico avviene all'interno di un quadro strutturale difensivo e può rappresentare "
            "un rally di reazione finché credito, volatilità e trend globale non confermano il cambio di regime."
        )
    elif np.sign(strategic.score) == np.sign(tactical.score):
        parts.append("Il segnale tattico è coerente con il contesto di fondo, aumentando la robustezza della lettura cross-asset.")
    else:
        parts.append("Gli orizzonti non sono pienamente allineati; il mercato si trova in una fase di transizione.")

    parts.append(
        f"Il principale sostegno tattico proviene da **{strongest.name.lower()}** ({strongest.state.lower()}), "
        f"mentre il freno più rilevante è **{weakest.name.lower()}** ({weakest.state.lower()})."
    )
    if tactical_negative:
        parts.append("Fattori di rischio attivi: " + "; ".join(tactical_negative[:3]) + ".")
    if tactical_positive:
        parts.append("Fattori di supporto: " + "; ".join(tactical_positive[:3]) + ".")

    coverage = tactical.coverage * 100.0
    parts.append(f"Copertura dati del livello tattico: **{coverage:.0f}%**.")
    parts.append("La diagnosi descrive l'ambiente cross-asset e non costituisce isolatamente un segnale sul singolo strumento.")
    return " ".join(parts)
