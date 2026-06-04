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
│       ├── auth.js         ← Password validation (server-side)
│       └── submissions.js  ← Fetches form data for dashboard
├── netlify.toml            ← Netlify config
└── README.md               ← This file
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
| `NETLIFY_SITE_ID` | *(see below)* | Your site's ID |
| `NETLIFY_API_TOKEN` | *(see below)* | Personal access token |

**How to get NETLIFY_SITE_ID:**
- Netlify → your site → Site configuration → Site ID (copy it)
- Looks like: `abc12345-1234-1234-1234-abc123456789`

**How to get NETLIFY_API_TOKEN:**
- Netlify → User settings (top right avatar) → Applications
- Click **New access token**
- Name it `knights-dashboard-api`
- Copy the token immediately (you won't see it again)

3. After adding all variables: click **Deploy → Trigger deploy → Deploy site**
   (Variables only take effect on new deploys)

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
The Netlify form name should be `session-rpe` to match what
`submissions.js` expects.

---

## TROUBLESHOOTING

**"Page not found" on /checkin**
→ Make sure publish directory is set to `public` in Netlify build settings

**Password always says incorrect**
→ Check `DASHBOARD_PASSWORD` env var is set in Netlify (no extra spaces)
→ Trigger a fresh deploy after setting env vars

**Dashboard shows sample data even after submissions**
→ Check Netlify → Forms — did the submission appear there?
→ Check `NETLIFY_SITE_ID` and `NETLIFY_API_TOKEN` are correct
→ Open browser console (F12) for error messages

**Form submissions not appearing in Netlify**
→ The hidden form detection element in `checkin.html` must be present
→ Try redeploying — Netlify scans for forms at deploy time

**Functions returning 500**
→ Netlify → Functions → click on `submissions` → view logs for the error

---

## PHASE 2 UPGRADE PATH

When ready to add player-facing profiles, history, and proper auth:
- **Database**: Supabase (free tier)
- **Auth**: Supabase Auth with Google OAuth
- **Framework**: Next.js on Vercel or Netlify
- All Netlify Forms data can be exported as CSV and imported to Supabase
