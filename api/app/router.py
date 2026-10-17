"""Fast planner: decides between a plain chat answer, ONE specialist agent, or a parallel team.

No LLM call is needed for routing, which keeps simple questions quick. An optional LLM router
(LLM_ROUTER=true) is only used when the rules cannot tell which agent fits.
"""
import json
import logging
import re
from typing import Optional

from .agents import engine
from .catalog import BY_ID, CATALOG, DEFAULT_AGENT
from .config import get_settings
from .datasets import DATASETS

log = logging.getLogger("router")

_STOP = set("the a an of to in for and or is are what which who how show me my our give with on by from "
            "at as it this that be can you please about do does".split())
_TOKEN = re.compile(r"[a-z0-9ऀ-ॿ]+")


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 2}


# Strong "skills" (a distinct way of working) vs business "domains" (what the data is about).
SKILLS = [
    ("forecast", r"forecast|predict|projection|project(ed)? (sales|revenue)|next (week|month|quarter|year)|outlook|expected demand", "forecasting-analyst"),
    ("anomaly", r"anomal|outlier|unusual|fraud|suspicious|duplicate", "anomaly-fraud-detector"),
    ("clean", r"clean(ing)?|missing values?|\bnulls?\b|data quality|inconsisten|data issues?", "data-cleaning-advisor"),
    ("dashboard", r"dashboard|visuali[sz]e (everything|all)", "dashboard-designer"),
    ("scorecard", r"scorecard|\bkpis?\b", "kpi-scorecard-builder"),
    ("pivot", r"pivot|cross.?tab|summary table", "pivot-report-builder"),
    ("formula", r"\bexcel\b|formula|vlookup|xlookup|sumifs|google sheets?", "excel-formula-helper"),
    ("dictionary", r"data dictionary|what does each column|explain (the )?columns|column meaning", "data-dictionary-writer"),
    ("docs", r"policy|policies|\bsops?\b|contract|document|manual|handbook|clause|agreement", "document-qa-assistant"),
]
DOMAINS = [
    ("sales", r"sales|revenue|orders?|invoice|\baov\b|turnover|top products?|best.?sellers?", "sales-revenue-analyst"),
    ("finance", r"expense|budget|profit|margin|\bcosts?\b|spend|payment|vendor|cash", "finance-expense-analyst"),
    ("marketing", r"campaign|marketing|\bleads?\b|conversion|\bcac\b|roas|channel|ad spend", "marketing-performance-analyst"),
    ("customer", r"customers?|churn|retention|repeat|segment|\brfm\b|cohort", "customer-analytics-analyst"),
    ("ops", r"inventory|stock|supplier|lead time|delivery|production|downtime|warehouse|shipment", "operations-supply-analyst"),
    ("hr", r"employees?|headcount|attrition|salary|salaries|hiring|tenure|payroll", "hr-people-analyst"),
]
ANALYTIC = re.compile(
    r"\b(total|sum|average|avg|mean|median|count|how many|top|bottom|highest|lowest|trend|compare|comparison|"
    r"growth|rate|percent|percentage|ratio|breakdown|chart|graph|plot|table|rows|columns|data|dataset|file|"
    r"sheet|csv|excel|report|analy[sz]e|analysis|insights?|kpis?|per|by month|by year)\b|kitn[ae]|sabse|ausat",
    re.I)
COMPLEX = re.compile(
    r"full (analysis|report)|deep.?dive|end.to.end|comprehensive|everything|across all|as well as|"
    r"then (recommend|suggest|forecast|build|create)|root cause|\bwhy\b.*\b(and|then)\b|complete (report|analysis)", re.I)
CONNECTOR = re.compile(r"\b(and|then|also|plus|along with)\b", re.I)

# Extra routing vocabulary for the public sample datasets (used when those tables are installed).
_DATASET_WORDS = {
    "ai4i_machines": "machine machines failure failures maintenance tool wear torque spindle rpm milling manufacturing",
    "online_retail": "retail invoice invoices basket cancellation cancellations price gift",
    "telco_churn": "churn telecom telco contract tenure subscriber internet monthly charges",
    "bank_marketing": "bank deposit loan loans subscribe call calls balance campaign",
    "bike_sharing": "bike bikes rental rentals weather hourly riders cycle",
    "adult_census": "census income education occupation workforce demographic hours",
}


def _agent_tokens(a) -> set[str]:
    base = f"{a.id.replace('-', ' ')} {a.name} {a.description} {a.focus} {' '.join(a.starters)}"
    extra = " ".join(_DATASET_WORDS.get(d, "") for d in a.datasets) if len(a.datasets) == 1 else ""
    return _tokens(base + " " + extra)


