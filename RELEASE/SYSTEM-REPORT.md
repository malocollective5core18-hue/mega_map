# System Discovery Report

> **Historical snapshot:** This was the read-only baseline for Mission 4. Its original defect findings describe the pre-fix source state. Current fixes, verification results, and remaining limitations are recorded in [`FIX-REPORT.md`](FIX-REPORT.md) and [`READINESS.md`](READINESS.md).

**Audit type:** Read-only source and environment review  
**Observed branch:** `audit-system-discovery-report` (created from `production` at `0b4a94b`)  
**Audit date:** 10 October 2026  
**Scope:** Repository content and locally available commands only. No production database, Render service, or Supabase project was accessed.  
**Privacy:** Secrets, personal contact values, customer data, and `.env` values are intentionally omitted.

## 1. Project overview

### Purpose and entry points

The system is a Django web application for a public location map, phone-bound customer key verification and business-location submissions, and a private staff dispatch/customer workspace. The project documents that purpose in `SRS.md:1-33` and `ARCHITECTURE.md:1-20`.

Entry points verified from source:

- `manage.py:1-10` selects `stocktaking.settings.dev` by default and invokes Django management commands.
- `stocktaking/wsgi.py:1-6` and `stocktaking/asgi.py:1-6` select the same default settings module for WSGI/ASGI.
- `stocktaking/urls.py:20-25` serves `/`, `/staff/`, `/admin/`, and `/api/`.
- `build.sh:1-9` installs requirements, collects static files, runs migrations, creates the cache table, and configures roles.
- `render.yaml:1-30` defines the Render web service and deployment environment names.

### Repository layout (depth 3)

| Path | Purpose evidenced in code/docs |
|---|---|
| `core/` | Django app: API views, models, serializers, security helpers, throttles, tests, admin, and management commands. |
| `core/migrations/` | Five ordered schema migrations (`0001`–`0005`). |
| `core/management/commands/` | `setup_roles` and `refresh_demand_cells` management commands. |
| `stocktaking/` | Django project URL, WSGI/ASGI, and settings modules. |
| `stocktaking/settings/` | Shared, development, production, and test settings. |
| `templates/staff/` | Staff dashboard and sign-in pages. |
| `RELEASE/` | Release readiness, checklist, rollback, audit, branching documents; this report is the only new repository file. |
| Root `index.html` | Public map and customer location flow. |
| Root Markdown files | API, architecture, deployment, assumptions, SRS, staff guide, test report, changelog. |
| Root deployment files | `requirements.txt`, `build.sh`, `render.yaml`, `docker-compose.yml`, `.env.example`. |

### Git evidence

`git status --short --branch` before the audit showed `production...origin/production` with no changes. The new branch was created from that checkout. `git log -15` returned eight commits, so fewer than 15 exist in the local history:

| Commit | Date | Subject |
|---|---|---|
| `0b4a94b` | 2026-10-10 | Add dashboard theme and reliable key generation |
| `7259bd3` | 2026-10-10 | Use email for staff sign in |
| `5179071` | 2026-10-10 | Shorten staff entry label to Sign in |
| `4617ed6` | 2026-10-10 | Move map credits to page footer and add route modes |
| `9bfb8af` | 2026-10-10 | Prepare production deployment |
| `26f328c` | 2026-10-10 | Remove internal agent prompts from repository |
| `1070513` | 2026-10-10 | Prepare Render and Supabase deployment |
| `662b889` | 2026-10-10 | Initial secure project setup |

`render.yaml:5-10` currently specifies branch `main`; this checkout’s production commit is on `production`. Whether the live Render service is configured separately from the blueprint is **Not verified**.

### Source line counts

Counts below are from tracked/application source paths, excluding `.git`, `.local-deps`, bytecode, virtual environments, and this newly written report. They count lines, not nonblank code lines.

| Language / type | Lines |
|---|---:|
| Python | 2,056 |
| HTML (including inline CSS/JS) | 1,797 |
| Markdown | 692 |
| YAML | 50 |
| Shell | 9 |
| Requirements text | 7 |

There are no standalone JavaScript or CSS source files; frontend code is embedded in `index.html` and the staff templates.

## 2. Stack and environment

### Languages, framework, dependencies

- Python runtime observed: `Python 3.14.4` (`python3 --version`). The Render declaration uses Python runtime (`render.yaml:3-4`); the deployed Python version is **Not verified**.
- Django and Django REST Framework versions observed in `.local-deps` metadata / `pip freeze --path .local-deps`: Django `5.2.18`, DRF `3.16.1`, django-cors-headers `4.9.0`, psycopg `3.3.6`, psycopg-binary `3.3.6`, asgiref `3.12.1`, sqlparse `0.6.0`.
- `requirements.txt:1-6` uses version ranges rather than a lock file: Django `>=5.2.18,<5.3`; DRF `>=3.16,<3.17`; django-cors-headers `>=4.7,<5`; psycopg[binary] `>=3.2,<4`; dj-database-url `>=2.3,<3`; whitenoise `>=6.9,<7`; gunicorn `>=23,<24`.
- In this local Python environment, dj-database-url, whitenoise, and gunicorn were not installed under `.local-deps`. The rest of the required dependency set was not independently resolved against package metadata. Render build installs `requirements.txt` (`build.sh:3-4`).
- Project dependency lock/pip freeze is unavailable: `pip freeze --path .local-deps` reflects only the local target directory, not the full resolved production environment. A global `pip freeze` included unrelated system packages and is not presented as the project dependency set.
- JavaScript library: Leaflet `1.9.4`. Staff template loads Leaflet from unpkg and includes SRI (`templates/staff/dashboard.html:6,197`). Public page loads Leaflet from cdnjs with no SRI (`index.html:8,855`). Public place search calls Photon (`index.html:1035-1040`); public map tiles use OSM and Esri services (`index.html:903-918`). Staff map uses Esri satellite tiles (`templates/staff/dashboard.html:208`).
- No Dockerfile was found. `docker-compose.yml` provides a local PostgreSQL 16 Alpine service, not the Django application container (`docker-compose.yml:1-21`).

