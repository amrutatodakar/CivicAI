# CivicAI

A working, AI-assisted civic complaint management platform built for Demo City. It covers the full loop: citizen submission and public tracking, officer triage with explainable AI, duplicate/hotspot detection, and an auditable workflow. Everything runs locally with SQLite and transparent rule-based fallbacks.

## Features

- **Citizen portal**: report issues with title, description, category, location, optional image. Submits without an account and returns a public `CIV-0001` ID.
- **Public tracking**: `/track/<id>` shows status, public notes only, AI summary/priority explanation, related suggestions, and location. "My reports" saves IDs in browser local storage.
- **Officer console**: dashboard with stats, priority queue, charts (Chart.js), complaint map + hotspots (Leaflet/OpenStreetMap), filters/search, complaint detail with workflow, priority review, duplicate review, action brief, and audit history.
- **AI analysis**: local rule-based NLP classifies category, extracts summary, and produces an explainable 0–100 priority score with factors. Optional OpenAI-compatible LLM can be configured via env vars; falls back to local rules on error/missing config. The UI labels the active engine.
- **Duplicate detection**: stdlib TF-IDF/cosine text similarity + haversine proximity. Suggestions require evidence and are never auto-merged; officers must confirm/reject. Confirmed links preserve both records and histories (newer linked to older as canonical).
- **Hotspot analysis**: greedy distance clustering (configurable radius/min size), ignores confirmed duplicates, surfaces concern level, categories, action brief with next steps and caveats.
- **Security/demo UX**: server validation, magic-byte + extension + size checks for uploads (PNG/JPG/JPEG/WEBP/GIF, ≤5 MB), CSRF for browser POSTs (API exempt where noted), single demo officer account, internal notes never exposed publicly.
- **Seed data**: 54 synthetic complaints with clusters/duplicates/status history; idempotent seeding via `AppSetting`.

## Tech stack

- Backend: Python 3.13, Flask 3.1, Flask-SQLAlchemy 3.1, SQLAlchemy
- DB: SQLite (default `instance/civicai.db`)
- Frontend: HTML/CSS/JS, Chart.js 4, Leaflet 1.9, OpenStreetMap
- AI: stdlib-only local NLP + rule-based priority; optional OpenAI-compatible via `requests`

## Quick start (Windows PowerShell)

```powershell
cd D:\hihih
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Run the app (creates DB, auto-seeds demo data on first start)
python app.py
```

App runs at `http://127.0.0.1:5000` by default.

## Environment variables

See `.env.example`. Key settings:
- `SECRET_KEY`, `DATABASE_URL`
- `OFFICER_USERNAME`, `OFFICER_PASSWORD` (defaults `officer` / `civic2026`)
- `SEED_ON_START` (default `1`), `CSRF_ENABLED` (default `1`)
- `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS` (optional)

## Seeding

Auto-seed runs on first app start when DB empty. Manual:
```powershell
.\.venv\Scripts\Activate.ps1
python scripts/seed_data.py        # load if missing
python scripts/seed_data.py --force # delete all complaints and reload
# or Flask CLI
flask --app app.py seed-demo
flask --app app.py seed-demo --force
flask --app app.py demo-reset --yes
```

## Demo walkthrough (5 min)

1. **Home** (`/`) — see totals, category mix, top hotspots.
2. **Report** (`/report`) — submit an issue (map picker/geolocation optional). Get `CIV-000X`.
3. **Track** (`/track/<id>` or `/track`) — see AI summary, explainable priority, related suggestions, status timeline (public notes only).
4. **My reports** (`/my-reports`) — saved IDs fetched live from API.
5. **Officer** (`/officer/login`, `officer`/`civic2026`) — queue, charts, map/hotspots, open a complaint: update workflow (status/dept/public note), review priority, confirm/reject duplicates, read action brief and audit log.

## API (useful)

- `GET /api/health` — status, DB count, AI engine
- `POST /api/complaints` — JSON or form submission (CSRF exempt), returns analysis + possible duplicates
- `GET /api/complaints/<public_id>` — public-safe complaint + history
- Officer (session auth): `GET /api/officer/dashboard`, `GET /api/officer/complaints` (filters), `GET /api/officer/hotspots`, `GET /api/officer/complaints/<id>/brief`

## Tests (smoke)

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```
Current smoke checks (manual/scripted): submission → persistence → tracking → officer auth → workflow update (public note) → priority review → duplicate confirm → API/dashboard/hotspots/brief all return 200. Run `tests` folder if added.

## Files of interest

- `app.py` — factory, CSRF, errors, CLI, Jinja filters
- `models.py` — schema (Complaint/StatusHistory/ActivityLog/DuplicateLink/AppSetting)
- `services/` — nlp/priority/ai/llm/duplicate/hotspot/action_brief/complaint/dashboard
- `routes/` — citizen/officer/api blueprints
- `templates/`, `static/css/`, `static/js/` — UI + JS
- `seed.py`, `scripts/seed_data.py`

## Notes/limitations

See `LIMITATIONS.md`. Key points: demo auth only, local heuristics (not ML trained on real data), no image vision, hotspots need coordinates, duplicate merge requires officer confirmation, no email/SMS, SQLite not for high concurrency.
