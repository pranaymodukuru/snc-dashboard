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
BOWLING_CSV  = DATA_DIR / "bowling.csv"

WELLNESS_COLS = [
    "timestamp", "player_name", "sleep_quality", "energy_level", "body_soreness",
    "mood", "stress_level", "hamstring_tightness", "groin_stiffness",
    "lower_back_stiffness", "notes",
]
ROSTER_COLS = [
    "name", "role", "type", "age", "is_fast_bowler",
    "injury_history", "current_status", "status_notes",
]
SESSIONS_COLS = ["timestamp", "player_name", "session_type", "duration_mins", "rpe", "notes"]
BOWLING_COLS  = ["timestamp", "player_name", "match_balls", "net_balls", "high_intensity_balls", "notes"]


def ensure_csv(path: Path, columns: list):
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)


def append_row(path: Path, columns: list, row: dict):
    ensure_csv(path, columns)
    df = pd.read_csv(path)
    new_row = pd.DataFrame([{col: row.get(col) for col in columns}])
    pd.concat([df, new_row], ignore_index=True).to_csv(path, index=False)


def df_to_json_response(df: pd.DataFrame) -> JSONResponse:
    """Serialize a DataFrame to JSON, converting NaN → null safely."""
    return JSONResponse(content=json.loads(df.to_json(orient="records")))


# ── Pydantic models ──────────────────────────────────────────────────────────

class WellnessSubmission(BaseModel):
    player_name: str
    sleep_quality: int
    energy_level: int
    body_soreness: int
    mood: int
    stress_level: int
    hamstring_tightness: Optional[int] = None
    groin_stiffness: Optional[int] = None
    lower_back_stiffness: Optional[int] = None
    notes: Optional[str] = ""


class SessionSubmission(BaseModel):
    player_name: str
    session_type: str
    duration_mins: int
    rpe: int
    notes: Optional[str] = ""


class BowlingSubmission(BaseModel):
    player_name: str
    match_balls: int = 0
    net_balls: int = 0
    high_intensity_balls: int = 0
    notes: Optional[str] = ""


# ── Check-in form ────────────────────────────────────────────────────────────

@app.get("/checkin", response_class=HTMLResponse)
async def checkin_form(request: Request):
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
    return templates.TemplateResponse("checkin.html", {
        "request": request,
        "players": players,
        "fast_bowlers": fast_bowlers,
    })


@app.post("/submit/wellness")
async def submit_wellness(data: WellnessSubmission):
    row = data.model_dump()
    row["timestamp"] = datetime.now().isoformat()
    append_row(WELLNESS_CSV, WELLNESS_COLS, row)
    return {"status": "ok", "player_name": data.player_name}


# ── Data read endpoints (used by dashboard) ──────────────────────────────────

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


@app.get("/data/bowling")
async def get_bowling():
    ensure_csv(BOWLING_CSV, BOWLING_COLS)
    return df_to_json_response(pd.read_csv(BOWLING_CSV))


# ── Data write endpoints (used by dashboard) ─────────────────────────────────

@app.post("/data/sessions")
async def post_session(data: SessionSubmission):
    row = data.model_dump()
    row["timestamp"] = datetime.now().isoformat()
    append_row(SESSIONS_CSV, SESSIONS_COLS, row)
    return {"status": "ok"}


@app.post("/data/bowling")
async def post_bowling(data: BowlingSubmission):
    row = data.model_dump()
    row["timestamp"] = datetime.now().isoformat()
    append_row(BOWLING_CSV, BOWLING_COLS, row)
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
