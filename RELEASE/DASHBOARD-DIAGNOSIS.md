# Dashboard customer and location data-flow diagnosis

**Date:** 16 October 2026  
**Branch:** `diagnose/dashboard-data-flow` (created from local `feature/link-preview` at `9d310f4`)  
**Diagnosis target:** Current checked-out source at `9d310f4`; deployed commit and branch are **Not verified**.  
**Scope:** Read-only source diagnosis, plus the approved read-only command `diagnose_dashboard_data`. No production code was changed. No Render/Supabase connection or customer data was accessed. No secrets or personal data were read or printed.

## 1. Summary

The strongest incident signal is the owner-provided Mission 9 note that staff list and detail calls returned HTTP 403. In the current source, an authenticated staff account without the `mfa_verified_user_id` session marker is explicitly denied by middleware with `error.code=mfa_required`; a staff account without the required role also receives 403. Thus a 403 is not evidence that the customer record is absent. The raw response body and the deployed code were not provided, so the precise live cause remains **Not verified**.

There are two additional confirmed visibility gaps. The service-provider dashboard opens key history instead of the customer inbox, and the customer inbox is restricted to dispatcher/admin/field-team roles. Also, a returning customer updates an existing business row; both staff lists order by its original `created_at`, not its updated timestamp, and the browser does not poll. The location can therefore be saved while not moving to the top or appearing in an already-open screen.

The current source has a valid submission path: a first successful submission creates a business, location and consent and writes `location.submitted` inside the transaction; a returning-customer update writes the submitted coordinates to the business linked to that customer's key and clears the older team correction. Staff list/detail serialization reads the resulting navigation coordinates. Whether Render is running this source is **Not verified**.

## 2. Definitions

| Term / record | Code meaning | Where it appears |
|---|---|---|
| Issued customer key | `ProviderCode`; may have a target phone and an optional business FK. | Key history only. A key not yet used for registration is shown as awaiting customer submission. It is not a submitted customer/business record. |
| Verified phone/session | `VerificationSession`; stores a token hash, expiry and use time. | Not listed as a customer in any staff customer list. A successfully verified phone does not itself create a business. |
| Submitted business/customer | `CustomerBusiness` plus its one-to-one `BusinessLocation` and `Consent`. | Dispatcher/admin inbox and registered-customer directory; field team sees only assigned rows. Staff serializers include the location. |
| Returning-customer profile update | `PUT /api/customer/profile` updates the existing `CustomerBusiness` addressed by `ProviderCode.business_id`. | The same inbox/directory row is updated; no new customer row is created. |
| Staff-created customer | No separate staff customer-creation API was found. Staff edit/assignment/status actions mutate an existing business. Django admin registration of these models was not verified in this read-only pass. | If created through Django admin or another external tool, it would be a `CustomerBusiness`; no distinct dashboard record type exists. |
| Publicly listed shop | A submitted business whose status is `served` and `Consent.public_listing=True`. | Public map/search only. A submitted/reviewed/unconsented customer is intentionally excluded from public results. |

The staff inbox and registered-customers directory list business records, not keys or sessions. The key-history view lists keys and can show an unsubmitted key without a customer record. The service-provider role is taken to key history on dashboard initialization and is denied the general business list endpoint. Public map/search is narrower still: served plus public-listing consent. The staff UI's “registered customers” label does not explain the key-only/session distinction clearly; provider key history does say “Awaiting customer submission.” Evidence: `core/models.py:8-73,76-103,122-152,209-217`; `core/views.py:99-109,1228-1278,1973-1996,2080-2094`; `templates/staff/dashboard.html:237,275`.

## 3. Deployed code identification

**Deployed branch:** Not verified. **Deployed commit:** Not verified. The Render build/runtime excerpts supplied in chat show successful installation, migrations and Gunicorn startup, but contain no Git branch or commit SHA. This assistant has no Render dashboard/log access.

Local comparison:

