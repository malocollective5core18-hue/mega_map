# Journey and location trust report

**Date:** 14 October 2026
**Implementation/check update:** 15 October 2026
**Branch:** `feature/user-journeys` (created from `fix/audit-defects` at `d26535e`)
**Scope:** Source review and implementation plan for Mission 6. No live systems or production/customer data were accessed.

## Journey status

| User journey | Status | Evidence / remaining gap |
|---|---|---|
| New customer registration | Gap fixed in source; runtime Not tested | Location capture, editable pin, field-level plausibility validation, consent and idempotent submission are implemented. Browser/device journey unverified. See `docs/USER-JOURNEYS.md` §§1, 3. |
| Returning customer update | Gap fixed in source; runtime Not tested | Reusable-key profile stores location source/accuracy/fix age/offset. Multiple businesses per phone remains an owner/data-model decision. |
| Customer bad paths | Gap fixed in source; runtime Not tested | Duplicate/idempotency 409 and GPS denied/unavailable/timeout paths have distinct handling. Browser assertions are not run. |
| Public visitor | Matches code, with UX gaps | Public map/layers/place and business search/contact flows exist. Copy is English-dominant; exact public privacy/consent context and mobile fit need improvement/testing. See §4. |
| Dispatcher | Matches source with open dispatch/visual gaps | MFA, inbox, customer search/edit/navigation/copy/correction exist. Directory markup and control bindings were restored. Full assignment lifecycle and browser behavior remain open. |
| Service provider | Matches code | MFA, phone-bound key creation, own key history and revoke flow exist. Real browser and compact fit are not tested. See §6. |
| Admin assistant / superuser | Matches code, with role-scope distinction | Admin assistant can export/audit/list/edit and control public listing, but cannot create staff accounts or issue keys. Superuser can create staff and issue keys. See §7 and screen role matrix. |
| Field team member | Implemented in source; tests/browser Not tested | Superuser can create field-team users. Assigned list/detail restrictions, one-time distance check, and assigned-pin correction are implemented. No staff coordinate is stored. See §8. |

## Part A artifact status

| Artifact | Status | Evidence |
|---|---|---|
| `docs/USER-JOURNEYS.md` | Pass (source reviewed) | Source-cited journeys/errors for eight user types; runtime and visual claims remain Not tested. |
| `docs/UI-SCREEN-SPEC.md` | Pass (source reviewed) | Inventory, field-team permission table, directory restoration, compact-fit status, and remaining visual mismatches. |
| Baseline source review | Pass | `index.html`, staff login/dashboard, Django views/models/serializers/URLs, SRS/API/Architecture/system report and tests inspected read-only before edits. |

## Part B and C status

| Work item | Status | Result |
|---|---|---|
| Registered customer directory | Gap fixed in source | `customersView` markup and role-guarded handlers restore the staff navigation view; runtime still Not tested. |
| 409 client error distinction | Gap fixed in source | Duplicate only succeeds; idempotency conflicts remain visible errors and preserve retry state. |
| GPS denial, unavailable and timeout UI | Gap fixed in source | Distinct messages stop capture watcher; browser permission behavior Not tested. |
| Accuracy circle during customer capture | Implemented in source | Circle uses the device-reported radius around the original fix; visual result Not tested. |
| GPS timestamp, fix age, speed prompt and watcher lifecycle | Implemented in source | Capture lasts ~15 seconds; best fix/time retained; speed remains client-only; cleanup covers complete/failure/leave/pagehide. Runtime Not tested. |
| Pin offset evidence | Implemented in source | Stores offset and hand-moved flag; no second raw coordinate is stored. Migration execution Not tested. |
| Server region / accuracy / timestamp plausibility checks | Implemented in source; owner boundary approval open | Configurable broad rectangle, maximum accuracy, fix age and future skew return field errors. API tests Not tested. |
| Confidence score | Implemented in source | Uses source, accuracy, age, offset and staff verification; large offset flags and does not block. Threshold decision remains open. |
| Arrival-distance check | Implemented in source; tests/browser Not tested | Assigned field-team endpoint validates one fix, returns approximate distance, and audits only distance band; never persists staff position. |
| Privacy notice update/version | Implemented in source/docs; owner/legal review open | Bilingual `2026-10-location-v1` notice enumerates signals, purpose and no tracking. Retention/legal approval remains open. |
| Playwright journeys/screenshots | Not tested | Registry DNS lookup fails, Playwright package/lockfile could not be generated or verified; no screenshots produced. CI browser gate remains blocked. |
| Device/browser viewport checks | Not tested | No 360×640 / 390×844 screenshots or real-device geolocation permissions were run. |

## Owner decisions before production policy is finalized

1. Approve the exact service boundary. Current broad Tanzania rectangle overlaps neighboring countries; replace it with the actual approved boundary/polygon before production.
2. Confirm the poor-accuracy warning threshold. Mission proposes about 50m; a warning does not prove correctness.
3. Confirm whether manual pin submissions are always accepted. Recommended baseline: accept with a Low confidence label and make the customer confirm, subject to the configured service boundary.
4. Confirm whether large pin offsets should only flag or block. Current baseline flags at a configurable distance and leaves submission available.
5. Approve location privacy notice/version and define retention, correction, and removal details.
6. Confirm assignment ownership and whether field team may update job status. Current field-team role can view/check/correct assigned pins only; dispatcher/admin assignment accepts active dispatcher/admin/field-team staff.

## Manual tests still required

- Android Chrome and iOS Safari: permission grant, deny, browser timeout, OS location disabled, accuracy changes while moving/stationary, and recovery after app backgrounding.
- Verify no geolocation call occurs before a user starts capture; verify `clearWatch` after success, denial, timeout, cancel, retry, and leaving the location step.
- Compare GPS fix with business entrance, drag the pin small/large distances, search a place, use a manual-only pin, and check staff confidence/flags.
- Test out-of-bound, stale, future-skewed, impossible-accuracy requests directly against the API.
- Test a field team assigned job, poor/no-network navigation, distance check, and audited correction only after role policy is approved.
- Capture screenshots at 360×640 and 390×844 for every public/customer/staff screen; verify inner list scrolling, keyboard/focus order, visible focus, reduced motion, touch target size and no page-level overflow.

No location claim should exceed browser-reported estimates and staff confirmation. Browser location does not expose raw GPS satellite measurements, Wi-Fi/cell signals or reliable spoof detection. Native app work is future scope and requires separate permission/privacy review.

## Current check results

| Check | Result | Evidence |
|---|---|---|
| Django suite / API tests | Not tested | Workspace `.venv` lacks `django_otp`; DNS lookup for pypi.org returned no address, so dependency installation is blocked. |
| PostgreSQL migrations and concurrency | Not tested | `pg_isready` reports no server; Docker is not installed. Migration 0009 is authored but not executed. |
| Frontend inline JavaScript syntax | Pass | `python3 scripts/check_frontend_js.py` checked five inline script blocks. |
| Python source compilation | Pass | `py_compile` passed for changed models, serializers, services, views, URLs, tests, settings and migration. |
| `git diff --check` | Pass | No whitespace errors. |
| Ruff | Not tested | Ruff executable is absent in `.venv`; package installation is blocked by unavailable PyPI DNS. |
| Playwright and screenshots | Not tested | No Playwright specs/package lock; npm registry DNS fails, and Chromium Snap refuses to launch because snapd/AppArmor confinement is unavailable. |
| Production/live data | Not tested by design | No Render, Supabase, or customer data was accessed. |
