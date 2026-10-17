"""Set a workspace plan (until you wire up a payment provider).

    python -m scripts.set_plan <tenant_id> pro      # or: starter
"""
import sys

from app import db


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[2] not in ("starter", "pro", "team", "business", "enterprise"):
        sys.exit(__doc__)
    db.table("tenants").update({"plan": sys.argv[2]}).eq("id", sys.argv[1]).execute()
    print(f"Tenant {sys.argv[1]} is now on the '{sys.argv[2]}' plan.")


if __name__ == "__main__":
    main()