- Diagnosis source: `feature/link-preview` at `9d310f4`; it includes business-linked keys, MFA middleware and migrations through `0011_providercode_business_scope`.
- `fix/audit-defects` local ref: `d26535e`.
- `feature/user-journeys` local ref: `fc1a0c6`.
- Local `production` and `main` refs: `0b4a94b`. Their `render.yaml` says `branch: main`, `build.sh` installs `requirements.txt`, and `requirements.txt` caps DRF below 3.17. Their tree has no `requirements.lock`.
- The supplied Render install log explicitly says it installed from `requirements.lock` and installed DRF 3.17.2 plus `django-otp` 1.7.4. Current diagnosis branch's lock has those pins; the local `.venv` has DRF 3.16.1 and lacks `django_otp`. This is a meaningful source/environment mismatch, but it does not uniquely identify a branch because Render service settings may differ from the Blueprint.
- Render logs report “No migrations to apply.” This only shows that the database contacted by that build reported no pending migrations for that code. It does not identify the database, prove customer rows exist there, or establish that web requests use the same service/database.

Conclusion: the supplied deployment cannot be mapped to `production`, `fix/audit-defects`, `feature/user-journeys`, or `feature/link-preview` with the evidence available. Treat whether unreviewed code is live as **Not verified**. The owner should read the Render service’s latest deploy details and supply branch plus short SHA, not environment values.

## 4. Data-flow map

```mermaid
sequenceDiagram
  participant C as Customer page (same origin)
  participant A as Django API
  participant DB as Configured database
  participant S as Staff browser
  C->>A: POST /api/provider-codes/verify {phone, code}
  A->>DB: Check key/phone; create hashed-token VerificationSession
  A-->>C: 200 {valid, verificationToken, existingCustomer?}
  alt New business
    C->>A: POST /api/location-submissions + Bearer + Idempotency-Key
    A->>DB: Validate, duplicate check, transaction creates business/location/consent/key link/audit
    A-->>C: 201 {accepted, reference, status}
  else Existing business
    C->>A: PUT /api/customer/profile + Bearer + Idempotency-Key
    A->>DB: Transaction updates linked business/location/consent; clears team correction; audit
    A-->>C: 200 {updated, reference, status}
  end
  S->>A: POST /api/admin/businesses (session cookie + CSRF)
  A->>A: MFA middleware, authentication, role and optional assignment checks
  alt MFA/role failure
    A-->>S: 403; dashboard renders response/error text in the table
  else Authorized
    A->>DB: Query rows, default newest 50 by created_at
    A-->>S: 200 {count, page, items with latitude/longitude}
  end
```

Customer endpoint details: `index.html:1036-1044,1589-1627,1730-1747`; routes `core/urls.py:10-12`; server validation and writes `core/views.py:290-402,418-578`; `core/services.py:77-107`. Customer verification passes phone and code in a same-origin POST body and receives a short-lived bearer token. The browser stores an in-progress draft in `sessionStorage`; customer PII/key/token are not put into the Render URL by these requests. The configured API base is empty, so calls are relative to the page origin; demo mode is `false` in this source (`index.html:1036-1044`).

Staff requests use the same origin, a Django session cookie, JSON bodies and CSRF header. List is `POST /api/admin/businesses`; detail is `GET /api/admin/businesses/<uuid>`. Both are real routes. The reported methods are not a route/method mismatch (`core/urls.py:30-37`; dashboard `templates/staff/dashboard.html:232-237`).