### Settings modules and environment variable names

- Base: `stocktaking/settings/base.py`; dev: `dev.py`; production: `prod.py`; tests: `test.py`.
- Variables read in source: `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `DB_CONN_MAX_AGE`, `DB_SSL_REQUIRE`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_CONN_MAX_AGE`, `DJANGO_DEBUG`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `PRIVACY_NOTICE_VERSION`, `PROVIDER_CODE_TTL_SECONDS`, `PUBLIC_API_RATE`, `CODE_VERIFY_RATE`, `SUBMISSION_RATE`, `STAFF_LOGIN_RATE`, `FRONTEND_ORIGIN`, `COMPANY_WHATSAPP_NUMBER`, `COMPANY_PHONE_NUMBER`, `LOG_LEVEL` (`stocktaking/settings/base.py:8-139`, `dev.py:1-4`).
- `.env.example` additionally documents local-only PostgreSQL values. `.env` variable names were inspected without printing values; it contains Django configuration and one-time superuser bootstrap variable names. **Values were not read into this report.**
- Base settings default to PostgreSQL and database-backed DRF throttling/cache; test settings switch to in-memory SQLite and locmem cache (`base.py:54-76`, `test.py:1-6`). Production settings require explicit allowed hosts and CSRF origins and enable HTTPS/HSTS/secure cookies (`prod.py:1-16`).

## 3. Data model

All project models are in `core/models.py`. Field types and options below are read from model declarations; no live schema was inspected.

| Model | Fields and relationships | Constraints / custom behavior |
|---|---|---|
| `ProviderCode` (`models.py:8-39`) | `code_hash` char(64), unique; `target_phone_hash` char(64), blank/default empty/indexed; `target_phone_last4` char(4), blank/default empty; `label` char(120), blank; `status` char(12), choices/default active/indexed; `expires_at` datetime; `max_uses`, `use_count` positive ints; `reusable` bool default false; `created_by` nullable FK user SET_NULL; `created_at` auto; `revoked_at` nullable. | Ordered newest first; `(status, expires_at)` index. `accepts()` checks active status, future expiry, and reusable-or-under-use-limit. |
| `VerificationSession` (`models.py:42-55`) | FK code PROTECT; unique token hash; indexed expiry; nullable used time; created time; IP hash. | `(provider_code, expires_at)` index; `usable` property checks unused and future expiry. |
| `CustomerBusiness` (`models.py:58-83`) | UUID PK; unique/indexed public reference; customer name char(160); business name char(200); phone char(20), indexed; status choices/default submitted/indexed; nullable assigned user SET_NULL; notes text blank; created/updated timestamps. | Ordered newest first; `(status, created_at)` index. No unique constraint on phone. |
| `BusinessLocation` (`models.py:86-125`) | OneToOne FK business CASCADE; lat/lng decimal(9,6); nullable accuracy decimal(9,2); source choices; captured timestamp; address/ward/district/region text fields; optional corrected coordinates; nullable corrected-by FK SET_NULL; corrected time; team_verified bool. | Coordinate range, nonnegative accuracy, corrected pair/range constraints; lat/lng index. Navigation properties use corrected values only when team_verified and both corrected coords exist. |
| `Consent` (`models.py:127-133`) | OneToOne FK business CASCADE; notice version; location-processing and public-listing booleans; given timestamp; IP hash. | No custom methods or additional indexes declared. |
| `ServiceVisit` (`models.py:136-145`) | FK business CASCADE; date; team; outcome; nullable created-by FK SET_NULL; created timestamp. | Ordered by visit date then creation time descending. |
| `DemandCell` (`models.py:148-156`) | Unique cell ID; JSONField GeoJSON; positive request count; updated timestamp; level choices. | Updated-time index. |
| `AuditLog` (`models.py:159-169`) | Nullable actor FK SET_NULL; action; object type/id; indexed timestamp; IP hash. | Ordered newest first; `(object_type, object_id, timestamp)` index. |
| `IdempotencyRecord` (`models.py:172-181`) | Unique HMAC key hash; nullable session FK CASCADE; nullable business FK SET_NULL; response status; JSON response body; created timestamp. | Created-time index. |
| `CodeAttempt` (`models.py:184-186`) | Indexed code hash and indexed created timestamp. | No cleanup/retention manager or custom method declared. |

Migrations are `0001_initial`, `0002_codeattempt_idempotencyrecord_session_and_more`, `0003_providercode_target_phone_hash`, `0004_providercode_target_phone_last4`, and `0005_providercode_reusable`, in dependency order (`core/migrations/0001_initial.py` through `0005_providercode_reusable.py`).

`makemigrations --check --dry-run` was attempted but did not reach Django because `dj_database_url` is missing locally. Model-to-migration drift is therefore **Not verified**. No model `save()` override, signal, or custom manager is defined in `core/models.py`.

## 4. API and URL map

All API paths below are prefixed by `/api` (`stocktaking/urls.py:20-25`, `core/urls.py:5-24`). Most response structures follow `API.md:1-25`; endpoint details were checked against `core/views.py`. DRF global permission defaults are `AllowAny`, so access control is explicit per API view or helper (`settings/base.py:120-132`). Public throttles use configured rates; staff mutation throttling is not configured on those views.

