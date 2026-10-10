from .base import *  # noqa: F403

if DEBUG:
    raise RuntimeError("Production settings must not run with DEBUG enabled.")
if not os.environ.get("DJANGO_ALLOWED_HOSTS"):
    raise RuntimeError("Set DJANGO_ALLOWED_HOSTS for production.")
if not os.environ.get("CSRF_TRUSTED_ORIGINS"):
    raise RuntimeError("Set CSRF_TRUSTED_ORIGINS for production.")

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
