# Journey and location trust report

**Date:** 14 October 2026
**Branch:** `feature/user-journeys` (created from `fix/audit-defects` at `d26535e`)
**Scope:** Source review and implementation plan for Mission 6. No live systems or production/customer data were accessed.

## Journey status

| User journey | Status | Evidence / remaining gap |
|---|---|---|
| New customer registration | Matches code, with location gaps | Key verification, data entry, explicit location confirmation, consent, idempotent submission and success screens exist. GPS fix metadata and backend plausibility rules are incomplete. See `docs/USER-JOURNEYS.md` §§1, 3. |
| Returning customer update | Matches code, with location gaps | Reusable-key profile loads and updates; latest matching phone record is selected. Same missing capture signals/validation. See §2. |
| Customer bad paths | Gap found | Most errors have user copy. Client mishandles 409 idempotency conflict as success; timeout/unavailable geolocation errors are not distinguished. See §3. |
| Public visitor | Matches code, with UX gaps | Public map/layers/place and business search/contact flows exist. Copy is English-dominant; exact public privacy/consent context and mobile fit need improvement/testing. See §4. |
| Dispatcher | Matches code, with dispatch gaps | MFA, inbox, customer search/edit/navigation/copy/correction exist. No field arrival-distance check or assigned-job queue. See §5. |
| Service provider | Matches code | MFA, phone-bound key creation, own key history and revoke flow exist. Real browser and compact fit are not tested. See §6. |
| Admin assistant / superuser | Matches code, with role-scope distinction | Admin assistant can export/audit/list/edit and control public listing, but cannot create staff accounts or issue keys. Superuser can create staff and issue keys. See §7 and screen role matrix. |
| Field team member | Gap open | No distinct field-team role or assigned-job view exists. Mission asks for arrival distance and audited correction on arrival. See §8. |

## Part A artifact status

| Artifact | Status | Evidence |
|---|---|---|
| `docs/USER-JOURNEYS.md` | Pass | Source-cited current journeys, errors, consent/location behavior, accessibility notes and gaps for all eight user types. |
| `docs/UI-SCREEN-SPEC.md` | Pass | Screen inventory, current role-permissions table, compact-fit status, design-rule audit and known mismatches. |
| Baseline source review | Pass | `index.html`, staff login/dashboard, Django views/models/serializers/URLs, SRS/API/Architecture/system report and tests inspected read-only before edits. |

## Part B and C status

| Work item | Status | Result |
|---|---|---|
| 409 client error distinction | Gap open | Server distinguishes `duplicate` from `idempotency_conflict`; UI currently maps all 409 to duplicate success. |
| GPS denial, unavailable and timeout UI | Gap open | Only permission-denied is handled immediately. |
| Accuracy circle during customer capture | Gap open | Accuracy circle currently exists only for public map's “My location” action. |
| GPS timestamp, fix age, speed prompt and watcher lifecycle | Gap open | No fix timestamp or speed is read/stored/used; acquisition currently lasts up to 30 seconds. |
| Pin offset evidence | Gap open | No `pin_offset_m` or moved-by-hand value is sent or persisted. |
| Server region / accuracy / timestamp plausibility checks | Gap open | Only global coordinate ranges and nonnegative accuracy are validated. |
| Confidence score | Partial | A basic staff band exists from source and accuracy only (`core/views.py:1038-1049`). It needs age, offset and staff verification inputs. |
| Arrival-distance check | Gap open | Staff can set a pin to current position, but there is no distance-to-customer result or dedicated check action. |
| Privacy notice update/version | Gap open | Current text does not enumerate exact browser signals or explicitly state one-time-only/no-background behavior. |
| Playwright journeys/screenshots | Not tested | Playwright configuration, package lock and browser journey suite are absent. Chromium is installed locally; no Playwright runner is available. |
| Device/browser viewport checks | Not tested | No 360×640 / 390×844 screenshots or real-device geolocation permissions were run. |

## Owner decisions before production policy is finalized

1. Approve the exact Tanzania service boundary. Initial configurable bounds can be a broad rectangle for mainland Tanzania plus Zanzibar, but this is not an administrative boundary and overlaps neighboring countries; replace it with an approved polygon or accurate bounds before treating it as authoritative.
2. Confirm the poor-accuracy warning threshold. Mission proposes about 50m; a warning does not prove correctness.
3. Confirm whether manual pin submissions are always accepted. Recommended baseline: accept with a Low confidence label and make the customer confirm, subject to the configured service boundary.
4. Confirm whether large pin offsets should only flag or block. Recommended baseline: flag at a configured distance, keep submission available, ask staff to call/verify; do not claim the customer's physical position.
5. Approve location privacy notice language/version for Kiswahili and English, including exact fields and retention period.
6. Confirm who may create field-team accounts, who assigns jobs, and whether field-team members can update statuses or only view/check/correct assigned jobs.

## Manual tests still required

- Android Chrome and iOS Safari: permission grant, deny, browser timeout, OS location disabled, accuracy changes while moving/stationary, and recovery after app backgrounding.
- Verify no geolocation call occurs before a user starts capture; verify `clearWatch` after success, denial, timeout, cancel, retry, and leaving the location step.
- Compare GPS fix with business entrance, drag the pin small/large distances, search a place, use a manual-only pin, and check staff confidence/flags.
- Test out-of-bound, stale, future-skewed, impossible-accuracy requests directly against the API.
- Test a field team assigned job, poor/no-network navigation, distance check, and audited correction only after role policy is approved.
- Capture screenshots at 360×640 and 390×844 for every public/customer/staff screen; verify inner list scrolling, keyboard/focus order, visible focus, reduced motion, touch target size and no page-level overflow.

No location claim should exceed browser-reported estimates and staff confirmation. Browser location does not expose raw GPS satellite measurements, Wi-Fi/cell signals or reliable spoof detection. Native app work is future scope and requires separate permission/privacy review.
