"""CI settings: retain DATABASE_URL (PostgreSQL in GitHub Actions) with fast cache."""

from .base import *  # noqa: F403

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "mauzosheet-ci",
    }
}
