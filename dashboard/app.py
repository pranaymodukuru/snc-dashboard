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

DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "knights2024")
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
    "tightness_locations","availability_status","notes",
    "mood","stress_level","hamstring_tightness","groin_stiffness","lower_back_stiffness",
]
ROSTER_COLS   = [
    "name","role","batting_style","bowling_style","dominant_side",
    "type","age","is_fast_bowler","contact",
    "injury_history","current_status","status_notes",
]
SESSIONS_COLS = ["timestamp","player_name","session_type","duration_mins","rpe","notes"]
BOWLING_COLS  = ["timestamp","player_name","match_balls","net_balls","high_intensity_balls","notes"]
EVENING_COLS  = ["timestamp","player_name","session_rpe","did_bowl","bowling_volume","bowling_intensity"]

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
    df = pd.DataFrame(_api_get("/data/wellness"), columns=WELLNESS_COLS)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
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
    df = pd.DataFrame(_api_get("/data/evening"), columns=EVENING_COLS)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["timestamp"].dt.date
    return df


@st.cache_data(ttl=30)
def load_sessions() -> pd.DataFrame:
    df = pd.DataFrame(_api_get("/data/sessions"), columns=SESSIONS_COLS)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["timestamp"].dt.date
        df["load_au"] = df["duration_mins"] * df["rpe"]
    return df


@st.cache_data(ttl=30)
def load_bowling() -> pd.DataFrame:
    df = pd.DataFrame(_api_get("/data/bowling"), columns=BOWLING_COLS)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["timestamp"].dt.date
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
    ("Green",  "#22c55e", 13, 15),
    ("Yellow", "#f59e0b", 10, 12),
    ("Red",    "#ef4444",  0,  9),
]

BOWLER_STATUS_THRESHOLDS = [
    ("Green",  "#22c55e",   0, 199),
    ("Yellow", "#f59e0b", 200, 230),
    ("Red",    "#ef4444", 231, 9999),
]

def readiness_score(row) -> int:
    """Sleep(1-5) + Energy(1-5) + inverted Soreness(1-5) → max 15."""
    sleep   = float(row.get("sleep_quality",  3) or 3)
    energy  = float(row.get("energy_level",   3) or 3)
    soreness= float(row.get("body_soreness",  3) or 3)
    return int(sleep + energy + (6 - soreness))

def readiness_band(score: int) -> tuple[str, str]:
    for label, color, lo, hi in READINESS_SCORE_RANGES:
        if lo <= score <= hi:
            return label, color
    return "Red", "#ef4444"

def bowler_status_band(balls: int) -> tuple[str, str]:
    for label, color, lo, hi in BOWLER_STATUS_THRESHOLDS:
        if lo <= balls <= hi:
            return label, color
    return "Red", "#ef4444"

