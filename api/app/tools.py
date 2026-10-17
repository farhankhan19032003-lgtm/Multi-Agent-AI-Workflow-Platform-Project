"""Tools that agents can call. Everything is tenant-scoped and read-only."""
import json
from dataclasses import dataclass, field

import httpx
from langchain_core.tools import tool

from . import analysis, knowledge, tenantdb
from .config import get_settings

CHART_TYPES = {"bar", "line", "pie", "doughnut", "scatter"}
MAX_TOOL_CHARS = 12000

ALL_TOOL_NAMES = [
    "list_tables", "describe_table", "run_sql", "make_chart", "profile_table", "forecast_series",
    "detect_anomalies", "correlations", "search_documents", "web_search",
]


@dataclass
class ToolContext:
    tenant_id: str
    charts: list = field(default_factory=list)


def _j(obj) -> str:
    return json.dumps(obj, default=str)


def build_tools(ctx: ToolContext, allowed: list[str]) -> dict:
    tid = ctx.tenant_id

    @tool
    def list_tables() -> str:
        """List the user's data tables (name, rows, columns)."""
        src = tenantdb.sources(tid, "table")
        if not src:
            return "No data uploaded yet. Ask the user to attach a CSV or Excel file."
        return _j([{"name": s["name"], "rows": s.get("rows"), "file": s.get("filename"),
                    "columns": [c["name"] for c in (s.get("columns") or [])]} for s in src])

    @tool
    def describe_table(name: str) -> str:
        """Columns, types, value ranges, category values and 3 sample rows of one table."""
        try:
            return _j(tenantdb.describe(tid, name))
        except Exception as e:
            return f"ERROR: {e}"

    @tool
    def run_sql(query: str) -> str:
        """Run ONE read-only DuckDB SELECT (or WITH ... SELECT) over the user's tables. Returns columns,
        rows (max 200) and row_count. Aggregate (GROUP BY, SUM, AVG, COUNT) instead of pulling raw rows.
        Quote identifiers with double quotes. On an error, fix the query and retry."""
        try:
            return _j(tenantdb.run_query(tid, query))
        except Exception as e:
            return f"ERROR: {e}"

    @tool
    def make_chart(chart_type: str, title: str, labels: list[str], series: list[dict]) -> str:
        """Show a chart. chart_type: bar | line | pie | doughnut | scatter. labels: x categories.
        series: [{"name": str, "data": [numbers aligned with labels]}]. For scatter use labels [] and
        data as [{"x": n, "y": n}]. Use real numbers from run_sql."""
        if chart_type not in CHART_TYPES:
            return f"ERROR: chart_type must be one of {sorted(CHART_TYPES)}"
        if not series:
            return "ERROR: series is empty"
        if chart_type != "scatter":
            for s in series:
                if len(s.get("data", [])) != len(labels):
                    return "ERROR: each series.data must have the same length as labels"
        ctx.charts.append({"type": chart_type, "title": title, "labels": labels, "series": series})
        return "Chart displayed to the user."

    @tool
    def profile_table(name: str) -> str:
        """Data-quality and statistics overview of a table: per-column type, nulls, distinct count, min/max
        and summary statistics."""
        try:
            return _j(analysis.profile(tid, name))
        except Exception as e:
            return f"ERROR: {e}"

    @tool
    def forecast_series(table: str, date_column: str, value_column: str, periods: int = 6,
                        freq: str = "month", agg: str = "sum") -> str:
        """Forecast a metric over time. freq: day|week|month|quarter|year. agg: sum|avg|count|min|max.
        Returns history, forecast with 80% interval, method and back-test error. It is a simple
        trend+seasonality estimate: always state the caveat."""
        try:
            return _j(analysis.forecast(tid, table, date_column, value_column, periods, freq, agg))
        except Exception as e:
            return f"ERROR: {e}"

    @tool
    def detect_anomalies(table: str, value_column: str, date_column: str = "", group_column: str = "",
                         method: str = "iqr") -> str:
        """Find unusual values in a numeric column (method: iqr | zscore). Optionally include a date and a
        group column for context. Returns the count, normal range and the most extreme rows."""
        try:
            return _j(analysis.anomalies(tid, table, value_column, date_column, group_column, method))
        except Exception as e:
            return f"ERROR: {e}"

    @tool
    def correlations(table: str, columns: list[str] | None = None) -> str:
        """Strongest correlations between numeric columns of a table (optionally limited to `columns`)."""
        try:
            return _j(analysis.correlations(tid, table, columns))
        except Exception as e:
            return f"ERROR: {e}"

    @tool
    def search_documents(question: str) -> str:
        """Search the company's uploaded documents (policies, SOPs, contracts, manuals) for passages."""
        hits = knowledge.search(tid, question, k=4)
        return _j(hits) if hits else "No matching passages (no documents uploaded, or nothing relevant)."

    @tool
    def web_search(query: str) -> str:
        """Search the web for current information. Returns titles, URLs and snippets."""
        key = get_settings().tavily_api_key
        if not key:
            return "Web search is not configured (TAVILY_API_KEY missing). Say so and answer from general knowledge."
        try:
            r = httpx.post("https://api.tavily.com/search", headers={"Authorization": f"Bearer {key}"},
                           json={"query": query, "max_results": 5}, timeout=30)
            r.raise_for_status()
            return _j([{"title": x.get("title"), "url": x.get("url"), "snippet": (x.get("content") or "")[:500]}
                       for x in r.json().get("results", [])])
        except Exception as e:
            return f"ERROR: search failed: {e}"

    registry = {t.name: t for t in (list_tables, describe_table, run_sql, make_chart, profile_table,
                                    forecast_series, detect_anomalies, correlations, search_documents, web_search)}
    return {n: registry[n] for n in allowed if n in registry}


def truncate(text: str) -> str:
    return text if len(text) <= MAX_TOOL_CHARS else text[:MAX_TOOL_CHARS] + "\n...[truncated]"
