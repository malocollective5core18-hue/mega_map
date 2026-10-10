# Release Readiness

**Status: NOT PRODUCTION-READY.** This audit made no deployment, production database, or Supabase changes. The candidate remains on local branch `fix/audit-defects`; it was not pushed, merged, or tagged.

## Mission 4 verification snapshot

| Gate | Status | Evidence / blocker |
|---|---|---|
| Django source suite | Partial | 39 SQLite tests: 38 passed, 1 PostgreSQL-only concurrent submission test skipped. SQLite is not the required release database. |
| PostgreSQL empty migration and full suite | Not tested | Docker unavailable; the installed local PostgreSQL cluster could not be started with workspace permissions. |
| Django check | Pass | Test settings `manage.py check` found no issues. |
| Production deploy check | Pass | `check --deploy` passed using dummy secret/host/origin values; not evidence for the live Render configuration. |
| Migration consistency | Pass | `makemigrations --check --dry-run`: no changes detected. Migration execution on PostgreSQL remains unverified. |
| Dependency reproducibility | Partial | Runtime packages pinned in `requirements.lock`, build uses it, Python 3.14.4 declared. Fresh isolated network install and lock hashes are not verified. |
| `pip-audit` and Ruff | Not tested | Not installed; package-index DNS blocked installation. |
| Browser and real devices | Not tested | No Playwright/browser run; key generation, CSP compatibility, GPS, pin drag, and Google Maps handoff need manual browser/device checks. |
| Render branch | Partial | Blueprint names `production`; live Render watched branch is unverified. |
| TOTP MFA | Fail | MFA enrollment, recovery, re-enrollment, and lockout are not implemented. Release blocker for routine live data. |
| CSP | Partial | Report-only header exists. Inline script/style compatibility has not been observed in browsers; enforcement is not enabled. |
| Django admin | Pass in source test | `/admin/` now checks active staff superuser status. It is not protected by MFA yet. |
| Phone uniqueness | Needs owner decision | Duplicate-check command exists, but no protected representative dataset was checked; no unique DB constraint is present. |
| Backups, restore, region, incident response | Not verified | Owner must document region, restore proof, recovery objective, response lead, and support/notification contacts. |
| Legal, privacy, retention | Not approved | Privacy notice/legal approval and retention/removal decisions remain open. |
| Secret scan | Partial | Prior targeted scan found no high-confidence secret in tracked source history. Ignored `.env` was deliberately not read; run a trusted full-history scanner before publication. |

## Release blockers

1. Complete staff TOTP MFA and test enrollment, wrong-code throttling/lockout, single-use recovery, and administrator reenrollment.
2. Provision or start a PostgreSQL test environment; run migrations from empty and protected previous-schema copies, then run the full suite including the concurrency test.
3. Run `pip-audit`, Ruff, and a trusted full-history secret scanner in a network-enabled isolated environment.
4. Run the phone duplicate checker against a protected representative data copy and resolve the owner policy before any unique constraint migration.
5. Verify CSP report-only compatibility in a real browser, then prepare and review the enforced policy. Verify public Leaflet SRI network loading.
6. Confirm Render's live branch, verify production host/secrets/configuration, and complete Supabase backup/restore and incident ownership records.
7. Perform manual key issuance/revoke/refresh checks and real Android/iPhone GPS, pin, and map-navigation checks.
8. Approve privacy/legal copy and retention/removal policy.

See [FIX-REPORT.md](FIX-REPORT.md) for defect statuses, regression names, commit IDs, owner tasks, and merge/tag/rollback commands. See [CHECKLIST.md](CHECKLIST.md) for the gate-by-gate release checklist.
