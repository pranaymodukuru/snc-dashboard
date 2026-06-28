from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
import math
import os
import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import api.notifications as notifications


def _parse_time(val: str) -> tuple[int, int]:
    h, m = val.split(":")
    return int(h), int(m)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    cfg = await get_config()
    scheduler = AsyncIOScheduler(timezone=os.getenv("TZ", "Asia/Kolkata"))

    async def _morning():
        await notifications.send_morning_reminders(DB_PATH)

    async def _evening():
        await notifications.send_evening_reminders(DB_PATH)

    morning_h, morning_m = _parse_time(cfg["morning_reminder_time"])
    evening_h, evening_m = _parse_time(cfg["evening_reminder_time"])
    scheduler.add_job(_morning, CronTrigger(hour=morning_h, minute=morning_m), id="morning_reminder")
    scheduler.add_job(_evening, CronTrigger(hour=evening_h, minute=evening_m), id="evening_reminder")
    scheduler.start()
    app.state.scheduler = scheduler

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(title="SNC Check-in API", lifespan=lifespan, docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_PROTECTED_PREFIXES = ("/data/", "/config", "/admin/")
_API_KEY = os.getenv("INTERNAL_API_KEY", "")


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    path = request.url.path
    if any(path.startswith(p) for p in _PROTECTED_PREFIXES):
        if not _API_KEY or request.headers.get("X-API-Key") != _API_KEY:
            return Response(status_code=403, content="Forbidden")
    return await call_next(request)

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

WELLNESS_COLS = [
    "timestamp", "player_name", "sleep_quality", "energy_level", "body_soreness",
    "tightness_locations", "complaint_severity", "availability_status", "notes",
    "mood", "stress", "sleep_hours", "is_sick",
    # kept for backward compat with data logged before the form update
    "stress_level", "hamstring_tightness", "groin_stiffness", "lower_back_stiffness",
]
ROSTER_COLS = [
    "name", "role", "batting_style", "bowling_style", "dominant_side",
    "type", "age", "is_fast_bowler", "contact",
    "injury_history", "current_status", "status_notes",
]
SESSIONS_COLS = ["timestamp", "player_name", "session_type", "duration_mins", "rpe", "notes"]
EVENING_COLS  = [
    "timestamp", "player_name", "session_rpe", "session_duration_hours",
    "did_bowl", "bowling_volume", "bowling_intensity",
    "did_bat", "balls_faced",
]


# ── SQLite data layer ────────────────────────────────────────────────────────
# Single DB file on the volume (DATA_DIR). WAL mode lets the dashboard's reads
# run concurrently with players' submits; SQLite serializes the single writer.

DB_PATH = DATA_DIR / "snc.db"

# table -> columns
TABLES = {
    "wellness": WELLNESS_COLS,
    "roster":   ROSTER_COLS,
    "sessions": SESSIONS_COLS,
    "evening":  EVENING_COLS,
}

_INT_COLS = {
    "sleep_quality", "energy_level", "body_soreness", "mood", "stress",
    "session_rpe", "duration_mins", "rpe", "age",
    "stress_level", "hamstring_tightness", "groin_stiffness", "lower_back_stiffness",
}
_REAL_COLS = {"sleep_hours", "session_duration_hours"}
_BOOL_COLS = {"is_sick", "did_bowl", "did_bat", "is_fast_bowler"}


def _col_type(col: str) -> str:
    if col in _INT_COLS or col in _BOOL_COLS:
        return "INTEGER"
    if col in _REAL_COLS:
        return "REAL"
    return "TEXT"


def _py(v):
    """Coerce pandas/numpy scalars to plain Python so sqlite3 can bind them."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "item"):  # numpy scalar
        try:
            return v.item()
        except Exception:
            return v
    return v


async def insert_row(table: str, columns: list, row: dict):
    cols = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join("?" for _ in columns)
    values = [_py(row.get(c)) for c in columns]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA busy_timeout=5000;")
        await db.execute(f'INSERT INTO "{table}" ({cols}) VALUES ({placeholders})', values)
        await db.commit()


async def fetch_all(table: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA busy_timeout=5000;")
        db.row_factory = aiosqlite.Row
        async with db.execute(f'SELECT rowid AS id, * FROM "{table}"') as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


def _rowid(rec: dict):
    """Existing rows carry the dashboard's `id` (= sqlite rowid). New rows don't."""
    rid = _py(rec.get("id"))
    if rid in (None, ""):
        return None
    try:
        return int(rid)
    except (TypeError, ValueError):
        return None


async def replace_roster(records: list):
    cols = ", ".join(f'"{c}"' for c in ROSTER_COLS)
    placeholders = ", ".join("?" for _ in ROSTER_COLS)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA busy_timeout=5000;")
        await db.execute('DELETE FROM "roster"')
        for rec in records:
            values = [_py(rec.get(c)) for c in ROSTER_COLS]
            rid = _rowid(rec)
            # Preserve the original rowid for existing players so the dashboard's
            # cached delete ids keep pointing at the right row after a save.
            if rid is not None:
                await db.execute(
                    f'INSERT INTO "roster" (rowid, {cols}) VALUES (?, {placeholders})',
                    [rid, *values],
                )
            else:
                await db.execute(f'INSERT INTO "roster" ({cols}) VALUES ({placeholders})', values)
        await db.commit()


async def _roster_players() -> tuple[list, list, list]:
    players, fast_bowlers, allrounders = [], [], []
    try:
        for r in await fetch_all("roster"):
            players.append({"name": r.get("name") or "", "role": r.get("role") or ""})
            if str(r.get("is_fast_bowler")).strip().lower() in ("true", "1", "yes"):
                fast_bowlers.append(r.get("name"))
            if "allrounder" in str(r.get("role") or "").lower().replace("-", "").replace(" ", ""):
                allrounders.append(r.get("name"))
    except Exception:
        pass
    return players, fast_bowlers, allrounders


CONFIG_DEFAULTS = {
    "morning_reminder_time": "07:30",
    "evening_reminder_time": "18:00",
}


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        for table, cols in TABLES.items():
            coldefs = ", ".join(f'"{c}" {_col_type(c)}' for c in cols)
            await db.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({coldefs})')
            # Migrate existing tables: add any columns introduced after the table
            # was first created (CREATE TABLE IF NOT EXISTS won't add them).
            async with db.execute(f'PRAGMA table_info("{table}")') as cur:
                existing = {row[1] for row in await cur.fetchall()}
            for c in cols:
                if c not in existing:
                    await db.execute(f'ALTER TABLE "{table}" ADD COLUMN "{c}" {_col_type(c)}')
        await db.execute(
            'CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL)'
        )
        for k, v in CONFIG_DEFAULTS.items():
            await db.execute('INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)', (k, v))
        await db.commit()


async def get_config() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT key, value FROM config') as cur:
            rows = await cur.fetchall()
    cfg = dict(CONFIG_DEFAULTS)
    cfg.update({r["key"]: r["value"] for r in rows})
    return cfg


async def set_config(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
            (key, value),
        )
        await db.commit()


# ── Pydantic models ──────────────────────────────────────────────────────────

class WellnessSubmission(BaseModel):
    player_name: str
    checkin_date: Optional[str] = None  # YYYY-MM-DD; defaults to today on the server
    sleep_quality: int
    energy_level: int
    body_soreness: int
    tightness_locations: Optional[str] = ""
    complaint_severity: Optional[str] = None
    availability_status: Optional[str] = "Available"
    notes: Optional[str] = ""
    mood: Optional[int] = None
    stress: Optional[int] = None
    sleep_hours: Optional[float] = None
    is_sick: Optional[bool] = None
    # backward compat — not collected by new form
    stress_level: Optional[int] = None
    hamstring_tightness: Optional[int] = None
    groin_stiffness: Optional[int] = None
    lower_back_stiffness: Optional[int] = None


class EveningSubmission(BaseModel):
    player_name: str
    checkin_date: Optional[str] = None  # YYYY-MM-DD; defaults to today on the server
    session_rpe: int
    session_duration_hours: Optional[float] = None
    did_bowl: bool = False
    bowling_volume: Optional[str] = None
    bowling_intensity: Optional[str] = None
    did_bat: bool = False
    balls_faced: Optional[str] = None


class SessionSubmission(BaseModel):
    player_name: str
    session_type: str
    duration_mins: int
    rpe: int
    notes: Optional[str] = ""


# ── Root / static ──────────────────────────────────────────────────────────

@app.get("/")
async def root():
    # No landing page is served from the API; send callers to the health probe
    # rather than letting the bare domain 404 (and pollute the 4xx metrics).
    return RedirectResponse(url="/health")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # Browsers request this on every page load; 204 keeps it out of the 4xx count.
    return Response(status_code=204)


# ── Check-in routes ──────────────────────────────────────────────────────────

@app.get("/checkin", response_class=HTMLResponse)
async def checkin_form(request: Request):
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Anurag Nalgonda Knights — Check-in</title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>
  body { background:#0a0c0f; color:#e8edf5; font-family:'DM Sans',sans-serif;
         display:flex; flex-direction:column; align-items:center; justify-content:center;
         min-height:100vh; margin:0; text-align:center; padding:24px; }
  .logo { display:flex; flex-direction:column; align-items:center; gap:12px; margin-bottom:48px; }
  .logo-name { font-family:'Bebas Neue',sans-serif; font-size:24px; letter-spacing:3px; }
  .logo-name span { color:#E8302A; }
  .icon { font-size:56px; margin-bottom:24px; }
  h1 { font-family:'Bebas Neue',sans-serif; font-size:32px; letter-spacing:2px; margin:0 0 12px; }
  p { color:#6b7a90; font-size:14px; line-height:1.6; max-width:320px; }
</style>
</head>
<body>
  <div class="logo">
    <img src="/static/logo.avif" alt="Anurag Nalgonda Knights" style="height:56px; width:auto;">
    <div class="logo-name">ANURAG NALGONDA <span>KNIGHTS</span></div>
  </div>
  <div class="icon">🔗</div>
  <h1>USE YOUR PERSONAL LINK</h1>
  <p>This page is no longer active. Open the personal check-in link your coach shared with you.</p>
</body>
</html>
""", status_code=200)


