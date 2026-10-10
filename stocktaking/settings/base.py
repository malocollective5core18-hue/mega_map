import os
from pathlib import Path

import dj_database_url


BASE_DIR = Path(__file__).resolve().parents[2]
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError("Set DJANGO_SECRET_KEY in the environment.")

DEBUG = False
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]
ROOT_URLCONF = "stocktaking.urls"
WSGI_APPLICATION = "stocktaking.wsgi.application"
ASGI_APPLICATION = "stocktaking.asgi.application"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "core.middleware.PrivateStaffNoStoreMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR, BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

if os.environ.get("DATABASE_URL"):
    DATABASES = {"default": dj_database_url.parse(
        os.environ["DATABASE_URL"],
        conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        ssl_require=os.environ.get("DB_SSL_REQUIRE", "true").lower() == "true",
    )}
else:
    DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.environ.get("POSTGRES_DB", "stocktaking"),
    "USER": os.environ.get("POSTGRES_USER", "stocktaking"),
    "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
    "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
    "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    "CONN_MAX_AGE": int(os.environ.get("POSTGRES_CONN_MAX_AGE", "60")),
    "OPTIONS": {"connect_timeout": 5},
    }}

CACHES = {"default": {
    "BACKEND": "django.core.cache.backends.db.DatabaseCache",
    "LOCATION": "django_cache",
    "TIMEOUT": 300,
}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-tz"
TIME_ZONE = "Africa/Dar_es_Salaam"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SESSION_COOKIE_AGE = 30 * 60
SESSION_SAVE_EVERY_REQUEST = True

CORS_ALLOWED_ORIGINS = [origin.strip() for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:8000").split(",") if origin.strip()]
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "http://localhost:8000").split(",") if origin.strip()]
CORS_ALLOW_CREDENTIALS = False

PRIVACY_NOTICE_VERSION = os.environ.get("PRIVACY_NOTICE_VERSION", "2026-01")
PROVIDER_CODE_TTL_SECONDS = int(os.environ.get("PROVIDER_CODE_TTL_SECONDS", "1800"))
PUBLIC_API_RATE = os.environ.get("PUBLIC_API_RATE", "60/min")
CODE_VERIFY_RATE = os.environ.get("CODE_VERIFY_RATE", "5/hour")
SUBMISSION_RATE = os.environ.get("SUBMISSION_RATE", "10/hour")
STAFF_LOGIN_RATE = os.environ.get("STAFF_LOGIN_RATE", "5/min")
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "")
COMPANY_WHATSAPP_NUMBER = os.environ.get("COMPANY_WHATSAPP_NUMBER", "")
COMPANY_PHONE_NUMBER = os.environ.get("COMPANY_PHONE_NUMBER", "")

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_THROTTLE_RATES": {
        "public": PUBLIC_API_RATE,
        "verify": CODE_VERIFY_RATE,
        "submit": SUBMISSION_RATE,
        "staff_login": STAFF_LOGIN_RATE,
    },
    "EXCEPTION_HANDLER": "core.api.exception_handler",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"safe": {"format": "{levelname} {asctime} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "safe"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
