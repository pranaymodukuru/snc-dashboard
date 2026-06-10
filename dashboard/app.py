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
    "tightness_locations","availability_status","notes",
    "mood","stress","sleep_hours","is_sick",
    "stress_level","hamstring_tightness","groin_stiffness","lower_back_stiffness",
]
ROSTER_COLS   = [
    "name","role","batting_style","bowling_style","dominant_side",
    "type","age","is_fast_bowler","contact",
    "injury_history","current_status","status_notes",
]
SESSIONS_COLS = ["timestamp","player_name","session_type","duration_mins","rpe","notes"]
EVENING_COLS  = ["timestamp","player_name","session_rpe","did_bowl","bowling_volume","bowling_intensity","did_bat","balls_faced"]

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
    records = _api_get("/data/evening")
    df = pd.DataFrame(records) if records else pd.DataFrame(columns=EVENING_COLS)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["timestamp"].dt.date
    return df


@st.cache_data(ttl=30)
def load_sessions() -> pd.DataFrame:
    records = _api_get("/data/sessions")
    df = pd.DataFrame(records) if records else pd.DataFrame(columns=SESSIONS_COLS)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
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
    ("Green",  "#22c55e", 13, 15),
    ("Yellow", "#f59e0b", 10, 12),
    ("Red",    "#ef4444",  0,  9),
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


