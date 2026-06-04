# Nalgonda Knights — Setup Guide
## Full deployment: GitHub → Netlify

---

## FOLDER STRUCTURE

```
knights-v2/
├── public/
│   ├── index.html          ← Coach dashboard (password protected)
│   └── checkin.html        ← Player check-in form (open, no login)
├── netlify/
│   └── functions/
│       └── auth.js         ← Password validation (server-side)
├── apps-script.gs          ← Google Apps Script (paste into your Sheet)
├── netlify.toml            ← Netlify config
└── README.md               ← This file
```

**Data flow (live mode):**
```
Player submits checkin.html
        ↓
Netlify Forms captures it
        ↓
Netlify outgoing webhook (built-in)
        ↓
Apps Script doPost() → writes a row to Google Sheet
        ↓
Apps Script doGet() → JSON
        ↓
Coach dashboard fetches it
```

**Two URLs when deployed:**
- `https://yoursite.netlify.app/` → Coach dashboard (password protected)
- `https://yoursite.netlify.app/checkin` → Player check-in (open, send this to players)

---

## STEP 1 — Create a GitHub repository

1. Go to **github.com** and sign in (create a free account if needed)
2. Click the **+** icon (top right) → **New repository**
3. Name: `knights-dashboard`
4. Visibility: **Private** ← important
5. Do NOT tick "Add a README" (we already have one)
6. Click **Create repository**

---

## STEP 2 — Push the code to GitHub

On your computer, open Terminal (Mac/Linux) or Command Prompt (Windows).

Navigate to the `knights-v2` folder:
```bash
cd path/to/knights-v2
```

Then run these commands one by one:
```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/knights-dashboard.git
git push -u origin main
```

Replace `YOUR_GITHUB_USERNAME` with your actual GitHub username.

When it asks for credentials, use your GitHub username and a
**Personal Access Token** (not your password):
- GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
- Generate new token → tick `repo` scope → copy the token
- Use this as the password when git prompts you

---

## STEP 3 — Create a Netlify account and connect GitHub

1. Go to **netlify.com** → Sign up with GitHub (easiest)
2. Click **Add new site → Import an existing project**
3. Click **GitHub**
4. Authorise Netlify to access your GitHub
5. Find and select **knights-dashboard**
6. Build settings:
   - Base directory: *(leave blank)*
   - Build command: *(leave blank)*
   - Publish directory: `public`
7. Click **Deploy site**

Netlify will deploy in about 30 seconds and give you a URL like:
`https://amazing-knight-abc123.netlify.app`

---

## STEP 4 — Set environment variables in Netlify

This is how the password stays OUT of your code.

1. In Netlify: go to your site → **Site configuration → Environment variables**
2. Click **Add a variable** for each of these:

| Key | Value | Notes |
|-----|-------|-------|
| `DASHBOARD_PASSWORD` | `YourSecretPassword` | Coach login password |
| `TOKEN_SECRET` | `any-random-string-here` | e.g. `knights2026xk9m` — just make it random |

> The dashboard reads its live data straight from Google Sheets (next step),
> so no Netlify API token is needed.

3. After adding all variables: click **Deploy → Trigger deploy → Deploy site**
   (Variables only take effect on new deploys)

---

## CONNECT GOOGLE SHEETS (live data)

Until you do this, the dashboard shows **sample data**. This connects the
pipeline so every player check-in lands permanently in a Google Sheet and
flows to the dashboard. No Zapier, no paid tier — all free.

### A — Create the Sheet
1. Go to **sheets.google.com** → **Blank spreadsheet**
2. Rename it `Knights Data` (top-left)
3. Leave the tabs empty — the script creates `wellness`, `sessions`,
   `bowling`, and `status` tabs automatically on first submission

### B — Add the Apps Script
1. In the Sheet: **Extensions → Apps Script**
2. Delete the placeholder `function myFunction() {}`
3. Open `apps-script.gs` from this repo, copy ALL of it, paste it in
4. (Optional) Change `SECRET_KEY` at the top to your own random string.
   If you do, set the same value as `APPS_SCRIPT_KEY` in `public/index.html`
5. Click the **Save** (disk) icon

### C — Deploy it as a Web App
1. Click **Deploy → New deployment**
2. Click the gear ⚙ next to "Select type" → **Web app**
3. Settings:
   - Description: `knights`
   - Execute as: **Me**
   - Who has access: **Anyone**  ← required, both Netlify and the dashboard call it
4. Click **Deploy** → **Authorize access** → pick your Google account →
   "Advanced" → "Go to … (unsafe)" → **Allow** (this is your own script)
5. Copy the **Web app URL** — it ends in `/exec`

> If you ever edit the script, you must **Deploy → Manage deployments →
> Edit (pencil) → Version: New version → Deploy** for changes to go live.
> The `/exec` URL stays the same.

