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
tab_overview, tab_wellness, tab_sessions, tab_bowling, tab_squad, tab_admin = st.tabs([
    "Overview", "Wellness", "Session Load", "Bowling Load", "Squad", "Admin",
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
@st.fragment
def render_wellness():
    wellness = load_wellness()
    today    = date.today()
    st.subheader("Wellness Submissions")

    # Interpretation legend
    legend_html = " &nbsp;·&nbsp; ".join(
        f'<span style="color:{color};">● {lo:.1f}–{hi:.1f} {label}</span>'
        if lo > 0 else
        f'<span style="color:{color};">● &lt;{hi+0.1:.1f} {label}</span>'
        for lo, hi, label, color in WELLNESS_INTERP
    )
    st.markdown(
        f'<div style="font-size:12px;margin-bottom:12px;">{legend_html}</div>',
        unsafe_allow_html=True,
    )

    if wellness.empty:
        st.info("No wellness data yet. Share the check-in form with your players.")
        return

    c1, c2 = st.columns([1, 2])
    with c1:
        player_opts = ["All"] + sorted(wellness["player_name"].dropna().unique().tolist())
        sel_player  = st.selectbox("Player", player_opts, key="w_player")
    with c2:
        date_range = st.date_input(
            "Date range",
            value=(today - timedelta(days=14), today),
            key="w_dates",
        )

    df_w = wellness.copy()
    if sel_player != "All":
        df_w = df_w[df_w["player_name"] == sel_player]
    if isinstance(date_range, tuple) and len(date_range) == 2:
        df_w = df_w[(df_w["date"] >= date_range[0]) & (df_w["date"] <= date_range[1])]
    df_w = df_w.sort_values("timestamp", ascending=False)

    keep_cols = ["date","player_name","sleep_quality","energy_level","body_soreness",
                 "tightness_locations","availability_status","notes"]
    display = df_w[[c for c in keep_cols if c in df_w.columns]].rename(columns={
        "player_name": "Player", "sleep_quality": "Sleep", "energy_level": "Energy",
        "body_soreness": "Soreness", "tightness_locations": "Tightness",
        "availability_status": "Availability",
    })

    def score_bg(val, inverse=False):
        try:
            v = int(val)
            if inverse:
                if v >= 4: return "background-color: rgba(239,68,68,0.25)"
                if v <= 2: return "background-color: rgba(34,197,94,0.25)"
            else:
                if v >= 4: return "background-color: rgba(34,197,94,0.25)"
                if v <= 2: return "background-color: rgba(239,68,68,0.25)"
            return "background-color: rgba(245,158,11,0.25)"
        except Exception:
            return ""

    num_cols = [c for c in ["Sleep","Energy","Soreness"] if c in display.columns]
    styled = display.style
    if "Sleep" in display.columns or "Energy" in display.columns:
        pos_cols = [c for c in ["Sleep","Energy"] if c in display.columns]
        if pos_cols:
            styled = styled.applymap(lambda v: score_bg(v, inverse=False), subset=pos_cols)
    if "Soreness" in display.columns:
        styled = styled.applymap(lambda v: score_bg(v, inverse=True), subset=["Soreness"])
    st.dataframe(styled, use_container_width=True, height=480)

with tab_wellness:
    render_wellness()

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — SESSION LOAD
# ════════════════════════════════════════════════════════════════════════════
@st.fragment
def render_sessions():
    roster   = load_roster()
    sessions = load_sessions()
    today    = date.today()
    st.subheader("Session RPE Load")

    rpe_html = " &nbsp;·&nbsp; ".join(
        f'<span style="color:{color};">{lo}{"–"+str(hi) if hi!=lo else ""} {label}</span>'
        for (lo, hi), (label, color) in RPE_LABELS.items()
    )
    st.markdown(
        f'<div style="font-size:12px;margin-bottom:12px;">{rpe_html}</div>',
        unsafe_allow_html=True,
    )

    with st.expander("+ Log Session", expanded=sessions.empty):
        c1, c2, c3, c4 = st.columns(4)
        player_list = roster["name"].tolist() if not roster.empty else []
        with c1:
            s_player = st.selectbox("Player", player_list, key="s_player")
        with c2:
            s_type = st.selectbox("Session Type", ["Training","Match","Gym","Recovery","Rehab"], key="s_type")
        with c3:
            s_dur = st.number_input("Duration (mins)", 1, 300, 60, key="s_dur")
        with c4:
            s_rpe = st.slider("RPE (1–10)", 1, 10, 6, key="s_rpe")
        s_notes = st.text_input("Notes", key="s_notes")
        if st.button("Log Session", type="primary"):
            try:
                r = requests.post(f"{API_URL}/data/sessions", json={
                    "player_name": s_player, "session_type": s_type,
                    "duration_mins": s_dur, "rpe": s_rpe, "notes": s_notes,
                }, timeout=5)
                r.raise_for_status()
                load_sessions.clear()
                st.success(f"Session logged for {s_player}")
                sessions = load_sessions()
            except Exception as e:
                st.error(f"Failed to log session: {e}")

    if not sessions.empty:
        cutoff = pd.Timestamp(today - timedelta(days=28))
        df_s   = sessions[sessions["timestamp"] >= cutoff].copy()
        if not df_s.empty:
            daily = df_s.groupby("date")["load_au"].mean().reset_index()
            daily.columns = ["date", "avg_load"]
            fig = px.bar(
                daily, x="date", y="avg_load",
                labels={"date": "Date", "avg_load": "Team Avg Load (AU)"},
                color="avg_load",
                color_continuous_scale=[[0,"#22c55e"],[0.55,"#f59e0b"],[1,"#ef4444"]],
            )
            fig.update_layout(**DARK_LAYOUT, height=280, coloraxis_showscale=False)
            fig.update_xaxes(gridcolor="#1f2530")
            fig.update_yaxes(gridcolor="#1f2530")
            st.plotly_chart(fig, use_container_width=True)

        bowlers = fast_bowlers(roster)
        if bowlers:
            st.markdown("**ACWR — Fast Bowlers**")
            now       = pd.Timestamp(today)
            acwr_rows = []
            for player in bowlers:
                ps = sessions[sessions["player_name"] == player]
                if ps.empty:
                    continue
                acute   = ps[ps["timestamp"] >= now - timedelta(days=7)]["load_au"].sum()
                chronic = ps[ps["timestamp"] >= now - timedelta(days=28)]["load_au"].sum() / 4
                acwr    = round(acute / chronic, 2) if chronic > 0 else 0.0
                risk    = "Low" if acwr < 1.3 else ("High" if acwr > 1.5 else "Moderate")
                acwr_rows.append({
                    "Player": player, "Acute 7d (AU)": int(acute),
                    "Chronic avg (AU)": int(chronic), "ACWR": acwr, "Risk": risk,
                })
            if acwr_rows:
                df_acwr = pd.DataFrame(acwr_rows)
                def risk_color(val):
                    return {"Low":"color:#22c55e","Moderate":"color:#f59e0b","High":"color:#ef4444"}.get(val,"")
                st.dataframe(df_acwr.style.applymap(risk_color, subset=["Risk"]), use_container_width=True)
    else:
        st.info("No session data yet. Use the form above to log sessions.")

with tab_sessions:
    render_sessions()

# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — BOWLING LOAD
# ════════════════════════════════════════════════════════════════════════════
@st.fragment
def render_bowling():
    roster  = load_roster()
    bowling = load_bowling()
    today   = date.today()
    st.subheader("Bowling Load — Fast Bowlers")

    bowlers = fast_bowlers(roster)

    with st.expander("+ Log Bowling Session", expanded=bowling.empty):
        c1, c2, c3, c4 = st.columns(4)
        bowl_opts = bowlers if bowlers else (roster["name"].tolist() if not roster.empty else [])
        with c1:
            b_player = st.selectbox("Bowler", bowl_opts, key="b_player")
        with c2:
            b_match = st.number_input("Match balls", 0, 500, 0, key="b_match")
        with c3:
            b_net = st.number_input("Net balls", 0, 500, 0, key="b_net")
        with c4:
            b_hi = st.number_input("High intensity", 0, 500, 0, key="b_hi")
        b_notes = st.text_input("Notes", key="b_notes")
        if st.button("Log Bowling", type="primary"):
            try:
                r = requests.post(f"{API_URL}/data/bowling", json={
                    "player_name": b_player, "match_balls": b_match,
                    "net_balls": b_net, "high_intensity_balls": b_hi, "notes": b_notes,
                }, timeout=5)
                r.raise_for_status()
                load_bowling.clear()
                st.success(f"Bowling session logged for {b_player}")
                bowling = load_bowling()
            except Exception as e:
                st.error(f"Failed to log bowling: {e}")

    if not bowling.empty:
        df_b = bowling.copy()
        df_b = df_b.assign(total_balls=df_b[["match_balls","net_balls","high_intensity_balls"]].fillna(0).sum(axis=1))
        if bowlers:
            cutoff = pd.Timestamp(today - timedelta(days=7))
            recent = df_b[df_b["timestamp"] >= cutoff].groupby("player_name")["total_balls"].sum().reset_index()
            recent.columns = ["Player", "Total balls (7d)"]
            fig = px.bar(
                recent, x="Player", y="Total balls (7d)",
                color="Total balls (7d)",
                color_continuous_scale=[[0,"#22c55e"],[0.6,"#f59e0b"],[1,"#ef4444"]],
            )
            fig.update_layout(**DARK_LAYOUT, height=260, coloraxis_showscale=False, showlegend=False)
            fig.update_xaxes(gridcolor="#1f2530")
            fig.update_yaxes(gridcolor="#1f2530")
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(
            df_b[["date","player_name","match_balls","net_balls","high_intensity_balls","total_balls","notes"]]
              .sort_values("date", ascending=False)
              .rename(columns={"player_name":"Player","match_balls":"Match","net_balls":"Net",
                               "high_intensity_balls":"High Int.","total_balls":"Total","notes":"Notes"}),
            use_container_width=True, height=380,
        )
    else:
        st.info("No bowling data yet.")

with tab_bowling:
    render_bowling()

# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — SQUAD
# ════════════════════════════════════════════════════════════════════════════
@st.fragment
def render_squad():
    roster   = load_roster()
    wellness = load_wellness()
    st.subheader("Squad")

    if roster.empty:
        st.info("No players yet — add them in the Admin tab.")
        return

    for _, player in roster.iterrows():
        status = player.get("current_status", "Unknown")
        color  = STATUS_COLORS.get(status, "#6b7a90")
        role   = player.get("role", "?")
        with st.expander(f"{player['name']}  —  {role}  |  {status}"):
            c_info, c_radar = st.columns([1, 2])
            with c_info:
                age_val = player.get('age')
                age_str = str(int(age_val)) if pd.notna(age_val) and age_val != '' else '—'

                def _f(val): return str(val) if pd.notna(val) and str(val).strip() else "—"

                st.markdown(f"**Name:** {_f(player.get('name'))}")
                st.markdown(f"**Age:** {age_str}")
                st.markdown(f"**Role:** {_f(player.get('role'))}")
                st.markdown(f"**Batting Style:** {_f(player.get('batting_style'))}")
                st.markdown(f"**Bowling Style:** {_f(player.get('bowling_style'))}")
                st.markdown(f"**Dominant Side:** {_f(player.get('dominant_side'))}")
                st.markdown(f"**Fast Bowler:** {'Yes' if is_fast_bowler(player.get('is_fast_bowler')) else 'No'}")
                st.markdown(f"**Contact:** {_f(player.get('contact'))}")
                ih = player.get("injury_history")
                if pd.notna(ih) and str(ih).strip():
                    st.markdown(f"**Injury History:** {ih}")
                sn = player.get("status_notes")
                if pd.notna(sn) and str(sn).strip():
                    st.markdown(f"**Status Notes:** {sn}")

                # Latest player-reported availability from morning checkin
                if not wellness.empty:
                    pw = wellness[wellness["player_name"] == player["name"]].sort_values("timestamp")
                    if not pw.empty:
                        last_avail = pw.iloc[-1].get("availability_status", "")
                        if last_avail and pd.notna(last_avail):
                            st.markdown(f"**Self-reported:** {last_avail}")
            with c_radar:
                if not wellness.empty:
                    pw = wellness[wellness["player_name"] == player["name"]].sort_values("timestamp")
                    if not pw.empty:
                        last     = pw.iloc[-1]
                        r_labels = ["Sleep","Energy","Soreness*","Mood","Stress*"]
                        r_vals   = [
                            float(last.get("sleep_quality", 3) or 3),
                            float(last.get("energy_level",  3) or 3),
                            float(last.get("body_soreness", 3) or 3),
                            float(last.get("mood",          3) or 3),
                            float(last.get("stress_level",  3) or 3),
                        ]
                        fig = go.Figure(go.Scatterpolar(
                            r=r_vals + [r_vals[0]],
                            theta=r_labels + [r_labels[0]],
                            fill="toself",
                            fillcolor="rgba(0,194,255,0.12)",
                            line=dict(color="#00c2ff", width=2),
                        ))
                        fig.update_layout(
                            polar=dict(
                                radialaxis=dict(visible=True, range=[0,5], color="#6b7a90", tickfont=dict(size=9)),
                                angularaxis=dict(color="#6b7a90"),
                                bgcolor="#111318",
                            ),
                            paper_bgcolor="#161a22",
                            font=dict(color="#e8edf5"),
                            height=240, margin=dict(t=16, b=16, l=16, r=16),
                            showlegend=False,
                        )
                        st.plotly_chart(fig, use_container_width=True, key=f"radar_{player['name']}")
                        st.caption(f"Last submission: {last['date']}")
                    else:
                        st.info("No wellness data for this player.")
                else:
                    st.info("No wellness data yet.")

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
        base_url = API_URL.rstrip("/")
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
