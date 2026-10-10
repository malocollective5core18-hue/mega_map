# Mission 4 — Defect Fix Report

**Branch:** `fix/audit-defects`  
**Date:** 10 October 2026  
**Scope:** Local source, SQLite test database, and repository configuration only. No Render service, production database, or Supabase project was accessed. No branch was pushed, merged, or tagged.

## Status summary

The mission's release rule requires each defect regression to pass on PostgreSQL. PostgreSQL was unavailable, so SQLite success is recorded as evidence but is not called a verified fix. “Fixed (not tested)” means source changes and local regression evidence exist, but the required PostgreSQL gate is still outstanding. No defect below should be treated as release-ready based on this report alone.

Test-first evidence is preserved for D-01 through D-05 and D-09/D-10 in the preceding work log/commit history. The D-08, D-11, and some D-12 regressions were added after their implementation changes; those tests provide coverage but do not satisfy Mission 4's test-first process requirement. This deviation is recorded rather than presented as test-first proof.

| Defect | Status | Commit(s) | Regression evidence / remaining gate |
|---|---|---|---|
| D-01 concurrent duplicate submissions | **Fixed (not tested)** | `e61147d` | `ConcurrentSubmissionTests.test_near_simultaneous_same_phone_submissions_create_only_one_business` is PostgreSQL-only and was skipped on SQLite. Advisory transaction locks cover phone and neighboring location cells, acquired in sorted order. Must pass on PostgreSQL before calling fixed. |
| D-02 phone edits and bound keys | **Fixed (not tested)** | `577075c` | `StaffPermissionTests.test_phone_change_rebinds_live_keys_and_audits_field_names` passed on SQLite: non-revoked keys follow the corrected phone; revoked keys remain unchanged; old/new verification and field-name-only audit are checked. PostgreSQL run remains required. |
| D-03 duplicate phones | **Needs owner decision** | `5d0ac77` | `DuplicatePhoneCheckTests.test_pre_migration_duplicate_check_masks_phone_and_does_not_write` and duplicate-edit regression passed on SQLite. The read-only command is `check_duplicate_customer_phones`. No representative data copy was available, so no database unique constraint was added. Confirm one-business-per-phone and run the command on a protected copy; resolve any duplicates before a unique migration. |
| D-04 Render branch mismatch | **Fixed (not tested)** | `53985c5` | `DeploymentConfigurationTests.test_render_blueprint_targets_production_branch` passed on SQLite/source. `render.yaml` now names `production`. The live Render dashboard's watched branch remains unverified and must be confirmed by the owner. |
| D-05 code-attempt retention | **Fixed (not tested)** | `bae8482` | `CodeAttemptRetentionTests` passed on SQLite for 24-hour bounded pruning and the opportunistic batch. PostgreSQL scheduled-command behavior remains to be verified. Schedule `manage.py prune_code_attempts --hours 24` daily. |
| D-06 reproducible environment | **Fixed (not tested)** | `a31a4c2` | Exact runtime pins are in `requirements.lock`; build uses it; Python 3.14.4 is declared. Test settings `check`, migration-state check, full SQLite suite, `pip check`, and production `check --deploy` were run. PostgreSQL migrations/tests, clean network install, `pip-audit`, and Ruff are outstanding. Package-index DNS prevented installing audit tools. `check --deploy` passes with a long dummy key; the check key was not a real credential. |
| D-07 MFA, CSP, and Django admin | **Not fixed** | `70e313f` | `/admin/` is restricted to superusers and a CSP report-only header is added; corresponding local tests pass. Required staff TOTP enrollment, recovery codes, reenrollment, and lockout were not implemented. CSP remains report-only; browser compatibility and enforcement are unverified. MFA blocks this defect and production release. Package installation of `django-otp` failed because package-index DNS was unavailable; no custom MFA cryptography was substituted. |
| D-08 audit coverage | **Fixed (not tested)** | `ac8569c`, `5d352c3` | Local regressions cover staff-user listing, denied access, failed sign-in, new-customer key verification, field-name-only edit metadata, and code-history view auditing. Full endpoint/event matrix and PostgreSQL run remain outstanding. Audit metadata excludes submitted values in the tested paths. |
| D-09 GPS accuracy wording | **Fixed (not tested)** | `89340b4` | `AccuracyLanguageTests.test_customer_copy_does_not_promise_guaranteed_gps_accuracy` first failed on the public page's numeric accuracy promise; customer wording was changed to an estimate without a percentage. The test then passed on SQLite. No wording promises guaranteed physical accuracy. |
| D-10 public Leaflet SRI | **Fixed (not tested)** | `89340b4`, `561f9b7` | `PublicAssetIntegrityTests.test_public_leaflet_assets_are_pinned_and_integrity_protected` failed before adding SRI and passed after. Public CSS/JS now use the same pinned Leaflet 1.9.4 unpkg URLs and integrity digests already present in the staff page. Browser/network verification was unavailable. The code change landed with D-09; the separate D-10 commit records its verification. |
| D-11 code-history query scan | **Fixed (not tested)** | `0d9aea0`, `2199b78` | Migration `0007_customerbusiness_phone_hash` backfills indexed HMAC phone digests from `DJANGO_SECRET_KEY` in batches of 500; model writes refresh the digest; history links by indexed digest. Tests passed on SQLite for write/update and history linking. PostgreSQL migration/query-plan verification is outstanding. Secret rotation requires an approved rehash/recovery procedure; do not rotate without it. |
| D-12 lifecycle, role matrix, revoke UI and test gaps | **Not fixed** | `c0156fe`, `e1c18a4` | Regressions include `CustomerFlowTests.test_reusable_key_repeats_until_expiry_or_revocation`, `test_expired_key_is_rejected`, `test_customer_can_update_profile_with_reusable_key`, `StaffPermissionTests.test_superuser_can_issue_reusable_customer_key`, `test_provider_cannot_revoke_another_providers_key`, `test_csv_export_escapes_formula_leading_values`, `test_withdrawing_public_consent_removes_public_shop`, `test_staff_endpoint_role_matrix_for_directory_export_codes_and_audit`, and login CSRF/email ambiguity. Dashboard Revoke now confirms before calling the existing API. A complete matrix for every staff endpoint and PostgreSQL/browser checks were not run. This defect has two commits because role/refresh coverage was added after the first D-12 commit. |
| Reported key-generation page refresh | **Fixed (not tested)** | `0b4a94b`, `e1c18a4` | Source has `preventDefault()`, renders the one-time-key result before dispatching the history refresh, and does not call `location.reload` from the submit handler. A source regression passes. No browser/Playwright run was possible, so actual no-reload behavior and visibility after history refresh require the manual test below. |

