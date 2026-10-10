# AI ENGINEERING MISSION 2: COMPLETE THE STOCKTAKING LOCATION PLATFORM

## 1. ROLE AND CONTEXT
You are continuing an existing Django + PostgreSQL + git project. Read first: `00-MISSION-COMMAND-PROMPT.md`, docs 01-07, and the repo's `ARCHITECTURE.md`, `API.md`, `ASSUMPTIONS.md`, `TEST-REPORT.md`, staff guide and code.
Already done (do not rebuild or break): customer APIs, staff sign-in, dispatch dashboard basics, audited customer details, navigation to server-validated coordinates, audited pin corrections, admin CSV export, audit view, provider-code creation, public-listing consent, 7 passing tests (SQLite).
Your job: finish every outstanding item below, verify honestly, and update the docs. Work on feature branches, small commits, no secrets in git.

## 2. OUTSTANDING WORK (do in this order)
1. **PostgreSQL verification.** Run migrations and the full test suite against real PostgreSQL (Docker Compose `db` service or a local install). Fix any SQLite-vs-PostgreSQL differences. If PostgreSQL still cannot run in your environment, say so in `TEST-REPORT.md` and give the exact commands for the owner.
2. **Staff MFA.** TOTP (authenticator app) required for all staff and admins, with enrolment, recovery codes, session timeout (30 min idle), login throttling and lockout. Tests for enforced MFA.
3. **Security headers.** Content-Security-Policy limited to the site, API, Leaflet CDN, Esri tiles and Nominatim; Subresource Integrity on CDN scripts; HSTS, secure/HttpOnly/SameSite cookies in prod settings; CSRF checks. Test that the pages still work under the CSP.
4. **Provider-code revocation and management UI.** Revoke, expire, set max uses, view usage; revoked codes fail verification with the same generic error. Audit-logged.
5. **Dispatch controls.** Assign team member, schedule date, valid status transitions (submitted → reviewed → scheduled → served, plus rejected/duplicate), visit records with outcome, notes, and a dispatcher-only "my jobs" mobile list. Role tests: dispatchers cannot export or manage codes.
6. **Reports.** Submissions per week and per ward, time to dispatch, demand cells ranked, accuracy distribution. Staff-only, no raw customer contact data in report views.
7. **Retention and anonymisation.** Management command plus scheduled job instructions: anonymise or delete records past the configured retention period, honour customer removal requests, remove a shop from the public map immediately on consent withdrawal. Make the retention period a setting with no hard-coded guess; document that the owner must decide it.
8. **Public map completion check.** Confirm layers "Shops we serve" and "Areas of demand" come only from the public serializer. Keep the automated test that fails if any public response contains a name, phone or unrounded coordinate, and add one for demand cells with count < 3.
9. **Location capture improvement (recommended).** In `index.html`, capture for about 15 seconds with `watchPosition`, keep the most accurate fix, show an accuracy circle, and advise retry when accuracy is worse than about 50 m. Always clear the watcher. Server stays authoritative; reject out-of-range or impossible points.

## 3. RULES
- Privacy and security rules from the first mission still apply in full.
- Never claim a fixed accuracy percentage. Confidence badges reflect device-reported accuracy only.
- Do not claim a check passed unless you ran it. Mark Pass, Fail or Not tested, and list what needs real devices (GPS, Google Maps navigation on Android/iPhone, slow networks) as a checklist for the owner.
- Do not deploy. Keep `DEPLOY.md` current for the owner's later deployment.
- Add tests for every new feature; the suite must pass on PostgreSQL.

## 4. DELIVERABLES
Updated code and migrations; updated `TEST-REPORT.md`, `ASSUMPTIONS.md`, `API.md`, `ARCHITECTURE.md`, staff guide (Kiswahili and English); a release-readiness checklist stating exactly what remains for the owner (retention period, legal notice review, who may export, real-device tests, production HTTPS and backups).

## 5. FINAL DIRECTIVE
Implement all items now, run every check you can, and report results truthfully. Do not stop at a plan.
