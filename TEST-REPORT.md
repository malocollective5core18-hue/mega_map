# Test report

## Current audit run

Date: 10 October 2026. Branch: `fix/audit-defects`. No production database or service was contacted.

- Runtime: Python 3.14.4; Django 5.2.18; DRF 3.16.1. Runtime dependencies are pinned in `requirements.lock`, and Render's `PYTHON_VERSION` is set in `render.yaml`.
- `DJANGO_SETTINGS_MODULE=stocktaking.settings.test python manage.py check`: Pass.
- `DJANGO_SETTINGS_MODULE=stocktaking.settings.test python manage.py makemigrations --check --dry-run`: Pass; no changes detected.
- `DJANGO_SETTINGS_MODULE=stocktaking.settings.test python manage.py test`: 39 tests; 38 passed and 1 PostgreSQL-only concurrency regression was skipped on SQLite.
- D-01 PostgreSQL concurrency regression: present but skipped because PostgreSQL is unavailable. Local PostgreSQL 18 is installed but the workspace user cannot start its stopped cluster; Docker is also unavailable.
- D-02 phone-change regression (`test_phone_change_rebinds_live_keys_and_audits_field_names`): Pass on SQLite; verifies key rebind, revoked-key preservation, old/new phone verification, and field-name-only audit metadata. PostgreSQL rerun remains required.
- D-03 duplicate-phone protection and masked read-only pre-migration command tests: Pass on SQLite. The unique database constraint is not added because duplicate-check execution against a protected representative database copy is unavailable; this item needs the owner/data gate.
- D-04 Render branch regression (`test_render_blueprint_targets_production_branch`): Pass on SQLite after changing the Blueprint to `production`. The live Render dashboard branch remains Not verified.
- D-05 cleanup tests (`CodeAttemptRetentionTests`): Pass on SQLite for 24-hour pruning, preserving recent rows, and bounded opportunistic deletion.
- `DJANGO_SETTINGS_MODULE=stocktaking.settings.prod ... python manage.py check --deploy`: Pass with a long dummy secret and explicit dummy host/origin values. No real production values were used.
- `.venv/bin/python -m pip check`: Pass; no broken requirements.
- PostgreSQL: Not tested. Docker is not installed, and local `pg_isready` previously reported no server response. PostgreSQL migration and concurrency gates remain open.
- `pip-audit` and `ruff`: Not run. The packages are unavailable locally and installing them failed because package-index DNS/network access is unavailable.
- JavaScript syntax: Pass for extracted inline scripts using `node --check` after substituting Django template booleans in temporary copies. The run includes the customer key Revoke action. No browser run was available.
- Secret scan: A targeted regex scan of tracked Git history found no private-key blocks, AWS access keys, GitHub tokens, Slack tokens, or credentialed URLs. This is not a full Gitleaks/trufflehog scan; those tools are unavailable. The ignored `.env` was not read or scanned.

## Release status

Not release-ready. SQLite does not meet the required PostgreSQL verification gate. TOTP MFA is not implemented; CSP remains report-only; production backup/restore, retention/anonymisation, legal/privacy approval, and real-device/browser checks remain open. See `RELEASE/FIX-REPORT.md` for defect-by-defect status and owner commands.
