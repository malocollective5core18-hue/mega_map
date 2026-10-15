# Changelog

## Unreleased
- Duplicate submissions are serialized by PostgreSQL transaction locks; customer phone changes rebind active keys and duplicate edits are rejected pending the owner data gate for DB uniqueness.
- Render Blueprint watches `production`; failed key attempts can be pruned by a daily management command.
- Runtime pins and Python version are declared, and customer key history uses indexed phone HMACs (secret rotation requires a rehash plan).
- Public Leaflet assets are pinned to version 1.9.4 and loaded with Subresource Integrity verification.
- Staff audit coverage now records failed sign-in, denied authorization, staff-user listing, new-customer key verification, and changed field names without storing submitted values.
- Customer access keys now identify a business profile, allowing separate businesses to share a phone without inheriting one another’s saved pin.
- Django `/admin/` is restricted to superusers; a report-only CSP header is available for compatibility observation. Staff TOTP MFA now uses django-otp, with hashed single-use recovery codes, throttling/lockout, verified-session gating, audit events, and recovery-owner-controlled re-enrollment. PostgreSQL/browser evidence and the named recovery owner remain release gates.
- DRF was upgraded to 3.17.2 after pip-audit identified advisories in 3.16.1. Ruff findings were corrected and action references updated for current Node 24 runners.
- Issued customer-key history now has a confirmed Revoke action.
- Public link previews now include absolute canonical/Open Graph/Twitter metadata, a versioned 1200×630 share image generated from tracked favicon assets, and crawler-only robots/sitemap controls. Staff, admin and API responses are marked noindex. Render must set `SITE_URL` to its exact HTTPS origin; WhatsApp/social cache refresh remains platform-controlled.
- Staff screens now show the UNI-COT collaboration mark. Dispatchers/admins can open stored customer flag cases; admin assistants/superusers can permanently delete a customer with confirmation, linked-key revocation, phone-ambiguity protection, and an audit record.

Changes are recorded here for release and deployment reviews.

## Unreleased — release audit documentation

- Added repository audit, proposed branch model, release checklist, readiness assessment, and rollback/recovery guidance under `RELEASE/`.
- Recorded that the audited `main` is `26f328c`, matches `origin/main`, and has no production branch/tag.
- Recorded verification limits: package installation could not reach an index, the local runtime dependency set is incomplete, PostgreSQL release gates were not run, and no live service/database was changed.
- Decision: no production branch or release tag until all blockers in `RELEASE/READINESS.md` pass on a reviewed commit.