**Network/security observations:** the customer page calls relative `/api/...` endpoints, so it follows the page origin and uses HTTPS when loaded over the Render HTTPS URL. Customer verification and submission use POST/PUT JSON bodies, with bearer token and idempotency key in headers on submit/update. Staff list search values are posted in JSON bodies; the detail path contains only a UUID. Public map bbox and public shop search are also POST bodies. The area-name suggestion text is sent to Photon in its URL query (`index.html:1311-1316`); the app does not send customer name, phone, key or coordinates to that query, but Render does not control Photon logs. CORS is not needed for same-origin app calls; production sets `CSRF_TRUSTED_ORIGINS`, and staff JavaScript sends the CSRF header (`stocktaking/settings/base.py:129-139`; login `templates/staff/login.html:27-29`; dashboard `232`). CSP is `Content-Security-Policy-Report-Only`, so it reports violations but does not block inline dashboard code (`core/middleware.py:33-55`). Production redirects HTTP to HTTPS, trusts Render's forwarded HTTPS header, and exempts `/healthz` (`stocktaking/settings/prod.py:11-29`). The previously shared `HEAD /` 301 is a root health-check redirect; it is not evidence that a customer POST was redirected or changed into GET. No such customer redirect was supplied. Browser/network behavior is **Not verified**.

**Persistence and filtering:** first submission creates `CustomerBusiness` with default status `submitted`, a `BusinessLocation`, and a `Consent` record; it links the provider key to that new business, marks the verification session used, stores the idempotent response and writes `location.submitted` within the atomic block (`core/models.py:76-103,122-152,209-217`; `core/services.py:77-107`; `core/views.py:321-402`). A duplicate instead writes a 409 idempotency response and no business. Returning profile update selects the business from the key's business FK and phone, updates its location and consent, clears staff-corrected coordinates, marks session used, saves idempotency output and writes `customer.profile_updated` (`core/views.py:449-578`). Staff listing reads from the active Django DB connection selected by `DATABASE_URL` or the local PostgreSQL environment settings (`stocktaking/settings/base.py:67-87`); the local test settings override this with in-memory SQLite. One database setting is configured per process, but the live Render build/web DB identity cannot be compared here. Migration 0007 hashes existing business phones using `DJANGO_SECRET_KEY`; migration 0009 adds location-trust fields; migration 0011 adds the business FK and legacy flag without backfilling those links (`core/migrations/0007_customerbusiness_phone_hash.py:8-36`; `0009_businesslocation_location_signals.py:10-33`; `0011_providercode_business_scope.py:10-26`). No CustomerBusiness retention or anonymization command was found; the prune command only deletes CodeAttempt records. Explicit staff DELETE is available to admin/superuser. No Django signal that deletes customer records was found. These findings concern source, not live row state.

## 5. Hypotheses

