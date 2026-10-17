"""Output-quality scoring. Scores go to Supabase and MLflow."""
import logging
import re

from . import db
from .config import get_settings

log = logging.getLogger("quality")

_NUM = re.compile(r"\d+(?:\.\d+)?")


def structure_score(markdown: str, expected_headings: list[str]) -> float:
    if not expected_headings:
        return 1.0
    present = sum(
        1 for h in expected_headings if re.search(rf"^#+\s*{re.escape(h)}", markdown, re.I | re.M)
    )
    return present / len(expected_headings)


def grounding_score(markdown: str, source_text: str) -> float:
    """Share of 'meaningful' numbers in the report that exist in the source data."""
    source = [float(n) for n in _NUM.findall(source_text)]
    claimed = [n for n in _NUM.findall(markdown) if "." in n or len(n) >= 2]
    if not claimed:
        return 1.0

    def found(n: float) -> bool:
        return any(abs(n - s) <= max(0.05, 0.005 * abs(s)) for s in source)

    return sum(found(float(n)) for n in claimed) / len(claimed)


def citation_score(markdown: str, min_sources: int = 2) -> float:
    urls = set(re.findall(r"https?://[^\s)\]]+", markdown))
    return min(1.0, len(urls) / min_sources)


def llm_judge(markdown: str, task: str) -> float | None:
    if not get_settings().enable_llm_judge:
        return None
    try:
        from .agents.base import BaseAgent

        judge = BaseAgent()
        judge.system_prompt = (
            "You grade business reports. Reply with ONLY an integer 1-5 for clarity, "
            "usefulness and accuracy relative to the task."
        )
        res = judge.invoke(f"Task: {task}\n\nReport:\n{markdown[:6000]}")
        m = re.search(r"[1-5]", res.text)
        return (int(m.group()) - 1) / 4 if m else None
    except Exception:
        log.exception("LLM judge failed")
        return None


def record(run_id: str, tenant_id: str, workflow: str, scores: dict[str, float]) -> None:
    clean = {k: round(float(v), 4) for k, v in scores.items() if v is not None}
    if not clean:
        return
    db.table("quality_scores").insert(
        [{"run_id": run_id, "tenant_id": tenant_id, "metric": k, "score": v} for k, v in clean.items()]
    ).execute()
    _log_mlflow(run_id, workflow, clean)


def _log_mlflow(run_id: str, workflow: str, scores: dict[str, float]) -> None:
    s = get_settings()
    try:
        import mlflow

        mlflow.set_tracking_uri(s.mlflow_tracking_uri)
        mlflow.set_experiment(s.mlflow_experiment)
        with mlflow.start_run(run_name=run_id):
            mlflow.set_tags({"workflow": workflow})
            mlflow.log_params({"model": s.llm_model, "provider": s.llm_provider})
            mlflow.log_metrics(scores)
    except Exception:  # monitoring must never fail a workflow
        log.exception("MLflow logging failed")
