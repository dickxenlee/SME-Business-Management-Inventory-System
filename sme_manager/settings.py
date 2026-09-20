"""Django settings for the SME Manager project."""

import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    """Read a boolean environment variable and reject ambiguous values."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"{name} must be a valid boolean value.")


def env_int(name, default, minimum=0, maximum=None):
    """Read a bounded integer environment variable."""
    value = os.getenv(name)
    try:
        parsed = default if value is None or not value.strip() else int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an integer.") from exc
    if parsed < minimum or (maximum is not None and parsed > maximum):
        raise ImproperlyConfigured(f"{name} is outside the permitted range.")
    return parsed


def env_list(name, default=""):
    """Read a comma-separated list, discarding empty entries."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def required_env(name):
    """Read a required non-empty environment value without echoing it."""
    value = os.getenv(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"{name} must be configured.")
    return value


DJANGO_ENVIRONMENT = os.getenv("DJANGO_ENVIRONMENT", "development").strip().lower()
if DJANGO_ENVIRONMENT not in {"development", "test", "production"}:
    raise ImproperlyConfigured(
        "DJANGO_ENVIRONMENT must be development, test, or production."
    )
IS_PRODUCTION = DJANGO_ENVIRONMENT == "production"

SECRET_KEY = required_env("DJANGO_SECRET_KEY")
if IS_PRODUCTION:
    normalized_secret = SECRET_KEY.lower()
    placeholder_markers = ("replace", "change-me", "changeme", "example")
    if (
        len(SECRET_KEY) < 50
        or len(set(SECRET_KEY)) < 5
        or normalized_secret.startswith("django-insecure-")
        or any(marker in normalized_secret for marker in placeholder_markers)
    ):
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be a strong, non-placeholder production value."
        )

DEBUG = False if IS_PRODUCTION else env_bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    default="" if IS_PRODUCTION else "localhost,127.0.0.1",
)
if IS_PRODUCTION:
    invalid_hosts = (
        not ALLOWED_HOSTS
        or any(
            host == "*"
            or "*" in host
            or "://" in host
            or "/" in host
            or host.startswith(".")
            or any(character.isspace() for character in host)
            for host in ALLOWED_HOSTS
        )
    )
    if invalid_hosts:
        raise ImproperlyConfigured(
            "DJANGO_ALLOWED_HOSTS must list explicit production host names."
        )

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
if IS_PRODUCTION:
    if not CSRF_TRUSTED_ORIGINS:
        raise ImproperlyConfigured(
            "DJANGO_CSRF_TRUSTED_ORIGINS must list explicit HTTPS origins."
        )
    for origin in CSRF_TRUSTED_ORIGINS:
        parsed_origin = urlparse(origin)
        if (
            parsed_origin.scheme != "https"
            or not parsed_origin.hostname
            or "*" in origin
            or parsed_origin.username
            or parsed_origin.password
            or parsed_origin.path not in {"", "/"}
            or parsed_origin.params
            or parsed_origin.query
            or parsed_origin.fragment
        ):
            raise ImproperlyConfigured(
                "DJANGO_CSRF_TRUSTED_ORIGINS entries must be valid HTTPS origins."
            )


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "core.apps.CoreConfig",
    "products.apps.ProductsConfig",
    "inventory.apps.InventoryConfig",
    "customers.apps.CustomersConfig",
    "sales.apps.SalesConfig",
    "invoices.apps.InvoicesConfig",
    "reports.apps.ReportsConfig",
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
    # Must follow AuthenticationMiddleware; it attaches the request that the
    # Axes backend needs to attribute a failed login.
    "axes.middleware.AxesMiddleware",
]

