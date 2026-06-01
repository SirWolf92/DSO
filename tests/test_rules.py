"""Tests voor de deterministische regel-engine."""

from app.rules import controleer
from app.schemas import Aanvraag, Aanvrager, Locatie, Severity


def _lege_aanvraag() -> Aanvraag:
    return Aanvraag()


def _goede_aanvraag() -> Aanvraag:
    return Aanvraag(
        aanvrager=Aanvrager(naam="Jan Jansen", type="particulier"),
        locatie=Locatie(adres="Dorpsstraat 1", postcode="1234 AB", gemeente="Utrecht"),
        activiteiten=["kappen"],
        omschrijving="Het vellen van een zieke kastanjeboom in de achtertuin, "
        "circa 12 meter hoog, met herplant van een nieuwe boom.",
        bouwkosten=0,
        bijlagen=["situatietekening", "foto_boom"],
    )


def test_lege_aanvraag_heeft_blokkerende_bevindingen():
    bevindingen = controleer(_lege_aanvraag())
    blok = [b for b in bevindingen if b.severity == Severity.BLOKKEREND]
    # Geen naam, geen locatie, geen activiteit, geen omschrijving -> meerdere blokkerend.
    assert len(blok) >= 4
    categorieen = {b.categorie for b in blok}
    assert {"Aanvrager", "Locatie", "Activiteit", "Omschrijving"} <= categorieen


def test_goede_aanvraag_zonder_blokkerend():
    bevindingen = controleer(_goede_aanvraag())
    blok = [b for b in bevindingen if b.severity == Severity.BLOKKEREND]
    assert blok == []


def test_ontbrekende_verplichte_bijlage_is_blokkerend():
    aanvraag = _goede_aanvraag()
    aanvraag.bijlagen = ["situatietekening"]  # foto_boom ontbreekt
    bevindingen = controleer(aanvraag)
    bijlage_blok = [
        b
        for b in bevindingen
        if b.categorie == "Bijlagen" and b.severity == Severity.BLOKKEREND
    ]
    assert any("foto" in b.bericht.lower() for b in bijlage_blok)


def test_bedrijf_zonder_kvk_geeft_waarschuwing():
    aanvraag = _goede_aanvraag()
    aanvraag.aanvrager.type = "bedrijf"
    aanvraag.aanvrager.kvk = None
    bevindingen = controleer(aanvraag)
    assert any(
        b.categorie == "Aanvrager" and "KvK" in b.bericht for b in bevindingen
    )


def test_ongeldige_postcode_geeft_waarschuwing():
    aanvraag = _goede_aanvraag()
    aanvraag.locatie.postcode = "ABCDEF"
    bevindingen = controleer(aanvraag)
    assert any(
        b.categorie == "Locatie" and "postcode" in b.bericht.lower()
        for b in bevindingen
    )


def test_korte_omschrijving_geeft_waarschuwing():
    aanvraag = _goede_aanvraag()
    aanvraag.omschrijving = "Boom weg"
    bevindingen = controleer(aanvraag)
    assert any(b.categorie == "Omschrijving" for b in bevindingen)


def test_complexe_activiteit_zonder_vooroverleg_waarschuwt():
    aanvraag = Aanvraag(
        aanvrager=Aanvrager(naam="BV X", type="bedrijf", kvk="12345678"),
        locatie=Locatie(adres="Industrieweg 5", postcode="3000 AA", gemeente="Rotterdam"),
        activiteiten=["milieu"],
        omschrijving="Het oprichten van een inrichting met opslag van gevaarlijke stoffen "
        "en bijbehorende processen, inclusief emissiebeheersing.",
        bouwkosten=250000,
        vooroverleg=False,
        bijlagen=["situatietekening", "milieu_onderbouwing", "bedrijfsbeschrijving"],
    )
    bevindingen = controleer(aanvraag)
    assert any(b.categorie == "Proces" and "vooroverleg" in b.bericht for b in bevindingen)
