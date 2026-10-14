# Release Readiness

**Status: NOT PRODUCTION-READY.** Mission 5 is on `fix/audit-defects`; Mission 6 implementation and documentation are committed on `feature/user-journeys` and pushed to `origin`. Django/PostgreSQL/browser verification remains incomplete. No production system was accessed or deployed.

## Mission 7 stabilization update — 15 October 2026

**Status: NOT PRODUCTION-READY.** Render and GitHub Actions account-level data could not be accessed from this environment. The deployed branch/commit, Actions runs, and live smoke test are therefore unverified. No merge, tag, deployment, or repository-setting change was made.

| Gate | Status | Evidence / blocker |
|---|---|---|
| Render deployed branch and commit | Not tested | No Render dashboard/deploy-log connector; `render.yaml` currently names `production`, but this does not prove the live service follows that branch. Local refs: `fix/audit-defects` at `d26535e`, `feature/user-journeys` at `fc1a0c6`, `production` at `0b4a94b`. Whether unreviewed code is live is unknown. |
| Dependency lock use | Pass (source) | `build.sh` and `.github/workflows/ci.yml` both install `requirements.lock`; it pins Django 5.2.18 and DRF 3.17.2. |
| Exact deployed/tested dependency versions | Not tested | The available `.venv` has Django 5.2.18/DRF 3.16.1 and lacks django-otp; system Python lacks Django. Current full lock was not installed and current suite did not run. |
| GitHub Actions results on both branches | Not tested | No `gh`/GitHub connector, GitHub DNS fails, and the public Actions page fetch was unavailable. Per-job CI failures and root causes cannot be confirmed. Source still has a Playwright job that fails when the suite/config is absent; repository required-check settings were not touched. |
| PostgreSQL migrations and 20 concurrency repetitions | Not tested | Local PostgreSQL has no response; Docker is unavailable. GitHub run evidence is inaccessible. |
| pip-audit / Ruff / full-history Gitleaks | Not tested in this run | Executables are unavailable locally; GitHub Actions result access and package/GitHub DNS are unavailable. Historical passes in Mission 5 are not substituted for current branch evidence. |
| Frontend syntax | Pass | `python3 scripts/check_frontend_js.py` checked five inline script blocks after the Mission 7 client request changes. |
| Favicon and health check | Implemented in source; deployed behavior Not tested | Added SVG favicon links, `/healthz` empty 204 response, HTTP redirect exemption, and Render blueprint health path `/healthz`. The actual Render health check configuration remains unverified. |
| Sensitive values in Render request URLs | Implemented in source; tests Not tested | Map bbox, public business search, staff customer filters, provider-code history search, phone/key verification and location payload use request bodies. Tests were authored to reject GET query forms and assert empty query strings for POST, but could not run. Customer-clicked navigation intentionally sends coordinates to the chosen external maps provider. Area lookup still sends a place query directly to Photon, outside the Render request URL/log path. |
| Superuser bootstrap variables | Pass (source review) | No application/build reference to `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, or `DJANGO_SUPERUSER_PASSWORD` was found. Owner may remove those names from Render if present; no values were read. |
| Live smoke test using test records | Not tested | Render cannot be reached from this environment and no isolated test account/key is available. No live operations were attempted. |
| Merge / PR sequence | Not started | CI is not confirmed green, so no PR was prepared. Do not merge or deploy until CI evidence and branch provenance are reviewed. |

Open product decisions remain unchanged: approved service boundary; 50 m poor-accuracy warning; manual-pin acceptance; large-offset handling; field-team rights/job-state authority. No policy was changed in this stabilization pass.

## Current gate status

| Gate | Status | Evidence / blocker |
|---|---|---|
| Fresh dependency install | Not tested | The earlier clean install passed before django-otp and qrcode were added to the lock. The new clean install could not resolve PyPI DNS on resume. |
| Django checks and migration drift | Not tested | Earlier checks passed against the prior dependency set; current code cannot import because django-otp is missing from the available environments. |
| SQLite test suite | Pass | MFA implementation run: 47 tests, 46 passed and 1 PostgreSQL-only concurrency test skipped. This run preceded only the MFA recovery table heading and `.env.example` edits. |
| PostgreSQL migrations and 20 concurrency repetitions | Not tested | Local PostgreSQL is down and Docker is unavailable. |
| Dependency security audit | Pass | `pip-audit` found no known vulnerabilities after DRF was upgraded to 3.17.2. |
| Ruff | Pass | Ruff 0.17.0 check and formatting checks passed. |
| Frontend syntax | Pass | Five inline JavaScript blocks checked. |
| CI workflow definitions | Pass | YAML and exact requested job labels checked; pinned Action versions exist. GitHub Actions run not observed. |
| Full-history secret scan | Not tested | Gitleaks release fetch failed on GitHub DNS. No clean-history claim is made. `.env` was not read. |
| TOTP MFA | Partial | TOTP, recovery codes, lockout, audit and staff session/API gating were previously covered by focused SQLite tests. Follow-up adds a password-only exception for the explicitly configured superuser email (`MFA_EXEMPT_SUPERUSER_EMAIL`); this change is not tested, and the Render value is not configured here. Other staff remain MFA-protected. |
| Full endpoint/role matrix | Fail | Current tests cover key permissions but not all endpoint/method/role combinations. |
| Playwright and enforced CSP | Fail | Playwright config and npm lockfile are absent; CSP remains report-only. |
| Customer phone uniqueness | Not tested | Owner decision and protected-data duplicate scan are outstanding; no unique constraint was added. |
| Production Render/Supabase settings | Not tested | Live branch, credentials, database migration, headers, backup/restore, and logging were not inspected. |
| Legal/privacy/retention and incident ownership | Not tested | Required owner decisions and approvals remain open. |
| Mission 6 journey documents | Pass (source review) | All eight user types are described in `docs/USER-JOURNEYS.md`; screen/role inventory is in `docs/UI-SCREEN-SPEC.md`. Browser behavior is not implied. |
| Mission 6 GPS signals, validation and confidence | Implemented in source; tests Not tested | Code, migration and tests authored for single capture, signal storage minimization, server plausibility and confidence. Django test environment lacks `django_otp`; PostgreSQL is unavailable. |
| Registered customers UI repair | Implemented in source; runtime Not tested | Restored missing `customersView` markup and guarded role-specific handlers; inline JavaScript syntax passes. |
| Field-team role, assignment and arrival check | Implemented in source; API/browser tests Not tested | Superuser creation, dispatcher assignment selector, assigned-only access, transient distance check and audited pin correction added. |
| Playwright screenshots and mobile fit | Not tested | npm registry DNS/Playwright dependency and lockfile unavailable; installed Chromium Snap refuses to launch because snapd/AppArmor confinement is unavailable. No screenshots or viewport measurements produced. |
| Mission 6 privacy notice | Implemented in source/docs; owner/legal approval open | Bilingual `PRIVACY-NOTICE.md`, notice version and precise device signal/data wording added. Retention and service-boundary approval required. |

## Required before production

1. Re-run TOTP MFA tests from the current lock, then verify PostgreSQL and browser behavior and name/configure the MFA recovery owner.
2. Complete role authorization coverage for all sensitive endpoints and methods.
3. Run PostgreSQL migrations and tests, including at least 20 concurrency regressions.
4. Pass a redacted full-history Gitleaks scan. Stop and report safely if any secret appears.
5. Add Playwright coverage and test with CSP enforcement in a browser.
6. Resolve the phone uniqueness policy and perform the approved masked duplicate scan before adding a constraint.
7. Verify production configuration, HTTPS, backup/restore, retention, privacy/legal approval, and support/incident ownership.

See [BLOCKERS-REPORT.md](BLOCKERS-REPORT.md) for Mission 5 gates, [JOURNEY-REPORT.md](JOURNEY-REPORT.md) for Mission 6, and [../TEST-REPORT.md](../TEST-REPORT.md) for check results.
