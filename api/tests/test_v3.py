"""Offline tests for v3: uploads, per-company data, routing, chat flows, quotas, export, workspace."""
import io
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from app import catalog, identity, ingest, localdb, quota, router
from app import tenantdb as tdb
from app.config import get_settings


class FakeLLM:
    """Scripted agent: run_sql -> make_chart -> answer. Also plain-text calls (title/synthesis/suggestions)."""

    def bind_tools(self, tools):
        return self

    def invoke(self, prompt):
        return AIMessage(content="Sales Summary")

    def stream(self, messages):
        if isinstance(messages, str):
            yield AIMessageChunk(content="Combined answer.")
            return
        last = messages[-1]
        if isinstance(last, ToolMessage) and last.name == "run_sql":
            yield AIMessageChunk(content="", tool_call_chunks=[{
                "name": "make_chart", "id": "c2", "index": 0,
                "args": json.dumps({"chart_type": "bar", "title": "By region", "labels": ["N", "S"],
                                    "series": [{"name": "rev", "data": [1, 2]}]})}])
        elif isinstance(last, ToolMessage):
            yield AIMessageChunk(content="North leads. ")
            yield AIMessageChunk(content="Done.", usage_metadata={"input_tokens": 50, "output_tokens": 10, "total_tokens": 60})
        elif "SQL" in str(getattr(last, "content", "")) or True:
            yield AIMessageChunk(content="Checking.", tool_call_chunks=[{
                "name": "run_sql", "id": "c1", "index": 0,
                "args": json.dumps({"query": "SELECT region, SUM(amount) AS rev FROM sales GROUP BY region"})}])


SALES = "order_id,region,amount,order_date\n001,North,\"₹1,200\",05/01/2024\n002,South,\"₹800\",15/01/2024\n003,North,\"₹2,000\",20/02/2024\n"


@pytest.fixture()
def env(monkeypatch, tmp_path):
    s = get_settings()
    monkeypatch.setattr(s, "data_dir", str(tmp_path))
    monkeypatch.setattr(s, "storage", "local")
    monkeypatch.setattr(localdb, "_store", None)
    monkeypatch.setattr(identity, "_local_ready", False)
    tdb._vocab_cache.clear() if hasattr(tdb, "_vocab_cache") else None
    quota._hits.clear()
    from app.agents import engine
    monkeypatch.setattr(engine, "get_llm", lambda fast=False: FakeLLM())
    from app.main import app
    return TestClient(app)


def upload(c, name="sales.csv", data=SALES):
    return c.post("/v1/files", files=[("files", (name, data, "text/csv"))])


def events(resp):
    return [json.loads(l[6:]) for l in resp.text.split("\n\n") if l.startswith("data: ")]


# ------------------------------------------------------------------ catalog
def test_catalog_size_and_unique_ids():
    assert len(catalog.CATALOG) >= 70
    assert len({a.id for a in catalog.CATALOG}) == len(catalog.CATALOG)
    assert catalog.DEFAULT_AGENT in catalog.BY_ID


# ------------------------------------------------------------------- ingest
def test_cleaning_amounts_dates_ids():
    (_, df, _), = ingest.parse_tabular("sales.csv", SALES.encode())
    assert float(df["amount"].sum()) == 4000.0
    assert list(df["order_id"]) == ["001", "002", "003"]          # leading zeros preserved
    assert str(df["order_date"].iloc[0])[:10] == "2024-01-05"     # dd/mm


def test_excel_multisheet_and_json():
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as w:
        pd.DataFrame({"A Col": [1, 2]}).to_excel(w, sheet_name="Jan", index=False)
        pd.DataFrame({"B Col": [3]}).to_excel(w, sheet_name="Feb", index=False)
    assert len(ingest.parse_tabular("book.xlsx", buf.getvalue())) == 2
    (_, df, _), = ingest.parse_tabular("x.json", b'[{"a":1,"b":"x"},{"a":2,"b":"y"}]')
    assert len(df) == 2


def test_unsupported_and_empty(env):
    r = env.post("/v1/files", files=[("files", ("a.exe", b"zz", "application/octet-stream"))]).json()
    assert r["results"][0]["status"] == "error"


# -------------------------------------------------------------- files + sql
def test_upload_list_preview_delete(env):
    r = upload(env).json()["results"][0]
    assert r["status"] == "ok" and r["tables"][0]["rows"] == 3
    files = env.get("/v1/files").json()
    assert files[0]["name"] == "sales"
    d = env.get(f"/v1/files/{files[0]['id']}").json()
    assert len(d["preview"]["rows"]) == 3
    assert env.delete(f"/v1/files/{files[0]['id']}").status_code == 200
    assert env.get("/v1/files").json() == []


def test_reupload_replaces(env):
    upload(env); upload(env)
    assert len(env.get("/v1/files").json()) == 1


def test_sql_sandbox(env):
    upload(env)
    tid = identity.LOCAL_TENANT
    assert tdb.run_query(tid, "SELECT SUM(amount) s FROM sales")["rows"][0][0] == 4000
    for bad in ("DROP TABLE sales", "SELECT * FROM read_csv('/etc/passwd')", "COPY sales TO '/tmp/x.csv'",
                "ATTACH '/tmp/x.db'", "SELECT 1; SELECT 2", "INSERT INTO sales VALUES (1)"):
        with pytest.raises(Exception):
            tdb.run_query(tid, bad)


def test_tenant_isolation(env):
    upload(env)
    with pytest.raises(Exception):
        tdb.run_query("other-tenant", "SELECT * FROM sales")


