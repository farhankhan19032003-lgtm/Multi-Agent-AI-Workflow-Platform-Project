"""Who is calling? Browser users (Supabase JWT), API keys, local single-user mode, dev bypass."""
import hashlib
import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, status

from . import db
from .auth import get_tenant_id
from .config import get_settings

log = logging.getLogger("identity")

LOCAL_TENANT = "local-workspace"
ROLES = ("owner", "admin", "member")


@dataclass
class Identity:
    tenant_id: str
    owner: str                      # stable user key used to scope chats
    email: Optional[str] = None
    role: str = "owner"

    @property
    def is_admin(self) -> bool:
        return self.role in ("owner", "admin")


_local_ready = False
_local_lock = threading.Lock()
_token_cache: dict[str, tuple[float, Identity]] = {}
_TOKEN_TTL = 60.0


def _ensure_local_tenant() -> None:
    global _local_ready
    if _local_ready:
        return
    with _local_lock:  # the first page load fires several requests at once; only one may create the tenant
        if _local_ready:
            return
        if not db.table("tenants").select("id").eq("id", LOCAL_TENANT).limit(1).execute().data:
            db.table("tenants").insert({"id": LOCAL_TENANT, "name": "My workspace", "plan": "pro"}).execute()
        _local_ready = True


def _membership(user_id: str, email: Optional[str]) -> tuple[str, str]:
    """Return (tenant_id, role). The most recently joined workspace wins. First login creates one."""
    rows = db.table("tenant_members").select("*").eq("user_id", user_id).execute().data
    if rows:
        best = max(rows, key=lambda r: str(r.get("joined_at") or ""))
        return best["tenant_id"], best.get("role", "member")
    tenant = db.table("tenants").insert({"name": f"{email or 'New user'} workspace"}).execute().data[0]
    db.table("tenant_members").insert(
        {"tenant_id": tenant["id"], "user_id": user_id, "role": "owner", "email": email}
    ).execute()
    return tenant["id"], "owner"


def invalidate_identity_cache() -> None:
    _token_cache.clear()


def get_identity(
    authorization: str = Header(default=""),
    x_api_key: str = Header(default="", alias="X-API-Key"),
) -> Identity:
    s = get_settings()
    if s.storage == "local":
        _ensure_local_tenant()
        return Identity(tenant_id=LOCAL_TENANT, owner="local", email=None, role="owner")

    if s.dev_no_auth:
        return Identity(tenant_id=s.demo_tenant_id, owner="dev", email="dev@local", role="owner")

    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        key = hashlib.sha256(token.encode()).hexdigest()
        hit = _token_cache.get(key)
        if hit and hit[0] > time.time():
            return hit[1]
        try:
            user = db.get_client().auth.get_user(token).user
        except Exception:
            log.warning("JWT verification failed", exc_info=True)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")
        tenant_id, role = _membership(user.id, user.email)
        ident = Identity(tenant_id, user.id, user.email, role)
        _token_cache[key] = (time.time() + _TOKEN_TTL, ident)
        return ident

    if x_api_key:
        return Identity(get_tenant_id(x_api_key), "apikey", None, "member")

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in required")