## Verification run

- Full test suite on SQLite: **39 tests, 38 passed, 1 PostgreSQL-only concurrency test skipped**. Django system check was clean.
- `makemigrations --check --dry-run`: passed, no changes detected.
- Production `check --deploy`: passed with a long dummy key and explicit dummy host/origin values.
- `pip check`: passed; no broken requirements.
- Inline JavaScript `node --check`: passed after substituting template role booleans in temporary copies.
- `git diff --check`: passed.
- PostgreSQL: **not run**. Docker is unavailable; the local PostgreSQL cluster was stopped and could not be started under the workspace account.
- `pip-audit` and Ruff: **not run**. They were absent and installation attempts failed because package-index DNS was unavailable.
- Browser/Playwright, Render dashboard, Supabase, real devices, and production data: **not accessed**.
- A targeted high-confidence history scan before code changes found no real secrets in tracked repository snapshots. The ignored `.env` was neither read nor scanned. Run a trusted full-history scanner before publication.

## Owner decisions and manual work still required

1. Approve or change the one-active-business-per-phone rule. Run `python manage.py check_duplicate_customer_phones` against a protected representative copy; decide how to resolve any duplicate records before adding the unique database constraint.
2. Confirm the live Render service watches `production`, and confirm the deployment environment has the exact pinned Python/runtime settings.
3. Complete staff MFA design/implementation and assign an enrollment, recovery, and reenrollment owner. Do not onboard routine live customer records before this gate passes.
4. Review CSP report-only violations in real browsers, resolve inline script/style needs, then move to enforced CSP only after compatibility evidence.
5. Demonstrate Supabase backup/restore and document data region, backup retention, recovery objective, incident commander, and notification/support owners.
6. Run empty PostgreSQL migrations and the whole suite on PostgreSQL, including the concurrent submission test; also migrate a protected previous-schema copy.
7. Run `pip-audit`, Ruff, and a trusted full-history secret scan from a network-enabled isolated environment.
8. Manually generate a customer key in a real browser; verify the page does not navigate/reload, the one-time key remains visible after history refresh, and Copy/Share work. Test real-device GPS, pin correction, and Google Maps handoff.
9. Obtain approved privacy/legal wording and resolve the retention, removal, and customer-data handling decisions in `SRS.md`.

## Owner release commands — not run by this audit

First publish the review branch, then open and approve a PR to protected `production` only after every release gate above is complete:

```sh
git switch fix/audit-defects
git status --short
git push -u origin fix/audit-defects
gh pr create --base production --head fix/audit-defects --title "Fix audited release defects" --body "See RELEASE/FIX-REPORT.md. Merge only after all release gates pass."
```

After the PR is approved and all checks pass, merge it through the repository's protected-branch review flow. If policy explicitly permits a verified fast-forward from the reviewed remote branch, the equivalent commands are:

```sh
git fetch origin
git switch production
git pull --ff-only origin production
git merge --ff-only origin/fix/audit-defects
git tag -a v1.0.0-rc1 -m "Mauzosheet release candidate 1"
git push origin production v1.0.0-rc1
```

Do not run those commands until MFA, PostgreSQL, data, browser, and operational gates are complete. For an application rollback after a bad deploy, keep branch history forward-moving and revert the reviewed release merge through a hotfix PR:

```sh
git fetch origin
git switch -c hotfix/revert-release origin/production
git revert -m 1 <release-merge-commit-sha>
git push -u origin hotfix/revert-release
gh pr create --base production --head hotfix/revert-release --title "Rollback faulty release" --body "Revert the faulty release merge; preserve forward-only production history."
```

Use Render's rollback control for immediate service recovery while the revert PR is reviewed. Database recovery must follow `RELEASE/ROLLBACK.md`; an application rollback does not reverse or restore database data.
