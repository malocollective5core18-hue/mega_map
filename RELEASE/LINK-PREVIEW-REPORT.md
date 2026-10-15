# Link preview release report

**Date:** 15 October 2026  
**Branch:** `feature/link-preview` (created from `fix/mission7-stabilization` at `dd81786`)  
**Scope:** Public-page share metadata, static preview/favicon assets, crawler endpoints, and local validation. No merge, deployment, Render dashboard change, production database access, or secret access was performed.

## Mission task status

| Task | Status | Evidence / limitation |
|---|---|---|
| 1. `SITE_URL` | Pass | Production settings require a valid HTTPS origin without trailing slash/path/query/fragment. `.env.example`, `render.yaml`, and `DEPLOY.md` document it. Blueprint hostname follows the supplied live URL `mega-map.onrender.com`; owner should verify the exact hostname in Render before applying. |
| 2. Public-page metadata | Pass | Title, bilingual description, canonical, OG, Twitter, theme, icons, manifest, and robots tags render from Django in the initial HTML. Metadata ordering/first 8 KB and absolute configured URLs are covered by `LinkPreviewMetadataTests`. |
| 3. Share image and favicon | Pass | Supplied PNG favicon assets were copied from ignored `staticfiles/icons/` into tracked app static sources. `scripts/make_og_image.py` reproducibly generates `core/static/og/share-1200x630-v1.png`; result 1200×630, 36,560 bytes. WhiteNoise production collection post-processed the files. |
| 4. Staff/API/admin exclusion | Pass | `X-Robots-Tag: noindex, nofollow`, staff template robots metadata, `/robots.txt`, and home-only `/sitemap.xml` are implemented and covered by focused tests. The report-only CSP already permits same-origin images; no policy relaxation was needed. |
| 5. Crawler reliability | Partial | Anonymous user-agent GET/HEAD tests for WhatsApp, Facebook, Twitter, and Telegram return 200 without cookies in Django tests. `/healthz` returns empty 204 and remains Render's configured health path. Live `curl -I` and live crawler checks are Not tested because DNS resolution for `mega-map.onrender.com` failed. Local in-process sample: 30 requests, median 6.45 ms, mean 32.87 ms, max 803.67 ms; excludes Render/network/cold-start. Render free-tier sleeping can delay the first preview. |
| 6. Optional share button | Skipped | A separate control would clutter the compact, screen-filling mobile map. Sharing the public root URL uses the page metadata and does not share customer data. |
| 7. Tests and CI | Partial | Five focused Django tests pass; static image served through WhiteNoise in tests. CI includes a step for these tests after `collectstatic`. Full 70-test SQLite suite fails on two unrelated existing wording assertions and skips one PostgreSQL-only concurrency test. Production `check --deploy` passes with dummy values. Browser console checks and PostgreSQL run are Not tested. |
| 8. Verification and owner checklist | Partial | Source/config/tests verified locally. Live social scraping and phone previews are Not tested; use the checklist below. |

## Test evidence

See [TEST-REPORT.md](../TEST-REPORT.md) for exact commands and statuses. Current locked dependency environment used Django 5.2.18 and DRF 3.17.2. The full-suite failures are:

- `AccuracyLanguageTests.test_customer_copy_does_not_promise_guaranteed_gps_accuracy`: its raw-template source assertion expects a phrase not present in the existing customer copy.
- `LocationSignalValidationTests.test_confidence_uses_accuracy_age_offset_and_staff_verification`: expects the word “offset” in existing customer-facing confidence text.

These GPS/customer-copy assertions are outside Mission 8 and were not modified. The PostgreSQL-only duplicate-submission concurrency test is skipped under SQLite; no PostgreSQL service is available locally.

## Commits

Changes are separated into implementation/tests, image/icon assets, and release documentation. The current branch tip contains the documentation commit and is recorded by Git; its ID is also reported in the completion message.

| Change | Commit |
|---|---|
| Metadata, crawler routes/policies, configuration, and regression tests | `920fde3` |
| Favicon/share image, manifest, and image generator | `3892197` |
| Changelog, deployment notes, test/readiness reports | Included in the documentation commit at the branch tip. |

## Owner manual checklist

1. In Facebook Sharing Debugger, submit the live public URL and inspect the parsed Open Graph fields and image; request a fresh scrape.
2. Send the public URL to yourself in WhatsApp on Android and iPhone. Confirm image/title/description and that tapping opens the public site.
3. After metadata changes, request a fresh scrape or use a new versioned image filename. WhatsApp controls cache lifetime; old chats may keep old cards. The app cannot force cache refresh.
4. Check the same URL in Telegram and an SMS app.
5. Keep the service awake with an always-on plan or uptime check if sharing widely. An uptime check does not force preview cache refresh.

The application was not deployed from this branch. No live preview result is claimed. Overall release status remains **NOT PRODUCTION-READY**; prior PostgreSQL, security, backup, legal/privacy, and real-device GPS gates remain open.
