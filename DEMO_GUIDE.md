# Demo Guide (5 minutes)

Follow this sequence to show the full CivicAI loop.

## Setup
```powershell
cd D:\hihih
.\.venv\Scripts\Activate.ps1
python app.py
```
Open `http://127.0.0.1:5000`. Demo data is auto-loaded.

**Officer login:** `officer` / `civic2026` (`/officer/login`)

## Walkthrough

### 1) Home (15s)
- Show totals, resolved %, high/critical open, category bars.
- Point to hotspots preview and "Working civic intelligence MVP" features.

### 2) Report a complaint (60s)
Go to **Report an issue** (`/report`):
- Title: `Deep pothole blocking school gate`
- Description: include safety impact and duration (≥20 chars)
- Category: leave as "Let AI decide" (or pick one)
- Address: `School Gate, Demo City`
- Click map or **Use my location** to drop pin (coordinates optional but help duplicates/hotspots)
- Submit → redirects to tracking page with success banner and `CIV-000X` ID. **Copy/save the ID**.

### 3) Track publicly (45s)
On the tracking page:
- Show AI summary, category confidence, priority level/score with factors/explanation
- Status timeline (public notes only)
- Related suggestions (if any) with text+distance
- Note: internal officer notes never appear here

Also try **Track complaint** form and **My reports** (add ID, fetched live).

### 4) Officer triage (2-2.5 min)
Sign in as officer → **Operations console** (`/officer/`):
- **Priority queue**: critical/high open first
- **Overview**: trends, priority/category/status charts
- **Map & hotspots**: see clusters, click a hotspot or "Show on map", read action brief
- **Management**: filter by category/status/priority/duplicates/search; click a row to open detail

Open the complaint you just submitted:
- **Analysis & evidence**: AI engine label, factors, explanation
- **Duplicate review**: suggestions with scores/reasons; confirm/reject (show behavior)
- **Action brief**: generated next steps/evidence/caveat
- **Assign & update** (Workflow): set status to `Under Review`/`Assigned`/`In Progress`, pick department, add **public** note → appears on citizen tracking
- **Review priority**: override score/level with reason (original retained)
- **History**: status history + internal audit log

### 5) Verify the loop (30s)
Return to public tracking for that ID — status, department, and public note are updated. Show **My reports** reflects live status.

## Tips
- Use the seeded College Road/Gandhi Market clusters to demo hotspots quickly.
- If map tiles don't load offline, use table + hotspot list.
- API: `curl http://127.0.0.1:5000/api/health`
- Reset demo: `python scripts/seed_data.py --force` or `flask --app app.py demo-reset --yes`
