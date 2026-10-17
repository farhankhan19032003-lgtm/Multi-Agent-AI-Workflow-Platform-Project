"""Chat API (ChatGPT-style): conversations, streaming answers, simple vs team routing."""
import json
import logging
import queue
import re
import threading
from datetime import datetime, timezone
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import db, quota, router
from . import tenantdb as tdb
from .agents import engine
from .catalog import BY_ID, CATALOG, CATEGORIES, DEFAULT_AGENT, public_view
from .config import get_settings
from .identity import Identity, get_identity
from .tools import ToolContext
from .workspace import load_instructions

log = logging.getLogger("chat")
api = APIRouter(prefix="/v1")

GREETING = re.compile(r"^\s*(hi+|hello+|hey+|namaste|namaskar|thanks?( you)?|thank u|ok(ay)?|good (morning|evening|night)|"
                      r"shukriya|dhanyavaad|bye)\W*$", re.I)


class ChatRequest(BaseModel):
    message: str = Field("", max_length=12000)
    conversation_id: Optional[str] = None
    agent_id: str = "auto"                       # "auto" | "team" | any catalog id
    regenerate: bool = False
    edit_message_id: Optional[str] = None        # edit & resend an earlier user message
    file_ids: list[str] = Field(default_factory=list)   # data-library files attached to this message
    images: list[str] = Field(default_factory=list)     # data URLs (not stored)


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


# ----------------------------------------------------------------- public info
@api.get("/config")
def public_config():
    s = get_settings()
    return {"app": "Agent Factory", "storage": s.storage, "dev_no_auth": s.dev_no_auth or s.storage == "local",
            "supabase_url": s.supabase_url if s.storage == "supabase" else "",
            "supabase_anon_key": s.supabase_anon_key if s.storage == "supabase" else "",
            "workspace_enabled": s.storage == "supabase"}


@api.get("/agents")
def list_agents(_: Identity = Depends(get_identity)):
    return {"agents": [public_view(a) for a in CATALOG], "categories": CATEGORIES, "default": DEFAULT_AGENT}


# --------------------------------------------------------------- conversations
def _own(ident: Identity, conv_id: str) -> dict:
    rows = (db.table("conversations").select("*").eq("id", conv_id).eq("tenant_id", ident.tenant_id)
            .eq("owner", ident.owner).limit(1).execute().data)
    if not rows:
        raise HTTPException(404, "Conversation not found")
    return rows[0]


@api.get("/conversations")
def list_conversations(ident: Identity = Depends(get_identity)):
    return (db.table("conversations").select("id,title,agent_id,updated_at")
            .eq("tenant_id", ident.tenant_id).eq("owner", ident.owner)
            .order("updated_at", desc=True).limit(200).execute().data)


@api.get("/conversations/{conv_id}")
def get_conversation(conv_id: str, ident: Identity = Depends(get_identity)):
    conv = _own(ident, conv_id)
    msgs = (db.table("messages").select("id,role,content,meta,created_at")
            .eq("conversation_id", conv_id).order("created_at").execute().data)
    return {"conversation": conv, "messages": msgs}


@api.patch("/conversations/{conv_id}")
def rename_conversation(conv_id: str, body: RenameRequest, ident: Identity = Depends(get_identity)):
    _own(ident, conv_id)
    db.table("conversations").update({"title": body.title.strip()}).eq("id", conv_id).execute()
    return {"ok": True}


@api.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str, ident: Identity = Depends(get_identity)):
    _own(ident, conv_id)
    db.table("messages").delete().eq("conversation_id", conv_id).execute()
    db.table("conversations").delete().eq("id", conv_id).execute()
    return {"ok": True}


# ------------------------------------------------------------------------ chat
def _agent_info(spec) -> dict:
    return {"id": spec.id, "name": spec.name, "icon": spec.icon, "category": spec.category}


def _team_events(agent_ids: list[str], history: list, message: str, tenant_id: str,
                 instructions: str, images: list[str]) -> Iterator[dict]:
    """Run the specialist agents IN PARALLEL, stream their tool activity, then synthesise one answer."""
    q: queue.Queue = queue.Queue()
    findings: dict[str, str] = {}
    steps = get_settings().team_agent_steps

    def worker(aid: str) -> None:
        spec, ctx, text = BY_ID[aid], ToolContext(tenant_id), ""
        try:
            for ev in engine.stream_agent(spec, history, message, ctx, images=images,
                                          instructions=instructions, max_steps=steps):
                if ev["type"] == "delta":
                    text += ev["text"]
                else:
                    if "id" in ev:
                        ev = {**ev, "id": f"{aid}:{ev['id']}"}
                    q.put({**ev, "agent": aid})
            findings[aid] = text.strip()
        except Exception as e:  # noqa: BLE001
            log.exception("team agent %s failed", aid)
            findings[aid] = f"(this agent failed: {e})"
        finally:
            q.put({"type": "_done", "agent": aid})

    for aid in agent_ids:
        yield {"type": "team_agent", "agent": _agent_info(BY_ID[aid])}
        threading.Thread(target=worker, args=(aid,), daemon=True).start()
    remaining = len(agent_ids)
    while remaining:
        ev = q.get()
        if ev["type"] == "_done":
            remaining -= 1
            yield {"type": "team_agent_done", "agent": _agent_info(BY_ID[ev["agent"]])}
        else:
            yield ev

    yield {"type": "team_synthesis"}
    body = "\n\n".join(f"### {BY_ID[a].name}\n{findings.get(a, '')}" for a in agent_ids)
    prompt = (
        "You are the lead analyst. Combine the specialist findings below into ONE clear, well-structured "
        "answer to the user's question. Keep every number exactly as the specialists reported it, merge "
        "overlaps, flag disagreements, and finish with a short recommended next step. Reply in the user's "
        f"language.\n\nQUESTION: {message}\n\nSPECIALIST FINDINGS:\n{body}")
    for chunk in engine.get_llm().stream(prompt):
        t = engine._chunk_text(chunk)
        if t:
            yield {"type": "delta", "text": t}