| ID | Status | Evidence |
|---|---|---|
| H1: incomplete MFA returns 403 | **Confirmed in source; probable live cause, not verified live** | The user-provided Mission text says list and detail requests returned 403. Middleware returns 403 with `mfa_required` when the user is authenticated but the session is not MFA-verified (`core/middleware.py:58-87`). The exact live response body was not provided. |
| H2: wrong role/group or field assignment | **Confirmed behavior; live account not verified** | Inbox requires dispatcher/admin/field-team; service providers are excluded (`core/views.py:594-634`). Field-team list is restricted to assigned rows; another user's detail is 404 (`core/views.py:1228-1235,1333-1335`). |
| H3: customer requests never reach server | **Not verified live; current source path is valid** | Source calls verify and submit/update endpoints as POST/PUT with same-origin routes, token and idempotency key (`index.html:1601,1744-1747`). No customer request logs/body/status were supplied. |
| H4: validation/duplicate rejection | **Confirmed possible; not verified for incident** | Region, GPS accuracy/time and consent checks can return 422 (`core/serializers.py:31-133`). Duplicate within 30 m returns 409, consumes the verification session and stores an idempotency result (`core/views.py:366-383`). |
| H5: status filter hides records | **Refuted for current staff list defaults** | API filters status only when a nonempty status is supplied. Current inbox UI defaults to “All statuses”; directory sends no status (`core/views.py:1235-1239`; `templates/staff/dashboard.html:233,237`). |
| H6: bbox/page hides rows | **Partly refuted / partly confirmed** | Current dashboard list sends no `bbox`; API supports one only when supplied. Both list pages are limited to 50, page 1 by default, and order by `created_at`. A row can be on a later page (`core/views.py:1256-1278`). |
| H7: frontend exception/field mismatch | **Not verified live; no current source mismatch found in inspected path** | Current list renderer reads `latitude`, `longitude`, `locationConfidence`; serializer supplies them (`core/views.py:1165-1185`; dashboard `237,242`). Current map marker collection is an `L.featureGroup`, which supports `getBounds` (`templates/staff/dashboard.html:224,242`). Previously reported `markers.getBounds is not a function` is not reproduced against the deployed build. |
| H8: different deployed code/database | **Not verified; source drift confirmed** | Render log dependency versions match current lock but not the local `.venv`; local `production` blueprint points at `main` and installs `requirements.txt`. Render deploy branch and database identity are not in supplied logs. |
| H9: key/verification mistaken for registered business | **Confirmed product distinction** | Provider key and verification session are separate models; neither creates a business. The key history can list “Awaiting customer submission” (`core/models.py:8-73`; dashboard `237`). |
| H10: returning customer updates instead of creating row | **Confirmed intended behavior and visibility risk** | Reusable key resolves to its linked business; update modifies that row and writes `updated_at`, but staff list orders by `created_at` (`core/views.py:494-578,1275`). No live customer update was inspected. |
| H11: retention/deletion/migration removes rows | **No automatic deletion found in inspected path; live DB not verified** | The pruning command deletes old `CodeAttempt` rows only; demand refresh replaces aggregates only. Staff DELETE exists for an authorized admin. Migrations 0007 and 0009 add/populate phone hash and location metadata; 0011 adds nullable key-business link and legacy flag without a data backfill. |
| H12: cache serves stale data | **Refuted in current app API path; external proxy not verified** | `PrivateStaffNoStoreMiddleware` adds `Cache-Control: no-store, private` to `/api/admin/` and staff pages (`core/middleware.py:6-30`). No application cache is used for list results in inspected views. Render/proxy/browser behavior not tested. |
| H13: time/order puts records far down | **Confirmed for returning updates** | List orders solely by descending `created_at`, while profile update changes `updated_at` (`core/views.py:548,1275`). Existing profile updates do not rise to the first page. |
| H14: 403 caused by request method/path | **Refuted for current source** | `POST /api/admin/businesses` and `GET /api/admin/businesses/<uuid>` are both registered and match dashboard methods (`core/urls.py:31-37`; dashboard `232-237`). A wrong method would be 405, not this code’s MFA 403. |
| H15: public-listing consent hides staff rows | **Refuted for current staff lists; confirmed for public map** | Staff query does not filter consent. Public shop query requires served status and public consent (`core/views.py:99-109,1232-1278`). |

## 6. Bug list

