"""Laadt en ontsluit de kennisbank: activiteiten, nationale en lokale richtlijnen, historie."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(naam: str) -> dict[str, Any]:
    with open(DATA_DIR / naam, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def activiteiten_data() -> dict[str, Any]:
    return _load("activiteiten.json")


@lru_cache(maxsize=1)
def richtlijnen_nationaal() -> dict[str, Any]:
    return _load("richtlijnen_nationaal.json")


@lru_cache(maxsize=1)
def richtlijnen_lokaal() -> dict[str, Any]:
    return _load("richtlijnen_lokaal.json")


@lru_cache(maxsize=1)
def historie() -> dict[str, Any]:
    return _load("historie.json")


def activiteit_index() -> dict[str, dict[str, Any]]:
    """Activiteitcode -> activiteitdefinitie."""
    return {a["code"]: a for a in activiteiten_data()["activiteiten"]}


def bijlage_labels() -> dict[str, str]:
    return activiteiten_data()["bijlage_labels"]


def gemeente_namen() -> list[str]:
    return list(richtlijnen_lokaal()["gemeenten"].keys())


def lokaal_profiel(gemeente: str) -> dict[str, Any]:
    """Profiel voor een gemeente; valt terug op 'Overige gemeente' als onbekend."""
    gemeenten = richtlijnen_lokaal()["gemeenten"]
    return gemeenten.get(gemeente, gemeenten["Overige gemeente"])


def meta() -> dict[str, Any]:
    """Metadata voor de frontend: activiteiten, bijlagen, gemeenten."""
    return {
        "activiteiten": activiteiten_data()["activiteiten"],
        "bijlage_labels": bijlage_labels(),
        "gemeenten": gemeente_namen(),
    }


def relevante_richtlijnen_tekst(activiteitcodes: list[str], gemeente: str) -> str:
    """Bouwt een leesbare tekst met alle relevante nationale + lokale richtlijnen.

    Wordt gebruikt als (cachebare) context voor het AI-model.
    """
    idx = activiteit_index()
    nat = richtlijnen_nationaal()["richtlijnen"]
    profiel = lokaal_profiel(gemeente)
    lokaal = profiel["richtlijnen"]

    regels: list[str] = []
    nat_gezien: set[str] = set()
    lok_gezien: set[str] = set()

    regels.append("=== NATIONALE RICHTLIJNEN ===")
    for code in activiteitcodes:
        act = idx.get(code)
        if not act:
            continue
        for rcode in act.get("richtlijnen_nationaal", []):
            if rcode in nat_gezien or rcode not in nat:
                continue
            nat_gezien.add(rcode)
            r = nat[rcode]
            regels.append(f"\n# {r['titel']} ({r['wettelijke_basis']})")
            regels.append("Kernpunten:")
            regels.extend(f"  - {p}" for p in r["kernpunten"])
            regels.append("Veelgemaakte fouten:")
            regels.extend(f"  - {p}" for p in r["veelgemaakte_fouten"])

    regels.append(f"\n=== LOKALE RICHTLIJNEN (gemeente: {gemeente}) ===")
    regels.append(f"Profiel: {profiel['accent']}")
    for code in activiteitcodes:
        act = idx.get(code)
        if not act:
            continue
        for rcode in act.get("richtlijnen_lokaal", []):
            if rcode in lok_gezien or rcode not in lokaal:
                continue
            lok_gezien.add(rcode)
            regels.append(f"\n# {rcode}")
            regels.extend(f"  - {p}" for p in lokaal[rcode])

    return "\n".join(regels)
