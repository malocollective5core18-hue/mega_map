# Mauzosheet Location and Service Platform — SRS

**Status:** Working baseline for product and engineering decisions
**Version:** 1.0 · **Date:** 10 October 2026
**Product name in the current customer interface:** Mauzosheet, Hotbano & Services
**Purpose:** Record what users need, what the current system implements, and what must be decided before the next development phase.

## 1. Product purpose

The system helps the company find customer businesses reliably, reduce confusion about where an agent should travel, and manage submitted customers in one staff workspace. A customer verifies access using a company-issued service code and phone number, provides business details, selects a location on a map, reviews the information, and sends it to the company.

Staff use a private dashboard to view customer submissions, inspect and correct map locations, contact customers, manage access codes, and navigate to a business. A separate public map can show served businesses that opted in and aggregated areas of demand.

The system must make it clear that a phone GPS reading is an estimate. Search results identify an area or landmark; the customer still needs to check and confirm the pin at the business entrance.

## 2. Scope

### In scope

- Public map and company contact entry points.
- Phone-and-reusable-key customer sign-in, first-time registration, and profile/location updates.
- Area, landmark, street, and bus-stand place search, followed by map-pin adjustment.
- Customer review, location correction before submission, explicit confirmation, and optional public-map consent.
- Recovery of an in-progress customer submission after an accidental reload in the same browser tab while the verified session remains valid.
- Private staff sign-in, customer map/inbox, registered-customer directory, customer edits, location copying, and map navigation.
- Superuser creation of field-team accounts, dispatcher assignment of jobs, assigned-only field-team access, one-time arrival-distance checks, and audited pin corrections.
- Administrator provider-code issuance and searchable/filterable history, CSV export, and audit log.
- Protection of customer contact and exact location data from public endpoints.

### Out of scope for the current baseline

- Native iOS or Android applications.
- Live agent tracking, route optimization, dispatch ETAs, or proof of arrival.
- Customer passwords, independent key recovery, or account recovery without company assistance.
- Payments, stocktaking/inventory records, or customer messaging automation.
- Automatic geocoder accuracy guarantees. Place search is a discovery aid, not proof of an address or entrance.
- Production operation on free hosting tiers for real customer records.

## 3. User groups and expectations

### 3.1 Customer / business owner

The customer expects to:

- Receive a reusable key for a specific business profile and sign in with that key and its linked phone; a new profile can be registered even when its phone is used by another business, with its own key.
- Enter their name and business name without typing the verified phone again.
- Get a useful location starting point from their device and search for a recognizable area, street, landmark, or bus stand.
- Select a search suggestion, see the pin move, and then adjust the pin onto the actual business entrance.
- Review the name, business, phone, coordinates, place description, and reported GPS accuracy before sending.
- Go back and correct the location or details if anything is wrong; returning customers can sign in again later with their reusable key to update their record.
- Copy/share the coordinates for use in Google Maps if needed.
- Have clear privacy language explaining what is sent to the company and what may appear on the public map.
- Recover typed details and the selected pin if they accidentally reload or leave and return in the same tab before the verification session expires.
- Receive a clear explanation if submission fails, including which field needs attention.

### 3.2 Field agent / dispatcher

The agent expects to:

- Sign in to a private staff interface that works on a phone and desktop.
- See submitted customers in a compact, readable table with a row number, key customer/business information, status, location, and row actions.
- Resize the customer panel so more of the map or table is visible.
- Search and filter customer records and open a selected customer’s details.
- Copy a customer’s coordinates and open directions in Google Maps or another map application.
- See the area/place description and understand whether the pin came from GPS or was manually adjusted.
- See a plain-language indication that GPS accuracy is an estimate, and know when to call the customer before travelling.
- Edit customer/contact/dispatch details when authorized and correct a pin after verifying it in the field.
- Field team members expect to see only assigned jobs, compare a one-time device fix with the job pin, and correct the assigned pin after checking the entrance.

### 3.3 Administrator, admin assistant, and service provider

The superuser expects to:

- Register admin assistants and service providers. Only the superuser can create staff accounts.
- Manage registered customer records and issue reusable business-profile keys checked against the linked phone, with an expiry.
- Review audit history and export customer data through authorized, audited actions.

