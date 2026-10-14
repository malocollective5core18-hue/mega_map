# UI screen specification and inventory

**Baseline:** `feature/user-journeys` based on `fix/audit-defects` (`d26535e`). This describes source-visible behavior only. “Compact fit” refers to required phone viewports 360×640 and 390×844; it is **Not tested** until browser measurements/screenshots are captured.

## Screen inventory

| Screen | Route / source | Users | Current states and exact notable copy | Compact fit |
|---|---|---|---|---|
| Public map | `/`, `index.html:669-715` | Visitor, customer | Map load, tile failure banner, search, menu/layers, support, share. Map banner: “Map could not load. Check your internet connection and reload. You can still share your location below.” | Not tested |
| Public area search | `/`, `index.html:684-685,1035-1122` | Visitor, customer | Searching, suggestions, empty, unavailable; search submitted to Photon. | Not tested |
| Public layer menu | `/`, `index.html:687-702,935-979` | Visitor, customer | Satellite / shops / demand toggles, notes/status, Sign in link. | Not tested |
| Customer key verification | `/`, `index.html:722-735,1264-1305` | New/returning customer | Invalid local fields, checking, invalid/expired/rate-limited/network/server. Generic invalid key copy. | Not tested |
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
| Registered customers | `/staff/`, `templates/staff/dashboard.html:88-92,214,224-244` | Dispatcher, admin, superuser | Search/filter/page, coordinates/copy, edit, renew-key affordance subject to role. | Not tested |
| Customer details/edit | `/staff/`, `templates/staff/dashboard.html:224-239` | Dispatcher, admin, superuser | Profile/status/notes/assignee, public-listing control for admin, map, visit history/add form, navigation, correction. | Not tested |
| Customer login keys | `/staff/`, `templates/staff/dashboard.html:90-93,110-196` | Provider, admin, superuser | Issue form for provider/superuser; paged/searchable/filterable history, revoke owned keys. Admin assistants only view history. | Not tested |
| Audit log | `/staff/`, `templates/staff/dashboard.html:95` onward | Admin, superuser | Recent 200 audited events, loading/empty/error. | Not tested |
| Customer CSV export | `/staff/`, `templates/staff/dashboard.html:95` onward | Admin, superuser | Download action and status/error. | Not tested |
| Register admin/provider users | `/staff/`, `templates/staff/dashboard.html:96-104` | Superuser | Separate forms and account tables; admin assistants cannot create users. Optional named recovery owner can trigger MFA reenrollment. | Not tested |
| Django admin | `/admin/`, Django admin + `core/admin.py:6-68` | Superuser only | Model admin protected by superuser and MFA-verified middleware. | Not tested |
| Assigned jobs / arrival check | No route/screen | Field team | **Gap:** no assigned-job list, arrival-distance screen, or mobile arrival action. | Planned |

## Role permissions (current backend/UI)

“Verified staff” means authenticated and passed mandatory TOTP or recovery challenge. `core/middleware.py` gates `/api/admin/` and `/admin/`; view permissions further limit each action.

| Capability | Public visitor | Customer key holder | Dispatcher | Admin assistant | Service provider | Superuser |
|---|---:|---:|---:|---:|---:|---:|
| View public map, consented served shops, aggregate demand | Yes | Yes | Yes | Yes | Yes | Yes |
| Verify phone-bound customer key, submit/update own latest matching business | No | Yes | No | No | No | No |
| View staff customer map/directory/details | No | No | Yes | Yes | No | Yes |
| Edit customer details/status/notes/assignee and corrected pin | No | No | Yes (allowlisted fields) | Yes (allowlisted fields) | No | Yes |
| Change public-listing consent | No | No | No | Yes | No | Yes |
| View/export CSV | No | No | No | Yes | No | Yes |
| View audit log | No | No | No | Yes | No | Yes |
| View provider-code history | No | No | No | Yes (all records) | Yes (own records) | Yes |
| Issue/revoke customer key | No | No | No | No | Issue/revoke own | Issue/revoke |
| Create staff users | No | No | No | No | No | Yes |
| Re-enrol staff MFA | No | No | No | No | No | Only configured MFA recovery-owner superuser |
| Django `/admin/` | No | No | No | No | No | Yes, with MFA |
| Assigned job queue / arrival check | No | No | No | No | No | No |

References: `core/views.py:557-623,867-1100`, `core/middleware.py:35-65`, `core/admin.py:6-68`, `templates/staff/dashboard.html:73-106`. The staff UI has no distinct field-team role. “Dispatcher” assignment exists as a nullable user relation, but an assigned-job workflow is not implemented (`core/models.py:86-95`).

## Interaction and visual rules audit

| Rule from Mission 6 | Current evidence | Status |
|---|---|---|
| 360×640 and 390×844 fit without whole-page scroll | No browser screenshots or viewport measurements were available in the inspected artifacts. | Not tested |
| Long tables/lists scroll within own area | Staff table containers use `overflow:auto`; verify viewport behavior in Playwright. | Partial; browser not tested |
| Solid thin lines only; no dotted/patterned backgrounds | Source CSS inspection required across templates; not runtime verified. | Not tested |
| Tabular figures for coordinates/counts/phone/reference | No system-wide numeric font audit or computed-style check yet. | Not tested |
| Very subtle depth shadows | Public menu/panels contain shadows; exact visual contrast not measured. | Not tested |
| 48px touch targets | Several compact dashboard row/page actions have explicit heights under 48px (e.g. 24–32px controls in `templates/staff/dashboard.html:12-13`). | Gap |
| Visible focus | Focus rules exist but whole interface keyboard inspection was not run. | Not tested |
| Reduced motion | Public page has a reduced-motion media query (`index.html:660-665`); dashboard parity not yet established. | Partial |
| Kiswahili-first with English available | Current public and staff content is mostly English; a few customer steps mix Kiswahili and English; no language toggle. | Gap |
| No unrequested/background location tracking | Customer geolocation APIs are invoked on explicit button actions; there is no `watchPosition` outside the customer capture action. Staff map does not request position. | Matches source; real-device permission test pending |

## Known UI/error mismatches to fix in Part B

1. Customer submit handler maps every 409 response to “already received” success (`index.html:1390`), while server also returns 409 for an idempotency key conflict (`core/views.py:322-329,545-555`). Distinguish duplicate success from conflict.
2. Geolocation callback only handles permission-denied error code 1; code 2 (unavailable) and code 3 (timeout) wait for the app timer and then share generic no-fix copy (`index.html:1347-1362`). Map them to clear immediate states while retaining a safe final cleanup path.
3. Customer confirmation map shows the selected pin but not the GPS accuracy circle. The “My location” public-map button does show an accuracy circle (`index.html:1467-1495`), so visually distinguish that visitor-location layer from the customer submission pin.
4. Current text is not consistently bilingual and no Kiswahili/English language control exists.
5. No Playwright configuration, test journeys, or screenshot artifacts exist. Pixel-fit, dialog focus, tab order, and touch-target claims are unverified.

The server already computes a basic staff confidence band from only source and reported accuracy (`core/views.py:1038-1049`). Part C must expand that calculation to include fix age, pin offset and team verification, not introduce a second confidence implementation. Part C implementation gaps and owner decisions are tracked in `RELEASE/JOURNEY-REPORT.md`.
