"""Harness for the jsdom UI test: real FastAPI app + real web UI in local mode, with a fake LLM.

    cd api/tests/ui && npm install && python ui_server.py &   # then:  node run.js
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ["STORAGE"] = "local"
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
API = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(API), str(API / "tests")]

import uvicorn  # noqa: E402

from app.config import get_settings  # noqa: E402

s = get_settings()
s.data_dir = tempfile.mkdtemp()
s.burst_requests = 1000

from test_v3 import FakeLLM  # noqa: E402
import app.agents.engine as eng  # noqa: E402

eng.get_llm = lambda fast=False: FakeLLM()
from app.main import app  # noqa: E402

uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
