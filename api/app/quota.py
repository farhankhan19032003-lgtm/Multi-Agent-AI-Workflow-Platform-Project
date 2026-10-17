"""Plans, daily message quotas and burst rate limiting."""
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import HTTPException

from . import db
from .config import get_settings
from .identity import Identity

PRO_PLANS = {"pro", "team", "business", "enterprise"}
_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


_PLAN_TTL = 30.0
_plans: dict[str, tuple[float, str]] = {}


def plan_of(tenant_id: str) -> str:
    # Cached briefly: every chat and /me call asks, and each Supabase round trip costs ~0.4s.
    hit = _plans.get(tenant_id)
    if hit and hit[0] > time.time():
        return hit[1]
    rows = db.table("tenants").select("plan").eq("id", tenant_id).limit(1).execute().data
    plan = (rows[0].get("plan") if rows else None) or "starter"
    _plans[tenant_id] = (time.time() + _PLAN_TTL, plan)
    return plan


def limit_for(plan: str) -> int:
    s = get_settings()
    return s.pro_daily_messages if plan in PRO_PLANS else s.free_daily_messages


def _day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _row(ident: Identity):
    rows = (db.table("usage_daily").select("*").eq("tenant_id", ident.tenant_id)
            .eq("owner", ident.owner).eq("day", _day()).limit(1).execute().data)
    return rows[0] if rows else None


def _scoped_update(ident: Identity, values: dict) -> None:
    (db.table("usage_daily").update(values).eq("tenant_id", ident.tenant_id)
     .eq("owner", ident.owner).eq("day", _day()).execute())


def usage(ident: Identity, row: dict | None = None) -> dict:
    plan = plan_of(ident.tenant_id)
    r = (row if row is not None else _row(ident)) or {}
    return {"plan": plan, "pro": plan in PRO_PLANS, "limit": limit_for(plan), "used": int(r.get("messages") or 0),
            "tokens_in": int(r.get("tokens_in") or 0), "tokens_out": int(r.get("tokens_out") or 0), "day": _day()}


def rate_limit(ident: Identity) -> None:
    s = get_settings()
    key = f"{ident.tenant_id}:{ident.owner}"
    now = time.time()
    with _lock:
        dq = _hits[key]
        while dq and dq[0] < now - s.burst_window_s:
            dq.popleft()
        if len(dq) >= s.burst_requests:
            raise HTTPException(429, detail={"code": "rate_limit",
                                             "message": "You are sending messages too fast. Please wait a few seconds."})
        dq.append(now)


def check_and_count(ident: Identity) -> None:
    """Raise 429 when today's message quota is used up; otherwise count this message."""
    row = _row(ident)
    u = usage(ident, row or {})
    if u["used"] >= u["limit"]:
        raise HTTPException(429, detail={
            "code": "quota",
            "message": f"You have used all {u['limit']} messages for today on the {u['plan']} plan. "
                       "It resets at midnight UTC. Upgrade to Pro for much higher limits."})
    if row:
        _scoped_update(ident, {"messages": u["used"] + 1})
    else:
        db.table("usage_daily").insert({"tenant_id": ident.tenant_id, "owner": ident.owner, "day": _day(),
                                        "messages": 1, "tokens_in": 0, "tokens_out": 0}).execute()


def add_tokens(ident: Identity, tokens_in: int, tokens_out: int) -> None:
    row = _row(ident)
    if not row:
        return
    _scoped_update(ident, {"tokens_in": int(row.get("tokens_in") or 0) + tokens_in,
                           "tokens_out": int(row.get("tokens_out") or 0) + tokens_out})