AUTHENTICATION_BACKENDS = [
    # Axes must come first so a locked-out attempt is refused before the
    # credentials are ever checked.
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

ROOT_URLCONF = "sme_manager.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "sme_manager.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": required_env("DB_NAME"),
        "USER": required_env("DB_USER"),
        "PASSWORD": required_env("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": str(env_int("DB_PORT", 5432, minimum=1, maximum=65535)),
        "CONN_MAX_AGE": env_int(
            "DB_CONN_MAX_AGE", 60 if IS_PRODUCTION else 0, minimum=0
        ),
        "CONN_HEALTH_CHECKS": IS_PRODUCTION,
        "OPTIONS": {
            "connect_timeout": env_int("DB_CONNECT_TIMEOUT", 5, minimum=1),
        },
    }
}

DB_SSLMODE = os.getenv("DB_SSLMODE", "").strip().lower()
if IS_PRODUCTION and DB_SSLMODE not in {"require", "verify-ca", "verify-full"}:
    raise ImproperlyConfigured(
        "DB_SSLMODE must explicitly require PostgreSQL TLS in production."
    )
if DB_SSLMODE:
    valid_ssl_modes = {
        "disable",
        "allow",
        "prefer",
        "require",
        "verify-ca",
        "verify-full",
    }
    if DB_SSLMODE not in valid_ssl_modes:
        raise ImproperlyConfigured("DB_SSLMODE is not a supported PostgreSQL mode.")
    DATABASES["default"]["OPTIONS"]["sslmode"] = DB_SSLMODE

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kuala_Lumpur"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if IS_PRODUCTION
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "core:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "core:login"

SESSION_COOKIE_SECURE = IS_PRODUCTION
CSRF_COOKIE_SECURE = IS_PRODUCTION
SECURE_SSL_REDIRECT = IS_PRODUCTION
# The platform health probe requests /health/ over plain HTTP and treats the
# HTTPS redirect as a failure. Exempt only that path so every other request
# is still upgraded.
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
SECURE_HSTS_SECONDS = (
    env_int("DJANGO_SECURE_HSTS_SECONDS", 0, minimum=0) if IS_PRODUCTION else 0
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

TRUST_PROXY_SSL_HEADER = env_bool("DJANGO_TRUST_PROXY_SSL_HEADER", default=False)
if TRUST_PROXY_SSL_HEADER:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_FAILURE_VIEW = "core.views.csrf_failure"

# Brute-force protection for the login form. Attempts are stored in
# PostgreSQL rather than the local-memory cache, so the limit holds across
# Gunicorn workers without needing a separate cache service.
AXES_ENABLED = env_bool("DJANGO_AXES_ENABLED", default=True)
AXES_FAILURE_LIMIT = env_int("DJANGO_AXES_FAILURE_LIMIT", 5, minimum=1)
AXES_COOLOFF_TIME = timedelta(
    minutes=env_int("DJANGO_AXES_COOLOFF_MINUTES", 15, minimum=1)
)
# Lock the username/IP pair, not the username alone: locking by username lets
# anyone lock a known user out of their own account from anywhere.
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
# Never write submitted credentials to the access log.
AXES_SENSITIVE_PARAMETERS = ["username", "password"]
AXES_LOCKOUT_TEMPLATE = "429_lockout.html"
AXES_VERBOSE = False
# Behind a trusted proxy REMOTE_ADDR is the proxy itself, which would put every
# attacker in one bucket and let a single attacker lock out the whole site.
# Read the forwarded client address instead, but only when the proxy is trusted
# to overwrite it -- otherwise a client could spoof the header to dodge the
# lockout entirely.
if TRUST_PROXY_SSL_HEADER:
    AXES_IPWARE_PROXY_COUNT = 1
    AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"]
else:
    AXES_IPWARE_PROXY_COUNT = None
    AXES_IPWARE_META_PRECEDENCE_ORDER = ["REMOTE_ADDR"]

LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO").strip().upper()
valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
if LOG_LEVEL not in valid_log_levels:
    raise ImproperlyConfigured("DJANGO_LOG_LEVEL must be a valid logging level.")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "production": {
            "format": "{asctime} | {levelname} | {name} | {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "production",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

INVOICE_SELLER_NAME = os.getenv("INVOICE_SELLER_NAME", "").strip()
INVOICE_SELLER_ADDRESS = os.getenv("INVOICE_SELLER_ADDRESS", "").strip()
