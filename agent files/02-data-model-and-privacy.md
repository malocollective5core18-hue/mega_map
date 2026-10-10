# 02 – Data Model and Privacy Rules

Decided stack: Django + Django REST Framework, PostgreSQL, git. Coordinates are stored as indexed decimal latitude/longitude columns (PostGIS optional later), so read "geom (Point)" below as latitude + longitude.

## Tables
**provider_code**: id, code_hash (never store plain), label, status (active/revoked/expired), expires_at, max_uses, use_count, created_by.
**verification_session**: id, provider_code_id, token_hash, expires_at (≤30 min), used_at.
**customer_business**: id, public_ref, customer_name, business_name, phone, status, created_at, updated_at, assigned_to, notes.
**business_location**: id, business_id, corrected_lat, corrected_lng, corrected_by, corrected_at, team_verified (bool), geom (Point, 4326), accuracy_m, source (gps/manual_pin), captured_at, address_text (optional), ward, district, region.
**consents**: business_id, privacy_notice_version, location_processing (bool), public_listing (bool), given_at, ip_hash.
**service_visit**: id, business_id, visit_date, team, outcome.
**demand_cell** (materialised view): cell_id, geom (~500 m grid), request_count, updated_at.
**audit_log**: actor, action, object, timestamp, ip_hash.

## Visibility matrix
| Data | Public | Dispatcher | Admin |
|---|---|---|---|
| Business name (opt-in served only) | yes | yes | yes |
| Exact coordinates | no | yes | yes |
| Public pin | rounded to 3 decimals (~110 m) or ward centroid | n/a | n/a |
| Customer name, phone | no | yes | yes |
| Demand cells | only if count ≥ 3 | yes | yes |
| Provider codes | no | no | hashed only |

## Rules
- Public API returns only a dedicated serializer built from opt-in rows; no field is ever "hidden by CSS".
- Never put coordinates or phone in URLs, analytics, or logs.
- Retention: define a period (suggest 24 months after last visit) and a deletion/anonymise job.
- Customer may request removal from the public map at any time; takes effect immediately.
- Respect Tanzania's Personal Data Protection Act, 2022 (get legal review of the notice and retention).
