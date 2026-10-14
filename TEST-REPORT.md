# Test report

## Mission 5 run

Date: 14 October 2026. Branch: `fix/audit-defects`. No production database, Render service, Supabase project, or GitHub repository settings were accessed. All locally generated credentials were dummy values.

### Environment and CI workflow

| Item | Status | Evidence |
|---|---|---|
| PyPI network access | Fail | On resume `getent ahosts pypi.org` returned no addresses. A fresh environment with ensurepip was created, but `pip install -r requirements.lock` failed DNS resolution at `/simple/asgiref/`. |
| GitHub network access | Fail | `getent ahosts github.com` returned no addresses; the earlier Gitleaks release download also failed with `Could not resolve host: github.com`. |
| PostgreSQL | Not tested | PostgreSQL 18 cluster exists but is stopped and owned by `nobody`; `pg_isready` has no response. Docker is unavailable. |
| GitHub Actions workflow syntax and exact job labels | Pass | YAML parsed locally; all five requested job names match exactly. |
| GitHub Action release references | Pass | Checkout v7.0.1, setup-python v7.0.0, setup-node v7.1.0, upload-artifact v7.0.2, pip-audit v1.1.0, Ruff Action v4.1.0, and Gitleaks Action v3.0.0 exist in their official release/project pages. |
| GitHub Actions execution | Not tested | The workflow was not triggered or observed in GitHub Actions. |
| Repository settings | Not tested | No branch protection or repository settings were changed. |

### Local checks

| Check | Status | Evidence |
|---|---|---|
| Fresh install from current `requirements.lock` | Not tested | The earlier install covered Django 5.2.18/DRF 3.17.2 before the latest MFA dependencies. Current install is blocked by DNS; django-otp is not available in the existing `.venv`. |
| `manage.py check` against current changes | Not tested | Current import is blocked because django-otp is unavailable. Earlier pre-MFA check passed. |
| `manage.py check --deploy` against current changes | Not tested | Current import is blocked because django-otp is unavailable. Earlier dummy-only deploy check passed against pre-MFA dependencies. |
| `makemigrations --check --dry-run` against current changes | Not tested | Current import is blocked because django-otp is unavailable. Earlier migration check passed before the MFA models/migration. |
| Full Django suite on SQLite | Pass | MFA run: 47 tests; 46 passed, 1 PostgreSQL-only concurrency test skipped. This preceded only the final MFA table heading and example environment variable documentation edits. |
| PostgreSQL suite and concurrency regression repeated 20 times | Not tested | PostgreSQL unavailable locally; SQLite skips this regression. CI evidence is also unavailable. |
| `pip check` | Pass | No broken requirements in the fresh environment. |
| `pip-audit -r requirements.lock` | Pass | After updating DRF to 3.17.2, no known vulnerabilities were reported. DRF 3.16.1 had two advisories and was the real dependency failure fixed. |
| `ruff check .` | Pass | Ruff 0.17.0; all checks passed. |
| Ruff formatting check | Pass | All 55 Python files passed `ruff format --check`. |
| Frontend JavaScript syntax | Pass | `scripts/check_frontend_js.py` checked five inline script blocks. |
| Full-history Gitleaks scan | Not tested | Official binary download was blocked by GitHub DNS failure. No secret finding is claimed. The ignored `.env` was not read. |

### Release blocker tasks

| Task | Status | Evidence / reason |
|---|---|---|
| Staff TOTP MFA, recovery, lockout, reenrollment | Pass | Implemented with django-otp and covered by eight focused tests within the 47-test SQLite run. PostgreSQL/browser verification is still open; recovery owner is not named/configured. |
| Complete role/endpoint matrix | Fail | Existing matrix covers core directory, export, code-history, revoke, and audit roles but does not cover every endpoint, method, and role pairing. |
| Playwright and CSP enforcement | Fail | No `package-lock.json` or `playwright.config.ts`; CI deliberately fails closed. CSP remains report-only and has not been browser-validated. Chromium exists locally, but no Playwright suite is configured. |
| Customer phone uniqueness constraint | Not tested | No constraint added. Owner decision and duplicate scan against a protected representative database are outstanding. |
| Runtime/config checks | Partial | Local checks pass as above; real Render, Supabase, HTTPS headers, production PostgreSQL migrations, backups, and secrets were not accessed. |
| Documentation updates | Pass | `RELEASE/BLOCKERS-REPORT.md`, this report, and `RELEASE/READINESS.md` now record task status and blockers. |

