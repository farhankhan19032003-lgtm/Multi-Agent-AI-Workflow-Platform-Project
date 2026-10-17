"""Per-company analytics store: one DuckDB file per tenant, so customers' data never mixes.

All agent SQL runs read-only inside a sandbox (single SELECT, no file access, timeouts).
"""
import re
import threading
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Optional

import duckdb

from . import db
from .config import get_settings

# ------------------------------------------------------------------ SQL safety
_BLOCKED = re.compile(
    r"\b(attach|detach|copy|export|import|install|load|pragma|call|create|insert|update|delete|drop|alter|"
    r"set|truncate|vacuum|checkpoint|glob|getenv|current_setting|read_\w+|scan_\w+|parquet_\w+|"
    r"duckdb_\w+|sniff_csv|which_secret)\b",
    re.I,
)


class SQLRejected(ValueError):
    pass


def validate_sql(sql: str) -> str:
    q_ = (sql or "").strip().rstrip(";").strip()
    if not q_:
        raise SQLRejected("Empty query")
    if ";" in re.sub(r"'[^']*'", "''", q_):
        raise SQLRejected("Only a single statement is allowed")
    if not re.match(r"^(select|with|from|summarize|describe|show)\b", q_, re.I):
        raise SQLRejected("Only SELECT queries are allowed")
    if _BLOCKED.search(re.sub(r"'[^']*'", "''", q_)):
        raise SQLRejected("Query contains a blocked keyword (read-only, SELECT only)")
    return q_


def q(ident: str) -> str:
    """Quote an identifier."""
    return '"' + str(ident).replace('"', '""') + '"'


def _json_safe(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))):
        return None
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    return str(v)


# ------------------------------------------------------------------ connections
_write_locks: dict[str, threading.Lock] = {}
_wl_guard = threading.Lock()


def _write_lock(tenant_id: str) -> threading.Lock:
    with _wl_guard:
        return _write_locks.setdefault(tenant_id, threading.Lock())