| Method/path | View | Authentication, permission, throttle | Input / validation and response | Audit |
|---|---|---|---|---|
| GET `/public/shops` | `public_shops` | AllowAny; PublicThrottle | Required `bbox=west,south,east,north`; optional integer limit clamped 1–500. Returns `{items:[id,name,area,lat,lng]}`; served + public-consent filter, rounded coords. | No |
| GET `/public/shops/search` | `public_shop_search` | AllowAny; PublicThrottle | `q` 2–100 chars; returns same public shop serializer, max 20. | No |
| GET `/public/demand-cells` | `public_demand_cells` | AllowAny; PublicThrottle | Required bbox; returns qualifying `{cellId,geojson,level}` for count >=3, omits count. | No |
| GET `/public/config` | `public_config` | AllowAny; PublicThrottle | No input; returns contact settings and privacy notice version. | No |
| POST `/provider-codes/verify` | `verify_code` | AllowAny, no auth class; VerifyThrottle and per-code failed-attempt check | JSON phone + code; serializer normalizes phone. Generic `{valid:false}` for invalid pair; on success returns bearer token and expiry and, for reusable keys with an existing record, `existingCustomer` profile/location. | Successful existing-customer sign-in is audited; failed attempts go to CodeAttempt. |
| POST `/location-submissions` | `submit_location` | AllowAny, no auth class; SubmissionThrottle | Validated name/business/phone, bounded decimal coordinates, optional accuracy, consent+confirmation true, publicListing bool; requires bearer token and 16–128 char idempotency key. 201 accepted/reference; errors include 400/401/409/410/422. | Submission logs `location.submitted`; idempotency/duplicate path otherwise not all audited. |
| PUT `/customer/profile` | `update_customer_profile` | AllowAny, no auth class; SubmissionThrottle | Same payload/token/key; requires reusable key, phone match, existing phone record; updates newest matching record. 200 updated/reference. | `customer.profile_updated`. |
| GET `/auth/csrf` | `auth_csrf` | AllowAny; no throttle annotation | Returns masked CSRF token. | No |
| POST `/auth/login` | `auth_login` | AllowAny; StaffLoginThrottle; explicit CSRF processing | Email/password strings; requires unique case-insensitive email match, valid active staff-role user. Returns authenticated/role or generic error. | Successful login audited. |
| POST `/auth/logout` | `auth_logout` | IsAuthenticated | No body; logs out and returns authenticated false. | Yes |
| GET/POST `/admin/staff-users` | `admin_staff_users` | IsAuthenticated plus superuser-only helper; no throttle | GET lists admin/service-provider accounts. POST username/email/password/role; validates lengths, fields, password policy, uniqueness; creates user and group. | Creation audited; listing is not. |
| GET `/admin/businesses` | `admin_businesses` | IsAuthenticated plus dispatcher/admin/superuser helper; no throttle | Optional status, q, bbox, page; 50/page; returns exact staff data and accountAccess. | List view audited. |
| GET/PATCH `/admin/businesses/{uuid}` | `admin_business_detail` | IsAuthenticated plus dispatcher/admin/superuser helper; no throttle | GET exact details. PATCH allowlisted names/business/phone/status/notes/assignee/publicListing/corrected coordinate pair; only admin changes publicListing; returns detail. | Reads, writes, and pin correction audited. |
| POST `/admin/businesses/{uuid}/visits` | `admin_business_visits` | IsAuthenticated plus dispatcher/admin/superuser helper; no throttle | Visit date parses as date, team <=160, outcome <=500. Returns id/date. | Yes |
| GET `/admin/export.csv` | `admin_export` | IsAuthenticated plus admin/superuser helper; no throttle | No request fields; all-record CSV including exact coordinates/contact. CSV formula-leading cell values are prefixed with apostrophe. | Export audited. |
| GET/POST `/admin/provider-codes` | `admin_provider_codes` | IsAuthenticated plus admin/superuser/service-provider; providers restricted to own records; no throttle on route | GET q/status/page; 50/page; never returns key secret. POST phone/label/future timezone-aware expiry; creates reusable key and returns its plaintext once. Admin assistants can list, not create; providers can create. | List and issue audited. |
| POST `/admin/provider-codes/{id}/revoke` | `admin_revoke_code` | IsAuthenticated; admin/superuser or owning provider | No body; revokes key, returns `{revoked:true}`. | Yes; repeated revoke also logs. |
| GET `/admin/audit-log` | `admin_audit_log` | IsAuthenticated plus admin/superuser helper | No input; most recent 200 audit records. | Viewing itself is logged. |
| GET `/admin/` | Django admin | Django admin staff/superuser checks | Default Django admin routes. Actual registrations checked in `core/admin.py`; no custom role policy beyond Django admin site was verified. | Django built-in logging behavior not audited here. |
| GET `/`, `/staff/` | `TemplateView` / `staff_home` | Public page open; staff page renders dashboard only for authenticated superuser or recognized group, otherwise sign-in page | HTML, not API. `/staff/` does not itself redirect unauthenticated users. | No |

**Endpoints missing an explicit permission check:** none identified for customer/staff sensitive views in the source review; global `AllowAny` makes every view’s explicit decorator/helper important. `GET /auth/csrf` is intentionally public. Django admin access configuration was not runtime-verified.

## 5. Business flows, step by step with code references

### a) Provider key issuance, hashing, expiry, use, and revocation

1. Superuser/service-provider authorization is checked in `admin_provider_codes` (`views.py:715-722`). Phone is normalized; expiry must parse, be timezone-aware and future; label max is 120 (`views.py:803-812`).
2. `issue_provider_code` generates 16 random characters, HMAC-hashes the key and normalized phone using `SECRET_KEY`, stores last four phone digits and metadata, and returns plaintext only to the caller (`security.py:13-15,31-44`). New dashboard-issued key is reusable (`views.py:812`).
3. Revoke is role-checked, and service providers may revoke only their own issued key (`views.py:817-836`).
4. Changing `DJANGO_SECRET_KEY` changes both code and phone digests; key continuity after secret rotation is **not implemented in the model** and migration/recovery procedure is **Not verified**.

### b) Phone + key verification and token issuance

