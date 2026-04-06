# cybercraft/cybercraft/settings.py
from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------------------
# CELERY CONFIG (must be early!)
# -------------------------------
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")

# Safety print for logs
print(f"[CELERY] BROKER: {CELERY_BROKER_URL}")
print(f"[CELERY] BACKEND: {CELERY_RESULT_BACKEND}")

if not CELERY_BROKER_URL:
    print("[WARNING] CELERY_BROKER_URL not set. Celery tasks will not work.")

# --- LOAD ENVIRONMENT VARIABLES ---
# Try multiple locations for .env
env_locations = [
    os.path.join(BASE_DIR, ".env"),
    os.path.join(BASE_DIR, "..", ".env"),
    ".env",
]

env_found = False
for loc in env_locations:
    if os.path.exists(loc):
        load_dotenv(loc, override=True)
        print(f"[Config] Loaded environment from: {loc}")
        env_found = True
        break

if not env_found:
    print("[Config] WARNING: No .env file found. Using system environment variables.")

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "generate-a-strong-key-here-for-now")
DEBUG = os.getenv("DEBUG", "False") == "True"

# Allowed hosts - PRODUCTION
ALLOWED_HOSTS = [
    "techspacehub.co.ke",
    "www.techspacehub.co.ke",
    "api.techspacehub.co.ke",
    "adrianchan101-techspacehub-backend.hf.space",
    ".hf.space",
]

# Frontend/Backend URLs - PRODUCTION
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://techspacehub.co.ke")
BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "https://adrianchan101-techspacehub-backend.hf.space",
)
SITE_NAME = "TechSpace"

# Brevo SMTP Configuration (replaced SendGrid)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp-relay.brevo.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@techspacehub.co.ke")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@techspacehub.co.ke")

# Async email via Celery (prevent blocking registration)
EMAIL_BACKEND = "django_celery_email.backends.CeleryEmailBackend"
CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Application definition
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third-party apps
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "dj_rest_auth",
    "dj_rest_auth.registration",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
    "django_celery_email",  # async email via Celery
    # my apps
    "accounts",
    "courses",
    "library",
    "dashboard",
    "chat",
    "labs",
    "billing",
    "live_classes",
    "management",
    "services",
    # Hub education-path apps
    "progress",
    "payments",
    "staff_dashboard",
    # AI Website Builder — credit system
    "builder",
    # Celery Results (store in DB instead of Redis)
    "django_celery_results",
]


SITE_ID = 1

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "accounts.middleware.SocialAuthRedirectMiddleware",
    # "middleware.large_request.LargeRequestMiddleware",
]

ROOT_URLCONF = "cybercraft.urls"

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

# ========== ENVIRONMENT DETECTION ==========
IS_RENDER = os.getenv("RENDER") == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Use ASGI for Render (Daphne + WebSocket support)
if IS_RENDER or ENVIRONMENT == "production":
    ASGI_APPLICATION = "cybercraft.asgi.application"
else:
    WSGI_APPLICATION = "cybercraft.wsgi.application"


# --- REDIS & CELERY CONFIGURATION (Upstash) ---
# All Redis URLs from environment variables (no localhost fallbacks)
REDIS_URL = os.getenv("REDIS_URL", "")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "django-db")

print(f"[Config] Redis URL configured from Upstash")
if REDIS_URL:
    # Mask sensitive parts for logging
    masked_url = REDIS_URL.split("@")[1] if "@" in REDIS_URL else "<redacted>"
    print(f"[Config] Broker: {masked_url}")
else:
    print(f"[WARNING] REDIS_URL not set. Celery will not work.")

# ========== CHANNELS (WebSocket) ==========
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
                "capacity": 1500,
                "expiry": 10,
            },
        },
    }
else:
    # Fallback to in-memory for development (not production-safe)
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }

# Database
DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL"),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Fallback to individual variables if DATABASE_URL is missing
if not DATABASES.get("default") or not DATABASES["default"].get("ENGINE"):
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
    }

# Ensure Postgres SSL
if DATABASES["default"].get("ENGINE") == "django.db.backends.postgresql":
    DATABASES["default"].setdefault("OPTIONS", {})["sslmode"] = "require"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)

# Allauth settings
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]

# Social account settings - PRODUCTION
SOCIALACCOUNT_EMAIL_VERIFICATION = "optional"
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_STORE_TOKENS = True
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_AUTO_SIGNUP = True
ACCOUNT_LOGOUT_ON_GET = True

# Redirect URLs - PRODUCTION
LOGIN_REDIRECT_URL = f"{FRONTEND_URL}/dashboard"
ACCOUNT_LOGOUT_REDIRECT_URL = f"{FRONTEND_URL}/login"
SOCIALACCOUNT_LOGIN_REDIRECT_URL = f"{FRONTEND_URL}/dashboard"