| ID / severity | Evidence and issue | Reproduction / expected behavior | Confidence |
|---|---|---|---|
| B-01 High — MFA 403 can block dashboard data | `core/middleware.py:71-87`; existing test `core/tests.py:952-958`. Authenticated but unverified staff are denied all staff-data URLs. | Sign in with password but do not complete MFA; call list and detail. Expect 403 `mfa_required`; complete MFA and repeat, expecting role-authorized access. | Confirmed by reading; regression test exists but not run here. |
| B-02 High — provider/field-team scope differs from general inbox | `core/views.py:620-634,1228-1235,1333-1335`; dashboard `templates/staff/dashboard.html:275`. Providers start in key history and cannot list businesses; field team sees assigned only. | Compare same fake record with authorized dispatcher/admin, provider, assigned and unassigned field-team. Expected provider receives 403 for general list; field team sees assigned only. | Confirmed by reading; live role not verified. |
| B-03 Medium — returning updates are hard to notice in lists | Update changes existing row and timestamp; both lists sort by `created_at`, 50/page (`core/views.py:548,1266-1277`; dashboard `233,237`). No polling is implemented. | Update an old fake business while list is open. It will not update the open screen until reload/refresh, and when reloaded it remains ordered at its original creation date. Expected latest updates should be easy for staff to find. | Confirmed by reading. |
| B-04 Medium — 30 m duplicate rule is global and ignores phone | `core/services.py:54-74`; `phone` parameter is not referenced. It searches every existing location without filtering business status or phone. | Submit a fake distinct business within 30 m of any existing fake record, including rejected/duplicate/served. Expected product policy is not fully defined; current behavior returns duplicate 409 even for different phones/businesses. | Confirmed by reading; not run. |
| B-05 Medium — duplicate rejection consumes the key session | `core/views.py:369-383`; customer UI turns only `error.code=duplicate` into “Already on file” result (`index.html:1749-1752,1785-1790`). | Send valid fake submission within 30 m. Expect 409 and no new business; current session is marked used, so customer must verify again for another attempt. | Confirmed by reading; not run. |
| B-06 Medium — legacy key cannot be unambiguously assigned for shared phone | `core/migrations/0011_providercode_business_scope.py:10-26` adds nullable business link and `legacy_phone_lookup=True` without backfill; `core/security.py:68-79` links only if exactly one business matches, otherwise verify returns `ambiguous_business` (`core/views.py:216-225`). | On a migrated fake DB, create two businesses for one phone and verify old unlinked key. Expected explicit resolution/reissue; current API returns 409. | Confirmed by reading; migrated production rows not inspected. |
| B-07 Low — page can be empty after dataset changes | `core/views.py:1262-1278`; page is clamped to >=1 but not to last available page. | Open page 2, delete enough fake rows, reload page 2. API can return count smaller than page offset and empty `items`. Expected UI to return to a valid page. | Confirmed by reading; not run. |
| B-08 Low — login can fall through to a doomed data load after CSRF fetch fails | Dashboard `templates/staff/dashboard.html:275`: both `.then` and `.catch` call `load()`. If CSRF retrieval failed, `csrf` remains empty; session-authenticated POST may fail CSRF with 403. Error text is shown, not silently treated as an empty list. | Simulate `/api/auth/csrf` network failure; observe subsequent list attempt. Expected one clear sign-in/session diagnostic, not a second avoidable request. | Confirmed by reading; not browser-tested. |
| B-09 Low — area search sends the typed query to Photon | `index.html:1311-1316`; the customer-entered area query is sent to external Photon via its URL. Customer name/phone/key/coordinates are not included by the app in that query. | Search a fake area and inspect Photon request. Expected area suggestions; avoid typing personal data into the area field. | Confirmed by reading; external provider logs not inspected. |
| B-10 Medium — staff list serializer performs per-row key queries | `core/views.py:1135-1162,1165-1177,1232-1277`. Each business calls `phone_access()`, which performs existence/status queries against provider codes and may count businesses. This creates multiple extra database queries per row (up to 50 rows). | Capture query count for the list with 50 fake records and compare query count as rows grow. Expected query count bounded independently of page size; database timing/impact not measured. | Confirmed by reading; not benchmarked. |

No current-source bug was found where a correctly authorized list response silently becomes an empty list on a server error: list and directory handlers render caught error text in the table (`templates/staff/dashboard.html:233,237`). A live JavaScript exception or old deployed `markers` object remains **Not verified**.

## 7. UX explanations

- A key-only record is not a submitted customer. Key history shows “Awaiting customer submission”; the customer inbox does not list keys or verification sessions.
- After successful first submission, staff can find the business in inbox/directory if their role and MFA allow it. The list includes all statuses and uses name, business, phone or reference search; pages are 50 rows.
- After a returning customer updates a profile, staff must refresh/reopen the view. The updated row stays at its original `created_at` position, potentially on a later page. The customer update does not create a new row.
- A 403 should be interpreted by its response body: `mfa_required` = complete MFA; `not_allowed`/`staff_role_required` = wrong group/role; CSRF HTML/`CSRF Failed` = reload/sign in to renew CSRF state. The HTTP access log alone cannot distinguish these.
- A 409 duplicate means no new business row was created; the UI says it is already on file. A 409 idempotency conflict has a different message and does not mean an existing customer was found.
- A field-team account with no assigned jobs sees no customer rows by design. An unassigned customer's detail is concealed as 404.
- A service provider's dashboard opens key history, not the main inbox. New issued keys can remain key-only until the customer submits.
- Public map/search intentionally omits unserved or non-publicly-consented customers. This does not hide the customer from an authorized staff inbox.

