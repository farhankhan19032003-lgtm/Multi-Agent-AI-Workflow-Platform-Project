import hashlib
from datetime import datetime, timezone

from fastapi import Header, HTTPException, status

from . import db


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def get_tenant_id(x_api_key: str = Header(default="", alias="X-API-Key")) -> str:
    """Resolve the tenant from the X-API-Key header. Only hashes are stored."""
    if not x_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-API-Key header")

    rows = (
        db.table("api_keys")
        .select("id,tenant_id,active")
        .eq("key_hash", hash_key(x_api_key))
        .limit(1)
        .execute()
        .data
    )
    if not rows or not rows[0]["active"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    db.table("api_keys").update(
        {"last_used_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", rows[0]["id"]).execute()
    return rows[0]["tenant_id"]
