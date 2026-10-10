# 06 – Security and Compliance

- HTTPS everywhere, HSTS, secure cookies (HttpOnly, SameSite) for staff sessions.
- Provider codes stored hashed, short-lived verification tokens, single use, brute-force throttling, generic error text.
- No secrets, admin credentials or private keys in frontend code.
- Content-Security-Policy listing only the tile, geocoder, Leaflet CDN and API origins; add Subresource Integrity to CDN scripts.
- Validate and escape all input and output (XSS), parameterised queries, CSRF protection for staff.
- Public endpoints return only the public serializer; test that exact coordinates and phones can never appear.
- Rate limits on public search and geocoding calls; cache tile/geocoder results as their terms allow.
- Satellite tiles (Esri) and Nominatim have usage terms; review them or switch to a licensed provider before heavy traffic.
- Privacy notice (Kiswahili + English): what is collected, why, who sees it, retention, how to remove a listing, contact. Version it and record acceptance.
- Backups encrypted, restore tested; logs exclude coordinates and phones; access reviewed quarterly.
- Incident plan: who is told, how customers are notified.
- Legal review against Tanzania's Personal Data Protection Act, 2022 and registration duties, before launch.
