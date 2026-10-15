from .base import *  # noqa: F403
from urllib.parse import urlsplit

if DEBUG:  # noqa: F405
    raise RuntimeError("Production settings must not run with DEBUG enabled.")
if not os.environ.get("DJANGO_ALLOWED_HOSTS"):  # noqa: F405
    raise RuntimeError("Set DJANGO_ALLOWED_HOSTS for production.")
if not os.environ.get("CSRF_TRUSTED_ORIGINS"):  # noqa: F405
    raise RuntimeError("Set CSRF_TRUSTED_ORIGINS for production.")

SITE_URL = os.environ.get("SITE_URL", "").strip().rstrip("/")
site_url_parts = urlsplit(SITE_URL)
if (
    site_url_parts.scheme != "https"
    or not site_url_parts.netloc
    or site_url_parts.path
    or site_url_parts.query
    or site_url_parts.fragment
):
    raise RuntimeError("Set SITE_URL to the public HTTPS origin, without a trailing slash or path.")

SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