## Release status

Not release-ready. Do not treat the skipped PostgreSQL test as a pass. MFA, a complete role matrix, browser tests under enforced CSP, full-history secret scanning, owner/data approval for uniqueness, and production operations evidence remain open. The branch is local and unpushed; no deployment was performed.

## Mission 6 user journeys and location signals

Date: 15 October 2026. Branch: `feature/user-journeys`, based on `fix/audit-defects`. No live services or customer data were accessed.

Implementation commit: `439a93e`; journey/privacy documentation commit: `96e26dc`. The feature branch push succeeded. No production branch or deployment was changed.

| Work/check | Status | Evidence / blocker |
|---|---|---|
| Journey and screen-spec documentation for all eight user types | Pass (source review) | `docs/USER-JOURNEYS.md`, `docs/UI-SCREEN-SPEC.md`, and `RELEASE/JOURNEY-REPORT.md` contain source-referenced journeys, screen states, errors, role permissions, decisions and manual checks. Browser claims remain Not tested. |
| Registered customers screen | Gap fixed in source; runtime Not tested | Restored missing `customersView` markup and guarded directory event bindings when the view is not rendered. This was a source-level cause of a blank/broken directory and potentially early dashboard JavaScript failure. |
| Customer location metadata and plausibility | Implemented in source; tests Not tested | Source sends source, timestamp, reported accuracy, final pin, offset and moved flag. Server calculates age; validates broad configured box, max accuracy, stale/future fixes; confidence includes source/accuracy/age/offset/staff verification. Migration 0009 authored but not applied. |
| GPS permission/error/watcher handling | Implemented in source; device Not tested | 15-second one-time watcher, best fix/accuracy circle, movement and 50m warnings, distinct denied/unavailable/timeout messages, cleanup on exit/pagehide. |
| Field-team role and assigned jobs | Implemented in source; API tests Not tested | Superuser registration UI, assignable staff API/select, field-team assignment support, assigned-only list/detail, one-time arrival distance endpoint, audit distance band only, assigned-pin correction. |
| Privacy notice | Implemented in source/docs; approval Not tested | New bilingual `PRIVACY-NOTICE.md`, version `2026-10-location-v1`, distinguishes client-only speed from stored/transmitted fields and states no background tracking. Legal/retention approval remains open. |
| Inline frontend JavaScript syntax | Pass | `python3 scripts/check_frontend_js.py` — 5 inline script blocks checked after adding Django template substitution for field-team flags. |
| Python source compilation | Pass | `py_compile` succeeded for changed application, test, settings, URL and migration files. |
| `git diff --check` | Pass | No whitespace errors in current worktree diff. |
| Mission 6 API test cases authored | Not tested | `LocationSignalValidationTests` covers fresh/stale/future/naive fixes, accuracy, bounds, manual pins, confidence and persisted signal minimization. `AssignedFieldTeamJourneyTests` covers assignment filtering, account assignment, unauthorized operations, arrival distance/audit, and assigned-pin correction. Runtime is blocked by missing `django_otp`. |
| Django check / migration drift / test suite | Not tested | All stop during app loading: `ModuleNotFoundError: django_otp` in the current `.venv`; PyPI DNS currently fails. |
| PostgreSQL migration/tests | Not tested | `pg_isready` reports no response and Docker is unavailable. |
| Ruff | Not tested | `.venv/bin/ruff` is absent; no install possible while package registry DNS fails. |
| Playwright journeys and owner screenshots | Not tested | No Playwright test specs/package lock; npm registry DNS fails. Chromium Snap refuses to launch because snapd/AppArmor confinement is unavailable. No screenshots generated. |
| Mobile viewport / real device permissions | Not tested | No browser-run checks at 360×640 / 390×844 or Android/iOS geolocation tests. |

### Mission 6 remaining owner/release decisions

- Approve actual service boundary; current Tanzania rectangle is broad and overlaps neighboring jurisdictions.
- Approve 50m warning, 250m large-offset flag, 100,000m max accuracy, 120-second max fix age, and 30-second future-skew defaults.
- Confirm manual pins are accepted at Low confidence and large offsets are flagged rather than blocked.
- Approve bilingual notice and retention/removal terms; name the privacy/support owner.
- Confirm field-job assignment ownership and whether field team may update outcome/status.
- Complete Playwright suite/screenshots and browser/device permission tests before asserting compact-fit or runtime success.

