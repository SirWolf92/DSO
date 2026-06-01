"""Tests voor de orkestratie (checker), historie en de API.

De AI-laag wordt niet aangeroepen zonder ANTHROPIC_API_KEY; deze tests draaien dus
op de deterministische fallback.
"""

from fastapi.testclient import TestClient

from app import historical
from app.checker import check
from app.main import app
from app.schemas import Aanvraag, Aanvrager, Locatie, Severity

client = TestClient(app)


def _goede_aanvraag() -> Aanvraag:
    return Aanvraag(
        aanvrager=Aanvrager(naam="Jan Jansen", type="particulier"),
        locatie=Locatie(adres="Dorpsstraat 1", postcode="1234 AB", gemeente="Rotterdam"),
        activiteiten=["kappen"],
        omschrijving="Het vellen van een zieke kastanjeboom in de achtertuin, "
        "circa 12 meter hoog, met herplant van een nieuwe boom.",
        bijlagen=["situatietekening", "foto_boom"],
    )


def test_check_lege_aanvraag_lage_score_niet_klaar():
    res = check(Aanvraag())
    assert res.score < 50
    assert res.klaar_voor_indienen is False
    assert res.ai_gebruikt is False
    assert len(res.tips) >= 1


def test_check_goede_aanvraag_klaar_voor_indienen():
    res = check(_goede_aanvraag())
    assert res.klaar_voor_indienen is True
    assert res.score >= 50


def test_score_binnen_bereik():
    res = check(_goede_aanvraag())
    assert 0 <= res.score <= 100


def test_historische_analyse_geeft_percentage():
    hist = historical.analyseer(_goede_aanvraag())
    assert hist.aantal_vergelijkbaar > 0
    assert hist.acceptatiepercentage is not None
    assert 0 <= hist.acceptatiepercentage <= 100


def test_vooroverleg_effect_velden():
    effect = historical.vooroverleg_effect()
    assert "met_vooroverleg" in effect
    assert "zonder_vooroverleg" in effect


def test_blokkerende_bevinding_verlaagt_klaarstatus():
    aanvraag = _goede_aanvraag()
    aanvraag.bijlagen = []  # verplichte bijlagen ontbreken
    res = check(aanvraag)
    assert res.klaar_voor_indienen is False
    assert any(b.severity == Severity.BLOKKEREND for b in res.bevindingen)


# --- API-tests ---


def test_api_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_api_meta_bevat_activiteiten():
    r = client.get("/api/meta")
    assert r.status_code == 200
    data = r.json()
    assert len(data["activiteiten"]) >= 5
    assert "gemeenten" in data
    assert "bijlage_labels" in data


def test_api_check_retourneert_resultaat():
    r = client.post("/api/check", json=_goede_aanvraag().model_dump())
    assert r.status_code == 200
    data = r.json()
    assert "score" in data
    assert "tips" in data
    assert "bevindingen" in data
    assert "historische_context" in data


def test_api_index_serveert_html():
    r = client.get("/")
    assert r.status_code == 200
    assert "DSO" in r.text