_INDEX = {a.id: _agent_tokens(a) for a in CATALOG}


def keyword_route(message: str, k: int = 1, only: Optional[set[str]] = None) -> list[str]:
    q = _tokens(message)
    scored = sorted(((len(q & toks), aid) for aid, toks in _INDEX.items() if not only or aid in only), reverse=True)
    best = [aid for score, aid in scored if score > 0][:k]
    return best or [DEFAULT_AGENT]


def _match(rules, text):
    return [(name, agent) for name, rx, agent in rules if re.search(rx, text, re.I)]


def plan(message: str, vocab: set[str], has_docs: bool = False, table_names: Optional[set[str]] = None,
         force_complex: bool = False) -> dict:
    """Return {"mode": "chat"|"simple"|"complex", "agents": [ids], "reason": str}."""
    text = message.strip()
    words = _tokens(text)
    skills, domains = _match(SKILLS, text), _match(DOMAINS, text)
    data_like = bool(words & vocab) or bool(ANALYTIC.search(text)) or bool(skills) or bool(domains)

    if not data_like and not force_complex:
        return {"mode": "chat", "agents": ["general-assistant"], "reason": "general question"}

    n_words = len(text.split())
    skill_agents = [a for _, a in skills]
    domain_agents = [a for _, a in domains]
    complex_ = force_complex or len(skills) >= 2 or n_words > 45 or bool(COMPLEX.search(text)) or (
        len(skills) >= 1 and len(domains) >= 1 and bool(CONNECTOR.search(text)))

    if complex_:
        picks = list(dict.fromkeys(skill_agents + domain_agents))
        # sample-data domain specialists, when those tables are installed and the words match
        sample = [n for n in (table_names or set()) if n in DATASETS]
        if sample:
            only = {a.id for a in CATALOG if set(a.datasets) & set(sample) and not a.generic}
            picks += [a for a in keyword_route(text, 2, only) if a not in picks]
        for filler in (DEFAULT_AGENT, "dashboard-designer", "kpi-scorecard-builder"):
            if len(picks) >= 2:
                break
            if filler not in picks:
                picks.append(filler)
        return {"mode": "complex", "agents": picks[:3], "reason": "multi-part question: agents work in parallel"}

    # simple: exactly one agent
    if skill_agents:
        return {"mode": "simple", "agents": [skill_agents[0]], "reason": "matched skill"}
    sample = [n for n in (table_names or set()) if n in DATASETS]
    if sample:
        only = {a.id for a in CATALOG if set(a.datasets) & set(sample) and not a.generic}
        best = keyword_route(text, 1, only)[0]
        if best != DEFAULT_AGENT and len(_INDEX[best] & _tokens(text)) >= 2:
            return {"mode": "simple", "agents": [best], "reason": "matched specialist"}
    if domain_agents:
        return {"mode": "simple", "agents": [domain_agents[0]], "reason": "matched domain"}
    if get_settings().llm_router and n_words > 8:
        try:
            return {"mode": "simple", "agents": route(text)["agents"][:1], "reason": "LLM routed"}
        except Exception:
            log.warning("LLM router failed", exc_info=True)
    return {"mode": "simple", "agents": [DEFAULT_AGENT], "reason": "general data question"}


# ----------------------------------------------------------------- optional LLM router
def _catalog_lines() -> str:
    return "\n".join(f"{a.id} | {a.category} | {a.description}" for a in CATALOG)


def route(message: str, previous_agent_id: Optional[str] = None, k: int = 1) -> dict:
    """LLM routing over the full catalog, with a keyword fallback."""
    hint = (f"The previous message was handled by '{previous_agent_id}'. Keep it for follow-ups unless the "
            "topic clearly changed.\n" if previous_agent_id in BY_ID else "")
    prompt = (
        f"You route user questions to the best specialist agent.\n{hint}"
        f"Choose {k} agent id(s) from this catalog (id | category | description):\n{_catalog_lines()}\n\n"
        f"User message: {message[:1500]}\n\n"
        'Reply with ONLY JSON: {"agents": ["id", ...], "reason": "short reason"}'
    )
    try:
        resp = engine.get_llm(fast=True).invoke(prompt)
        text = resp.content if isinstance(resp.content, str) else "".join(
            b.get("text", "") for b in resp.content if isinstance(b, dict))
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group()) if m else {}
        ids = [i for i in data.get("agents", []) if i in BY_ID][:k]
        if ids:
            return {"agents": ids, "reason": str(data.get("reason", ""))[:200], "method": "llm"}
    except Exception:
        log.warning("LLM routing failed, using keyword fallback", exc_info=True)
    return {"agents": keyword_route(message, k), "reason": "keyword match", "method": "keyword"}
