"""Workspace, settings, usage, members/invites, feedback, suggestions and exports."""
import csv
import io
import json
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import db, quota
from . import tenantdb as tdb
from .agents import engine
from .config import get_settings
from .identity import Identity, get_identity, invalidate_identity_cache

log = logging.getLogger("workspace")
api = APIRouter(prefix="/v1")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _need_admin(ident: Identity) -> None:
    if not ident.is_admin:
        raise HTTPException(403, "Only workspace owners and admins can do this")


def _need_team_mode() -> None:
    if db.is_local():
        raise HTTPException(400, "Workspaces with multiple members need Supabase mode (STORAGE=supabase).")


# ------------------------------------------------------------------------ me
@api.get("/me")
def me(ident: Identity = Depends(get_identity)):
    t = db.table("tenants").select("id,name,plan").eq("id", ident.tenant_id).limit(1).execute().data
    s = get_settings()
    return {"email": ident.email, "role": ident.role, "mode": s.storage,
            "workspace_enabled": not db.is_local(),
            "tenant": t[0] if t else {"id": ident.tenant_id, "name": "Workspace", "plan": "starter"},
            "usage": quota.usage(ident),
            "limits": {"max_upload_mb": s.max_upload_mb, "max_table_rows": s.max_table_rows}}


@api.get("/usage")
def get_usage(ident: Identity = Depends(get_identity)):
    return quota.usage(ident)


# ------------------------------------------------------- custom instructions
class SettingsIn(BaseModel):
    about: str = Field("", max_length=1500)
    style: str = Field("", max_length=1500)


@api.get("/settings")
def get_settings_api(ident: Identity = Depends(get_identity)):
    rows = (db.table("user_settings").select("*").eq("tenant_id", ident.tenant_id)
            .eq("owner", ident.owner).limit(1).execute().data)
    r = rows[0] if rows else {}
    return {"about": r.get("about", ""), "style": r.get("style", "")}


@api.put("/settings")
def put_settings(body: SettingsIn, ident: Identity = Depends(get_identity)):
    db.table("user_settings").upsert(
        {"tenant_id": ident.tenant_id, "owner": ident.owner, "about": body.about, "style": body.style,
         "updated_at": _now().isoformat()}, on_conflict="tenant_id,owner").execute()
    return {"ok": True}


def load_instructions(ident: Identity) -> str:
    s = get_settings_api(ident)
    parts = []
    if s["about"].strip():
        parts.append("About the user: " + s["about"].strip())
    if s["style"].strip():
        parts.append("How to respond: " + s["style"].strip())
    return "\n".join(parts)


# ------------------------------------------------------- workspace / members
class WorkspaceIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


@api.put("/workspace")
def rename_workspace(body: WorkspaceIn, ident: Identity = Depends(get_identity)):
    _need_admin(ident)
    db.table("tenants").update({"name": body.name.strip()}).eq("id", ident.tenant_id).execute()
    return {"ok": True}


@api.get("/workspace/members")
def members(ident: Identity = Depends(get_identity)):
    _need_team_mode()
    rows = db.table("tenant_members").select("*").eq("tenant_id", ident.tenant_id).execute().data
    return [{"user_id": r["user_id"], "email": r.get("email"), "role": r.get("role"),
             "joined_at": r.get("joined_at")} for r in rows]


@api.delete("/workspace/members/{user_id}")
def remove_member(user_id: str, ident: Identity = Depends(get_identity)):
    _need_team_mode()
    _need_admin(ident)
    rows = db.table("tenant_members").select("*").eq("tenant_id", ident.tenant_id).eq("user_id", user_id).execute().data
    if not rows:
        raise HTTPException(404, "Member not found")
    if rows[0].get("role") == "owner":
        raise HTTPException(400, "The owner cannot be removed")
    db.table("tenant_members").delete().eq("tenant_id", ident.tenant_id).eq("user_id", user_id).execute()
    invalidate_identity_cache()
    return {"ok": True}


@api.post("/workspace/invites")
def create_invite(ident: Identity = Depends(get_identity)):
    _need_team_mode()
    _need_admin(ident)
    token = secrets.token_urlsafe(16)
    exp = (_now() + timedelta(days=7)).isoformat()
    db.table("invites").insert({"token": token, "tenant_id": ident.tenant_id, "role": "member",
                                "created_by": ident.owner, "expires_at": exp, "uses": 0}).execute()
    return {"token": token, "expires_at": exp, "path": f"/?join={token}"}


class JoinIn(BaseModel):
    token: str