1. Serializer normalizes Tanzanian local/international phone formats (`serializers.py:6-25`).
2. Verification selects the code row under `select_for_update`, checks active/future expiry/reusable-or-uses-left and constant-time phone digest comparison (`security.py:47-67`, `models.py:31-36`).
3. A random token is created; only SHA-256 token digest is stored, expiry is min(configured TTL, 30 min); use_count increments (`security.py:56-67`).
4. A bad key adds a `CodeAttempt`; five matching-code failures in one hour trigger code-level throttle, in addition to IP-based VerifyThrottle (`security.py:70-72`, `views.py:138-169`). Attempt cleanup is absent from source.
5. Reusable-key login returns the newest matching phone record and location if one exists (`views.py:155-168`).

### c) Customer submission

1. Serializer validates name lengths, phone, coordinate ranges/precision, nonnegative accuracy, booleans, and required consent/confirmation (`serializers.py:27-54`).
2. Submission requires bearer session and 16–128 character idempotency header (`views.py:182-198`).
3. Transaction locks session; same key + same session returns stored response; cross-session reuse returns 409. Expired/used token returns 410 (`views.py:199-214`).
4. Phone digest must match code target. Duplicate check rejects an already-used phone or location within 30m (`views.py:212-220`, `services.py:21-41`).
5. Record, location, consent, and audit row are written; session marked used and idempotency result stored (`services.py:44-66`, `views.py:221-229`).
6. Coordinates are persisted to six decimal places; public business coordinates are rounded to 0.001 degrees (`models.py:91-94`, `services.py:17-19`).

### d) Browser draft recovery

`index.html:1182-1231` saves a draft in `sessionStorage`: token, expiry, current step, name/business/phone, selected position, idempotency key, and public-listing choice. It validates client-side expiry on restore; it does not make a server call until a later API operation. Clear happens on reset/success/known expired/unauthorized submission paths (`index.html:1189-1208,1387-1405`). Storage access exceptions are swallowed.

### e) Staff sign-in, roles, sessions

The staff HTML form collects email/password (`templates/staff/login.html:12-22`). Login checks CSRF, looks up one case-insensitive email, authenticates Django credentials, requires active status and a staff group/superuser, then creates a Django session and audit row (`views.py:353-383`). Base session age is 30 minutes, HTTP-only and SameSite Lax; production marks secure cookies (`settings/base.py:97-104`, `prod.py:10-16`). MFA is not implemented (`SRS.md:163`, `TEST-REPORT.md:14`).

Role enforcement: admin staff user creation is superuser-only; code creation is superuser/provider; provider code reads are own-only for service providers; admin assistants can read code history; customer/business operations permit dispatcher/admin/superuser; export and audit are admin/superuser (`views.py:318-344,386-436,555-584,691-712,715-850`).

### f) Customer edits, pin correction, route links

Reusable-key profile update selects the newest `CustomerBusiness` with the normalized phone and updates its business/location/consent, resetting staff-corrected coordinates (`views.py:237-315`). Staff PATCH supports contact/business/status/notes/assignee, public consent for admins, and paired corrected coordinates (`views.py:587-664`). Navigation URLs are generated from validated coordinates with six decimals for Google driving/walking and other map services (`views.py:455-479`). The page exposes Drive and Walk options (`templates/staff/dashboard.html:211,218`).

### g) Public shops and demand cells

Public shop queries require status `SERVED` and `consent.public_listing=True`; serializer returns reference, business name, ward/district/region concatenation, and 0.001-degree coordinates (`views.py:50-72,74-103`, `services.py:17-19`). Demand refresh groups non-served statuses submitted/reviewed/scheduled into roughly 500m cells and stores only cells with >=3 records (`refresh_demand_cells.py:13-47`). Public endpoint returns polygon, cell ID, and low/medium/high level, but no count (`views.py:105-124`). Public data withdrawal is controlled by admin PATCH `publicListing`; customer profile update can also update consent (`views.py:603-604,650-654,294-300`).

### h) CSV export and audit log

Admin/superuser-only CSV export iterates all customer businesses, includes exact current navigation coordinates and phone, formula-protects text fields, sets attachment and no-store response (`views.py:686-712`). Audit records store actor, action, object type/id, timestamp, and HMAC IP digest (`security.py:17-28`, `models.py:159-169`). Some list/login/key/customer actions are logged; the coverage gaps are detailed below.

## 6. Frontend behaviour

### Public page (`index.html`)

- Main areas: map, area search, menu/sidebar, customer key verification, new/existing customer form, location selection, review, and result panels (`index.html:672-855`).
- App state includes step, verified token/expiry, customer details, current location/accuracy, GPS watch/timer, selected place, idempotency key, and session draft (`index.html:860-885,1182-1245`).
- Map uses Leaflet, OSM street layer, Esri imagery, and Esri boundary/place labels; satellite default and attribution are in map setup (`index.html:903-918` and layer handlers `983-995`).
- Place search goes to Photon/OSM. Home and registration search results are rendered with DOM node creation and `textContent` (`index.html:1035-1167`). Search text is sent to Photon; no geocoder result proves a business entrance.
- Customer pin is draggable; GPS `watchPosition` retains the best device-reported accuracy until threshold or timeout and allows manual pin adjustment (`index.html:999-1022,1323-1362`). This does not guarantee physical truth/99% accuracy.
- Location submission uses `fetchT`, bearer token, idempotency key, and maps server 401/403/409/410/422 errors to messages (`index.html:1170-1175,1375-1408`).
- User content is mostly assigned through `textContent`; fixed template-generated Leaflet div icons and spinner markup use `innerHTML` (`index.html:1017,1090,1175,1331,1475`). These strings are constants. Search result text is not interpolated into HTML. Dynamic staff-inserted markup is separately escaped (below).
- Accessibility includes labeled search combobox/listbox, buttons, error/status text, keyboard handling for menu/drawer/search, focus handling and `aria-expanded`/`aria-busy` state (`index.html:684-706,886-902,1042-1167,1467-1495`). Full screen-reader testing is **Not verified**.
- Uses `sessionStorage` for verified workflow draft; no `localStorage` use in the public page was found. No password/key is placed in localStorage.

