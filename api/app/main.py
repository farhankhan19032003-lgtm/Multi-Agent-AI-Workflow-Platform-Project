import logging
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import db, orchestrator
from .auth import get_tenant_id
from .chat import api as chat_api
from .config import get_settings
from .files import api as files_api
from .workspace import api as workspace_api
from .schemas import (
    DocumentIn,
    FactoryReportRequest,
    MetricsBatch,
    ResearchRequest,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="Agent Factory API", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(chat_api)
app.include_router(files_api)
app.include_router(workspace_api)


# ---------------------------------------------------------------- workflows
def _launch(workflow: str, payload: dict, background: bool, tenant_id: str,
            tasks: BackgroundTasks, triggered_by: str):
    run_id = orchestrator.create_run(tenant_id, workflow, payload, triggered_by)
    if background:
        tasks.add_task(orchestrator.execute_run, run_id, tenant_id, workflow, payload)
        return {"run_id": run_id, "status": "running"}
    result = orchestrator.execute_run(run_id, tenant_id, workflow, payload)
    if result["status"] == "failed":
        raise HTTPException(500, detail=result)
    return result


@app.post("/v1/workflows/factory-report")
def factory_report(
    body: FactoryReportRequest,
    tasks: BackgroundTasks,
    request: Request,
    tenant_id: str = Depends(get_tenant_id),
):
    payload = body.model_dump(exclude={"background"})
    return _launch("daily_factory_report", payload, body.background, tenant_id, tasks,
                   request.headers.get("x-triggered-by", "api"))


@app.post("/v1/workflows/research")
def research(
    body: ResearchRequest,
    tasks: BackgroundTasks,
    request: Request,
    tenant_id: str = Depends(get_tenant_id),
):
    payload = body.model_dump(exclude={"background"})
    return _launch("research", payload, body.background, tenant_id, tasks,
                   request.headers.get("x-triggered-by", "api"))


# --------------------------------------------------------------------- runs
@app.get("/v1/runs/{run_id}")
def get_run(run_id: str, tenant_id: str = Depends(get_tenant_id)):
    rows = (
        db.table("workflow_runs").select("*")
        .eq("id", run_id).eq("tenant_id", tenant_id).limit(1).execute().data
    )
    if not rows:
        raise HTTPException(404, "Run not found")
    steps = (
        db.table("agent_tasks")
        .select("agent_kind,step,status,tokens_in,tokens_out,latency_ms")
        .eq("run_id", run_id).order("step").execute().data
    )
    scores = db.table("quality_scores").select("metric,score").eq("run_id", run_id).execute().data
    return {**rows[0], "steps": steps, "quality": scores}


@app.get("/v1/runs")
def list_runs(limit: int = 20, tenant_id: str = Depends(get_tenant_id)):
    return (
        db.table("workflow_runs")
        .select("id,workflow,status,started_at,latency_ms,error")
        .eq("tenant_id", tenant_id)
        .order("started_at", desc=True)
        .limit(min(limit, 100))
        .execute()
        .data
    )


# -------------------------------------------------------------------- ingest
@app.post("/v1/ingest/production-metrics")
def ingest_metrics(body: MetricsBatch, tenant_id: str = Depends(get_tenant_id)):
    """Bulk upsert shift data from MES/ERP/CSV (called by n8n)."""
    pairs = {(m.plant, m.line_name) for m in body.metrics}
    db.table("factory_lines").upsert(
        [{"tenant_id": tenant_id, "plant": p, "line_name": l} for p, l in pairs],
        on_conflict="tenant_id,plant,line_name",
        ignore_duplicates=True,
    ).execute()
    lines = db.table("factory_lines").select("id,plant,line_name").eq("tenant_id", tenant_id).execute().data
    line_ids = {(l["plant"], l["line_name"]): l["id"] for l in lines}

    rows = [
        {
            "tenant_id": tenant_id,
            "line_id": line_ids[(m.plant, m.line_name)],
            "shift_date": m.shift_date.isoformat(),
            "shift": m.shift,
            "units_produced": m.units_produced,
            "units_defective": m.units_defective,
            "downtime_minutes": m.downtime_minutes,
            "downtime_reason": m.downtime_reason,
        }
        for m in body.metrics
    ]
    db.table("production_metrics").upsert(rows, on_conflict="line_id,shift_date,shift").execute()
    return {"upserted": len(rows)}


@app.post("/v1/documents", status_code=201)
def add_document(body: DocumentIn, tenant_id: str = Depends(get_tenant_id)):
    """Add an SOP / manual that agents can reference (LlamaIndex lookup)."""
    row = db.table("documents").insert(
        {"tenant_id": tenant_id, "title": body.title, "content": body.content}
    ).execute().data[0]
    return {"id": row["id"]}


# ------------------------------------------------------------------ chat web UI
# Mounted last so every /v1 and /health route above takes priority.
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