@app.get("/checkin/{player_name}", response_class=HTMLResponse)
async def checkin_player(request: Request, player_name: str):
    players, fast_bowlers, allrounders = await _roster_players()
    return templates.TemplateResponse("checkin.html", {
        "request": request,
        "players": players,
        "fast_bowlers": fast_bowlers,
        "allrounders": allrounders,
        "preselected_player": player_name,
    })


# ── Submit endpoints ─────────────────────────────────────────────────────────

def _build_timestamp(checkin_date: Optional[str]) -> str:
    """Full ISO timestamp for a submission. If the player picked a date, stamp it
    with the current wall-clock time so intra-day ordering and the dashboard's
    datetime parsing keep working; otherwise just use now()."""
    now = datetime.now()
    if checkin_date:
        try:
            d = datetime.strptime(checkin_date, "%Y-%m-%d").date()
            return datetime.combine(d, now.time()).isoformat()
        except ValueError:
            pass  # malformed date — fall back to now()
    return now.isoformat()


@app.post("/submit/wellness")
async def submit_wellness(data: WellnessSubmission):
    row = data.model_dump()
    row["timestamp"] = _build_timestamp(data.checkin_date)
    await insert_row("wellness", WELLNESS_COLS, row)
    return {"status": "ok", "player_name": data.player_name}