### Staff templates and scripts

- `templates/staff/login.html` supplies compact email/password inputs with browser autocomplete, obtains CSRF token, POSTs login and redirects on success (`login.html:12-22`).
- `templates/staff/dashboard.html` owns map/inbox, draggable bottom panel, customer directory, key issuance/history, audit, export, role registration, and theme toggle (`dashboard.html:72-103,197-243`).
- Key issuance has a standalone early submit listener; it calls `preventDefault()`, fetches CSRF, posts JSON, renders one-time key with DOM `textContent`, Copy and Share controls, resets form, and dispatches history refresh (`dashboard.html:104-196`). Static source shows no native form-submit path for this listener; reproduction in a browser is **Not verified**.
- Dashboard theme preference uses `localStorage` key `mauzosheet-staff-theme` (`dashboard.html:71,202-205`).
- `esc()` escapes `& < > " '` before most customer, audit, and code table/detail interpolation into `innerHTML` (`dashboard.html:207 onward`). Fixed literals and validated enum/status values are also inserted. A Leaflet tooltip receives `esc(x.businessName)` at line 217; tooltips treat the string as text by default in Leaflet, but runtime behavior was **Not verified**.
- Inline template values for `IS_ADMIN`, `IS_PROVIDER`, `IS_SUPERUSER` are Django template tags (`dashboard.html:200`); raw extracted template JS therefore cannot be directly parsed until those values are rendered/substituted.
- Keyboard alternative for drawer resize exists via ArrowUp/ArrowDown/Home/End (`dashboard.html:235`). Drag behavior, phone viewport layout, focus trap, and full assistive technology behavior were not browser-tested.
- Public CDN Leaflet resources do not set SRI; staff CDN resources do (`index.html:8,855`; `dashboard.html:6,197`).

## 7. Security and privacy configuration

- Production settings require nonempty `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`, require `DEBUG=False`, enable SSL redirect, HSTS for one year with subdomains/preload, secure session/CSRF cookies, and trust forwarded HTTPS header (`prod.py:1-16`). Live headers/domain/proxy configuration are **Not verified**.
- Base session cookie is HTTP-only, SameSite Lax, 30-minute age, saved every request; base session secure flag is only set in prod (`base.py:97-104`). CSRF cookie secure likewise only prod. CSRF trusted origins/CORS origins are environment-based; credentials CORS false (`base.py:106-108`).
- `X_FRAME_OPTIONS=DENY`, content-type nosniff, strict-origin-when-cross-origin referrer policy (`base.py:100-102`). No CSP setting or CSP middleware was found. MFA is absent.
- Password validators include similarity, minimum length 12, common password, numeric password (`base.py:78-83`). Staff login is rate-limited to configured 5/min by default; verification, public, and submission scopes default 30/hour, 60/min, and 10/hour (`base.py:110-115`). DRF throttle cache is database-backed; anti-brute-force robustness under multiple workers/production cache behavior was not runtime-tested.
- CORS is configured for a same-origin default and credential sharing disabled. Staff browser requests use same-origin cookies (`base.py:106-108`, dashboard request helper at `dashboard.html:209`).
- Public serializers expose only `id` (public reference), business name, area names, rounded lat/lng; no phone/name. Public config exposes configured company phone/WhatsApp and notice version (`views.py:62-72,127-135`). Demand serializer exposes cell ID/polygon/level, not exact count (`views.py:116-124`). Public shop endpoint behavior has unit tests in source but not executed in this environment.
- Staff serializer returns full name, business, phone, exact navigation coordinates, accuracy, status, access state, consent, timestamps; detail adds original/corrected pins, source/address/administrative areas/notes and visit outcomes (`views.py:513-552`). Admin CSV includes all exact phone/location (`views.py:700-707`). These are behind staff/admin role checks in source.
- Code secrets are HMAC-hashed at rest and returned once; bearer verification token stored as SHA-256 digest (`security.py:13-15,31-67`). Phone hashes depend on the same Django secret.
- Audit events do not store names/phone/coordinates as object fields; they store object IDs, however audit and app logging deployment output has not been inspected. Base logger format does not itself show request bodies (`base.py:134-139`). Whether hosting/proxy logs contain sensitive request/query data is **Not verified**.
- No retention/anonymization or code-attempt cleanup process is present in inspected management commands (`core/management/commands/refresh_demand_cells.py`, `setup_roles.py`).
- CSP, production backups/restores, data-region, MFA, retention, legal copy, and incident response are open in `RELEASE/CHECKLIST.md`, `ASSUMPTIONS.md`, and `SRS.md`.

## 8. Tests and checks

### Existing tests

`core/tests.py` defines seven tests across public privacy, demand threshold, code/submission idempotency, invalid code response, phone match, staff permission, staff landing, and pin correction/audit/navigation. The source contains test methods at `core/tests.py:14-109`. There are no explicit tests in that file for staff login CSRF/email ambiguity, key issuance/revocation, reusable customer profile update, concurrent duplicate writes, admin account creation, CSV injection, provider ownership, browser-only form behavior, draft expiry, GPS/search/map error paths, or public-consent withdrawal.

### Commands run and outcomes

| Check | Outcome |
|---|---|
| `python3 --version` | Python 3.14.4. |
| `python3 -m pip freeze --path .local-deps` | Returned the locally available subset shown in Section 2. This is not a complete resolved project environment. |
| `DJANGO_SETTINGS_MODULE=stocktaking.settings.test ... python3 manage.py check` | **Blocked before checks:** `ModuleNotFoundError: No module named 'dj_database_url'` while importing `stocktaking/settings/base.py:4`. Dummy audit secret used; no real secret values printed. |
| `python3 manage.py check --deploy` | **Not run to Django checks** for the same missing import. |
| `python3 manage.py makemigrations --check --dry-run` | **Blocked** for the same missing import; schema drift not verified. |
| `python3 manage.py test` | **Blocked** for the same missing import; tests not executed. |
| PostgreSQL test run | PostgreSQL is unavailable locally: `pg_isready` reported no response at local port 5432. No remote DB was contacted. |
| JavaScript syntax checks | `node --check` passed for all extracted inline scripts after substituting Django template booleans in a `/tmp` copy. This is syntax-only; no browser execution. |
| `pip-audit` | Not installed. |
| `ruff` / `flake8` | Not installed; no project lint configuration found in the root inventory. |

