# Dashboard data-flow stabilization report

**Date:** 16 October 2026
**Branch:** `fix/dashboard-data-flow`, based on local `diagnose/dashboard-data-flow` at `26282cd` because Render's deployed SHA was not supplied.
**Scope:** Local source and fake-data tests only. No Render, Supabase, GitHub Actions account, production database, or customer data was accessed. No push, merge, or deploy was performed.

## 1. Root causes and confidence

The exact live cause of the missing customer rows remains **Not verified**. Owner-provided deployment and request evidence needed to distinguish deployment drift, an MFA 403, role scope, submission rejection, or an unsubmitted key was not provided. The source confirms several ways this can happen:

- An authenticated staff session without a verified MFA marker receives a 403 `mfa_required`; a wrong role also receives a 403. The dashboard now renders distinct visible explanations. **Confirmed source behavior; live cause not verified.** `core/middleware.py`, `core/views.py`, `templates/staff/dashboard.html`.
- A key or verified phone is not a submitted customer row. Provider key history identifies keys still awaiting customer submission. **Confirmed source model/behavior.**
- Returning-customer updates mutate the linked business. They do not make a new row; lists now order by `updated_at` by default. **Confirmed source behavior.**
- A new code review found a remaining radius inconsistency: the duplicate candidate bounds use `LOCATION_DUPLICATE_RADIUS_M`, but the final distance comparison in `core/services.py` still compares against literal 30 m. PostgreSQL advisory-lock cells also use literal 30 m. A 100 m regression case was briefly drafted but could not be run and is not retained in the test suite because the current workspace cannot import `dj_database_url` and PyPI DNS is unavailable. This remains an evidenced source defect, **unfixed and unverified by execution**.

## 2. Environment and baseline

Prior Mission 10 run evidence preserved in this branch's work history: a fresh `/tmp/m10-venv` was installed from `requirements.lock` (Django 5.2.18, DRF 3.17.2, django-otp 1.7.4, psycopg 3.3.6); PostgreSQL 18.6 ran from a temporary data directory on port 55432. On that environment, checks and the full suite passed (89 tests, 0 skipped), PostgreSQL concurrency regression passed 20 consecutive runs, and migrations succeeded forward, backward to core 0001, then forward again on a fresh temporary DB. The final legacy dashboard UI change then passed focused tests and frontend syntax. The temporary environment was removed after that run.

Current workspace recheck: a fresh venv install attempt failed resolving `asgiref` because PyPI DNS returned “Name or service not known”; system Python and `.local-deps` cannot load the current app configuration (`dj_database_url` missing). Local PostgreSQL port 55432 has no response. Therefore no final full-suite rerun was possible after the final UI commits. Treat the earlier successful test run as valid for the code state at that time, and the final focused test evidence as limited to the listed committed tests; it is not a new clean install now.

## 3. Deployment identity and dependency alignment

Render's actual branch/SHA and GitHub Actions results are **Not verified**. The supplied Render installation logs identify package versions but not branch or commit. The branch was based on `diagnose/dashboard-data-flow` at `26282cd` per the mission fallback rule. Local refs and deployment comparison are documented in `RELEASE/DASHBOARD-DIAGNOSIS.md`; they do not establish what Render runs.

Source alignment: `build.sh` and `.github/workflows/ci.yml` install `requirements.lock`; `requirements.txt` includes the lock, and `render.yaml` selects the build script. A regression test covers the install-path consistency (`test_every_install_path_uses_the_locked_application_dependencies`). Source alignment does not prove the live Render dashboard has no override.

## 4. Hypotheses H1–H15

