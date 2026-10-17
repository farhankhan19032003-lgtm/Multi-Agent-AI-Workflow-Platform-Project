@echo off
REM One-command local run (Windows). Needs Python 3.10+ from python.org.
cd /d "%~dp0api"
if not exist .env (
  copy ..\.env.local.example .env >nul
  echo Created api\.env. Open it, paste your ANTHROPIC_API_KEY, then run this file again.
  pause
  exit /b
)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
echo Open http://localhost:8000
uvicorn app.main:app --host 127.0.0.1 --port 8000
