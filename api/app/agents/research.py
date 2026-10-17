import httpx

from ..config import get_settings
from .base import AgentResult, BaseAgent


class ResearchAgent(BaseAgent):
    kind = "research"
    system_prompt = (
        "You are a meticulous research analyst. Using ONLY the provided search results, "
        "write structured research notes. Cite every claim with its source URL in "
        "parentheses. If the results do not support something, say so. Never invent sources."
    )

    def _search(self, query: str, n: int) -> list[dict]:
        key = get_settings().tavily_api_key
        if not key:
            return []
        r = httpx.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {key}"},
            json={"query": query, "max_results": n, "search_depth": "advanced"},
            timeout=45,
        )
        r.raise_for_status()
        return r.json().get("results", [])

    def run(self, query: str, max_sources: int = 5) -> AgentResult:
        results = self._search(query, max_sources)
        if not results:
            res = self.invoke(
                f"Research question: {query}\n\nNo web search is configured. Answer from "
                "general knowledge, clearly labelling that nothing was verified online."
            )
            res.meta["sources"] = []
            return res

        context = "\n\n".join(
            f"[{i+1}] {r.get('title')}\nURL: {r.get('url')}\n{(r.get('content') or '')[:1500]}"
            for i, r in enumerate(results)
        )
        res = self.invoke(f"Research question: {query}\n\nSearch results:\n{context}")
        res.meta["sources"] = [r.get("url") for r in results]
        return res
