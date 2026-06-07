import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime, timedelta, date
import os

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Nalgonda Knights — Dashboard",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "knights2024")
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stSidebar"] { display: none; }
  [data-testid="collapsedControl"] { display: none; }
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
WELLNESS_COLS = ["timestamp","player_name","sleep_quality","energy_level","body_soreness",
                 "mood","stress_level","hamstring_tightness","groin_stiffness","lower_back_stiffness","notes"]
ROSTER_COLS   = ["name","role","type","age","is_fast_bowler","injury_history","current_status","status_notes"]
SESSIONS_COLS = ["timestamp","player_name","session_type","duration_mins","rpe","notes"]
BOWLING_COLS  = ["timestamp","player_name","match_balls","net_balls","high_intensity_balls","notes"]

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
def ensure_csv(path: Path, columns: list):
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)

def save_row(path: Path, columns: list, row: dict):
    ensure_csv(path, columns)
    df = pd.read_csv(path)
    new = pd.DataFrame([{c: row.get(c) for c in columns}])
    pd.concat([df, new], ignore_index=True).to_csv(path, index=False)

@st.cache_data(ttl=30)
def load_wellness() -> pd.DataFrame:
    p = DATA_DIR / "wellness.csv"
    ensure_csv(p, WELLNESS_COLS)
    df = pd.read_csv(p)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["timestamp"].dt.date
    return df

@st.cache_data(ttl=30)
def load_roster() -> pd.DataFrame:
    p = DATA_DIR / "roster.csv"
    ensure_csv(p, ROSTER_COLS)
    return pd.read_csv(p)

@st.cache_data(ttl=30)
def load_sessions() -> pd.DataFrame:
    p = DATA_DIR / "sessions.csv"
    ensure_csv(p, SESSIONS_COLS)
    df = pd.read_csv(p)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["timestamp"].dt.date
        df["load_au"] = df["duration_mins"] * df["rpe"]
    return df

@st.cache_data(ttl=30)
def load_bowling() -> pd.DataFrame:
    p = DATA_DIR / "bowling.csv"
    ensure_csv(p, BOWLING_COLS)
    df = pd.read_csv(p)
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

