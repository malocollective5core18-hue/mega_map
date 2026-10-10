# Test report

## Automated checks

- Django system check: Pass (`manage.py check`, local development settings).
- Python bytecode compilation: Pass (`compileall` for `core` and `stocktaking`).
- API/model tests: 7 tests cover code verification, idempotent customer submission, public shop privacy rounding/opt-in, demand threshold, dispatcher restrictions, dashboard access, and audited corrected navigation. Run with `DJANGO_SETTINGS_MODULE=stocktaking.settings.test python manage.py test core`.
- Staff JavaScript syntax: Pass (`node --check` on extracted login and dashboard scripts).
- PostgreSQL migrations/integration: Not tested; the local PostgreSQL 18 cluster is stopped and cannot be started by the current workspace user. SQLite in-memory settings were used for the API suite only.
- Real-device navigation, GPS hardware, mobile layout/accessibility, tile-blocked fallback, HTTPS, backup restore, and full 500-pin performance: Not tested.

## Release status

Not release-ready. MFA, retention/anonymisation automation, CSP, OpenAPI schema, reports/code-management dashboard controls and production HTTPS/restore checks remain outstanding. Owner and legal decisions are listed in `ASSUMPTIONS.md`.