@st.fragment
def render_overview():
    roster   = load_roster()
    wellness = load_wellness()
    bowling  = load_bowling()
    today    = date.today()

    col_left, col_right = st.columns([1, 1], gap="large")

    # ── LEFT COLUMN ──────────────────────────────────────────────────────────
    with col_left:

        # ── Team Availability ────────────────────────────────────────────────
        st.markdown("### Team Availability")

        avail_map = {
            "Fully Available": ("#22c55e", ["Full Training"]),
            "Modified":        ("#00c2ff", ["Modified", "Recovery"]),
            "Rehab":           ("#f97316", ["Rehab", "Unavailable"]),
        }

        avail_counts = {}
        if not roster.empty and "current_status" in roster.columns:
            sc = roster["current_status"].value_counts().to_dict()
            for label, (color, statuses) in avail_map.items():
                avail_counts[label] = sum(sc.get(s, 0) for s in statuses)
        else:
            avail_counts = {k: 0 for k in avail_map}

        total_players = sum(avail_counts.values())

        pie_labels  = list(avail_counts.keys())
        pie_values  = list(avail_counts.values())
        pie_colors  = [avail_map[k][0] for k in pie_labels]

        fig_pie = go.Figure(go.Pie(
            labels=pie_labels,
            values=pie_values,
            marker=dict(colors=pie_colors),
            hole=0.45,
            textinfo="percent",
            hovertemplate="%{label}: %{value}<extra></extra>",
        ))
        pie_layout = {**DARK_LAYOUT, "margin": dict(t=8, b=8, l=8, r=8)}
        fig_pie.update_layout(
            **pie_layout,
            height=230,
            showlegend=False,
        )

        pc_col, legend_col = st.columns([2, 1])
        with pc_col:
            st.plotly_chart(fig_pie, use_container_width=True)
        with legend_col:
            st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)
            for label, (color, _) in avail_map.items():
                cnt = avail_counts.get(label, 0)
                st.markdown(f"""
                <div style="margin-bottom:10px;">
                  <span style="display:inline-block;width:12px;height:12px;border-radius:50%;
                               background:{color};margin-right:6px;vertical-align:middle;"></span>
                  <span style="color:#e8edf5;font-size:13px;">{label}</span>
                  <span style="float:right;font-weight:700;color:{color};font-size:18px;">{cnt}</span>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        st.divider()

        # ── Fast Bowlers Status ───────────────────────────────────────────────
        st.markdown("### Fast Bowlers Status")

        fb_names = fast_bowlers(roster)
        if not fb_names:
            st.info("No fast bowlers in roster yet.")
        else:
            sel_bowler = st.selectbox("Select FB Name", ["All"] + fb_names, key="fb_select")

            display_bowlers = fb_names if sel_bowler == "All" else [sel_bowler]

            now_ts = pd.Timestamp(today)
            cutoff_week = now_ts - timedelta(days=7)

            rows = []
            for name in display_bowlers:
                weekly_balls = 0
                if not bowling.empty:
                    pb = bowling[
                        (bowling["player_name"] == name) &
                        (bowling["timestamp"] >= cutoff_week)
                    ]
                    if not pb.empty:
                        weekly_balls = int(
                            pb[["match_balls", "net_balls", "high_intensity_balls"]]
                            .fillna(0).sum().sum()
                        )
                label, color = bowler_status_band(weekly_balls)
                rows.append({"Name": name, "Weekly Balls": weekly_balls, "_color": color, "_label": label})

            for r in rows:
                col_n, col_b, col_s = st.columns([2, 1, 1])
                with col_n:
                    st.markdown(f"<span style='font-size:14px;'>{r['Name']}</span>", unsafe_allow_html=True)
                with col_b:
                    st.markdown(f"<span style='font-size:14px;font-weight:600;'>{r['Weekly Balls']}</span>", unsafe_allow_html=True)
                with col_s:
                    st.markdown(f"""
                    <span style="background:{r['_color']}22;color:{r['_color']};
                                 border:1px solid {r['_color']}55;border-radius:4px;
                                 padding:2px 10px;font-size:12px;font-weight:600;">
                      {r['_label']}
                    </span>""", unsafe_allow_html=True)
            st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)

    # ── RIGHT COLUMN ─────────────────────────────────────────────────────────
    with col_right:

        # ── Readiness Scores (by date) ────────────────────────────────────────
        st.markdown("### Readiness Scores")

        date_options = []
        if not wellness.empty and "date" in wellness.columns:
            date_options = sorted(wellness["date"].dropna().unique(), reverse=True)

        sel_date = st.selectbox(
            "Date",
            options=date_options if date_options else [today],
            format_func=lambda d: str(d),
            key="readiness_date",
        )

        green_count = yellow_count = red_count = 0
        if not wellness.empty:
            day_df = wellness[wellness["date"] == sel_date]
            latest_per_player = day_df.sort_values("timestamp").groupby("player_name").last()
            for _, row in latest_per_player.iterrows():
                sc = readiness_score(row)
                band, _ = readiness_band(sc)
                if band == "Green":   green_count  += 1
                elif band == "Yellow": yellow_count += 1
                else:                  red_count    += 1

        r1, r2, r3 = st.columns(3)
        for col, label, color, count in [
            (r1, "Green",  "#22c55e", green_count),
            (r2, "Yellow", "#f59e0b", yellow_count),
            (r3, "Red",    "#ef4444", red_count),
        ]:
            with col:
                st.markdown(f"""
                <div class="metric-card" style="border-top:2px solid {color};text-align:center;">
                  <div class="metric-label" style="color:{color};">{label}</div>
                  <div class="metric-value" style="color:{color};font-size:44px;">{count}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
        st.caption("Readiness = Sleep(5) + Energy(5) + Soreness(5) = max 15 · 13–15 Green · 10–12 Yellow · <10 Red")

        st.divider()

        # ── Top Concerns ──────────────────────────────────────────────────────
        st.markdown("### Top Concerns")

        concerns = []
        if not wellness.empty:
            today_df = wellness[wellness["date"] == today]
            latest   = today_df.sort_values("timestamp").groupby("player_name").last()
            for player_name, row in latest.iterrows():
                flags = []
                # new format: tightness_locations is a comma-separated string
                locs = str(row.get("tightness_locations") or "").strip()
                if locs and locs.lower() != "none":
                    for loc in locs.split(","):
                        loc = loc.strip()
                        if loc and loc.lower() != "none":
                            flags.append(f"{loc} tightness")
                # old format: per-area 1-5 scale fields (backward compat)
                if not locs:
                    if pd.notna(row.get("hamstring_tightness")) and row["hamstring_tightness"] >= 4:
                        flags.append("Hamstring tightness")
                    if pd.notna(row.get("groin_stiffness")) and row["groin_stiffness"] >= 4:
                        flags.append("Groin tightness")
                    if pd.notna(row.get("lower_back_stiffness")) and row["lower_back_stiffness"] >= 4:
                        flags.append("Lower back tightness")
                if row.get("sleep_quality", 5) <= 2:
                    flags.append("Low sleep")
                if row.get("energy_level", 5) <= 2:
                    flags.append("Low energy")
                if row.get("body_soreness", 1) >= 4:
                    flags.append("High soreness")
                avail = str(row.get("availability_status") or "").strip()
                if avail and avail not in ("Available", ""):
                    flags.append(f"Self-reported: {avail}")
                if flags:
                    concerns.append({"player": player_name, "flags": flags})

        if concerns:
            for i, c in enumerate(concerns[:5], 1):
                flag_str = " / ".join(c["flags"])
                st.markdown(f"""
                <div class="alert-item">
                  <div class="alert-name">{i}. {c['player']}</div>
                  <div class="alert-tags">{flag_str}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.success("No concerns flagged today")

        st.divider()

        # ── Wellness Completed ────────────────────────────────────────────────
        st.markdown("### Wellness Completed")

        submitted = set()
        if not wellness.empty:
            submitted = set(wellness[wellness["date"] == today]["player_name"].tolist())
        total = len(roster) if not roster.empty else 0

        st.markdown(f"""
        <div style="font-size:32px;font-weight:800;color:#e8edf5;margin:8px 0;">
          {len(submitted)}
          <span style="font-size:18px;color:#6b7a90;">/ {total} players</span>
        </div>
        """, unsafe_allow_html=True)

        missing = [n for n in (roster["name"].tolist() if not roster.empty else []) if n not in submitted]
        if missing:
            with st.expander(f"Not submitted ({len(missing)})"):
                for name in missing:
                    st.markdown(f"- {name}")

with tab_overview:
    render_overview()

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — WELLNESS
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

    # ── Morning wellness ─────────────────────────────────────────────────────
    with st.expander("Morning Check-ins (Wellness)", expanded=True):
        wellness = load_wellness()
        if wellness.empty:
            st.info("No morning check-in data yet.")
        else:
            df_w = _date_filter(wellness, "wellness")
            keep = ["date","player_name","sleep_quality","energy_level","body_soreness",
                    "tightness_locations","availability_status","notes"]
            df_w = df_w[[c for c in keep if c in df_w.columns]].rename(columns={
                "player_name":"Player","sleep_quality":"Sleep","energy_level":"Energy",
                "body_soreness":"Soreness","tightness_locations":"Tightness",
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
            st.dataframe(styled, use_container_width=True, height=380)
            _export_btn(df_w, "morning_checkins")

    # ── Evening check-ins ────────────────────────────────────────────────────
    with st.expander("Evening Check-ins (Session RPE & Bowling)", expanded=False):
        evening = load_evening()
        if evening.empty:
            st.info("No evening check-in data yet.")
        else:
            df_e = _date_filter(evening, "evening")
            st.dataframe(df_e.drop(columns=["timestamp"], errors="ignore"),
                         use_container_width=True, height=320)
            _export_btn(df_e, "evening_checkins")

    # ── Session load ─────────────────────────────────────────────────────────
    with st.expander("Session Load (Coach Logged)", expanded=False):
        sessions = load_sessions()
        if sessions.empty:
            st.info("No session data yet.")
        else:
            df_s = _date_filter(sessions, "sessions")
            st.dataframe(
                df_s[["date","player_name","session_type","duration_mins","rpe","load_au","notes"]]
                  .rename(columns={"player_name":"Player","session_type":"Type",
                                   "duration_mins":"Duration (min)","load_au":"Load (AU)"}),
                use_container_width=True, height=320,
            )
            _export_btn(df_s, "sessions")

    # ── Bowling load ─────────────────────────────────────────────────────────
    with st.expander("Bowling Load (Coach Logged)", expanded=False):
        bowling = load_bowling()
        if bowling.empty:
            st.info("No bowling data yet.")
        else:
            df_b = _date_filter(bowling, "bowling")
            df_b = df_b.assign(total=df_b[["match_balls","net_balls","high_intensity_balls"]].fillna(0).sum(axis=1))
            st.dataframe(
                df_b[["date","player_name","match_balls","net_balls","high_intensity_balls","total","notes"]]
                  .rename(columns={"player_name":"Player","match_balls":"Match","net_balls":"Net",
                                   "high_intensity_balls":"High Int.","total":"Total"}),
                use_container_width=True, height=320,
            )
            _export_btn(df_b, "bowling")

    # ── Roster ───────────────────────────────────────────────────────────────
    with st.expander("Roster", expanded=False):
        roster = load_roster()
        if roster.empty:
            st.info("No roster data yet.")
        else:
            st.dataframe(roster, use_container_width=True, height=320)
            _export_btn(roster, "roster")

with tab_raw:
    render_raw_data()

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — PLAYER LOAD  (session + bowling combined)
# ════════════════════════════════════════════════════════════════════════════
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

@st.fragment
def render_player_load():
    roster   = load_roster()
    sessions = load_sessions()
    bowling  = load_bowling()
    today    = date.today()
    now_ts   = pd.Timestamp(today)

    st.subheader("Player Load")

    if roster.empty:
        st.info("No players in roster yet — add them in the Admin tab.")
        return

    # ── Player selector ──────────────────────────────────────────────────────
    names = roster["name"].dropna().tolist()
    col_sel, col_log_s, col_log_b = st.columns([2, 1, 1])
    with col_sel:
        sel = st.selectbox("Select Player", names, key="load_player_sel", label_visibility="collapsed")

    player_row = roster[roster["name"] == sel].iloc[0]
    is_fb      = is_fast_bowler(player_row.get("is_fast_bowler"))

    ps = sessions[sessions["player_name"] == sel].copy() if not sessions.empty else pd.DataFrame()
    pb = bowling[bowling["player_name"] == sel].copy()   if not bowling.empty  else pd.DataFrame()

    week_ago  = now_ts - timedelta(days=7)
    month_ago = now_ts - timedelta(days=28)

    # ── Log forms ────────────────────────────────────────────────────────────
    with col_log_s:
        if st.button("+ Log Session", use_container_width=True):
            st.session_state["show_log_session"] = True
    with col_log_b:
        if is_fb:
            if st.button("+ Log Bowling", use_container_width=True):
                st.session_state["show_log_bowling"] = True

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

    if st.session_state.get("show_log_bowling") and is_fb:
        with st.expander("Log Bowling", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1: b_match = st.number_input("Match balls",        0, 500, 0, key="bl_match")
            with c2: b_net   = st.number_input("Net balls",          0, 500, 0, key="bl_net")
            with c3: b_hi    = st.number_input("High intensity balls",0, 500, 0, key="bl_hi")
            b_notes = st.text_input("Notes", key="bl_notes")
            cc1, cc2 = st.columns([1, 4])
            with cc1:
                if st.button("Submit", type="primary", key="bl_submit"):
                    try:
                        r = requests.post(f"{API_URL}/data/bowling", json={
                            "player_name": sel, "match_balls": b_match,
                            "net_balls": b_net, "high_intensity_balls": b_hi, "notes": b_notes,
                        }, timeout=5)
                        r.raise_for_status()
                        load_bowling.clear()
                        st.session_state["show_log_bowling"] = False
                        st.success(f"Bowling logged for {sel}")
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

    if ps.empty:
        st.info(f"No session data for {sel} yet.")
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

    # ════════════════════════════════════════════════════════════════════════
    # BOWLING LOAD SECTION  (fast bowlers only)
    # ════════════════════════════════════════════════════════════════════════
    if not is_fb:
        return

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    st.divider()
    st.markdown("### Bowling Load")

    if pb.empty:
        st.info(f"No bowling data for {sel} yet.")
        return

    pb = pb.assign(
        total_balls=pb[["match_balls","net_balls","high_intensity_balls"]].fillna(0).sum(axis=1)
    )

    pb_week  = pb[pb["timestamp"] >= week_ago]
    pb_month = pb[pb["timestamp"] >= month_ago]

    weekly_balls   = int(pb_week["total_balls"].sum())
    acute_b        = float(pb_week["total_balls"].sum())
    chronic_b      = float(pb_month["total_balls"].sum()) / 4 if len(pb_month) >= 4 else float(pb_month["total_balls"].sum())
    acwr_b         = round(acute_b / chronic_b, 2) if chronic_b > 0 else 0.0
    acwr_b_risk    = "Low" if acwr_b < 1.3 else ("High" if acwr_b > 1.5 else "Moderate")
    acwr_b_color   = {"Low": "#22c55e", "Moderate": "#f59e0b", "High": "#ef4444"}.get(acwr_b_risk, "#6b7a90")

    # Bowling status band from overview thresholds
    bowl_label, bowl_color = bowler_status_band(weekly_balls)

    b1, b2, b3 = st.columns(3)
    with b1: st.markdown(_metric_card("Weekly Balls (7d)", str(weekly_balls), color=bowl_color), unsafe_allow_html=True)
    with b2: st.markdown(_metric_card("4-Week Avg (balls/wk)", str(int(chronic_b)), color="#6b7a90"), unsafe_allow_html=True)
    with b3: st.markdown(_metric_card("Bowling ACWR", str(acwr_b), sub=f"{acwr_b_risk} risk", color=acwr_b_color), unsafe_allow_html=True)

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # ── Stacked bar: balls by type over 4 weeks ──────────────────────────────
    if not pb_month.empty:
        pb_month_copy = pb_month.copy()
        pb_month_copy["week"] = pb_month_copy["timestamp"].dt.to_period("W").astype(str)
        weekly_by_type = pb_month_copy.groupby("week")[["match_balls","net_balls","high_intensity_balls"]].sum().reset_index()

        fig_bowl = go.Figure()
        ball_types = [
            ("match_balls",          "Match",          "#f59e0b"),
            ("net_balls",            "Net",             "#00c2ff"),
            ("high_intensity_balls", "High Intensity",  "#ef4444"),
        ]
        for col, label, color in ball_types:
            if col in weekly_by_type.columns:
                fig_bowl.add_trace(go.Bar(
                    x=weekly_by_type["week"], y=weekly_by_type[col],
                    name=label, marker_color=color,
                    hovertemplate=f"{label}: %{{y}} balls<extra></extra>",
                ))
        fig_bowl.update_layout(
            **{**DARK_LAYOUT, "margin": dict(t=32, b=24, l=8, r=8)},
            height=240, barmode="stack",
            title=dict(text="Weekly Bowling Volume by Type (last 4 weeks)", font=dict(size=13), x=0),
            xaxis=dict(gridcolor="#1f2530", title="Week"),
            yaxis=dict(gridcolor="#1f2530", title="Balls"),
            legend=dict(orientation="h", y=-0.25),
        )
        st.plotly_chart(fig_bowl, use_container_width=True, key=f"bowl_stack_{sel}")

    # ── Recent bowling table ──────────────────────────────────────────────────
    with st.expander("Recent Bowling Sessions", expanded=False):
        display_b = pb.sort_values("timestamp", ascending=False).head(20)[
            ["date","match_balls","net_balls","high_intensity_balls","total_balls","notes"]
        ].rename(columns={
            "date": "Date", "match_balls": "Match", "net_balls": "Net",
            "high_intensity_balls": "High Int.", "total_balls": "Total", "notes": "Notes",
        })
        st.dataframe(display_b, use_container_width=True, height=300)

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
            readiness_sc = int(sleep + energy + (6 - soreness))
            band, band_color = readiness_band(readiness_sc)

            # Readiness score pill
            st.markdown(f"""
            <div style="text-align:center;margin-bottom:16px;">
              <div style="font-size:11px;color:#6b7a90;letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;">
                Readiness Score
              </div>
              <div style="font-size:52px;font-weight:800;color:{band_color};line-height:1;">{readiness_sc}</div>
              <div style="font-size:13px;color:{band_color};margin-top:2px;">{band} &nbsp;/ 15</div>
            </div>
            """, unsafe_allow_html=True)

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
                (6 - trend["body_soreness"].fillna(3))
            )
            trend["date_str"] = trend["date"].astype(str)
            fig_trend = go.Figure()
            metrics = [
                ("sleep_quality", "Sleep",    "#00c2ff"),
                ("energy_level",  "Energy",   "#22c55e"),
                ("body_soreness", "Soreness", "#f59e0b"),
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
            fig_rs.add_hrect(y0=13, y1=15, fillcolor="#22c55e", opacity=0.07, line_width=0)
            fig_rs.add_hrect(y0=10, y1=12, fillcolor="#f59e0b", opacity=0.07, line_width=0)
            fig_rs.add_hrect(y0=0,  y1=9,  fillcolor="#ef4444", opacity=0.07, line_width=0)
            fig_rs.add_trace(go.Scatter(
                x=trend["date_str"], y=trend["readiness"],
                line=dict(color="#00c2ff", width=2),
                mode="lines+markers", marker=dict(size=7),
                name="Readiness",
            ))
            fig_rs.update_layout(
                **{**DARK_LAYOUT, "margin": dict(t=16, b=24, l=8, r=8)},
                height=200,
                yaxis=dict(range=[0, 16], gridcolor="#1f2530",
                           tickvals=[0, 10, 13, 15],
                           ticktext=["0","10 (Yellow)","13 (Green)","15"]),
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
                r = requests.put(f"{API_URL}/data/roster",
                                 json=edited.to_dict(orient="records"), timeout=10)
                r.raise_for_status()
                load_roster.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Failed to save roster: {e}")

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
        "wellness": load_wellness(),
        "sessions": load_sessions(),
        "bowling":  load_bowling(),
        "roster":   current_roster,
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
