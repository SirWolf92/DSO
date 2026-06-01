"""Orkestreert de volledige controle: regels + historie + AI, en berekent de score."""

from __future__ import annotations

from . import ai_review, historical, rules
from .historical import vooroverleg_effect
from .knowledge import activiteit_index
from .schemas import (
    Aanvraag,
    Bevinding,
    CheckResultaat,
    HistorischeContext,
    Severity,
    Tip,
)

# Aftrek per bevinding op de basisscore.
AFTREK = {Severity.BLOKKEREND: 22, Severity.WAARSCHUWING: 8, Severity.INFO: 2}


def _score_label(score: int) -> str:
    if score >= 80:
        return "Grote kans op acceptatie"
    if score >= 55:
        return "Redelijke kans, met aandachtspunten"
    if score >= 30:
        return "Kleine kans; belangrijke punten openstaand"
    return "Zeer kleine kans; aanvraag nog niet indienen"


def _bereken_score(bevindingen: list[Bevinding], hist: HistorischeContext) -> int:
    """Combineert een aftrekmodel op bevindingen met de historische acceptatiekans."""
    basis = 100
    for b in bevindingen:
        basis -= AFTREK.get(b.severity, 0)
    basis = max(0, min(100, basis))

    if hist.acceptatiepercentage is None:
        return basis

    # Weeg de op regels gebaseerde score (70%) met de historische kans (30%).
    gecombineerd = round(0.7 * basis + 0.3 * hist.acceptatiepercentage)
    return max(0, min(100, gecombineerd))


def _fallback_tips(
    aanvraag: Aanvraag, bevindingen: list[Bevinding], hist: HistorischeContext
) -> list[Tip]:
    """Genereert tips zonder AI, op basis van de bevindingen en historie."""
    tips: list[Tip] = []
    idx = activiteit_index()

    blokkerend = [b for b in bevindingen if b.severity == Severity.BLOKKEREND]
    if blokkerend:
        tips.append(
            Tip(
                titel="Los eerst de blokkerende punten op",
                advies=(
                    "Er zijn "
                    f"{len(blokkerend)} blokkerende punten. Vul de ontbrekende verplichte "
                    "gegevens en bijlagen aan voordat u indient; anders wordt de aanvraag "
                    "buiten behandeling gesteld."
                ),
                impact="hoog",
                bron="ow_algemeen",
            )
        )

    ontbrekende_bijlagen = [
        b for b in bevindingen if b.categorie == "Bijlagen" and b.severity != Severity.INFO
    ]
    if ontbrekende_bijlagen:
        tips.append(
            Tip(
                titel="Maak het dossier compleet",
                advies=(
                    "Voeg de ontbrekende verplichte bijlagen toe. Een compleet dossier is de "
                    "belangrijkste factor voor een snelle, positieve beoordeling."
                ),
                impact="hoog",
            )
        )

    # Vooroverleg-tip op basis van historische data.
    effect = vooroverleg_effect()
    if not aanvraag.vooroverleg and effect["met_vooroverleg"] > effect["zonder_vooroverleg"]:
        tips.append(
            Tip(
                titel="Voer vooroverleg met de gemeente",
                advies=(
                    f"In de historische data wordt {effect['met_vooroverleg']}% van de aanvragen "
                    f"mét vooroverleg verleend, tegenover {effect['zonder_vooroverleg']}% zonder. "
                    "Plan vooroverleg om verrassingen te voorkomen."
                ),
                impact="midden",
            )
        )

    # Tips op basis van veelvoorkomende weigeringsredenen.
    for reden in hist.veelvoorkomende_weigeringsredenen:
        tips.append(
            Tip(
                titel="Speel in op een veelvoorkomende weigeringsreden",
                advies=(
                    f"Vergelijkbare aanvragen werden geweigerd om: \"{reden}\". "
                    "Onderbouw in uw aanvraag expliciet hoe u dit ondervangt."
                ),
                impact="midden",
            )
        )

    # Omschrijving verbeteren.
    if any(b.categorie == "Omschrijving" for b in bevindingen):
        tips.append(
            Tip(
                titel="Maak de omschrijving concreet",
                advies=(
                    "Beschrijf wat u doet, met welke materialen, afmetingen en waarom. Een heldere "
                    "omschrijving voorkomt vragen en versnelt de behandeling."
                ),
                impact="midden",
                bron="ow_algemeen",
            )
        )

    if not tips:
        tips.append(
            Tip(
                titel="Dossier ziet er compleet uit",
                advies=(
                    "Er zijn geen grote tekortkomingen gevonden. Controleer de tekeningen op "
                    "actualiteit en dien in via het Omgevingsloket."
                ),
                impact="laag",
            )
        )

    return tips


def _samenvatting_fallback(score: int, bevindingen: list[Bevinding]) -> str:
    n_blok = sum(1 for b in bevindingen if b.severity == Severity.BLOKKEREND)
    n_waarsch = sum(1 for b in bevindingen if b.severity == Severity.WAARSCHUWING)
    return (
        f"Geschatte kans op acceptatie: {score}/100. "
        f"{n_blok} blokkerende punt(en) en {n_waarsch} waarschuwing(en) gevonden. "
        "Deze inschatting is gebaseerd op een regelcontrole en historische data "
        "(zonder AI-analyse)."
    )


def check(aanvraag: Aanvraag) -> CheckResultaat:
    """Voert de volledige controle uit en bouwt het resultaat."""
    bevindingen = rules.controleer(aanvraag)
    hist = historical.analyseer(aanvraag)

    ai = ai_review.analyseer(aanvraag, bevindingen, hist)
    ai_gebruikt = ai is not None

    if ai_gebruikt:
        bevindingen = bevindingen + ai["extra_bevindingen"]
        tips = ai["tips"] or _fallback_tips(aanvraag, bevindingen, hist)
        samenvatting = ai["samenvatting"]
    else:
        tips = _fallback_tips(aanvraag, bevindingen, hist)
        samenvatting = ""

    # Sorteer bevindingen op ernst.
    volgorde = {Severity.BLOKKEREND: 0, Severity.WAARSCHUWING: 1, Severity.INFO: 2}
    bevindingen.sort(key=lambda b: volgorde.get(b.severity, 3))

    score = _bereken_score(bevindingen, hist)
    if not samenvatting:
        samenvatting = _samenvatting_fallback(score, bevindingen)

    klaar = not any(b.severity == Severity.BLOKKEREND for b in bevindingen)

    return CheckResultaat(
        score=score,
        score_label=_score_label(score),
        samenvatting=samenvatting,
        bevindingen=bevindingen,
        tips=tips,
        historische_context=hist,
        ai_gebruikt=ai_gebruikt,
        klaar_voor_indienen=klaar,
    )