## 8. Reproduction tests and results

**New reproduction tests committed:** None. The issue is environment/session/role dependent; a failing production reproduction cannot be established safely without the deployed commit, fake test key, and PostgreSQL test environment. Existing tests already cover MFA denial, customer submission/profile update, staff role matrix, key ownership, and location corrections: `core/tests.py:650-845,909-1074,1121-1298`.

| Check | Result | Evidence |
|---|---|---|
| PostgreSQL availability | **Fail / unavailable** | `pg_isready` → `/var/run/postgresql:5432 - no response`; Docker is unavailable. |
| Django `check` | **Not tested** | Blocked during Django setup: `ModuleNotFoundError: No module named 'django_otp'` (with a dummy-only `DJANGO_SECRET_KEY`). |
| Django test suite | **Not tested** | Same missing `django_otp`; PostgreSQL required for the concurrency regression is also unavailable. |
| PostgreSQL end-to-end role × MFA matrix | **Not tested** | No PostgreSQL server or local test DB; no Render DB accessed. Existing source test matrix `core/tests.py:1248-1303` was reviewed. |
| Frontend JavaScript syntax | **Pass** | `python3 scripts/check_frontend_js.py` → “Checked JavaScript syntax in 5 inline script blocks.” |
| Diagnostic command Python syntax | **Pass** | `.venv/bin/python -m py_compile core/management/commands/diagnose_dashboard_data.py`. |
| Whitespace | **Pass** | `git diff --check`. |
| Browser requests/console/rendering | **Not tested** | No browser suite available or run. |
| Live request logs/audit evidence | **Not tested** | Render/Supabase not accessible. User supplied only summarized 403s and build logs without SHA or response bodies. |

## 9. Owner live-check instructions

### 9.1 Identify deployed source (do not paste secrets)

In Render, open the web service → **Events/Deploys** → latest successful deploy. Record only the branch and commit SHA shown. Also record the service name and deploy time. Compare that SHA against `production`, `fix/audit-defects`, and `feature/user-journeys`. Do not paste environment-variable values, raw database URLs, cookies or tokens. The current Render blueprint has branch/build information in the repository, but the dashboard can override it.

### 9.2 Run the read-only diagnostic in Render Shell

Use the deployed service's Shell and run:

```sh
python manage.py diagnose_dashboard_data
```

The command prints counts, status/action names, migration label/time, DB vendor, a one-way masked host fingerprint, and a deployment commit if Render exposes `RENDER_GIT_COMMIT` (otherwise `null`). It does not print names, phones, keys, coordinates, IDs, session data, database name/URL or secrets. It performs SELECT/count queries only. The output shape is JSON; counts below are placeholders, not actual production results:

```json
{
  "database": {"vendor": "postgresql", "host_fingerprint": "sha256:<masked>"},
  "deployed_commit": "<short SHA or null>",
  "latest_migration_applied": {"app": "core", "name": "<migration>", "applied_at": "<timestamp>"},
  "provider_codes_by_effective_status": {"active": "<count>"},
  "verification_sessions": {"used": "<count>", "unused_valid": "<count>", "unused_expired": "<count>"},
  "businesses_by_status": {"submitted": "<count>"},
  "businesses_created_by_day_last_14_days": {"<date>": "<count>"},
  "locations": {"present": "<count>", "null": "<count>"},
  "consents": {"present": "<count>", "null": "<count>"},
  "audit_events_by_action_last_14_days": {"location.submitted": "<count>"}
}
```

Share this JSON only after checking the host fingerprint is acceptable. The command's runtime execution against Render is **Not tested** by this diagnosis.

