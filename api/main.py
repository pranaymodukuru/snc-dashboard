from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import pandas as pd
from pathlib import Path
from datetime import datetime
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

WELLNESS_COLS = [
    "timestamp", "player_name", "sleep_quality", "energy_level", "body_soreness",
    "mood", "stress_level", "hamstring_tightness", "groin_stiffness",
    "lower_back_stiffness", "notes",
]
ROSTER_COLS = [
    "name", "role", "type", "age", "is_fast_bowler",
    "injury_history", "current_status", "status_notes",
]


def ensure_csv(path: Path, columns: list):
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)


def append_row(path: Path, columns: list, row: dict):
    ensure_csv(path, columns)
    df = pd.read_csv(path)
    new_row = pd.DataFrame([{col: row.get(col) for col in columns}])
    pd.concat([df, new_row], ignore_index=True).to_csv(path, index=False)


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


@app.get("/health")
async def health():
    return {"status": "ok"}
