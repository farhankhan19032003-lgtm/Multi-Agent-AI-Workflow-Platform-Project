"""Multi-agent orchestration: runs workflows step by step, persisting every step."""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from . import db, memory, quality
from .agents import AgentResult, AnalyticsAgent, ResearchAgent, SummarizerAgent

log = logging.getLogger("orchestrator")

FACTORY_SECTIONS = ["Summary", "Key Findings", "Risks", "Recommended Actions"]
RESEARCH_SECTIONS = ["Summary", "Key Findings", "Sources"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_run(tenant_id: str, workflow: str, payload: dict, triggered_by: str = "api") -> str:
    row = (
        db.table("workflow_runs")
        .insert(
            {
                "tenant_id": tenant_id,
                "workflow": workflow,
                "input": payload,
                "triggered_by": triggered_by,
            }
        )
        .execute()
        .data[0]
    )
    return row["id"]


class RunContext:
    def __init__(self, run_id: str, tenant_id: str):
        self.run_id = run_id
        self.tenant_id = tenant_id

    def agent_config(self, kind: str) -> dict:
        """Per-tenant overrides (custom prompt / model / disabled) from the agents table."""
        rows = (
            db.table("agents")
            .select("system_prompt,model,enabled")
            .eq("tenant_id", self.tenant_id)
            .eq("kind", kind)
            .limit(1)
            .execute()
            .data
        )
        if not rows:
            return {}
        if not rows[0]["enabled"]:
            raise RuntimeError(f"Agent '{kind}' is disabled for this tenant")
        return {k: v for k, v in rows[0].items() if k in ("system_prompt", "model") and v}

    def step(self, kind: str, idx: int, task_input: Any, fn: Callable[[], AgentResult]) -> AgentResult:
        task = (
            db.table("agent_tasks")
            .insert(
                {
                    "run_id": self.run_id,
                    "tenant_id": self.tenant_id,
                    "agent_kind": kind,
                    "step": idx,
                    "input": json.loads(json.dumps(task_input, default=str))
                    if isinstance(task_input, dict)
                    else {"value": str(task_input)[:4000]},
                }
            )
            .execute()
            .data[0]
        )
        try:
            res = fn()
        except Exception as e:
            db.table("agent_tasks").update(
                {"status": "failed", "output": {"error": str(e)[:1000]}}
            ).eq("id", task["id"]).execute()
            raise
        db.table("agent_tasks").update(
            {
                "status": "succeeded",
                "output": {"text": res.text[:8000]},
                "tokens_in": res.tokens_in,
                "tokens_out": res.tokens_out,
                "latency_ms": res.latency_ms,
            }
        ).eq("id", task["id"]).execute()
        return res


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------
def _factory_report(ctx: RunContext, payload: dict) -> dict:
    plant = payload.get("plant")
    days = int(payload.get("days", 7))
    scope = f"factory:{plant or 'all'}"

    analysis = ctx.step(
        "analytics", 1, payload,
        lambda: AnalyticsAgent(ctx.tenant_id, **ctx.agent_config("analytics")).run(plant, days),
    )
    previous = memory.get(ctx.tenant_id, scope, "last_summary")
    summary = ctx.step(
        "summarizer", 2, {"analysis_chars": len(analysis.text)},
        lambda: SummarizerAgent(**ctx.agent_config("summarizer")).run(
            analysis.text, FACTORY_SECTIONS, previous_summary=previous, audience="plant manager"
        ),
    )
    memory.set(ctx.tenant_id, scope, "last_summary", summary.text)

    facts = analysis.meta["facts"]
    title = summary.text.splitlines()[0].lstrip("# ").strip() or "Daily Factory Report"
    report_id = _save_report(ctx, "daily_factory_report", title, summary.text)

    scores = {
        "structure": quality.structure_score(summary.text, FACTORY_SECTIONS),
        "grounding": quality.grounding_score(summary.text, json.dumps(facts, default=str)),
        "judge": quality.llm_judge(summary.text, "Daily factory performance briefing"),
    }
    quality.record(ctx.run_id, ctx.tenant_id, "daily_factory_report", scores)
    return {
        "report_id": report_id,
        "title": title,
        "markdown": summary.text,
        "kpis": {k: facts[k] for k in (
            "total_units_produced", "overall_defect_rate_pct",
            "total_downtime_minutes", "anomaly_count")},
        "alerts": facts["anomalies"][:5],
        "quality": scores,
    }


def _research(ctx: RunContext, payload: dict) -> dict:
    query = payload["query"]
    research = ctx.step(
        "research", 1, payload,
        lambda: ResearchAgent(**ctx.agent_config("research")).run(query, int(payload.get("max_sources", 5))),
    )
    summary = ctx.step(
        "summarizer", 2, {"research_chars": len(research.text)},
        lambda: SummarizerAgent(**ctx.agent_config("summarizer")).run(
            research.text, RESEARCH_SECTIONS, audience="business owner"
        ),
    )
    title = summary.text.splitlines()[0].lstrip("# ").strip() or query[:80]
    report_id = _save_report(ctx, "research", title, summary.text)
    scores = {
        "structure": quality.structure_score(summary.text, RESEARCH_SECTIONS),
        "citations": quality.citation_score(summary.text) if research.meta.get("sources") else None,
        "judge": quality.llm_judge(summary.text, f"Research briefing: {query}"),
    }
    quality.record(ctx.run_id, ctx.tenant_id, "research", scores)
    return {
        "report_id": report_id,
        "title": title,
        "markdown": summary.text,
        "sources": research.meta.get("sources", []),
        "quality": scores,
    }


def _save_report(ctx: RunContext, kind: str, title: str, body: str) -> str:
    return (
        db.table("reports")
        .insert(
            {"tenant_id": ctx.tenant_id, "run_id": ctx.run_id, "kind": kind,
             "title": title[:200], "body_markdown": body}
        )
        .execute()
        .data[0]["id"]
    )


WORKFLOWS: dict[str, Callable[[RunContext, dict], dict]] = {
    "daily_factory_report": _factory_report,
    "research": _research,
}


def execute_run(run_id: str, tenant_id: str, workflow: str, payload: dict) -> dict:
    """Run a workflow to completion. Never raises; failures are recorded on the run."""
    t0 = time.perf_counter()
    ctx = RunContext(run_id, tenant_id)
    try:
        output = WORKFLOWS[workflow](ctx, payload)
        db.table("workflow_runs").update(
            {
                "status": "succeeded",
                "output": json.loads(json.dumps(output, default=str)),
                "finished_at": _now(),
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            }
        ).eq("id", run_id).execute()
        return {"run_id": run_id, "status": "succeeded", "output": output}
    except Exception as e:
        log.exception("Workflow %s failed (run %s)", workflow, run_id)
        db.table("workflow_runs").update(
            {
                "status": "failed",
                "error": str(e)[:2000],
                "finished_at": _now(),
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            }
        ).eq("id", run_id).execute()
        return {"run_id": run_id, "status": "failed", "error": str(e)[:500]}