# Combine ALLOWED_HOSTS from environment variable and hardcoded ones
env_allowed_hosts = os.getenv("ALLOWED_HOSTS", "").split(",")
ALLOWED_HOSTS = [
    "techspacehub.co.ke",
    "www.techspacehub.co.ke",
    "api.techspacehub.co.ke",
    "techspacehub-backend.onrender.com",
    "https://adrianchan101-techspacehub-backend.hf.space",
] + [host for host in env_allowed_hosts if host]

# CORS settings - PRODUCTION
CORS_ALLOWED_ORIGINS = [
    "https://techspacehub.co.ke",
    "https://www.techspacehub.co.ke",
    "https://api.techspacehub.co.ke",
    "https://techspacehub-backend.onrender.com",
    "https://adrianchan101-techspacehub-backend.hf.space",
]

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = [
    "content-disposition",
    "x-total-count",
    "x-total-pages",
]

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "HEAD",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]
ALLOWED_HOSTS = list(set(ALLOWED_HOSTS))
CSRF_TRUSTED_ORIGINS = [
    "https://techspacehub.co.ke",
    "https://www.techspacehub.co.ke",
    "https://api.techspacehub.co.ke",
    "https://techspacehub-backend.onrender.com",
    "https://adrianchan101-techspacehub-backend.hf.space",
]


# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "20/min",
        "user": "200/min",
        "login": "5/min",
        "signup": "3/min",
        "payment": "10/hour",  # Prevent payment spam
        "ai_generate": "5/hour",  # Limit intensive CPU processing to 5 websites per user per hour
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
    "PAGE_SIZE_QUERY_PARAM": "page_size",
    "MAX_PAGE_SIZE": 1000,
}


# Social providers - PRODUCTION
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "OAUTH_PKCE_ENABLED": True,
    },
}

# Additional settings to ensure proper site info
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[TechSpace] "
EMAIL_SUBJECT_PREFIX = "[TechSpace] "

# Social account adapter to customize the flow
SOCIALACCOUNT_ADAPTER = "accounts.adapters.CustomSocialAccountAdapter"

# JWT Settings for longer token expiration
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=2),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# File upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10240

X_FRAME_OPTIONS = "ALLOWALL"  # Allow embedding generated HTML in frontend iframe
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

# Enhanced Security Settings
if not DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # HSTS Settings (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Session and Cookie Security (always enforced)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 86400  # 24 hours

# API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Payment configurations
# === LIPANA M-Pesa STK Push (PRIMARY) ===
LIPANA_SECRET_KEY = os.getenv("LIPANA_SECRET_KEY", "")
LIPANA_WEBHOOK_SECRET = os.getenv("LIPANA_WEBHOOK_SECRET", "")
LIPANA_ENVIRONMENT = os.getenv("LIPANA_ENVIRONMENT", "production")

# === STRIPE (Card Payments) ===
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# === LEGACY M-Pesa (Safaricom - Deprecated, kept for backward compatibility) ===
MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "")
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "")
MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE", "")
MPESA_PASSKEY = os.getenv("MPESA_PASSKEY", "")

ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "accounts": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "billing": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# For Render.com and other cloud platforms
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Increase request size for cloud platforms
if not DEBUG:
    # These help with larger requests on cloud platforms
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Services Settings
REPORTS_ROOT = os.path.join(MEDIA_ROOT, "reports")

# Celery Configuration
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Free tier optimizations for Upstash Redis (10K commands/day limit)
CELERY_RESULT_BACKEND = "django-db"  # Store results in Supabase, not Redis
CELERY_TASK_IGNORE_RESULT = True  # Don't store task results by default (saves Redis commands)
CELERY_ACKS_LATE = True  # Acknowledge after task completes (safer on free tier)
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Only prefetch 1 task at a time (prevents hoarding)
CELERY_TASK_MAX_RETRIES = 1
CELERY_TASK_DEFAULT_RETRY_DELAY = 60

# Global rate limiting to protect free Redis limits (2 scans/hour = ~48 commands/day)
# Each scan uses ~24 Redis commands (reserve, ack, result storage if enabled)
# This keeps us well under 10K/day even with other app usage
CELERY_TASK_ANNOTATIONS = {
    'services.audits.tasks.run_automated_scan': {
        'rate_limit': '2/h',  # Enforced globally as backup
    }
}

# Worker settings for free tier (low memory)
CELERY_WORKER_MAX_TASKS_PER_CHILD = 10  # Restart worker after 10 tasks (prevents memory leaks)
CELERY_WORKER_SEND_TASK_EVENTS = False  # Disable events (saves Redis commands)
CELERY_TASK_SEND_SENT_EVENT = False
