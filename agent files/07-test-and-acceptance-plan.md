# 07 – Test and Acceptance Plan

Mark each item Pass / Fail / Not tested. Do not claim a result that was not run.

## Customer flow
- Empty and invalid inputs (name, business, Tanzanian and international phones).
- Valid, invalid, expired, revoked and rate-limited codes.
- GPS allowed, denied, unavailable, timeout; retry; stale request ignored.
- High-accuracy capture keeps the best device-reported fix for up to 30 seconds and may finish early at ≤30 m; lower-accuracy fixes stay visibly estimated and require the user to check the pin. Never present this as a 99% guarantee.
- Manual pin drag and map tap; confirm, back, and Sitisha clear all data.
- Double-tap on "Thibitisha na Tuma" sends one request; server 409/410/422/5xx and offline messages.
- Demo mode never says data was sent.

## Public map
- Only opted-in shops appear; removing consent hides a shop at once.
- Public JSON contains no phone, full name, or exact coordinates (automated test).
- Demand cells with count < 3 never returned.
- 500+ pins cluster and stay smooth on a low-end Android phone.

## Staff
- Role checks per endpoint; dispatcher cannot export or see codes.
- Audit entries written for exports and views of exact data.
- Session timeout and MFA.

## Navigation
- Navigate link opens Google Maps with the exact pin as destination on Android, iPhone and desktop (check on real devices; mark Not tested if unavailable).
- Backup links (Waze, Apple Maps, OSM), Copy coordinates and WhatsApp share all work, and none contain name or phone.
- Corrected pin replaces the original in every new link; correction is audit-logged.
- Missing or invalid coordinates disable the button with a message.
- Confidence badge shows High, Medium or Low correctly for test accuracy values.

## Cross-cutting
Chrome/Android, Safari/iOS, desktop; portrait/landscape; slow 3G; keyboard-only; screen reader pass; contrast check; tiles blocked fallback.

## Release gate
All privacy tests pass, DEMO_MODE off, HTTPS live, backups restored once, legal notice approved, owner signs off.
