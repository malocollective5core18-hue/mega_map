# 04 – Backend API Contract

Base path `/api`. JSON only, HTTPS only, CORS limited to the site origin.

## Public (no login, rate-limited)
- `GET /public/shops?bbox=w,s,e,n&limit=500` → `{items:[{id,name,area,lat,lng}]}` (opt-in rows only, rounded coordinates).
- `GET /public/demand-cells?bbox=` → `{items:[{cellId,geojson,level}]}` (count ≥ 3, level low/med/high, no raw counts needed).
- `GET /public/config` → company contact numbers, privacy notice version.

## Customer flow (existing frontend)
- `POST /provider-codes/verify` `{phone,code}` → `{valid:true,verificationToken,expiresAt}` or `{valid:false}`. Phone is normalized to E.164 and must match the target phone bound to that random code. 401/403/410/429 as needed. Same response for every invalid pair.
- `POST /location-submissions` with `Authorization: Bearer <token>`: `{customerName,businessName,phone,latitude,longitude,accuracyMeters,clientTimestamp,consent:true,confirmed:true,publicListing:bool}` → `201 {accepted:true,reference}`. 409 duplicate, 410 expired, 422 invalid.
- Token is single-use; server assigns id and timestamp; client values are advisory only.

## Staff (login required, roles dispatcher/admin)
- `POST /auth/login`, `POST /auth/logout`, MFA recommended.
- `GET /admin/businesses?status=&q=&bbox=&page=`
- `GET /admin/businesses/{id}` (full detail)
- `PATCH /admin/businesses/{id}` status, notes, assignee, publicListing
- `POST /admin/businesses/{id}/visits`
- `GET /admin/export.csv` (admin only, audit-logged)
- `POST /admin/provider-codes` `{phone,label,expiresAt,maxUses}` (returns a random plain code once, bound to a keyed hash of the normalized phone), `POST /admin/provider-codes/{id}/revoke`
- `GET /admin/audit-log`

## Standards
Validation server-side (phone, lat −90..90, lng −180..180, accuracy ≥ 0); error shape `{error:{code,message}}`; throttling per IP and per code; idempotency key on submissions; OpenAPI file published.
