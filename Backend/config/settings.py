"""
Django settings for the teacher's educational website (config project).

Stack: Django 6 + Tailwind CSS (standalone CLI) + HTMX + django-unfold admin.

The repository is split into three top-level directories:

    Backend/    this Django project (config + content app)
    Frontend/   templates and static sources served to the browser
    Database/   the SQLite file and everything users upload
"""

from datetime import timedelta
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
# Defaults to False: forgetting the variable on a server must not expose
# tracebacks, settings and SQL to the internet. Local development opts in
# explicitly through .env.
DEBUG = env_bool("DJANGO_DEBUG", False)

# In production the key MUST come from the environment: a missing DJANGO_SECRET_KEY
# would otherwise silently fall back to a value that is public in this repository,
# which makes sessions and password-reset tokens forgeable.
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
_KEY_HELP = (
    "Generate one with: python -c \"from django.core.management.utils import "
    'get_random_secret_key; print(get_random_secret_key())" and put it in .env.'
)
if not DEBUG:
    # A weak or placeholder key in production makes sessions, password-reset
    # links and signed cookies forgeable, so refuse to start on one.
    if not SECRET_KEY:
        raise ImproperlyConfigured(f"DJANGO_SECRET_KEY is not set. {_KEY_HELP}")
    if SECRET_KEY.startswith("django-insecure-") or len(SECRET_KEY) < 50:
        raise ImproperlyConfigured(
            f"DJANGO_SECRET_KEY looks like a development placeholder. {_KEY_HELP}"
        )
elif not SECRET_KEY:
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
    "csp",
    "axes",
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
    "content.middleware.AdminAwareCSPMiddleware",
    "content.middleware.SecurityHeadersMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    # Must come last: it needs an authenticated request to record the outcome
    # of a login attempt.
    "axes.middleware.AxesMiddleware",
]

# Brute-force protection wraps the normal backend; Axes must be first.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# The only login on this site is the admin. Django's default lands you on
# /accounts/profile/, a URL nothing here defines — so whenever the sign-in form
# arrives without a ?next=, the teacher logs in and gets a 404.
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/"
LOGOUT_REDIRECT_URL = "/"

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
# Passwords
# ---------------------------------------------------------------------------
# Argon2id first (OWASP's recommended password hash). The remaining hashers stay
# listed so existing PBKDF2 passwords keep working and are re-hashed to Argon2
# on the owner's next successful login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        # ASVS 2.1.1 asks for at least 12 characters.
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Brute-force protection (django-axes)
# ---------------------------------------------------------------------------
# The admin login is the only authentication surface on this site.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(hours=1)
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = ["ip_address", "username"]
AXES_ENABLE_ACCESS_FAILURE_LOG = True
AXES_VERBOSE = True
# Behind a reverse proxy the real client IP arrives in X-Forwarded-For; without
# this every visitor looks like the proxy and one attacker locks out everyone.
AXES_IPWARE_PROXY_COUNT = int(os.getenv("DJANGO_PROXY_COUNT", "0")) or None
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"]

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

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # Hashed filenames in production: long-lived caching without ever
        # serving a stale file, and a changed asset gets a new URL.
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
        )
    },
}

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

# Formats with no dependable magic bytes. Only these may be stored when the
# sniffer cannot identify the content; everything else must be recognisable,
# so a text/HTML payload renamed to .pdf is refused.
UNSNIFFABLE_UPLOAD_TYPES = {"doc"}

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
# Caps a request-body DoS built from thousands of tiny form fields.
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200
DATA_UPLOAD_MAX_NUMBER_FILES = 20
# Files land on disk readable by the owner only, not by every local account.
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750

# ---------------------------------------------------------------------------
# Sessions & cookies
# ---------------------------------------------------------------------------
# JavaScript never needs these cookies, so keep them out of its reach: an XSS
# bug then cannot read a session or the CSRF token.
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # the CSRF token is read from the form, not JS
SESSION_COOKIE_SAMESITE = "Lax"  # survives normal navigation, blocks cross-site POSTs
CSRF_COOKIE_SAMESITE = "Strict"
# Names without the "session"/"csrf" giveaway make automated scanning marginally
# harder and avoid clashing with anything else on the same domain.
SESSION_COOKIE_NAME = "nk_sessionid"
CSRF_COOKIE_NAME = "nk_csrftoken"

SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 hours
SESSION_SAVE_EVERY_REQUEST = True  # idle timeout rather than absolute
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# ---------------------------------------------------------------------------
# HTTP security headers
# ---------------------------------------------------------------------------
# These cost nothing in development and keep dev/production behaviour aligned.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Content Security Policy (django-csp). Everything the site needs is served
# from its own origin — fonts and htmx are vendored under Frontend/static —
# so no external origin is allowed to run or load anything.
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'"],
        "img-src": ["'self'", "data:"],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
        "form-action": ["'self'"],
        "base-uri": ["'none'"],
        "object-src": ["'none'"],
        "frame-ancestors": ["'none'"],
        "frame-src": ["'none'"],
        "manifest-src": ["'self'"],
        "upgrade-insecure-requests": True,
    }
}

# The admin (django-unfold, Alpine.js) ships inline styles and scripts, so the
# strict policy above would break it. It gets a looser one — still same-origin
# only, so an injected <script src="https://evil/"> is refused there too.
# Applied by content.middleware.AdminAwareCSPMiddleware.
ADMIN_CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["'self'", "data:", "blob:"],
        "font-src": ["'self'", "data:"],
        "connect-src": ["'self'"],
        "form-action": ["'self'"],
        "base-uri": ["'none'"],
        "object-src": ["'none'"],
        "frame-ancestors": ["'none'"],
    }
}

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # one year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Only trust this header when a reverse proxy you control sets it.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Gunicorn listens on a unix socket, so there is no TCP peer and
    # REMOTE_ADDR arrives empty — django-ratelimit then raises rather than
    # rate-limit everyone as one visitor, which took the contact form down with
    # a 500 on every submission. nginx *overwrites* X-Real-IP on every request
    # (proxy_set_header X-Real-IP $remote_addr), so a visitor cannot forge it,
    # and nothing but nginx can reach the socket.
    RATELIMIT_IP_META_KEY = "HTTP_X_REAL_IP"

# ---------------------------------------------------------------------------
# Email — notifications for messages sent from the contact form
# ---------------------------------------------------------------------------
# Without SMTP credentials the mail is printed to the console instead of being
# sent, so development never needs a mail server and never emails anyone by
# accident. Set DJANGO_EMAIL_HOST in .env to switch it on.
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("DJANGO_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_PASSWORD", "")
EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("DJANGO_EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = 10  # never let a stuck mail server hang a visitor's request
EMAIL_SUBJECT_PREFIX = "[Ιστοσελίδα] "

EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend"
)

# The "From" address. Many providers refuse to send mail whose From is not the
# authenticated account, so it defaults to the SMTP user.
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_FROM_EMAIL", EMAIL_HOST_USER or "noreply@localhost")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Who gets told about a new contact message. Left empty, the site emails every
# active superuser at the address on their account.
CONTACT_NOTIFY_EMAILS = env_list("DJANGO_CONTACT_NOTIFY_EMAILS")

# ---------------------------------------------------------------------------
# Caching (used by the contact form's rate limit)
# ---------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "nk-default",
    }
}

# ---------------------------------------------------------------------------
# Logging — security events go to a file that survives a restart
# ---------------------------------------------------------------------------
LOG_DIR = Path(os.getenv("DJANGO_LOG_DIR", PROJECT_ROOT / "Database" / "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "security.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        # Suspicious operations, host header attacks, CSRF failures.
        "django.security": {
            "handlers": ["console", "security_file"],
            "level": "INFO",
            "propagate": False,
        },
        # 4xx/5xx raised while handling a request.
        "django.request": {
            "handlers": ["console", "security_file"],
            "level": "WARNING",
            "propagate": False,
        },
        # Login attempts, lockouts.
        "axes": {
            "handlers": ["console", "security_file"],
            "level": "INFO",
            "propagate": False,
        },
        # This project's own security events (uploads, rate limits, downloads).
        "content.security": {
            "handlers": ["console", "security_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

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
