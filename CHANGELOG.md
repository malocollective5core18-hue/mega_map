# Changelog

## Unreleased
- Public Leaflet assets are pinned to version 1.9.4 and loaded with Subresource Integrity verification.
- Staff audit coverage now records failed sign-in, denied authorization, staff-user listing, new-customer key verification, and changed field names without storing submitted values.
- Django `/admin/` is restricted to superusers; a report-only CSP header is available for compatibility observation. MFA is still a release blocker.
- Issued customer-key history now has a confirmed Revoke action.

Changes are recorded here for release and deployment reviews.

## Unreleased — release audit documentation

- Added repository audit, proposed branch model, release checklist, readiness assessment, and rollback/recovery guidance under `RELEASE/`.
- Recorded that the audited `main` is `26f328c`, matches `origin/main`, and has no production branch/tag.
- Recorded verification limits: package installation could not reach an index, the local runtime dependency set is incomplete, PostgreSQL release gates were not run, and no live service/database was changed.
- Decision: no production branch or release tag until all blockers in `RELEASE/READINESS.md` pass on a reviewed commit.
