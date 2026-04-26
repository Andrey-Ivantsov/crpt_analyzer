import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Security ─────────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

DEBUG = os.environ.get("DEBUG", "False") == "True"

# Railway healthcheck uses internal IP — allow all hosts.
# Access control is handled at the Railway network level.
ALLOWED_HOSTS = ["*"]

# Required in production for CSRF to work.
# Railway domain is read from the env var Railway injects automatically.
_railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
CSRF_TRUSTED_ORIGINS = [f"https://{_railway_domain}"] if _railway_domain else []

# ─── Applications ─────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "market",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",   # static files in production
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

# ─── Internationalisation ─────────────────────────────────────────────────────

LANGUAGE_CODE = "ru-ru"
TIME_ZONE     = "UTC"
USE_I18N      = True
USE_TZ        = True

# ─── Static files ─────────────────────────────────────────────────────────────

STATIC_URL  = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Compress and cache-bust static files via whitenoise
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
