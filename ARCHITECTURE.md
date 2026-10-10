# Architecture

The customer map is served from `index.html` by Django. The vanilla JavaScript calls same-origin Django REST Framework endpoints under `/api/`. Leaflet is pinned to 1.9.4 and public imagery uses Esri World Imagery.

`core` owns provider codes, single-use verification sessions, customer submissions, consent records, service visits, demand cells and immutable audit events. PostgreSQL is the application database. Coordinates are indexed decimal latitude/longitude fields; duplicate detection uses a bounding query followed by haversine distance. Public map APIs only query served, opted-in businesses and round coordinates to 0.001 degrees. Demand cells are only returned once they aggregate at least three requests.

Staff use `/staff/` with Django session authentication and a separate interface. API permissions distinguish dispatcher and admin groups. Exact-data detail views, list views, edits, corrections and exports create audit records. Navigation URLs are composed server-side from validated coordinates only; a verified team correction becomes the navigation destination.

`stocktaking.settings.base` contains shared configuration. `dev`, `test`, and `prod` provide environment-specific settings. Local PostgreSQL is available through Docker Compose. Provider-code hashes, bearer-token hashes, consent IP hashes, throttling and role checks are handled server-side.

## Current boundaries

The staff dashboard currently covers sign-in, searchable/paged business listing, satellite pins, customer detail, status/assignee/notes updates, pin correction, admin CSV export, recent audit events, provider-code issuance and public-listing consent control. Code revocation/reporting, bulk listing controls, aggregate reports, team-specific access/sharing, and staff MFA still need completion. There is no Git repository metadata in this workspace, so changes cannot be committed here.
