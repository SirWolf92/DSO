"""Pydantic-modellen voor de DSO-aanvraag en het controleresultaat."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Aanvrager(BaseModel):
    naam: str = Field(default="", description="Naam van de aanvrager")
    type: str = Field(default="particulier", description="particulier of bedrijf")
    kvk: Optional[str] = Field(default=None, description="KvK-nummer bij een bedrijf")


class Locatie(BaseModel):
    adres: str = Field(default="", description="Straat en huisnummer")
    postcode: str = Field(default="", description="Postcode, bv. 1011 AB")
    gemeente: str = Field(default="", description="Naam van de gemeente")
    kadastrale_aanduiding: Optional[str] = Field(
        default=None, description="Kadastrale aanduiding (gemeente, sectie, nummer)"
    )


class Aanvraag(BaseModel):
    """Een complete DSO-vergunningaanvraag zoals ingevuld door de gebruiker."""

    aanvrager: Aanvrager = Field(default_factory=Aanvrager)
    locatie: Locatie = Field(default_factory=Locatie)
    activiteiten: list[str] = Field(
        default_factory=list, description="Lijst met activiteitcodes"
    )
    omschrijving: str = Field(default="", description="Omschrijving van de werkzaamheden")
    bouwkosten: float = Field(default=0, description="Geschatte bouwkosten in euro's")
    vooroverleg: bool = Field(default=False, description="Is er vooroverleg geweest?")
    startdatum: Optional[str] = Field(default=None, description="Geplande startdatum")
    bijlagen: list[str] = Field(
        default_factory=list, description="Lijst met toegevoegde bijlagecodes"
    )


class Severity(str, Enum):
    BLOKKEREND = "blokkerend"
    WAARSCHUWING = "waarschuwing"
    INFO = "info"


class Bevinding(BaseModel):
    """Een individueel controlepunt."""

    severity: Severity
    categorie: str
    bericht: str
    bron: Optional[str] = Field(default=None, description="Verwijzing naar richtlijn")


class Tip(BaseModel):
    """Een advies om de kans op acceptatie te vergroten."""

    titel: str
    advies: str
    impact: str = Field(default="midden", description="hoog, midden of laag")
    bron: Optional[str] = None


class HistorischeContext(BaseModel):
    aantal_vergelijkbaar: int = 0
    acceptatiepercentage: Optional[float] = None
    veelvoorkomende_weigeringsredenen: list[str] = Field(default_factory=list)
    toelichting: str = ""


class CheckResultaat(BaseModel):
    """Het volledige resultaat van de controle."""

    score: int = Field(description="Geschatte kans op acceptatie 0-100")
    score_label: str
    samenvatting: str
    bevindingen: list[Bevinding] = Field(default_factory=list)
    tips: list[Tip] = Field(default_factory=list)
    historische_context: HistorischeContext = Field(default_factory=HistorischeContext)
    ai_gebruikt: bool = Field(
        default=False, description="Is de AI-analyse gebruikt of de fallback?"
    )
    klaar_voor_indienen: bool = False
