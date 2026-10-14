# UI screen specification and inventory

**Baseline:** `feature/user-journeys` based on `fix/audit-defects` (`d26535e`). This describes source-visible behavior only. “Compact fit” refers to required phone viewports 360×640 and 390×844; it is **Not tested** until browser measurements/screenshots are captured.

## Screen inventory

| Screen | Route / source | Users | Current states and exact notable copy | Compact fit |
|---|---|---|---|---|
| Public map | `/`, `index.html:669-715` | Visitor, customer | Map load, tile failure banner, search, menu/layers, support, share. Map banner: “Map could not load. Check your internet connection and reload. You can still share your location below.” | Not tested |
| Public area search | `/`, `index.html:684-685,1035-1122` | Visitor, customer | Searching, suggestions, empty, unavailable; search submitted to Photon. | Not tested |
| Public layer menu | `/`, `index.html:687-702,935-979` | Visitor, customer | Satellite / shops / demand toggles, notes/status, Sign in link. | Not tested |
| Customer key verification | `/`, `index.html:722-735,1264-1305` | New/returning customer | Phone and service key are entered together and checked with one Continue action; no separate customer OTP step. Invalid local fields, checking, invalid/expired/rate-limited/network/server. Sheet follows visual viewport and scrolls focused input above the mobile keyboard (device behavior not tested). | Not tested |
| No-key contact | `/`, `index.html:734-751` | Customer | WhatsApp, call, back, cancel; missing contact config uses JS alert. | Not tested |
| Returning account welcome | `/`, `index.html:737-742,1286-1303` | Returning customer | “Welcome back”, signed-in identity, review/edit and close. | Not tested |
| Customer details | `/`, `index.html:753-766,1308-1320` | New/returning customer | Name/business/verified phone, field errors, continue/back/cancel. | Not tested |
| Location introduction | `/`, `index.html:768-777` | Customer | Kiswahili heading and instruction with English explanation; continue/cancel/back. Permission is requested after continuing. | Not tested |
| Pin confirmation | `/`, `index.html:779-804,1323-1362` | Customer | Search list, selected pin, coordinates, reported accuracy, place, GPS loading/permission/no-fix/poor accuracy, retry/manual pin/review/cancel. | Not tested |
| Customer review | `/`, `index.html:806-832,1364-1371` | Customer | Profile/location summary, privacy and optional public consent, submit/edit/back/cancel. | Not tested |
| Customer completion | `/`, `index.html:834-845,1410-1422` | Customer | Submission/update/dedup success, reference, done/support. | Not tested |
| Customer cancellation confirm | `/`, `index.html:847-852` | Customer | Confirms data will be cleared; continue or cancel. | Not tested |
| Staff sign in / MFA | `/staff/`, `templates/staff/login.html:1-40` | Dispatcher, admin, provider, superuser | Password, MFA challenge, recovery, enrollment QR/manual secret, one-time recovery codes, errors. | Not tested |
| Staff map/inbox | `/staff/`, `templates/staff/dashboard.html:72-93,208-243` | Dispatcher, admin, superuser | Map, list loading/empty/error, search/status filter, pagination, detail drawer. | Not tested |
| Registered customers | `/staff/`, `templates/staff/dashboard.html` | Dispatcher, admin, superuser | Search/page, coordinates/copy, edit, renew-key affordance subject to role. A staff-directory view was missing from the template at the start of Part B; it has now been restored and its bindings are guarded by role. | Not tested |
| Customer details/edit | `/staff/`, `templates/staff/dashboard.html:224-239` | Dispatcher, admin, superuser | Profile/status/notes/assignee, public-listing control for admin, map, visit history/add form, navigation, correction. | Not tested |
| Customer login keys | `/staff/`, `templates/staff/dashboard.html:90-93,110-196` | Provider, admin, superuser | Issue form for provider/superuser; paged/searchable/filterable history, revoke owned keys. Admin assistants only view history. | Not tested |
| Audit log | `/staff/`, `templates/staff/dashboard.html:95` onward | Admin, superuser | Recent 200 audited events, loading/empty/error. | Not tested |
| Customer CSV export | `/staff/`, `templates/staff/dashboard.html:95` onward | Admin, superuser | Download action and status/error. | Not tested |
| Register admin/provider/field-team users | `/staff/`, `templates/staff/dashboard.html` | Superuser | Separate forms and account tables; admin assistants cannot create users. Optional named recovery owner can trigger MFA reenrollment. | Not tested |
| Django admin | `/admin/`, Django admin + `core/admin.py:6-68` | Superuser only | Model admin protected by superuser and MFA-verified middleware. | Not tested |
| Assigned jobs / arrival check | `/staff/`, `templates/staff/dashboard.html`; `/api/admin/businesses` and `/{uuid}/arrival-check` | Field team | Assigned-only job list, detail/navigation, one-time position check, audited pin correction. Browser/runtime behavior remains unverified. | Not tested |

