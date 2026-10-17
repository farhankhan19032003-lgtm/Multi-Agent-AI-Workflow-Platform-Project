"""Zero-setup storage: a tiny document store on SQLite that mimics the subset of the
supabase-py query builder this app uses (select/eq/gte/order/limit/insert/update/upsert/delete).

It is meant for single-user local use. Rows are stored as JSON; filtering happens in Python.
"""
import json
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_DEFAULTS = {
    "conversations": {"title": "New chat", "agent_id": "auto"},
    "messages": {"meta": {}},
    "workflow_runs": {"status": "running", "triggered_by": "api"},
    "agent_tasks": {"status": "running"},
    "tenants": {"plan": "starter"},
    "tenant_members": {"role": "member"},
    "data_sources": {"kind": "table"},
}
_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")


class _Res:
    def __init__(self, data):
        self.data = data


class LocalStore:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.RLock()
        self._known: set[str] = set()

    def _ensure(self, name: str) -> None:
        if name in self._known:
            return
        if not _NAME.match(name):
            raise ValueError(f"bad table name {name!r}")
        self._conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{name}" '
            "(seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, data TEXT NOT NULL)"
        )
        self._known.add(name)

    def all(self, name: str) -> list[dict]:
        with self._lock:
            self._ensure(name)
            return [json.loads(r[0]) for r in self._conn.execute(f'SELECT data FROM "{name}" ORDER BY seq')]

    def put(self, name: str, row: dict, new: bool) -> None:
        with self._lock:
            self._ensure(name)
            data = json.dumps(row, default=str)
            if new:
                self._conn.execute(f'INSERT INTO "{name}" (id, data) VALUES (?, ?)', (row["id"], data))
            else:
                self._conn.execute(f'UPDATE "{name}" SET data = ? WHERE id = ?', (data, row["id"]))

    def remove(self, name: str, row_id: str) -> None:
        with self._lock:
            self._ensure(name)
            self._conn.execute(f'DELETE FROM "{name}" WHERE id = ?', (row_id,))

    def table(self, name: str) -> "LocalQuery":
        return LocalQuery(self, name)


class LocalQuery:
    def __init__(self, store: LocalStore, name: str):
        self.store, self.name = store, name
        self.filters: list[tuple] = []
        self._op, self._payload, self._kw = "select", None, {}
        self._order: tuple | None = None
        self._limit: int | None = None
        self._cols: list[str] | None = None

    # ---- builder ----
    def select(self, cols: str = "*", **_):
        self._op = "select"
        self._cols = None if cols.strip() == "*" else [c.strip() for c in cols.split(",") if c.strip()]
        return self

    def eq(self, col, val): self.filters.append(("eq", col, val)); return self
    def neq(self, col, val): self.filters.append(("neq", col, val)); return self
    def gte(self, col, val): self.filters.append(("gte", col, val)); return self
    def lte(self, col, val): self.filters.append(("lte", col, val)); return self
    def in_(self, col, vals): self.filters.append(("in", col, list(vals))); return self
    def order(self, col, desc=False, **_): self._order = (col, bool(desc)); return self
    def limit(self, n): self._limit = n; return self
    def insert(self, payload): self._op, self._payload = "insert", payload; return self
    def update(self, payload): self._op, self._payload = "update", payload; return self
    def delete(self): self._op = "delete"; return self

    def upsert(self, payload, on_conflict: str = "id", ignore_duplicates: bool = False, **_):
        self._op, self._payload = "upsert", payload
        self._kw = {"on_conflict": on_conflict, "ignore": ignore_duplicates}
        return self

    # ---- execution ----
    def _match(self, row: dict) -> bool:
        for kind, col, val in self.filters:
            v = row.get(col)
            if kind == "eq" and v != val: return False
            if kind == "neq" and v == val: return False
            if kind == "in" and v not in val: return False
            if kind == "gte" and (v is None or str(v) < str(val)): return False
            if kind == "lte" and (v is None or str(v) > str(val)): return False
        return True

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _new_row(self, item: dict) -> dict:
        row = {**json.loads(json.dumps(_DEFAULTS.get(self.name, {}))), **item}
        row.setdefault("id", str(uuid.uuid4()))
        row.setdefault("created_at", self._now())
        if self.name == "conversations":
            row.setdefault("updated_at", row["created_at"])
        if self.name == "tenant_members":
            row.setdefault("joined_at", row["created_at"])
        return row

    def execute(self):
        s, n = self.store, self.name
        with s._lock:
            if self._op == "insert":
                items = self._payload if isinstance(self._payload, list) else [self._payload]
                out = []
                for it in items:
                    row = self._new_row(it)
                    s.put(n, row, new=True)
                    out.append(row)
                return _Res(out)

            if self._op == "upsert":
                items = self._payload if isinstance(self._payload, list) else [self._payload]
                keys = [k.strip() for k in self._kw["on_conflict"].split(",")]
                existing = s.all(n)
                out = []
                for it in items:
                    hit = next((r for r in existing if all(r.get(k) == it.get(k) for k in keys)), None)
                    if hit is None:
                        row = self._new_row(it)
                        s.put(n, row, new=True)
                        existing.append(row)
                        out.append(row)
                    elif not self._kw["ignore"]:
                        hit.update(it)
                        s.put(n, hit, new=False)
                        out.append(hit)
                return _Res(out)

            rows = [r for r in s.all(n) if self._match(r)]
            if self._op == "update":
                for r in rows:
                    r.update(self._payload)
                    s.put(n, r, new=False)
                return _Res(rows)
            if self._op == "delete":
                for r in rows:
                    s.remove(n, r["id"])
                return _Res(rows)

            if self._order:
                col, desc = self._order
                rows.sort(key=lambda r: (r.get(col) is None, str(r.get(col) if r.get(col) is not None else "")),
                          reverse=desc)
            if self._limit:
                rows = rows[: self._limit]
            if self._cols:
                rows = [{c: r.get(c) for c in self._cols} for r in rows]
            return _Res(rows)


_store: LocalStore | None = None
_store_lock = threading.Lock()


def get_store() -> LocalStore:
    global _store
    from .config import get_settings

    with _store_lock:
        if _store is None:
            _store = LocalStore(str(Path(get_settings().data_dir) / "local.sqlite"))
        return _store
