"""Data library: upload, list, preview and delete a company's own files."""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from . import db, ingest, knowledge
from . import tenantdb as tdb
from .config import get_settings
from .identity import Identity, get_identity

log = logging.getLogger("files")
api = APIRouter(prefix="/v1")


def _summary(s: dict) -> dict:
    return {"id": s["id"], "name": s["name"], "kind": s.get("kind", "table"), "filename": s.get("filename"),
            "sheet": s.get("sheet"), "rows": s.get("rows"), "column_count": len(s.get("columns") or []),
            "size_bytes": s.get("size_bytes"), "created_at": s.get("created_at"), "is_sample": bool(s.get("is_sample"))}


def _ingest_table(ident: Identity, name: str, data: bytes) -> dict:
    tid = ident.tenant_id
    parsed = ingest.parse_tabular(name, data)
    existing = {s["name"]: s for s in tdb.sources(tid, "table")}
    own = {n for n, s in existing.items() if s.get("filename") == name}   # re-upload replaces its own tables
    taken = set(existing) - own
    out = []
    for sheet, df, notes in parsed:
        tname = ingest.table_name(name, sheet if len(parsed) > 1 else None, taken)
        taken.add(tname)
        info = tdb.write_table(tid, tname, df)
        db.table("data_sources").upsert({
            "tenant_id": tid, "name": tname, "kind": "table", "filename": name, "sheet": sheet,
            "rows": info["rows"], "columns": info["columns"], "size_bytes": len(data),
            "uploaded_by": ident.owner, "is_sample": False}, on_conflict="tenant_id,name").execute()
        out.append({"name": tname, "rows": info["rows"], "columns": len(info["columns"]), "sheet": sheet, "notes": notes})
    for stale in own - {t["name"] for t in out}:
        tdb.drop_table(tid, stale)
        db.table("data_sources").delete().eq("tenant_id", tid).eq("name", stale).execute()
    tdb.invalidate_vocab(tid)
    return {"kind": "table", "tables": out}


def _ingest_document(ident: Identity, name: str, data: bytes) -> dict:
    tid = ident.tenant_id
    text = ingest.parse_document(name, data)
    db.table("documents").delete().eq("tenant_id", tid).eq("title", name).execute()
    db.table("documents").insert({"tenant_id": tid, "title": name, "content": text}).execute()
    db.table("data_sources").upsert({
        "tenant_id": tid, "name": name, "kind": "document", "filename": name, "rows": len(text), "columns": [],
        "size_bytes": len(data), "uploaded_by": ident.owner, "is_sample": False}, on_conflict="tenant_id,name").execute()
    return {"kind": "document", "characters": len(text), "chunks": len(knowledge.chunk_text(text))}


def _process(f: UploadFile, ident: Identity) -> dict:
    s = get_settings()
    name = Path(f.filename or "upload").name
    res = {"filename": name, "status": "error"}
    kind = ingest.kind_of(name)
    if kind == "image":
        res["error"] = "Images are attached directly to a chat message, not to the data library."
        return res
    if kind == "unsupported":
        res["error"] = "Unsupported file type. Use CSV, Excel, JSON, PDF, Word (.docx), TXT or MD."
        return res
    limit = s.max_upload_mb * 1024 * 1024
    data = f.file.read(limit + 1)
    if len(data) > limit:
        res["error"] = f"File is larger than {s.max_upload_mb} MB."
        return res
    try:
        res.update(_ingest_table(ident, name, data) if kind == "table" else _ingest_document(ident, name, data))
        res["status"] = "ok"
    except ValueError as e:
        res["error"] = str(e)
    except Exception as e:  # noqa: BLE001
        log.exception("ingest failed for %s", name)
        res["error"] = f"Could not read this file ({type(e).__name__}). Try saving it as CSV or .xlsx."
    return res


@api.post("/files")
def upload(files: list[UploadFile] = File(...), ident: Identity = Depends(get_identity)):
    if not files:
        raise HTTPException(400, "No files received")
    return {"results": [_process(f, ident) for f in files[:10]]}


@api.get("/files")
def list_files(ident: Identity = Depends(get_identity)):
    return [_summary(s) for s in reversed(tdb.sources(ident.tenant_id))]


def _own_source(ident: Identity, source_id: str) -> dict:
    rows = db.table("data_sources").select("*").eq("id", source_id).eq("tenant_id", ident.tenant_id).limit(1).execute().data
    if not rows:
        raise HTTPException(404, "File not found")
    return rows[0]


@api.get("/files/{source_id}")
def file_detail(source_id: str, ident: Identity = Depends(get_identity)):
    s = _own_source(ident, source_id)
    if s.get("kind") == "document":
        doc = db.table("documents").select("content").eq("tenant_id", ident.tenant_id).eq("title", s["name"]).limit(1).execute().data
        text = doc[0]["content"] if doc else ""
        return {**_summary(s), "preview_text": text[:2500]}
    try:
        prev = tdb.run_query(ident.tenant_id, f"SELECT * FROM {tdb.q(s['name'])}", limit=20)
    except Exception as e:  # noqa: BLE001
        prev = {"columns": [], "rows": [], "error": str(e)}
    return {**_summary(s), "columns": s.get("columns") or [], "preview": prev}


@api.delete("/files/{source_id}")
def delete_file(source_id: str, ident: Identity = Depends(get_identity)):
    s = _own_source(ident, source_id)
    if s.get("kind") == "document":
        db.table("documents").delete().eq("tenant_id", ident.tenant_id).eq("title", s["name"]).execute()
    else:
        tdb.drop_table(ident.tenant_id, s["name"])
    db.table("data_sources").delete().eq("id", source_id).execute()
    tdb.invalidate_vocab(ident.tenant_id)
    return {"ok": True}


@api.post("/samples/install")
def install_samples(ident: Identity = Depends(get_identity)):
    """Optional: copy the public sample datasets (UCI / IBM) into this workspace."""
    try:
        return {"installed": [{"name": t["name"], "rows": t["rows"]} for t in tdb.copy_from_samples(ident.tenant_id)]}
    except RuntimeError as e:
        raise HTTPException(400, str(e))
