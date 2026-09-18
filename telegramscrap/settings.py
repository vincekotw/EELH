"""
Django settings for telegramscrap project.

Detecta el entorno automáticamente:
  - Si DATABASE_URL está definida → producción (Neon PostgreSQL)
  - Si no → desarrollo (SQLite local)
"""

import os
from pathlib import Path

import dj_database_url


# ═══════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════
BASE_DIR = Path(__file__).resolve().parent.parent

# Crear carpeta de logs si no existe
(BASE_DIR / 'logs').mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════
# ENTORNO
# ═══════════════════════════════════════════════════════════════
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'dev-insecure-key-change-me-please',
)

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get(
        'ALLOWED_HOSTS',
        'localhost,127.0.0.1,0.0.0.0',
    ).split(',') if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    s.strip() for s in os.environ.get(
        'CSRF_TRUSTED_ORIGINS',
        'http://localhost:8000,http://127.0.0.1:8000',
    ).split(',') if s.strip()
]


# ═══════════════════════════════════════════════════════════════
# SEGURIDAD (solo en producción)
# ═══════════════════════════════════════════════════════════════
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# ═══════════════════════════════════════════════════════════════
# APLICACIONES
# ═══════════════════════════════════════════════════════════════
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

LOCAL_APPS = [
    'apps.telegram_base',
    'apps.circuitos',
    'apps.metricas',
    'apps.usuarios',
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS


# ═══════════════════════════════════════════════════════════════
# MIDDLEWARE
# ═══════════════════════════════════════════════════════════════
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',            # ← static en prod
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.usuarios.middleware.TrackingMiddleware',           # ← tracking
]


# ═══════════════════════════════════════════════════════════════
# URLS / WSGI
# ═══════════════════════════════════════════════════════════════
ROOT_URLCONF = 'telegramscrap.urls'
WSGI_APPLICATION = 'telegramscrap.wsgi.application'


# ═══════════════════════════════════════════════════════════════
# TEMPLATES
# ═══════════════════════════════════════════════════════════════
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.usuarios.context_processors.notificaciones_context',
            ],
        },
    },
]


# ═══════════════════════════════════════════════════════════════
# BASE DE DATOS
# ═══════════════════════════════════════════════════════════════
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,
        ),
    }
    print('[DB] PostgreSQL (Neon)')
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        },
    }
    print('[DB] SQLite (local)')


# ═══════════════════════════════════════════════════════════════
# AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'usuarios:login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'


# ═══════════════════════════════════════════════════════════════
# INTERNACIONALIZACIÓN
# ═══════════════════════════════════════════════════════════════
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'America/Havana'
USE_I18N = True
USE_TZ = True


# ═══════════════════════════════════════════════════════════════
# STATIC FILES
# ═══════════════════════════════════════════════════════════════
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ═══════════════════════════════════════════════════════════════
# EMAIL
# ═══════════════════════════════════════════════════════════════
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# ═══════════════════════════════════════════════════════════════
# TELEGRAM SCRAPER
# ═══════════════════════════════════════════════════════════════
TELEGRAM_CANAL_USERNAME = 'EmpresaElectricaDeLaHabana'
TELEGRAM_CANAL_URL = f'https://t.me/{TELEGRAM_CANAL_USERNAME}'
TELEGRAM_ID_INICIAL = 81270
TELEGRAM_PAUSA = 1.2
TELEGRAM_TIMEOUT = 15


# ═══════════════════════════════════════════════════════════════
# SCHEDULER INTERNO (APScheduler)
# ═══════════════════════════════════════════════════════════════
# En desarrollo: APScheduler corre cada 5 minutos dentro del
# proceso runserver.
# En producción: se desactiva y se usa el cron externo
# (/api/cron/tick/ llamado por cron-job.org cada 5 min).
ENABLE_SCHEDULER = os.environ.get('ENABLE_SCHEDULER', 'True').lower() == 'true'
SCHEDULER_INTERVALO_MINUTOS = int(
    os.environ.get('SCHEDULER_INTERVALO_MINUTOS', '5'),
)

# Token para el endpoint /api/cron/tick/ (producción)
CRON_TOKEN = os.environ.get('CRON_TOKEN', '')


# ═══════════════════════════════════════════════════════════════
# WEB PUSH (Fase 6 — se configurará más adelante)
# ═══════════════════════════════════════════════════════════════
WEBPUSH_SETTINGS = {
    'VAPID_PUBLIC_KEY': os.environ.get('VAPID_PUBLIC_KEY', ''),
    'VAPID_PRIVATE_KEY': os.environ.get('VAPID_PRIVATE_KEY', ''),
    'VAPID_ADMIN_EMAIL': os.environ.get(
        'VAPID_ADMIN_EMAIL', 'admin@example.com',
    ),
}


# ═══════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '{asctime} [{levelname}] {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file_scheduler': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(BASE_DIR / 'logs' / 'scheduler.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'simple',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'apps.telegram_base.scheduler': {
            'handlers': ['console', 'file_scheduler'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}