# Dashboard data-flow release report

**Date:** 16 October 2026
**Branch:** `release/dashboard-data-flow`, created from local `fix/dashboard-data-flow`.
**Live access:** None. Render, Supabase, GitHub Actions and customer data were not accessed. No code fix, push, merge, deployment, or PR creation was performed.

## 1. Verdict

The branch is **not ready for staging verification yet**: Mission 11 requires a fresh install and PostgreSQL baseline before the defect fix, but PyPI DNS is unavailable and the local wheel cache has no project dependencies. The duplicate-radius defect remains open. Earlier Mission 10 PostgreSQL results are historical and explicitly not reused as a current pass. No live cause for missing customer rows is established.

## 2. Root causes of the reported symptoms

| Symptom/candidate | Evidence | Confidence |
|---|---|---|
| Customer rows missing in staff dashboard | Source denies staff list/detail for incomplete MFA (`mfa_required`) and restricted roles; dashboard now renders separate explanations. | Confirmed source paths; live cause Not verified without deployed SHA and request `error.code`. |
| Location shared but row not visible | A successfully submitted location creates a business; a returning key updates its linked business. A key or verified phone alone is not a customer row. | Confirmed source behavior; whether a live submission reached the server Not verified. |
| Old/incorrect code deployed | Render logs supplied earlier lack branch/SHA. Blueprint says `production`, but service settings may override it. | Not verified; compare Render Deploys branch/SHA. |

Owner inputs in Mission 11 §0 are all unknown/not supplied: deploy SHA, before/after masked diagnostics, staff role/MFA status, list error code, customer request statuses, and current network access evidence. `MFA_EXEMPT_SUPERUSER_EMAIL` is read from settings; whether it matches the signed-in account is unknown. No environment values were inspected.

## 3. Phase A: environment and tests

| Check | Result | Evidence |
|---|---|---|
| PyPI / npm / GitHub DNS | Fail / unavailable | `getent ahosts pypi.org`, `registry.npmjs.org`, and `github.com` returned no addresses. |
| Fresh install from `requirements.lock` | Not verified | A fresh `/tmp/m11-venv` was created; pip install could not resolve `asgiref` from PyPI. Existing local wheel files were only for unrelated `cloudinary` and `django-tenants`; no project wheel/download set was found. Per mission, this install subtask stops here. |
| Versions in a fresh current environment | Not verified | No locked install completed. Lock declarations are not reported as installed versions. |
| PostgreSQL | Not tested | Port 55432 returned no response. PostgreSQL 18 binaries exist, but no temporary cluster was initialized or started because the mandatory fresh locked app environment was blocked. |
| `check`, dummy `check --deploy`, migration drift, full suite | Not tested | Stopped after the blocked dependency gate; the existing `.local-deps` lacks `dj_database_url`. |
| Fresh DB migration round-trip and concurrency 20x | Not tested | No current PostgreSQL environment or test run. |
| pip-audit, Ruff, Gitleaks | Not tested | Executables unavailable; no current full-history scan result is claimed. |
| Frontend syntax / `git diff --check` | Pass (current) | `python3 scripts/check_frontend_js.py`: five inline script blocks checked; `git diff --check` clean. |
| Browser suite / screenshots | Not tested | Playwright is not installed; npm DNS is unavailable. No screenshots were produced. |

Mission 10's earlier 89-test and 20/20 concurrency results pre-date its final commits and are not reused as current Mission 11 evidence.

## 4. Phase B: duplicate-radius defect

Source inspection confirms the defect at `core/services.py`: candidate bounds use `LOCATION_DUPLICATE_RADIUS_M`, while the final Haversine comparison uses literal 30 m (around line 82). `acquire_submission_locks` also uses literal 30 m for latitude/longitude cell dimensions (around lines 30–32). The setting is parsed as an integer at startup in `stocktaking/settings/base.py` but has no positive-value or upper-bound validation.

**Tests before/fix:** Not run. The required 100 m / 80 m reproduction, 30 m / 80 m acceptance, 29/31 m boundary tests, concurrency-across-cell-boundary test, and invalid-setting startup tests were not added or run because the fresh dependency gate failed. Consequently no fix was made; there is no before/after pass claim. Existing duplicate scoping code still filters by phone hash, case-insensitive business name, and submitted/reviewed/scheduled/served status; regression re-verification is also Not tested in Mission 11.

## 5. Phase C: browser evidence

| Scenario | Expected | Observed | Screenshot |
|---|---|---|---|
| Dashboard without MFA / wrong role | Visible explanation, not empty table | Not verified in browser; source-focused tests existed in Mission 10. | Not produced |
| Provider / unassigned field team | Account scope explained | Not verified in browser. | Not produced |
| Dispatcher with/without rows | Correct data or genuine empty state | Not verified in browser. | Not produced |
| CSRF request blocked | One error, no list call | Not verified in browser. | Not produced |
| Customer verify/submit/duplicate/expired/validation/500 | Success only on 2xx, distinct failure copy | Not verified in browser. | Not produced |
| New and returning full journey | Staff sees row/location; update sorts first | Not verified in browser. | Not produced |
| 375 px mobile layout | No clipping/overflow | Not verified in browser. | Not produced |

Owner manual checklist: use a local/test deployment with fake records; inspect browser Network and Console for each scenario; verify error text, request status and no false success; capture 375 px screenshots into `RELEASE/evidence/`; never use real customer records.

## 6. Phase D: authorization matrix