@api.post("/workspace/join")
def join_workspace(body: JoinIn, ident: Identity = Depends(get_identity)):
    _need_team_mode()
    if ident.owner in ("apikey", "dev"):
        raise HTTPException(400, "Sign in with a user account to join a workspace")
    rows = db.table("invites").select("*").eq("token", body.token.strip()).limit(1).execute().data
    inv = rows[0] if rows else None
    if not inv or str(inv["expires_at"]) < _now().isoformat() or int(inv.get("uses") or 0) >= 25:
        raise HTTPException(400, "This invite link is invalid or has expired")
    already = db.table("tenant_members").select("*").eq("tenant_id", inv["tenant_id"]).eq("user_id", ident.owner).execute().data
    if not already:
        db.table("tenant_members").insert({"tenant_id": inv["tenant_id"], "user_id": ident.owner,
                                           "role": inv.get("role", "member"), "email": ident.email,
                                           "joined_at": _now().isoformat()}).execute()
        db.table("invites").update({"uses": int(inv.get("uses") or 0) + 1}).eq("token", inv["token"]).execute()
    else:  # re-opening the link: make this the active workspace
        db.table("tenant_members").update({"joined_at": _now().isoformat()}).eq(
            "tenant_id", inv["tenant_id"]).eq("user_id", ident.owner).execute()
    invalidate_identity_cache()
    t = db.table("tenants").select("id,name").eq("id", inv["tenant_id"]).limit(1).execute().data
    return {"ok": True, "tenant": t[0] if t else {"id": inv["tenant_id"]}}


# ------------------------------------------------------------------ feedback
class FeedbackIn(BaseModel):
    value: Optional[Literal["up", "down"]] = None


@api.post("/messages/{message_id}/feedback")
def feedback(message_id: str, body: FeedbackIn, ident: Identity = Depends(get_identity)):
    msg = db.table("messages").select("*").eq("id", message_id).eq("tenant_id", ident.tenant_id).limit(1).execute().data
    if not msg:
        raise HTTPException(404, "Message not found")
    conv = (db.table("conversations").select("owner").eq("id", msg[0]["conversation_id"]).limit(1).execute().data)
    if not conv or conv[0]["owner"] != ident.owner:
        raise HTTPException(404, "Message not found")
    meta = dict(msg[0].get("meta") or {})
    if body.value:
        meta["feedback"] = body.value
    else:
        meta.pop("feedback", None)
    db.table("messages").update({"meta": meta}).eq("id", message_id).execute()
    return {"ok": True}


# --------------------------------------------------------------- suggestions
_GENERIC = [
    "What can you do with my data?",
    "Summarize my data and show the 5 most important insights",
    "Draft a polite follow-up email to a customer",
    "Explain GST input credit in simple words",
]
_sugg_cache: dict[str, tuple[tuple, list[str]]] = {}


def _heuristic(tables: list[dict]) -> list[str]:
    t = tables[0]
    cols = t.get("columns") or []
    num = [c["name"] for c in cols if tdb._is_num(c["type"]) and not re.search(r"(^|_)(id|code|no|number)$", c["name"])]
    cat = [c["name"] for c in cols if "VARCHAR" in c["type"].upper() and 1 < (c.get("distinct") or 0) <= 30]
    dat = [c["name"] for c in cols if tdb._is_date(c["type"])]
    out = [f"Give me a quick summary of {t['name']}: the key numbers and what stands out"]
    if dat and num:
        out.append(f"Show the monthly trend of {num[0]} with a chart")
    if cat and num:
        out.append(f"Which {cat[0]} has the highest total {num[0]}? Show a chart")
    out.append(f"Check the data quality of {t['name']}")
    return out[:4]


@api.get("/suggestions")
def suggestions(ident: Identity = Depends(get_identity)):
    tables = tdb.sources(ident.tenant_id, "table")
    if not tables:
        return {"has_data": False, "questions": _GENERIC}
    sig = tuple((t["name"], t.get("rows")) for t in tables)
    hit = _sugg_cache.get(ident.tenant_id)
    if hit and hit[0] == sig:
        return {"has_data": True, "questions": hit[1]}
    questions = _heuristic(tables)
    try:
        prompt = ("Here is a company's data schema:\n" + tdb.schema_text(ident.tenant_id, max_chars=5000) +
                  "\n\nWrite 4 short, specific questions a business owner would ask about THIS data, each answerable "
                  "with SQL. Use real column names. Reply with ONLY a JSON array of 4 strings.")
        resp = engine.get_llm(fast=True).invoke(prompt)
        text = resp.content if isinstance(resp.content, str) else "".join(
            b.get("text", "") for b in resp.content if isinstance(b, dict))
        m = re.search(r"\[.*\]", text, re.S)
        arr = [x for x in json.loads(m.group()) if isinstance(x, str)][:4] if m else []
        if len(arr) >= 3:
            questions = arr
    except Exception:
        log.info("LLM suggestions unavailable, using heuristics")
    _sugg_cache[ident.tenant_id] = (sig, questions)
    return {"has_data": True, "questions": questions}


# -------------------------------------------------------------------- export
class ExportIn(BaseModel):
    sql: str = Field(..., min_length=5, max_length=20000)
    format: Literal["csv", "xlsx"] = "csv"


@api.post("/export")
def export(body: ExportIn, ident: Identity = Depends(get_identity)):
    try:
        res = tdb.run_query(ident.tenant_id, body.sql, limit=get_settings().export_row_limit)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, str(e))
    if body.format == "xlsx":
        from openpyxl import Workbook

        wb = Workbook(write_only=True)
        ws = wb.create_sheet("Result")
        ws.append(res["columns"])
        for r in res["rows"]:
            ws.append(r)
        buf = io.BytesIO()
        wb.save(buf)
        return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": 'attachment; filename="result.xlsx"'})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(res["columns"])
    w.writerows(res["rows"])
    return Response(("﻿" + buf.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="result.csv"'})
