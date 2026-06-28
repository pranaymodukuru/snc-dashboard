# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Nalgonda Knights S&C (strength & conditioning) dashboard for a cricket team. Two
separate Python services deployed as two Railway services from this one repo:

- **`api/`** — FastAPI. Owns the SQLite database, serves the player check-in form,
  exposes read/write JSON endpoints.
- **`dashboard/`** — Streamlit. Password-protected coach UI. Holds **no** database
  access — it reaches all data through the API over HTTP.

## Commands

```bash
uv sync                                              # install all deps (one venv, both services)
uv run uvicorn api.main:app --reload --port 8000     # run the API (check-in form + data endpoints)
uv run streamlit run dashboard/app.py                # run the dashboard (http://localhost:8501)
```

Both services must run together for the dashboard to show data. Copy `.env.example`
to `.env` first and set `DASHBOARD_PASSWORD`. There is no test suite, linter, or
build step configured.

## Architecture — the key constraint

The SQLite DB (`data/snc.db`, created on first API run) lives **only on the API
service**. The dashboard never opens the file; it goes through the API:

```
Player → GET /checkin/<name> (FastAPI form) → POST /submit/wellness → snc.db
Coach  → Streamlit dashboard → GET/POST/PUT/DELETE/PATCH API HTTP endpoints → snc.db
```

This split exists because Railway mounts the persistent Volume on the API service
only, and SQLite is single-writer. **Do not add direct DB access to the dashboard.**
When you add a data field or feature, the change usually spans both files:

1. `api/main.py` — column lists (`WELLNESS_COLS`, `ROSTER_COLS`, `SESSIONS_COLS`,
   `EVENING_COLS`), the matching Pydantic model, and type sets (`_INT_COLS`,
   `_REAL_COLS`, `_BOOL_COLS`).
2. `dashboard/app.py` — the corresponding column-list constant and the `load_*`
   loader that builds the DataFrame.

These two column-list definitions are duplicated across the files by hand and must
be kept in sync.

### Database details (`api/main.py`)

- Four tables, all schema-driven from the `TABLES` dict; `init_db()` runs
  `CREATE TABLE IF NOT EXISTS` on startup via the FastAPI `lifespan` hook.
- WAL mode + `busy_timeout=5000` so dashboard reads don't block player submits.
- `fetch_all` returns `rowid AS id` — the dashboard uses that `id` for DELETE and
  to preserve rowids on roster save (`replace_roster` does DELETE-all + re-INSERT
  but keeps original rowids so cached delete ids stay valid).
- Several `WELLNESS_COLS` are kept only for backward compat with data logged before
  a form change (`stress_level`, `hamstring_tightness`, etc.) — don't reuse them.
- `PATCH /data/{table}/{id}` — partial update endpoint for correcting individual
  wellness, evening, or session rows from the dashboard's edit dialog.

### Internal API key

Admin and mutating endpoints (`/admin/*`, `/config`, `PATCH /data/*`) are gated
behind `X-API-Key` middleware. The key comes from `INTERNAL_API_KEY` env var. An
empty value disables the check locally; always set it in production. The dashboard
injects the key automatically via `_api_session`.

### Telegram reminders (`api/notifications.py`)

APScheduler runs inside the API's lifespan and fires two daily cron jobs:

- **Morning reminder** (default 07:30) — messages players who haven't submitted a
  morning wellness check-in yet.
- **Evening reminder** (default 18:00) — same for evening check-ins.

Reminder times are adjustable at runtime via `PUT /config` (no redeploy needed).
`TZ` controls the scheduler timezone (default `Asia/Kolkata`). Telegram is
optional — jobs run silently if `TELEGRAM_BOT_TOKEN` is unset. Manual triggers
available at `POST /admin/notify/morning` and `POST /admin/notify/evening`.

### Dashboard details (`dashboard/app.py`)

- Single ~2100-line file. Five tabs, each a `@st.fragment` render function:
  `render_overview`, `render_player_load`, `render_squad`, `render_admin_tab`,
  `render_raw_data`.
- Auth is a session-state password check (`require_auth`) against
  `DASHBOARD_PASSWORD`; the whole app errors at import if that env var is missing.
- All four `load_*` functions are `@st.cache_data(ttl=30)`. After any write
  (session, roster save, delete, patch) call `st.cache_data.clear()` so the UI
  refreshes.
- Derived metrics computed in the dashboard, not stored: `load_au = duration_mins
  × rpe`; readiness score = `Sleep + Energy + (6 − Soreness)` (max 15; Green ≥ 13,
  Yellow 10–12, Red < 10); ACWR (acute:chronic workload ratio, 7-day / 28-day).
- **Compliance banner** at the top of Overview shows today's morning, evening, and
  combined submission rates across the full squad.
- **Edit dialog** in Raw Data tab lets coaches correct any wellness, evening, or
  session row via `_patch_row()` → `PATCH /data/{table}/{id}`.
- **Squad ACWR panel** in Overview shows a horizontal bar chart of every player's
  current ACWR coloured by risk band (undertraining / optimal / caution / high risk).

## Environment variables

| Var | Used by | Purpose |
|-----|---------|---------|
| `DASHBOARD_PASSWORD` | dashboard | coach login (required, hard-fails if unset) |
| `API_URL` | dashboard | where to reach the API (Railway: private `*.railway.internal:8000`) |
| `PUBLIC_URL` | dashboard | API's public domain, used to build shareable player check-in links (falls back to `API_URL`) |
| `INTERNAL_API_KEY` | api + dashboard | shared secret for admin/mutating endpoints; generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATA_DIR` | api | DB directory; `./data` locally, `/data` (Volume mount) on Railway |
| `TELEGRAM_BOT_TOKEN` | api | Telegram bot token for player reminders (optional) |
| `TZ` | api | scheduler timezone for reminders (default: `Asia/Kolkata`) |

## Claude Code hooks

A `PreToolUse` hook at `.claude/hooks/protect-env.js` blocks Claude from reading
`.env` files (`.env`, `.env.local`, `.env.production`, etc.). `.env.sample` is
explicitly allowed. If you need to inspect secrets during a session, run the
command directly in the terminal with `! cat .env`.

## Deployment

Push to `main` auto-redeploys both Railway services. Each service builds from its
own Dockerfile (`api/Dockerfile`, `dashboard/Dockerfile`) with the repo root as
build context. API health probe is `/health`. See README.md for full Railway setup.
