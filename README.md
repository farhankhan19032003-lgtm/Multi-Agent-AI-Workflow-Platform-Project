# Agent Factory v3 (Pro)

A ChatGPT-style assistant for **your own company data**. Upload CSV / Excel / JSON / PDF / Word files, then chat with 75 specialist agents that query *your* data with safe SQL, draw charts, forecast, find anomalies and search your documents.

- **Simple question → one fast agent** (a single SQL query, usually a few seconds).
- **Complex question → a team of up to 3 agents working in parallel**, then one combined answer.
- **Auto mode decides** with a rule-based planner (no extra LLM call, so no routing delay). You can also pin an agent or force Team mode.

## What it does (ChatGPT parity + business extras)

| | |
|---|---|
| Chat | Streaming answers, markdown, code copy, stop, regenerate, **edit & resend**, 👍/👎, auto chat titles, rename/delete/search chats, download chat, dark/light, mobile layout |
| Inputs | Attach files (button, drag-drop, paste), **image questions**, voice input (browser support needed) |
| Your data | Upload many files; Excel multi-sheet; messy data auto-cleaned (₹/$ amounts, %, dd/mm dates, leading-zero IDs kept as text); re-upload replaces; preview and delete in **Data library** |
| Analysis | Safe read-only SQL, charts, profiling, forecast (with accuracy backtest), anomaly detection, correlations, document search; **download any result as CSV / Excel** |
| Personalisation | Custom instructions (about you / response style) |
| Sign-in | ChatGPT-style login/sign-up page: email + password (with email verification and password reset), **Continue with Google**, **Continue with GitHub** (Supabase mode) |
| Pro | Plans & daily message limits, burst rate-limit, usage meter, workspaces with invite links and members (Supabase mode) |
| Automation | The original n8n workflows (daily report, alerts, ingestion) still work |

## Run it in 2 minutes (single user, no Supabase)

1. Install Python 3.10+.
2. **Windows:** double-click `run_local.bat`  ·  **Mac/Linux:** `./run_local.sh`
3. First run creates `api/.env`. Paste your `ANTHROPIC_API_KEY` into it, run the script again.
4. Open http://127.0.0.1:8000 (on some Windows machines `localhost` resolves to IPv6 and is taken by another program; `127.0.0.1` always works), drop in a file, ask a question.

**Using Google Gemini instead of Claude (free tier available):** get a key at https://aistudio.google.com/apikey and set in `api/.env`:
```
LLM_PROVIDER=google_genai
LLM_MODEL=gemini-3.8-flash
LLM_FAST_MODEL=gemini-3.5-flash-lite
GOOGLE_API_KEY=your-key
```
Model names change often; list the ones your key can use with `google.genai.Client(api_key=...).models.list()`. Free tiers sometimes answer `503 high demand`; requests are retried automatically (`LLM_MAX_RETRIES`, default 5). The same switch works for OpenAI (`LLM_PROVIDER=openai`, `OPENAI_API_KEY`).

**Several Gemini keys (rotation):** put extra keys in `GOOGLE_API_KEYS=key2,key3`. When one key hits its quota (429), the next one answers within the same request, and the exhausted key is skipped for 60 seconds. Quota is per Google Cloud project, so keys only help if they belong to different projects you own; check Google's terms before relying on this. When switching `LLM_PROVIDER`, also change `LLM_FALLBACK_MODELS` to models of the same provider.

Data is stored in `api/data/` (SQLite + one DuckDB file per workspace). No login in this mode.

## Run it for many customers (Supabase)

1. Create a Supabase project. In the SQL editor run, in order: `supabase/schema.sql`, `schema_v2_chat.sql`, `schema_v3_pro.sql`.
2. Copy `.env.example` to `.env` and fill `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`, `ANTHROPIC_API_KEY`. Keep `STORAGE=supabase`, `DEV_NO_AUTH=false`.
3. `docker compose up -d --build` (add `--profile prod` for HTTPS via Caddy; set `API_DOMAIN`).
4. Users sign up in the UI; each gets a private workspace. Share an invite link (Settings → Workspace) to add teammates.
5. **Social login (optional).** In Supabase → Authentication → Sign In / Providers enable **Google** and/or **GitHub** and paste the Client ID and Secret from Google Cloud Console / GitHub Developer settings. In both, the callback URL is `https://<your-project>.supabase.co/auth/v1/callback`. Under Authentication → URL Configuration set the Site URL and add your app URL (for example `http://127.0.0.1:8000` locally, your domain in production) to Redirect URLs. Google's consent screen must be **published** or only listed test users can sign in. The login buttons check which providers are enabled and show a friendly message if one is not.
6. **Email sending.** Supabase's built-in mailer is heavily rate-limited. For real traffic configure custom SMTP, or turn off "Confirm email".
7. Upgrade a customer: `python -m scripts.set_plan <tenant_id> pro` (or edit `tenants.plan`). Limits: Free 40 / Pro 3000 messages per day per user (`FREE_DAILY_MESSAGES`, `PRO_DAILY_MESSAGES`).

## Deploy to a VPS (Docker + automatic HTTPS)

The app keeps each workspace's DuckDB file on disk, so it needs a server with a **persistent disk** (not a serverless host). A 2 GB RAM VPS is enough.

1. Point a DNS **A record** (for example `app.yourdomain.com`) at the server's IP and install Docker.
2. `git clone` this repo on the server and create `.env` in the repo root (copy `api/.env`; it is never committed). Add `API_DOMAIN=app.yourdomain.com` and `CORS_ORIGINS=https://app.yourdomain.com`, keep `STORAGE=supabase` and `DEV_NO_AUTH=false`.
3. `docker compose -f docker-compose.prod.yml up -d --build` starts the API and Caddy (certificates are issued automatically). The full `docker-compose.yml` additionally runs n8n and MLflow.
4. Check `https://app.yourdomain.com/health`, then add the domain to Supabase → URL Configuration.
5. Back up the `analytics_data` Docker volume regularly.

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
cd api && pip install -r requirements.txt pytest && python -m pytest tests -q      # 39 backend tests
cd tests/ui && npm install && python ui_server.py &  node run.js                    # 49 chat-UI checks (jsdom)
cd tests/ui && node auth.js                                                         # login / sign-up / reset / Google / GitHub (fake Supabase client)
```
Tests use a scripted fake LLM, so they need no API key. Start `ui_server.py` fresh for each `run.js` run: it keeps the uploaded file between runs.

## Honest limits
- **What has been run live:** the backend against a real Supabase project (auth enforcement, per-user workspace creation, upload, 24 concurrent requests, streaming chat with SQL + chart) with Google Gemini, and Google and GitHub sign-in in a real browser. **Not run live:** the Claude (Anthropic) provider, OpenAI, and the `docker-compose.prod.yml` stack.
- Email sign-up, verification and password reset are covered by simulated-DOM tests only; check them once in a real browser against your own Supabase project and mailer.
- A chat answer takes roughly 20-30 seconds with Gemini (about three model steps); each Supabase round trip adds around half a second. Layout was not checked on phones.
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
