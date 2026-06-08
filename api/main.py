from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import pandas as pd
from pathlib import Path
from datetime import datetime
import json
import os

app = FastAPI(title="SNC Check-in API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

WELLNESS_CSV = DATA_DIR / "wellness.csv"
ROSTER_CSV   = DATA_DIR / "roster.csv"
SESSIONS_CSV = DATA_DIR / "sessions.csv"
EVENING_CSV  = DATA_DIR / "evening_checkin.csv"

WELLNESS_COLS = [
    "timestamp", "player_name", "sleep_quality", "energy_level", "body_soreness",
    "tightness_locations", "availability_status", "notes",
    # kept for backward compat with data logged before the form update
    "mood", "stress_level", "hamstring_tightness", "groin_stiffness", "lower_back_stiffness",
]
ROSTER_COLS = [
    "name", "role", "batting_style", "bowling_style", "dominant_side",
    "type", "age", "is_fast_bowler", "contact",
    "injury_history", "current_status", "status_notes",
]
SESSIONS_COLS = ["timestamp", "player_name", "session_type", "duration_mins", "rpe", "notes"]
EVENING_COLS  = [
    "timestamp", "player_name", "session_rpe",
    "did_bowl", "bowling_volume", "bowling_intensity",
]


def ensure_csv(path: Path, columns: list):
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)


def append_row(path: Path, columns: list, row: dict):
    ensure_csv(path, columns)
    df = pd.read_csv(path)
    new_row = pd.DataFrame([{col: row.get(col) for col in columns}])
    pd.concat([df, new_row], ignore_index=True).to_csv(path, index=False)


def df_to_json_response(df: pd.DataFrame) -> JSONResponse:
    return JSONResponse(content=json.loads(df.to_json(orient="records")))


def _roster_players() -> tuple[list, list]:
    ensure_csv(ROSTER_CSV, ROSTER_COLS)
    players, fast_bowlers = [], []
    try:
        roster = pd.read_csv(ROSTER_CSV)
        if not roster.empty:
            players = roster[["name", "role"]].fillna("").to_dict("records")
            fast_bowlers = roster[
                roster["is_fast_bowler"].astype(str).str.lower().isin(["true", "1", "yes"])
            ]["name"].tolist()
    except Exception:
        pass
    return players, fast_bowlers


# ── Pydantic models ──────────────────────────────────────────────────────────

class WellnessSubmission(BaseModel):
    player_name: str
    sleep_quality: int
    energy_level: int
    body_soreness: int
    tightness_locations: Optional[str] = ""
    availability_status: Optional[str] = "Available"
    notes: Optional[str] = ""
    # backward compat — not collected by new form
    mood: Optional[int] = None
    stress_level: Optional[int] = None
    hamstring_tightness: Optional[int] = None
    groin_stiffness: Optional[int] = None
    lower_back_stiffness: Optional[int] = None


class EveningSubmission(BaseModel):
    player_name: str
    session_rpe: int
    did_bowl: bool = False
    bowling_volume: Optional[str] = None
    bowling_intensity: Optional[str] = None


class SessionSubmission(BaseModel):
    player_name: str
    session_type: str
    duration_mins: int
    rpe: int
    notes: Optional[str] = ""


# ── Check-in routes ──────────────────────────────────────────────────────────

@app.get("/checkin", response_class=HTMLResponse)
async def checkin_form(request: Request):
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Knights — Check-in</title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>
  body { background:#0a0c0f; color:#e8edf5; font-family:'DM Sans',sans-serif;
         display:flex; flex-direction:column; align-items:center; justify-content:center;
         min-height:100vh; margin:0; text-align:center; padding:24px; }
  .logo { font-family:'Bebas Neue',sans-serif; font-size:28px; letter-spacing:4px; margin-bottom:48px; }
  .logo span { color:#00c2ff; }
  .icon { font-size:56px; margin-bottom:24px; }
  h1 { font-family:'Bebas Neue',sans-serif; font-size:32px; letter-spacing:2px; margin:0 0 12px; }
  p { color:#6b7a90; font-size:14px; line-height:1.6; max-width:320px; }
</style>
</head>
<body>
  <div class="logo">NALGONDA <span>KNIGHTS</span></div>
  <div class="icon">🔗</div>
  <h1>USE YOUR PERSONAL LINK</h1>
  <p>This page is no longer active. Open the personal check-in link your coach shared with you.</p>
</body>
</html>
""", status_code=410)


@app.get("/checkin/{player_name}", response_class=HTMLResponse)
async def checkin_player(request: Request, player_name: str):
    players, fast_bowlers = _roster_players()
    return templates.TemplateResponse("checkin.html", {
        "request": request,
        "players": players,
        "fast_bowlers": fast_bowlers,
        "preselected_player": player_name,
    })


# ── Submit endpoints ─────────────────────────────────────────────────────────

@app.post("/submit/wellness")
async def submit_wellness(data: WellnessSubmission):
    row = data.model_dump()
    row["timestamp"] = datetime.now().isoformat()
    append_row(WELLNESS_CSV, WELLNESS_COLS, row)
    return {"status": "ok", "player_name": data.player_name}


@app.post("/submit/evening")
async def submit_evening(data: EveningSubmission):
    row = data.model_dump()
    row["timestamp"] = datetime.now().isoformat()
    append_row(EVENING_CSV, EVENING_COLS, row)
    return {"status": "ok", "player_name": data.player_name}


# ── Data read endpoints ──────────────────────────────────────────────────────

@app.get("/data/wellness")
async def get_wellness():
    ensure_csv(WELLNESS_CSV, WELLNESS_COLS)
    return df_to_json_response(pd.read_csv(WELLNESS_CSV))


@app.get("/data/roster")
async def get_roster():
    ensure_csv(ROSTER_CSV, ROSTER_COLS)
    return df_to_json_response(pd.read_csv(ROSTER_CSV))


@app.get("/data/sessions")
async def get_sessions():
    ensure_csv(SESSIONS_CSV, SESSIONS_COLS)
    return df_to_json_response(pd.read_csv(SESSIONS_CSV))


@app.get("/data/evening")
async def get_evening():
    ensure_csv(EVENING_CSV, EVENING_COLS)
    return df_to_json_response(pd.read_csv(EVENING_CSV))


# ── Data write endpoints ─────────────────────────────────────────────────────

@app.post("/data/sessions")
async def post_session(data: SessionSubmission):
    row = data.model_dump()
    row["timestamp"] = datetime.now().isoformat()
    append_row(SESSIONS_CSV, SESSIONS_COLS, row)
    return {"status": "ok"}


@app.put("/data/roster")
async def put_roster(records: list[dict]):
    df = pd.DataFrame(records)
    df.to_csv(ROSTER_CSV, index=False)
    return {"status": "ok"}


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}