def _decide(choice: str, message: str, ident: Identity) -> dict:
    tid = ident.tenant_id
    if choice in BY_ID:
        return {"mode": "fixed", "agents": [choice], "reason": ""}
    srcs = tdb.sources(tid)
    names = {s["name"] for s in srcs if s.get("kind") == "table"}
    has_docs = any(s.get("kind") == "document" for s in srcs)
    return router.plan(message, tdb.vocabulary(tid), has_docs, names, force_complex=(choice == "team"))


def _turn_events(plan: dict, history: list, message: str, ctx: ToolContext, instructions: str,
                 images: list[str], routed: bool) -> Iterator[dict]:
    agents = plan["agents"]
    if plan["mode"] == "complex":
        specs = [BY_ID[a] for a in agents]
        yield {"type": "meta", "mode": "complex", "routed": routed, "reason": plan["reason"],
               "agent": {"id": "team", "name": f"Team of {len(specs)} agents", "icon": "🧑‍🤝‍🧑",
                         "category": "Multi-agent"},
               "team": [_agent_info(s) for s in specs]}
        yield from _team_events(agents, history, message, ctx.tenant_id, instructions, images)
        return
    spec = BY_ID[agents[0]]
    yield {"type": "meta", "mode": plan["mode"], "routed": routed, "reason": plan["reason"],
           "agent": _agent_info(spec)}
    fast = plan["mode"] == "chat" and bool(GREETING.match(message)) and not images
    yield from engine.stream_agent(spec, history, message, ctx, images=images, instructions=instructions, fast=fast)


def _attach_note(ident: Identity, file_ids: list[str]) -> tuple[str, list[dict]]:
    if not file_ids:
        return "", []
    rows = [s for s in tdb.sources(ident.tenant_id) if s["id"] in set(file_ids)]
    lines, meta = [], []
    for s in rows:
        if s.get("kind") == "document":
            lines.append(f"document `{s['filename']}` (searchable with search_documents)")
        else:
            lines.append(f"table `{s['name']}` from {s.get('filename')} "
                         f"({int(s.get('rows') or 0):,} rows, {len(s.get('columns') or [])} columns)")
        meta.append({"id": s["id"], "name": s.get("filename") or s["name"], "kind": s.get("kind")})
    note = "[The user just attached: " + "; ".join(lines) + ". Inspect it before answering.]" if lines else ""
    return note, meta


def _make_title(question: str, answer: str) -> Optional[str]:
    try:
        resp = engine.get_llm(fast=True).invoke(
            "Write a 3 to 6 word title for this chat. No quotes, no trailing punctuation.\n\n"
            f"User: {question[:400]}\nAssistant: {answer[:400]}")
        text = resp.content if isinstance(resp.content, str) else "".join(
            b.get("text", "") for b in resp.content if isinstance(b, dict))
        title = re.sub(r"[\"'*#\n]", "", text).strip().rstrip(".")
        return title[:60] or None
    except Exception:  # noqa: BLE001
        return None


