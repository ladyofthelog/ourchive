"""
Django settings for ourchive_app project.

Generated by 'django-admin startproject' using Django 2.2.2.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.2/ref/settings/
"""

import os
from dotenv import load_dotenv, find_dotenv


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(find_dotenv())

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('OURCHIVE_SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('OURCHIVE_DEBUG') == 'True'

hosts = []
if os.getenv('OURCHIVE_DEV') == 'True':
    hosts = ["127.0.0.1:8000", "127.0.0.1", "host.docker.internal", "localhost", "http://localhost:8000",]
else:
    hosts = ["ourchive-dev.stopthatimp.net", "45.79.159.247"]

ALLOWED_HOSTS = hosts

API_PROTOCOL = 'http://' if DEBUG else 'https://'

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'frontend',
    'django.contrib.postgres',
    'corsheaders',
    'anymail',
    'api'
    #'background_task',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]

CORS_ALLOWED_ORIGINS = [
    'http://127.0.0.1:8000',
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGIN_REGEXES = [
    'http://127.0.0.1:8000',
]

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
]

CAPTCHA_SITE_KEY = os.environ.get('OURCHIVE_CAPTCHA_SITE_KEY')
CAPTCHA_SECRET = os.environ.get('OURCHIVE_CAPTCHA_SECRET')
USE_CAPTCHA = os.environ.get('OURCHIVE_USE_CAPTCHA')
CAPTCHA_PROVIDER = os.environ.get('OURCHIVE_CAPTCHA_PROVIDER')
CAPTCHA_PARAM = os.environ.get('OURCHIVE_CAPTCHA_PARAM')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

ROOT_URLCONF = 'ourchive_app.urls'

MEDIA_ROOT = os.getenv('OURCHIVE_MEDIA_ROOT')

MEDIA_URL = os.getenv('OURCHIVE_MEDIA_URL')

TMP_ROOT = os.getenv('OURCHIVE_TMP_ROOT')

FILE_PROCESSOR = 'local'

S3_BUCKET = 'ourchive_media'

SEARCH_BACKEND = 'POSTGRES'

if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    EMAIL_FILE_PATH = BASE_DIR+"/sent_emails"
else:
    ANYMAIL = {
        "MAILGUN_API_KEY": os.getenv("OURCHIVE_MAILGUN_API_KEY"),
        "MAILGUN_SENDER_DOMAIN": 'ourchive-mail.stopthatimp.net', 
    }
    EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend" 
DEFAULT_FROM_EMAIL = "admin@ourchive-dev.stopthatimp.net"  
SERVER_EMAIL = "serveradmin@ourchive-dev.stopthatimp.net" 


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        "DIRS": [os.path.join(BASE_DIR,"templates")],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'frontend.context_processors.set_style',
                'frontend.context_processors.set_has_notifications',
                'frontend.context_processors.set_content_pages',
                'frontend.context_processors.set_captcha',
                'frontend.context_processors.load_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'ourchive_app.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ourchive_db',
        'USER': 'ourchive',
        'PASSWORD': os.getenv('OURCHIVE_DB_PW'),
        'HOST': 'localhost',
        'PORT': '5432',
    }
}


# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTH_USER_MODEL = 'api.User'


# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static/')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'api.custom_exception_handler.custom_exception_handler',
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly'
    ],
     'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'api.custom_pagination.CustomPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '1000/day',
        'user': '10000/day'
    }
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{name} {levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'ourchive.log',
            'formatter': 'simple',
        }
    },
    'loggers': {
        '': {
            'level': 'DEBUG',
            'handlers': ['file'],
        },
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.getenv('OURCHIVE_DJANGO_CACHE'),
    }
}
