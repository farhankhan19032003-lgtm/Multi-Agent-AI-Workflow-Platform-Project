"""Tool-calling agent loop with token streaming."""
import json
import logging
import time
from datetime import datetime
from typing import Any, Iterator, Optional

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from .. import tenantdb
from ..catalog import AgentSpec
from ..config import get_settings
from ..tools import ToolContext, build_tools, truncate

log = logging.getLogger("engine")

DATA_TOOL_NAMES = {"run_sql", "describe_table", "list_tables"}

BASE_PROMPT = """You are {name}, a specialist agent inside Agent Factory, an AI assistant for company data.
Today is {today}.

{focus}

How to work:
- Ground every number in data you retrieved with a tool. Never invent or estimate figures; if something is missing, say exactly what is missing and which file would fix it.
- Be efficient: usually 1 to 3 queries are enough. Do not run exploratory queries you do not need. Every extra step costs the user seconds: get several figures with ONE query (CTEs, UNION ALL, window functions), and when you need several independent tool calls, issue them together in the same step.
- Use DuckDB SQL. Quote identifiers with double quotes. Prefer aggregation (GROUP BY, SUM, AVG, COUNT) over raw rows. If a query errors, read the error, fix it and retry.
- When a chart would help, call make_chart with the real numbers you queried.
- Answer first, then evidence, then caveats and one suggested next step. Keep it concise and well structured (short paragraphs, tables for comparisons).
- State sample sizes when comparing groups, and avoid causal claims the data cannot support.
- Reply in the user's language (English, Hindi or Hinglish).
{sample_note}{prefs}
{schema_block}"""


_FALLBACK_MARKERS = ("429", "503", "500", "529", "resource_exhausted", "unavailable", "overloaded",
                     "rate limit", "quota", "not_found", "no longer available", "high demand")


def _should_fallback(exc: Exception) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return any(m in text for m in _FALLBACK_MARKERS)


class FallbackLLM:
    """Tries each model in order. Falls over only if the failure happens before any output was
    produced, so the user never gets a half answer glued to a second one."""

    def __init__(self, llms: list, tags: Optional[list] = None):
        self.llms = llms
        self.tags = tags or [None] * len(llms)

    def bind_tools(self, tools):
        return FallbackLLM([m.bind_tools(tools) for m in self.llms], self.tags)

    def _failed(self, i: int, e: Exception) -> None:
        log.warning("model %d failed (%s: %.120s); trying fallback", i, type(e).__name__, e)
        if self.tags[i] and any(m in f"{e}".lower() for m in _QUOTA_MARKERS):
            _cooldown[self.tags[i]] = time.time() + _COOLDOWN_S  # skip this key+model for a while

    def stream(self, messages):
        for i, m in enumerate(self.llms):
            started = False
            try:
                for chunk in m.stream(messages):
                    started = True
                    yield chunk
                return
            except Exception as e:  # noqa: BLE001
                if started or i == len(self.llms) - 1 or not _should_fallback(e):
                    raise
                self._failed(i, e)

    def invoke(self, messages, *args, **kwargs):
        for i, m in enumerate(self.llms):
            try:
                return m.invoke(messages, *args, **kwargs)
            except Exception as e:  # noqa: BLE001
                if i == len(self.llms) - 1 or not _should_fallback(e):
                    raise
                self._failed(i, e)


_QUOTA_MARKERS = ("429", "resource_exhausted", "quota", "rate limit")
_COOLDOWN_S = 60.0
_cooldown: dict[tuple[str, str], float] = {}   # (api key, model) -> time until it is tried again


def _gemini_keys(s) -> list[str]:
    """All configured Gemini keys, main key first, without duplicates."""
    keys = [s.google_api_key] + s.google_api_keys.split(",")
    return list(dict.fromkeys(k.strip() for k in keys if k.strip()))


def get_llm(fast: bool = False):
    s = get_settings()
    names = [s.llm_fast_model if fast else s.llm_model]
    names += [n.strip() for n in s.llm_fallback_models.split(",") if n.strip() and n.strip() not in names]
    keys = _gemini_keys(s) if s.llm_provider == "google_genai" else []
    # candidates: every model with every key; the main model keeps all its keys ahead of the fallback models
    combos = [(n, k) for n in names for k in (keys or [None])]
    now = time.time()
    if keys:  # keys that just hit their quota go to the back of their model's line
        combos.sort(key=lambda c: (names.index(c[0]), _cooldown.get((c[1], c[0]), 0) > now))
    llms, tags = [], []
    for i, (name, key) in enumerate(combos):
        # Fail over quickly on non-final candidates; only the last one keeps the long retry/backoff.
        kw = {"max_retries": s.llm_max_retries if i == len(combos) - 1 else 1}
        if s.llm_temperature is not None:
            kw["temperature"] = s.llm_temperature
        if key:
            kw["google_api_key"] = key
        llms.append(init_chat_model(name, model_provider=s.llm_provider, **kw))
        tags.append((key, name) if key else None)
    return llms[0] if len(llms) == 1 else FallbackLLM(llms, tags)


