# Release Gate Checklist

Use this for each candidate. Attach command output or CI links to `READINESS.md`; a box is complete only when evidence is recorded for the exact commit being released.

## Source and dependencies

- [ ] Start from a clean checkout of the candidate commit; record full SHA and verify branch ancestry.
- [ ] Run a full-history secret scan with Gitleaks or equivalent. Resolve findings and rotate any exposed real credential.
- [ ] Create a new isolated virtual environment from a supported Python version.
- [ ] Pin every runtime and development dependency exactly and preferably with hashes; install only from that manifest.
- [ ] Run `pip-audit`; record and resolve or explicitly accept each finding.

## Django and configuration

- [ ] Set production settings with `DEBUG=False`, a strong environment-only secret, explicit hosts/origins, PostgreSQL URL, HTTPS-only cookies, HSTS, SSL redirect, correct Render proxy handling, and no default production credentials.
- [ ] Run `python manage.py check --deploy` with production settings and resolve every warning.
- [ ] Verify static collection and serving via WhiteNoise or the approved equivalent.
- [ ] Verify production logs omit customer names, phone numbers, code secrets, and exact coordinates.
- [ ] Verify CSP, CSRF/session behavior, rate limits, output escaping, security headers, and all staff authorization checks.

## Database and application tests

- [ ] Run all migrations from an empty PostgreSQL database.
- [ ] Run `python manage.py makemigrations --check --dry-run`.
- [ ] Apply migrations to a protected copy of representative data and document rollback/forward-fix behavior.
- [ ] Run the complete automated suite on PostgreSQL (SQLite does not satisfy this gate).
- [ ] Verify public APIs omit customer names, phones, exact coordinates, non-consented/non-served shops, and demand cells below the configured threshold; verify public coordinates are rounded.
- [ ] Verify role permissions, consent, code/token hashing, expiry, idempotency, throttling, audit records, code revocation, and sensitive exports.

## Frontend, docs, and operations

- [ ] Run JavaScript syntax checks on template-rendered scripts; check browser console and network errors.
- [ ] Pin every CDN dependency and use Subresource Integrity where supported.
- [ ] Confirm map/tile/geocoder failures do not block core customer/staff form use.
- [ ] Test GPS, pin correction, and Google Maps navigation on real Android and iPhone devices.
- [ ] Test keyboard use, screen reader labels, responsive tables, and panel resizing on representative devices.
- [ ] Review `DEPLOY.md`, `CHANGELOG.md`, `RELEASE/ROLLBACK.md`, known limitations, and owner/legal decisions.
- [ ] Demonstrate a production-grade Supabase backup and restore; verify HTTPS domain, MFA, privacy approval, retention, incident response, and support ownership.
- [ ] Record every gate as Pass, Fail, or Not tested in `READINESS.md` for the release SHA.
- [ ] Obtain PR approval, merge to protected `production`, tag the approved commit, and have the owner deploy it.
