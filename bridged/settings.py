import os
from pathlib import Path

PROJECT_PACKAGE = Path(__file__).resolve().parent

BASE_DIR = PROJECT_PACKAGE.parent


ALLOWED_HOSTS = ["fx.bridged.co", 'bridged.antonskvortsov.com','127.0.0.1']

AUTH_USER_MODEL = 'core.MyUser'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'bridged',
        'USER': 'postgres',
        'PASSWORD': os.environ['POSTGRES_PASSWORD'],
        'HOST': 'postgres',
        'PORT': '5432',
    },
}

DEBUG = False

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    "bootstrap4",
    # User apps
    "core",
    "transfers",
]

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'homepage'

LOGOUT_REDIRECT_URL = 'login'

STATIC_URL = '/static/'
STATIC_ROOT = "static/"

SECRET_KEY = '4*w4nhgsx6@siy$v(hn%9-4v&4r$t+c$pj)%&89fyu=!s_rqz3'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [PROJECT_PACKAGE.joinpath("templates")],
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


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'bridged.urls'

WSGI_APPLICATION = 'bridged.wsgi.application'


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


# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Third-party app settings

# Bootstrap4
BOOTSTRAP4 = {
    'include_jquery': True,
}

# Celery
REDIS_HOST = 'redis'
REDIS_PORT = '6379'

BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'
BROKER_TRANSPORT_OPTIONS = {
    'visibility_timeout': 3600,
}

CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'
WORKER_MAX_TASKS_PER_CHILD = 1


# User settings

BRIDGED_SPIDERS_DIR = BASE_DIR / "scrapyproject" / "spiders"
BRIDGED_SCRAPY_LOGS_DIR = BASE_DIR / "logs"
BRIDGED_RESULTS_DIR = BASE_DIR / "results"