The complete endpoint × method × role × MFA table-driven matrix was **Not tested**. Existing tests cover selected role boundaries and staff list/detail behavior (`test_denials_return_codes_that_match_each_role_boundary`, `test_staff_endpoint_role_matrix_for_directory_export_codes_and_audit`, `test_staff_list_and_detail_distinguish_mfa_and_role_scope`), but do not cover every requested pairing. No access was widened. Gaps: all endpoint/method pairs for superuser, admin, admin assistant, dispatcher, key-owning provider, other provider, assigned/unassigned field team, anonymous, each with verified and unverified MFA where applicable.

## 7. Deployed-code comparison and branch handoff

Render's branch/SHA remains unknown. The local release branch starts from `fix/dashboard-data-flow`; this only establishes ancestry locally. Ask the owner to supply the Render Deploys branch and short SHA. If it differs from this branch's source ancestry, do not merge blindly. Create a branch from the deployed SHA and transplant/review the Mission 10 commits there.

Suggested commands after the SHA is known (do not run until reviewed). If the deployed SHA descends from the known base `26282cd`, create a branch from it and transplant the release commits after that base:

```sh
git fetch origin
git switch release/dashboard-data-flow
git switch -c release/dashboard-data-flow-on-render <DEPLOYED_SHA>
git rebase --onto release/dashboard-data-flow-on-render 26282cd release/dashboard-data-flow
```

If the deployed SHA is unrelated to `26282cd`, create a branch at that SHA and cherry-pick the Mission 10 commits listed in `DASHBOARD-FIX-REPORT.md` in order, resolving each conflict by review. Then add the verified Mission 11 fix. Rerun all gates. Prepare a PR into a staging branch first; do not open it until branch provenance and CI results are verified.

## 8. Phase F: release preparation (not executed)

### Pull request draft

**Title:** Stabilize dashboard customer visibility and customer data flow

**Summary:** Add explicit MFA/role/network/error states; make updated records easier to find; bound list queries and paging; make duplicate rejection recoverable and PII-minimized; add admin resolution for ambiguous legacy keys; align install paths to the lock.

**Risk:** Staff authorization and customer submission handling are sensitive. No access was broadened. The configurable-radius inconsistency remains open, so do not approve until its test-first fix and PostgreSQL concurrency test pass.

**Evidence:** Mission 10 earlier local PostgreSQL results: 89 tests, 0 skipped; 20/20 concurrency repetitions; migrations round-trip. These are historical and predate final commits. Mission 11 clean environment and browser evidence are Not tested due unavailable package DNS.

**Rollback:** Redeploy the prior known-good Render SHA. No Mission 10 schema migration was introduced; do not roll back unrelated migrations.

### Blueprint and Render dashboard comparison

Source alignment: `render.yaml` selects `branch: production`, `buildCommand: ./build.sh`, Gunicorn start command, and `/healthz`; `build.sh` installs `requirements.lock`; `requirements.txt` includes the lock; CI installs the same lock. Live dashboard overrides are unknown. Compare branch, build command, start command, health-check path, and **environment variable names only**. Relevant names include `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `DJANGO_DEBUG`, `CSRF_TRUSTED_ORIGINS`, `MFA_EXEMPT_SUPERUSER_EMAIL`, `LOCATION_DUPLICATE_RADIUS_M`, and configured rate/privacy settings. Never paste values.

### Deploy/verify/rollback runbook for owner

1. Record current known-good deploy SHA from Render before a staging/production deploy; currently **unknown** to this workspace.
2. In the approved test environment run `python manage.py migrate --plan`, review it, then `python manage.py migrate` only after owner approval.
3. Run `python manage.py diagnose_dashboard_data`; inspect and share only masked JSON.
4. Submit one fake test customer with a test key; verify `location.submitted` count increases and the authorized staff dashboard shows its row/location. Test a returning update and confirm it sorts first.
5. Sign in with test provider and unassigned field-team accounts; confirm explanatory states.
6. Roll back by redeploying the saved prior SHA. No Mission 10 schema migration needs rollback.

### Release owners / blockers

| Item | Owner to confirm |
|---|---|
| Render branch/SHA and dashboard overrides | Service owner |
| MFA enforcement and recovery owner; superuser exemption applicability | Security/admin owner |
| CSP enforcement and browser validation | Application/security owner |
| Supabase backup and restore evidence | Database owner |
| Privacy notice, retention, deletion and legal approval | Privacy/legal owner |
| Real-device location and 375 px UI tests | Product/QA owner |
| Service boundary, 50 m warning, manual-pin and large-offset policy | Product/privacy owner |
| Field-team assignment and job-state rights | Operations owner |

## 9. Open decisions and risks

Open Mission 6 decisions remain unchanged: approved service boundary, 50 m poor-accuracy warning, manual-pin acceptance, large-offset behavior, and field-team rights. Mission 7 blockers remain: MFA enforcement proof, CSP enforcement, backup/restore, privacy/legal approval, real-device GPS tests. Add current install/test/browser blocks and duplicate-radius bug as release blockers. No production-ready claim is made.

## 10. Commit list and unverified items

No Mission 11 code/test commit was made because the required repro could not run. The release branch was created locally. The inherited Mission 10 commits are listed in `RELEASE/DASHBOARD-FIX-REPORT.md`; the Mission 10 report updates and Mission 11 reports remain uncommitted in the worktree. No push, PR, merge or deployment occurred.

**Not verified:** deployed branch/SHA; before/after diagnostics; live request statuses; signed-in role/MFA and exemption applicability; clean locked environment; PostgreSQL baseline/migrations/concurrency; pip-audit/Ruff/Gitleaks; duplicate-radius repro/fix; full authorization matrix; browser screenshots; live smoke.
**Highest priority:** obtain the Render deployed branch/SHA and one post-MFA list request's status plus `error.code`.
