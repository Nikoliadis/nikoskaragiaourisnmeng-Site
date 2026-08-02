"""
Django settings for the teacher's educational website (config project).

Stack: Django 6 + Tailwind CSS (standalone CLI) + HTMX + django-unfold admin.

The repository is split into three top-level directories:

    Backend/    this Django project (config + content app)
    Frontend/   templates and static sources served to the browser
    Database/   the SQLite file and everything users upload
"""

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv
import os

# BASE_DIR is Backend/ (the directory holding manage.py).
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / "Frontend"
DATABASE_DIR = PROJECT_ROOT / "Database"

# Load environment variables from a local .env file (never commit it).
load_dotenv(PROJECT_ROOT / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core security
# ---------------------------------------------------------------------------
DEBUG = env_bool("DJANGO_DEBUG", True)

# In production the key MUST come from the environment: a missing DJANGO_SECRET_KEY
# would otherwise silently fall back to a value that is public in this repository,
# which makes sessions and password-reset tokens forgeable.
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is not set. Generate one with "
            "`python -c \"from django.core.management.utils import get_random_secret_key;"
            " print(get_random_secret_key())\"` and put it in your .env file."
        )
    SECRET_KEY = "django-insecure-development-only-key-do-not-use-in-production"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # django-unfold must come before django.contrib.admin.
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "django_htmx",
    # Local
    "content",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [FRONTEND_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "content.context_processors.navigation",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATABASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalization — Greek
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "el"
TIME_ZONE = "Europe/Athens"
USE_I18N = True
USE_TZ = True

LANGUAGES = [("el", _("Ελληνικά"))]

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [FRONTEND_DIR / "static"]
STATIC_ROOT = FRONTEND_DIR / "staticfiles"

# Public media (images used in announcements, hero, etc.) served normally.
MEDIA_URL = "media/"
MEDIA_ROOT = DATABASE_DIR / "media"

# PROTECTED storage: documents live OUTSIDE the public media root and are
# only ever served through the protected download view (content.views.download).
# In production, place this directory outside the web server's document root.
PROTECTED_MEDIA_ROOT = Path(
    os.getenv("PROTECTED_MEDIA_ROOT", DATABASE_DIR / "protected_media")
)

# ---------------------------------------------------------------------------
# File upload limits & whitelist (used by content.validators)
# ---------------------------------------------------------------------------
# Max size per uploaded document (bytes). Default 25 MB.
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 25 * 1024 * 1024))

# Allowed extensions -> set of allowed sniffed MIME types.
ALLOWED_UPLOAD_TYPES = {
    "pdf": {"application/pdf"},
    "doc": {"application/msword"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",  # docx is a zip container; filetype sniffs it as zip
    },
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png": {"image/png"},
}

# The MIME type stored on the model and sent back by the download view. Derived
# from the extension *after* it has been checked against the file's magic bytes,
# so it never depends on the Content-Type the browser claimed at upload time.
CANONICAL_UPLOAD_MIME = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
}

# Reject upload streams larger than this before they hit disk.
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # spill to temp file above 5 MB

# ---------------------------------------------------------------------------
# Security hardening (active when DEBUG is off)
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# django-unfold admin configuration (Greek)
# ---------------------------------------------------------------------------
UNFOLD = {
    "SITE_TITLE": "Διαχείριση Ιστοσελίδας",
    "SITE_HEADER": "Πίνακας Διαχείρισης",
    "SITE_SUBHEADER": "Νικόλαος Καραγκιαούρης — Μηχανολόγος ΠΕ82",
    "SITE_URL": "/",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "THEME": None,  # allow light/dark toggle
    "COLORS": {
        "primary": {
            "50": "240 249 255",
            "100": "224 242 254",
            "200": "186 230 253",
            "300": "125 211 252",
            "400": "56 189 248",
            "500": "14 165 233",
            "600": "2 132 199",
            "700": "3 105 161",
            "800": "7 89 133",
            "900": "12 74 110",
            "950": "8 47 73",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": _("Περιεχόμενο"),
                "separator": True,
                "items": [
                    {
                        "title": _("Αρχική Πίνακα"),
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:index"),
                    },
                    {
                        "title": _("Κατηγορίες"),
                        "icon": "folder",
                        "link": reverse_lazy("admin:content_category_changelist"),
                    },
                    {
                        "title": _("Έγγραφα / Υλικό"),
                        "icon": "description",
                        "link": reverse_lazy("admin:content_document_changelist"),
                    },
                    {
                        "title": _("Ανακοινώσεις"),
                        "icon": "campaign",
                        "link": reverse_lazy("admin:content_announcement_changelist"),
                    },
                    {
                        "title": _("Μηνύματα Επικοινωνίας"),
                        "icon": "mail",
                        "link": reverse_lazy("admin:content_contactmessage_changelist"),
                    },
                ],
            },
        ],
    },
}
