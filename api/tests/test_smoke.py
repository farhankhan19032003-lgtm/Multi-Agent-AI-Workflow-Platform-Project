"""Offline smoke tests: in-memory fake Supabase + fake LLM, no network needed.

Run from the api/ folder:  python -m pytest tests -q
"""
import os
import uuid
from datetime import date

os.environ.setdefault("SUPABASE_URL", "http://fake.supabase.local")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "fake")
os.environ.setdefault("MLFLOW_TRACKING_URI", "file:/tmp/agent-factory-test-mlruns")

import pytest
from fastapi.testclient import TestClient

from app import db, quality
from app.auth import hash_key


class _Res:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    """Tiny subset of the supabase-py query builder used by the app."""

    def __init__(self, store, name):
        self.store, self.name = store, name
        self.filters, self._op, self._payload, self._limit, self._kw = [], "select", None, None, {}

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val)); return self

    def gte(self, col, val):
        self.filters.append(("gte", col, val)); return self

    def order(self, *_a, **_k):
        return self

    def limit(self, n):
        self._limit = n; return self

    def insert(self, payload):
        self._op, self._payload = "insert", payload; return self

    def update(self, payload):
        self._op, self._payload = "update", payload; return self

    def upsert(self, payload, **kw):
        self._op, self._payload, self._kw = "upsert", payload, kw; return self

    def delete(self):
        self._op = "delete"; return self

    @staticmethod
    def _get(row, col):
        cur = row
        for part in col.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        return cur

    def _match(self, row):
        for kind, col, val in self.filters:
            v = self._get(row, col)
            if kind == "eq" and v != val:
                return False
            if kind == "gte" and (v is None or str(v) < str(val)):
                return False
        return True

    def execute(self):
        rows = self.store.setdefault(self.name, [])
        items = self._payload if isinstance(self._payload, list) else [self._payload]
        if self._op == "insert":
            out = [{"id": str(uuid.uuid4()), **it} for it in items]
            rows.extend(out)
            return _Res(out)
        if self._op == "delete":
            gone = [r for r in rows if self._match(r)]
            self.store[self.name] = [r for r in rows if r not in gone]
            return _Res(gone)
        if self._op == "update":
            out = [r for r in rows if self._match(r)]
            for r in out:
                r.update(self._payload)
            return _Res(out)
        if self._op == "upsert":
            conflict = self._kw.get("on_conflict", "id").split(",")
            for it in items:
                existing = next((r for r in rows if all(r.get(c) == it.get(c) for c in conflict)), None)
                if existing is None:
                    rows.append({"id": str(uuid.uuid4()), **it})
                elif not self._kw.get("ignore_duplicates"):
                    existing.update(it)
            return _Res(items)
        out = [r for r in rows if self._match(r)]
        return _Res(out[: self._limit] if self._limit else out)


class FakeLLM:
    def invoke(self, messages):
        system = messages[0][1]
        if "executive briefings" in system:
            text = (
                "# Plant Performance Briefing\n## Summary\nStable week.\n"
                "## Key Findings\n- Line-1 led.\n## Risks\n- Jams.\n"
                "## Recommended Actions\n- Inspect feeder.\n## Sources\n- none"
            )
        elif "manufacturing operations analyst" in system:
            text = "Line-1 outperformed Line-2; machine jams drove most downtime."
        else:
            text = "Notes from general knowledge."
        return type("M", (), {"content": text, "usage_metadata": {"input_tokens": 10, "output_tokens": 5}})()


TENANT = "11111111-1111-1111-1111-111111111111"
API_KEY = "test-key"


@pytest.fixture()
def client(monkeypatch):
    today = date.today().isoformat()
    store = {
        "api_keys": [{"id": "k1", "tenant_id": TENANT, "key_hash": hash_key(API_KEY), "active": True}],
        "factory_daily_kpis": [
            {"tenant_id": TENANT, "plant": "Jaipur Plant", "line_name": "Line-1", "shift_date": today,
             "units_produced": 3300, "units_defective": 150, "defect_rate_pct": 4.55,
             "downtime_minutes": 60, "target_attainment_pct": 92.0},
            {"tenant_id": TENANT, "plant": "Jaipur Plant", "line_name": "Line-2", "shift_date": today,
             "units_produced": 2000, "units_defective": 20, "defect_rate_pct": 1.0,
             "downtime_minutes": 20, "target_attainment_pct": 74.0},
        ],
        "production_metrics": [
            {"tenant_id": TENANT, "shift_date": today, "downtime_minutes": 40,
             "downtime_reason": "Machine jam", "factory_lines": {"plant": "Jaipur Plant", "line_name": "Line-1"}},
        ],
    }
    monkeypatch.setattr(db, "table", lambda name: FakeQuery(store, name))
    monkeypatch.setattr("app.agents.base.init_chat_model", lambda *a, **k: FakeLLM())
    from app.main import app

    c = TestClient(app)
    c.store = store
    c.headers.update({"X-API-Key": API_KEY})
    return c


def test_health_and_auth(client):
    assert client.get("/health").json() == {"status": "ok"}
    bad = client.post("/v1/workflows/research", json={"query": "test"}, headers={"X-API-Key": "nope"})
    assert bad.status_code == 401


def test_factory_report_end_to_end(client):
    r = client.post("/v1/workflows/factory-report", json={"plant": "Jaipur Plant", "days": 7})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "succeeded"
    out = body["output"]
    assert out["kpis"]["total_units_produced"] == 5300
    assert out["alerts"], "defect and below-target anomalies should be flagged"
    assert out["quality"]["structure"] == 1.0

    run = client.get(f"/v1/runs/{body['run_id']}").json()
    assert [s["agent_kind"] for s in run["steps"]] == ["analytics", "summarizer"]
    assert any(m["metric"] == "grounding" for m in run["quality"])
    assert client.store["agent_memory"][0]["key"] == "last_summary"
    assert len(client.store["reports"]) == 1


def test_background_run_and_research(client):
    r = client.post("/v1/workflows/research", json={"query": "CNC maintenance trends", "background": True})
    assert r.json()["status"] == "running"
    runs = client.get("/v1/runs").json()
    assert runs and runs[0]["workflow"] == "research"


def test_ingest_metrics(client):
    payload = {"metrics": [{"plant": "P1", "line_name": "L1", "shift_date": "2026-10-15", "shift": "A",
                            "units_produced": 100, "units_defective": 2}]}
    assert client.post("/v1/ingest/production-metrics", json=payload).json() == {"upserted": 1}
    # idempotent re-send
    client.post("/v1/ingest/production-metrics", json=payload)
    assert len([m for m in client.store["production_metrics"] if m.get("line_id")]) == 1


def test_quality_helpers():
    assert quality.structure_score("## Summary\n## Risks", ["Summary", "Risks", "Actions"]) == pytest.approx(2 / 3)
    assert quality.grounding_score("Defect rate 4.55%", "defect_rate_pct: 4.55") == 1.0
    assert quality.grounding_score("Defect rate 9.99%", "defect_rate_pct: 4.55") == 0.0
    assert quality.citation_score("see https://a.com and https://b.com") == 1.0
