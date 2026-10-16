# Test report

## Mission 11 verification — 16 October 2026

**Branch:** `release/dashboard-data-flow`, created from local `fix/dashboard-data-flow`. No live services or customer data were accessed. Nothing was pushed, opened as a PR, merged, or deployed.

| Check | Result | Evidence |
|---|---|---|
| PyPI/npm/GitHub DNS | Fail / unavailable | `getent ahosts` returned no addresses for pypi.org, registry.npmjs.org, or github.com. |
| Fresh venv and locked install | Fail / blocked | Created `/tmp/m11-venv`; `pip install -r requirements.lock` failed resolving `/simple/asgiref/`. Checked available wheel files; only unrelated cloudinary/django-tenants wheels were present. |
| Exact installed locked versions | Not tested | The install did not complete. |
| PostgreSQL | Not tested | `pg_isready -p 55432` returned no response. No cluster was initialized. |
| Django checks/full suite/migrations/concurrency 20x | Not tested | Stopped at required environment gate; `.local-deps` cannot import current settings because `dj_database_url` is missing. |
| Duplicate-radius reproduction/fix | Not tested | Source confirms hard-coded 30 m distance comparison and lock grid; no regression or fix was run. |
| Playwright/browser scenarios/screenshots | Not tested | No installed Playwright suite; npm registry DNS unavailable. |
| Authorization matrix | Not tested | Full endpoint × method × role × MFA table-driven matrix is absent; existing tests cover selected combinations only. |
| pip-audit/Ruff/Gitleaks | Not tested | Tools unavailable; no scan result claimed. |
| Frontend syntax | Pass | `python3 scripts/check_frontend_js.py`: five inline blocks checked. |
| Python compile / whitespace | Pass | Python compilation for core services/views/middleware/diagnostic command/URLs passed; `git diff --check` passed. |

See [DASHBOARD-RELEASE-REPORT.md](RELEASE/DASHBOARD-RELEASE-REPORT.md) for detailed blocked gates and owner steps.

## Mission 10 dashboard data-flow run — 16 October 2026

**Branch:** `fix/dashboard-data-flow`, based on local `diagnose/dashboard-data-flow` at `26282cd` because the deployed Render SHA was not supplied. No live services or customer data were accessed; no push, merge, or deploy was performed. See [DASHBOARD-FIX-REPORT.md](RELEASE/DASHBOARD-FIX-REPORT.md).

| Check | Status | Evidence |
|---|---|---|
| Fresh locked dependency install (current resume) | Fail / blocked | `python3 -m venv /tmp/m10-venv && /tmp/m10-venv/bin/python -m pip install -r requirements.lock` failed DNS resolution for PyPI (`/simple/asgiref/`). The earlier successful temporary venv was removed. |
| Current Django startup | Not tested | Available `.local-deps` lacks `dj_database_url`; system Python has no Django. Current settings cannot load. |
| PostgreSQL availability (current resume) | Not tested / unavailable | `pg_isready -p 55432` returned no response. Earlier temporary PostgreSQL 18.6 run results are preserved in the Mission 10 report. |
| Full PostgreSQL suite / concurrency 20x | Pass (earlier Mission 10 run; not rerun on this resume) | Earlier locked venv + PostgreSQL 18.6: 89 tests, 0 skipped; dedicated concurrency test passed 20 consecutive runs. Final dashboard legacy-key action received focused test coverage after that full run. |
| Migration round-trip | Pass (earlier Mission 10 run) | Fresh disposable DB migrated forward, backward to core 0001, and forward again. |
| Django checks / migration drift | Pass (earlier Mission 10 run; not rerun now) | `check` and `makemigrations --check --dry-run` passed in the temporary locked environment. |
| Frontend JavaScript syntax | Pass | Current `python3 scripts/check_frontend_js.py`: five inline script blocks checked. |
| Whitespace | Pass | Current `git diff --check`. |
| pip-audit / Ruff / full-history Gitleaks | Not tested in current run | Tools/results unavailable now; no current clean scan claim. |
| Playwright and live test-data smoke | Not tested | Browser suite and test account unavailable; Render was not accessed. |

### Newly identified open regression

`core/services.py` uses `LOCATION_DUPLICATE_RADIUS_M` for candidate bounds but still has a literal 30 m final distance cutoff and 30 m advisory-lock grid. A regression case for a 100 m setting was briefly drafted, could not be executed because the current environment cannot import Django dependencies, and was not retained. This defect remains unfixed and is not counted as a passing test.

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

## Mission 8 link preview — 15 October 2026

Branch: `feature/link-preview`, created from local `fix/mission7-stabilization` at `dd81786`. No production branch, live database or Render deployment was changed. Dependencies were installed into `/tmp/link-preview-venv` from `requirements.lock`; observed Django 5.2.18 and DRF 3.17.2. The ignored local `.env` was not read.

| Check | Status | Evidence |
|---|---|---|
| Locked dependency install and `pip check` | Pass | Fresh isolated environment installed `requirements.lock`; `pip check` reported no broken requirements. |
| Django `check` | Pass | `stocktaking.settings.test`; no issues. |
| Production `check --deploy` | Pass | Dummy-only `SITE_URL`, allowed host, CSRF origin and long secret; no real configuration values. |
| `makemigrations --check --dry-run` | Pass | No changes detected. |
| Link preview metadata/static tests | Pass | `core.tests.LinkPreviewMetadataTests` and `LinkPreviewImageTests`: 5 tests pass; checks raw HTML tag order/placement, absolute metadata, anonymous crawler GET/HEAD, noindex/private pages, robots/sitemap, and the WhiteNoise image dimensions/type/size. |
| Production static collection and template rendering | Pass | `collectstatic` using production settings post-processed 424 assets; secure Django test-client request returned 200 and rendered the hashed share-image URL. |
| Full existing Django suite | Fail | 70 tests: 2 assertion failures, 1 PostgreSQL-only concurrency test skipped. Failures are existing unrelated assertions in `AccuracyLanguageTests.test_customer_copy_does_not_promise_guaranteed_gps_accuracy` (it reads template source and expects a phrase not present) and `LocationSignalValidationTests.test_confidence_uses_accuracy_age_offset_and_staff_verification` (expects the word “offset” in customer copy). No PostgreSQL-backed run was available. |
| Frontend syntax and whitespace | Pass | `python3 scripts/check_frontend_js.py` and `git diff --check`. |
| Share-image regeneration | Pass | `python3 scripts/make_og_image.py` reproduced identical SHA-256 `663261f9fcaf5ceb3f02208f79825a1096f21c0657a09ce60889c656a94982b5`; PNG is 1200×630 and 36,560 bytes. Generator-only Pillow dependency is pinned in `requirements-image.txt`. |
| Local response-time sample | Pass (local only) | Django in-process test client, production settings, 30 requests: median 6.45 ms, mean 32.87 ms, max 803.67 ms. This excludes hosting, network and cold-start latency and is not a Render performance result. |
| Render `curl -I` and live crawler agents | Not tested | DNS lookup failed with `Could not resolve host: mega-map.onrender.com`; no live HTTP response or response time is claimed. |
| Browser preview / WhatsApp / social cache refresh | Not tested | No Playwright/browser or physical phone test. Platforms control preview scraping and caching; this code cannot force refresh. |
| PostgreSQL / GitHub Actions | Not tested | No local PostgreSQL service or accessible GitHub Actions run evidence. |

See [LINK-PREVIEW-REPORT.md](RELEASE/LINK-PREVIEW-REPORT.md) for task-by-task status, owner checklist, and commit references. The overall release remains **NOT PRODUCTION-READY**.
