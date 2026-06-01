"""AI-analyse van de aanvraag met de Claude API.

Gebruikt nationale + lokale richtlijnen als (cachebare) context en vraagt om
extra bevindingen en concrete tips. Valt terug op een heuristiek wanneer er geen
API-sleutel is of de aanroep mislukt.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from .knowledge import activiteit_index, relevante_richtlijnen_tekst
from .historical import vooroverleg_effect
from .schemas import Aanvraag, Bevinding, HistorischeContext, Severity, Tip

logger = logging.getLogger("dso.ai")

MODEL = os.environ.get("DSO_MODEL", "claude-opus-4-8")
EFFORT = os.environ.get("DSO_EFFORT", "medium")  # low | medium | high | max

SYSTEM_ROL = """Je bent een ervaren vergunningverlener en adviseur voor het \
Digitaal Stelsel Omgevingswet (DSO) in Nederland. Je beoordeelt concept-aanvragen \
voordat ze worden ingediend bij het Omgevingsloket.

Je taak:
1. Beoordeel de aanvraag tegen de meegeleverde nationale EN lokale richtlijnen.
2. Benoem risico's en aandachtspunten die een geautomatiseerde volledigheidscheck \
mist (inhoudelijke en kwalitatieve punten).
3. Geef concrete, uitvoerbare tips waarmee de aanvraag een grotere kans heeft om \
geaccepteerd te worden, onderbouwd met de richtlijnen en (indien meegeleverd) de \
historische data.

Belangrijke regels:
- Schrijf in helder, zakelijk Nederlands.
- Wees concreet: verwijs naar de specifieke richtlijn of het ontbrekende element.
- Verzin geen wettelijke eisen die niet uit de meegeleverde richtlijnen blijken.
- Herhaal niet klakkeloos de reeds gevonden bevindingen; vul ze aan.
- Geef je antwoord uitsluitend als geldig JSON volgens het schema."""

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "samenvatting": {
            "type": "string",
            "description": "Korte risico-inschatting (2-4 zinnen) in het Nederlands.",
        },
        "extra_bevindingen": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["blokkerend", "waarschuwing", "info"],
                    },
                    "categorie": {"type": "string"},
                    "bericht": {"type": "string"},
                    "bron": {"type": "string"},
                },
                "required": ["severity", "categorie", "bericht", "bron"],
                "additionalProperties": False,
            },
        },
        "tips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titel": {"type": "string"},
                    "advies": {"type": "string"},
                    "impact": {
                        "type": "string",
                        "enum": ["hoog", "midden", "laag"],
                    },
                    "bron": {"type": "string"},
                },
                "required": ["titel", "advies", "impact", "bron"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["samenvatting", "extra_bevindingen", "tips"],
    "additionalProperties": False,
}


def _aanvraag_tekst(
    aanvraag: Aanvraag, bevindingen: list[Bevinding], hist: HistorischeContext
) -> str:
    idx = activiteit_index()
    namen = [idx.get(c, {}).get("naam", c) for c in aanvraag.activiteiten]
    regels = [
        "=== CONCEPT-AANVRAAG ===",
        f"Aanvrager: {aanvraag.aanvrager.naam or '(leeg)'} ({aanvraag.aanvrager.type})",
        f"Locatie: {aanvraag.locatie.adres or '(leeg)'}, {aanvraag.locatie.postcode} "
        f"{aanvraag.locatie.gemeente or '(geen gemeente)'}",
        f"Kadastraal: {aanvraag.locatie.kadastrale_aanduiding or '(leeg)'}",
        f"Activiteiten: {', '.join(namen) or '(geen)'}",
        f"Bouwkosten: EUR {aanvraag.bouwkosten:,.0f}",
        f"Vooroverleg gehad: {'ja' if aanvraag.vooroverleg else 'nee'}",
        f"Geplande start: {aanvraag.startdatum or '(leeg)'}",
        f"Toegevoegde bijlagen: {', '.join(aanvraag.bijlagen) or '(geen)'}",
        "",
        "Omschrijving werkzaamheden:",
        aanvraag.omschrijving or "(leeg)",
        "",
        "=== REEDS GEVONDEN BEVINDINGEN (volledigheidscheck) ===",
    ]
    if bevindingen:
        regels.extend(f"- [{b.severity.value}] {b.categorie}: {b.bericht}" for b in bevindingen)
    else:
        regels.append("(geen)")

    regels.append("")
    regels.append("=== HISTORISCHE CONTEXT ===")
    regels.append(hist.toelichting or "(geen)")
    if hist.veelvoorkomende_weigeringsredenen:
        regels.append("Veelvoorkomende weigeringsredenen bij vergelijkbare aanvragen:")
        regels.extend(f"- {r}" for r in hist.veelvoorkomende_weigeringsredenen)

    effect = vooroverleg_effect()
    regels.append(
        f"Effect vooroverleg (hele dataset): met {effect['met_vooroverleg']}% verleend, "
        f"zonder {effect['zonder_vooroverleg']}% verleend."
    )
    return "\n".join(regels)


def beschikbaar() -> bool:
    """Is de AI-analyse beschikbaar (API-sleutel aanwezig en SDK geïnstalleerd)?"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def analyseer(
    aanvraag: Aanvraag, bevindingen: list[Bevinding], hist: HistorischeContext
) -> Optional[dict[str, Any]]:
    """Roept Claude aan en geeft een dict met samenvatting, extra_bevindingen en tips.

    Geeft None terug als de AI niet beschikbaar is of de aanroep mislukt.
    """
    if not beschikbaar():
        return None

    import anthropic

    richtlijnen = relevante_richtlijnen_tekst(
        aanvraag.activiteiten, aanvraag.locatie.gemeente.strip()
    )
    gebruikers_tekst = _aanvraag_tekst(aanvraag, bevindingen, hist)

    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            thinking={"type": "adaptive"},
            output_config={
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
            },
            system=[
                {"type": "text", "text": SYSTEM_ROL},
                {
                    "type": "text",
                    "text": "RICHTLIJNEN (toets hierop):\n\n" + richtlijnen,
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            messages=[{"role": "user", "content": gebruikers_tekst}],
        )
    except Exception as exc:  # noqa: BLE001 - bewust breed: val terug op heuristiek
        logger.warning("AI-analyse mislukt, val terug op heuristiek: %s", exc)
        return None

    tekst = next((b.text for b in response.content if b.type == "text"), None)
    if not tekst:
        return None
    try:
        data = json.loads(tekst)
    except json.JSONDecodeError:
        logger.warning("AI gaf ongeldig JSON terug; fallback.")
        return None

    return _normaliseer(data)


def _normaliseer(data: dict[str, Any]) -> dict[str, Any]:
    """Zet ruwe AI-output om naar onze schema-objecten."""
    bevindingen = []
    for b in data.get("extra_bevindingen", []):
        try:
            bevindingen.append(
                Bevinding(
                    severity=Severity(b.get("severity", "info")),
                    categorie=b.get("categorie", "Overig"),
                    bericht=b.get("bericht", ""),
                    bron=b.get("bron") or None,
                )
            )
        except ValueError:
            continue
    tips = [
        Tip(
            titel=t.get("titel", "Tip"),
            advies=t.get("advies", ""),
            impact=t.get("impact", "midden"),
            bron=t.get("bron") or None,
        )
        for t in data.get("tips", [])
    ]
    return {
        "samenvatting": data.get("samenvatting", ""),
        "extra_bevindingen": bevindingen,
        "tips": tips,
    }
