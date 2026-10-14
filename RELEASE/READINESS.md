# Release Readiness

**Status: NOT PRODUCTION-READY.** Mission 5 work is confined to local branch `fix/audit-defects`. Nothing was pushed, merged, deployed, or run against production systems.

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
| TOTP MFA | Pass | django-otp TOTP, recovery codes, lockout, audit, session/API gating, and named-owner reenrollment are implemented and covered by focused SQLite tests. PostgreSQL/browser checks and selection/configuration of the recovery owner remain open. |
| Full endpoint/role matrix | Fail | Current tests cover key permissions but not all endpoint/method/role combinations. |
| Playwright and enforced CSP | Fail | Playwright config and npm lockfile are absent; CSP remains report-only. |
| Customer phone uniqueness | Not tested | Owner decision and protected-data duplicate scan are outstanding; no unique constraint was added. |
| Production Render/Supabase settings | Not tested | Live branch, credentials, database migration, headers, backup/restore, and logging were not inspected. |
| Legal/privacy/retention and incident ownership | Not tested | Required owner decisions and approvals remain open. |

## Required before production

1. Re-run TOTP MFA tests from the current lock, then verify PostgreSQL and browser behavior and name/configure the MFA recovery owner.
2. Complete role authorization coverage for all sensitive endpoints and methods.
3. Run PostgreSQL migrations and tests, including at least 20 concurrency regressions.
4. Pass a redacted full-history Gitleaks scan. Stop and report safely if any secret appears.
5. Add Playwright coverage and test with CSP enforcement in a browser.
6. Resolve the phone uniqueness policy and perform the approved masked duplicate scan before adding a constraint.
7. Verify production configuration, HTTPS, backup/restore, retention, privacy/legal approval, and support/incident ownership.

See [BLOCKERS-REPORT.md](BLOCKERS-REPORT.md) for task statuses and detailed next gates, and [../TEST-REPORT.md](../TEST-REPORT.md) for commands and results.
