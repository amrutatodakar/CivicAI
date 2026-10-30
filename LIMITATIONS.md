# Limitations

## By design (MVP scope)
- **Authentication**: single shared demo officer account via env vars. No roles/permissions, no citizen accounts.
- **Data**: synthetic demo dataset in `Demo City`. No municipal system integration, no real citizen PII.
- **AI**: priority and category are explainable heuristics. Optional LLM is best-effort and falls back to local rules; outputs are decision support, not facts.
- **Vision**: uploaded images are stored for evidence only — no automatic image classification/vision analysis.
- **Duplicates**: suggestions only; merging requires explicit officer confirmation. Location is important; text-only matches need higher similarity.
- **Hotspots**: require geolocated reports (≥3 by default within ~0.7 km). Clusters indicate concentration, not proven causes.
- **Persistence**: SQLite; not tuned for high concurrency. File uploads stored locally in `static/uploads/`.
- **Security**: CSRF enabled for browser forms (API endpoints for programmatic submission/health are exempt in this demo). No rate limiting, no CSP beyond basic headers.
- **Validation**: client-side checks are UX only; server validation is authoritative.
- **i18n/time**: English only; times stored as naive UTC in SQLite.
- **Public exposure**: only public status notes appear on tracking; internal notes/audit logs stay officer-only.

## Potential rough edges
- Offline without CDN: Chart.js/Leaflet may fail to load — tables/text fallbacks are shown where added; map requires network for tiles.
- Browser storage: "My reports" uses `localStorage` (private to device/browser).
- Duplicate direction: canonical is recorded as newer → older on confirmation; UI states this.
- Priority overrides are logged but do not re-run duplicate/hotspot logic automatically.
- Auto-seed runs on first app creation; in tests set `SEED_ON_START=False`.
