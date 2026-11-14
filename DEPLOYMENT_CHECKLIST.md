# Railway Deployment Checklist

## ✅ Files Already Created (Ready to Push)

- [x] `Procfile` — Railway startup entry point
- [x] `railway.json` — Railway configuration
- [x] `.railwayignore` — deployment ignore rules
- [x] `backend/start.sh` — startup script (migrations + seeding)
- [x] `docs/RAILWAY_DEPLOYMENT.md` — deployment guide
- [x] Tests pass: 186 backend, frontend build, real OCR, live Sarvam

## 🚀 Next Steps (In Order)

### Step 1: Commit & Push to GitHub
```bash
git add Procfile railway.json .railwayignore backend/start.sh docs/RAILWAY_DEPLOYMENT.md docs/progress.md
git commit -m "Deploy: Add Railway configuration and deployment scripts"
git push origin main
```

### Step 2: Configure Railway Project (Dashboard)
Go to https://railway.app/dashboard

1. **Select your Byte Bot project**
2. **Click: Add Plugin → PostgreSQL** (wait for ✓ Success)
3. **Click: Variables tab** and add these:
   ```
   DATABASE_URL=                         # Auto-filled by PostgreSQL plugin
   BYTEBOT_EXTRACTION_MODE=sarvam        # Use sarvam extraction (key configured in your .env)
   SARVAM_API_KEY=sk_xxxxx               # Copy your Sarvam key from your local .env
   SARVAM_CHAT_MODEL=sarvam-105b-conversations
   COOKIE_SECURE=true                    # HTTPS in production
   OCR_MODEL_DIR=.cache/easyocr
   GEMINI_API_KEY=                       # Leave blank (not configured)
   GEMINI_MODEL=                         # Leave blank (not configured)
   ```

### Step 3: Add Services
In Railway Dashboard → **Services**

**Backend Service:**
- Click: **+ Create Service from GitHub**
- Repository: `shishirshebbar/Byte-Bot`
- Root Directory: `backend/`
- Runtime: Python 3.12 (auto-detected)
- Start Command: `bash ./start.sh`
- Port: 8000
- **Link Database:** Click **Plugins** → Select PostgreSQL → Link
  - This auto-populates `DATABASE_URL` variable

**Frontend Service:**
- Click: **+ Create Service from GitHub**
- Repository: `shishirshebbar/Byte-Bot`
- Root Directory: `frontend/`
- Runtime: Node.js 22 (auto-detected)
- Build Command: `npm ci && npm run build`
- Start Command: `npm run preview`
- Port: 4174
- Environment Variable:
  ```
  VITE_API_URL=https://bytebot-api.railway.app/api
  ```
  (Replace `bytebot-api` with your actual backend service name)

### Step 4: Deploy
1. Click: **Trigger Deploy** (or auto-triggers on GitHub push)
2. Watch: **Deployments** tab shows build progress
3. Wait for: Both services show ✓ **Deployed**

### Step 5: Verify Deployment
1. Get your Railway URLs from dashboard
2. Test backend health:
   ```bash
   curl https://your-backend-service.railway.app/api/v1/health
   ```
   Should return: `{"status":"ok","database":"connected"}`

3. Open frontend in browser:
   - Main app: `https://your-frontend-service.railway.app/`
   - Console: `https://your-frontend-service.railway.app/console`
   - Metrics: `https://your-frontend-service.railway.app/metrics`

4. Test a scenario:
   - Click: **Load / reopen scenario**
   - Select: **Scenario A** (seeded demo data)
   - Click: **Ask Byte Bot** → Type evidence or upload screenshot
   - Click: **Analyze & prepare report**
   - Verify result loads (risk score, findings, etc.)

### Step 6: (Optional) Custom Domain
1. In Railway → **Settings** → **Custom Domain**
2. Add domains:
   - Backend: `api.yourdomain.com` → points to backend service
   - Frontend: `yourdomain.com` → points to frontend service
3. Update DNS CNAME records at your domain provider

---

## ⚠️ Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| `DATABASE_URL not found` | Make sure PostgreSQL plugin is linked to backend service |
| `Frontend shows 404` | Check `VITE_API_URL` points to correct Railway backend URL |
| `Backend fails to start` | Check Railway logs: `railway logs --service bytebot-api` |
| `502 Bad Gateway` | Backend crashed; check logs and environment variables |
| `Migrations fail` | Ensure `DATABASE_URL` is set and PostgreSQL is ready |

---

## 📊 What You Have

✅ **Sarvam AI** (configured with key, tested live)
✅ **Real OCR** (EasyOCR models tested)
✅ **186 backend tests** passing
✅ **Frontend build** passing
✅ **PostgreSQL** ready for Railway
✅ **Deployment scripts** ready to push

---

## 🎯 After Go-Live

Once Railway deployment is live:

1. **Monitor:**
   - Railway dashboard logs (real-time backend output)
   - Frontend `/metrics` page (Byte Bot KPIs)

2. **Test scenarios A–E:**
   - Load each seeded scenario
   - Submit evidence (text, screenshot, or voice note in Hindi)
   - Verify analysis completes and shows risk category
   - Check for escalations to console if expected

3. **Check console (escalation queue):**
   - Go to `/console` on frontend
   - Test human approvals for escalated cases

4. **Demo to stakeholders:**
   - Share the live URL
   - Run through Scenario B walkthrough (high-concern case)

---

## 📝 Summary

You now have:
1. ✅ All deployment files ready
2. ✅ Step-by-step Railway guide (`docs/RAILWAY_DEPLOYMENT.md`)
3. ✅ This checklist
4. ⏭️ Just need to: Push → Configure Railway → Deploy

**Time to live:** ~10 minutes (after Railway finishes building)

Questions? Check `docs/RAILWAY_DEPLOYMENT.md` for detailed troubleshooting.
