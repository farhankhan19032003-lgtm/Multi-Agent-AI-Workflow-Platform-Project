"""Create an API key for a tenant.

Usage (from api/ with .env loaded):
    python -m scripts.create_api_key <tenant_uuid> <key_name>

Prints the plaintext key ONCE. Only its SHA-256 hash is stored.
"""
import secrets
import sys

from app import db
from app.auth import hash_key


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    tenant_id, name = sys.argv[1], sys.argv[2]
    raw = "af_" + secrets.token_urlsafe(32)
    db.table("api_keys").insert(
        {"tenant_id": tenant_id, "name": name, "key_hash": hash_key(raw)}
    ).execute()
    print(f"API key for '{name}' (store it now, it cannot be shown again):\n{raw}")


if __name__ == "__main__":
    main()