## 9. Defects found

Severity reflects potential impact and likelihood based on source review, not an exploit demonstration. “Confirmed by reading” means the control flow/data model is visible; none of these defects was verified against production data.

### D-01 — Concurrent duplicate customer submissions can pass duplicate detection

- **Severity:** High
- **Evidence:** `core/views.py:199-229` serializes each session, but `services.py:21-41` performs a phone/location duplicate check without locking the candidate phone/location rows; `CustomerBusiness.phone` is indexed but not unique (`core/models.py:67-80`).
- **Why it fails:** Two different valid sessions/idempotency keys can concurrently check the same phone or nearby coordinates before either insert commits, then both write records. The session lock only protects a given verification session; the phone/location has no database uniqueness constraint.
- **Reproduction / expected:** Concurrently submit two requests with different valid code sessions but the same phone or location. Expected one accepted record and one duplicate response.
- **Confidence:** Confirmed by reading; not run against PostgreSQL.

### D-02 — Staff phone edits do not update bound provider-code phone hashes

- **Severity:** High
- **Evidence:** Staff PATCH changes only `CustomerBusiness.phone` (`core/views.py:617-621,650-662`). Provider keys retain an independently stored `target_phone_hash` (`core/models.py:14-16`); customer verification compares against that code phone hash (`core/security.py:51-54`).
- **Why it fails:** Editing a customer’s phone in staff UI makes the existing key continue to accept the old phone, while directory access lookup for the new phone reports no issued key. There is no phone-change workflow to reconcile key hashes, revoke/reissue keys, or notify the customer.
- **Expected:** A phone correction should have explicit, atomic key transfer/revocation/reissue semantics and preserve auditability.
- **Confidence:** Confirmed by reading.

### D-03 — Staff phone edit can create duplicate phone accounts; profile update targets newest only

- **Severity:** Medium
- **Evidence:** No uniqueness constraint exists on `CustomerBusiness.phone` (`models.py:67-80`); staff phone patch validates format but not uniqueness (`views.py:617-621`); reusable profile update selects `.filter(phone=...).order_by("-created_at").first()` (`views.py:271-276`).
- **Why it fails:** Staff can assign a phone already used by another customer. A reusable key then updates only the newest matching business, while verification similarly returns only the newest record (`views.py:155-156`). Other records for that phone become ambiguous/unreachable through the customer flow.
- **Expected:** Enforce the product’s account-to-phone cardinality or provide explicit multi-business selection and update semantics.
- **Confidence:** Confirmed by reading.

### D-04 — Render blueprint branch conflicts with the production branch

- **Severity:** High operational risk
- **Evidence:** Current audit branch was created from `production` at `0b4a94b`; `render.yaml:5-10` says `branch: main`. Local `main` was at older commit `26f328c` per `git branch -vv`.
- **Why it fails:** A Render service created/updated from this blueprint will watch `main`, not receive commits pushed to `production`. The existing live service’s manual branch setting is not accessible here.
- **Expected:** Blueprint branch and Render service’s configured watch branch must agree before relying on automatic production deploys.
- **Confidence:** Confirmed configuration mismatch; impact on currently configured service not verified.

### D-05 — Failed code-attempt records have no cleanup

- **Severity:** Medium
- **Evidence:** Every invalid eligible verification creates a `CodeAttempt` row (`core/security.py:53-55`); the throttle queries the last hour (`security.py:70-72`); no deletion/expiry job exists in inspected management commands. The table stores indexed digests/timestamps (`models.py:184-186`).
- **Why it matters:** Old attempt rows remain indefinitely, growing storage and index cost. Throttle logic only counts recent rows, so keeping older records provides no shown behavior benefit.
- **Expected:** Scheduled pruning or a TTL-capable storage/cache mechanism with a documented retention period.
- **Confidence:** Confirmed by reading; production volume not verified.

### D-06 — Local test/check environment is incomplete and no database is available

- **Severity:** Medium release confidence risk
- **Evidence:** `manage.py check`, migrations check, and tests fail during settings import because `dj_database_url` is absent; `pg_isready` reports no PostgreSQL response. `requirements.txt` does include the missing dependency.
- **Why it matters:** Current source has not been proven to start, pass tests, or migrate in this checkout; deployment build is expected to install requirements but was not run.
- **Expected:** Recreate the declared dependency environment, run Django checks and tests on PostgreSQL, and attach results to release evidence.
- **Confidence:** Confirmed by command output.

### D-07 — Sensitive operational controls are absent or unverified for production

- **Severity:** High release risk
- **Evidence:** No CSP configuration found; SRS says MFA not implemented (`SRS.md:163,184-188`); checklist/readiness documents backup/restore, MFA, privacy/legal and production checks outstanding (`RELEASE/CHECKLIST.md`, `RELEASE/READINESS.md`).
- **Why it matters:** Staff accounts can access exact customer locations and phone numbers. Password/session/rate-limit protections exist, but MFA, CSP, restore evidence, production header verification, and complete audit coverage remain release gaps.
- **Expected:** Resolve controls and demonstrate operation before handling routine production customer records.
- **Confidence:** Confirmed by source/docs that controls are missing/open; live configuration not verified.

### D-08 — Audit coverage omits some sensitive read paths and failed actions

