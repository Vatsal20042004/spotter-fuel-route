"""Django settings. Everything environment-specific is read from env vars."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
if not DEBUG and SECRET_KEY.startswith("dev-only"):
    raise RuntimeError("Set DJANGO_SECRET_KEY when DJANGO_DEBUG is off.")
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*" if DEBUG else "localhost").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "fuel",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "fuel.middleware.ResponseTimeMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_PATH", BASE_DIR / "db.sqlite3"),
    }
}

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Map tile servers (OpenStreetMap) require a Referer; Django's default "same-origin" strips it.
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": os.environ.get("API_THROTTLE", "120/min")},
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Spotter Fuel Route API",
    "DESCRIPTION": "Route + cost-optimal fuel stops for a 500-mile-range, 10 mpg vehicle.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Cache holds geocodes and routes so repeated requests make zero external calls.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# --- Domain configuration -------------------------------------------------
VEHICLE_RANGE_MILES = float(os.environ.get("VEHICLE_RANGE_MILES", 500))
VEHICLE_MPG = float(os.environ.get("VEHICLE_MPG", 10))
# A stop must save at least this many $/gal to justify an extra stop (0 = strict optimum).
MIN_PRICE_ADVANTAGE = float(os.environ.get("MIN_PRICE_ADVANTAGE", 0.05))
# Purchases smaller than this are folded into the previous stop (no stopping for a few gallons).
MIN_PURCHASE_GALLONS = float(os.environ.get("MIN_PURCHASE_GALLONS", 5))
# How far (miles) a station may sit from the route and still count as "on route".
MAX_STATION_DETOUR_MILES = float(os.environ.get("MAX_STATION_DETOUR_MILES", 5))

OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")
NOMINATIM_BASE_URL = os.environ.get("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org")
EXTERNAL_RETRY_DELAY_SECONDS = float(os.environ.get("EXTERNAL_RETRY_DELAY_SECONDS", 0.5))
EXTERNAL_TIMEOUT_SECONDS = float(os.environ.get("EXTERNAL_TIMEOUT_SECONDS", 15))
# Nominatim's usage policy requires an identifying User-Agent.
EXTERNAL_USER_AGENT = os.environ.get("EXTERNAL_USER_AGENT", "spotter-fuel-route-assessment/1.0")
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", 60 * 60 * 24))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"fuel": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")}},
}