Admin assistants expect to manage customer records and review searchable key history. They cannot create staff accounts or issue customer keys.

Service providers expect to issue reusable keys for customer phone numbers and manage keys they issued. They do not have access to the full customer directory, staff registration, or customer data exports.

### 3.4 Public visitor

The visitor expects to:

- Understand the company’s service area and find its contact information.
- See only eligible businesses that have been served and opted in, displayed with approximate locations.
- See demand areas only when enough submissions have been aggregated to avoid exposing an individual customer.
- Never see a customer’s phone number, full name, exact address, or exact coordinates.

## 4. System context and principal flows

### 4.1 Customer submission

1. Customer opens the public map and chooses **Share office/business location**.
2. Customer enters the phone number associated with their reusable key and the key itself.
3. Server verifies the pair and issues a short-lived session. If the key is linked to an existing business, that profile and location load for review/editing. A new-profile key starts a separate registration, even when another profile uses the same phone.
4. A new customer enters their name and business name; the verified phone is displayed as read-only. Returning customers can edit their saved details.
5. Customer confirms they are at the business and acquires a GPS estimate or places the pin manually.
6. Customer may search a place name. Selecting a result moves the pin; it does not finish location confirmation.
7. Customer zooms/adjusts the pin, reviews the submitted details, confirms the location, and separately chooses whether to consent to a later approximate public-map listing.
8. Server validates and stores a new submission or updates the existing profile, location, consent, and audit event. Each short-lived session is single-use; the customer key remains reusable until expiry/revocation, and retries use an idempotency key.

### 4.2 Staff customer handling

1. Staff signs in at `/staff/`.
2. Staff opens the customer map/inbox or Registered customers from the staff menu.
3. Staff searches, filters, pages, opens, edits, copies coordinates, or navigates to a customer.
4. Staff can correct details or the pin according to their role. Sensitive reads and changes are audited.
5. Administrators can issue replacement/renewal codes and review code history, exports, and audit events.

### 4.3 Public map

The public map reads from dedicated public API representations. It displays only served, opted-in businesses at rounded coordinates and aggregate demand cells above the minimum aggregation threshold. Staff-only customer submissions never appear as individual public pins.

## 5. Functional requirements

Priorities: **M** = must-have for the next usable release; **S** = should-have; **C** = later/could-have. “Current” describes the inspected project baseline and is not a warranty that a deployed instance is configured correctly.

### 5.1 Public map and branding

| ID | Priority | Requirement | Baseline |
|---|---|---|---|
| PUB-01 | M | The home page shall show a usable map, map controls, service explanation, and clear customer entry point. | Current |
| PUB-02 | M | The customer brand shall show the Chap-Map icon with “Mauzosheet, Hotbano & Services” beneath it, in the compact treatment requested by the owner. | Verify against latest visual build |
| PUB-03 | M | Visitors shall be able to toggle served-shop and demand layers and search for a business/place. | Current; real data/service availability depends on configuration |
| PUB-04 | M | Public shop records shall require served status and public-listing consent and use approximate/rounded coordinates. | Current backend rule |
| PUB-05 | M | Public demand cells shall require at least three requests and shall not disclose individual customer records or exact counts. | Current backend rule |
| PUB-06 | S | Map, contact, search, and layer failures shall produce understandable feedback without blocking customer location submission. | Partially implemented; confirm at release |

### 5.2 Customer access and submission