@st.fragment
def render_overview():
    roster   = load_roster()
    wellness = load_wellness()
    evening  = load_evening()
    today    = date.today()

    col_left, col_right = st.columns([1, 1], gap="large")

    # ── LEFT COLUMN ──────────────────────────────────────────────────────────
    with col_left:

        # ── Team Availability ────────────────────────────────────────────────
        st.markdown("### Team Availability")

        avail_map = {
            "Available":       ("#22c55e", ["Available"]),
            "Modified Training": ("#00c2ff", ["Modified Training"]),
            "Recovery Only":   ("#f59e0b", ["Recovery Only"]),
            "Rehab":           ("#f97316", ["Rehab"]),
            "Unavailable":     ("#ef4444", ["Unavailable"]),
            "Not Submitted":   ("#6b7a90", []),
        }

        avail_counts = {k: 0 for k in avail_map}
        total_players = len(roster) if not roster.empty else 0

        if not wellness.empty and "date" in wellness.columns:
            today_w = wellness[wellness["date"] == today]
            if not today_w.empty:
                latest = today_w.sort_values("timestamp").groupby("player_name").last()
                sc = latest["availability_status"].fillna("Available").value_counts().to_dict()
                for label, (color, statuses) in avail_map.items():
                    avail_counts[label] = sum(sc.get(s, 0) for s in statuses)
                submitted_count = sum(avail_counts[l] for l in avail_map if l != "Not Submitted")
                avail_counts["Not Submitted"] = max(0, total_players - submitted_count)
            else:
                avail_counts["Not Submitted"] = total_players
        else:
            avail_counts["Not Submitted"] = total_players

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

            INTENSITY_COLOR = {"Low": "#22c55e", "Moderate": "#f59e0b", "High": "#ef4444"}

            rows = []
            for name in display_bowlers:
                bowling_days = 0
                dominant_intensity = "—"
                intensity_color = "#6b7a90"
                if not evening.empty:
                    pe = evening[
                        (evening["player_name"] == name) &
                        (evening["timestamp"] >= cutoff_week) &
                        (evening["did_bowl"].astype(str).str.lower().isin(["true", "1", "yes"]))
                    ]
                    if not pe.empty:
                        bowling_days = len(pe["date"].unique())
                        intensities = pe["bowling_intensity"].dropna()
                        if not intensities.empty:
                            dominant_intensity = intensities.mode().iloc[0]
                            intensity_color = INTENSITY_COLOR.get(dominant_intensity, "#6b7a90")
                rows.append({
                    "Name": name,
                    "Bowling Days": bowling_days,
                    "_intensity": dominant_intensity,
                    "_color": intensity_color,
                })

            for r in rows:
                col_n, col_b, col_s = st.columns([2, 1, 1])
                with col_n:
                    st.markdown(f"<span style='font-size:14px;'>{r['Name']}</span>", unsafe_allow_html=True)
                with col_b:
                    st.markdown(f"<span style='font-size:14px;font-weight:600;'>{r['Bowling Days']}d</span>", unsafe_allow_html=True)
                with col_s:
                    st.markdown(f"""
                    <span style="background:{r['_color']}22;color:{r['_color']};
                                 border:1px solid {r['_color']}55;border-radius:4px;
                                 padding:2px 10px;font-size:12px;font-weight:600;">
                      {r['_intensity']}
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
                if str(row.get("is_sick", "")).lower() in ("true", "1", "yes"):
                    flags.append("Sick today")
                if row.get("sleep_quality", 5) <= 2:
                    flags.append("Low sleep quality")
                if row.get("energy_level", 5) <= 2:
                    flags.append("Low energy")
                if row.get("body_soreness", 1) >= 4:
                    flags.append("High soreness")
                try:
                    if float(row.get("mood") or 5) <= 2:
                        flags.append("Low mood")
                except (TypeError, ValueError):
                    pass
                try:
                    if float(row.get("stress") or 1) >= 4:
                        flags.append("High stress")
                except (TypeError, ValueError):
                    pass
                try:
                    if float(row.get("sleep_hours") or 8) < 6:
                        flags.append(f"Low sleep ({row.get('sleep_hours')}h)")
                except (TypeError, ValueError):
                    pass
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

        # ── Check-in Completion ───────────────────────────────────────────────
        total = len(roster) if not roster.empty else 0
        roster_names = roster["name"].tolist() if not roster.empty else []

        morning_submitted = set()
        if not wellness.empty:
            morning_submitted = set(wellness[wellness["date"] == today]["player_name"].tolist())

        evening_submitted = set()
        if not evening.empty and "date" in evening.columns:
            evening_submitted = set(evening[evening["date"] == today]["player_name"].tolist())

        checkin_col1, checkin_col2 = st.columns(2)

        with checkin_col1:
            st.markdown("### Morning Check-in Submitted")
            st.markdown(f"""
            <div style="font-size:32px;font-weight:800;color:#e8edf5;margin:8px 0;">
              {len(morning_submitted)}
              <span style="font-size:18px;color:#6b7a90;">/ {total} players</span>
            </div>
            """, unsafe_allow_html=True)
            missing_morning = [n for n in roster_names if n not in morning_submitted]
            if missing_morning:
                with st.expander(f"Not submitted ({len(missing_morning)})"):
                    for name in missing_morning:
                        st.markdown(f"- {name}")

        with checkin_col2:
            st.markdown("### Evening Check-in Submitted")
            st.markdown(f"""
            <div style="font-size:32px;font-weight:800;color:#e8edf5;margin:8px 0;">
              {len(evening_submitted)}
              <span style="font-size:18px;color:#6b7a90;">/ {total} players</span>
            </div>
            """, unsafe_allow_html=True)
            missing_evening = [n for n in roster_names if n not in evening_submitted]
            if missing_evening:
                with st.expander(f"Not submitted ({len(missing_evening)})"):
                    for name in missing_evening:
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
                    "tightness_locations","availability_status","notes"]
            df_w = df_w_full[[c for c in keep if c in df_w_full.columns]].rename(columns={
                "player_name":"Player","sleep_quality":"Sleep","energy_level":"Energy",
                "body_soreness":"Soreness","mood":"Mood","stress":"Stress",
                "sleep_hours":"Sleep Hrs","is_sick":"Sick",
                "tightness_locations":"Tightness","availability_status":"Availability",
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
            c1, c2 = st.columns([1, 5])
            with c1:
                _export_btn(df_w, "morning_checkins")
            with c2:
                sel_idx = sel_w.selection.rows
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
            keep_e = ["date","player_name","session_rpe","did_bowl","bowling_volume","bowling_intensity","did_bat","balls_faced"]
            df_e_display = df_e_full[[c for c in keep_e if c in df_e_full.columns]].rename(columns={
                "player_name":"Player","session_rpe":"RPE","did_bowl":"Bowled",
                "bowling_volume":"Bowl Vol","bowling_intensity":"Bowl Int",
                "did_bat":"Batted","balls_faced":"Balls Faced",
            })
            sel_e = st.dataframe(df_e_display, use_container_width=True, height=320,
                                 selection_mode="multi-row", on_select="rerun",
                                 key="raw_evening")
            c1, c2 = st.columns([1, 5])
            with c1:
                _export_btn(df_e_full, "evening_checkins")
            with c2:
                sel_idx = sel_e.selection.rows
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
            c1, c2 = st.columns([1, 5])
            with c1:
                _export_btn(df_s_full, "sessions")
            with c2:
                sel_idx = sel_s.selection.rows
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
                c1, c2 = st.columns([1, 5])
                with c1:
                    _export_btn(df_bowl_full, "bowling_checkins")
                with c2:
                    sel_idx = sel_b.selection.rows
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
            c1, c2 = st.columns([1, 5])
            with c1:
                _export_btn(roster_display, "roster")
            with c2:
                sel_idx = sel_r.selection.rows
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
                (6 - trend["body_soreness"].fillna(3))
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
                                 json=edited.where(edited.notna(), other=None).to_dict(orient="records"), timeout=10)
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
