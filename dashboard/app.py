from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta, date
import os
import urllib.parse
import requests

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Nalgonda Knights — Dashboard",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD")
if not DASHBOARD_PASSWORD:
    raise RuntimeError("DASHBOARD_PASSWORD env var not set")
API_URL = os.getenv("API_URL", "http://localhost:8000")

# Public base URL for player-facing links (check-in forms etc.)
# Set PUBLIC_URL in Railway dashboard env vars to the API's public domain.
# Locally falls back to API_URL (http://localhost:8000).
PUBLIC_URL = os.getenv("PUBLIC_URL", API_URL).rstrip("/")

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stSidebar"] { display: none; }
  [data-testid="collapsedControl"] { display: none; }
  [data-testid="stToolbar"] { display: none; }
  #MainMenu { display: none; }
  header[data-testid="stHeader"] { display: none; }
  .block-container { padding-top: 1.5rem; }
  .metric-card {
    background: #161a22; border: 1px solid #1f2530; border-radius: 10px;
    padding: 16px 18px; height: 100%;
  }
  .metric-label { color: #6b7a90; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
  .metric-value { font-size: 38px; font-weight: 700; margin-top: 2px; line-height: 1; }
  .alert-item {
    background: rgba(239,68,68,0.08); border-left: 3px solid #ef4444;
    padding: 10px 12px; border-radius: 4px; margin: 6px 0;
  }
  .alert-name { font-weight: 600; font-size: 13px; }
  .alert-tags { font-size: 11px; color: #ef4444; margin-top: 2px; }
  div[data-testid="stHorizontalBlock"] { gap: 12px; }
</style>
""", unsafe_allow_html=True)

# ── Auth ─────────────────────────────────────────────────────────────────────
def require_auth():
    if st.session_state.get("authenticated"):
        return
    st.markdown("""
    <div style="text-align:center; padding: 80px 0 24px;">
      <div style="font-size: 42px; font-weight: 800; letter-spacing: 4px; color: #e8edf5;">
        NALGONDA <span style="color: #00c2ff;">KNIGHTS</span>
      </div>
      <div style="color: #6b7a90; font-size: 12px; letter-spacing: 3px; text-transform: uppercase; margin-top: 6px;">
        S&amp;C DASHBOARD
      </div>
    </div>
    """, unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        pwd = st.text_input("Password", type="password", label_visibility="collapsed",
                            placeholder="Enter password")
        if st.button("ACCESS DASHBOARD", use_container_width=True, type="primary"):
            if pwd == DASHBOARD_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password")
    st.stop()

require_auth()

# ── Constants ────────────────────────────────────────────────────────────────
WELLNESS_COLS = [
    "timestamp","player_name","sleep_quality","energy_level","body_soreness",
    "tightness_locations","complaint_severity","availability_status","notes",
    "mood","stress","sleep_hours","is_sick",
    "stress_level","hamstring_tightness","groin_stiffness","lower_back_stiffness",
]
ROSTER_COLS   = [
    "name","role","batting_style","bowling_style","dominant_side",
    "type","age","is_fast_bowler","contact",
    "injury_history","current_status","status_notes",
]
SESSIONS_COLS = ["timestamp","player_name","session_type","duration_mins","rpe","notes"]
EVENING_COLS  = ["timestamp","player_name","session_rpe","session_duration_hours","did_bowl","bowling_volume","bowling_intensity","did_bat","balls_faced"]

RPE_LABELS = {
    (1, 2):  ("Recovery",  "#22c55e"),
    (3, 4):  ("Easy",      "#00c2ff"),
    (5, 6):  ("Moderate",  "#f59e0b"),
    (7, 8):  ("Hard",      "#ef4444"),
    (9, 9):  ("Very Hard", "#ef4444"),
    (10, 10):("Maximal",   "#ef4444"),
}

WELLNESS_INTERP = [
    (4.5, 5.0, "Excellent Readiness", "#22c55e"),
    (3.5, 4.4, "Normal",              "#00c2ff"),
    (2.5, 3.4, "Monitor",             "#f59e0b"),
    (0.0, 2.4, "High Attention",      "#ef4444"),
]

STATUS_COLORS = {
    "Full Training": "#22c55e",
    "Modified":      "#00c2ff",
    "Recovery":      "#f59e0b",
    "Rehab":         "#f97316",
    "Unavailable":   "#ef4444",
}

DARK_LAYOUT = dict(
    paper_bgcolor="#0a0c0f",
    plot_bgcolor="#111318",
    font=dict(color="#e8edf5"),
    margin=dict(t=24, b=24, l=8, r=8),
)

# ── Data helpers ─────────────────────────────────────────────────────────────

def _api_get(path: str) -> list:
    """GET from API; returns list of records or empty list on error."""
    try:
        r = requests.get(f"{API_URL}{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.warning(f"Could not reach API ({path}): {e}")
        return []


@st.cache_data(ttl=30)
def load_wellness() -> pd.DataFrame:
    records = _api_get("/data/wellness")
    df = pd.DataFrame(records) if records else pd.DataFrame(columns=WELLNESS_COLS)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601")
        df["date"] = df["timestamp"].dt.date
    return df


@st.cache_data(ttl=30)
def load_roster() -> pd.DataFrame:
    records = _api_get("/data/roster")
    df = pd.DataFrame(records) if records else pd.DataFrame(columns=ROSTER_COLS)
    for col in ROSTER_COLS:
        if col not in df.columns:
            df[col] = None
    if not df.empty:
        str_cols = ["name","role","batting_style","bowling_style","dominant_side",
                    "type","contact","injury_history","current_status","status_notes"]
        df = df.assign(**{col: df[col].fillna("") for col in str_cols if col in df.columns})
        if "is_fast_bowler" in df.columns:
            df = df.assign(
                is_fast_bowler=df["is_fast_bowler"].fillna(False).infer_objects(copy=False).astype(bool)
            )
    return df


@st.cache_data(ttl=30)
def load_evening() -> pd.DataFrame:
    records = _api_get("/data/evening")
    df = pd.DataFrame(records) if records else pd.DataFrame(columns=EVENING_COLS)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601")
        df["date"] = df["timestamp"].dt.date
        if "session_rpe" in df.columns and "session_duration_hours" in df.columns:
            df["evening_au"] = df["session_rpe"] * df["session_duration_hours"].fillna(0)
    return df


@st.cache_data(ttl=30)
def load_sessions() -> pd.DataFrame:
    records = _api_get("/data/sessions")
    df = pd.DataFrame(records) if records else pd.DataFrame(columns=SESSIONS_COLS)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601")
        df["date"] = df["timestamp"].dt.date
        df["load_au"] = df["duration_mins"] * df["rpe"]
    return df


def is_fast_bowler(val) -> bool:
    return str(val).lower().strip() in ("true", "1", "yes")

def fast_bowlers(roster: pd.DataFrame) -> list:
    if roster.empty or "is_fast_bowler" not in roster.columns:
        return []
    return roster[roster["is_fast_bowler"].apply(is_fast_bowler)]["name"].tolist()

# ── Header ───────────────────────────────────────────────────────────────────
c_title, c_logout = st.columns([5, 1])
with c_title:
    st.markdown("""
    <div style="font-size: 26px; font-weight: 800; letter-spacing: 3px; line-height: 1.2;">
      NALGONDA <span style="color: #00c2ff;">KNIGHTS</span>
      <span style="font-size: 12px; color: #6b7a90; font-weight: 400; letter-spacing: 2px;"> — S&amp;C DASHBOARD</span>
    </div>
    """, unsafe_allow_html=True)
with c_logout:
    if st.button("Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

st.markdown("<hr style='border-color:#1f2530; margin: 8px 0 16px;'>", unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_overview, tab_load, tab_squad, tab_admin, tab_raw = st.tabs([
    "Team Overview", "Load Monitor", "Player Profiles", "Admin", "Raw Data",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — COACH SIDE DASHBOARD (Overview)
# ════════════════════════════════════════════════════════════════════════════

READINESS_SCORE_RANGES = [
    ("Normal",            "#22c55e", 18, 25),
    ("Monitor",           "#f59e0b", 14, 17),
    ("Potential Concern", "#ef4444",  0, 13),
]


def readiness_score(row) -> int:
    """Sleep + Energy + inv(Soreness) + inv(Stress) + Mood → max 25."""
    sleep   = float(row.get("sleep_quality",  3) or 3)
    energy  = float(row.get("energy_level",   3) or 3)
    soreness= float(row.get("body_soreness",  3) or 3)
    stress  = float(row.get("stress",         3) or 3)
    mood    = float(row.get("mood",           3) or 3)
    return int(sleep + energy + (6 - soreness) + (6 - stress) + mood)

def readiness_band(score: int) -> tuple[str, str]:
    for label, color, lo, hi in READINESS_SCORE_RANGES:
        if lo <= score <= hi:
            return label, color
    return "Red", "#ef4444"


# ── Shared display helpers (used by Overview + Player Load) ───────────────────

def _rpe_color(rpe: float) -> str:
    if rpe <= 2:  return "#22c55e"
    if rpe <= 4:  return "#00c2ff"
    if rpe <= 6:  return "#f59e0b"
    if rpe <= 8:  return "#ef4444"
    return "#ff4444"

def _load_color(load: float) -> str:
    if load < 200: return "#22c55e"
    if load < 400: return "#f59e0b"
    return "#ef4444"

def _metric_card(label: str, value: str, sub: str = "", color: str = "#e8edf5") -> str:
    return f"""
    <div class="metric-card">
      <div class="metric-label">{label}</div>
      <div class="metric-value" style="color:{color};font-size:32px;">{value}</div>
      {"<div style='font-size:11px;color:#6b7a90;margin-top:4px;'>"+sub+"</div>" if sub else ""}
    </div>"""


# ── Overview (AMS) helpers ───────────────────────────────────────────────────

def wellness_pct(row) -> int:
    """Readiness score (max 25) expressed as a 0–100% wellness figure."""
    return int(round(readiness_score(row) / 25 * 100))

def wellness_band(pct: int) -> tuple[str, str]:
    """AMS readiness bands: Ready ≥80 · Monitor 60–79 · Flagged <60."""
    if pct >= 80: return "Ready",   "#22c55e"
    if pct >= 60: return "Monitor", "#f59e0b"
    return "Flagged", "#ef4444"

# Map roster `current_status` / self-reported availability → 4 AMS buckets.
AMS_AVAIL_BUCKETS = [
    ("Full Training",    "#22c55e"),
    ("Modified Training","#f59e0b"),
    ("Rehab",            "#f97316"),
    ("Unavailable",      "#ef4444"),
]
_AVAIL_TO_BUCKET = {
    "Full Training": "Full Training", "Available": "Full Training",
    "Modified": "Modified Training", "Modified Training": "Modified Training",
    "Recovery": "Modified Training", "Recovery Only": "Modified Training",
    "Rehab": "Rehab",
    "Unavailable": "Unavailable",
}

def aggregate_range(wellness: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """One row per player averaging their wellness submissions across [start, end].
    Numeric metrics are means; categorical fields take the latest value in range."""
    if wellness.empty or "date" not in wellness.columns:
        return pd.DataFrame()
    rng = wellness[(wellness["date"] >= start) & (wellness["date"] <= end)]
    if rng.empty:
        return pd.DataFrame()
    num_cols = ["sleep_quality", "energy_level", "body_soreness", "mood", "stress", "sleep_hours"]
    rows = []
    for name, g in rng.groupby("player_name"):
        g = g.sort_values("timestamp")
        rec = {"player_name": name, "submissions": len(g)}
        for c in num_cols:
            if c in g.columns:
                s = pd.to_numeric(g[c], errors="coerce").dropna()
                rec[c] = round(s.mean(), 1) if not s.empty else None
        last = g.iloc[-1]
        for c in ["availability_status", "tightness_locations", "complaint_severity", "is_sick"]:
            rec[c] = last.get(c)
        rows.append(rec)
    return pd.DataFrame(rows)


def _ams_metric(emoji: str, value: str, label: str, color: str) -> str:
    return f"""
    <div style="text-align:center;flex:1;">
      <div style="font-size:26px;line-height:1;">{emoji}</div>
      <div style="font-size:26px;font-weight:800;color:{color};margin-top:6px;line-height:1;">{value}</div>
      <div style="font-size:10px;color:#6b7a90;letter-spacing:1px;text-transform:uppercase;margin-top:4px;">{label}</div>
    </div>"""


def _panel_title(text: str) -> None:
    st.markdown(
        f"<div style='font-size:12px;font-weight:700;color:#9fb0c6;letter-spacing:1.5px;"
        f"text-transform:uppercase;margin:0 0 10px;'>{text}</div>",
        unsafe_allow_html=True,
    )


def _top_session_loads(evening: pd.DataFrame, start: date, end: date,
                       roster: pd.DataFrame = None) -> list:
    """Each player's single heaviest evening session in range, sorted desc.
    Load = RPE × duration (mins)."""
    rows = []
    if evening.empty or "date" not in evening.columns:
        return rows
    rng = evening[(evening["date"] >= start) & (evening["date"] <= end)]
    if rng.empty:
        return rows
    role_map = {}
    if roster is not None and not roster.empty:
        for _, row in roster.iterrows():
            role_map[row.get("name")] = (row.get("type", ""), row.get("is_fast_bowler", False))
    for name, g in rng.groupby("player_name"):
        best = None
        for _, r in g.iterrows():
            rpe, hrs = r.get("session_rpe"), r.get("session_duration_hours")
            if pd.isna(rpe) or pd.isna(hrs) or not hrs:
                continue
            dur = int(round(float(hrs) * 60))
            load = int(round(float(rpe) * dur))
            if best is None or load > best["load"]:
                best = {"player": name, "dur": dur, "rpe": int(rpe), "load": load}
        if best:
            role, is_fb = role_map.get(name, ("", False))
            best["role"] = role
            best["is_fb"] = is_fb
            rows.append(best)
    rows.sort(key=lambda x: x["load"], reverse=True)
    return rows


# Per-role weekly AU reference ranges (session-RPE load = RPE × minutes).
# A week outside the player's range is flagged red.
AU_BANDS = {
    "Fast Bowler": (2500, 4000),
    "Spinner":     (2000, 3000),
    "Batsman":     (2000, 3500),
}


def player_au_band(role, is_fb) -> tuple:
    """(band name, low, high) for a player based on role / fast-bowler flag."""
    r = str(role or "").strip().lower()
    if is_fast_bowler(is_fb):
        name = "Fast Bowler"
    elif "spin" in r or "off-spin" in r or "leg-spin" in r:
        name = "Spinner"
    elif "bowler" in r or "rounder" in r:
        name = "Fast Bowler"
    else:
        name = "Batsman"
    return (name, *AU_BANDS[name])


def _load_color_for_role(load: float, role: str, is_fb) -> str:
    _, lo, hi = player_au_band(role, is_fb)
    if load < lo:  return "#f59e0b"   # below range → orange
    if load > hi:  return "#ef4444"   # above range → red
    return "#22c55e"                  # in range → green


def _weekly_loads(evening: pd.DataFrame, roster: pd.DataFrame, start: date, end: date) -> list:
    """Per-player weekly AU over [start, end], normalised to a 7-day equivalent so
    the role bands stay valid for any range length. Load = RPE × minutes."""
    if evening.empty or "date" not in evening.columns:
        return []
    rng = evening[(evening["date"] >= start) & (evening["date"] <= end)].copy()
    if rng.empty:
        return []
    rng["au"] = (pd.to_numeric(rng["session_rpe"], errors="coerce")
                 * pd.to_numeric(rng["session_duration_hours"], errors="coerce") * 60)
    totals = rng.groupby("player_name")["au"].sum().dropna()
    span = max((end - start).days + 1, 1)
    role_map = {}
    if not roster.empty:
        for _, r in roster.iterrows():
            role_map[r.get("name")] = (r.get("role"), r.get("is_fast_bowler"))
    out = []
    for name, au in totals.items():
        weekly = au * 7.0 / span
        role, fb = role_map.get(name, (None, None))
        band, lo, hi = player_au_band(role, fb)
        out.append({"player": name, "weekly": int(round(weekly)), "total": int(round(au)),
                    "band": band, "lo": lo, "hi": hi, "in_band": lo <= weekly <= hi})
    out.sort(key=lambda x: x["weekly"], reverse=True)
    return out


# Representative ball count for each bowling-volume bucket logged in the evening
# check-in (midpoint of the range; 60+ taken as ~72). Lets us estimate balls
# bowled from the volume data players already submit.
VOLUME_BALLS = {"<24": 12, "24-36": 30, "36-48": 42, "48-60": 54, "60+": 72}


def _bowling_load(evening: pd.DataFrame, roster: pd.DataFrame, start: date, end: date) -> list:
    """Per-bowler estimated balls bowled in [start, end] vs the equal-length window
    immediately before it. Estimated from `bowling_volume` buckets."""
    if evening.empty or "bowling_volume" not in evening.columns or "date" not in evening.columns:
        return []
    fb = fast_bowlers(roster)
    ev = evening[evening["did_bowl"].astype(str).str.lower().isin(["true", "1", "yes"])].copy()
    ev["balls"] = ev["bowling_volume"].map(VOLUME_BALLS)
    ev = ev[ev["balls"].notna()]
    span = max((end - start).days + 1, 1)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span - 1)
    # Show every roster fast bowler (0 if they logged no bowling in the range);
    # fall back to whoever actually bowled when the roster has no fast-bowler flags.
    players = fb if fb else list(ev["player_name"].unique())
    rows = []
    for p in players:
        pe = ev[ev["player_name"] == p]
        this_w = pe[(pe["date"] >= start) & (pe["date"] <= end)]["balls"].sum()
        prev_w = pe[(pe["date"] >= prev_start) & (pe["date"] <= prev_end)]["balls"].sum()
        if not fb and this_w == 0 and prev_w == 0:
            continue
        change = round((this_w - prev_w) / prev_w * 100) if prev_w > 0 else None
        rows.append({"player": p, "this_week": int(this_w),
                     "prev_week": int(prev_w), "change": change})
    rows.sort(key=lambda x: x["this_week"], reverse=True)
    return rows


def _has_tightness(v) -> bool:
    s = str(v or "").strip()
    return bool(s) and s.lower() != "none"


def _injury_items(wellness: pd.DataFrame, start: date, end: date) -> list:
    """Physical-complaint rows (area, worst severity, days reported) across [start, end]."""
    if wellness.empty or "date" not in wellness.columns:
        return []
    rng = wellness[(wellness["date"] >= start) & (wellness["date"] <= end)]
    if rng.empty:
        return []
    sev_w = {"Severe": 3, "Moderate": 2, "Mild": 1}
    items = []
    for name, g in rng.groupby("player_name"):
        tight = g[g["tightness_locations"].apply(_has_tightness)]
        sick = g[g["is_sick"].astype(str).str.lower().isin(["true", "1", "yes"])]
        if tight.empty and sick.empty:
            continue
        if not tight.empty:
            areas = set()
            for v in tight["tightness_locations"]:
                for a in str(v).split(","):
                    a = a.strip()
                    if a and a.lower() != "none":
                        areas.add(a)
            area = ", ".join(sorted(areas)) if areas else "Illness"
            sevs = [s for s in tight.get("complaint_severity", pd.Series([], dtype=object))
                    if isinstance(s, str) and s]
            sev = max(sevs, key=lambda s: sev_w.get(s, 0)) if sevs else "—"
            days = tight["date"].nunique()
        else:
            area, sev, days = "Illness", "Illness", sick["date"].nunique()
        items.append({"player": name, "area": area, "severity": sev, "days": max(days, 1)})
    items.sort(key=lambda x: (sev_w.get(x["severity"], 0), x["days"]), reverse=True)
    return items


def _attention_cards(per_player: pd.DataFrame) -> list:
    """Players whose range-averaged check-ins flag an issue, worst first."""
    cards = []
    if per_player.empty:
        return cards
    for _, r in per_player.iterrows():
        flags, severe = [], False
        wp = wellness_pct(r)
        band, _ = wellness_band(wp)
        locs = str(r.get("tightness_locations") or "").strip()
        if _has_tightness(locs):
            sev = r.get("complaint_severity")
            sev_txt = f" ({sev})" if isinstance(sev, str) and sev else ""
            flags.append(f"{locs} tightness{sev_txt}")
            if isinstance(sev, str) and sev == "Severe":
                severe = True
        if str(r.get("is_sick", "")).lower() in ("true", "1", "yes"):
            flags.append("Reported illness"); severe = True
        try:
            if float(r.get("sleep_hours") or 8) < 6:
                flags.append("Low sleep")
        except (TypeError, ValueError):
            pass
        try:
            if float(r.get("energy_level") or 5) <= 2:
                flags.append("Low energy")
        except (TypeError, ValueError):
            pass
        try:
            if float(r.get("body_soreness") or 1) >= 4:
                flags.append("Elevated soreness")
        except (TypeError, ValueError):
            pass
        try:
            if float(r.get("stress") or 1) >= 4:
                flags.append("High stress")
        except (TypeError, ValueError):
            pass
        avail = str(r.get("availability_status") or "").strip()
        if avail and avail not in ("Available", ""):
            flags.append(f"Self-reported: {avail}")
            if avail == "Unavailable":
                severe = True
        if band == "Flagged":
            severe = True
        if not flags:
            continue
        level = "Monitor Closely" if severe else "Monitor"
        cards.append({"player": r["player_name"], "flags": flags, "level": level, "wpct": wp})
    cards.sort(key=lambda c: (0 if c["level"] == "Monitor Closely" else 1, c["wpct"]))
    return cards


def _sc_recommendation(per_player: pd.DataFrame, cards: list, au_overload: list) -> str:
    if per_player.empty:
        return "No check-ins submitted in this date range — no recommendation available."
    parts = []
    if cards:
        closely = [c["player"] for c in cards if c["level"] == "Monitor Closely"]
        monitor = [c["player"] for c in cards if c["level"] == "Monitor"]
        parts.append("Proceed with planned training.")
        if closely:
            parts.append(f"Manage loads carefully for {', '.join(closely)} — review before full participation.")
        if monitor:
            parts.append(f"Continue monitoring {', '.join(monitor)} and adjust as required.")
    else:
        parts.append("Squad readiness is good across the board. Proceed with planned training.")
    if au_overload:
        parts.append(f"Weekly load is outside the target band for {', '.join(au_overload)} — review training volume.")
    parts.append("Prioritise recovery and early management of any flagged complaints.")
    return " ".join(parts)


@st.fragment
def render_overview():
    roster   = load_roster()
    wellness = load_wellness()
    evening  = load_evening()
    today    = date.today()

    # ── Header row: title + start→end date range ─────────────────────────────
    c_h1, c_h2 = st.columns([3, 1])
    with c_h1:
        st.markdown(
            "<div style='font-size:22px;font-weight:800;letter-spacing:1px;'>AMS OVERVIEW</div>"
            "<div style='font-size:11px;color:#6b7a90;letter-spacing:2px;text-transform:uppercase;'>"
            "S&amp;C Snapshot · Weekly Analysis</div>",
            unsafe_allow_html=True,
        )
    with c_h2:
        dr = st.date_input("Date range", value=(today - timedelta(days=6), today),
                           key="ov_range", label_visibility="collapsed")
        if isinstance(dr, (tuple, list)) and len(dr) == 2:
            start, end = dr
        elif isinstance(dr, (tuple, list)) and len(dr) == 1:
            start = end = dr[0]
        else:
            start = end = dr

    if start > end:
        start, end = end, start
    span_days     = (end - start).days + 1
    total_players = len(roster) if not roster.empty else 0
    per_player    = aggregate_range(wellness, start, end)

    st.markdown("<hr style='border-color:#1f2530;margin:10px 0 16px;'>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # ROW 1 — Squad Readiness · Wellness Summary · Availability
    # ════════════════════════════════════════════════════════════════════════
    r1c1, r1c2, r1c3 = st.columns([1, 1.2, 1], gap="medium")

    # ── Squad Readiness donut ────────────────────────────────────────────────
    with r1c1:
        _panel_title("Squad Readiness")
        ready = monitor = flagged = 0
        avg_pct = 0
        if not per_player.empty:
            pcts = per_player.apply(wellness_pct, axis=1)
            avg_pct = int(round(pcts.mean()))
            for p in pcts:
                b, _ = wellness_band(int(p))
                if   b == "Ready":   ready   += 1
                elif b == "Monitor": monitor += 1
                else:                flagged += 1
        donut = go.Figure(go.Pie(
            labels=["Ready", "Monitor", "Flagged"],
            values=[ready, monitor, flagged],
            marker=dict(colors=["#22c55e", "#f59e0b", "#ef4444"]),
            hole=0.72, sort=False, textinfo="none",
            hovertemplate="%{label}: %{value}<extra></extra>",
        ))
        donut.add_annotation(text=f"<b>{avg_pct}%</b>", x=0.5, y=0.54, showarrow=False,
                             font=dict(size=30, color="#e8edf5"))
        donut.add_annotation(text="AVG WELLNESS", x=0.5, y=0.36, showarrow=False,
                             font=dict(size=9, color="#6b7a90"))
        donut.update_layout(**{**DARK_LAYOUT, "margin": dict(t=4, b=4, l=4, r=4)},
                            height=180, showlegend=False)
        st.plotly_chart(donut, use_container_width=True, key="ov_readiness_donut")
        for label, color, cnt in [("Ready (80%+)", "#22c55e", ready),
                                  ("Monitor (60-79%)", "#f59e0b", monitor),
                                  ("Flagged (<60%)", "#ef4444", flagged)]:
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;font-size:12px;margin:3px 0;'>"
                f"<span><span style='display:inline-block;width:9px;height:9px;border-radius:50%;"
                f"background:{color};margin-right:6px;'></span>{label}</span>"
                f"<span style='font-weight:700;color:{color};'>{cnt}</span></div>",
                unsafe_allow_html=True)
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;font-size:12px;color:#6b7a90;"
            f"border-top:1px solid #1f2530;margin-top:6px;padding-top:6px;'><span>Total Players</span>"
            f"<span style='font-weight:700;'>{total_players}</span></div>", unsafe_allow_html=True)

    # ── Wellness Summary (squad average over range) ──────────────────────────
    with r1c2:
        _panel_title("Wellness Summary (Squad Average)")

        def _avg(col):
            if per_player.empty or col not in per_player.columns:
                return None
            s = pd.to_numeric(per_player[col], errors="coerce").dropna()
            return round(s.mean(), 1) if not s.empty else None

        def _fmt(v, suf=""):
            return f"{v}{suf}" if v is not None else "—"

        sleep_h  = _avg("sleep_hours")
        energy   = _avg("energy_level")
        soreness = _avg("body_soreness")
        mood     = _avg("mood")
        stress   = _avg("stress")
        cards = [
            ("🌙", _fmt(sleep_h, "h"), "Sleep", "#00c2ff"),
            ("⚡", _fmt(energy) + ("/5" if energy is not None else ""), "Energy", "#22c55e"),
            ("🔥", _fmt(soreness) + ("/5" if soreness is not None else ""), "Soreness", "#f59e0b"),
            ("🙂", _fmt(mood) + ("/5" if mood is not None else ""), "Mood", "#facc15"),
            ("🧠", _fmt(stress) + ("/5" if stress is not None else ""), "Stress", "#a78bfa"),
        ]
        st.markdown(
            "<div style='display:flex;gap:6px;background:#161a22;border:1px solid #1f2530;"
            "border-radius:10px;padding:20px 8px;'>" +
            "".join(_ams_metric(*c) for c in cards) + "</div>",
            unsafe_allow_html=True)
        st.caption(f"{len(per_player)} of {total_players} players submitted · "
                   f"{start:%d %b} → {end:%d %b} ({span_days}d)")

        # ── Check-in submission status (morning + evening over range) ────────
        roster_names = (sorted(roster["name"].dropna().astype(str).str.strip()
                               .replace("", pd.NA).dropna().unique().tolist())
                        if not roster.empty and "name" in roster.columns else [])

        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        checkin_day = st.date_input("Check-in date", value=end, min_value=start,
                                    max_value=end, key="ov_checkin_day")

        def _submitters(df):
            if df.empty or "date" not in df.columns or "player_name" not in df.columns:
                return set()
            day = df[df["date"] == checkin_day]
            return set(day["player_name"].astype(str).str.strip())

        morning_done = _submitters(wellness)
        evening_done = _submitters(evening)
        m_not = [n for n in roster_names if n not in morning_done]
        e_not = [n for n in roster_names if n not in evening_done]

        def _checkin_status(title, done, not_done):
            _panel_title(title)
            st.markdown(
                f"<div style='font-size:22px;font-weight:800;color:#e8edf5;'>"
                f"{len(done)} <span style='font-size:12px;color:#6b7a90;font-weight:600;'>"
                f"/ {total_players} players</span></div>", unsafe_allow_html=True)
            if not_done:
                with st.expander(f"Not submitted ({len(not_done)})"):
                    st.markdown("<br>".join(not_done), unsafe_allow_html=True)

        sc1, sc2 = st.columns(2)
        with sc1:
            _checkin_status("Morning Check-in Submitted", morning_done, m_not)
        with sc2:
            _checkin_status("Evening Check-in Submitted", evening_done, e_not)

    # ── Availability Overview donut ──────────────────────────────────────────
    with r1c3:
        _panel_title("Availability Overview")
        bucket_counts = {b: 0 for b, _ in AMS_AVAIL_BUCKETS}
        not_set = 0
        if not roster.empty and "current_status" in roster.columns:
            for v in roster["current_status"].fillna("").tolist():
                key = _AVAIL_TO_BUCKET.get(str(v).strip())
                if key:
                    bucket_counts[key] += 1
                else:
                    not_set += 1
        # Fall back to self-reported availability if the roster has no statuses set.
        if sum(bucket_counts.values()) == 0 and not per_player.empty and "availability_status" in per_player.columns:
            for v in per_player["availability_status"].fillna("Available").tolist():
                bucket_counts[_AVAIL_TO_BUCKET.get(str(v).strip(), "Full Training")] += 1
            not_set = max(0, total_players - len(per_player))
        labels = [b for b, _ in AMS_AVAIL_BUCKETS]
        colors = [c for _, c in AMS_AVAIL_BUCKETS]
        values = [bucket_counts[b] for b in labels]
        if not_set:
            labels = labels + ["Not Set"]; colors = colors + ["#6b7a90"]; values = values + [not_set]
        adonut = go.Figure(go.Pie(labels=labels, values=values, marker=dict(colors=colors),
                                  hole=0.62, sort=False, textinfo="none",
                                  hovertemplate="%{label}: %{value}<extra></extra>"))
        adonut.update_layout(**{**DARK_LAYOUT, "margin": dict(t=4, b=4, l=4, r=4)},
                             height=168, showlegend=False)
        st.plotly_chart(adonut, use_container_width=True, key="ov_avail_donut")
        for lab, col, val in zip(labels, colors, values):
            pctv = round(val / total_players * 100) if total_players else 0
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;font-size:12px;margin:3px 0;'>"
                f"<span><span style='display:inline-block;width:9px;height:9px;border-radius:50%;"
                f"background:{col};margin-right:6px;'></span>{lab}</span>"
                f"<span style='font-weight:700;color:{col};'>{val} "
                f"<span style='color:#6b7a90;font-weight:400;'>({pctv}%)</span></span></div>",
                unsafe_allow_html=True)

    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # ROW 2 — Daily Wellness · Top Training Load · Weekly Load
    # ════════════════════════════════════════════════════════════════════════
    r2c1, r2c2, r2c3 = st.columns([1.3, 1, 1], gap="medium")

    def _c_hi(v):   # higher is better
        try: v = float(v)
        except (TypeError, ValueError): return "#6b7a90"
        return "#22c55e" if v >= 4 else ("#ef4444" if v <= 2 else "#f59e0b")

    def _c_lo(v):   # lower is better
        try: v = float(v)
        except (TypeError, ValueError): return "#6b7a90"
        return "#22c55e" if v <= 2 else ("#ef4444" if v >= 4 else "#f59e0b")

    def _num(r, col):
        val = r.get(col)
        if pd.isna(val) or val == "":
            return "—"
        try:
            return f"{float(val):.1f}".rstrip("0").rstrip(".")
        except (TypeError, ValueError):
            return val

    with r2c1:
        _panel_title("Wellness Overview (Range Avg)")
        if per_player.empty:
            st.info("No check-ins submitted in this range.")
        else:
            tbl = per_player.copy()
            tbl["wpct"] = tbl.apply(wellness_pct, axis=1)
            tbl = tbl.sort_values("wpct")
            head = "".join(
                f"<th style='text-align:right;padding:4px 6px;color:#6b7a90;font-weight:500;'>{h}</th>"
                for h in ["Sleep", "Energy", "Sore", "Mood", "Stress", "Well%"])
            body = ""
            for _, r in tbl.iterrows():
                sh = _num(r, "sleep_hours")
                wp = int(r["wpct"]); _, wcol = wellness_band(wp)
                body += (
                    f"<tr style='border-top:1px solid #1f2530;'>"
                    f"<td style='padding:5px 6px;'>{r['player_name']}</td>"
                    f"<td style='text-align:right;padding:5px 6px;'>{(str(sh)+'h') if sh != '—' else '—'}</td>"
                    f"<td style='text-align:right;color:{_c_hi(r.get('energy_level'))};'>{_num(r,'energy_level')}</td>"
                    f"<td style='text-align:right;color:{_c_lo(r.get('body_soreness'))};'>{_num(r,'body_soreness')}</td>"
                    f"<td style='text-align:right;color:{_c_hi(r.get('mood'))};'>{_num(r,'mood')}</td>"
                    f"<td style='text-align:right;color:{_c_lo(r.get('stress'))};'>{_num(r,'stress')}</td>"
                    f"<td style='text-align:right;font-weight:700;color:{wcol};padding-right:6px;'>{wp}%</td></tr>")
            st.markdown(
                f"<div style='max-height:340px;overflow-y:auto;'>"
                f"<table style='width:100%;border-collapse:collapse;font-size:12px;'>"
                f"<thead><tr style='position:sticky;top:0;background:#0e1117;z-index:1;'>"
                f"<th style='text-align:left;padding:4px 6px;color:#6b7a90;font-weight:500;'>Player</th>"
                f"{head}</tr></thead><tbody>{body}</tbody></table></div>", unsafe_allow_html=True)

    with r2c2:
        _panel_title("Squad Training Loads")
        load_rows = _top_session_loads(evening, start, end, roster)
        if not load_rows:
            st.info("No session load in this range.")
        else:
            body = ""
            for r in load_rows:
                lc = _load_color_for_role(r["load"], r.get("role", ""), r.get("is_fb", False))
                body += (
                    f"<tr style='border-top:1px solid #1f2530;'>"
                    f"<td style='padding:5px 6px;'>{r['player']}</td>"
                    f"<td style='text-align:right;'>{r['dur']}m</td>"
                    f"<td style='text-align:right;'>{r['rpe']}</td>"
                    f"<td style='text-align:right;font-weight:700;color:{lc};"
                    f"padding-right:6px;'>{r['load']}</td></tr>")
            st.markdown(
                "<div style='max-height:340px;overflow-y:auto;'>"
                "<table style='width:100%;border-collapse:collapse;font-size:12px;'>"
                "<thead><tr style='position:sticky;top:0;background:#0e1117;z-index:1;'>"
                "<th style='text-align:left;color:#6b7a90;font-weight:500;padding:4px 6px;'>Player</th>"
                "<th style='text-align:right;color:#6b7a90;font-weight:500;'>Dur</th>"
                "<th style='text-align:right;color:#6b7a90;font-weight:500;'>RPE</th>"
                "<th style='text-align:right;color:#6b7a90;font-weight:500;padding-right:6px;'>Load</th>"
                f"</tr></thead><tbody>{body}</tbody></table></div>", unsafe_allow_html=True)
            st.caption("Peak session per player · Load = RPE × mins")
            st.markdown(
                "<div style='display:flex;gap:14px;margin-top:6px;flex-wrap:wrap;'>"
                "<span style='font-size:11px;color:#6b7a90;display:flex;align-items:center;gap:4px;'>"
                "<span style='width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block;'></span>In range</span>"
                "<span style='font-size:11px;color:#6b7a90;display:flex;align-items:center;gap:4px;'>"
                "<span style='width:8px;height:8px;border-radius:50%;background:#f59e0b;display:inline-block;'></span>Below target</span>"
                "<span style='font-size:11px;color:#6b7a90;display:flex;align-items:center;gap:4px;'>"
                "<span style='width:8px;height:8px;border-radius:50%;background:#ef4444;display:inline-block;'></span>Above target</span>"
                "</div>"
                "<div style='margin-top:4px;font-size:10px;color:#4b5563;'>"
                "Fast Bowler 2,500–4,000 &nbsp;·&nbsp; Spinner 2,000–3,000 &nbsp;·&nbsp; Batsman 2,000–3,500 AU"
                "</div>",
                unsafe_allow_html=True)

    with r2c3:
        _panel_title("Weekly Load (AU)")
        wloads = _weekly_loads(evening, roster, start, end)
        if not wloads:
            st.info("No load data in this range.")
        else:
            wl = wloads[:8][::-1]
            bar_colors = ["#22c55e" if w["in_band"] else "#ef4444" for w in wl]
            fig = go.Figure(go.Bar(
                x=[w["weekly"] for w in wl], y=[w["player"] for w in wl], orientation="h",
                marker_color=bar_colors,
                text=[f"{w['weekly']:,}" for w in wl], textposition="outside",
                cliponaxis=False,
                customdata=[[w["band"], w["lo"], w["hi"]] for w in wl],
                hovertemplate="%{y}: %{x:,} AU/wk<br>%{customdata[0]} band "
                              "%{customdata[1]:,}–%{customdata[2]:,}<extra></extra>"))
            fig.update_layout(**{**DARK_LAYOUT, "margin": dict(t=6, b=6, l=6, r=70)},
                              height=220, xaxis=dict(visible=False),
                              yaxis=dict(tickfont=dict(size=11)), showlegend=False)
            st.plotly_chart(fig, use_container_width=True, key="ov_weekly_load")
            st.caption("AU = RPE × mins, normalised to 7 days · "
                       "🟥 outside role band (Bat 2,500–4,000 · Bowl 3,000–5,500 AU/wk)")

    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # ROW 3 — Bowling Load · Injury / Complaints · Wellness Trend
    # ════════════════════════════════════════════════════════════════════════
    r3c1, r3c2, r3c3 = st.columns([1, 1, 1.3], gap="medium")

    with r3c1:
        _panel_title("Bowling Load (Range)")
        bl = _bowling_load(evening, roster, start, end)
        if not bl:
            st.info("No bowling logged in this range.")
        else:
            body = ""
            for r in bl:
                ch = r["change"]
                ch_col = ("#ef4444" if ch is not None and ch >= 15
                          else "#22c55e" if ch is not None and ch < 0 else "#f59e0b")
                ch_txt = "—" if ch is None else (f"+{ch}%" if ch >= 0 else f"{ch}%")
                body += (
                    f"<tr style='border-top:1px solid #1f2530;'>"
                    f"<td style='padding:5px 6px;'>{r['player']}</td>"
                    f"<td style='text-align:right;font-weight:600;'>{r['this_week']}</td>"
                    f"<td style='text-align:right;color:#6b7a90;'>{r['prev_week']}</td>"
                    f"<td style='text-align:right;font-weight:700;color:{ch_col};"
                    f"padding-right:6px;'>{ch_txt}</td></tr>")
            st.markdown(
                "<div style='max-height:340px;overflow-y:auto;'>"
                "<table style='width:100%;border-collapse:collapse;font-size:12px;'>"
                "<thead><tr style='position:sticky;top:0;background:#0e1117;z-index:1;'>"
                "<th style='text-align:left;color:#6b7a90;font-weight:500;padding:4px 6px;'>Player</th>"
                "<th style='text-align:right;color:#6b7a90;font-weight:500;'>This</th>"
                "<th style='text-align:right;color:#6b7a90;font-weight:500;'>Prev</th>"
                "<th style='text-align:right;color:#6b7a90;font-weight:500;padding-right:6px;'>&Delta;%</th>"
                f"</tr></thead><tbody>{body}</tbody></table></div>", unsafe_allow_html=True)
            st.caption("Est. balls bowled (from volume buckets) · range vs prior equal window")

    with r3c2:
        _panel_title("Injury / Physical Complaints")
        items = _injury_items(wellness, start, end)
        if not items:
            st.success("No physical complaints reported.")
        else:
            sev_col = {"Severe": "#ef4444", "Moderate": "#f59e0b", "Mild": "#22c55e"}
            body = ""
            for it in items:
                sc = sev_col.get(it["severity"], "#6b7a90")
                body += (
                    f"<tr style='border-top:1px solid #1f2530;'>"
                    f"<td style='padding:5px 6px;'>{it['player']}</td>"
                    f"<td style='font-size:11px;'>{it['area']}</td>"
                    f"<td style='color:{sc};font-weight:600;'>{it['severity']}</td>"
                    f"<td style='text-align:right;padding-right:6px;'>{it['days']}</td></tr>")
            st.markdown(
                "<div style='max-height:340px;overflow-y:auto;'>"
                "<table style='width:100%;border-collapse:collapse;font-size:12px;'>"
                "<thead><tr style='position:sticky;top:0;background:#0e1117;z-index:1;'>"
                "<th style='text-align:left;color:#6b7a90;font-weight:500;padding:4px 6px;'>Player</th>"
                "<th style='text-align:left;color:#6b7a90;font-weight:500;'>Area</th>"
                "<th style='text-align:left;color:#6b7a90;font-weight:500;'>Severity</th>"
                "<th style='text-align:right;color:#6b7a90;font-weight:500;padding-right:6px;'>Days</th>"
                f"</tr></thead><tbody>{body}</tbody></table></div>", unsafe_allow_html=True)

    with r3c3:
        _panel_title("Wellness Trend")
        if wellness.empty or "date" not in wellness.columns:
            st.info("No wellness history.")
        else:
            hist = wellness[(wellness["date"] >= start) & (wellness["date"] <= end)].copy()
            if hist.empty:
                st.info("No wellness in this range.")
            else:
                hist["wpct"] = hist.apply(wellness_pct, axis=1)
                daily = hist.sort_values("timestamp").groupby(["date", "player_name"]).last().reset_index()
                squad = daily.groupby("date")["wpct"].mean().reset_index()
                squad["date_str"] = squad["date"].astype(str)
                fig = go.Figure()
                flagged_players = []
                if not per_player.empty:
                    lp = per_player.copy(); lp["wpct"] = lp.apply(wellness_pct, axis=1)
                    flagged_players = lp.sort_values("wpct").head(3)["player_name"].tolist()
                palette = ["#ef4444", "#f59e0b", "#00c2ff"]
                for i, pl in enumerate(flagged_players):
                    pld = daily[daily["player_name"] == pl]
                    if not pld.empty:
                        fig.add_trace(go.Scatter(
                            x=pld["date"].astype(str), y=pld["wpct"], name=pl,
                            mode="lines+markers", line=dict(color=palette[i % 3], width=2),
                            marker=dict(size=5)))
                fig.add_trace(go.Scatter(
                    x=squad["date_str"], y=squad["wpct"].round(0), name="Squad Avg",
                    mode="lines+markers", line=dict(color="#9fb0c6", width=2, dash="dash"),
                    marker=dict(size=5)))
                fig.update_layout(**{**DARK_LAYOUT, "margin": dict(t=6, b=6, l=6, r=6)},
                                  height=220, yaxis=dict(range=[0, 100], gridcolor="#1f2530", title=""),
                                  xaxis=dict(gridcolor="#1f2530"),
                                  legend=dict(orientation="h", y=-0.25, font=dict(size=10)))
                st.plotly_chart(fig, use_container_width=True, key="ov_wellness_trend")

    # ════════════════════════════════════════════════════════════════════════
    # Players Requiring Attention + S&C Recommendation
    # ════════════════════════════════════════════════════════════════════════
    st.markdown("<hr style='border-color:#1f2530;margin:18px 0 14px;'>", unsafe_allow_html=True)
    _panel_title("Players Requiring Attention")
    cards = _attention_cards(per_player)
    au_overload = [w["player"] for w in _weekly_loads(evening, roster, start, end) if not w["in_band"]]
    if not cards:
        st.success("No players currently require attention.")
    else:
        cols = st.columns(4)
        for col, card in zip(cols, cards[:4]):
            with col:
                lvl_col = "#ef4444" if card["level"] == "Monitor Closely" else "#f59e0b"
                flags_html = "".join(f"<li style='margin:2px 0;'>{f}</li>" for f in card["flags"][:3])
                st.markdown(
                    f"<div style='background:#161a22;border:1px solid #1f2530;border-left:3px solid {lvl_col};"
                    f"border-radius:8px;padding:12px 14px;height:100%;'>"
                    f"<div style='font-weight:700;font-size:13px;margin-bottom:6px;'>🚩 {card['player']}</div>"
                    f"<ul style='margin:0;padding-left:16px;font-size:11px;color:#c3cedd;'>{flags_html}</ul>"
                    f"<div style='color:{lvl_col};font-size:11px;font-weight:700;margin-top:8px;'>"
                    f"{card['level']}</div></div>", unsafe_allow_html=True)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
    rec = _sc_recommendation(per_player, cards, au_overload)
    st.markdown(
        f"<div style='background:rgba(0,194,255,0.06);border:1px solid rgba(0,194,255,0.25);"
        f"border-radius:10px;padding:14px 18px;'>"
        f"<div style='color:#00c2ff;font-weight:700;font-size:13px;margin-bottom:6px;'>"
        f"🛡 S&amp;C RECOMMENDATION</div>"
        f"<div style='font-size:13px;color:#c3cedd;line-height:1.6;'>{rec}</div></div>",
        unsafe_allow_html=True)


with tab_overview:
    render_overview()

# ════════════════════════════════════════════════════════════════════════════
# RAW DATA — shared helpers & dialogs (module-level so @st.dialog works)
# ════════════════════════════════════════════════════════════════════════════

def _patch_row(table: str, row_id: int, updates: dict) -> bool:
    try:
        r = requests.patch(f"{API_URL}/data/{table}/{row_id}", json=updates, timeout=5)
        r.raise_for_status()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Update failed: {e}")
        return False

def _ts_with_new_date(orig_ts_str: str, new_date) -> str:
    orig = pd.to_datetime(orig_ts_str)
    return f"{new_date.isoformat()}T{orig.time().isoformat()}"

def _safe_int(val, default=3):
    try: return int(val) if pd.notna(val) else default
    except: return default

def _safe_float(val, default=0.0):
    try: return float(val) if pd.notna(val) else default
    except: return default

def _safe_str(val):
    return str(val) if pd.notna(val) and val is not None else ""


@st.dialog("Edit Morning Check-in", width="large")
def _edit_wellness_dialog(row):
    with st.form("dlg_wellness"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            orig_ts    = pd.to_datetime(row["timestamp"])
            new_date   = st.date_input("Date", value=orig_ts.date())
            new_player = st.text_input("Player", value=_safe_str(row.get("player_name")))
            avail_opts = ["Available", "Limited", "Unavailable"]
            cur_avail  = _safe_str(row.get("availability_status"))
            avail_idx  = avail_opts.index(cur_avail) if cur_avail in avail_opts else 0
            new_avail  = st.selectbox("Availability", avail_opts, index=avail_idx)
        with c2:
            new_sleep_q  = st.number_input("Sleep Quality (1–5)", 1, 5, _safe_int(row.get("sleep_quality")))
            new_energy   = st.number_input("Energy (1–5)", 1, 5, _safe_int(row.get("energy_level")))
            new_soreness = st.number_input("Soreness (1–5)", 1, 5, _safe_int(row.get("body_soreness")))
        with c3:
            new_mood    = st.number_input("Mood (1–5)", 1, 5, _safe_int(row.get("mood")))
            new_stress  = st.number_input("Stress (1–5)", 1, 5, _safe_int(row.get("stress")))
            new_sleep_h = st.number_input("Sleep Hours", 0.0, 24.0, _safe_float(row.get("sleep_hours")), step=0.5)
        with c4:
            new_sick      = st.checkbox("Sick", value=bool(row.get("is_sick")))
            new_tightness = st.text_input("Tightness Locations", value=_safe_str(row.get("tightness_locations")))
            new_severity  = st.text_input("Complaint Severity", value=_safe_str(row.get("complaint_severity")))
            new_notes     = st.text_input("Notes", value=_safe_str(row.get("notes")))
        if st.form_submit_button("Save changes", type="primary"):
            updates = {
                "timestamp": _ts_with_new_date(row["timestamp"], new_date),
                "player_name": new_player,
                "sleep_quality": new_sleep_q, "energy_level": new_energy,
                "body_soreness": new_soreness, "mood": new_mood, "stress": new_stress,
                "sleep_hours": new_sleep_h, "is_sick": int(new_sick),
                "tightness_locations": new_tightness, "complaint_severity": new_severity,
                "availability_status": new_avail, "notes": new_notes,
            }
            if _patch_row("wellness", int(row["id"]), updates):
                st.rerun()


@st.dialog("Edit Evening Check-in", width="large")
def _edit_evening_dialog(row):
    with st.form("dlg_evening"):
        c1, c2, c3 = st.columns(3)
        with c1:
            orig_ts    = pd.to_datetime(row["timestamp"])
            new_date   = st.date_input("Date", value=orig_ts.date())
            new_player = st.text_input("Player", value=_safe_str(row.get("player_name")))
            new_rpe    = st.number_input("Session RPE (1–10)", 1, 10, _safe_int(row.get("session_rpe"), 5))
        with c2:
            new_dur      = st.number_input("Duration (hrs)", 0.0, 12.0, _safe_float(row.get("session_duration_hours")), step=0.25)
            new_did_bowl = st.checkbox("Did Bowl", value=bool(row.get("did_bowl")))
            new_bowl_vol = st.text_input("Bowling Volume", value=_safe_str(row.get("bowling_volume")))
        with c3:
            new_bowl_int = st.text_input("Bowling Intensity", value=_safe_str(row.get("bowling_intensity")))
            new_did_bat  = st.checkbox("Did Bat", value=bool(row.get("did_bat")))
            new_balls    = st.text_input("Balls Faced", value=_safe_str(row.get("balls_faced")))
        if st.form_submit_button("Save changes", type="primary"):
            updates = {
                "timestamp": _ts_with_new_date(row["timestamp"], new_date),
                "player_name": new_player,
                "session_rpe": new_rpe, "session_duration_hours": new_dur,
                "did_bowl": int(new_did_bowl), "bowling_volume": new_bowl_vol,
                "bowling_intensity": new_bowl_int,
                "did_bat": int(new_did_bat), "balls_faced": new_balls,
            }
            if _patch_row("evening", int(row["id"]), updates):
                st.rerun()


@st.dialog("Edit Session Load", width="large")
def _edit_sessions_dialog(row):
    with st.form("dlg_sessions"):
        c1, c2, c3 = st.columns(3)
        with c1:
            orig_ts    = pd.to_datetime(row["timestamp"])
            new_date   = st.date_input("Date", value=orig_ts.date())
            new_player = st.text_input("Player", value=_safe_str(row.get("player_name")))
        with c2:
            new_type = st.text_input("Session Type", value=_safe_str(row.get("session_type")))
            new_dur  = st.number_input("Duration (min)", 0, 600, _safe_int(row.get("duration_mins"), 60))
        with c3:
            new_rpe   = st.number_input("RPE (1–10)", 1, 10, _safe_int(row.get("rpe"), 5))
            new_notes = st.text_input("Notes", value=_safe_str(row.get("notes")))
        if st.form_submit_button("Save changes", type="primary"):
            updates = {
                "timestamp": _ts_with_new_date(row["timestamp"], new_date),
                "player_name": new_player, "session_type": new_type,
                "duration_mins": new_dur, "rpe": new_rpe, "notes": new_notes,
            }
            if _patch_row("sessions", int(row["id"]), updates):
                st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# RAW DATA TAB
# ════════════════════════════════════════════════════════════════════════════
@st.fragment
def render_raw_data():
    today   = date.today()

    def _date_filter(df, section: str):
        c1, c2 = st.columns([1, 2])
        with c1:
            players = ["All"] + sorted(df["player_name"].dropna().unique().tolist()) if "player_name" in df.columns else ["All"]
            sel = st.selectbox("Player", players, key=f"raw_player_{section}")
        with c2:
            dr = st.date_input("Date range", value=(today - timedelta(days=30), today), key=f"raw_dr_{section}")
        out = df.copy()
        if sel != "All" and "player_name" in out.columns:
            out = out[out["player_name"] == sel]
        if isinstance(dr, tuple) and len(dr) == 2 and "date" in out.columns:
            out = out[(out["date"] >= dr[0]) & (out["date"] <= dr[1])]
        return out.sort_values("timestamp", ascending=False) if "timestamp" in out.columns else out

    def _export_btn(df, name):
        if not df.empty:
            st.download_button(f"Export {name}.csv", df.to_csv(index=False),
                               file_name=f"{name}.csv", mime="text/csv")

    def _delete_rows(table: str, row_ids: list):
        for rid in row_ids:
            try:
                requests.delete(f"{API_URL}/data/{table}/{rid}", timeout=5)
            except Exception as e:
                st.error(f"Delete failed for row {rid}: {e}")
        st.cache_data.clear()

    # ── Morning wellness ─────────────────────────────────────────────────────
    with st.expander("Morning Check-ins (Wellness)", expanded=True):
        wellness = load_wellness()
        if wellness.empty:
            st.info("No morning check-in data yet.")
        else:
            df_w_full = _date_filter(wellness, "wellness")
            keep = ["date","player_name","sleep_quality","energy_level","body_soreness",
                    "mood","stress","sleep_hours","is_sick",
                    "tightness_locations","complaint_severity","availability_status","notes"]
            df_w = df_w_full[[c for c in keep if c in df_w_full.columns]].rename(columns={
                "player_name":"Player","sleep_quality":"Sleep","energy_level":"Energy",
                "body_soreness":"Soreness","mood":"Mood","stress":"Stress",
                "sleep_hours":"Sleep Hrs","is_sick":"Sick",
                "tightness_locations":"Tightness","complaint_severity":"Complaint Severity",
                "availability_status":"Availability",
            })

            def _bg(val, inv=False):
                try:
                    v = int(val)
                    hi = "background-color:rgba(239,68,68,0.2)"
                    lo = "background-color:rgba(34,197,94,0.2)"
                    mid = "background-color:rgba(245,158,11,0.2)"
                    if inv:
                        return hi if v >= 4 else (lo if v <= 2 else mid)
                    return lo if v >= 4 else (hi if v <= 2 else mid)
                except: return ""

            styled = df_w.style
            for col in [c for c in ["Sleep","Energy"] if c in df_w.columns]:
                styled = styled.applymap(lambda v: _bg(v, inv=False), subset=[col])
            if "Soreness" in df_w.columns:
                styled = styled.applymap(lambda v: _bg(v, inv=True), subset=["Soreness"])
            sel_w = st.dataframe(styled, use_container_width=True, height=380,
                                 selection_mode="multi-row", on_select="rerun",
                                 key="raw_wellness")
            sel_idx = sel_w.selection.rows
            c1, c2, c3 = st.columns([2, 2, 6])
            with c1:
                _export_btn(df_w, "morning_checkins")
            with c2:
                if len(sel_idx) == 1:
                    if st.button("Edit selected", key="edit_wellness"):
                        _edit_wellness_dialog(df_w_full.iloc[sel_idx[0]])
            with c3:
                if sel_idx:
                    if st.button(f"Delete {len(sel_idx)} selected", type="primary",
                                 key="del_wellness"):
                        _delete_rows("wellness", df_w_full.iloc[sel_idx]["id"].tolist())
                        st.rerun()

    # ── Evening check-ins ────────────────────────────────────────────────────
    with st.expander("Evening Check-ins (Session RPE & Bowling)", expanded=False):
        evening = load_evening()
        if evening.empty:
            st.info("No evening check-in data yet.")
        else:
            df_e_full = _date_filter(evening, "evening")
            keep_e = ["date","player_name","session_rpe","session_duration_hours","did_bowl","bowling_volume","bowling_intensity","did_bat","balls_faced"]
            df_e_display = df_e_full[[c for c in keep_e if c in df_e_full.columns]].rename(columns={
                "player_name":"Player","session_rpe":"RPE","session_duration_hours":"Duration (hrs)",
                "did_bowl":"Bowled","bowling_volume":"Bowl Vol","bowling_intensity":"Bowl Int",
                "did_bat":"Batted","balls_faced":"Balls Faced",
            })
            sel_e = st.dataframe(df_e_display, use_container_width=True, height=320,
                                 selection_mode="multi-row", on_select="rerun",
                                 key="raw_evening")
            sel_idx = sel_e.selection.rows
            c1, c2, c3 = st.columns([2, 2, 6])
            with c1:
                _export_btn(df_e_full, "evening_checkins")
            with c2:
                if len(sel_idx) == 1:
                    if st.button("Edit selected", key="edit_evening"):
                        _edit_evening_dialog(df_e_full.iloc[sel_idx[0]])
            with c3:
                if sel_idx:
                    if st.button(f"Delete {len(sel_idx)} selected", type="primary",
                                 key="del_evening"):
                        _delete_rows("evening", df_e_full.iloc[sel_idx]["id"].tolist())
                        st.rerun()

    # ── Session load ─────────────────────────────────────────────────────────
    with st.expander("Session Load (Coach Logged)", expanded=False):
        sessions = load_sessions()
        if sessions.empty:
            st.info("No session data yet.")
        else:
            df_s_full = _date_filter(sessions, "sessions")
            display_cols = ["date","player_name","session_type","duration_mins","rpe","load_au","notes"]
            df_s_display = df_s_full[[c for c in display_cols if c in df_s_full.columns]].rename(
                columns={"player_name":"Player","session_type":"Type",
                         "duration_mins":"Duration (min)","load_au":"Load (AU)"}
            )
            sel_s = st.dataframe(df_s_display, use_container_width=True, height=320,
                                 selection_mode="multi-row", on_select="rerun",
                                 key="raw_sessions")
            sel_idx = sel_s.selection.rows
            c1, c2, c3 = st.columns([2, 2, 6])
            with c1:
                _export_btn(df_s_full, "sessions")
            with c2:
                if len(sel_idx) == 1:
                    if st.button("Edit selected", key="edit_sessions"):
                        _edit_sessions_dialog(df_s_full.iloc[sel_idx[0]])
            with c3:
                if sel_idx:
                    if st.button(f"Delete {len(sel_idx)} selected", type="primary",
                                 key="del_sessions"):
                        _delete_rows("sessions", df_s_full.iloc[sel_idx]["id"].tolist())
                        st.rerun()

    # ── Bowling check-ins ─────────────────────────────────────────────────────
    with st.expander("Bowling Check-ins", expanded=False):
        evening_raw = load_evening()
        if evening_raw.empty:
            st.info("No evening check-in data yet.")
        else:
            df_bowl_full = _date_filter(
                evening_raw[evening_raw["did_bowl"].astype(str).str.lower().isin(["true", "1", "yes"])].copy(),
                "bowl_checkin",
            )
            if df_bowl_full.empty:
                st.info("No bowling check-ins in selected date range.")
            else:
                bowl_cols = ["date","player_name","bowling_volume","bowling_intensity","session_rpe"]
                df_bowl_display = df_bowl_full[[c for c in bowl_cols if c in df_bowl_full.columns]].rename(
                    columns={"player_name":"Player","bowling_volume":"Volume",
                             "bowling_intensity":"Intensity","session_rpe":"RPE"}
                )
                sel_b = st.dataframe(df_bowl_display, use_container_width=True, height=320,
                                     selection_mode="multi-row", on_select="rerun",
                                     key="raw_bowling")
                sel_idx = sel_b.selection.rows
                c1, c2 = st.columns([1, 5])
                with c1:
                    _export_btn(df_bowl_full, "bowling_checkins")
                with c2:
                    if sel_idx:
                        if st.button(f"Delete {len(sel_idx)} selected", type="primary",
                                     key="del_bowling"):
                            _delete_rows("evening", df_bowl_full.iloc[sel_idx]["id"].tolist())
                            st.rerun()

    # ── Roster ───────────────────────────────────────────────────────────────
    with st.expander("Roster", expanded=False):
        roster = load_roster()
        if roster.empty:
            st.info("No roster data yet.")
        else:
            roster_display = roster[[c for c in ROSTER_COLS if c in roster.columns]]
            sel_r = st.dataframe(roster_display, use_container_width=True, height=320,
                                 selection_mode="multi-row", on_select="rerun",
                                 key="raw_roster")
            sel_idx = sel_r.selection.rows
            c1, c2 = st.columns([1, 5])
            with c1:
                _export_btn(roster_display, "roster")
            with c2:
                if sel_idx:
                    if st.button(f"Delete {len(sel_idx)} selected", type="primary",
                                 key="del_roster"):
                        _delete_rows("roster", roster.iloc[sel_idx]["id"].tolist())
                        st.rerun()

with tab_raw:
    render_raw_data()

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — PLAYER LOAD  (session + bowling combined)
# ════════════════════════════════════════════════════════════════════════════
@st.fragment
def render_player_load():
    roster   = load_roster()
    sessions = load_sessions()
    evening  = load_evening()
    today    = date.today()
    now_ts   = pd.Timestamp(today)

    st.subheader("Player Load")

    if roster.empty:
        st.info("No players in roster yet — add them in the Admin tab.")
        return

    # ── Player selector ──────────────────────────────────────────────────────
    names = roster["name"].dropna().tolist()
    col_sel, col_log_s = st.columns([3, 1])
    with col_sel:
        sel = st.selectbox("Select Player", names, key="load_player_sel", label_visibility="collapsed")

    player_row = roster[roster["name"] == sel].iloc[0]
    is_fb      = is_fast_bowler(player_row.get("is_fast_bowler"))

    ps  = sessions[sessions["player_name"] == sel].copy() if not sessions.empty else pd.DataFrame()
    pec = evening[evening["player_name"] == sel].copy()   if not evening.empty  else pd.DataFrame()

    week_ago  = now_ts - timedelta(days=7)
    month_ago = now_ts - timedelta(days=28)

    # ── Log form ─────────────────────────────────────────────────────────────
    with col_log_s:
        if st.button("+ Log Session", use_container_width=True):
            st.session_state["show_log_session"] = True

    if st.session_state.get("show_log_session"):
        with st.expander("Log Session", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            with c1: s_type = st.selectbox("Type", ["Training","Match","Gym","Recovery","Rehab"], key="sl_type")
            with c2: s_dur  = st.number_input("Duration (mins)", 1, 300, 60, key="sl_dur")
            with c3: s_rpe  = st.slider("RPE (1–10)", 1, 10, 6, key="sl_rpe")
            with c4: s_notes= st.text_input("Notes", key="sl_notes")
            cc1, cc2 = st.columns([1, 4])
            with cc1:
                if st.button("Submit", type="primary", key="sl_submit"):
                    try:
                        r = requests.post(f"{API_URL}/data/sessions", json={
                            "player_name": sel, "session_type": s_type,
                            "duration_mins": s_dur, "rpe": s_rpe, "notes": s_notes,
                        }, timeout=5)
                        r.raise_for_status()
                        load_sessions.clear()
                        st.session_state["show_log_session"] = False
                        st.success(f"Session logged for {sel}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # SESSION LOAD SECTION
    # ════════════════════════════════════════════════════════════════════════
    st.markdown("### Session Load")

    # RPE legend
    rpe_html = " &nbsp;·&nbsp; ".join(
        f'<span style="color:{color};">{lo}{"–"+str(hi) if hi!=lo else ""} {label}</span>'
        for (lo, hi), (label, color) in RPE_LABELS.items()
    )
    st.markdown(f'<div style="font-size:12px;margin-bottom:16px;">{rpe_html}</div>', unsafe_allow_html=True)

    if ps.empty and pec.empty:
        st.info(f"No session data for {sel} yet.")
    elif ps.empty and not pec.empty:
        # Only evening check-in data available — show RPE trend from check-ins
        st.caption("Showing RPE from evening check-ins. Use '+ Log Session' to add full sessions with load (AU) tracking.")
        pec_week  = pec[pec["timestamp"] >= week_ago]
        pec_month = pec[pec["timestamp"] >= month_ago]

        checkins_this_week = len(pec_week)
        avg_rpe_week = round(pec_week["session_rpe"].mean(), 1) if not pec_week.empty else 0

        m1, m2 = st.columns(4)[:2]
        with m1: st.markdown(_metric_card("Check-ins this week", str(checkins_this_week)), unsafe_allow_html=True)
        with m2: st.markdown(_metric_card("Avg RPE (7d)", str(avg_rpe_week), color=_rpe_color(avg_rpe_week)), unsafe_allow_html=True)

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

        if not pec_month.empty:
            daily_ec = pec_month.groupby("date").agg(
                avg_rpe=("session_rpe", "mean"),
                count=("session_rpe", "count"),
            ).reset_index()
            daily_ec["date_str"] = daily_ec["date"].astype(str)
            daily_ec["color"] = daily_ec["avg_rpe"].apply(_rpe_color)

            fig_ec = go.Figure()
            for _, row in daily_ec.iterrows():
                fig_ec.add_trace(go.Bar(
                    x=[row["date_str"]], y=[row["avg_rpe"]],
                    marker_color=row["color"], name="", showlegend=False,
                    hovertemplate=f"<b>{row['date_str']}</b><br>Avg RPE: {row['avg_rpe']:.1f}<br>Check-ins: {int(row['count'])}<extra></extra>",
                ))
            fig_ec.update_layout(
                **{**DARK_LAYOUT, "margin": dict(t=16, b=24, l=8, r=8)},
                height=220, barmode="stack", bargap=0.15,
                title=dict(text="28-Day RPE Trend (Evening Check-ins)", font=dict(size=13), x=0),
                xaxis=dict(gridcolor="#1f2530"),
                yaxis=dict(gridcolor="#1f2530", title="Avg RPE", range=[0, 10]),
            )
            st.plotly_chart(fig_ec, use_container_width=True, key=f"ec_rpe_trend_{sel}")

        with st.expander("Recent Check-ins", expanded=False):
            display_ec = pec.sort_values("timestamp", ascending=False).head(20)[
                ["date", "session_rpe", "did_bowl", "bowling_volume", "bowling_intensity"]
            ].rename(columns={
                "date": "Date", "session_rpe": "RPE", "did_bowl": "Bowled",
                "bowling_volume": "Volume", "bowling_intensity": "Intensity",
            })
            def rpe_style_ec(val):
                try: return f"color:{_rpe_color(float(val))}"
                except: return ""
            st.dataframe(display_ec.style.applymap(rpe_style_ec, subset=["RPE"]),
                         use_container_width=True, height=320)
    else:
        ps_week  = ps[ps["timestamp"] >= week_ago]
        ps_month = ps[ps["timestamp"] >= month_ago]

        sessions_this_week = len(ps_week)
        avg_rpe_week       = round(ps_week["rpe"].mean(), 1) if not ps_week.empty else 0
        total_load_week    = int(ps_week["load_au"].sum())

        # ACWR
        acute   = ps_week["load_au"].sum()
        chronic = ps_month["load_au"].sum() / 4 if len(ps_month) >= 4 else ps_month["load_au"].sum()
        acwr    = round(acute / chronic, 2) if chronic > 0 else 0.0
        acwr_risk = "Low" if acwr < 1.3 else ("High" if acwr > 1.5 else "Moderate")
        acwr_color = {"Low": "#22c55e", "Moderate": "#f59e0b", "High": "#ef4444"}.get(acwr_risk, "#6b7a90")

        # ── Key metrics cards ────────────────────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.markdown(_metric_card("Sessions this week", str(sessions_this_week)), unsafe_allow_html=True)
        with m2: st.markdown(_metric_card("Avg RPE (7d)", str(avg_rpe_week), color=_rpe_color(avg_rpe_week)), unsafe_allow_html=True)
        with m3: st.markdown(_metric_card("Total Load (7d)", f"{total_load_week} AU", color=_load_color(total_load_week)), unsafe_allow_html=True)
        with m4: st.markdown(_metric_card("ACWR", str(acwr), sub=f"{acwr_risk} risk", color=acwr_color), unsafe_allow_html=True)

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

        # ── 28-day load trend ────────────────────────────────────────────────
        if not ps_month.empty:
            daily = ps_month.groupby("date").agg(
                total_load=("load_au", "sum"),
                sessions=("load_au", "count"),
                avg_rpe=("rpe", "mean"),
            ).reset_index()
            daily["date_str"] = daily["date"].astype(str)
            daily["color"] = daily["total_load"].apply(_load_color)

            fig_load = go.Figure()
            for _, row in daily.iterrows():
                fig_load.add_trace(go.Bar(
                    x=[row["date_str"]], y=[row["total_load"]],
                    marker_color=row["color"], name="", showlegend=False,
                    hovertemplate=f"<b>{row['date_str']}</b><br>Load: {int(row['total_load'])} AU<br>Sessions: {int(row['sessions'])}<br>Avg RPE: {row['avg_rpe']:.1f}<extra></extra>",
                ))
            fig_load.update_layout(
                **{**DARK_LAYOUT, "margin": dict(t=16, b=24, l=8, r=8)},
                height=220, barmode="stack", bargap=0.15,
                title=dict(text="28-Day Load Trend (AU)", font=dict(size=13), x=0),
                xaxis=dict(gridcolor="#1f2530"),
                yaxis=dict(gridcolor="#1f2530", title="Load (AU)"),
            )
            st.plotly_chart(fig_load, use_container_width=True, key=f"load_trend_{sel}")

        # ── Session breakdown + RPE distribution ─────────────────────────────
        col_type, col_rpe = st.columns(2)

        with col_type:
            type_counts = ps["session_type"].value_counts()
            type_colors = {
                "Training": "#00c2ff", "Match": "#f59e0b",
                "Gym": "#22c55e", "Recovery": "#6b7a90", "Rehab": "#ef4444",
            }
            fig_type = go.Figure(go.Pie(
                labels=type_counts.index.tolist(),
                values=type_counts.values.tolist(),
                marker=dict(colors=[type_colors.get(t, "#6b7a90") for t in type_counts.index]),
                hole=0.5,
                hovertemplate="%{label}: %{value} sessions (%{percent})<extra></extra>",
            ))
            fig_type.update_layout(
                **{**DARK_LAYOUT, "margin": dict(t=32, b=8, l=8, r=8)},
                height=220, showlegend=True,
                title=dict(text="Session Type Breakdown", font=dict(size=13), x=0),
                legend=dict(orientation="v", font=dict(size=11)),
            )
            st.plotly_chart(fig_type, use_container_width=True, key=f"type_pie_{sel}")

        with col_rpe:
            rpe_counts = ps["rpe"].value_counts().sort_index()
            fig_rpe = go.Figure(go.Bar(
                x=rpe_counts.index.tolist(),
                y=rpe_counts.values.tolist(),
                marker_color=[_rpe_color(v) for v in rpe_counts.index],
                hovertemplate="RPE %{x}: %{y} sessions<extra></extra>",
            ))
            fig_rpe.update_layout(
                **{**DARK_LAYOUT, "margin": dict(t=32, b=8, l=8, r=8)},
                height=220,
                title=dict(text="RPE Distribution", font=dict(size=13), x=0),
                xaxis=dict(tickvals=list(range(1,11)), gridcolor="#1f2530", title="RPE"),
                yaxis=dict(gridcolor="#1f2530", title="Sessions"),
            )
            st.plotly_chart(fig_rpe, use_container_width=True, key=f"rpe_dist_{sel}")

        # ── Recent sessions table ─────────────────────────────────────────────
        with st.expander("Recent Sessions", expanded=False):
            display_s = ps.sort_values("timestamp", ascending=False).head(20)[
                ["date","session_type","duration_mins","rpe","load_au","notes"]
            ].rename(columns={
                "date": "Date", "session_type": "Type", "duration_mins": "Duration (min)",
                "rpe": "RPE", "load_au": "Load (AU)", "notes": "Notes",
            })
            def rpe_style(val):
                try: return f"color:{_rpe_color(float(val))}"
                except: return ""
            st.dataframe(display_s.style.applymap(rpe_style, subset=["RPE"]),
                         use_container_width=True, height=320)

        # ── Evening check-in RPE trend (if available) ─────────────────────────
        if not pec.empty:
            pec_month = pec[pec["timestamp"] >= month_ago]
            if not pec_month.empty:
                st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
                daily_ec = pec_month.groupby("date").agg(
                    avg_rpe=("session_rpe", "mean"),
                    count=("session_rpe", "count"),
                ).reset_index()
                daily_ec["date_str"] = daily_ec["date"].astype(str)
                fig_ec = go.Figure(go.Scatter(
                    x=daily_ec["date_str"], y=daily_ec["avg_rpe"],
                    mode="lines+markers",
                    marker=dict(color=[_rpe_color(v) for v in daily_ec["avg_rpe"]], size=8),
                    line=dict(color="#6b7a90", width=1.5),
                    hovertemplate="<b>%{x}</b><br>Check-in RPE: %{y:.1f}<extra></extra>",
                ))
                fig_ec.update_layout(
                    **{**DARK_LAYOUT, "margin": dict(t=16, b=24, l=8, r=8)},
                    height=180,
                    title=dict(text="Evening Check-in RPE (28d)", font=dict(size=13), x=0),
                    xaxis=dict(gridcolor="#1f2530"),
                    yaxis=dict(gridcolor="#1f2530", title="RPE", range=[0, 10]),
                )
                st.plotly_chart(fig_ec, use_container_width=True, key=f"ec_line_{sel}")

    # ════════════════════════════════════════════════════════════════════════
    # EVENING AU TREND  (player vs team average)
    # ════════════════════════════════════════════════════════════════════════
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    st.divider()
    st.markdown("### Evening AU Trend vs Team Average")
    st.caption("AU = RPE × Session Duration · sourced from evening check-ins · last 28 days")

    if not evening.empty and "evening_au" in evening.columns:
        ev_all_28 = evening[
            (evening["timestamp"] >= month_ago) &
            (evening["session_duration_hours"].notna()) &
            (evening["session_duration_hours"] > 0)
        ].copy()

        if ev_all_28.empty:
            st.info("No AU data yet — players need to submit session duration in the evening check-in.")
        else:
            # Team daily avg AU
            team_daily_au = ev_all_28.groupby("date")["evening_au"].mean().reset_index()
            team_daily_au.columns = ["date", "team_avg_au"]
            team_daily_au["date_str"] = team_daily_au["date"].astype(str)

            # Player daily AU
            player_daily_au = pd.DataFrame()
            if not pec.empty and "evening_au" in pec.columns:
                pec_28 = pec[
                    (pec["timestamp"] >= month_ago) &
                    (pec["session_duration_hours"].notna()) &
                    (pec["session_duration_hours"] > 0)
                ]
                if not pec_28.empty:
                    player_daily_au = pec_28.groupby("date")["evening_au"].sum().reset_index()
                    player_daily_au.columns = ["date", "player_au"]
                    player_daily_au["date_str"] = player_daily_au["date"].astype(str)

            fig_au = go.Figure()
            fig_au.add_trace(go.Scatter(
                x=team_daily_au["date_str"],
                y=team_daily_au["team_avg_au"].round(2),
                name="Team Avg AU",
                mode="lines",
                line=dict(color="#6b7a90", width=2, dash="dot"),
                hovertemplate="<b>%{x}</b><br>Team avg: %{y:.1f} AU<extra></extra>",
            ))
            if not player_daily_au.empty:
                fig_au.add_trace(go.Bar(
                    x=player_daily_au["date_str"],
                    y=player_daily_au["player_au"].round(2),
                    name=f"{sel} AU",
                    marker_color="#00c2ff",
                    opacity=0.75,
                    hovertemplate="<b>%{x}</b><br>" + sel + ": %{y:.1f} AU<extra></extra>",
                ))
            fig_au.update_layout(
                **{**DARK_LAYOUT, "margin": dict(t=16, b=24, l=8, r=8)},
                height=240, barmode="overlay",
                title=dict(text=f"{sel} — Daily AU vs Team Avg (28d)", font=dict(size=13), x=0),
                xaxis=dict(gridcolor="#1f2530"),
                yaxis=dict(gridcolor="#1f2530", title="AU (RPE × hrs)"),
                legend=dict(orientation="h", y=-0.25),
            )
            st.plotly_chart(fig_au, use_container_width=True, key=f"au_trend_{sel}")
    else:
        st.info("No AU data yet — players need to submit session duration in the evening check-in.")

    # ════════════════════════════════════════════════════════════════════════
    # BATTING LOAD SECTION  (all players, sourced from evening check-ins)
    # ════════════════════════════════════════════════════════════════════════
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    st.divider()
    st.markdown("### Batting Load")

    pec_bat = pd.DataFrame()
    if not pec.empty and "did_bat" in pec.columns:
        pec_bat = pec[pec["did_bat"].astype(str).str.lower().isin(["true", "1", "yes"])].copy()

    if pec_bat.empty:
        st.info(f"No batting data for {sel} yet.")
    else:
        BALLS_ORDER = {"<24": 1, "24-36": 2, "36-48": 3, "48-60": 4, "60+": 5}
        BALLS_COLOR = {"<24": "#22c55e", "24-36": "#00c2ff", "36-48": "#f59e0b", "48-60": "#ef4444", "60+": "#ff4444"}

        pec_bat_week  = pec_bat[pec_bat["timestamp"] >= week_ago]
        pec_bat_month = pec_bat[pec_bat["timestamp"] >= month_ago]

        batting_days_week = len(pec_bat_week["date"].unique())
        if not pec_bat_week.empty and "balls_faced" in pec_bat_week.columns:
            dominant_balls = pec_bat_week["balls_faced"].dropna().mode()
            dominant_balls = dominant_balls.iloc[0] if not dominant_balls.empty else "—"
        else:
            dominant_balls = "—"
        balls_color = BALLS_COLOR.get(dominant_balls, "#6b7a90")

        bb1, bb2 = st.columns(2)
        with bb1: st.markdown(_metric_card("Batting days (7d)", str(batting_days_week)), unsafe_allow_html=True)
        with bb2: st.markdown(_metric_card("Typical balls faced (7d)", dominant_balls, color=balls_color), unsafe_allow_html=True)

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

        if not pec_bat_month.empty and "balls_faced" in pec_bat_month.columns:
            bat_daily = pec_bat_month.groupby("date").agg(
                balls=("balls_faced", lambda x: x.mode().iloc[0] if not x.dropna().empty else "<24"),
                sessions=("balls_faced", "count"),
            ).reset_index()
            bat_daily["date_str"] = bat_daily["date"].astype(str)
            bat_daily["color"] = bat_daily["balls"].map(BALLS_COLOR).fillna("#6b7a90")
            bat_daily["rank"]  = bat_daily["balls"].map(BALLS_ORDER).fillna(1)

            fig_bat = go.Figure()
            for balls_cat, color in BALLS_COLOR.items():
                subset = bat_daily[bat_daily["balls"] == balls_cat]
                if not subset.empty:
                    fig_bat.add_trace(go.Bar(
                        x=subset["date_str"], y=subset["rank"],
                        name=balls_cat, marker_color=color,
                        hovertemplate="<b>%{x}</b><br>Balls faced: " + balls_cat + "<extra></extra>",
                    ))
            fig_bat.update_layout(
                **{**DARK_LAYOUT, "margin": dict(t=16, b=24, l=8, r=8)},
                height=220, barmode="group",
                title=dict(text="Batting Days — Balls Faced (28d)", font=dict(size=13), x=0),
                xaxis=dict(gridcolor="#1f2530"),
                yaxis=dict(gridcolor="#1f2530", tickvals=[1,2,3,4,5],
                           ticktext=["<24","24-36","36-48","48-60","60+"], title=""),
                legend=dict(orientation="h", y=-0.3),
            )
            st.plotly_chart(fig_bat, use_container_width=True, key=f"bat_load_{sel}")

        with st.expander("Recent Batting Check-ins", expanded=False):
            display_bat = pec_bat.sort_values("timestamp", ascending=False).head(20)[
                ["date", "balls_faced", "session_rpe"]
            ].rename(columns={"date": "Date", "balls_faced": "Balls Faced", "session_rpe": "RPE"})
            st.dataframe(display_bat, use_container_width=True, height=280)

    # ════════════════════════════════════════════════════════════════════════
    # BOWLING LOAD SECTION  (fast bowlers only, sourced from evening check-ins)
    # ════════════════════════════════════════════════════════════════════════
    if not is_fb:
        return

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    st.divider()
    st.markdown("### Bowling Load")

    pec_bowl = pec[pec["did_bowl"].astype(str).str.lower().isin(["true", "1", "yes"])].copy() if not pec.empty else pd.DataFrame()

    if pec_bowl.empty:
        st.info(f"No bowling data for {sel} yet.")
        return

    # Intensity order for sorting / coloring
    INTENSITY_ORDER = {"Low": 1, "Moderate": 2, "High": 3}
    INTENSITY_COLOR = {"Low": "#22c55e", "Moderate": "#f59e0b", "High": "#ef4444"}

    pec_bowl_week  = pec_bowl[pec_bowl["timestamp"] >= week_ago]
    pec_bowl_month = pec_bowl[pec_bowl["timestamp"] >= month_ago]

    bowling_days_week = len(pec_bowl_week["date"].unique())
    if not pec_bowl_week.empty and "bowling_intensity" in pec_bowl_week.columns:
        dominant_intensity = pec_bowl_week["bowling_intensity"].mode().iloc[0] if not pec_bowl_week["bowling_intensity"].dropna().empty else "—"
    else:
        dominant_intensity = "—"
    intensity_color = INTENSITY_COLOR.get(dominant_intensity, "#6b7a90")

    b1, b2 = st.columns(2)
    with b1: st.markdown(_metric_card("Bowling days (7d)", str(bowling_days_week)), unsafe_allow_html=True)
    with b2: st.markdown(_metric_card("Dominant intensity (7d)", dominant_intensity, color=intensity_color), unsafe_allow_html=True)

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # ── 28-day bowling intensity timeline ────────────────────────────────────
    if not pec_bowl_month.empty:
        bowl_daily = pec_bowl_month.groupby("date").agg(
            intensity=("bowling_intensity", lambda x: x.mode().iloc[0] if not x.dropna().empty else "Low"),
            volume=("bowling_volume", lambda x: x.mode().iloc[0] if not x.dropna().empty else ""),
            sessions=("bowling_intensity", "count"),
        ).reset_index()
        bowl_daily["date_str"] = bowl_daily["date"].astype(str)
        bowl_daily["color"] = bowl_daily["intensity"].map(INTENSITY_COLOR).fillna("#6b7a90")
        bowl_daily["intensity_rank"] = bowl_daily["intensity"].map(INTENSITY_ORDER).fillna(1)

        fig_bowl = go.Figure()
        for intensity, color in INTENSITY_COLOR.items():
            subset = bowl_daily[bowl_daily["intensity"] == intensity]
            if not subset.empty:
                fig_bowl.add_trace(go.Bar(
                    x=subset["date_str"], y=subset["intensity_rank"],
                    name=intensity, marker_color=color,
                    hovertemplate="<b>%{x}</b><br>Intensity: " + intensity + "<br>Volume: %{customdata}<extra></extra>",
                    customdata=subset["volume"],
                ))
        fig_bowl.update_layout(
            **{**DARK_LAYOUT, "margin": dict(t=16, b=24, l=8, r=8)},
            height=220, barmode="group",
            title=dict(text="Bowling Days — Intensity (28d)", font=dict(size=13), x=0),
            xaxis=dict(gridcolor="#1f2530"),
            yaxis=dict(gridcolor="#1f2530", tickvals=[1, 2, 3], ticktext=["Low", "Moderate", "High"], title=""),
            legend=dict(orientation="h", y=-0.3),
        )
        st.plotly_chart(fig_bowl, use_container_width=True, key=f"bowl_intensity_{sel}")

    # ── Recent bowling check-ins table ────────────────────────────────────────
    with st.expander("Recent Bowling Check-ins", expanded=False):
        display_b = pec_bowl.sort_values("timestamp", ascending=False).head(20)[
            ["date", "bowling_volume", "bowling_intensity", "session_rpe"]
        ].rename(columns={
            "date": "Date", "bowling_volume": "Volume", "bowling_intensity": "Intensity", "session_rpe": "RPE",
        })
        def intensity_style(val):
            return f"color:{INTENSITY_COLOR.get(val, '#e8edf5')}"
        st.dataframe(display_b.style.applymap(intensity_style, subset=["Intensity"]),
                     use_container_width=True, height=300)

with tab_load:
    render_player_load()

# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — SQUAD
# ════════════════════════════════════════════════════════════════════════════
@st.fragment
def render_squad():
    roster   = load_roster()
    wellness = load_wellness()
    today    = date.today()

    if roster.empty:
        st.info("No players yet — add them in the Admin tab.")
        return

    def _f(val):
        return str(val) if pd.notna(val) and str(val).strip() else "—"

    names = roster["name"].dropna().tolist()
    selected_name = st.selectbox("Select Player", names, key="squad_player_select")

    player = roster[roster["name"] == selected_name].iloc[0]
    pw = pd.DataFrame()
    if not wellness.empty:
        pw = wellness[wellness["player_name"] == selected_name].sort_values("timestamp")

    status = player.get("current_status", "")
    status_color = STATUS_COLORS.get(status, "#6b7a90")
    age_val = player.get("age")
    age_str = str(int(age_val)) if pd.notna(age_val) and age_val != "" else "—"

    # ── Status banner ────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:{status_color}18;border:1px solid {status_color}44;border-radius:10px;
                padding:12px 20px;margin:12px 0 20px;display:flex;align-items:center;gap:12px;">
      <div style="width:12px;height:12px;border-radius:50%;background:{status_color};flex-shrink:0;"></div>
      <span style="font-size:15px;font-weight:600;color:{status_color};">{status or 'No status set'}</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Profile + Radar ──────────────────────────────────────────────────────
    col_profile, col_radar = st.columns([1, 1], gap="large")

    with col_profile:
        st.markdown("#### Player Profile")

        def info_row(label, value, color=None):
            val_style = f"color:{color};" if color else ""
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;padding:8px 0;
                        border-bottom:1px solid #1f2530;font-size:14px;">
              <span style="color:#6b7a90;">{label}</span>
              <span style="font-weight:500;{val_style}">{value}</span>
            </div>""", unsafe_allow_html=True)

        info_row("Name",          _f(player.get("name")))
        info_row("Age",           age_str)
        info_row("Role",          _f(player.get("role")))
        info_row("Batting Style", _f(player.get("batting_style")))
        info_row("Bowling Style", _f(player.get("bowling_style")))
        info_row("Dominant Side", _f(player.get("dominant_side")))
        info_row("Fast Bowler",   "Yes" if is_fast_bowler(player.get("is_fast_bowler")) else "No")
        info_row("Contact",       _f(player.get("contact")))

        ih = player.get("injury_history")
        if pd.notna(ih) and str(ih).strip():
            st.markdown("<div style='margin-top:12px;font-size:13px;color:#6b7a90;'>Injury History</div>",
                        unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:13px;padding:6px 0;'>{ih}</div>", unsafe_allow_html=True)

        sn = player.get("status_notes")
        if pd.notna(sn) and str(sn).strip():
            st.markdown("<div style='margin-top:8px;font-size:13px;color:#6b7a90;'>Status Notes</div>",
                        unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:13px;padding:6px 0;'>{sn}</div>", unsafe_allow_html=True)

        if not pw.empty:
            last_avail = pw.iloc[-1].get("availability_status", "")
            if last_avail and pd.notna(last_avail):
                avail_color = "#22c55e" if last_avail == "Available" else (
                    "#f59e0b" if "Modified" in last_avail or "Recovery" in last_avail else "#ef4444"
                )
                st.markdown("<div style='margin-top:8px;font-size:13px;color:#6b7a90;'>Self-reported (latest)</div>",
                            unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:13px;padding:6px 0;color:{avail_color};font-weight:600;'>{last_avail}</div>",
                            unsafe_allow_html=True)

    with col_radar:
        st.markdown("#### Latest Wellness")
        if not pw.empty:
            last = pw.iloc[-1]
            sleep    = float(last.get("sleep_quality", 3) or 3)
            energy   = float(last.get("energy_level",  3) or 3)
            soreness = float(last.get("body_soreness", 3) or 3)
            stress   = float(last.get("stress",        3) or 3)
            mood     = float(last.get("mood",          3) or 3)
            readiness_sc = int(sleep + energy + (6 - soreness) + (6 - stress) + mood)
            band, band_color = readiness_band(readiness_sc)

            # Readiness score pill
            st.markdown(f"""
            <div style="text-align:center;margin-bottom:16px;">
              <div style="font-size:11px;color:#6b7a90;letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;">
                Readiness Score
              </div>
              <div style="font-size:52px;font-weight:800;color:{band_color};line-height:1;">{readiness_sc}</div>
              <div style="font-size:13px;color:{band_color};margin-top:2px;">{band} &nbsp;/ 25</div>
            </div>
            """, unsafe_allow_html=True)

            # Extra wellness metrics
            _mood        = last.get("mood")
            _stress      = last.get("stress")
            _sleep_hours = last.get("sleep_hours")
            _is_sick     = str(last.get("is_sick", "")).lower() in ("true", "1", "yes")
            extra_items = []
            if pd.notna(_mood) and _mood != "":
                mood_color = "#22c55e" if float(_mood) >= 4 else ("#ef4444" if float(_mood) <= 2 else "#f59e0b")
                extra_items.append(f'<span style="color:#6b7a90;">Mood</span> <span style="font-weight:600;color:{mood_color};">{int(float(_mood))}/5</span>')
            if pd.notna(_stress) and _stress != "":
                stress_color = "#ef4444" if float(_stress) >= 4 else ("#22c55e" if float(_stress) <= 2 else "#f59e0b")
                extra_items.append(f'<span style="color:#6b7a90;">Stress</span> <span style="font-weight:600;color:{stress_color};">{int(float(_stress))}/5</span>')
            if pd.notna(_sleep_hours) and _sleep_hours != "":
                sh_color = "#22c55e" if float(_sleep_hours) >= 8 else ("#ef4444" if float(_sleep_hours) < 6 else "#f59e0b")
                extra_items.append(f'<span style="color:#6b7a90;">Sleep</span> <span style="font-weight:600;color:{sh_color};">{float(_sleep_hours):.0f}h</span>')
            sick_color = "#ef4444" if _is_sick else "#22c55e"
            extra_items.append(f'<span style="color:#6b7a90;">Sick</span> <span style="font-weight:600;color:{sick_color};">{"Yes" if _is_sick else "No"}</span>')
            if extra_items:
                st.markdown(
                    '<div style="display:flex;flex-wrap:wrap;gap:16px;justify-content:center;margin-bottom:12px;">' +
                    "".join(f'<div style="text-align:center;font-size:13px;">{item}</div>' for item in extra_items) +
                    "</div>",
                    unsafe_allow_html=True,
                )

            r_labels = ["Sleep", "Energy", "Soreness"]
            r_vals   = [sleep, energy, soreness]
            fig_radar = go.Figure(go.Scatterpolar(
                r=r_vals + [r_vals[0]],
                theta=r_labels + [r_labels[0]],
                fill="toself",
                fillcolor=f"rgba({','.join(str(int(band_color.lstrip('#')[i:i+2], 16)) for i in (0,2,4))},0.12)",
                line=dict(color=band_color, width=2),
            ))
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0,5], color="#6b7a90", tickfont=dict(size=9)),
                    angularaxis=dict(color="#6b7a90"),
                    bgcolor="#111318",
                ),
                paper_bgcolor="#161a22",
                font=dict(color="#e8edf5"),
                height=220, margin=dict(t=8, b=8, l=8, r=8),
                showlegend=False,
            )
            st.plotly_chart(fig_radar, use_container_width=True, key=f"radar_{selected_name}")
            st.caption(f"Last submission: {last['date']}")
        else:
            st.info("No wellness submissions yet.")

    # ── 7-day wellness trend ─────────────────────────────────────────────────
    st.markdown("#### 7-Day Wellness Trend")
    if not pw.empty:
        cutoff = pd.Timestamp(today) - timedelta(days=6)
        trend = pw[pw["timestamp"] >= cutoff].copy()
        if not trend.empty:
            trend["readiness"] = (
                trend["sleep_quality"].fillna(3) +
                trend["energy_level"].fillna(3) +
                (6 - trend["body_soreness"].fillna(3)) +
                (6 - trend["stress"].fillna(3)) +
                trend["mood"].fillna(3)
            )
            trend["date_str"] = trend["date"].astype(str)
            fig_trend = go.Figure()
            metrics = [
                ("sleep_quality", "Sleep",    "#00c2ff"),
                ("energy_level",  "Energy",   "#22c55e"),
                ("body_soreness", "Soreness", "#f59e0b"),
                ("mood",          "Mood",      "#a78bfa"),
                ("stress",        "Stress",    "#f87171"),
            ]
            for col, label, color in metrics:
                if col in trend.columns:
                    fig_trend.add_trace(go.Scatter(
                        x=trend["date_str"], y=trend[col],
                        name=label, line=dict(color=color, width=2),
                        mode="lines+markers", marker=dict(size=6),
                        connectgaps=False,
                    ))
            fig_trend.update_layout(
                **{**DARK_LAYOUT, "margin": dict(t=16, b=24, l=8, r=8)},
                height=240,
                yaxis=dict(range=[0.5, 5.5], tickvals=[1,2,3,4,5], gridcolor="#1f2530"),
                xaxis=dict(gridcolor="#1f2530"),
                legend=dict(orientation="h", y=-0.2),
            )
            st.plotly_chart(fig_trend, use_container_width=True, key=f"trend_{selected_name}")

            # Readiness score trend
            st.markdown("#### Readiness Score (last 7 days)")
            fig_rs = go.Figure()
            fig_rs.add_hrect(y0=18, y1=25, fillcolor="#22c55e", opacity=0.07, line_width=0)
            fig_rs.add_hrect(y0=14, y1=17, fillcolor="#f59e0b", opacity=0.07, line_width=0)
            fig_rs.add_hrect(y0=0,  y1=13, fillcolor="#ef4444", opacity=0.07, line_width=0)
            fig_rs.add_trace(go.Scatter(
                x=trend["date_str"], y=trend["readiness"],
                line=dict(color="#00c2ff", width=2),
                mode="lines+markers", marker=dict(size=7),
                name="Readiness",
            ))
            fig_rs.update_layout(
                **{**DARK_LAYOUT, "margin": dict(t=16, b=24, l=8, r=8)},
                height=200,
                yaxis=dict(range=[0, 26], gridcolor="#1f2530",
                           tickvals=[0, 14, 18, 25],
                           ticktext=["0","14 (Monitor)","18 (Normal)","25"]),
                xaxis=dict(gridcolor="#1f2530"),
                showlegend=False,
            )
            st.plotly_chart(fig_rs, use_container_width=True, key=f"rs_{selected_name}")
        else:
            st.info("No wellness data in the last 7 days.")
    else:
        st.info("No wellness data for this player.")

