from typing import Optional

from .base import AgentResult, BaseAgent


class SummarizerAgent(BaseAgent):
    kind = "summarizer"
    system_prompt = (
        "You write concise executive briefings for busy plant managers and business "
        "owners. Use plain language, short bullets, and markdown headings. Never add "
        "facts or numbers that are not in the input."
    )

    def run(
        self,
        content: str,
        sections: list[str],
        previous_summary: Optional[str] = None,
        audience: str = "plant manager",
    ) -> AgentResult:
        heading_list = "\n".join(f"## {s}" for s in sections)
        prompt = (
            f"Audience: {audience}.\n"
            f"Write the briefing using exactly these markdown headings, in order:\n{heading_list}\n\n"
            "Start with a one-line title as an H1.\n\n"
            f"INPUT:\n{content}\n"
        )
        if previous_summary:
            prompt += (
                "\nPREVIOUS BRIEFING (for trend context; mention what changed, do not repeat it):\n"
                f"{previous_summary[:3000]}\n"
            )
        return self.invoke(prompt)