| Hypothesis | Final status | Evidence |
|---|---|---|
| H1 MFA incomplete | Confirmed in source; live not verified | Middleware returns `mfa_required`; dashboard now gives a visible re-authentication path. |
| H2 wrong role/assignment | Confirmed behavior; live not verified | Role restrictions and stable error codes; role/MFA tests cover key list/detail paths. |
| H3 customer request never reaches server | Not verified live | Local source uses same-origin POST/PUT JSON request bodies; no live request log supplied. |
| H4 validation/duplicate rejection | Confirmed possible; incident not verified | API validation and duplicate error paths covered in tests. |
| H5 status filter hides rows | Refuted for default source path | Default list uses all statuses. |
| H6 bbox/page hides rows | Partly confirmed | Page is bounded; page clamp fixed; pagination still limits rows per page. |
| H7 frontend exception/field mismatch | Refuted for inspected current source; live not verified | Serializer and renderer fields align; syntax and focused tests passed. |
| H8 different deployed code/database | Not verified | No Render branch/SHA or database identity provided. |
| H9 key/verification mistaken for registered business | Confirmed product distinction | Keys awaiting submission are separate from business records and counted in key history. |
| H10 returning update changes existing row | Confirmed intended behavior | Profile updates target linked business; now sorted by updated time. |
| H11 retention/deletion/migration loss | Not verified live | No production DB examined. Source review found no automatic business cleanup path. |
| H12 stale cache | Refuted in inspected app path | Staff APIs use private no-store middleware; proxy/browser behavior unverified. |
| H13 ordering hides older updated row | Confirmed source defect; fixed | Sort defaults to updated timestamp with stable tie-breaker and UI shows last update. |
| H14 wrong route/method causes 403 | Refuted in inspected source | Registered POST list and GET detail paths match dashboard calls; actual live response not supplied. |
| H15 public consent hides staff rows | Refuted for staff lists | Staff query does not require public consent; public map does. |

## 5. Fixes and regression coverage

| Finding | Change and evidence | Status |
|---|---|---|
| PostgreSQL staff phone edit lock error | Row lock narrowed to the business row (`select_for_update(of=("self",))`); `test_staff_phone_edit_succeeds_with_postgresql_locking`. | Fixed; PG test passed in prior local PG run. |
| Dashboard makes errors look like empty table | Separate messages for MFA, 401, role 403, 5xx, network and genuine empty state; explicit CSRF failure; `test_dashboard_explains_staff_roles_errors_and_csrf_failure`. | Fixed; prior focused test passed. |
| Role/key state unclear | Header shows role/MFA; provider landing explains limited scope; awaiting-submission key count and note added. | Fixed in source; focused tests passed. |
| Updated customer hard to find | Updated timestamp, updated-first default sort, stable tie-breaker and created-time option; `test_staff_list_and_detail_distinguish_mfa_and_role_scope`. | Fixed in source; prior focused tests passed. |
| Paging and N+1 list queries | Clamp page; return page counts; batch key/business lookups and bound list query count; `test_customer_list_query_count_stays_bounded_for_fifty_rows`. | Fixed in source; 50-row query test passed in prior PG run. |
| Duplicate looked like success and consumed session | Explicit conflict message, recoverable session/idempotency retry behavior and PII-free rejection audit; `test_duplicate_keeps_verification_session_for_corrected_retry`, `test_duplicate_is_a_conflict_and_never_a_success_screen`. | Fixed in source; focused tests passed. |
| Duplicate matching rejected neighboring customers | Scope by phone hash, normalized business identity and eligible statuses; radius is named setting; policy tests cover phone/name/status. | Partially fixed: final distance literal remains 30 m; setting >30 m is inconsistent and is open. |
| Ambiguous legacy key | Admin-only explicit reference relink with phone-match guard and audit; dashboard action; `test_admin_can_resolve_ambiguous_legacy_key_and_audit_link`, `test_admin_dashboard_offers_safe_legacy_resolution_action`. | Fixed in source; focused tests passed. |
| Failed submission observability | Log status and error code without PII; test verifies fake phone/name/coordinates are absent. | Fixed in source; test passed. |
| Lock/deploy consistency and diagnostic masking | All installers include lock; diagnostic emits commit and masked fingerprint; tests cover alignment and data masking. | Fixed in source; focused tests passed. |
| Stable staff authorization errors | Return role-specific `error.code` values and test role boundaries. | Improved; full endpoint × role × MFA matrix remains incomplete. |

## 6. UX messages

Dashboard messages are rendered in the customer list region using text content, never interpreted as HTML:

