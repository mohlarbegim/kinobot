import os
import sys
import logging
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Test muhitini aniqlash (pytest yoki `manage.py test`). Testlarda haqiqiy SECRET_KEY
# talab qilinmaydi; prod'da pytest bo'lmaydi, shuning uchun bu qoida kuchda qoladi.
_TESTING = 'pytest' in sys.modules or 'test' in sys.argv

# Security: SECRET_KEY must be set in production
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if _TESTING or os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes'):
        SECRET_KEY = 'django-insecure-dev-only-key-do-not-use-in-production'
        logging.warning("WARNING: Using insecure SECRET_KEY. Set SECRET_KEY in .env for production!")
    else:
        raise ValueError("SECRET_KEY environment variable must be set in production!")

DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

# Security: Don't allow all hosts in production.
# Loopback doim ruxsat etiladi - start.py ichki /health/ tekshiruvi 127.0.0.1 ga uradi;
# DEBUG=False bo'lganda ALLOWED_HOSTS ichida bo'lmasa Django 400 (host rad etildi) beradi
# va healthcheck hech qachon 200 olmaydi.
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']

# Foydalanuvchi bergan qo'shimcha hostlar (vergul bilan)
ALLOWED_HOSTS += [h.strip() for h in os.getenv('ALLOWED_HOSTS', '').split(',') if h.strip()]

# Railway domenlari: umumiy *.railway.app + aniq public/private domenlar
if '.railway.app' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('.railway.app')
for _rw_var in ('RAILWAY_PUBLIC_DOMAIN', 'RAILWAY_PRIVATE_DOMAIN'):
    _rw_host = os.getenv(_rw_var, '').strip()
    if _rw_host and _rw_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_rw_host)

# Railway specific: CSRF trusted origins (admin panelga HTTPS orqali kirish uchun)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()]
if 'https://*.railway.app' not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append('https://*.railway.app')
_rw_public = os.getenv('RAILWAY_PUBLIC_DOMAIN', '').strip()
if _rw_public:
    _rw_origin = f'https://{_rw_public}'
    if _rw_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_rw_origin)

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
    'corsheaders',

    # Local apps
    'apps.users',
    'apps.movies',
    'apps.channels',
    'apps.payments',
    'apps.core',
    'apps.api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database configuration
# Railway provides DATABASE_URL automatically
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # Railway PostgreSQL configuration
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=0,  # Railway uchun connection pooling o'chirish
            conn_health_checks=True,
            ssl_require=True,  # Railway PostgreSQL SSL talab qiladi
        )
    }
    # SSL sozlamalari
    DATABASES['default']['OPTIONS'] = {
        'sslmode': 'require',
    }
elif os.getenv('USE_POSTGRES', 'False').lower() in ('true', '1', 'yes'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'kinobot'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Redis faqat REDIS_URL mavjud bo'lganda ishlatiladi
REDIS_URL = os.getenv('REDIS_URL')
USE_REDIS = os.getenv('USE_REDIS', 'False').lower() in ('true', '1', 'yes')

if USE_REDIS and REDIS_URL and not REDIS_URL.startswith('redis://localhost'):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
else:
    # Local memory cache - Redis yo'q bo'lsa
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'uz'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []

# Whitenoise for static files (STORAGES - Django 4.2+; STATICFILES_STORAGE 5.1 da
# olib tashlangan, requirements Django<6.0 ga ruxsat beradi). CompressedStaticFilesStorage
# manifest xatolarini oldini oladi.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Bot settings
BOT_TOKEN = os.getenv('BOT_TOKEN', '')


def _parse_admin_ids(raw: str):
    """ADMINS ni xavfsiz o'qish - raqam bo'lmagan qiymat butun ilovani buzmasligi uchun."""
    admin_ids = []
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            admin_ids.append(int(part))
        except ValueError:
            logging.warning("ADMINS: noto'g'ri (raqam bo'lmagan) qiymat o'tkazib yuborildi: %r", part)
    return admin_ids


ADMINS = _parse_admin_ids(os.getenv('ADMINS', ''))

# Xatolik/bug kanali - bot ishlashida yuz bergan xatolar shu kanalga yuboriladi.
# Bot shu kanalda ADMIN bo'lishi shart. Bo'sh bo'lsa - xabar yuborilmaydi (faqat log).
# Railway'da BUG_CHANNEL_ID env orqali o'zgartirish mumkin.
BUG_CHANNEL_ID = os.getenv('BUG_CHANNEL_ID', '-1004470243589')

# Payment settings
DEFAULT_CARD_NUMBER = os.getenv('DEFAULT_CARD_NUMBER', '8600 0000 0000 0000')
DEFAULT_CARD_HOLDER = os.getenv('DEFAULT_CARD_HOLDER', 'CARD HOLDER')

# ---------------------------------------------------------------------------
# REST API (React admin dashboard)
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    # Barcha endpointlar default holatda faqat is_staff foydalanuvchilar uchun.
    # Login endpointi AllowAny bilan alohida ochiladi.
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAdminUser',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'UPDATE_LAST_LOGIN': True,
}

# CORS: prod'da React Django bilan bir domendan beriladi (CORS shart emas).
# Faqat lokal dev (Vite :5173 -> Django :8000) uchun ochamiz.
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if o.strip()]
if DEBUG:
    CORS_ALLOWED_ORIGINS += ['http://localhost:5173', 'http://127.0.0.1:5173']
CORS_ALLOW_CREDENTIALS = True
