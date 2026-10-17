#!/usr/bin/env bash
# One-command local run (Mac/Linux). Needs Python 3.10+.
set -e
cd "$(dirname "$0")/api"
[ -f .env ] || { cp ../.env.local.example .env; echo ">> Created api/.env. Open it, paste your ANTHROPIC_API_KEY, then run this script again."; exit 0; }
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
echo ">> Open http://localhost:8000"
exec uvicorn app.main:app --host 127.0.0.1 --port 8000
