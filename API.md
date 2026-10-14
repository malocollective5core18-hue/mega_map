# API guide

All routes below are under `/api`; requests and responses are JSON unless the route is a CSV export. Staff routes use same-origin Django session cookies and CSRF tokens. Public endpoints are rate-limited. Errors use `{ "error": { "code": "...", "message": "..." } }` except code verification, whose invalid-code response is deliberately uniform: `{ "valid": false }`.

## Public map

- `GET /public/config` returns configured contact numbers, privacy notice version, and public location-warning thresholds. These are guidance values, not evidence of physical accuracy.
- `GET /public/shops?bbox=west,south,east,north&limit=500` returns served and opted-in shops with 0.001-degree rounded coordinates.
- `GET /public/shops/search?q=...` searches only served, opted-in business names and returns the same rounded, scrubbed public representation.
- `GET /public/demand-cells?bbox=...` returns aggregate GeoJSON cells with at least three requests and no raw counts.

## Customer submission

- `POST /provider-codes/verify` with `{ "phone": "0712345678", "code": "..." }` returns a short-lived bearer session only when both match. Newly issued keys are phone-bound and reusable until expiry or revocation. If the phone already has a submitted business, the response also includes its editable profile and saved location as `existingCustomer`. Invalid pairs return the same `{valid:false}` response.
- `POST /location-submissions` registers a new customer using `Authorization: Bearer <token>` and an `Idempotency-Key` header (16–128 characters). Payload fields include `customerName`, `businessName`, `phone`, `latitude`, `longitude`, `accuracyMeters`, `locationSource` (`gps` or `manual_pin`), `fixTimestamp` (device fix time), `pinOffsetMeters`, `pinMovedByHand`, `consent:true`, `confirmed:true`, and `publicListing:boolean`. Server checks configured service bounds, accuracy maximum, and fix age/skew; it stores the calculated age, final location, source and offset, never the original GPS coordinate or speed. Success returns `201 {accepted,reference}`.
- `PUT /customer/profile` uses the same bearer session and payload to update the matching registered phone's details, location, and public-listing consent. Success returns `200 {updated,reference}`. Update retries with the same idempotency key return the original result. Expired or used verification sessions return `410`; invalid submission returns field-level `422` details.

## Staff

- `GET /auth/csrf` obtains a CSRF token. `POST /auth/login` accepts email/password and starts mandatory staff MFA: it returns `mfaEnrollmentRequired` for accounts without a confirmed authenticator or `mfaRequired` for enrolled accounts. A password-only session cannot read staff APIs or Django `/admin/`.
- `POST /auth/mfa/enroll` returns an authenticator provisioning URI, QR SVG data URL, and manual Base32 key for the authenticated but not yet verified staff user. `POST /auth/mfa/confirm` verifies the initial TOTP and returns ten recovery codes once. Recovery codes are stored as Django password hashes, consumed once, and never returned by history APIs.
- `POST /auth/mfa/verify` completes the five-minute password-plus-TOTP challenge. `POST /auth/mfa/recovery` completes it with an unused recovery code. Invalid factors use a generic response; five failures lock the account for 15 minutes. Both successful and failed MFA events are audited without the submitted code.
- `POST /auth/mfa/recovery/regenerate` requires a verified staff session and a fresh TOTP, invalidates outstanding recovery codes, and displays replacements once. `POST /admin/staff-users/{id}/mfa-reenroll` removes a staff member's existing authenticator and recovery codes only for the configured, verified superuser recovery owner. Set `MFA_RECOVERY_OWNER_EMAIL` after the owner is named; with no configured owner the operation fails closed.
- Staff sessions expire after 30 minutes. `POST /auth/logout` ends the session. The Django `/admin/` site is superuser-only and requires the same MFA-verified session. TOTP work has SQLite test coverage; PostgreSQL and browser checks remain outstanding.
- `GET /admin/businesses?status=&q=&bbox=&page=` returns up to 50 customer records per page, including the latest phone-bound service-code state as `accountAccess`. `GET /admin/businesses/{uuid}` returns audited exact contact/location data and server-built navigation links.
- `PATCH /admin/businesses/{uuid}` accepts `customerName`, `businessName`, normalized `phone`, status, notes, active staff assignee, admin-only `publicListing`, and paired `correctedLatitude`/`correctedLongitude`. A phone already assigned to another business is rejected with HTTP 422 (`phone_in_use`). Changes and pin corrections are audited.
- `POST /admin/businesses/{uuid}/visits` accepts `visitDate`, `team`, and `outcome`.
- Field-team member only: `POST /admin/businesses/{uuid}/arrival-check` accepts one current `latitude`, `longitude`, `accuracyMeters`, and `fixTimestamp` for an assigned job. It returns approximate distance and device-reported accuracy, audits only a distance band, and does not persist the staff member's coordinates.
- Superuser only: `GET/POST /admin/staff-users` lists staff accounts or creates an `admin` assistant, `service_provider`, or `field_team`; other roles cannot create staff accounts. Field-team members can only list/open assigned jobs, check distance, and correct an assigned pin.
- Dispatcher/admin/superuser: `GET /admin/assignable-staff` lists active dispatcher, admin, and field-team IDs/names/roles for job assignment. Field-team members cannot list assignees, create visit records, or edit customer profile/status fields.
- Superuser and service providers: `POST /admin/provider-codes` with customer `phone`, `label`, and `expiresAt` returns a reusable random key once. Admin assistants may view/filter the key history but cannot issue keys. `GET /admin/provider-codes?q=&status=&page=` never returns key secrets; providers see only keys they issued and masked phone details. Providers may revoke their own keys; admins and the superuser may revoke any key. Customer history links use indexed HMAC phone digests; changing `DJANGO_SECRET_KEY` requires a rehash migration.
- Admin assistants and superuser: `GET /admin/export.csv`, `GET /admin/audit-log`.

Google Maps, Waze, Apple Maps, OpenStreetMap and WhatsApp URLs in staff detail contain coordinate destinations only, generated server-side at six decimals. No business name or phone is included.
