# 05 – Staff and Admin Dashboard Specification

Separate private app/URL (e.g. `/staff/`), never mixed into the public page. Login + MFA, session timeout 30 min.

## Views
1. **Inbox**: new submissions, newest first; badge for accuracy > 100 m or duplicates.
2. **Map**: satellite map with layers: new, scheduled, served, demand cells; click pin → side panel.
3. **Business detail**: name, phone (tap to call/WhatsApp), exact coordinates, accuracy, "Open in Google Maps / OSM" link for navigation, consent record, visit history, notes.
4. **Dispatch**: assign team/date, change status; teams see only their assignments.
5. **Provider codes** (admin): create, set expiry/uses, revoke, usage report.
6. **Public listing control**: toggle which served shops appear publicly; bulk actions.
7. **Reports**: submissions per week, per ward; demand cells ranked; time to dispatch; CSV export.
8. **Audit log** (admin).

## Roles
- Dispatcher: view/edit businesses, assign, no export, no codes.
- Admin: everything including exports, users, codes, audit.
- Teams (optional): read-only list of assigned jobs on mobile.

## Rules
Every view of exact coordinates or phone and every export writes an audit entry. Edits show who and when. Deleting = anonymise, not hard delete, unless legally required.

## Navigation to the customer (required, reliability-critical)
On the business detail page, and on the mobile job list for teams, show a primary **Navigate** button plus backups:
1. **Navigate (Google Maps):** `https://www.google.com/maps/dir/?api=1&destination=<lat>,<lng>&travelmode=driving`. Use coordinates only, never the business name or address text, so the destination is the exact pin. Opens the Google Maps app on Android/iPhone where installed; the user taps Start there. No API key needed.
2. **Backups:** Waze `https://waze.com/ul?ll=<lat>,<lng>&navigate=yes`, Apple Maps `https://maps.apple.com/?daddr=<lat>,<lng>`, OpenStreetMap link, and a **Copy coordinates** button (`lat, lng`, 6 decimals).
3. **Send to team:** a button that shares the Navigate link by WhatsApp to the assigned team member (link contains coordinates only, no customer name or phone).
4. Coordinates are validated server-side (numbers in range, 6 decimal places) before the link is built; if invalid or missing, the button is disabled with a clear message.
5. Show the coordinates as text beside the buttons and a **location confidence** badge: High (GPS accuracy ≤ 30 m), Medium (31-100 m), Low (> 100 m or manually placed pin). For Low, show "Call the customer to confirm before travelling".
6. **Pin correction:** after arriving, staff can press "Set pin to my current position" or drag the pin. This saves `corrected_lat/lng`, who changed it and when (audit-logged), marks the location `team_verified`, and all later Navigate links use the corrected pin.
7. Staff can see the customer's original pin and the corrected pin side by side.
8. Estimated travel time and traffic come from Google Maps itself; the dashboard never promises them.
