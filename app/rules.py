"""Deterministische controle-regels (werken altijd, ook zonder AI).

Genereert bevindingen op basis van volledigheid en geldigheid van de aanvraag.
"""

from __future__ import annotations

import re

from .knowledge import activiteit_index, bijlage_labels
from .schemas import Aanvraag, Bevinding, Severity

POSTCODE_RE = re.compile(r"^\s*\d{4}\s?[A-Za-z]{2}\s*$")


def controleer(aanvraag: Aanvraag) -> list[Bevinding]:
    """Voert alle regels uit en geeft een lijst bevindingen terug."""
    bevindingen: list[Bevinding] = []
    idx = activiteit_index()
    labels = bijlage_labels()

    # --- Basisgegevens aanvrager ---
    if not aanvraag.aanvrager.naam.strip():
        bevindingen.append(
            Bevinding(
                severity=Severity.BLOKKEREND,
                categorie="Aanvrager",
                bericht="De naam van de aanvrager ontbreekt.",
                bron="ow_algemeen",
            )
        )
    if aanvraag.aanvrager.type == "bedrijf" and not (aanvraag.aanvrager.kvk or "").strip():
        bevindingen.append(
            Bevinding(
                severity=Severity.WAARSCHUWING,
                categorie="Aanvrager",
                bericht="Bij een bedrijf is een KvK-nummer vereist.",
                bron="ow_algemeen",
            )
        )

    # --- Locatie ---
    if not aanvraag.locatie.adres.strip() and not (
        aanvraag.locatie.kadastrale_aanduiding or ""
    ).strip():
        bevindingen.append(
            Bevinding(
                severity=Severity.BLOKKEREND,
                categorie="Locatie",
                bericht="Geef een adres of een kadastrale aanduiding op; de locatie is verplicht.",
                bron="ow_algemeen",
            )
        )
    if aanvraag.locatie.postcode and not POSTCODE_RE.match(aanvraag.locatie.postcode):
        bevindingen.append(
            Bevinding(
                severity=Severity.WAARSCHUWING,
                categorie="Locatie",
                bericht="De postcode lijkt niet geldig (verwacht formaat: 1234 AB).",
            )
        )
    if not aanvraag.locatie.gemeente.strip():
        bevindingen.append(
            Bevinding(
                severity=Severity.WAARSCHUWING,
                categorie="Locatie",
                bericht="De gemeente is niet ingevuld; lokale regels kunnen niet goed worden bepaald.",
            )
        )

    # --- Activiteit(en) ---
    if not aanvraag.activiteiten:
        bevindingen.append(
            Bevinding(
                severity=Severity.BLOKKEREND,
                categorie="Activiteit",
                bericht="Kies minimaal één activiteit. Zonder activiteit kan niet worden getoetst.",
                bron="ow_algemeen",
            )
        )

    onbekend = [c for c in aanvraag.activiteiten if c not in idx]
    for code in onbekend:
        bevindingen.append(
            Bevinding(
                severity=Severity.WAARSCHUWING,
                categorie="Activiteit",
                bericht=f"Onbekende activiteitcode '{code}'.",
            )
        )

    # --- Omschrijving ---
    omschrijving = aanvraag.omschrijving.strip()
    if not omschrijving:
        bevindingen.append(
            Bevinding(
                severity=Severity.BLOKKEREND,
                categorie="Omschrijving",
                bericht="Een omschrijving van de werkzaamheden ontbreekt.",
                bron="ow_algemeen",
            )
        )
    elif len(omschrijving) < 40:
        bevindingen.append(
            Bevinding(
                severity=Severity.WAARSCHUWING,
                categorie="Omschrijving",
                bericht="De omschrijving is erg kort. Beschrijf concreet wat, waar en hoe u gaat (ver)bouwen.",
                bron="ow_algemeen",
            )
        )

    # --- Mogelijk vergunningvrij (vooral voor particulieren) ---
    for code in aanvraag.activiteiten:
        act = idx.get(code)
        if not act or not act.get("vergunningvrij_mogelijk"):
            continue
        hint = act.get("vergunningcheck_hint", "")
        bevindingen.append(
            Bevinding(
                severity=Severity.INFO,
                categorie="Vergunningcheck",
                bericht=(
                    f"Mogelijk vergunningvrij: '{act['naam']}'. {hint} "
                    "Doe de vergunningcheck in het Omgevingsloket; is het vergunningvrij, "
                    "dan hoef je niets aan te vragen."
                ).strip(),
                bron="ow_algemeen",
            )
        )

    # --- Bijlagen per activiteit ---
    aanwezig = set(aanvraag.bijlagen)
    for code in aanvraag.activiteiten:
        act = idx.get(code)
        if not act:
            continue
        for verplicht in act.get("verplichte_bijlagen", []):
            if verplicht not in aanwezig:
                label = labels.get(verplicht, verplicht)
                bevindingen.append(
                    Bevinding(
                        severity=Severity.BLOKKEREND,
                        categorie="Bijlagen",
                        bericht=f"Verplichte bijlage ontbreekt voor '{act['naam']}': {label}.",
                        bron=(act.get("richtlijnen_nationaal") or [None])[0],
                    )
                )
        for aanbevolen in act.get("aanbevolen_bijlagen", []):
            if aanbevolen not in aanwezig:
                label = labels.get(aanbevolen, aanbevolen)
                bevindingen.append(
                    Bevinding(
                        severity=Severity.INFO,
                        categorie="Bijlagen",
                        bericht=f"Aanbevolen bijlage ontbreekt voor '{act['naam']}': {label}.",
                    )
                )

    # --- Bouwkosten plausibiliteit ---
    bouwactiviteiten = {"bouw_omgevingsplan", "bouw_technisch", "monument", "milieu"}
    if set(aanvraag.activiteiten) & bouwactiviteiten and aanvraag.bouwkosten <= 0:
        bevindingen.append(
            Bevinding(
                severity=Severity.WAARSCHUWING,
                categorie="Kosten",
                bericht="Vul de geschatte bouwkosten in; deze zijn nodig voor de leges en toetsing.",
            )
        )

    # --- Vooroverleg bij complexe activiteiten ---
    complex_codes = [
        code
        for code in aanvraag.activiteiten
        if idx.get(code, {}).get("complexiteit") == "hoog"
    ]
    if complex_codes and not aanvraag.vooroverleg:
        namen = ", ".join(idx[c]["naam"] for c in complex_codes)
        bevindingen.append(
            Bevinding(
                severity=Severity.WAARSCHUWING,
                categorie="Proces",
                bericht=(
                    f"Voor complexe activiteit(en) ({namen}) is vooroverleg met de gemeente "
                    "sterk aan te raden om de kans op acceptatie te vergroten."
                ),
            )
        )

    return bevindingen
