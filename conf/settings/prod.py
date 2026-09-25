"""Production settings stub.

Requires in server .env:
    DJANGO_SECRET_KEY, ALLOWED_HOSTS
Optional: DATABASE_URL (when Postgres is added later).
"""

from decouple import Csv, config

from .base import *  # noqa: F401,F403

DEBUG = False

SECRET_KEY = config("DJANGO_SECRET_KEY", default="") or config("SECRET_KEY", default="")
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY or SECRET_KEY is required in production.")

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
SESSION_COOKIE_SECURE = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
CSRF_COOKIE_SECURE = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
