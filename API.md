# API guide

All routes below are under `/api`; requests and responses are JSON unless the route is a CSV export. Staff routes use same-origin Django session cookies and CSRF tokens. Public endpoints are rate-limited. Errors use `{ "error": { "code": "...", "message": "..." } }` except code verification, whose invalid-code response is deliberately uniform: `{ "valid": false }`.

## Public map

- `GET /public/config` returns configured contact numbers and privacy notice version.
- `GET /public/shops?bbox=west,south,east,north&limit=500` returns served and opted-in shops with 0.001-degree rounded coordinates.
- `GET /public/shops/search?q=...` searches only served, opted-in business names and returns the same rounded, scrubbed public representation.
- `GET /public/demand-cells?bbox=...` returns aggregate GeoJSON cells with at least three requests and no raw counts.

## Customer submission

- `POST /provider-codes/verify` with `{ "phone": "0712345678", "code": "..." }` returns a short-lived bearer verification token only when both match. Phone is normalized and compared against the keyed hash bound to the code; invalid pairs return the same response.
- `POST /location-submissions` uses `Authorization: Bearer <token>` and an `Idempotency-Key` header (16–128 characters). Payload fields: `customerName`, `businessName`, `phone`, `latitude`, `longitude`, optional `accuracyMeters`, `consent:true`, `confirmed:true`, and `publicListing:boolean`. Success returns `201 {accepted,reference}`. Duplicate phone/pin returns `409`; expired or used verification returns `410`; invalid submission returns `422`.

## Staff

- `GET /auth/csrf` obtains a CSRF token; `POST /auth/login` accepts username/password and `POST /auth/logout` ends the session. Sessions expire after 30 minutes.
- `GET /admin/businesses?status=&q=&bbox=&page=` returns up to 50 customer records per page, including the latest phone-bound service-code state as `accountAccess`. `GET /admin/businesses/{uuid}` returns audited exact contact/location data and server-built navigation links.
- `PATCH /admin/businesses/{uuid}` accepts `customerName`, `businessName`, normalized `phone`, status, notes, active staff assignee, admin-only `publicListing`, and paired `correctedLatitude`/`correctedLongitude`. Changes and pin corrections are audited.
- `POST /admin/businesses/{uuid}/visits` accepts `visitDate`, `team`, and `outcome`.
- Admin only: `GET /admin/export.csv`, `POST /admin/provider-codes` with customer `phone`, `label`, `expiresAt`, and `maxUses` (returns a random code once), `GET /admin/provider-codes?q=&status=&page=` for the searchable, filtered issued-code list (never returns the code), `POST /admin/provider-codes/{id}/revoke`, `GET /admin/audit-log`.

Google Maps, Waze, Apple Maps, OpenStreetMap and WhatsApp URLs in staff detail contain coordinate destinations only, generated server-side at six decimals. No business name or phone is included.