@app.post("/submit/evening")
async def submit_evening(data: EveningSubmission):
    row = data.model_dump()
    row["timestamp"] = _build_timestamp(data.checkin_date)
    await insert_row("evening", EVENING_COLS, row)
    return {"status": "ok", "player_name": data.player_name}


# ── Data read endpoints ──────────────────────────────────────────────────────

@app.get("/data/wellness")
async def get_wellness():
    return JSONResponse(content=await fetch_all("wellness"))


@app.get("/data/roster")
async def get_roster():
    return JSONResponse(content=await fetch_all("roster"))


@app.get("/data/sessions")
async def get_sessions():
    return JSONResponse(content=await fetch_all("sessions"))


@app.get("/data/evening")
async def get_evening():
    return JSONResponse(content=await fetch_all("evening"))


# ── Data write endpoints ─────────────────────────────────────────────────────

@app.post("/data/sessions")
async def post_session(data: SessionSubmission):
    row = data.model_dump()
    row["timestamp"] = datetime.now().isoformat()
    await insert_row("sessions", SESSIONS_COLS, row)
    return {"status": "ok"}


@app.put("/data/roster")
async def put_roster(records: list[dict]):
    await replace_roster(records)
    return {"status": "ok"}


@app.patch("/data/{table}/{row_id}")
async def patch_row(table: str, row_id: int, updates: dict):
    if table not in TABLES:
        raise HTTPException(status_code=404, detail=f"Unknown table: {table}")
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    allowed = set(TABLES[table])
    bad = set(updates) - allowed
    if bad:
        raise HTTPException(status_code=400, detail=f"Unknown fields: {bad}")
    set_clause = ", ".join(f'"{k}" = ?' for k in updates)
    values = list(updates.values()) + [row_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA busy_timeout=5000;")
        await db.execute(f'UPDATE "{table}" SET {set_clause} WHERE rowid = ?', values)
        await db.commit()
    return {"status": "ok"}


@app.delete("/data/{table}/{row_id}")
async def delete_row(table: str, row_id: int):
    if table not in TABLES:
        raise HTTPException(status_code=404, detail=f"Unknown table: {table}")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA busy_timeout=5000;")
        await db.execute(f'DELETE FROM "{table}" WHERE rowid = ?', (row_id,))
        await db.commit()
    return {"status": "ok"}


# ── Config endpoints ─────────────────────────────────────────────────────────

@app.get("/config")
async def read_config():
    return await get_config()


class ConfigUpdate(BaseModel):
    morning_reminder_time: Optional[str] = None
    evening_reminder_time: Optional[str] = None


@app.put("/config")
async def update_config(body: ConfigUpdate, request: Request):
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        # Validate HH:MM format
        try:
            _parse_time(value)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid time format for {key}: use HH:MM")
        await set_config(key, value)

    # Reschedule jobs with new times
    scheduler = request.app.state.scheduler
    cfg = await get_config()
    if "morning_reminder_time" in updates:
        h, m = _parse_time(cfg["morning_reminder_time"])
        scheduler.reschedule_job("morning_reminder", trigger=CronTrigger(hour=h, minute=m))
    if "evening_reminder_time" in updates:
        h, m = _parse_time(cfg["evening_reminder_time"])
        scheduler.reschedule_job("evening_reminder", trigger=CronTrigger(hour=h, minute=m))

    return cfg


# ── Admin: manual notification triggers ─────────────────────────────────────

@app.post("/admin/notify/morning")
async def trigger_morning():
    return await notifications.send_morning_reminders(DB_PATH)


@app.post("/admin/notify/evening")
async def trigger_evening():
    return await notifications.send_evening_reminders(DB_PATH)


# ── Telegram bot webhook ─────────────────────────────────────────────────────
# Players send /start to the bot; it replies with their chat_id so they can
# share it with the coach to add to the roster contact field.

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    first_name = message.get("from", {}).get("first_name", "")
    if chat_id and text.startswith("/start"):
        reply = (
            f"Hi {first_name}! 👋\n\n"
            f"Your Telegram Chat ID is:\n"
            f"`{chat_id}`\n\n"
            f"Send this number to your coach so they can add it to the roster."
        )
        notifications.send_telegram(str(chat_id), reply)
    return {"ok": True}


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}
