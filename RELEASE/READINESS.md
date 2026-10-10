# Release Readiness

**Status: NOT PRODUCTION-READY. No release branch or tag was created.**
**Audited commit:** `26f328cd9201cc2d1765de9510eaa67dfec0b16d` (`main` = `origin/main`)
**Working-tree caveat:** the SRS currently open in the IDE is an untracked file and is not included in this commit.

Statuses mean: **Pass** = verified with recorded evidence for this audit; **Fail** = gate is unmet or command failed; **Not tested** = no valid evidence was available. “Fail” includes a blocked check; it does not necessarily mean application behavior is defective.

## Phase C release gates

| Gate | Status | Evidence / blocker |
|---|---|---|
| Clean checkout for candidate | Fail | `SRS.md` is untracked; no clean candidate checkout was prepared. `main` itself has no tracked edits and matches origin. |
| Reproducible dependency install | Fail | `requirements.txt` uses ranges, not exact versions/hashes. Fresh `/tmp` virtualenv install failed because package index DNS/network is unavailable. |
| Dependency vulnerability scan | Not tested | `pip-audit` is unavailable and package index access is unavailable. |
| Production Django deploy check | Fail | `check --deploy` could not load settings: `dj_database_url` is missing in the available local dependency set. No production check results can be claimed. |
| Python compilation | Pass | `python3 -m compileall -q core stocktaking` exited 0. |
| Migration consistency | Not tested | `makemigrations --check --dry-run` was attempted but could not load settings due to missing `dj_database_url`. |
| Empty PostgreSQL migration run | Not tested | No fresh PostgreSQL database was provisioned for this audit. |
| Representative-data migration/rollback | Not tested | No database copy or rollback drill was available; no live database was touched. |
| Full suite on PostgreSQL | Not tested | Test run could not load settings because dependencies are incomplete. Existing `TEST-REPORT.md` reports 7 tests previously run on SQLite, which does not meet this gate. |
| Public API privacy behavior | Not tested in this audit | Seven existing tests are documented in `TEST-REPORT.md`, but no test run was possible here and PostgreSQL suite evidence is absent. |
| Backend permission/security review | Fail | Existing role checks and throttles are present, but full endpoint-by-endpoint tests, MFA, CSP, and complete sensitive-action audit coverage are not verified. MFA is absent per `DEPLOY.md` and `TEST-REPORT.md`. |
| Secret scan | Pass with limitation | Targeted history scan found only test fixture passwords; no real credential found. Gitleaks/trufflehog not installed, so CI/trusted-host full scan remains necessary. |
| Frontend JavaScript syntax | Pass | `node --check` passed for public and staff-login scripts. Staff dashboard passed after replacing its Django template boolean with a rendered boolean. |
| CDN integrity | Fail | Leaflet in the public page lacks SRI; staff Leaflet is pinned with SRI. Other remote geocoding/map services rely on third-party availability/terms. |
| Browser/real-device/map failure checks | Not tested | No browser console run, tile-blocked fallback check, GPS hardware check, Android/iPhone navigation, or accessibility session was performed. |
| Static build/WhiteNoise production check | Not tested | `collectstatic` could not be run under production settings because dependencies are incomplete. |
| Docs and operational recovery | Fail | No changelog/rollback plan previously existed; documents are being added here, but backup/restore, retention, MFA, HTTPS domain, and privacy approval are still unproven/open. |

## SRS Must-have and acceptance status

“Baseline noted” means code/docs indicate a capability but it was not independently validated in this audit. It is not a Pass for release acceptance.

| SRS requirements / criteria | Status | Evidence / open item |
|---|---|---|
| PUB-01–03, customer entry, map layers/search | Not tested | Feature baseline described in SRS/API/docs; browser and service behavior not exercised here. |
| PUB-04–05, consent/rounded public shops and aggregated demand | Not tested | `core/views.py` filters served/consented businesses, rounds coordinates, and filters demand count >= 3; regression suite was not runnable in this environment. |
| CUS-01–12, code, location, review, recovery, errors, retries | Not tested | API and client code contain these flows; full end-to-end checks did not run. Location reliability must not be represented as “99% truth.” |
| STF-01–09, staff login, tables, resizing, editing/navigation | Not tested | UI/API baseline exists; viewport/device review and full role tests remain. |
| STF-10, complete sensitive-action permissions and audit | Fail | Existing audit/role code is partial; full coverage and policy validation remain. |
| STF-11, searchable provider-code history | Not tested | Dashboard/API baseline exists; test and verify with both new and legacy records. |
| STF-12, revoke/history detail; STF-13 MFA; STF-14 reports | Fail | Revoke API exists but UI is incomplete; MFA and reports are outstanding. |
| PRI-01–05, privacy serializers, hashed codes/tokens, consent | Not tested | Source code indicates controls; tests not rerun on supported PostgreSQL. |
| PRI-06–09, notice/legal, retention/removal, logging, backup/incident plan | Fail | Privacy/legal review, retention automation, backup restore proof, and operational controls are open. |
| SRS acceptance 1–8 | Not tested | Requires working test environment and full API/browser suite. |
| SRS acceptance 9–11 | Fail | Audit coverage, device review, paid production setup, backup/restore, privacy/legal and MFA decisions are incomplete. |

## Ordered release blockers

1. **Restore a reproducible build:** use a supported Python version, exact dependency pins (and preferably hashes), and a trusted package source; run `pip-audit`.
2. **Make configuration checks executable:** install complete deps in a clean environment; run `check --deploy`, migration consistency, and static collection. Resolve all warnings and prove production environment settings.
3. **Prove PostgreSQL behavior:** fresh-schema migrations and the full suite on PostgreSQL, including public privacy, role access, audit, code lifecycle, and migration-copy coverage.
4. **Resolve security gaps:** MFA decision and implementation, CSP, complete endpoint authorization/audit review, CDN SRI, and a maintained full-history secret scan.
5. **Resolve owner/legal operations:** retention and removal policy, privacy notice/legal approval for Tanzania/Singapore data location, production hosting budget/region, backup and restore drill, incident/support ownership, approved dispatch/role and code policy.
6. **Validate users/devices:** mobile/desktop accessibility, real GPS and pin correction, Google Maps handoff, and degraded map/geocoder behavior.
7. **Commit the SRS and release evidence through review.** Then rerun every gate on the exact proposed release SHA before creating a protected `production` branch or tag.

Until these blockers are cleared, use free hosting for demos or tightly controlled pilots only. Do not onboard routine real-customer records.
