"""
Django settings for immobilier_project project.
"""

from pathlib import Path
from urllib.parse import urlparse
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Sécurité ──────────────────────────────────────────────────────────────────
SECRET_KEY = config("SECRET_KEY", default="django-insecure-changez-moi")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1,.onrender.com").split(",")

# ── Applications ──────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'django_filters',
    # django-plotly-dash
    'django_plotly_dash.apps.DjangoPlotlyDashConfig',
    'channels',
    # Local
    'properties',
    # ImmoAnalytics dashboards
    'immoanalytics_dash.apps.ImmoAnalyticsDashConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django_plotly_dash.middleware.BaseMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'immobilier_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'immobilier_project.wsgi.application'

# ── Base de données (même Neon PostgreSQL que Scrapy) ─────────────────────────
_db_url = config(
    "DATABASE_URL",
    default="postgresql://neondb_owner:npg_ciyfh8H9bZdj@ep-frosty-wind-a4aoph5q-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
)
_parsed = urlparse(_db_url)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': _parsed.path.strip('/'),
        'USER': _parsed.username,
        'PASSWORD': _parsed.password,
        'HOST': _parsed.hostname,
        'PORT': _parsed.port or 5432,
        'CONN_MAX_AGE': 0,          # Nouvelle connexion à chaque requête (Neon serverless)
        'CONN_HEALTH_CHECKS': True, # Vérifier la connexion avant utilisation
        'OPTIONS': {
            'sslmode':         'require',
            'connect_timeout': 10,
            'keepalives':      1,
            'keepalives_idle': 30,
            'keepalives_interval': 5,
            'keepalives_count': 3,
        },
    }
}

# ── Django REST Framework ─────────────────────────────────────────────────────
CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'https://*.onrender.com',
]

# ── Production (Render) ───────────────────────────────────────────────────────
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE   = True
    CSRF_COOKIE_SECURE      = True

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# ── Internationalisation ──────────────────────────────────────────────────────
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Dakar'
USE_I18N = True
USE_TZ = True

# ── Static files ──────────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
CORS_ALLOW_ALL_ORIGINS = True

# ── django-plotly-dash ────────────────────────────────────────────────────────
X_FRAME_OPTIONS = 'SAMEORIGIN'

PLOTLY_DASH = {
    "ws_route"           : "dpd/ws/channel",
    "http_route"         : "dpd/views",
    "http_poke_enabled"  : True,
    "view_decorator"     : None,
    "cache_arguments"    : True,
    "serve_locally"      : False,
    "insert_demo_viewer" : False,
}

ASGI_APPLICATION = 'immobilier_project.asgi.application'

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

LOGIN_URL = '/immo/login/'