def _chunk_text(chunk: Any) -> str:
    c = chunk.content
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    return ""


def build_system_prompt(spec: AgentSpec, tenant_id: str, instructions: str = "") -> str:
    uses_data = bool(DATA_TOOL_NAMES & set(spec.tools))
    schema_block = ""
    if uses_data:
        schema_block = "THE USER'S DATA (tables you can query):\n" + tenantdb.schema_text(tenant_id, spec.datasets)
    sample_note = ""
    if spec.datasets and not spec.generic:
        sample_note = ("- The guidance above was written for the sample table(s) "
                       f"{', '.join(spec.datasets)}. If they are not in the schema, apply the same ideas to "
                       "the user's own tables with similar columns, or say what is missing.\n")
    prefs = f"\nThe user's own preferences (follow them unless unsafe):\n{instructions.strip()[:1500]}\n" if instructions.strip() else ""
    return BASE_PROMPT.format(name=spec.name, today=datetime.now().strftime("%A, %d %B %Y"),
                              focus=spec.focus, sample_note=sample_note, prefs=prefs,
                              schema_block=schema_block).strip()


def _history_messages(history: list[dict]):
    out = []
    for m in history[-16:]:
        cls = HumanMessage if m["role"] == "user" else AIMessage
        if m.get("content"):
            out.append(cls(content=m["content"]))
    return out


def _user_message(text: str, images: Optional[list[str]]):
    if not images:
        return HumanMessage(text)
    blocks: list[dict] = [{"type": "text", "text": text}]
    blocks += [{"type": "image_url", "image_url": {"url": url}} for url in images[:4]]
    return HumanMessage(content=blocks)


def _preview(name: str, result: str) -> dict:
    if name == "run_sql" and not result.startswith("ERROR"):
        try:
            d = json.loads(result)
            return {"columns": d["columns"], "rows": d["rows"][:10], "row_count": d["row_count"],
                    "truncated": d["truncated"]}
        except Exception:
            pass
    return {"text": result[:300]}


def stream_agent(spec: AgentSpec, history: list[dict], user_message: str, ctx: ToolContext, *,
                 images: Optional[list[str]] = None, instructions: str = "", max_steps: Optional[int] = None,
                 fast: bool = False) -> Iterator[dict]:
    """Yield events: delta | tool_start | tool_result | chart | usage."""
    s = get_settings()
    steps = max_steps or s.max_agent_steps
    llm = get_llm(fast=fast)
    tools = build_tools(ctx, spec.tools)
    llm_t = llm.bind_tools(list(tools.values())) if tools else llm

    messages = [SystemMessage(build_system_prompt(spec, ctx.tenant_id, instructions))] + \
        _history_messages(history) + [_user_message(user_message, images)]
    tokens_in = tokens_out = 0
    charts_sent = 0

    for step in range(steps):
        full = None
        step_text = ""
        t_step, t_first = time.time(), None
        for chunk in llm_t.stream(messages):
            if t_first is None:
                t_first = time.time() - t_step
            full = chunk if full is None else full + chunk
            t = _chunk_text(chunk)
            if t:
                step_text += t
                yield {"type": "delta", "text": t}
        if full is None:
            break
        usage = getattr(full, "usage_metadata", None) or {}
        tokens_in += int(usage.get("input_tokens", 0))
        tokens_out += int(usage.get("output_tokens", 0))

        calls = getattr(full, "tool_calls", None) or []
        log.info("agent step %d: first token %.1fs, total %.1fs, in=%s out=%s, tool calls=%s", step + 1,
                 t_first or 0, time.time() - t_step, usage.get("input_tokens", 0), usage.get("output_tokens", 0),
                 [c["name"] for c in calls])
        if not calls:
            break
        if step_text:
            yield {"type": "delta", "text": "\n\n"}
        messages.append(full)
        for call in calls:
            yield {"type": "tool_start", "id": call["id"], "name": call["name"], "args": call["args"]}
            tool = tools.get(call["name"])
            try:
                result = tool.invoke(call["args"]) if tool else f"ERROR: unknown tool {call['name']}"
            except Exception as e:  # let the model see and fix the error
                result = f"ERROR: {e}"
            result = truncate(str(result))
            messages.append(ToolMessage(content=result, tool_call_id=call["id"], name=call["name"]))
            yield {"type": "tool_result", "id": call["id"], "name": call["name"],
                   "ok": not result.startswith("ERROR"), "preview": _preview(call["name"], result)}
            while charts_sent < len(ctx.charts):
                yield {"type": "chart", "spec": ctx.charts[charts_sent]}
                charts_sent += 1
    else:
        # Step limit reached: force a final answer without tools.
        messages.append(HumanMessage("Give your best final answer now using only the data retrieved so far."))
        for chunk in llm.stream(messages):
            t = _chunk_text(chunk)
            if t:
                yield {"type": "delta", "text": t}

    yield {"type": "usage", "tokens_in": tokens_in, "tokens_out": tokens_out}