- **Severity:** Medium
- **Evidence:** Customer business list/detail, successful login, code issue/list/revoke, export, audit-log view, profile update, and submission have audit calls (`views.py:168,309,374,582,597,660-662,697,801,835,846`). Staff user listing and customer code verification with no existing profile are not logged; failed authorization/actions are not generally logged. The implementation does not record changed fields/old-new values.
- **Why it matters:** Audit log cannot fully answer who attempted sensitive actions or which exact fields changed, and it cannot attribute a new-account key login to a CustomerBusiness object when no existing record is linked.
- **Expected:** Define event coverage and include appropriate field-level change metadata without copying secrets/PII unnecessarily.
- **Confidence:** Confirmed by reading.

### D-09 — High-accuracy GPS success threshold is not a reliability guarantee

- **Severity:** Low product risk / expectation mismatch
- **Evidence:** Browser watches device geolocation and stops early at configured target or timeout using reported `coords.accuracy` (`index.html:1341-1362`); manual pin bypasses accuracy metadata (`index.html:1020-1022`).
- **Why it matters:** The UI can only present device-reported radius and user-confirmed pin; this is not a 99% probability that the actual entrance is correct. This limit is also documented in SRS (`SRS.md:192-194`).
- **Expected:** Keep language as estimate and require user/agent pin verification; do not promise 99% truth.
- **Confidence:** Confirmed by reading browser API use; actual device accuracy not tested.

### D-10 — Public map assets lack Subresource Integrity

- **Severity:** Low/Medium security hardening
- **Evidence:** Public Leaflet CSS/JS CDN references omit `integrity`/`crossorigin` (`index.html:8,855`); staff Leaflet references do include them (`templates/staff/dashboard.html:6,197`).
- **Why it matters:** Public application code trusts third-party CDN content without browser SRI verification. This increases supply-chain exposure relative to the staff page’s configuration.
- **Expected:** Pin and integrity-protect the public CDN resources or self-host vetted assets.
- **Confidence:** Confirmed by reading.

### D-11 — Long-running code history search scans all businesses per page

- **Severity:** Low/Medium scalability
- **Evidence:** For a page of provider codes, staff code history iterates all businesses with `.iterator()` and HMAC-computes phone hashes until linked codes are found (`core/views.py:771-780`).
- **Why it matters:** Cost can grow with total customer records, and each code-history page can repeatedly scan a large customer table. No measured performance data exists.
- **Expected:** Persist a searchable relation/index or restrict lookup to candidate phones in a database-friendly manner.
- **Confidence:** Confirmed by reading; impact not benchmarked.

### D-12 — Customer one-time account access and update API contracts differ from older docs/tests

- **Severity:** Low documentation/test consistency
- **Evidence:** `API.md` and `SRS.md` describe current reusable keys, but `core/tests.py:45-59` tests one-time single-use semantics using a default non-reusable code. `TEST-REPORT.md` may describe an earlier code state; release report date/version should be checked against current source.
- **Why it matters:** The test confirms legacy one-time behavior, not new reusable key sign-in/update behavior. A passing legacy flow would not establish the current product contract.
- **Expected:** Add focused tests for reusable code reuse until expiry/revocation, profile update, and staff issuance behavior; label legacy one-use coverage clearly.
- **Confidence:** Confirmed by reading test and current implementation; no tests ran.

### Other search results

`rg` found no TODO/FIXME/HACK/XXX markers in project source. The only broad exception catch is staff account field validation (`core/views.py:418-422`) which re-raises unexpected exceptions. No concrete additional unreachable branch was verified. The reported key-generation refresh defect is not reproducible from source alone: the current listener calls `preventDefault()` before the request and renders the key without waiting for the dashboard history event (`templates/staff/dashboard.html:110-112,144-187`). Browser reproduction is **Not verified**.

## 10. SRS compliance matrix

Statuses are based on source/doc review only; anything requiring deployment/browser behavior is labeled Not verified. Requirement definitions are in `SRS.md:122-178`; acceptance criteria are in `SRS.md:221-235`.

