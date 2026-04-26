import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Security ─────────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

DEBUG = os.environ.get("DEBUG", "False") == "True"

# Railway injects RAILWAY_PUBLIC_DOMAIN automatically.
# Additional hosts can be added via ALLOWED_HOSTS env var (comma-separated).
_extra_hosts = os.environ.get("ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in _extra_hosts.split(",") if h.strip()]

_railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if _railway_domain:
    ALLOWED_HOSTS.append(_railway_domain)

if DEBUG or not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["*"]

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
