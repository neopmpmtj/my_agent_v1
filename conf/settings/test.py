"""Test settings — fast hasher (used automatically by manage.py test)."""

from .dev import *  # noqa: F401,F403

TESTING = True

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

STATIC_ROOT.mkdir(parents=True, exist_ok=True)
