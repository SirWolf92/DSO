"""FastAPI-applicatie: serveert de frontend en de controle-API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import ai_review, checker
from .knowledge import meta
from .schemas import Aanvraag, CheckResultaat

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="DSO Aanvraag Checker",
    description=(
        "Controleer je DSO-/Omgevingswet-aanvraag met AI, historische data en "
        "nationale + lokale richtlijnen voordat je indient."
    ),
    version="1.0.0",
)


@app.get("/api/health")
def health() -> dict:
    """Statuscheck; laat zien of de AI-analyse beschikbaar is."""
    return {"status": "ok", "ai_beschikbaar": ai_review.beschikbaar()}


@app.get("/api/meta")
def get_meta() -> dict:
    """Metadata voor de frontend: activiteiten, bijlagen, gemeenten."""
    data = meta()
    data["ai_beschikbaar"] = ai_review.beschikbaar()
    return data


@app.post("/api/check", response_model=CheckResultaat)
def post_check(aanvraag: Aanvraag) -> CheckResultaat:
    """Controleert een aanvraag en geeft score, bevindingen en tips terug."""
    return checker.check(aanvraag)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# Statische bestanden (js/css) op /static.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