| ID | Priority | Requirement | Baseline |
|---|---|---|---|
| CUS-01 | M | A customer shall be able to continue only when the entered phone and issued reusable key match. Invalid pairs should not reveal which part was wrong. A key linked to an existing profile loads only that profile; a new-profile key starts a separate profile even if the phone is already used elsewhere. | Implemented with profile-scoped reusable keys; ambiguous legacy shared-phone keys must be reissued |
| CUS-02 | M | A valid key shall authorize a short-lived session for one registration or profile update, with a server-enforced expiry. The customer key itself remains reusable until expiry or revocation. | Current; default maximum is 30 minutes |
| CUS-03 | M | Customer name, business name, verified phone, coordinates, consent, and confirmation shall be validated on the server. | Current |
| CUS-04 | M | The verified phone shall be displayed read-only during the submission flow. | Current |
| CUS-05 | M | The customer shall be able to get a GPS estimate, retry GPS, search place suggestions, tap/drag the pin, and adjust the pin before review. | Current |
| CUS-06 | M | Place suggestions shall be described as search results; the user must check the pin on the business entrance before confirming. | Current UX intent |
| CUS-07 | M | Review shall show name, business, phone, latitude, longitude, selected place, and accuracy/source status before transmission. | Current |
| CUS-08 | M | Public-map listing consent shall be a separate, optional, initially unchecked choice and shall not be implied by submitting a location. | Current |
| CUS-09 | M | The customer shall be able to return to edit details or location from review. | Current |
| CUS-10 | M | After accidental same-tab reload, an unexpired verified draft shall restore the customer’s details, selected pin, and consent choice. Explicit cancel, success, invalidation, and expiry shall clear the draft. | Implemented with browser session storage; device/browser changes are not covered |
| CUS-11 | M | A failed request shall show a useful field-level reason where the server can identify one, and preserve valid unsent form information for correction/retry. | Field-level 422 response recently added; verify on deployment |
| CUS-12 | M | Duplicate or retry requests shall not create duplicate customer records. Expired/used sessions shall be explained and require a fresh company-issued code. | Current backend idempotency/single-use behavior |
| CUS-13 | S | Customer-facing type scale and text treatment shall be visually consistent with the staff workspace while remaining readable on small screens. | Owner requested; confirm in visual review |
| CUS-14 | M | A customer-started, short GPS capture shall retain the best device fix for up to about 15 seconds, show accuracy and an accuracy circle, allow manual pin adjustment, and stop on completion/cancel/exit. | Implemented in source; device/browser test outstanding |
| CUS-15 | M | Customer location payload shall contain fix timestamp, reported accuracy, source, final pin, pin offset and hand-moved state; the server shall calculate age and shall not store original fix coordinates or device speed. | Implemented in source; tests outstanding |
| CUS-16 | M | Server shall reject customer coordinates outside configured service bounds and implausible accuracy/stale/future timestamps with actionable 422 details. | Implemented in source; actual service boundary approval outstanding |

### 5.3 Staff workspace and customer records

| ID | Priority | Requirement | Baseline |
|---|---|---|---|
| STF-01 | M | Staff workspace shall require authentication and distinguish dispatcher and administrator permissions. | Current username/password + session roles |
| STF-02 | M | Staff shall have menu navigation to the customer map/inbox and all registered submitted customers. | Current |
| STF-03 | M | Customer lists shall use compact tables with row numbering, search, pagination, row actions, and responsive layouts. | Current; inspect at supported viewport sizes |
| STF-04 | M | The customer/details panel shall support drag/keyboard resizing so agents can choose more table or map space. | Current |
| STF-05 | M | Registered customer rows shall expose location coordinates and a Copy location action. | Current |
| STF-06 | M | Staff shall be able to edit permitted customer and dispatch details. | Current |
| STF-07 | M | Service providers and the superuser shall issue reusable keys scoped to an individual business profile and checked against its phone; admin assistants may view key history but cannot issue keys. This is customer key sign-in, not a password account. | Implemented |
| STF-08 | M | Staff detail shall provide coordinate-based navigation to Google Maps and available alternative map apps. | Current |
| STF-09 | M | Staff shall see source/accuracy context and be advised to contact customers when location confidence is low. | Current |
| STF-10 | M | Staff exact-data views, updates, pin corrections, exports, code issuance, and audit access shall be permission-checked and auditable. | Partially current; review audit coverage and role policy |
| STF-11 | M | Admin shall be able to search/filter/page issued code records by available customer identity, phone, label, and status. The one-time code secret shall never be returned by history. | Current list; legacy records may only expose last four phone digits until matched to a submitted record |
| STF-12 | S | Admin shall be able to revoke an issued code from the UI and inspect use history. | API has revoke support; UI/history detail needs completion |
| STF-13 | S | Staff authentication shall support enforced MFA and safe account recovery. | Implemented; named superuser exception is configurable |
| STF-14 | S | Admin shall have reports for submission volume, service area, dispatch time, and location quality without exposing unnecessary contact data. | Not implemented |
| STF-15 | M | Superuser shall create field-team accounts; dispatch staff shall assign jobs; field team shall see only assigned jobs, run a one-time arrival-distance check, and correct an assigned pin. The staff member's raw coordinate shall not be persisted. | Implemented in source; API/browser tests outstanding |