def test_export(env):
    upload(env)
    r = env.post("/v1/export", json={"sql": "SELECT region, SUM(amount) a FROM sales GROUP BY region", "format": "csv"})
    assert r.status_code == 200 and "North" in r.text
    r = env.post("/v1/export", json={"sql": "SELECT * FROM sales", "format": "xlsx"})
    assert r.content[:2] == b"PK"
    assert env.post("/v1/export", json={"sql": "DROP TABLE sales"}).status_code == 400


# ----------------------------------------------------------------- planner
def test_planner():
    vocab = {"sales", "amount", "region"}
    p = router.plan("hello", vocab, False, {"sales"})
    assert p["mode"] == "chat"
    p = router.plan("total sales by region", vocab, False, {"sales"})
    assert p["mode"] == "simple" and len(p["agents"]) == 1
    p = router.plan("full review of sales: forecast next quarter, find anomalies and recommend actions", vocab, False, {"sales"})
    assert p["mode"] == "complex" and 2 <= len(p["agents"]) <= 4
    assert router.plan("anything", vocab, False, {"sales"}, force_complex=True)["mode"] == "complex"


# -------------------------------------------------------------------- chat
def test_simple_chat_flow(env):
    upload(env)
    r = env.post("/v1/chat", json={"message": "total sales by region", "agent_id": "auto"})
    ev = events(r)
    types = [e["type"] for e in ev]
    assert types[0] == "start" and "tool_start" in types and "chart" in types and "done" in types
    meta = next(e for e in ev if e["type"] == "meta")
    assert meta["mode"] in ("simple", "fixed")
    assert any(e["type"] == "title" and e["title"] == "Sales Summary" for e in ev)
    cid = ev[0]["conversation_id"]
    msgs = env.get(f"/v1/conversations/{cid}").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert "North leads" in msgs[1]["content"] and msgs[1]["meta"]["charts"]


def test_team_mode_parallel(env):
    upload(env)
    r = env.post("/v1/chat", json={"message": "complete analysis of sales", "agent_id": "team"})
    ev = events(r)
    types = [e["type"] for e in ev]
    assert "team_agent" in types and "team_synthesis" in types and types[-2:] != ["error"]
    assert next(e for e in ev if e["type"] == "meta")["mode"] == "complex"
    assert "Combined answer." in "".join(e.get("text", "") for e in ev if e["type"] == "delta")
    assert "error" not in types


def test_greeting_no_tools(env):
    ev = events(env.post("/v1/chat", json={"message": "hello"}))
    assert next(e for e in ev if e["type"] == "meta")["mode"] == "chat"


def test_attachment_note_and_meta(env):
    upload(env)
    fid = env.get("/v1/files").json()[0]["id"]
    ev = events(env.post("/v1/chat", json={"message": "check this", "file_ids": [fid]}))
    cid = ev[0]["conversation_id"]
    m = env.get(f"/v1/conversations/{cid}").json()["messages"][0]
    assert m["meta"]["files"][0]["name"] == "sales.csv"


def test_regenerate_edit_rename_delete_feedback(env):
    upload(env)
    ev = events(env.post("/v1/chat", json={"message": "total sales by region"}))
    cid, uid = ev[0]["conversation_id"], ev[0]["user_message_id"]
    events(env.post("/v1/chat", json={"conversation_id": cid, "regenerate": True}))
    msgs = env.get(f"/v1/conversations/{cid}").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    events(env.post("/v1/chat", json={"conversation_id": cid, "edit_message_id": uid, "message": "sales by month"}))
    msgs = env.get(f"/v1/conversations/{cid}").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"] and msgs[0]["content"] == "sales by month"
    aid = msgs[1]["id"]
    assert env.post(f"/v1/messages/{aid}/feedback", json={"value": "up"}).status_code == 200
    assert env.get(f"/v1/conversations/{cid}").json()["messages"][1]["meta"]["feedback"] == "up"
    assert env.patch(f"/v1/conversations/{cid}", json={"title": "Renamed"}).status_code == 200
    assert env.delete(f"/v1/conversations/{cid}").status_code == 200
    assert env.get(f"/v1/conversations/{cid}").status_code == 404


def test_unknown_agent_and_empty(env):
    assert env.post("/v1/chat", json={"message": "x", "agent_id": "nope"}).status_code == 400
    assert env.post("/v1/chat", json={"message": ""}).status_code == 400


def test_quota_429(env, monkeypatch):
    monkeypatch.setattr(get_settings(), "pro_daily_messages", 2)
    monkeypatch.setattr(get_settings(), "burst_requests", 100)
    for _ in range(2):
        assert env.post("/v1/chat", json={"message": "hello"}).status_code == 200
    r = env.post("/v1/chat", json={"message": "hello"})
    assert r.status_code == 429 and r.json()["detail"]["code"] == "quota"
    assert env.get("/v1/usage").json()["used"] == 2


def test_burst_rate_limit(env, monkeypatch):
    monkeypatch.setattr(get_settings(), "burst_requests", 2)
    codes = [env.post("/v1/chat", json={"message": "hello"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# --------------------------------------------------------------- workspace
def test_me_settings_suggestions(env):
    me = env.get("/v1/me").json()
    assert me["mode"] == "local" and me["tenant"]["plan"] == "pro"
    env.put("/v1/settings", json={"about": "I run a shop", "style": "short"})
    assert env.get("/v1/settings").json()["about"] == "I run a shop"
    assert env.get("/v1/suggestions").json()["has_data"] is False
    upload(env)
    s = env.get("/v1/suggestions").json()
    assert s["has_data"] and len(s["questions"]) >= 3


def test_team_features_need_supabase(env):
    assert env.post("/v1/workspace/invites").status_code == 400


def test_config_and_agents_and_ui(env):
    assert env.get("/v1/config").json()["storage"] == "local"
    a = env.get("/v1/agents").json()
    assert len(a["agents"]) >= 70
    assert env.get("/").status_code == 200