def tenant_dir(tenant_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", tenant_id)
    return Path(get_settings().data_dir) / "tenants" / safe


def db_file(tenant_id: str) -> Path:
    return tenant_dir(tenant_id) / "data.duckdb"


def _connect(tenant_id: str, read_only: bool):
    path = db_file(tenant_id)
    if read_only and not path.exists():
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    cfg: dict[str, Any] = {"threads": 2}
    if read_only:
        cfg.update(enable_external_access=False, memory_limit="1GB")
    last: Exception | None = None
    for _ in range(40):  # another worker/thread may briefly hold the file
        try:
            return duckdb.connect(str(path), read_only=read_only, config=cfg)
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            if "lock" in msg or "configuration" in msg or "being used" in msg:
                last = e
                time.sleep(0.15)
                continue
            raise
    raise RuntimeError(f"Data store is busy, please retry ({last})")


def has_data(tenant_id: str) -> bool:
    return db_file(tenant_id).exists()


# ------------------------------------------------------------------ querying
def run_query(tenant_id: str, sql: str, limit: Optional[int] = None) -> dict:
    s = get_settings()
    limit = limit or s.sql_row_limit
    sql = validate_sql(sql)
    con = _connect(tenant_id, read_only=True)
    if con is None:
        raise RuntimeError("No data uploaded yet. Upload a CSV or Excel file first.")
    timer = threading.Timer(s.sql_timeout_s, con.interrupt)
    timer.start()
    try:
        cur = con.execute(f"SELECT * FROM ({sql}) AS _q LIMIT {int(limit) + 1}")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    except duckdb.InterruptException:
        raise RuntimeError(f"Query took longer than {s.sql_timeout_s}s. Add filters or aggregate more.")
    finally:
        timer.cancel()
        con.close()
    truncated = len(rows) > limit
    rows = rows[:limit]
    return {
        "columns": cols,
        "rows": [[_json_safe(v) for v in r] for r in rows],
        "row_count": len(rows),
        "truncated": truncated,
    }


def query_df(tenant_id: str, sql: str, limit: int = 200000, trusted: bool = False):
    """Return a pandas DataFrame. `trusted=True` is only for SQL built by our own tools."""
    sql = sql if trusted else validate_sql(sql)
    con = _connect(tenant_id, read_only=True)
    if con is None:
        raise RuntimeError("No data uploaded yet.")
    s = get_settings()
    timer = threading.Timer(s.sql_timeout_s * 2, con.interrupt)
    timer.start()
    try:
        return con.execute(f"SELECT * FROM ({sql}) AS _q LIMIT {int(limit)}").df()
    finally:
        timer.cancel()
        con.close()


def table_columns(tenant_id: str, table: str) -> list[tuple[str, str]]:
    con = _connect(tenant_id, read_only=True)
    if con is None:
        return []
    try:
        return [(r[0], r[1]) for r in con.execute(f"DESCRIBE {q(table)}").fetchall()]
    except duckdb.CatalogException:
        return []
    finally:
        con.close()


def list_tables(tenant_id: str) -> list[dict]:
    con = _connect(tenant_id, read_only=True)
    if con is None:
        return []
    try:
        out = []
        for (name,) in con.execute("SHOW TABLES").fetchall():
            n = con.execute(f"SELECT COUNT(*) FROM {q(name)}").fetchone()[0]
            cols = [(r[0], r[1]) for r in con.execute(f"DESCRIBE {q(name)}").fetchall()]
            out.append({"name": name, "rows": n, "columns": [{"name": c, "type": t} for c, t in cols]})
        return out
    finally:
        con.close()


# ------------------------------------------------------------------ profiling
def _is_num(t: str) -> bool:
    t = t.upper()
    return any(x in t for x in ("INT", "DOUBLE", "FLOAT", "DECIMAL", "REAL", "NUMERIC")) and "INTERVAL" not in t


def _is_date(t: str) -> bool:
    t = t.upper()
    return "DATE" in t or "TIMESTAMP" in t


def profile_columns(con, table: str) -> list[dict]:
    cols = [(r[0], r[1]) for r in con.execute(f"DESCRIBE {q(table)}").fetchall()]
    parts = ["COUNT(*) AS n"]
    for i, (c, t) in enumerate(cols):
        parts += [f"COUNT({q(c)}) AS nn{i}", f"approx_count_distinct({q(c)}) AS d{i}"]
        if _is_num(t) or _is_date(t):
            parts += [f"MIN({q(c)}) AS mn{i}", f"MAX({q(c)}) AS mx{i}"]
    row = con.execute(f"SELECT {', '.join(parts)} FROM {q(table)}").fetchone()
    n, pos, out = row[0], 1, []
    for i, (c, t) in enumerate(cols):
        nn, d = row[pos], row[pos + 1]
        pos += 2
        info = {"name": c, "type": t, "null_pct": round(100 * (n - nn) / n, 1) if n else 0, "distinct": d}
        if _is_num(t) or _is_date(t):
            info["min"], info["max"] = _json_safe(row[pos]), _json_safe(row[pos + 1])
            pos += 2
        out.append(info)
    for info in [c for c in out if "VARCHAR" in c["type"].upper() and 0 < c["distinct"] <= 25][:40]:
        vals = con.execute(
            f"SELECT {q(info['name'])} FROM {q(table)} WHERE {q(info['name'])} IS NOT NULL "
            f"GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 12"
        ).fetchall()
        info["values"] = [str(v[0])[:40] for v in vals]
    return out


def write_table(tenant_id: str, name: str, df) -> dict:
    """Create/replace a table from a DataFrame. Returns {name, rows, columns(profile)}."""
    with _write_lock(tenant_id):
        con = _connect(tenant_id, read_only=False)
        try:
            con.register("df_in", df)
            con.execute(f"CREATE OR REPLACE TABLE {q(name)} AS SELECT * FROM df_in")
            con.unregister("df_in")
            rows = con.execute(f"SELECT COUNT(*) FROM {q(name)}").fetchone()[0]
            prof = profile_columns(con, name)
        finally:
            con.close()
    return {"name": name, "rows": rows, "columns": prof}


def drop_table(tenant_id: str, name: str) -> None:
    with _write_lock(tenant_id):
        con = _connect(tenant_id, read_only=False)
        try:
            con.execute(f"DROP TABLE IF EXISTS {q(name)}")
        finally:
            con.close()


# ------------------------------------------------------------------ metadata
def sources(tenant_id: str, kind: Optional[str] = None) -> list[dict]:
    rows = db.table("data_sources").select("*").eq("tenant_id", tenant_id).execute().data
    rows = [r for r in rows if not kind or r.get("kind") == kind]
    return sorted(rows, key=lambda r: str(r.get("created_at") or ""))


def _col_line(c: dict) -> str:
    bits = []
    if c.get("values"):
        bits.append("values: " + " | ".join(str(v) for v in c["values"][:10]))
    elif c.get("min") is not None:
        bits.append(f"{c['min']} to {c['max']}")
    elif c.get("distinct") is not None:
        bits.append(f"~{c['distinct']} distinct")
    if c.get("null_pct"):
        bits.append(f"{c['null_pct']}% null")
    return f"  - {c['name']} {c['type']}" + (f" ({'; '.join(bits)})" if bits else "")


def schema_text(tenant_id: str, priority: Iterable[str] = (), max_chars: int = 14000) -> str:
    tables = sources(tenant_id, "table")
    if not tables:
        return "(The user has not uploaded any data yet. For data questions, ask them to attach a CSV or Excel file.)"
    pri = list(priority)
    tables.sort(key=lambda r: (0 if r["name"] in pri else 1))
    out, size = [], 0
    for t in tables[:25]:
        cols = t.get("columns") or []
        head = f"TABLE {q(t['name'])} ({int(t.get('rows') or 0):,} rows)" + (
            f" from file {t['filename']}" if t.get("filename") else "")
        body = "\n".join(_col_line(c) for c in cols[:60])
        if len(cols) > 60:
            body += f"\n  ... {len(cols) - 60} more columns (use describe_table)"
        block = head + "\n" + body
        if size + len(block) > max_chars:
            out.append("... more tables exist (use list_tables)")
            break
        out.append(block)
        size += len(block)
    return "\n\n".join(out)


_vocab_cache: dict[str, tuple[float, set]] = {}
_TOK = re.compile(r"[a-z0-9ऀ-ॿ]+")


def vocabulary(tenant_id: str) -> set[str]:
    """Lower-case words from the tenant's table and column names, used by the fast planner."""
    hit = _vocab_cache.get(tenant_id)
    if hit and hit[0] > time.time():
        return hit[1]
    words: set[str] = set()
    for t in sources(tenant_id, "table"):
        for part in [t["name"]] + [c["name"] for c in (t.get("columns") or [])]:
            words.update(w for w in _TOK.findall(part.lower()) if len(w) > 2)
    _vocab_cache[tenant_id] = (time.time() + 20, words)
    return words


def invalidate_vocab(tenant_id: str) -> None:
    _vocab_cache.pop(tenant_id, None)


def describe(tenant_id: str, table: str, sample_rows: int = 3) -> dict:
    src = next((s for s in sources(tenant_id, "table") if s["name"] == table), None)
    if not src:
        names = ", ".join(s["name"] for s in sources(tenant_id, "table")) or "none"
        raise KeyError(f"Unknown table '{table}'. Available: {names}")
    sample = run_query(tenant_id, f"SELECT * FROM {q(table)}", limit=sample_rows) if sample_rows else {
        "columns": [], "rows": []}
    return {
        "name": table, "rows": src.get("rows"), "file": src.get("filename"),
        "columns": src.get("columns") or [],
        "sample": [dict(zip(sample["columns"], r)) for r in sample["rows"]],
    }


def copy_from_samples(tenant_id: str) -> list[dict]:
    """Copy the public sample datasets (loaded by scripts.load_datasets) into this tenant."""
    from . import datasets as samples

    if not samples.is_loaded():
        raise RuntimeError("Sample datasets are not loaded on this server (run: python -m scripts.load_datasets).")
    con = duckdb.connect(str(samples.db_path()), read_only=True, config={"enable_external_access": False})
    try:
        names = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        frames = {n: con.execute(f"SELECT * FROM {q(n)}").df() for n in names}
    finally:
        con.close()
    out = []
    for name, df in frames.items():
        info = write_table(tenant_id, name, df)
        db.table("data_sources").upsert(
            {"tenant_id": tenant_id, "name": name, "kind": "table", "filename": f"{name} (sample dataset)",
             "rows": info["rows"], "columns": info["columns"], "size_bytes": 0, "is_sample": True,
             "uploaded_by": "system"}, on_conflict="tenant_id,name").execute()
        out.append(info)
    invalidate_vocab(tenant_id)
    return out
