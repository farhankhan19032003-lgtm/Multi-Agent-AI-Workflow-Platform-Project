import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- Storage backend --------------------------------------------------
    # "supabase": multi-user company workspaces (production)
    # "local":    single-user, zero setup (SQLite file on this machine)
    storage: str = "supabase"
    supabase_url: str = ""
    supabase_service_role_key: str = ""  # server-side only; never expose it
    # Public (anon) key for the browser login. Safe to expose.
    supabase_anon_key: str = ""

    # ---- LLM (any LangChain-supported provider: anthropic, openai, ...) ----
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    # Extra Gemini keys (comma-separated). When one key hits its quota (429), the next one is used.
    google_api_keys: str = ""
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-5-5"
    # Small fast model for greetings, titles and suggestions
    llm_fast_model: str = "claude-haiku-5-5"
    # None = use the model's default (newer Claude models reject non-default temperature)
    llm_temperature: float | None = None
    # Retries with backoff on 429/503 ("high demand"), common on free tiers
    llm_max_retries: int = 5
    # Comma-separated models to try, in order, when the main model is rate limited / overloaded / unavailable
    llm_fallback_models: str = ""
    # Let a small LLM pick the agent when keyword routing is unsure (adds ~1s). Default off = fastest.
    llm_router: bool = False

    # Web search for the Research agent and General Assistant (optional)
    tavily_api_key: str = ""

    # ---- MLflow monitoring (v1 workflows) ----
    mlflow_tracking_uri: str = "file:./mlruns"
    mlflow_experiment: str = "agent-factory"
    enable_llm_judge: bool = False

    # Optional LlamaIndex vector search for documents (needs an embeddings key). BM25 is the default.
    enable_knowledge: bool = False

    # Factory alert thresholds (v1 daily report)
    defect_alert_pct: float = 3.0
    target_alert_pct: float = 85.0

    cors_origins: str = "*"

    # LOCAL TRYOUT ONLY (supabase mode): skips login and uses the demo tenant.
    dev_no_auth: bool = False
    demo_tenant_id: str = "11111111-1111-1111-1111-111111111111"

    # ---- Data, limits ----------------------------------------------------
    data_dir: str = "./data"
    sql_row_limit: int = 200
    sql_timeout_s: int = 20
    export_row_limit: int = 100000
    max_agent_steps: int = 6
    team_agent_steps: int = 4
    max_upload_mb: int = 50
    max_table_rows: int = 3_000_000
    max_columns: int = 400

    # ---- Plans / abuse protection ----------------------------------------
    free_daily_messages: int = 40
    pro_daily_messages: int = 3000
    burst_requests: int = 8          # per user ...
    burst_window_s: int = 10         # ... per this many seconds


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # LangChain provider clients read keys from the process environment, not from our .env parsing.
    for name, value in (("ANTHROPIC_API_KEY", s.anthropic_api_key), ("OPENAI_API_KEY", s.openai_api_key),
                        ("GOOGLE_API_KEY", s.google_api_key)):
        if value and not os.environ.get(name):
            os.environ[name] = value
    return s