| ID | Status | Evidence / note |
|---|---|---|
| PUB-01 | Partial | Public map and entry points exist (`index.html:672-855`); external tile availability/runtime not checked. |
| PUB-02 | Not verified | Visual branding exists; latest rendering/asset sizing not checked. |
| PUB-03 | Partial | Layers, toggles, place/business search implemented (`index.html:924-995,1035-1167`); network availability unverified. |
| PUB-04 | Implemented in source | Served+consented filter and rounded coordinates (`views.py:50-72`). |
| PUB-05 | Implemented in source | Demand rows >=3, count omitted (`views.py:116-124`; refresh command `13-47`). |
| PUB-06 | Partial | Several UI error messages exist; live service failure behavior not browser-tested. |
| CUS-01 | Implemented in source | Phone/code match and generic invalid response (`views.py:138-169`; `security.py:47-67`). |
| CUS-02 | Implemented in source | Reusable key and <=30-minute verification session (`views.py:812`; `security.py:56-67`). |
| CUS-03 | Implemented in source | Serializer and server validations (`serializers.py:27-54`). |
| CUS-04 | Implemented in source | Verified phone displayed read-only in customer flow (`index.html:1308-1320`). |
| CUS-05 | Implemented in source | GPS, Photon search, pin drag/manual map (`index.html:999-1167,1323-1362`). |
| CUS-06 | Implemented in source | Search result/entrance warning (`index.html:1082-1095,1132-1141`). |
| CUS-07 | Implemented in source | Review displays details, coordinates, source/accuracy (`index.html:1364-1371`). |
| CUS-08 | Implemented in source | Separate publicListing field; serializer requires consent/confirmation (`index.html:824-828`; `serializers.py:34-54`). Default unchecked verified in markup at `index.html:818-823`. |
| CUS-09 | Implemented in source | Review actions return to edit flow (`index.html:1433-1452`). |
| CUS-10 | Partial | sessionStorage draft includes fields and expiry (`index.html:1189-1231`); explicit cancel/success clear; browser behavior and session backend alignment not runtime-tested. |
| CUS-11 | Partial | Server includes serializer error details and UI parses 422 (`views.py:183-189`; `index.html:1391-1400`); HTTP deployment not verified. |
| CUS-12 | Partial | Idempotency and single-use session covered in code; duplicate check concurrency gap D-01; reusable updates/test behavior unverified. |
| CUS-13 | Not verified | Customer/staff styling source exists; comparative viewport review not run. |
| STF-01 | Partial | Auth, roles, Django session implemented; MFA absent, live session settings unverified. |
| STF-02 | Implemented in source | Menu navigation includes map/customer views by role (`dashboard.html:74`). |
| STF-03 | Partial | Compact/paged tables and actions present (`dashboard.html:82-93,211-216`); responsive visual review not run. |
| STF-04 | Partial | Pointer and keyboard resize code (`dashboard.html:78,235`); behavior not browser-tested. |
| STF-05 | Implemented in source | Directory returns coordinates and Copy location (`dashboard.html:214`). |
| STF-06 | Partial | PATCH edits customer/dispatch data (`views.py:599-664`); phone uniqueness/key synchronization issue D-02/D-03. |
| STF-07 | Partial | Superuser/provider issue reusable phone-bound key; assistant cannot issue (`views.py:715-814`). User/provider role and Render account setup unverified. |
| STF-08 | Implemented in source | Coordinate routes include Google drive/walk and alternatives (`views.py:455-479`). |
| STF-09 | Implemented in source | Confidence labels/agent instruction (`views.py:481-489`, dashboard detail). |
| STF-10 | Partial | Several backend role checks/audit events exist; audit coverage incomplete (D-08), runtime role tests blocked. |
| STF-11 | Partial | Search/filter/paging, no secret in history, provider ownership and legacy masked phone (`views.py:723-802`); UI revocation/access details incomplete per SRS. |
| STF-12 | Partial | Revoke API exists (`views.py:817-836`); current dashboard history row has no revoke action (`dashboard.html:216`). |
| STF-13 | Missing | MFA not implemented (`SRS.md:163`, no MFA setting/dependency found). |
| STF-14 | Missing | No reporting endpoint/dashboard found in routes or views. |
| PRI-01 | Partial | Public serializer excludes contact/name/exact coords, but runtime endpoint checks not run. |
| PRI-02 | Implemented in source | HMAC hash at rest and one-time issue response (`security.py:31-44`; `views.py:812-814`). |
| PRI-03 | Implemented in source | SHA-256 token digest storage and expiry (`security.py:56-67`). |
| PRI-04 | Implemented in source | Coordinates rounded and demand cells aggregated (`services.py:17-19`; `refresh_demand_cells.py:13-47`). |
| PRI-05 | Partial | Processing and public listing distinct fields, notice version stored; consent text/legal status not approved here (`models.py:127-133`, SRS). |
| PRI-06 | Partial | Interface contains consent explanation; approved bilingual policy, retention and contact/removal wording not established. |
| PRI-07 | Missing | No retention/anonymization or customer deletion/removal workflow found. |
| PRI-08 | Not verified | Application logger format appears safe, but hosting/access logs were unavailable. |
| PRI-09 | Missing / Not verified | No tested backup/restore/incident process in repository; production provider configuration unavailable. |
| AC-01 | Partial | Source enforces phone/key session, but full runtime test suite was blocked. |
| AC-02 | Partial | GPS/search/drag/review paths implemented, not browser/device tested. |
| AC-03 | Implemented in source | Consent is a distinct checkbox, false by default. |
| AC-04 | Partial | Draft restore/clear code exists; reload/expired server session end-to-end not tested. |
| AC-05 | Partial | 422 details and idempotency paths exist; tests blocked and duplicate race found. |
| AC-06 | Partial | Serializer/filter source is privacy-minimizing; public API tests not executed. |
| AC-07 | Partial | Staff edit/copy/navigation and role checks in source; UI/backend tests blocked. |
| AC-08 | Partial | History does not serialize key secret; runtime/filter tests blocked. |
| AC-09 | Partial | Audit calls exist but completeness issue D-08 and no tests executed. |
| AC-10 | Not verified | No representative browser viewport/device test performed. |
| AC-11 | Missing / Not verified | Backup/restore, MFA decision, retention, privacy/legal approval and live HTTPS not evidenced as complete. |

## 11. Open questions and risks

1. Confirm whether Render currently watches `production` or `main`; `render.yaml` says `main` while this repository’s active production branch is separate.
2. Define customer phone-change semantics: transfer/revoke/reissue keys, resolve duplicate phone assignment, and handle multiple businesses per phone.
3. Confirm desired concurrent duplicate behavior and add database-level or transactional protection for same phone/location.
4. Decide whether failed `CodeAttempt` rows need a retention period and schedule cleanup.
5. Decide staff MFA, account recovery, and who owns support/security incidents.
6. Confirm data retention, deletion/anonymization, public consent withdrawal SLA, and privacy notice language.
7. Obtain evidence of production backup/restore, database region, HTTPS/security headers, access controls, and logging redaction. None was verified from this local checkout.
8. Establish a repeatable local dependency environment. `requirements.txt` declares Django runtime packages, but this machine’s `.local-deps` is incomplete, tests were blocked, and PostgreSQL is unavailable.
9. Agree whether public demand polygons at approximately 500m granularity and threshold 3 meet the privacy expectation for every served region; no privacy threat review or geographic data test was performed.
10. User reports a key-generation refresh issue. The current event handler prevents native form submit and displays the generated key before refreshing the history list; no browser reproduction was possible, so the reported issue remains **Not verified**, not confirmed fixed in a live deployment.

**Defect totals:** **High: 4** (D-01, D-02, D-04, D-07); **Medium: 5** (D-03, D-05, D-06, D-08, D-12); **Low/Medium: 3** (D-09–D-11). The five riskiest areas are concurrent duplicate writes, phone/key desynchronization, production branch mismatch, missing production security/backup assurance (MFA/CSP/restore), and incomplete local testability/coverage.
