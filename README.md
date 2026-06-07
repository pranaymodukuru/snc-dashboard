# Nalgonda Knights — S&C Dashboard

A cricket team strength & conditioning dashboard built with FastAPI + Streamlit, deployed on Railway.

---

## Architecture

```
api/                     FastAPI — serves player check-in form, saves submissions to CSV
  main.py
  templates/
    checkin.html         Player check-in (open, no login required)
  requirements.txt
  Dockerfile

dashboard/               Streamlit — coach dashboard (password protected)
  app.py
  .streamlit/
    config.toml
  requirements.txt
  Dockerfile

data/                    CSV files (local dev only — Railway uses a Volume)
  wellness.csv
  sessions.csv
  bowling.csv
  roster.csv

.env.example             Copy to .env for local dev
```

**Data flow:**
```
Player opens /checkin (FastAPI)
        ↓
Selects name → fills in sliders → submits
        ↓
POST /submit/wellness → appended to /data/wellness.csv
        ↓
Coach opens Streamlit dashboard (password protected)
        ↓
Reads CSVs from shared /data volume → renders charts
```

**Two URLs in production:**
- `https://your-api.railway.app/checkin` → player check-in (send this to players)
- `https://your-dashboard.railway.app` → coach dashboard (password protected)

---

## Local Development

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Two terminal windows (one for each service)

### Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/snc-dashboard.git
cd snc-dashboard

# Create venv and install all dependencies (run once)
uv sync

# Copy env file
cp .env.example .env
# Edit .env and set DASHBOARD_PASSWORD to whatever you want
```

### Run the API (check-in form)

```bash
uv run uvicorn api.main:app --reload --port 8000
```

Check-in form available at: http://localhost:8000/checkin

### Run the Dashboard

```bash
uv run streamlit run dashboard/app.py
```

Dashboard available at: http://localhost:8501

> The `DATA_DIR=../data` prefix tells both services to share the same `data/` folder at the repo root.
> The folder is created automatically on first run.

### First run

1. Open the dashboard at http://localhost:8501
2. Log in with the password you set in `.env`
3. Go to the **Admin** tab → add your players → click **Save Roster**
4. Open the check-in form at http://localhost:8000/checkin — your players will now appear

---

## Deploying to Railway

Railway runs both services as separate containers that share a persistent Volume for CSV storage.

### Step 1 — Push code to GitHub

```bash
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOUR_USERNAME/snc-dashboard.git
git push -u origin main
```

### Step 2 — Create a Railway project

1. Go to [railway.app](https://railway.app) and sign in with GitHub
2. Click **New Project → Deploy from GitHub repo**
3. Select your `snc-dashboard` repository

### Step 3 — Configure the API service

Railway will create one service by default. Configure it as the API:

1. Click on the service → **Settings**
2. Leave **Root Directory** blank (build context is the repo root)
3. Set **Dockerfile Path** to `api/Dockerfile`
4. Under **Networking → Expose port**: set to `8000`
5. Click **Generate Domain** to get a public URL (this is your `/checkin` URL)

### Step 4 — Add the Dashboard service

1. In your Railway project → click **New → GitHub Repo** (same repo)
2. Click on the new service → **Settings**
3. Leave **Root Directory** blank (build context is the repo root)
4. Set **Dockerfile Path** to `dashboard/Dockerfile`
5. Under **Networking → Expose port**: set to `8501`
6. Click **Generate Domain** to get a public URL (this is your dashboard URL)

### Step 5 — Create a shared Volume

Both services need to read/write the same CSV files.

1. In your Railway project → click **New → Volume**
2. Name it `snc-data`
3. **Attach it to the API service**:
   - Click the API service → **Volumes** tab
   - Select `snc-data` → Mount path: `/data`
4. **Attach it to the Dashboard service**:
   - Click the dashboard service → **Volumes** tab
   - Select `snc-data` → Mount path: `/data`

### Step 6 — Set environment variables

Set these on **both** services (API and Dashboard):

| Variable | Value | Notes |
|----------|-------|-------|
| `DASHBOARD_PASSWORD` | `YourSecretPassword` | Coach login password |
| `DATA_DIR` | `/data` | Must match the Volume mount path |

To set variables:
- Click the service → **Variables** tab → **New Variable**

After adding variables, Railway will automatically redeploy both services.

### Step 7 — Verify deployment

1. Open `https://your-api.railway.app/checkin` — you should see the player check-in form
2. Open `https://your-dashboard.railway.app` — you should see the login screen
3. Log in, go to **Admin**, add your players, click **Save Roster**
4. Go back to the check-in form — players should now appear

### Step 8 — Share with players

Send players the check-in URL and ask them to bookmark it:
- iPhone: Safari → Share → **Add to Home Screen**
- Android: Chrome → menu (⋮) → **Add to Home Screen**

It appears as an app icon on their phone. One tap → select name → submit.

---

## Making changes

Any push to `main` triggers an automatic redeploy on Railway:

```bash
git add .
git commit -m "describe what you changed"
git push
```

---

## Troubleshooting

**Check-in form shows "No players in roster yet"**
→ Log into the dashboard → Admin tab → add players → Save Roster.
The check-in form reads the roster at page load time from the shared volume.

**Dashboard login always fails**
→ Check that `DASHBOARD_PASSWORD` is set correctly on the dashboard service in Railway (no extra spaces).
→ Trigger a manual redeploy after updating env vars.

**Submissions not appearing in the dashboard**
→ Confirm both services have the same Volume mounted at `/data`.
→ Check Railway logs for the API service (click service → **Logs**) for any write errors.

**Volume shows empty after redeployment**
→ Railway Volumes are persistent — data is not lost on redeploy. If the CSV is missing, it may not have been written yet. Submit a test check-in and refresh.

**Port not accessible**
→ Make sure the port is exposed under **Networking** in each service's settings (8000 for API, 8501 for dashboard).

---

## Adding session RPE and bowling data

Session load and bowling data can be logged directly from the **Session Load** and **Bowling Load** tabs in the coach dashboard — no separate form needed. Use the expandable **+ Log Session** / **+ Log Bowling Session** panels.