## Mission 7 stabilization — 15 October 2026

No Render dashboard, GitHub Actions account, production database, customer data, or live mutation was accessed. Network/DNS checks in this run failed for GitHub and PyPI; local PostgreSQL had no response and Docker was unavailable.

### Environment and CI evidence

| Check | Status | Evidence |
|---|---|---|
| Render deployment branch/commit | Not tested | No dashboard/deploy-log access. The blueprint currently targets `production`; live service provenance remains unknown, so we cannot say whether unreviewed code is live. |
| Dependency installer alignment | Pass (source) | `build.sh` installs `requirements.lock`; `.github/workflows/ci.yml` installs the same file. It pins Django 5.2.18 and djangorestframework 3.17.2. |
| Exact pinned versions in latest test run | Not tested | Local venv reports Django 5.2.18 and DRF 3.16.1, while lacking django-otp; system Python lacks Django. The current lock could not be installed because PyPI DNS fails. Previous test evidence does not establish a run against the complete current lock. |
| GitHub Actions for `fix/audit-defects` and `feature/user-journeys` | Not tested | No GitHub connector or `gh` CLI; DNS resolution for github.com fails and public Actions fetch is unavailable. Job statuses and root causes are unknown. The committed workflow's Playwright guard will fail while `playwright.config.ts`/`package-lock.json` are absent; required-check settings were not changed. |
| PostgreSQL migrations/full suite/concurrency 20x | Not tested | `pg_isready` reports no server and Docker is absent; no Actions evidence is reachable. |
| pip-audit | Not tested in this run | Tool is unavailable locally; current CI result cannot be inspected. Earlier Mission 5 pass is historical only. |
| Ruff | Not tested in this run | Tool is unavailable locally; current CI result cannot be inspected. Earlier Mission 5 pass is historical only. |
| Full-history Gitleaks | Not tested in this run | Tool/result unavailable; no current clean-history claim is made. |
| Frontend JavaScript syntax | Pass | `python3 scripts/check_frontend_js.py` checked five inline script blocks after the Mission 7 request changes. |
| Django checks and tests | Not tested | System Python has no Django. Available `.venv` is stale/incomplete and cannot run the current locked project (django-otp missing). |

### Stabilization changes and checks

| Item | Status | Evidence |
|---|---|---|
| SVG favicon | Implemented in source | Linked from public, staff login, and staff dashboard templates; served from app static files. Static collection/live serving not tested. |
| `/healthz` | Implemented in source; runtime Not tested | Returns HTTP 204 with no body; production `SECURE_REDIRECT_EXEMPT` excludes this path from HTTPS redirect. Test authored; unable to run Django suite. |
| Render health-check path | Pass (blueprint source) | `render.yaml` now specifies `/healthz`; actual Render dashboard setting not verified. |
| Query-string exposure from app API | Implemented in source; tests Not tested | Public bbox/shop searches, staff customer filters, provider-code history filters, phone/key verification, and location coordinates use JSON/body requests. New tests reject query-based GET forms and assert POST query strings are empty. |
| Public place suggestions | Limitation documented | Browser still sends place-search text directly to Photon using its query parameter API. It does not put that value in a Render request URL, but it does leave the browser in an external request URL; do not claim global URL/query-free search or that Photon never receives search text. |
| External map navigation | Intentional external transfer | Clicking Drive/Walk/map links sends destination coordinates to the selected map provider. They are not included in an incoming Render API URL. |
| One-time superuser bootstrap variables | Pass (source review) | No code/build references found. If present in Render, owner may remove `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, and `DJANGO_SUPERUSER_PASSWORD`. Values were not read or printed. |
| Pending owner decisions | Open | Service boundary, 50 m warning, manual-pin acceptance, large-offset policy, field-team rights/job-state authority were left unchanged. |

### Live smoke test (test data only)

All steps are **Not tested**: public map; issue test key; customer location flow; duplicate-phone rejection; staff customer view; navigate and copy coordinates; revoke key; logout; MFA login. No test credentials/key were supplied, Render is unreachable from this environment, and no live operation was attempted.

### Release / merge status

Not release-ready. The deployed Render commit and branch, latest CI status, live smoke test, PostgreSQL verification, enforced CSP, Supabase backup/restore, approved legal notice, and real-device GPS tests remain unverified or open. No PR was prepared because green CI has not been confirmed. No merge, tag, deploy, production commit, or repository-setting change was made.
