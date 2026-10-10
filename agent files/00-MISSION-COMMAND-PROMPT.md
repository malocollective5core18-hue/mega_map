# AI ENGINEERING MISSION: BUILD THE COMPLETE STOCKTAKING LOCATION PLATFORM

## 1. ROLE
Act as a Principal Full-Stack Engineer, Geospatial Systems Architect, Security Engineer, UI/UX Designer and QA Lead. You own this build end to end.

## 2. BUSINESS CONTEXT
We are a stocktaking and inventory-counting company serving shops, businesses and offices (base: Dar es Salaam, Tanzania). Clients phone us and describe where they are, and our teams get lost. We are building one platform that:
1. Lets a client share a verified business location (provider code, details, GPS pin, explicit confirmation).
2. Shows the public a satellite map of **shops we already serve** (opt-in only) and **areas of demand** (aggregated only).
3. Gives staff a private dashboard for **new customers**, dispatch, codes, reports and audit.

## 3. SOURCE OF TRUTH (read all before writing code)
- `index.html` – existing single-file customer flow (Leaflet, Esri satellite only, green #0f3d2e with amber accent, Kiswahili/English). Preserve its design, flow and working behaviour.
- `01-product-requirements.md`, `02-data-model-and-privacy.md`, `03-public-map-and-ui-spec.md`, `04-backend-api-contract.md`, `05-admin-dashboard-spec.md`, `06-security-and-compliance.md`, `07-test-and-acceptance-plan.md`.
If documents conflict, privacy and security (02, 06) win. If anything essential is missing, list your assumptions in `ASSUMPTIONS.md` and continue; do not stop to ask unless blocked.

## 4. TECHNICAL STACK
- Backend: Django + Django REST Framework with PostgreSQL. This is decided; do not substitute another framework. Store coordinates as indexed latitude/longitude decimal fields (no PostGIS required); use bounding-box queries and haversine distance for duplicate checks. PostGIS can be added later without changing the API.
- Public and customer frontend: HTML5, CSS3, vanilla JS, Leaflet via CDN with pinned versions. No build step.
- Staff dashboard: server-rendered Django templates plus vanilla JS and Leaflet (no SPA framework).
- Config via environment variables; `.env.example` provided; no secrets in code or repo.
- Version control: git from the first commit, `main` plus short-lived feature branches, one commit per step with clear messages, `.gitignore` (env files, media, venv, db dumps), no secrets ever committed.
- Local development only for now: run with `python manage.py runserver` and a local PostgreSQL (Docker Compose optional). Deployment is deferred until all features are complete; do not spend effort on production infrastructure beyond `DEPLOY.md`, production-ready settings split (`settings/base.py`, `dev.py`, `prod.py`) and an environment-variable `.env.example`.

## 5. BUILD PHASES (complete in order, commit-sized steps)
**Phase 1 – Backend foundation:** project, models per doc 02, migrations, hashed provider codes, verification sessions, audit log, admin roles (dispatcher, admin).
**Phase 2 – APIs:** every endpoint in doc 04 with validation, throttling, error shape, idempotent submission, duplicate detection (same phone or pin within 30 m), OpenAPI schema.
**Phase 3 – Customer flow:** wire `index.html` to the real endpoints, set `DEMO_MODE=false`, send `publicListing` consent as a separate unticked checkbox, handle every error in doc 04.
**Phase 4 – Public map:** layers "Shops we serve" and "Areas of demand" from the public endpoints only, bbox loading, clustering, popups, search, layer panel, request-service button.
**Phase 5 – Staff dashboard:** reliable navigation to each customer (Navigate button using the exact-coordinates Google Maps directions link, Waze/Apple/OSM backups, copy coordinates, WhatsApp share, confidence badge and team pin correction exactly as in doc 05), inbox, satellite map with all layers, business detail with navigation links, dispatch, provider-code management, public-listing control, reports, CSV export, audit view (doc 05).
**Phase 6 – Security hardening:** doc 06 in full (CSP, SRI, CSRF, MFA for staff, rate limits, secure cookies, HSTS, retention job, anonymise-on-delete).
**Phase 7 – Tests and docs:** automated tests plus the manual checklist in doc 07; write `DEPLOY.md` for later use (the owner deploys after all features are complete, so do not deploy anything).

## 6. NON-NEGOTIABLE RULES
- Never expose exact coordinates, names or phone numbers of customers on any public endpoint, page, URL, log or analytics event. Public pins are opt-in and rounded; demand cells need at least 3 requests.
- Do not treat a non-empty code as verified. Verify on the server; return identical errors for every invalid code.
- Never fabricate coordinates, test results or successful submissions. Success is shown only after the server confirms.
- Navigation links use exact coordinates only, are built and validated on the server, and never contain customer names or phone numbers. Never claim route accuracy or arrival times; those come from Google Maps.
- Every view of exact data and every export is audit-logged.
- No dead buttons, fake features or TODOs for essential functionality.
- Do not replace working functionality without reason. Keep the satellite-only map.
- Mobile-first, large touch targets, keyboard accessible, reduced-motion support, clear fallback if tiles or API fail.
- Respect Tanzania's Personal Data Protection Act, 2022; flag items needing legal review rather than guessing.
- Note third-party terms (Esri imagery, Nominatim geocoding) and make providers configurable.

## 7. TESTING (required before declaring done)
- Automated: model and API tests, role-permission tests, and a test that fails if any public response contains a phone, name or unrounded coordinate.
- Manual checklist from doc 07. Mark each item Pass, Fail or Not tested. Where GPS hardware, real devices or production HTTPS are unavailable, say so and describe the controlled scenario you used. Do not invent results.

## 8. FINAL DELIVERABLES
1. Complete repository: backend, templates, static files, `index.html`, Docker setup, `.env.example`, seed/demo data command clearly labelled as demo.
2. `ARCHITECTURE.md`, `ASSUMPTIONS.md`, `API.md` (or OpenAPI file), `DEPLOY.md` (HTTPS, env vars, backups, cron for retention and demand-cell refresh).
3. Test report: what ran, results, what could not be verified.
4. Production-readiness checklist with every open owner decision (regions, retention period, who may export, legal notice approval).
5. Short staff guide in Kiswahili and English for dispatchers.

## 9. FINAL DIRECTIVE
Build the actual platform now. Do not stop at a plan, mockup or pseudocode. Deliver working code for all seven phases, and clearly identify anything that depends on external decisions or services. Do not sacrifice privacy, security or location accuracy for visual polish.
