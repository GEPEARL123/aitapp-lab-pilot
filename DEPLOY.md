# AIiTAPP — Deployment Guide

Two paths: Railway (recommended) or Render. Both are free-tier compatible
for a sandbox pilot. Total time from zero to live URL: under 15 minutes.

---

## Option A — Railway (Recommended)

Railway auto-detects the Procfile and deploys with one click.

### Step 1 — Push to GitHub

```bash
cd ~/Desktop/aitapp-lab-pilot
git init
git add .
git commit -m "AIiTAPP lab pilot v1.1.0"
```

Create a new repo at github.com (private recommended), then:
```bash
git remote add origin https://github.com/YOUR_USERNAME/aitapp-lab-pilot.git
git push -u origin main
```

### Step 2 — Deploy on Railway

1. Go to railway.app and sign in (GitHub login works)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repo
4. Railway detects the Procfile automatically — no configuration needed
5. Click Deploy

### Step 3 — Set Environment Variables

In Railway dashboard → your project → Variables tab:
```
AITAPP_API_KEY   =   your-secret-key-here
```

Do not set PORT — Railway injects it automatically.

### Step 4 — Get Your URL

Railway assigns a URL like: `https://aitapp-lab-pilot-production.up.railway.app`

Find it in: Settings → Networking → Public Domain

### Step 5 — Verify

```bash
curl https://YOUR_RAILWAY_URL/health
# Expected: {"status":"healthy","timestamp":"..."}
```

---

## Option B — Render

1. Go to render.com → New → Web Service
2. Connect your GitHub repo
3. Set:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Under Environment → add `AITAPP_API_KEY=your-secret-key`
5. Click Create Web Service

Render's free tier spins down after inactivity — the first request after
idle may take 30-60 seconds. Railway's free tier is more reliable for demos.

---

## After Deployment — Run Validation

```bash
export AITAPP_API_URL=https://YOUR_DEPLOYED_URL
python validate.py
```

All three checks should return PASS before running a demo or sharing
the URL with a lab contact.

---

## Running Demos Against the Deployed API

```bash
export AITAPP_API_URL=https://YOUR_DEPLOYED_URL
python demo_medical.py
python demo_evidence_integrity.py
```

---

## Updating a Deployment

```bash
git add .
git commit -m "update description"
git push
```

Railway and Render redeploy automatically on push.

---

## Security Notes

- The demo endpoints (`/v1/action/score/demo`, `/v1/evidence/check/demo`) require
  no API key. They are intentionally open for conference and lab demonstrations.
- Remove or disable demo endpoints before any production deployment.
- The `AITAPP_API_KEY` env var protects the authenticated endpoints. Change it
  from the default `dev-key-change-in-production` before sharing the URL.
- Do not commit `.env` to version control. `.env.example` is safe to commit.
