# Agent Factory v3 (Pro)

A ChatGPT-style assistant for **your own company data**. Upload CSV / Excel / JSON / PDF / Word files, then chat with 75 specialist agents that query *your* data with safe SQL, draw charts, forecast, find anomalies and search your documents.

- **Simple question → one fast agent** (a single SQL query, usually a few seconds).
- **Complex question → a team of up to 4 agents working in parallel**, then one combined answer.
- **Auto mode decides** with a rule-based planner (no extra LLM call, so no routing delay). You can also pin an agent or force Team mode.

## What it does (ChatGPT parity + business extras)

| | |
|---|---|
| Chat | Streaming answers, markdown, code copy, stop, regenerate, **edit & resend**, 👍/👎, auto chat titles, rename/delete/search chats, download chat, dark/light, mobile layout |
| Inputs | Attach files (button, drag-drop, paste), **image questions**, voice input (browser support needed) |
| Your data | Upload many files; Excel multi-sheet; messy data auto-cleaned (₹/$ amounts, %, dd/mm dates, leading-zero IDs kept as text); re-upload replaces; preview and delete in **Data library** |
| Analysis | Safe read-only SQL, charts, profiling, forecast (with accuracy backtest), anomaly detection, correlations, document search; **download any result as CSV / Excel** |
| Personalisation | Custom instructions (about you / response style) |
| Pro | Plans & daily message limits, burst rate-limit, usage meter, workspaces with invite links and members (Supabase mode) |
| Automation | The original n8n workflows (daily report, alerts, ingestion) still work |

## Run it in 2 minutes (single user, no Supabase)

1. Install Python 3.10+.
2. **Windows:** double-click `run_local.bat`  ·  **Mac/Linux:** `./run_local.sh`
3. First run creates `api/.env`. Paste your `ANTHROPIC_API_KEY` into it, run the script again.
4. Open http://localhost:8000, drop in a file, ask a question.

**Using Google Gemini instead of Claude (free tier available):** get a key at https://aistudio.google.com/apikey and set in `api/.env`:
```
LLM_PROVIDER=google_genai
LLM_MODEL=gemini-3.8-flash
LLM_FAST_MODEL=gemini-3.5-flash-lite
GOOGLE_API_KEY=your-key
```
Model names change often; list the ones your key can use with `google.genai.Client(api_key=...).models.list()`. Free tiers sometimes answer `503 high demand`; requests are retried automatically (`LLM_MAX_RETRIES`, default 5). The same switch works for OpenAI (`LLM_PROVIDER=openai`, `OPENAI_API_KEY`).

Data is stored in `api/data/` (SQLite + one DuckDB file per workspace). No login in this mode.

## Run it for many customers (Supabase)

1. Create a Supabase project. In the SQL editor run, in order: `supabase/schema.sql`, `schema_v2_chat.sql`, `schema_v3_pro.sql`.
2. Copy `.env.example` to `.env` and fill `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`, `ANTHROPIC_API_KEY`. Keep `STORAGE=supabase`, `DEV_NO_AUTH=false`.
3. `docker compose up -d --build` (add `--profile prod` for HTTPS via Caddy; set `API_DOMAIN`).
4. Users sign up in the UI; each gets a private workspace. Share an invite link (Settings → Workspace) to add teammates.
5. Upgrade a customer: `python -m scripts.set_plan <tenant_id> pro` (or edit `tenants.plan`). Limits: Free 40 / Pro 3000 messages per day per user (`FREE_DAILY_MESSAGES`, `PRO_DAILY_MESSAGES`).

## How an answer is produced

1. **Plan** (`router.plan`): greeting/general → chat; one skill/table match → *simple*; several skills ("full review, forecast and recommend") → *complex*.
2. **Simple:** one agent, its prompt contains your table schemas, so it usually needs a single `run_sql` call.
3. **Complex:** the specialists run in parallel threads (each limited to 4 tool steps), their tool activity streams live, and the main model writes one synthesis.
4. Tool results are previewed in the chat; every SQL query is shown and downloadable.

### Data safety
- Each workspace has its **own DuckDB file**; queries cannot reach another workspace's file.
- SQL is validated (single SELECT/WITH only), runs with external file access disabled, a memory cap and a timeout, and results are row-limited.
- No code execution tool: analysis uses fixed, tested functions.
- The service-role key stays on the server. Supabase RLS isolates the metadata tables.

## Tests
```
cd api && pip install -r requirements.txt pytest && python -m pytest tests -q      # 26 backend tests
cd tests/ui && npm install && python ui_server.py &  node run.js                    # 49 browser-DOM checks
```
Tests use a scripted fake LLM, so they need no API key.

## Honest limits
- **Not yet run against a live Supabase project or a live LLM** in my environment: the backend and UI were tested with a fake LLM and the local store. Expect to fix small integration details on your first real run, especially Supabase auth/RLS.
- The UI was tested in a simulated DOM (jsdom), not looked at in a real browser; check layout on your phone and desktop.
- No Python code interpreter (deliberate, for safety). Pivot tables, charts and forecasts are done through SQL and the built-in tools.
- Images sent in chat are used for that answer only and are not stored.
- Payments are not integrated; plans are set manually (see above).
- Single server: per-workspace DuckDB files live on that server's disk (the Docker volume). Back them up, and don't scale horizontally without shared storage.
- Voice input depends on the browser's speech recognition (Chrome/Edge/Safari).
- Public sample datasets (UCI/IBM) are optional (`python -m scripts.load_datasets`, then "try public sample datasets" in the UI).

## Resume bullets
- Built a multi-tenant "chat with your data" platform: file ingestion/cleaning (CSV/Excel/JSON/PDF/DOCX), per-tenant DuckDB stores, 75 tool-calling LangChain agents with SSE streaming.
- Designed a latency-aware planner: single agent for simple questions, parallel multi-agent teams with synthesis for complex ones.
- Implemented a sandboxed SQL layer, quotas/rate-limits, workspaces and invites on Supabase (RLS), plus n8n automation and MLflow tracking.
