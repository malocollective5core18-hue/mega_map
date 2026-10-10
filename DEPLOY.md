# Local setup and later deployment

Deployment is not part of this project stage. The production settings file is present for later review; complete the security and owner-decision items before exposing the service publicly.

## Local development

1. Install Python 3.12 or newer and Docker Compose.
2. Copy `.env.example` to `.env`, set a unique `DJANGO_SECRET_KEY` and PostgreSQL password, then run `docker compose up -d db`.
3. Install `requirements.txt` in a virtual environment. Export the values from `.env` into your shell.
4. Run `python manage.py migrate`, `python manage.py createcachetable`, `python manage.py setup_roles`, then create an admin account using `python manage.py createsuperuser` and add staff to `dispatcher` or `admin` groups.
5. Run `python manage.py runserver`. Customer map is `/`; staff sign-in is `/staff/`.
6. Run tests with `DJANGO_SETTINGS_MODULE=stocktaking.settings.test python manage.py test core` (the test settings use in-memory SQLite; production/local configuration remains PostgreSQL).

## Later deployment checklist

- Use a supported HTTPS reverse proxy, restrict hosts/origins, enable HSTS only after HTTPS is confirmed, and use secure session/CSRF cookies.
- Provide secrets through the deployment secret manager. Set `DJANGO_SETTINGS_MODULE=stocktaking.settings.prod`, `DJANGO_SECRET_KEY`, database credentials, allowed hosts, trusted CSRF origins, company contact details and privacy-notice version.
- Add a restrictive Content Security Policy compatible with the chosen CDN/map tile origins; pin and review CDN assets and use SRI where supported.
- Provision PostgreSQL backups, encrypt them, restrict access, test a restore, and document retention. Do not place dumps in the repository.
- Schedule and monitor `python manage.py refresh_demand_cells` and the approved retention/anonymisation job once retention policy is decided and the job is implemented.
- Run migrations, create role groups, create named admin accounts, verify MFA enforcement, rate limits, audit access, and public privacy tests before opening traffic.
- Confirm Esri terms, privacy notice/legal review, monitoring that avoids PII, incident response, and data-subject request procedures.