### D — Point the dashboard at the Sheet
1. In `public/index.html`, near the top of the `<script>` find:
   ```javascript
   const APPS_SCRIPT_URL = '';
   const APPS_SCRIPT_KEY = 'knights-sheet-key';
   ```
2. Paste your `/exec` URL into `APPS_SCRIPT_URL`. Make sure `APPS_SCRIPT_KEY`
   matches `SECRET_KEY` in `apps-script.gs`
3. Push to GitHub (`git add . && git commit -m "connect sheets" && git push`)

### E — Forward Netlify submissions to the script
1. Netlify → your site → **Site configuration → Notifications → Forms**
   (also reachable via **Forms → Settings & usage → Form notifications**)
2. **Add notification → Outgoing webhook**
3. Settings:
   - Event to listen for: **New form submission**
   - URL to notify: *paste your `/exec` Web app URL* (no `?key=` needed here)
   - Form: **Any form** (or pick `daily-wellness`)
4. **Save**

### F — Test it end-to-end
1. Open `https://yoursite.netlify.app/checkin`, submit a check-in
2. Within a second or two, a row appears in the `wellness` tab of your Sheet
3. Open the dashboard, log in, refresh — the banner turns green
   (**"Connected to Google Sheets — live data"**) and the entry shows up

---

## STEP 5 — Update the player list

In `public/checkin.html`, find the `PLAYERS` array near the top of the `<script>` section:

```javascript
const PLAYERS = [
  {name:"Ravi Kumar",    role:"All-Rounder", isBowler: true},
  ...
];
```

Update names, roles, and set `isBowler: true` for all fast bowlers/seamers
(they get the extra hamstring/groin/back questions).

After editing, push to GitHub:
```bash
git add .
git commit -m "update player list"
git push
```

Netlify auto-redeploys in ~20 seconds.

---

## STEP 6 — Test everything

**Test player check-in:**
1. Open `https://yoursite.netlify.app/checkin`
2. Select a player, fill in the sliders, submit
3. Go to Netlify → your site → **Forms** → you should see the submission

**Test coach dashboard:**
1. Open `https://yoursite.netlify.app`
2. Enter the password you set in `DASHBOARD_PASSWORD`
3. Should log in and show the dashboard
4. After a player submits, refresh the dashboard — data should appear

---

## STEP 7 — Share with players

Send players this link:
```
https://yoursite.netlify.app/checkin
```

Ask them to **bookmark it** on their phone's home screen:
- iPhone: Safari → Share → Add to Home Screen
- Android: Chrome → menu (3 dots) → Add to Home Screen

It will appear as an app icon. One tap, select name, submit. Done.

---

## UPDATING THE DASHBOARD IN FUTURE

Any change is just:
```bash
git add .
git commit -m "describe what you changed"
git push
```

Netlify picks it up automatically. Live in ~20 seconds.

---

## ADDING SESSION RPE FORM (Phase 1.5)

When you're ready to add a post-training RPE form, create
`public/rpe.html` following the same pattern as `checkin.html`.
The Netlify form name must be `session-rpe` to match the `FORM_TABS`
map in `apps-script.gs` (the bowling and status forms map to
`bowling-load` and `player-status` respectively). No script changes
needed — the matching tab is created automatically on first submission.

---

## TROUBLESHOOTING

**"Page not found" on /checkin**
→ Make sure publish directory is set to `public` in Netlify build settings

**Password always says incorrect**
→ Check `DASHBOARD_PASSWORD` env var is set in Netlify (no extra spaces)
→ Trigger a fresh deploy after setting env vars

**Dashboard shows sample data even after submissions**
→ Is `APPS_SCRIPT_URL` filled in (and pushed) in `public/index.html`?
→ Does `APPS_SCRIPT_KEY` match `SECRET_KEY` in `apps-script.gs`?
→ Open the `/exec` URL with `?key=YOUR_KEY` in a browser — you should see JSON.
   If you see "Unauthorized", the keys don't match. If you see a Google login
   page, the Web app "Who has access" isn't set to **Anyone**
→ Open browser console (F12) on the dashboard for error messages

**Rows not appearing in the Google Sheet**
→ Netlify → Forms — did the submission appear there first?
→ Netlify → Notifications → confirm the outgoing webhook points to the `/exec` URL
→ Apps Script editor → **Executions** (left sidebar) — look for failed `doPost` runs
→ If you edited the script, re-deploy a **New version** (see step C note)

**Form submissions not appearing in Netlify**
→ The hidden form detection element in `checkin.html` must be present
→ Try redeploying — Netlify scans for forms at deploy time

---

## PHASE 2 UPGRADE PATH

When ready to add player-facing profiles, history, and proper auth:
- **Database**: Supabase (free tier)
- **Auth**: Supabase Auth with Google OAuth
- **Framework**: Next.js on Vercel or Netlify
- All Netlify Forms data can be exported as CSV and imported to Supabase
