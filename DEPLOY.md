# Render + Supabase deployment

This repository is prepared for a Render Python web service with Supabase Postgres. `render.yaml` describes the web service; `build.sh` installs dependencies, collects static assets, applies migrations, creates the cache table, and ensures the staff role groups exist.

## Free tier use

Treat the free configuration as a demo or tightly controlled pilot. Render sleeps free web services after 15 minutes without inbound traffic, and the first request after sleep can wait about a minute. Its filesystem is temporary, so all persistent state must stay in Supabase. Supabase may pause a free project after a week with too little database activity; its free database also has a 500 MB quota and no automatic backups. This app holds names, phone numbers, and precise business locations, so do not use the free configuration for routine live customer operations. Upgrade the web service and database, enable managed backups, and validate recovery before handling production customer records. See [Render free instance limits](https://render.com/docs/free), [Supabase free project pausing](https://supabase.com/docs/guides/platform/free-project-pausing), and [Supabase backups](https://supabase.com/docs/guides/platform/backups).

The same sleep can delay a social crawler's first request enough that it misses the link preview. For reliable sharing, use an always-on paid web instance or an uptime check that keeps the service awake. An uptime check does not guarantee that a platform refreshes a cached preview.

## 1. Create the Supabase database

1. Create a Supabase project in Singapore (`ap-southeast-1`) to keep it close to the Render service region.
2. Set a strong database password and store it in your password manager.
3. In **Connect**, select the **Session pooler** connection method and copy the full URI. The free Supabase direct endpoint may be IPv6-only, while Render's free service needs an IPv4-reachable endpoint. Session pooling is a fit for this long-running Django web process. Do not use the transaction pooler for this app's normal Django connection.
4. Keep the URI private. If the password has URI-reserved characters, use the exact encoded URI Supabase provides.

Supabase's connection methods and IP support are documented in its [Postgres connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres).

## 2. Deploy the Render service

1. The Blueprint targets the GitHub `production` branch. In the Render dashboard, confirm that the live service is configured to watch `production`; the repository cannot verify that live setting.
2. In Render, create or update the **Blueprint** from `malocollective5core18-hue/mega_map` and apply `render.yaml`. Select Singapore if Render asks for a region.
3. In the new web service's environment settings, set `DATABASE_URL` to the Supabase **Session pooler** URI. Render marks this value `sync: false`, so it is entered privately in the Render dashboard.
4. Set `SITE_URL` to the exact public HTTPS origin, for example `https://mega-map.onrender.com`, with no trailing slash or path. The production app refuses to start with a missing or non-HTTPS value; canonical, sitemap, and social preview URLs are based on this setting.
5. Confirm `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` match the exact Render hostname shown on the service. If using a custom domain, add its hostname and `https://` origin as comma-separated values.
6. Deploy. The build applies Django migrations and initializes roles/cache; the start command runs one Gunicorn worker with four threads, suitable for the free instance's small memory limit.

Render runs `build.sh` on each build and uses the service command in the Blueprint. The free service has no persistent disk or dashboard shell. Its temporary filesystem is only used for build output and collected static files; the database is external. The Blueprint health check uses `/healthz`, which returns an empty HTTP 204 response without reading customer or database data; production settings exempt this path from the HTTPS redirect for liveness checks.

The crawler endpoints are public `/robots.txt` and `/sitemap.xml`; the sitemap lists only `/`. `/staff/`, `/api/`, and `/admin/` responses carry `X-Robots-Tag: noindex, nofollow`. Public link metadata and its static image are rendered in the initial HTML response. Social services cache previews independently: re-scrape with their debugger or use a new image version when metadata changes. The application cannot force WhatsApp or another platform to refresh old chats.

The public Open Graph image is generated from `core/static/core/icons/icon-512.png`. To edit and regenerate it, install the development-only dependency (`python -m pip install -r requirements-image.txt`) and run `python scripts/make_og_image.py`. Pillow is not part of the web service runtime lock.

## 3. Create the first administrator

Do not add credentials to the repository or blueprint. Do not put a superuser password in permanent Render environment variables, and do not upload `.env`; Render does not read your local `.env` file. Create the superuser once against the production database from a trusted computer. Make a private environment file outside the repository containing the Render `DJANGO_SECRET_KEY`, exact host/origin values, and the Supabase session-pooler `DATABASE_URL`. Keep it private and delete it when finished. Install the exact deployment lock locally and run:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
set -a
. /secure/path/mauzosheet-production.env
set +a
DJANGO_SETTINGS_MODULE=stocktaking.settings.prod .venv/bin/python manage.py createsuperuser
```

The build creates `admin`, `dispatcher`, and `service_provider` role groups. Sign in at `/staff/` with this superuser account. Use its sidebar to register admin assistants and service providers. Admin assistants cannot create staff or issue customer keys; service providers can issue reusable phone-bound customer keys. Do not share the superuser account. Rotate any password that has been pasted into chat or exposed elsewhere before creating the production account. The application does not read `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, or `DJANGO_SUPERUSER_PASSWORD`; remove these one-time bootstrap variables from Render after creating the account if they were added there.

## 4. Before serving live customers

- Move off Render and Supabase free tiers for live operations; configure Supabase automated backups and perform a restore drill.
- Staff sign-in enforces TOTP or a recovery code for staff accounts. If the owner explicitly wants password-only access for the superuser, set `MFA_EXEMPT_SUPERUSER_EMAIL` in Render to that active superuser's exact email. This exception applies only to a superuser with that email; leave it blank to require MFA for every staff account. Password-only administrator access weakens account protection and should be limited to the named owner account.
- Set `COMPANY_PHONE_NUMBER=+255685496334` and `COMPANY_WHATSAPP_URL=https://wa.me/qr/F37XYALS2AS2I1` in Render for the office contact actions. These environment values override the same local defaults.
- Review the privacy notice and data handling for Tanzania, including hosting customer names, phone numbers, and exact locations in Singapore. Confirm legal and owner approval before collecting real customer records.
- Confirm map tile/geocoding service terms, retention/deletion procedures, monitoring and incident response. Logs should not include customer details.
- Check the deployment and database health after every migration. Keep an off-site database export if operating without managed backup coverage.

## Local development

For local use, continue with `.env.example` and `docker compose up -d db`; the existing discrete `POSTGRES_*` settings remain supported. Do not point a shared production database at local development commands except for the one-time administrator setup above.

Before any future migration that adds a unique constraint to customer phones, run `python manage.py check_duplicate_customer_phones` against a protected, representative database copy. This read-only command exits with an error and lists only masked last-four identifiers when duplicates exist. Stop the migration process and resolve the records before proceeding. No phone uniqueness migration is included until this data gate has been satisfied.

Schedule `python manage.py prune_code_attempts --hours 24` to run daily. It deletes old failed-key attempt digests in bounded batches; the verification path also removes at most 200 stale rows opportunistically on approximately one percent of attempts.

Customer-business phone digests are HMACs keyed by `DJANGO_SECRET_KEY`, matching provider-code phone digests for indexed code-history lookup. Changing that secret invalidates provider-code verification as well as these indexes; secret rotation requires a controlled migration that rehashes both data sets atomically. Do not rotate the key without a planned rehash/recovery procedure.