# ── Load data ────────────────────────────────────────────────────────────────
wellness = load_wellness()
roster   = load_roster()
sessions = load_sessions()
bowling  = load_bowling()
today    = date.today()

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_overview, tab_wellness, tab_sessions, tab_bowling, tab_squad, tab_admin = st.tabs([
    "Overview", "Wellness", "Session Load", "Bowling Load", "Squad", "Admin",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
with tab_overview:
    # Squad status bar
    status_counts = {}
    if not roster.empty and "current_status" in roster.columns:
        status_counts = roster["current_status"].value_counts().to_dict()

    cols = st.columns(len(STATUS_COLORS))
    for i, (label, color) in enumerate(STATUS_COLORS.items()):
        count = status_counts.get(label, 0)
        with cols[i]:
            st.markdown(f"""
            <div class="metric-card" style="border-top: 2px solid {color};">
              <div class="metric-label">{label}</div>
              <div class="metric-value" style="color:{color};">{count}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    col_heat, col_right = st.columns([3, 1])

    with col_heat:
        st.markdown("**7-Day Wellness Heatmap**")
        METRIC_COLS = ["sleep_quality","energy_level","body_soreness","mood","stress_level"]

        if not wellness.empty:
            cutoff = pd.Timestamp(today) - timedelta(days=6)
            df7 = wellness[wellness["timestamp"] >= cutoff].copy()
            if not df7.empty:
                # Composite score: invert soreness and stress (high = bad)
                df7["wellness_score"] = (
                    df7["sleep_quality"].fillna(3) +
                    df7["energy_level"].fillna(3) +
                    (6 - df7["body_soreness"].fillna(3)) +
                    df7["mood"].fillna(3) +
                    (6 - df7["stress_level"].fillna(3))
                ) / 5

                latest = df7.sort_values("timestamp").groupby(["player_name","date"]).last().reset_index()
                pivot = latest.pivot_table(index="player_name", columns="date",
                                           values="wellness_score", aggfunc="mean")
                pivot.columns = [str(c) for c in pivot.columns]

                fig = px.imshow(
                    pivot,
                    color_continuous_scale=[[0,"#ef4444"],[0.4,"#f59e0b"],[0.7,"#22c55e"],[1,"#22c55e"]],
                    zmin=1, zmax=5,
                    text_auto=".1f",
                    aspect="auto",
                )
                fig.update_layout(**DARK_LAYOUT, height=280, coloraxis_showscale=False)
                fig.update_xaxes(title="", tickfont=dict(size=11), gridcolor="#1f2530")
                fig.update_yaxes(title="", tickfont=dict(size=11), gridcolor="#1f2530")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data in the last 7 days.")
        else:
            st.info("No wellness submissions yet.")

    with col_right:
        # Alerts
        st.markdown("**Alerts**")
        if not wellness.empty:
            today_df = wellness[wellness["date"] == today]
            alerts = []
            for _, r in today_df.iterrows():
                issues = []
                if r.get("sleep_quality", 5) <= 2:   issues.append("Low sleep")
                if r.get("energy_level", 5) <= 2:    issues.append("Low energy")
                if r.get("body_soreness", 1) >= 4:   issues.append("High soreness")
                if r.get("stress_level", 1) >= 4:    issues.append("High stress")
                if pd.notna(r.get("hamstring_tightness")) and r["hamstring_tightness"] >= 4:
                    issues.append("Hamstring ⚠")
                if pd.notna(r.get("groin_stiffness")) and r["groin_stiffness"] >= 4:
                    issues.append("Groin ⚠")
                if pd.notna(r.get("lower_back_stiffness")) and r["lower_back_stiffness"] >= 4:
                    issues.append("Lower back ⚠")
                if issues:
                    alerts.append({"player": r["player_name"], "issues": issues})

            if alerts:
                for a in alerts:
                    st.markdown(f"""
                    <div class="alert-item">
                      <div class="alert-name">{a['player']}</div>
                      <div class="alert-tags">{' · '.join(a['issues'])}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.success("No alerts today")

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        st.markdown("**Today's Check-ins**")

        if not roster.empty:
            submitted = set()
            if not wellness.empty:
                submitted = set(wellness[wellness["date"] == today]["player_name"].tolist())
            total = len(roster)
            pct = int(len(submitted) / total * 100) if total else 0
            st.metric("Submitted", f"{len(submitted)} / {total}", f"{pct}%")

            missing = [n for n in roster["name"].tolist() if n not in submitted]
            if missing:
                with st.expander(f"Missing ({len(missing)})"):
                    for name in missing:
                        st.markdown(f"- {name}")

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — WELLNESS
# ════════════════════════════════════════════════════════════════════════════
with tab_wellness:
    st.subheader("Wellness Submissions")

    if wellness.empty:
        st.info("No wellness data yet. Share the check-in form with your players.")
    else:
        c1, c2 = st.columns([1, 2])
        with c1:
            player_opts = ["All"] + sorted(wellness["player_name"].dropna().unique().tolist())
            sel_player = st.selectbox("Player", player_opts, key="w_player")
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

        display = df_w[["date","player_name","sleep_quality","energy_level","body_soreness",
                         "mood","stress_level","notes"]].rename(columns={
            "player_name": "Player", "sleep_quality": "Sleep", "energy_level": "Energy",
            "body_soreness": "Soreness", "mood": "Mood", "stress_level": "Stress",
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

        styled = display.style \
            .applymap(lambda v: score_bg(v, inverse=False), subset=["Sleep","Energy","Mood"]) \
            .applymap(lambda v: score_bg(v, inverse=True),  subset=["Soreness","Stress"])

        st.dataframe(styled, use_container_width=True, height=480)

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — SESSION LOAD
# ════════════════════════════════════════════════════════════════════════════
with tab_sessions:
    st.subheader("Session RPE Load")

    # Manual entry form
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
            save_row(DATA_DIR / "sessions.csv", SESSIONS_COLS, {
                "timestamp": datetime.now().isoformat(),
                "player_name": s_player, "session_type": s_type,
                "duration_mins": s_dur, "rpe": s_rpe, "notes": s_notes,
            })
            st.success(f"Session logged for {s_player}")
            st.cache_data.clear()
            st.rerun()

    if not sessions.empty:
        cutoff = pd.Timestamp(today - timedelta(days=28))
        df_s = sessions[sessions["timestamp"] >= cutoff].copy()

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

        # ACWR table for fast bowlers
        bowlers = fast_bowlers(roster)
        if bowlers:
            st.markdown("**ACWR — Fast Bowlers**")
            now = pd.Timestamp(today)
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
                st.dataframe(
                    df_acwr.style.applymap(risk_color, subset=["Risk"]),
                    use_container_width=True,
                )
    else:
        st.info("No session data yet. Use the form above to log sessions.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — BOWLING LOAD
# ════════════════════════════════════════════════════════════════════════════
with tab_bowling:
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
            save_row(DATA_DIR / "bowling.csv", BOWLING_COLS, {
                "timestamp": datetime.now().isoformat(),
                "player_name": b_player, "match_balls": b_match,
                "net_balls": b_net, "high_intensity_balls": b_hi, "notes": b_notes,
            })
            st.success(f"Bowling session logged for {b_player}")
            st.cache_data.clear()
            st.rerun()

    if not bowling.empty:
        df_b = bowling.copy()
        df_b["total_balls"] = df_b[["match_balls","net_balls","high_intensity_balls"]].fillna(0).sum(axis=1)

        # Rolling 7-day total per bowler
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

# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — SQUAD
# ════════════════════════════════════════════════════════════════════════════
with tab_squad:
    st.subheader("Squad")

    if roster.empty:
        st.info("No players yet — add them in the Admin tab.")
    else:
        for _, player in roster.iterrows():
            status = player.get("current_status", "Unknown")
            color  = STATUS_COLORS.get(status, "#6b7a90")
            label  = f"**{player['name']}** &nbsp; `{player.get('role','?')}` &nbsp; <span style='color:{color}'>{status}</span>"

            with st.expander(f"{player['name']}  —  {player.get('role','?')}  |  {status}"):
                c_info, c_radar = st.columns([1, 2])

                with c_info:
                    st.markdown(f"**Role:** {player.get('role','—')}")
                    st.markdown(f"**Type:** {player.get('type','—')}")
                    st.markdown(f"**Age:** {player.get('age','—')}")
                    st.markdown(f"**Fast bowler:** {'Yes' if is_fast_bowler(player.get('is_fast_bowler')) else 'No'}")
                    ih = player.get("injury_history")
                    if pd.notna(ih) and ih:
                        st.markdown(f"**Injury history:** {ih}")
                    sn = player.get("status_notes")
                    if pd.notna(sn) and sn:
                        st.markdown(f"**Notes:** {sn}")

                with c_radar:
                    if not wellness.empty:
                        pw = wellness[wellness["player_name"] == player["name"]].sort_values("timestamp")
                        if not pw.empty:
                            last = pw.iloc[-1]
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
                            st.plotly_chart(fig, use_container_width=True)
                            st.caption(f"Last submission: {last['date']}")
                        else:
                            st.info("No wellness data for this player.")
                    else:
                        st.info("No wellness data yet.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 6 — ADMIN
# ════════════════════════════════════════════════════════════════════════════
with tab_admin:
    st.subheader("Roster Management")
    st.caption("Edit directly in the table. Add rows with the + button. Save when done.")

    edited = st.data_editor(
        roster,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "name":           st.column_config.TextColumn("Name", required=True),
            "role":           st.column_config.SelectboxColumn("Role",
                                options=["Batsman","Bowler","All-rounder","Wicket-keeper"]),
            "type":           st.column_config.TextColumn("Playing Type", help="e.g. Right-arm fast, Left-hand bat"),
            "age":            st.column_config.NumberColumn("Age", min_value=10, max_value=60, step=1),
            "is_fast_bowler": st.column_config.CheckboxColumn("Fast Bowler?"),
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
            edited.to_csv(DATA_DIR / "roster.csv", index=False)
            st.success("Roster saved!")
            load_roster.clear()
            st.rerun()

    st.divider()
    st.subheader("Export Data")
    c1, c2, c3, c4 = st.columns(4)
    dfs = {"wellness": wellness, "sessions": sessions, "bowling": bowling, "roster": roster}
    for col, (name, df) in zip([c1, c2, c3, c4], dfs.items()):
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
