import os
import secrets
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Stateless API: no sessions are signed, so a per-process random key is safe.
SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(50)
DEBUG = os.environ.get('DEBUG', 'false') == 'true'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'rest_framework',
    'accounts',
]
MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

if os.environ.get('DB_ENGINE', 'postgresql') == 'sqlite':
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': os.environ.get('DB_PATH', str(BASE_DIR / 'dev.sqlite3')), 'OPTIONS': {'timeout': 20}}}
else:
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'identity'),
        'USER': os.environ.get('DB_USER', 'identity'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }}

LANGUAGE_CODE = 'ar'
TIME_ZONE = 'Africa/Cairo'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'UNAUTHENTICATED_USER': None,
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
]

LOCKOUT_MINUTES = int(os.environ.get('LOCKOUT_MINUTES', '15'))
if LOCKOUT_MINUTES < 1:
    raise ImproperlyConfigured('Invalid lockout policy value')

# Owner tokens are opaque random strings; only their SHA-256 hash is stored.
TOKEN_TTL_HOURS = int(os.environ.get('TOKEN_TTL_HOURS', '12'))
if TOKEN_TTL_HOURS < 1:
    raise ImproperlyConfigured('Invalid token TTL')