## Role permissions (current backend/UI)

“Verified staff” means authenticated and passed mandatory TOTP or recovery challenge. `core/middleware.py` gates `/api/admin/` and `/admin/`; view permissions further limit each action.

| Capability | Public visitor | Customer key holder | Dispatcher | Admin assistant | Service provider | Field team | Superuser |
|---|---:|---:|---:|---:|---:|---:|---:|
| View public map, consented served shops, aggregate demand | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Verify phone-bound customer key, submit/update own latest matching business | No | Yes | No | No | No | No | No |
| View staff customer map/directory/details | No | No | Yes | Yes | No | Assigned only | Yes |
| Edit customer details/status/notes/assignee | No | No | Yes | Yes | No | No | Yes |
| Correct location pin | No | No | Yes | Yes | No | Assigned only | Yes |
| Change public-listing consent | No | No | No | Yes | No | No | Yes |
| View/export CSV | No | No | No | Yes | No | No | Yes |
| View audit log | No | No | No | Yes | No | No | Yes |
| View provider-code history | No | No | No | Yes (all records) | Yes (own records) | No | Yes |
| Issue/revoke customer key | No | No | No | No | Issue/revoke own | No | Issue/revoke |
| Create staff users | No | No | No | No | No | No | Yes |
| Re-enrol staff MFA | No | No | No | No | No | No | Only configured MFA recovery-owner superuser |
| Django `/admin/` | No | No | No | No | No | No | Yes, with MFA |
| One-time arrival distance check | No | No | No | No | No | Assigned only | No |

References: `core/views.py` role and business handlers, `core/middleware.py`, `core/admin.py`, `templates/staff/dashboard.html`, and `core/models.py:CustomerBusiness.assigned_to`. Field teams can see only assigned records; assignment creation is available through dispatcher/admin record editing and should be reviewed for operational usability.

## Interaction and visual rules audit

| Rule from Mission 6 | Current evidence | Status |
|---|---|---|
| 360×640 and 390×844 fit without whole-page scroll | No browser screenshots or viewport measurements were available in the inspected artifacts. | Not tested |
| Long tables/lists scroll within own area | Staff table containers use `overflow:auto`; verify viewport behavior in Playwright. | Partial; browser not tested |
| Solid thin lines only; no dotted/patterned backgrounds | Source CSS inspection required across templates; not runtime verified. | Not tested |
| Tabular figures for coordinates/counts/phone/reference | No system-wide numeric font audit or computed-style check yet. | Not tested |
| Very subtle depth shadows | Public menu/panels contain shadows; exact visual contrast not measured. | Not tested |
| 48px touch targets | Several compact dashboard row/page actions have explicit heights under 48px. | Gap; no blanket style change because it would break dense-table fit without visual evidence. |
| Visible focus | Focus rules exist but whole interface keyboard inspection was not run. | Not tested |
| Reduced motion | Public page has a reduced-motion media query (`index.html:660-665`); dashboard parity not yet established. | Partial |
| Kiswahili-first with English available | Current public and staff content is mostly English; a few customer steps mix Kiswahili and English; no language toggle. | Gap |
| No unrequested/background location tracking | Customer geolocation APIs are invoked on explicit button actions; there is no `watchPosition` outside the customer capture action. Staff map does not request position. | Matches source; real-device permission test pending |

## UI/error mismatches and remaining verification

1. Fixed: the Registered customers navigation existed but its view markup was missing; startup script also dereferenced absent directory controls for roles that do not have that screen. The view/table and role-guarded control bindings are now present.
2. Fixed in source: 409 duplicate and idempotency conflict receive distinct handling; geolocation permission, unavailable and timeout errors have separate copy; capture shows an accuracy circle and 50m warning.
3. Remaining gap: current text is not consistently bilingual and no Kiswahili/English language switch exists.
4. Playwright configuration, journey tests, and screenshots remain Not tested because Playwright is unavailable locally and npm registry DNS is failing. Pixel-fit, focus, and touch-target compliance remain unverified.

The server confidence band now considers source, accuracy, server-calculated age, offset, and team verification (`core/views.py` `location_confidence`). Part C implementation and owner decisions are tracked in `RELEASE/JOURNEY-REPORT.md`.