### 5.4 Privacy, consent, and data management

| ID | Priority | Requirement | Baseline |
|---|---|---|---|
| PRI-01 | M | Exact coordinates, full customer names, and phone numbers shall be unavailable from public APIs and unauthenticated pages. | Current public serializers; retain automated regression coverage |
| PRI-02 | M | Code secrets shall be stored only as hashes and shown only once at issuance. | Current |
| PRI-03 | M | Verification bearer tokens shall be stored server-side as hashes and expire. | Current |
| PRI-04 | M | Public coordinates shall be rounded, and public demand cells shall be aggregated. | Current |
| PRI-05 | M | Location-processing consent and public-listing consent shall be distinct and recorded with notice version. | Current |
| PRI-06 | M | The privacy notice shall explain collection, purpose, access, public display, retention, and contact/removal process in languages approved by the owner. | Copy/legal review remains open |
| PRI-07 | M | The system shall support a documented retention/anonymization policy and customer data correction/removal requests. | Policy and automation not complete |
| PRI-08 | M | Production monitoring and logs shall avoid names, phone numbers, codes, and exact coordinates. | Must be reviewed for deployment |
| PRI-09 | M | Database backup, restore, authorized access, and incident response shall be defined before real customer operation. | Deployment decision outstanding |

## 6. Non-functional requirements

### Security

- All production access shall use HTTPS, secure/HttpOnly staff session cookies, CSRF protection, host/origin allowlists, and rate limits.
- Staff permissions shall be enforced in the backend, not only by hiding menu items.
- All dynamic text rendered into HTML shall be escaped or inserted as text.
- Secrets and database credentials shall be provided through private deployment settings, never committed to GitHub or placed in frontend code.
- Sensitive records shall use least-privilege access and audit trails. MFA is required for staff, except an owner-approved superuser explicitly named by `MFA_EXEMPT_SUPERUSER_EMAIL`; that password-only exception increases account risk and must remain limited to the owner's active account.

### Privacy and data integrity

- Customer details and exact location must only be disclosed to authorized staff for service purposes.
- A staff arrival check is one user-initiated fix, validates its timestamp/accuracy/service bounds, returns distance, and records only a distance band in the audit event. It does not persist the staff member's coordinate or continue tracking.
- Public display must be consent-based and approximate; revoking public consent must remove the business from the public map.
- Coordinates shall be validated and handled at the precision the API/database accepts; the review and stored/submitted values should agree.
- GPS accuracy is device-reported. The product must not claim “99% accurate” or guarantee the physical truth of a location.
- Submission retry behavior must be safe against duplicate records.

### Usability and accessibility

- Primary flows shall work on small mobile screens and desktop browsers.
- Tables shall show useful information at a glance, shrink/adapt on narrow screens, and allow horizontal scrolling only when unavoidable.
- Interactive controls shall be keyboard reachable, have labels, visible focus, and appropriate screen-reader state.
- Drag resizing shall have keyboard alternatives.
- Errors shall use plain language and say what the user can do next.
- Customer and staff typography shall feel consistent while preserving adequate contrast and readable text.

### Availability and performance

- A customer shall be able to recover a valid in-progress same-tab draft after a reload; drafts expire with server authorization.
- The map shall not block forms or staff table use when third-party map tiles are unavailable.
- Production data shall be stored in managed PostgreSQL, not on an ephemeral web-service filesystem.
- Free hosting tiers may sleep, pause, or lack backup guarantees and are limited to demo/controlled pilot use. Routine production use requires appropriate paid availability, backups, and a tested restore process.

### Maintainability and deployment

- Migrations shall be versioned and deployed repeatably.
- Local development, test, and production settings shall remain separate.
- Render and Supabase credentials shall be managed outside the source tree.
- Every release shall document changes, required migrations, and known limitations.

## 7. Core acceptance criteria

The next release is acceptable for a controlled pilot only when all M requirements are demonstrated:

