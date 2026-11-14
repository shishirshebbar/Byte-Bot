# Railway Deployment Guide

## Quick Start (5 minutes)

You have Railway project and Git repo ready. Follow these steps to deploy:

### Step 1: Configure Railway Project (Dashboard)

1. Go to https://railway.app/dashboard
2. Click your Byte Bot project
3. Click **Add Plugin** → Select **PostgreSQL**
4. Wait for PostgreSQL to provision (shows `✓ Success`)

### Step 2: Set Environment Variables

In Railway Dashboard, click **Variables** tab and add:

```
DATABASE_URL=                    # Auto-filled by PostgreSQL plugin
BYTEBOT_EXTRACTION_MODE=sarvam
SARVAM_API_KEY=sk_xxxxx          # Copy from your .env
SARVAM_CHAT_MODEL=sarvam-105b-conversations
COOKIE_SECURE=true
BYTEBOT_CORS_ORIGINS=https://bytebot-frontend.railway.app
OCR_MODEL_DIR=.cache/easyocr
GEMINI_API_KEY=                  # Leave blank
GEMINI_MODEL=                    # Leave blank
```

### Step 3: Configure Services

**Service 1: Backend (Python/FastAPI)**

1. In Dashboard → **Services** → Add service from GitHub
2. Select `shishirshebbar/Byte-Bot`
3. Set:
   - **Name:** `bytebot-api`
   - **Root Directory:** `backend/`
   - **Start Command:** `bash ./start.sh`
   - **Runtime:** Python 3.12
   - **Port:** 8000

4. Link PostgreSQL:
   - Click **Plugins** → **Link Database**
   - Select PostgreSQL
   - This auto-populates `DATABASE_URL`

**Service 2: Frontend (Node.js/Vite)**

1. Add another service from same GitHub repo
2. Set:
   - **Name:** `bytebot-frontend`
   - **Root Directory:** `frontend/`
   - **Build Command:** `npm ci && npm run build`
   - **Start Command:** `npm run preview`
   - **Runtime:** Node.js 22
   - **Port:** 4174
   - **Environment Variable:** `VITE_API_URL=https://{backend-url}.railway.app/api`
     (Replace `{backend-url}` with your Railway backend domain)

### Step 4: Deploy

1. Click **Trigger Deploy** in Railway dashboard
2. Watch logs in **Deployments** tab
3. Wait for:
   - Backend: `✓ Deployed` (running on 8000)
   - Frontend: `✓ Deployed` (running on 4174)

### Step 5: Verify

1. Get your Railway URLs:
   - Backend: `https://bytebot-api.railway.app` (visible in Dashboard)
   - Frontend: `https://bytebot-frontend.railway.app`

2. Test endpoints:
   ```bash
   # Backend health check
   curl https://bytebot-api.railway.app/api/v1/health

   # Should return: {"status":"ok","database":"connected"}
   ```

3. Open in browser:
   - Frontend: `https://bytebot-frontend.railway.app/`
   - Console: `https://bytebot-frontend.railway.app/console`
   - Metrics: `https://bytebot-frontend.railway.app/metrics`

### Step 6: Custom Domain (Optional)

1. In Dashboard → **Settings** → **Custom Domain**
2. Add:
   - Backend: `api.yourdomain.com`
   - Frontend: `yourdomain.com`
3. Update DNS records in your domain provider (CNAME to Railway)
4. Set `BYTEBOT_CORS_ORIGINS` on the backend to the frontend origin, without a trailing slash.

---

## What's Already in the Repo

✅ **Deployment files created:**
- `Procfile` — tells Railway how to start the backend
- `railway.json` — Railway configuration
- `.railwayignore` — files to exclude (cache, venv, etc.)
- `backend/start.sh` — startup script (migrations + seeding + server)

✅ **Environment ready:**
- Python 3.12 runtime (`.python-version`)
- Node.js 22 (`.node-version`)
- PostgreSQL 16 compatible schema
- Sarvam AI integration (key in `.env`)

---

## Troubleshooting

### "Railway can't find DATABASE_URL"
→ Ensure PostgreSQL plugin is linked to backend service

### "Frontend can't reach backend API"
→ Update `VITE_API_URL` in frontend environment to your Railway backend URL

### "Migrations failed"
→ Check Railway logs in **Deployments** → **View Logs**
```
railway logs --service bytebot-api
```

### "502 Bad Gateway"
→ Backend service crashed. Check logs:
```
railway logs --service bytebot-api --tail 50
```

---

## Git Push & Deploy

```bash
# Commit deployment files
git add Procfile railway.json .railwayignore backend/start.sh
git commit -m "Add Railway deployment configuration"
git push origin main

# Railway auto-detects changes and redeploys
```

---

## After Deployment

### First-time setup in production:
1. Wait for migrations to complete (logs will show `✓ Migrations completed`)
2. Seeds insert 8 demo transactions per session automatically
3. Open frontend → **Load / reopen scenario** → Pick Scenario A–E

### Monitor in production:
- Railway Dashboard → **Logs** (real-time)
- Railway Dashboard → **Metrics** (CPU, memory, bandwidth)
- Frontend **/metrics** page (Byte Bot KPIs)

---

## Quick Command Reference

```bash
# View backend logs (last 50 lines)
railway logs --service bytebot-api --tail 50

# View frontend logs
railway logs --service bytebot-frontend --tail 50

# Trigger manual deploy
railway up

# Show current environment variables
railway variables

# Set variable from CLI
railway variables set BYTEBOT_EXTRACTION_MODE=sarvam
```

---

## Next Steps

1. **Push these files to GitHub:**
   ```bash
   git add .
   git commit -m "Deploy: Add Railway configuration"
   git push
   ```

2. **Trigger deploy in Railway dashboard** (or wait for auto-trigger on push)

3. **Test live at:** `https://your-railway-app.railway.app/`

4. **Monitor:** Check logs in Railway dashboard for any errors

That's it! Your Byte Bot is now live. 🚀
