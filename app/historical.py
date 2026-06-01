"""Analyse van historische aanvragen om een acceptatiekans en weigeringsredenen te schatten."""

from __future__ import annotations

from collections import Counter

from .knowledge import historie
from .schemas import Aanvraag, HistorischeContext


def analyseer(aanvraag: Aanvraag) -> HistorischeContext:
    """Bepaalt vergelijkbare historische aanvragen en leidt statistiek af."""
    records = historie()["aanvragen"]
    activiteiten = set(aanvraag.activiteiten)
    gemeente = aanvraag.locatie.gemeente.strip()

    # Eerst proberen op activiteit + gemeente, anders alleen op activiteit.
    op_activiteit = [r for r in records if r["activiteit"] in activiteiten]
    op_beide = [r for r in op_activiteit if r["gemeente"] == gemeente]

    gebruikt = op_beide if len(op_beide) >= 3 else op_activiteit
    schaal = "activiteit en gemeente" if gebruikt is op_beide and op_beide else "activiteit"

    if not gebruikt:
        return HistorischeContext(
            aantal_vergelijkbaar=0,
            acceptatiepercentage=None,
            veelvoorkomende_weigeringsredenen=[],
            toelichting="Geen vergelijkbare historische aanvragen gevonden.",
        )

    verleend = sum(1 for r in gebruikt if r["uitkomst"] == "verleend")
    percentage = round(100 * verleend / len(gebruikt))

    geweigerd = [r for r in gebruikt if r["uitkomst"] == "geweigerd"]
    redenen = Counter(r["reden"] for r in geweigerd)
    top_redenen = [reden for reden, _ in redenen.most_common(3)]

    return HistorischeContext(
        aantal_vergelijkbaar=len(gebruikt),
        acceptatiepercentage=percentage,
        veelvoorkomende_weigeringsredenen=top_redenen,
        toelichting=(
            f"Gebaseerd op {len(gebruikt)} vergelijkbare aanvragen (op {schaal}). "
            f"Daarvan werd {percentage}% verleend."
        ),
    )


def vooroverleg_effect() -> dict[str, float]:
    """Laat het effect van vooroverleg zien over de hele dataset (voor tips)."""
    records = historie()["aanvragen"]
    met = [r for r in records if r["vooroverleg"]]
    zonder = [r for r in records if not r["vooroverleg"]]

    def pct(rs: list[dict]) -> float:
        if not rs:
            return 0.0
        return round(100 * sum(1 for r in rs if r["uitkomst"] == "verleend") / len(rs))

    return {"met_vooroverleg": pct(met), "zonder_vooroverleg": pct(zonder)}
