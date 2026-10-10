# Architecture

The customer map is served from `index.html` by Django. The vanilla JavaScript calls same-origin Django REST Framework endpoints under `/api/`. Leaflet 1.9.4 public and staff assets are pinned with Subresource Integrity. Public imagery uses Esri World Imagery.

`core` owns provider codes, single-use verification sessions, customer submissions, consent records, service visits, demand cells and audit events. PostgreSQL is the application database. Customer phone HMACs are indexed for code-history linking; values depend on `SECRET_KEY`, so rotation requires a controlled rehash migration. Coordinates are indexed decimal latitude/longitude fields; duplicate detection uses sorted PostgreSQL transaction advisory locks and a bounding query followed by haversine distance. Public map APIs only query served, opted-in businesses and round coordinates to 0.001 degrees. Demand cells are only returned once they aggregate at least three requests.

Staff use `/staff/` with Django session authentication and a separate interface. API permissions distinguish dispatcher and admin groups. Successful sensitive reads, staff-user listing, failed sign-in, denied staff authorization, new-customer key verification, customer profile changes, and staff edits create audit records. Audit metadata records field names/reason categories only and does not contain submitted values. Navigation URLs are composed server-side from validated coordinates only; a verified team correction becomes the navigation destination.

`stocktaking.settings.base` contains shared configuration. `dev`, `test`, and `prod` provide environment-specific settings. Local PostgreSQL is available through Docker Compose. Provider-code hashes, bearer-token hashes, consent IP hashes, throttling and role checks are handled server-side.

## Current boundaries

The staff dashboard currently covers sign-in, searchable/paged business listing, satellite pins, customer detail, status/assignee/notes updates, pin correction, admin CSV export, recent audit events, searchable provider-code history with revoke, and public-listing consent control. Bulk listing controls, aggregate reports, team-specific access/sharing, and staff MFA still need completion. Render deployment configuration is in `render.yaml` and `build.sh`; see `DEPLOY.md` for setup and current free-tier limits.
