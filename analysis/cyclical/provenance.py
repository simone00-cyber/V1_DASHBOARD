"""Methodological provenance and explicit model boundaries."""

from analysis.cyclical.models import MethodologyStatus


def methodology_coverage() -> tuple[MethodologyStatus, ...]:
    return (
        MethodologyStatus(
            component="KEY / XTL / Composite Momentum",
            status="VERIFIED FORMULA",
            source="CM_Prt.pdf; CM_MetaStock.pdf",
            note="Formula verificata riga per riga contro le formule ProRealTime e MetaStock originali: corrispondenza esatta. La convenzione Stochastic(5,3) è confermata identica nelle due fonti, nessuna ambiguità residua.",
        ),
        MethodologyStatus(
            component="Quattro posizioni cicliche U/A/D/T",
            status="DOCUMENTED RULE",
            source="Metodologia Ciclica, sezione Comprensione dello scenario ciclico",
            note="UP, ADVANCING, DOWN, TERMINATING derivano da segno e direzione del Composite Momentum.",
        ),
        MethodologyStatus(
            component="Gerarchia annuale/trimestrale/mensile/settimanale",
            status="DOCUMENTED RULE",
            source="La Metodologia Ciclica.pdf, teoria ciclo dominante e secondario",
            note="Il timeframe inferiore governa il timing di esecuzione rispetto al ciclo dominante. Durate documentate da minimo a minimo: ciclo di lungo termine (Composite trimestrale) 30-60 mesi, ciclo di medio termine (Composite mensile) 9-24 mesi, ciclo di breve termine (Composite settimanale) 2,5-4 mesi.",
        ),
        MethodologyStatus(
            component="Matrice tattica multi-timeframe",
            status="DOCUMENTED RULE",
            source="Metodologia Ciclica, organigramma dei cicli",
            note="BUY, SELL SHORT, TAKE PROFIT e rating sono letture della matrice pubblicata.",
        ),
        MethodologyStatus(
            component="Durata dello stato e cronologia",
            status="DERIVED METRIC",
            source="Calcolo deterministico sui cambi di quadrante CM",
            note="Misura descrittiva aggiunta dal software; non è presentata come indicatore proprietario.",
        ),
        MethodologyStatus(
            component="Signal history e backtest della matrice",
            status="DOCUMENTED RULE + DERIVED RESEARCH",
            source="Matrice tattica pubblicata; convenzioni di esecuzione dichiarate nel software",
            note="I segnali derivano dalla matrice. Chiusura settimanale, costi, long-only/long-short e metriche sono convenzioni di ricerca trasparenti, non componenti proprietarie.",
        ),
        MethodologyStatus(
            component="Investitore Disciplinato",
            status="NOT IMPLEMENTED",
            source="Materiale ID fornito",
            note="Stati e caratteristiche sono documentati, ma la formula dei livelli regime-switching è proprietaria e non pubblicata.",
        ),
        MethodologyStatus(
            component="Fear/Complacency Index",
            status="NOT IMPLEMENTED",
            source="Materiale metodologico fornito",
            note="Formula completa non disponibile.",
        ),
    )