@api.post("/chat")
def chat(body: ChatRequest, ident: Identity = Depends(get_identity)):
    if body.agent_id not in BY_ID and body.agent_id not in ("auto", "team"):
        raise HTTPException(400, f"Unknown agent '{body.agent_id}'")
    text = body.message.strip()
    if not text and not body.file_ids and not body.images and not body.regenerate:
        raise HTTPException(400, "Message is empty")
    images = [i for i in body.images[:4] if isinstance(i, str) and i.startswith("data:image/") and len(i) < 8_000_000]
    quota.rate_limit(ident)

    is_new = body.conversation_id is None
    if is_new:
        title = " ".join((text or "New chat").split())[:48]
        conv = db.table("conversations").insert({
            "tenant_id": ident.tenant_id, "owner": ident.owner, "title": title,
            "agent_id": body.agent_id}).execute().data[0]
        msgs: list[dict] = []
    else:
        conv = _own(ident, body.conversation_id)
        msgs = (db.table("messages").select("id,role,content,meta").eq("conversation_id", conv["id"])
                .order("created_at").execute().data)

    insert_user = True
    if body.edit_message_id:
        idx = next((i for i, m in enumerate(msgs) if m["id"] == body.edit_message_id and m["role"] == "user"), None)
        if idx is None:
            raise HTTPException(400, "Message to edit not found")
        for m in msgs[idx:]:
            db.table("messages").delete().eq("id", m["id"]).execute()
        msgs = msgs[:idx]
    elif body.regenerate:
        if msgs and msgs[-1]["role"] == "assistant":
            db.table("messages").delete().eq("id", msgs.pop()["id"]).execute()
        if not msgs or msgs[-1]["role"] != "user":
            raise HTTPException(400, "Nothing to regenerate")
        text, insert_user = msgs.pop()["content"], False
    if not text:
        text = "Please analyze the attached file(s) and tell me what is in them."

    quota.check_and_count(ident)

    note, file_meta = _attach_note(ident, body.file_ids)
    user_row = None
    if insert_user:
        user_row = db.table("messages").insert({
            "conversation_id": conv["id"], "tenant_id": ident.tenant_id, "role": "user", "content": text,
            "meta": {"files": file_meta, "images": len(images)}}).execute().data[0]
    llm_message = (note + "\n\n" + text) if note else text
    instructions = load_instructions(ident)
    plan = _decide(body.agent_id, text, ident)
    if images and plan["mode"] != "chat" and not tdb.vocabulary(ident.tenant_id) & set(re.findall(r"[a-z0-9]+", text.lower())):
        plan = {"mode": "chat", "agents": ["general-assistant"], "reason": "image question"}
    routed = body.agent_id in ("auto", "team")

    ctx = ToolContext(tenant_id=ident.tenant_id)
    sink = {"text": "", "tools": [], "charts": [], "agent": None, "team": None, "mode": plan["mode"],
            "reason": plan["reason"], "usage": {"tokens_in": 0, "tokens_out": 0}}
    state = {"saved": None}

    def persist() -> Optional[str]:
        if state["saved"] or not (sink["text"] or sink["tools"]):
            return state["saved"]
        meta = {k: sink[k] for k in ("agent", "tools", "charts", "usage", "team", "mode", "reason")}
        row = db.table("messages").insert({
            "conversation_id": conv["id"], "tenant_id": ident.tenant_id, "role": "assistant",
            "content": sink["text"], "meta": json.loads(json.dumps(meta, default=str))}).execute().data[0]
        db.table("conversations").update({"updated_at": _now(), "agent_id": body.agent_id}).eq("id", conv["id"]).execute()
        quota.add_tokens(ident, sink["usage"]["tokens_in"], sink["usage"]["tokens_out"])
        state["saved"] = row["id"]
        return row["id"]

    def collect(ev: dict) -> None:
        t = ev["type"]
        if t == "meta":
            sink["agent"], sink["team"] = ev["agent"], ev.get("team")
        elif t == "delta":
            sink["text"] += ev["text"]
        elif t == "tool_start":
            sink["tools"].append({"id": ev["id"], "name": ev["name"], "args": ev["args"], "agent": ev.get("agent")})
        elif t == "tool_result":
            for tool in sink["tools"]:
                if tool["id"] == ev["id"]:
                    tool.update(ok=ev["ok"], preview=ev["preview"])
        elif t == "chart":
            sink["charts"].append(ev["spec"])
        elif t == "usage":
            sink["usage"]["tokens_in"] += ev["tokens_in"]
            sink["usage"]["tokens_out"] += ev["tokens_out"]

    def stream() -> Iterator[str]:
        yield _sse({"type": "start", "conversation_id": conv["id"], "title": conv["title"], "is_new": is_new,
                    "user_message_id": user_row["id"] if user_row else None})
        try:
            for ev in _turn_events(plan, msgs, llm_message, ctx, instructions, images, routed):
                collect(ev)
                yield _sse(ev)
            mid = persist()
            yield _sse({"type": "done", "message_id": mid, "conversation_id": conv["id"], "usage": sink["usage"]})
            if is_new and sink["text"]:
                title = _make_title(text, sink["text"])
                if title:
                    db.table("conversations").update({"title": title}).eq("id", conv["id"]).execute()
                    yield _sse({"type": "title", "title": title})
        except Exception as e:  # noqa: BLE001
            log.exception("chat stream failed")
            persist()
            msg = str(e)
            if "authentication" in msg.lower() or "api key" in msg.lower() or "api_key" in msg.lower():
                msg = "The AI provider key is missing or invalid. Set the key for your LLM_PROVIDER (ANTHROPIC_API_KEY, GOOGLE_API_KEY or OPENAI_API_KEY) in api/.env and restart the server."
            else:
                msg = f"{type(e).__name__}: {msg[:300]}"
            yield _sse({"type": "error", "message": msg})
        finally:
            persist()  # also runs when the client disconnects mid-stream (Stop button)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
