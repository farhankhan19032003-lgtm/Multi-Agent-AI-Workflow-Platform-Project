import time
from dataclasses import dataclass, field
from typing import Any, Optional

from langchain.chat_models import init_chat_model
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import get_settings


@dataclass
class AgentResult:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    meta: dict[str, Any] = field(default_factory=dict)


def _to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # content blocks (e.g. Anthropic)
        return "".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in content
        )
    return str(content)


class BaseAgent:
    kind = "base"
    system_prompt = "You are a helpful assistant."

    def __init__(self, system_prompt: Optional[str] = None, model: Optional[str] = None):
        s = get_settings()
        if system_prompt:
            self.system_prompt = system_prompt
        kw = {} if s.llm_temperature is None else {"temperature": s.llm_temperature}
        self.llm = init_chat_model(
            model or s.llm_model,
            model_provider=s.llm_provider,
            **kw,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
    def _call(self, user_prompt: str):
        return self.llm.invoke(
            [("system", self.system_prompt), ("human", user_prompt)]
        )

    def invoke(self, user_prompt: str, meta: Optional[dict] = None) -> AgentResult:
        t0 = time.perf_counter()
        resp = self._call(user_prompt)
        usage = getattr(resp, "usage_metadata", None) or {}
        return AgentResult(
            text=_to_text(resp.content).strip(),
            tokens_in=int(usage.get("input_tokens", 0)),
            tokens_out=int(usage.get("output_tokens", 0)),
            latency_ms=int((time.perf_counter() - t0) * 1000),
            meta=meta or {},
        )
