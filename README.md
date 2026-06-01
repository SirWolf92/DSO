# DSO Aanvraag Checker

Een webapplicatie die je helpt je **DSO-/Omgevingswet-aanvraag** in te vullen en
**controleert vóórdat je indient**. De checker combineert:

- 🤖 **AI-analyse** met de Claude API (inhoudelijke beoordeling);
- 📊 **historische data** van eerdere aanvragen (acceptatiekans + veelvoorkomende
  weigeringsredenen);
- 📚 **nationale én lokale richtlijnen** (Omgevingswet, Bbl, Bal + omgevingsplan/
  welstand per gemeente).

Je krijgt een **ingeschatte kans op acceptatie**, een lijst met **bevindingen**
(blokkerend / waarschuwing / info) en concrete **tips om je aanvraag te
verbeteren** — onderbouwd met die bronnen.

> Demo met voorbeeldrichtlijnen en -historie. Geen officieel overheidsadvies.

---

## Snel starten

```bash
# 1. Dependencies installeren
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. (optioneel) AI activeren
export ANTHROPIC_API_KEY=sk-ant-...      # zonder sleutel: regels + historie

# 3. Server starten
uvicorn app.main:app --reload
```

Open daarna **http://127.0.0.1:8000** in je browser.

### Tests

```bash
pytest -q
```

---

## Werkt ook zonder API-sleutel

De app is zo gebouwd dat hij **altijd** werkt:

| Onderdeel | Met `ANTHROPIC_API_KEY` | Zonder sleutel (fallback) |
|---|---|---|
| Volledigheidscontrole (regels) | ✅ | ✅ |
| Historische acceptatiekans | ✅ | ✅ |
| Inhoudelijke AI-bevindingen | ✅ (Claude) | – |
| Tips | ✅ (AI, op maat) | ✅ (heuristisch) |

De statusindicator rechtsboven laat zien welke modus actief is.

---

## Hoe de score tot stand komt

1. **Regelcontrole** (`app/rules.py`) — toetst verplichte velden, locatie,
   omschrijving en per-activiteit **verplichte/aanbevolen bijlagen**. Elke
   bevinding krijgt een ernst: *blokkerend*, *waarschuwing* of *info*.
2. **Historische analyse** (`app/historical.py`) — zoekt vergelijkbare aanvragen
   (op activiteit, en indien mogelijk ook gemeente) en berekent het
   acceptatiepercentage en de meest voorkomende weigeringsredenen.
3. **AI-analyse** (`app/ai_review.py`) — stuurt de aanvraag + de relevante
   richtlijnen + de gevonden bevindingen naar Claude en vraagt om extra
   inhoudelijke bevindingen en tips (gestructureerde JSON-output).
4. **Score** (`app/checker.py`) — combineert een aftrekmodel op de bevindingen
   (70%) met de historische acceptatiekans (30%) tot een getal van 0–100.

---

## Projectstructuur

```
app/
  main.py        # FastAPI: serveert frontend + API (/api/meta, /api/check, /api/health)
  schemas.py     # Pydantic-modellen (Aanvraag, CheckResultaat, ...)
  knowledge.py   # Laadt kennisbank, bouwt richtlijnen-context voor de AI
  rules.py       # Deterministische volledigheids-/geldigheidsregels
  historical.py  # Statistiek over historische aanvragen
  ai_review.py   # Claude API-aanroep (adaptive thinking, prompt caching, JSON-output)
  checker.py     # Orkestratie + scoreberekening + fallback-tips
data/
  activiteiten.json          # Activiteiten + vereiste bijlagen + gekoppelde richtlijnen
  richtlijnen_nationaal.json # Omgevingswet, Bbl, Bal, natuur, erfgoed
  richtlijnen_lokaal.json    # Per gemeente: omgevingsplan, welstand, ...
  historie.json              # Voorbeeldset eerdere aanvragen met uitkomst
static/
  index.html, app.js, styles.css   # Frontend (vanilla, geen build-stap)
tests/
  test_rules.py, test_checker.py
```

---

## API

| Endpoint | Methode | Beschrijving |
|---|---|---|
| `/` | GET | De webapplicatie |
| `/api/meta` | GET | Activiteiten, bijlage-labels, gemeenten, AI-status |
| `/api/check` | POST | Controleert een `Aanvraag` (JSON) → `CheckResultaat` |
| `/api/health` | GET | Status + of AI beschikbaar is |

Voorbeeld:

```bash
curl -X POST http://127.0.0.1:8000/api/check \
  -H "Content-Type: application/json" \
  -d '{
    "aanvrager": {"naam": "Jan Jansen", "type": "particulier"},
    "locatie": {"adres": "Dorpsstraat 1", "postcode": "1234 AB", "gemeente": "Rotterdam"},
    "activiteiten": ["kappen"],
    "omschrijving": "Het vellen van een zieke kastanjeboom met herplant.",
    "bijlagen": ["situatietekening", "foto_boom"]
  }'
```

---

## Configuratie

| Variabele | Standaard | Toelichting |
|---|---|---|
| `ANTHROPIC_API_KEY` | – | Activeert de AI-analyse |
| `DSO_MODEL` | `claude-opus-4-8` | Te gebruiken Claude-model |
| `DSO_EFFORT` | `medium` | Denk-inspanning: `low` / `medium` / `high` / `max` |

---

## Eigen richtlijnen of historie toevoegen

De kennisbank zit volledig in `data/`. Voeg activiteiten, gemeenten,
richtlijnen of historische records toe als JSON — de app en de AI-context passen
zich automatisch aan. Zo kun je dit model vullen met de echte richtlijnen en
historische besluiten van jouw gemeente.
