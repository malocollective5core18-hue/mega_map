# 01 – Product Requirements (PRD)

## Purpose
Replace phone-call directions with a verified location system, and give the company one map showing (a) shops already served, (b) areas where demand exists, (c) new customers awaiting service.

## Users
| Role | Goal |
|---|---|
| Customer | Share exact business location with a provider code, in Kiswahili/English, on a phone |
| Visitor / prospect | See where the company already works; request service or a code |
| Dispatcher (staff) | See new submissions, find the business, assign a team |
| Admin | Manage codes, users, customer visibility, exports, audit logs |

## Map layers
1. **Served shops** (public, opt-in only): business name, area/ward, approximate pin.
2. **Demand areas** (public, aggregated): grid cells with a count of requests/prospects; never individual points.
3. **New customers** (staff only): exact pin, contact, status.

## Customer statuses
`submitted` → `reviewed` → `scheduled` → `served` (appears in layer 1 if public listing consent = true) | `rejected` | `duplicate`.

## Functional requirements
- FR1 Customer location-sharing flow (already built in index.html; keep it).
- FR2 Public map page with layers 1 and 2, search, filter by area/region, and "Request service" button that starts FR1 or contacts the company.
- FR3 Staff dashboard (doc 05) with map + table of all layers, status changes, notes, assignment.
- FR4 Provider-code issuing, expiry, revoke, usage count.
- FR5 Customer consent: separate checkbox for "show my business on the public map".
- FR6 CSV export for staff (role-restricted, logged).
- FR7 Duplicate detection (same phone or pins within 30 m).
- FR8 Kiswahili default, English toggle.

## Non-goals (v1)
Payments, route optimisation, customer login, native apps.

## Success metrics
- Share of visits where the team arrives without calling for directions.
- Median time from submission to dispatch.
- Submissions with GPS accuracy ≤ 50 m.

## Open questions for the owner
Regions covered at launch; whether served shops may be listed by default or strictly opt-in (recommended: strictly opt-in); who may see exact pins.
