# Test report

## Current audit run

Date: 10 October 2026. Branch: `fix/audit-defects`. No production database or service was contacted.

- Runtime: Python 3.14.4; Django 5.2.18; DRF 3.16.1. Runtime dependencies are pinned in `requirements.lock`, and Render's `PYTHON_VERSION` is set in `render.yaml`.
- `DJANGO_SETTINGS_MODULE=stocktaking.settings.test python manage.py check`: Pass.
- `DJANGO_SETTINGS_MODULE=stocktaking.settings.test python manage.py makemigrations --check --dry-run`: Pass; no changes detected.
- `DJANGO_SETTINGS_MODULE=stocktaking.settings.test python manage.py test`: 9 passed, 1 PostgreSQL-only concurrency regression skipped on SQLite.
- D-01 PostgreSQL concurrency regression: present but skipped because PostgreSQL is unavailable. Local PostgreSQL 18 is installed but the workspace user cannot start its stopped cluster; Docker is also unavailable.
- D-02 phone-change regression (`test_phone_change_rebinds_live_keys_and_audits_field_names`): Pass on SQLite; verifies key rebind, revoked-key preservation, old/new phone verification, and field-name-only audit metadata. PostgreSQL rerun remains required.
- `DJANGO_SETTINGS_MODULE=stocktaking.settings.prod ... python manage.py check --deploy`: Command completed with one expected `security.W009` warning because the audit used a deliberately short dummy secret. This is not production-secret evidence.
- `.venv/bin/python -m pip check`: Pass; no broken requirements.
- PostgreSQL: Not tested. Docker is not installed, and local `pg_isready` previously reported no server response. PostgreSQL migration and concurrency gates remain open.
- `pip-audit` and `ruff`: Not run. The packages are unavailable locally and installing them failed because package-index DNS/network access is unavailable.
- JavaScript syntax: Pass for extracted inline scripts using `node --check` after substituting Django template booleans in temporary copies. No browser run was available.
- Secret scan: No high-confidence secret patterns found across tracked files and the eight commits reachable from local refs. The ignored `.env` was not read or scanned.

## Release status

Not release-ready. The current SQLite checks do not meet the required PostgreSQL verification gate. MFA, CSP enforcement, production backup/restore, retention/anonymisation, legal/privacy approval, and real-device/browser checks remain open. See `RELEASE/FIX-REPORT.md` for defect-by-defect status as work proceeds.
