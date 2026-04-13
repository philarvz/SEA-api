import os
from pathlib import Path
from datetime import timedelta
from decouple import config
from loguru import logger

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-default-key-change-this')

# Encryption key for sensitive data (AES-256)
# Generate with: import base64, os; base64.b64encode(os.urandom(32)).decode()
# This MUST be stored in .env file
ENCRYPTION_KEY = config('ENCRYPTION_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_spectacular',
    
    # Local apps
    'apps.authentication',
    'apps.core',
    'apps.users',
    'apps.academic',
    'apps.questions',
    'apps.exams',
    'apps.answers',
    'apps.audit',
]

# Custom user model
AUTH_USER_MODEL = 'users.User'

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.core.middleware.RequestContextMiddleware',
    'apps.audit.middleware.AuditUserMiddleware',
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


USE_DATABASE = config('USE_DATABASE', default=False, cast=bool)

if USE_DATABASE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='postgres'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

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


LANGUAGE_CODE = 'es-mx'

TIME_ZONE = 'America/Mexico_City'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Default throttle rate shared by several authenticated endpoints (60 req/min).
# Extracted to avoid duplicating the literal and satisfy static-analysis rules.
_THROTTLE_RATE_STANDARD = '60/minute'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.audit.authentication.AuditJWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # CWE-770 / OWASP API4 — rate limiting to prevent brute-force and DoS
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': config('THROTTLE_ANON_RATE', default='30/minute'),
        'user': config('THROTTLE_USER_RATE', default='120/minute'),
        'student_assignments': config('THROTTLE_STUDENT_RATE', default=_THROTTLE_RATE_STANDARD),
        'created_by_me': config('THROTTLE_CREATED_BY_ME_RATE', default=_THROTTLE_RATE_STANDARD),
        'teacher_subjects': config('THROTTLE_TEACHER_SUBJECTS_RATE', default=_THROTTLE_RATE_STANDARD),
        'teacher_my_groups': config('THROTTLE_TEACHER_MY_GROUPS_RATE', default=_THROTTLE_RATE_STANDARD),
        'grade_export': config('THROTTLE_GRADE_EXPORT_RATE', default='30/minute'),
    },
}


# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME', default=60, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(minutes=config('JWT_REFRESH_TOKEN_LIFETIME', default=1440, cast=int)),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'UPDATE_LAST_LOGIN': False,

    'ALGORITHM': config('JWT_ALGORITHM', default='HS256'),
    'SIGNING_KEY': config('JWT_SECRET_KEY', default='legacydevs'),
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id_user',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',

    'JTI_CLAIM': 'jti',

    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}


# CORS Configuration - Open for development
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-active-role',
    'x-csrftoken',
    'x-requested-with',
]


# Mock Credentials Configuration
MOCK_EMAIL = config('MOCK_EMAIL', default='admin@legacydevs.com')
MOCK_PASSWORD = config('MOCK_PASSWORD', default='1234')


# ------------------------------------------------------------------
# E-mail Configuration (Gmail SMTP with App Password)
# ------------------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='20233tn070@utez.edu.mx')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='oipe vgdd faaa jyoc')
DEFAULT_FROM_EMAIL = config(
    'DEFAULT_FROM_EMAIL',
    default='SEA Sistema <20233tn070@utez.edu.mx>',
)
# Timeout de conexión SMTP en segundos
EMAIL_TIMEOUT = 10


# Spectacular (Swagger) Configuration
SPECTACULAR_SETTINGS = {
    'TITLE': 'SEA-API',
    'DESCRIPTION': 'Sistema de Evaluación Académica - API para gestión de exámenes y evaluaciones',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api/',
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
    },
    # Configuración de seguridad para JWT
    'SECURITY': [{'bearerAuth': []}],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'bearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
                'description': 'JWT Authorization header using the Bearer scheme. Example: "Bearer {token}"'
            }
        }
    },
    # Especificar explícitamente que AuditJWTAuthentication usa el esquema bearerAuth
    'AUTHENTICATION_WHITELIST': [
        'apps.audit.authentication.AuditJWTAuthentication',
    ],
    # Evita el warning "multiple names for the same choice set" en DifficultyEnum
    # (tanto Question como Exam definen DIFFICULTY_CHOICES con los mismos valores)
    'ENUM_NAME_OVERRIDES': {
        'DifficultyEnum': 'apps.questions.models.Question.DIFFICULTY_CHOICES',
    },
}

LOGGING_CONFIG = None

os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# Loguru constants
LOGURU_FORMAT = "{time: YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}: {function}: {line} - {message}"
LOGURU_ROTATION = '10 MB'
LOGURU_RETENTION = '2 days'

LOGURU_LOGGINS = {
    'handlers': [
        {
            'sink': BASE_DIR / 'logs/debug.log',
            'level': 'DEBUG',
            'filter': lambda record: record['level'].no == logger.level('DEBUG').no,
            'format': LOGURU_FORMAT,
            'rotation': LOGURU_ROTATION,
            'retention': LOGURU_RETENTION,
            'compression': 'zip',
        },
        {
            'sink': BASE_DIR / 'logs/error.log',
            'level': 'ERROR',
            'filter': lambda record: record['level'].no == logger.level('ERROR').no,
            'format': LOGURU_FORMAT,
            'rotation': LOGURU_ROTATION,
            'retention': LOGURU_RETENTION,
            'compression': 'zip'
        }
        ,
        {
            'sink': BASE_DIR / 'logs/info.log',
            'level': 'INFO',
            'filter': lambda record: record['level'].no == logger.level('INFO').no,
            'format': LOGURU_FORMAT,
            'rotation': LOGURU_ROTATION,
            'retention': LOGURU_RETENTION,
            'compression': 'zip',
        },
           {
            'sink': BASE_DIR / 'logs/warning.log',
            'level': 'WARNING',
            'filter': lambda record: record['level'].no == logger.level('WARNING').no,
            'format': LOGURU_FORMAT,
            'rotation': LOGURU_ROTATION,
            'retention': LOGURU_RETENTION,
            'compression': 'zip'
        },
        {
            'sink': BASE_DIR / 'logs/critical.log',
            'level': 'CRITICAL',
            'filter': lambda record: record['level'].no == logger.level('CRITICAL').no,
            'format': LOGURU_FORMAT,
            'rotation': LOGURU_ROTATION,
            'retention': LOGURU_RETENTION,
            'compression': 'zip'
        }
    ]
}

logger.configure(**LOGURU_LOGGINS)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'loguru': {
            'class': 'SEA-api.interceptor.InterceptorHandler',
        },
    },
    'root': {
        'handlers': ['loguru'],
        'level': 'DEBUG',
    },
}


# ------------------------------------------------------------------
# APScheduler Configuration
# ------------------------------------------------------------------
# APScheduler is used to automatically advance academic levels on:
# - January 1 at 00:00 (Periodo Enero-Abril)
# - May 1 at 00:00 (Periodo Mayo-Agosto)
# - September 1 at 00:00 (Periodo Septiembre-Diciembre)
APSCHEDULER_ENABLED = config('APSCHEDULER_ENABLED', default=True, cast=bool)