- MFA expired: “Your two-step verification expired. Return to Staff sign in and verify again.”
- Session expired: “Your staff sign-in expired. Sign in again to load customer records.”
- Role denied: “Your staff role cannot see the customer inbox. Sign out and use a dispatcher or admin account.”
- Server unavailable: “The staff server is temporarily unavailable. Try Refresh in a moment.”
- Network error: “The network could not load customer records. Check your connection and try Refresh.”
- True empty results: “No customers match this search.”; unassigned field team: “No jobs are assigned to your account.”
- CSRF state unavailable: “Could not prepare secure sign-in state. Refresh this page and sign in again.” No list request is sent after this failure.
- Duplicate: “This location is already on file. Nothing new was submitted. Your verification is still active; review the business details or pin and try again.”

## 7. Migrations

No Mission 10 schema migration was added. Existing migration reversibility was checked in the earlier temporary PostgreSQL run by migrating forward, backward to `core.0001_initial`, and forward again on a fresh disposable database. No customer data was used or altered.

## 8. Test results and limits

Prior local PostgreSQL run: Django suite **89 passed, 0 skipped**; concurrency regression **20/20 runs passed**; check, migration drift check, fresh-database migration round-trip, focused dashboard/duplicate/role/diagnostic/dependency tests, and frontend syntax passed. Current branch has a later small dashboard legacy-resolution view change covered by focused tests and frontend syntax. The current filesystem no longer has the temporary locked venv/PostgreSQL data directory, and current dependency reinstall is blocked by PyPI DNS. `pip-audit`, Ruff and full-history Gitleaks are not currently available; do not infer a current clean result. Playwright/browser and live smoke tests were not run.

Current in-worktree actions: `git diff --check` passes; `python3 scripts/check_frontend_js.py` passes (5 inline script blocks). A proposed regression for `LOCATION_DUPLICATE_RADIUS_M > 30` could not run because `dj_database_url` is absent from the available local dependency path; it was removed and is not counted as a pass.

## 9. Owner live-check and rollback

1. In Render → service → Deploys, copy only deployed branch and short SHA. Compare that SHA to the reviewed source branch and the owner’s intended release branch. Do not paste environment values.
2. In the browser Network panel after staff sign-in and MFA, inspect `POST /api/admin/businesses`; share only status and `error.code`. Do not share cookies, tokens, body, phone, name, reference, or coordinates.
3. In Render Shell run `python manage.py diagnose_dashboard_data`; share its masked JSON only after reviewing it for acceptable host fingerprint and counts.
4. Use a test-only key and fake customer in the owner-controlled test environment. Confirm submission status, `location.submitted` audit increment, staff list row and location; then test returning update and provider/unassigned field-team explanations.
5. Keep the current known-good deploy SHA from Render before any owner-approved deployment. Roll back by selecting that prior deploy in Render. No migration rollback is needed for this branch; no deploy was done here.

## 10. Open decisions and risks

- Exact deployed Render branch/SHA, live 403 response code, whether submission reached the server, and production DB counts remain **Not verified**.
- Complete every endpoint × role × MFA test pair; review both requested branch Actions runs and their failing job logs.
- Run fresh locked install, `check --deploy` with dummy values, pip-audit, Ruff, full-history Gitleaks, current full PostgreSQL suite and 20 concurrency repeats when network/tooling are available.
- Run Playwright/browser checks and live smoke using only test data after owner setup; do not infer from source tests.
- Fix and test the remaining configurable-radius mismatch before treating duplicate detection as fully configurable.
- Open product decisions remain: exact service boundary, poor-accuracy warning threshold, manual-pin acceptance, large-offset policy, and field-team rights.
- Recovery/legacy key resolution, support responsibility, retention/privacy/legal approval, HTTPS/CSP, backups/restore, and real-device GPS checks require owner evidence.

### Commits

`73b1197`, `2405269`, `1f65c9a`, `36ba483`, `1fcadf5`, `8a94c77`, `1970d7b`, `7d283d5`, `5d12ef3`, `0454738`, `88ea599`, `acadb13`, `dfc19f4`, `c23a563`, `121b271`, `eb10790`, `f36127f`, `1a9acc2`, `7ac2b38`, `4c81353`, `3f0521b`, `2bf5568`, `54f2128`, `1451167`, `54745b8`, `40abd08`, `e29e8f1`.

**Severity totals:** 8 confirmed source findings fixed, 1 confirmed configurable-radius defect remains open; live incident root cause remains unverified. Counts are source findings, not live incidents. The highest-priority owner check is to identify the exact Render branch/SHA and the `error.code` from one staff list request after MFA.