with tab_squad:
    render_squad()

# ════════════════════════════════════════════════════════════════════════════
# TAB 6 — ADMIN
# ════════════════════════════════════════════════════════════════════════════
@st.fragment
def render_admin_tab():
    st.subheader("Roster Management")
    st.caption("Edit directly in the table. Add rows with the + button. Save when done.")

    current_roster = load_roster()

    edited = st.data_editor(
        current_roster,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "name":           st.column_config.TextColumn("Name", required=True),
            "role":           st.column_config.SelectboxColumn("Role",
                                options=["Batsman","Bowler","All-rounder","Wicket-keeper"]),
            "batting_style":  st.column_config.SelectboxColumn("Batting Style",
                                options=["Right-hand bat","Left-hand bat"]),
            "bowling_style":  st.column_config.TextColumn("Bowling Style",
                                help="e.g. Right-arm fast, Left-arm spin, Off-spin"),
            "dominant_side":  st.column_config.SelectboxColumn("Dominant Side",
                                options=["Right","Left"]),
            "type":           st.column_config.TextColumn("Playing Type",
                                help="e.g. Aggressive opener, Finisher"),
            "age":            st.column_config.NumberColumn("Age", min_value=None, max_value=None, step=1),
            "is_fast_bowler": st.column_config.CheckboxColumn("Fast Bowler?"),
            "contact":        st.column_config.TextColumn("Contact", help="Phone or email"),
            "injury_history": st.column_config.TextColumn("Injury History"),
            "current_status": st.column_config.SelectboxColumn("Status",
                                options=list(STATUS_COLORS.keys())),
            "status_notes":   st.column_config.TextColumn("Notes"),
        },
        key="roster_editor",
    )

    c_save, c_gap = st.columns([1, 4])
    with c_save:
        if st.button("Save Roster", type="primary", use_container_width=True):
            try:
                import json
                records = json.loads(edited.to_json(orient="records"))
                r = requests.put(f"{API_URL}/data/roster",
                                 json=records, timeout=10)
                r.raise_for_status()
                load_roster.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Failed to save roster: {e}")

    st.divider()

    # ── Delete Player ────────────────────────────────────────────────────────
    st.subheader("Delete Player")
    if not current_roster.empty:
        player_options = {
            f"{row['name']} (#{int(row['id'])})" if pd.notna(row.get("id")) else row["name"]: int(row["id"])
            for _, row in current_roster.iterrows()
            if pd.notna(row.get("name")) and str(row.get("name")).strip()
        }
        selected_label = st.selectbox("Select player to delete", options=list(player_options.keys()), key="delete_player_select")
        if st.button("Delete Player", type="secondary"):
            player_id = player_options[selected_label]
            try:
                r = requests.delete(f"{API_URL}/data/roster/{player_id}", timeout=10)
                r.raise_for_status()
                load_roster.clear()
                st.success(f"Deleted {selected_label}")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to delete player: {e}")
    else:
        st.caption("No players in roster.")

    st.divider()

    # ── Player Check-in Links ────────────────────────────────────────────────
    with st.expander("Player Check-in Links"):
        st.caption("Share each player's personal link — they land directly on their Morning/Evening choice.")
        base_url = PUBLIC_URL
        if not current_roster.empty:
            names = [n for n in current_roster["name"].dropna().tolist() if str(n).strip()]
            for name in names:
                slug = urllib.parse.quote(str(name), safe="")
                col_name, col_link = st.columns([1, 3])
                with col_name:
                    st.markdown(
                        f"<div style='padding-top:8px;font-size:14px;font-weight:500;'>{name}</div>",
                        unsafe_allow_html=True,
                    )
                with col_link:
                    st.code(f"{base_url}/checkin/{slug}", language=None)
        else:
            st.info("No players in roster yet.")

    st.divider()
    st.subheader("Export Data")
    c1, c2, c3, c4 = st.columns(4)
    export_dfs = {
        "wellness":        load_wellness(),
        "sessions":        load_sessions(),
        "evening_checkins": load_evening(),
        "roster":          current_roster,
    }
    for col, (name, df) in zip([c1, c2, c3, c4], export_dfs.items()):
        with col:
            if not df.empty:
                st.download_button(
                    f"Export {name}.csv",
                    df.to_csv(index=False),
                    file_name=f"{name}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            else:
                st.button(f"Export {name}.csv", disabled=True, use_container_width=True)

with tab_admin:
    render_admin_tab()
