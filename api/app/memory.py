"""Persistent agent memory, shared across task cycles (stored in Supabase)."""
from datetime import datetime, timezone
from typing import Any, Optional

from . import db


def get(tenant_id: str, scope: str, key: str) -> Optional[Any]:
    rows = (
        db.table("agent_memory")
        .select("value")
        .eq("tenant_id", tenant_id)
        .eq("scope", scope)
        .eq("key", key)
        .limit(1)
        .execute()
        .data
    )
    return rows[0]["value"] if rows else None


def set(tenant_id: str, scope: str, key: str, value: Any) -> None:  # noqa: A001
    db.table("agent_memory").upsert(
        {
            "tenant_id": tenant_id,
            "scope": scope,
            "key": key,
            "value": value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="tenant_id,scope,key",
    ).execute()
