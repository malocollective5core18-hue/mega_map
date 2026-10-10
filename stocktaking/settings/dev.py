from .base import *  # noqa: F403

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
INTERNAL_IPS = ["127.0.0.1"]
