import os
import secrets
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Stateless API: no sessions are signed, so a per-process random key is safe.
# Set SECRET_KEY in the environment for a stable key.
SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(50)
DEBUG = os.environ.get('DEBUG', 'false') == 'true'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'rest_framework',
    'booking',
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
        'NAME': os.environ.get('DB_NAME', 'booking'),
        'USER': os.environ.get('DB_USER', 'booking'),
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

CUSTOMER_CUTOFF_MINUTES = int(os.environ.get('CUSTOMER_CUTOFF_MINUTES', '120'))
SLOT_STEP_MINUTES = int(os.environ.get('SLOT_STEP_MINUTES', '30'))
if CUSTOMER_CUTOFF_MINUTES < 0 or SLOT_STEP_MINUTES not in [15, 30, 60]:
    raise ImproperlyConfigured('Invalid booking policy values')

# Identity service used to verify owner tokens. Required for owner endpoints.
IDENTITY_API_URL = os.environ.get('IDENTITY_API_URL', 'http://localhost:8002').rstrip('/')
IDENTITY_VERIFY_TIMEOUT = float(os.environ.get('IDENTITY_VERIFY_TIMEOUT', '4'))

SEED_DEMO = os.environ.get('SEED_DEMO', 'true') != 'false'
