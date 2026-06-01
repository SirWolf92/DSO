#!/usr/bin/env bash
# SessionStart-hook: zorgt dat de Python-omgeving klaarstaat zodat tests en de
# server direct kunnen draaien in een (web)sessie. Idempotent en stil.
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"

if [ ! -d .venv ]; then
  "$PY" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# Installeer alleen als een kernpakket nog ontbreekt (scheelt tijd bij herstart).
if ! python -c "import fastapi, anthropic, pydantic" >/dev/null 2>&1; then
  pip install -q --disable-pip-version-check -r requirements.txt
fi

echo "DSO-omgeving klaar. Tests: 'source .venv/bin/activate && pytest -q'. Server: 'uvicorn app.main:app --reload'."
