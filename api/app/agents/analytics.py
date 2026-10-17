import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Optional

from .. import db
from ..config import get_settings
from ..knowledge import lookup_sops
from .base import AgentResult, BaseAgent


class AnalyticsAgent(BaseAgent):
    kind = "analytics"
    system_prompt = (
        "You are a manufacturing operations analyst. You are given pre-computed facts as "
        "JSON. Write an analysis using ONLY those numbers; never calculate new figures or "
        "invent causes. Cover: overall performance, best/worst lines, defect and downtime "
        "patterns, anomalies, and where SOP snippets apply."
    )

    def __init__(self, tenant_id: str, **kw):
        super().__init__(**kw)
        self.tenant_id = tenant_id

    # ---- deterministic number crunching (no LLM math) -------------------
    def compute_facts(self, plant: Optional[str], days: int) -> dict:
        s = get_settings()
        since = (date.today() - timedelta(days=days - 1)).isoformat()

        q = (
            db.table("factory_daily_kpis")
            .select("*")
            .eq("tenant_id", self.tenant_id)
            .gte("shift_date", since)
        )
        if plant:
            q = q.eq("plant", plant)
        kpis = q.order("shift_date").execute().data

        dq = (
            db.table("production_metrics")
            .select("downtime_minutes,downtime_reason,factory_lines!inner(plant,line_name)")
            .eq("tenant_id", self.tenant_id)
            .gte("shift_date", since)
        )
        if plant:
            dq = dq.eq("factory_lines.plant", plant)
        downtime_rows = dq.execute().data

        by_line: dict[str, dict] = defaultdict(
            lambda: {"produced": 0, "defective": 0, "downtime": 0, "attain": []}
        )
        anomalies = []
        for r in kpis:
            key = f"{r['plant']} / {r['line_name']}"
            agg = by_line[key]
            agg["produced"] += r["units_produced"] or 0
            agg["defective"] += r["units_defective"] or 0
            agg["downtime"] += r["downtime_minutes"] or 0
            if r["target_attainment_pct"] is not None:
                agg["attain"].append(float(r["target_attainment_pct"]))
            if (r["defect_rate_pct"] or 0) > s.defect_alert_pct:
                anomalies.append(
                    {"type": "high_defect_rate", "line": key, "date": r["shift_date"],
                     "defect_rate_pct": float(r["defect_rate_pct"])}
                )
            if r["target_attainment_pct"] is not None and float(r["target_attainment_pct"]) < s.target_alert_pct:
                anomalies.append(
                    {"type": "below_target", "line": key, "date": r["shift_date"],
                     "target_attainment_pct": float(r["target_attainment_pct"])}
                )

        lines = {}
        for key, a in by_line.items():
            lines[key] = {
                "units_produced": a["produced"],
                "units_defective": a["defective"],
                "defect_rate_pct": round(100 * a["defective"] / a["produced"], 2) if a["produced"] else 0,
                "downtime_minutes": a["downtime"],
                "avg_target_attainment_pct": round(sum(a["attain"]) / len(a["attain"]), 2) if a["attain"] else None,
            }

        reasons = Counter()
        for r in downtime_rows:
            if r.get("downtime_reason"):
                reasons[r["downtime_reason"]] += r["downtime_minutes"] or 0
        top_reasons = [{"reason": k, "minutes": v} for k, v in reasons.most_common(3)]

        total_prod = sum(a["produced"] for a in by_line.values())
        total_def = sum(a["defective"] for a in by_line.values())
        facts = {
            "period_days": days,
            "plant": plant or "all plants",
            "total_units_produced": total_prod,
            "total_units_defective": total_def,
            "overall_defect_rate_pct": round(100 * total_def / total_prod, 2) if total_prod else 0,
            "total_downtime_minutes": sum(a["downtime"] for a in by_line.values()),
            "lines": lines,
            "top_downtime_reasons": top_reasons,
            "anomalies": anomalies[:15],
            "anomaly_count": len(anomalies),
        }
        if top_reasons:
            facts["sop_snippets"] = lookup_sops(
                self.tenant_id, f"How to prevent or resolve: {top_reasons[0]['reason']}"
            )
        return facts

    def run(self, plant: Optional[str], days: int = 7) -> AgentResult:
        facts = self.compute_facts(plant, days)
        if not facts["lines"]:
            raise ValueError("No production data found for the requested period")
        res = self.invoke(
            "FACTS (JSON):\n" + json.dumps(facts, indent=2, default=str), meta={"facts": facts}
        )
        return res