### 9.3 Controlled customer test and redacted evidence

1. Have a staff member with a test-only key issue one test key for a test phone. Record the issue time and key-history row count; do not paste the key.
2. From a test phone, submit one fake customer through the public flow. Record local time to the minute and the returned reference only in a private owner note (do not send a phone, name, reference, key or coordinates here).
3. In Render logs, copy only request method, route path, status and timestamp for `/api/provider-codes/verify`, `/api/location-submissions` or `/api/customer/profile`. Redact query strings and all personal values. These routes should use JSON bodies; do not copy request bodies or Authorization headers.
4. In staff browser DevTools → Network, inspect `POST /api/admin/businesses` and, if opening a row, `GET /api/admin/businesses/<uuid>`. Share only method, path with UUID replaced by `<id>`, status, and the response's `error.code` / generic message. Remove `Cookie`, `Set-Cookie`, `Authorization`, CSRF values and any response PII. Copy console errors with names, phone, IDs and coordinates removed.
5. Confirm the role by its group label (superuser/admin/dispatcher/service_provider/field_team), whether TOTP/recovery verification completed, and whether there is a recent `auth.mfa_succeeded` event for that account. Do not share account email or MFA secrets.
6. From the diagnostic JSON, compare before/after counts for `businesses_by_status`, `locations`, and `location.submitted` audit events. A successful new submission should increase a business status count, location-present count, and `location.submitted` count. A profile update should change no business count but should add `customer.profile_updated` and change the existing record's coordinates; the command intentionally never prints coordinates.

Expected current-source statuses: valid new submission 201; valid profile update 200; validation 422; duplicate proximity 409 with code `duplicate`; expired customer token 410; staff list/detail without MFA 403 `mfa_required`; anonymous staff request generally 401 or session-auth 403; wrong staff role 403; unassigned field-team detail 404. Exact live behavior is **Not verified**.

## 10. Open questions, risks, and ranked likely causes

1. Which exact branch and SHA did Render deploy for the 403 logs, and does that SHA include current MFA/role code?
2. What exact error body accompanies each 403: `mfa_required`, `not_allowed`, `staff_role_required`, or CSRF failure?
3. Which role is affected? Is it a service provider viewing the customer inbox or an unassigned field-team account?
4. Did the customer use a new key (expected new record) or a linked reusable key (expected existing row update)? What status did the verify and submit/update endpoints return?
5. Does the same Render service use one shared database URL for web and build? The actual database identity/data are not available here.
6. Should distinct businesses at the same/nearby storefront be permitted? Current 30 m duplicate logic is global and ignores phone; the desired duplicate policy must be clarified before any fix.
7. Does support want updated customer profiles ordered by `updated_at` or a visible “location updated” timestamp? Current inbox does not expose it.
8. Exact service boundary, warning threshold, pin policies and field-team rights remain owner decisions; this diagnosis does not change them.

**Severity totals:** High 2 (B-01, B-02); Medium 5 (B-03–B-06, B-10); Low 3 (B-07–B-09). These are code-path risks, not confirmed live incident causes.

**Three most likely causes, ranked:**

1. **MFA not completed or stale staff session** — strongest because the owner-provided Mission note says both list and detail requests returned 403, and middleware maps this state directly to 403. Confirm with response JSON `error.code=mfa_required` or an `auth.mfa_succeeded` audit event after completing MFA.
2. **The signed-in role cannot see the general inbox** — likely if the account is a service provider (key-history dashboard only) or field team with no matching assigned job. Confirm the account role and compare one authorized dispatcher/admin request with the same list request.
3. **The customer updated an old existing row, or the page was left open** — a returning-key update changes the existing row; list order remains `created_at`, and the dashboard does not poll. Confirm `customer.profile_updated` at the test time, then manually refresh/search the same business and check its returned coordinates in DevTools without sharing them.

The single best next evidence bundle is the exact deploy branch/SHA plus the redacted status and `error.code` for one `POST /api/admin/businesses` request. No production fix is made by this report.