1. A valid phone/code pair can submit once; an invalid pair cannot submit and receives a generic verification response.
2. A customer can use GPS or search/select a place, move the pin to the business entrance, review all sent values, and correct details before sending.
3. Public-listing consent is separate, unchecked by default, and does not prevent private submission when left unchecked.
4. Reloading the same tab during a valid session restores the draft; cancelling or successful submission clears it; an expired session cannot submit.
5. Invalid server fields are identified in the interface, and a corrected request can be retried without creating duplicate records.
6. Public API responses contain no full customer phone/name/exact location, expose only opted-in served businesses at rounded coordinates, and suppress demand areas under the agreed threshold.
7. Dispatchers can find, inspect, edit, copy coordinates, and navigate to a submitted customer; unauthorized admin actions are rejected by the backend.
8. Admin code history is searchable/filterable and never reveals an already-issued code secret.
9. Sensitive staff operations create the intended audit entries; privacy/logging and access controls are reviewed.
10. The interface is checked on representative mobile and desktop sizes, including compact tables and resizing controls.
11. Before real customer operation, production database backup/restore, HTTPS, MFA decision, retention decision, and privacy/legal approval are complete.

## 8. Decisions required from the owner before the next build phase

These are product decisions, not assumptions for an engineer to silently settle:

1. **Account meaning:** Customer profiles use a reusable business-scoped key plus a short-lived session; a key is also checked against its profile phone. A separate business sharing a phone requires its own key. The system remains key-based, without customer passwords or independent recovery.
3. **Code policy:** Default expiry, use count, renewal process, revoked-code behavior, and who may issue/revoke codes.
4. **Staff roles:** Which roles may view exact phone/location, edit records, copy coordinates, export, issue codes, correct a pin, or view audit logs? Should only administrators see every customer?
5. **Dispatch scope:** Is the next phase only customer registration and navigation, or must it assign named agents/teams, schedule visits, record outcomes, and restrict teams to assigned jobs?
6. **Location rules:** Is manual pin placement always accepted? Should the customer be warned or stopped above an accuracy radius? Which value/source should staff trust when GPS and selected place differ?
7. **Public map:** Exact opt-in wording, served-status eligibility, area/name detail to expose, whether consent can be withdrawn by the customer or staff, and how quickly removal must take effect.
8. **Retention:** Retention duration by record/status, deletion/anonymization process, and response to customer correction/removal requests.
9. **Languages and brand:** Kiswahili-first or bilingual default; approved spelling/capitalization of “Chap-Map” and “Mauzosheet, Hotbano & Services”; final logo asset and typography.
10. **Hosting and launch:** Confirm demo/pilot versus live operations, approved data-hosting region, budget for paid runtime/database/backups, uptime expectations, and support/incident owner.
11. **Operations:** Final company telephone/WhatsApp numbers, staff account lifecycle, MFA/recovery method, backup owners, and training/support contact.

## 9. Recommended next development sequence

1. Resolve decisions 1–6 (identity/access, code lifecycle, staff roles, dispatch and pin acceptance) before changing core data models.
2. Complete security foundations: staff MFA, rate-limit/lockout review, CSP, CSRF/session review, and least-privilege API checks.
3. Complete code lifecycle UX (view use details, revoke, renew, status semantics) and audit coverage.
4. Implement the agreed retention/removal controls and public consent withdrawal behavior.
5. Complete end-to-end validation of form recovery, field-level 422 errors, location edits, and mobile staff/customer UI.
6. Decide whether dispatch assignment/visit workflow and reports belong in this release or a later phase.
7. Only then approve live customer onboarding and a production hosting/backup plan.

## 10. Relationship to implementation documents

- `ARCHITECTURE.md` describes current code boundaries.
- `API.md` documents the API contract.
- `ASSUMPTIONS.md` lists existing assumptions and owner/legal decisions.
- `STAFF-GUIDE.md` describes current staff interactions.
- `DEPLOY.md` documents the Render/Supabase path and free-tier limitations.
- `TEST-REPORT.md` records the last documented verification state and known release gaps.

When this SRS conflicts with legal/privacy requirements, security controls, or current verified code behavior, record the conflict and resolve it through the owner decisions above; do not silently describe an unimplemented capability as complete.
