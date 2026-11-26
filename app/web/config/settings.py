import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def _secret_key():
    # The web service signs its server-side session records with this key, so
    # every worker process must share one value. When SECRET_KEY is not set,
    # a random key is generated once and kept in a private file next to the
    # session database (never committed); deleting it just ends all sessions.
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    key_file = Path(os.environ.get('WEB_DB_PATH', str(BASE_DIR / 'web.sqlite3'))).parent / '.web-secret-key'
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_urlsafe(50)
    key_file.write_text(key)
    key_file.chmod(0o600)
    return key


SECRET_KEY = _secret_key()
DEBUG = os.environ.get('DEBUG', 'false') == 'true'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'whitenoise.runserver_nostatic',
    'pages',
]
MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.messages.context_processors.messages',
        'pages.context.common',
    ]},
}]
WSGI_APPLICATION = 'config.wsgi.application'

# The web service owns no business data. Its private SQLite file stores only
# its own server-side sessions; it is never shared with the other services.
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': os.environ.get('WEB_DB_PATH', str(BASE_DIR / 'web.sqlite3')), 'OPTIONS': {'timeout': 20}}}

LANGUAGE_CODE = 'ar'
TIME_ZONE = 'Africa/Cairo'
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
WHITENOISE_USE_FINDERS = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 1800
SESSION_SAVE_EVERY_REQUEST = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True

# Public HTTPS entry (a Cloudflare Quick Tunnel in front of the gateway).
# All four default to off, so local runs and kubectl port-forward keep today's
# behavior; the web-config ConfigMap turns them on for the deployed pod.
# The gateway forwards X-Forwarded-Proto only on its tunnel-only listener
# (8001, cloudflared-only), which is what bounds the trust in that header.
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if o]
if os.environ.get('TRUST_X_FORWARDED_PROTO', 'false') == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false') == 'true'
CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', 'false') == 'true'

BOOKING_API_URL = os.environ.get('BOOKING_API_URL', 'http://localhost:8001').rstrip('/')
IDENTITY_API_URL = os.environ.get('IDENTITY_API_URL', 'http://localhost:8002').rstrip('/')
API_TIMEOUT = float(os.environ.get('API_TIMEOUT', '6'))

# Displayed policy values; the booking and identity services enforce the real
# rules and keep their own copies.
CUSTOMER_CUTOFF_MINUTES = int(os.environ.get('CUSTOMER_CUTOFF_MINUTES', '120'))
LOCKOUT_MINUTES = int(os.environ.get('LOCKOUT_MINUTES', '15'))
SLOT_STEP_MINUTES = int(os.environ.get('SLOT_STEP_MINUTES', '30'))
