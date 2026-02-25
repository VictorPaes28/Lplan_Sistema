"""
Django settings for Sistema LPLAN Central - Unificado.
"""
from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

# ALLOWED_HOSTS: em produção defina no .env (ex: ALLOWED_HOSTS=seudominio.com.br,www.seudominio.com.br)
_hosts = os.environ.get('ALLOWED_HOSTS', '').strip()
ALLOWED_HOSTS = [h.strip() for h in _hosts.split(',') if h.strip()] if _hosts else []

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_filters',
    'treebeard',
    # LPLAN Apps
    'core',  # Diario_obra
    'gestao_aprovacao',  # Gestao_aprovacao (renomeado de obras)
    'mapa_obras',  # Mapa_Controle/obras (renomeado)
    'accounts',  # Mapa_Controle/accounts
    'suprimentos',  # Mapa_Controle/suprimentos
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'core.middleware.SecurityHeadersMiddleware',
]

ROOT_URLCONF = 'lplan_central.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',  # Templates globais
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Context processors dos apps
                'core.context_processors.sidebar_counters',
                'gestao_aprovacao.context_processors.notificacoes_count',
                'gestao_aprovacao.context_processors.user_context',
                'mapa_obras.context_processors.obra_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'lplan_central.wsgi.application'

# Database
# Desenvolvimento: SQLite (padrão)
# Produção cPanel (MySQL): USE_MYSQL=True, DB_NAME=lplan_Sistema, DB_USER=lplan_gestaoap2, DB_PASSWORD=...
# Produção PostgreSQL: USE_POSTGRES=True, DB_NAME=..., DB_USER=..., DB_PASSWORD=...
USE_MYSQL = os.environ.get('USE_MYSQL', 'False').lower() in ('true', '1', 'yes')
USE_POSTGRES = os.environ.get('USE_POSTGRES', 'False').lower() in ('true', '1', 'yes')

if USE_MYSQL:
    # MySQL (cPanel – mesmo usuário do GestControll: lplan_gestaoap2, banco lplan_Sistema)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('DB_NAME', 'lplan_Sistema'),
            'USER': os.environ.get('DB_USER', 'lplan_gestaoap2'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES', default_storage_engine=INNODB",
            },
        }
    }
elif USE_POSTGRES:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'lplan_central'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }
else:
    # SQLite para desenvolvimento
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
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
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    # Permite acesso à raiz da API sem autenticação (apenas visualização)
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# Security Settings
# Note: In production, set DEBUG=False and configure these appropriately
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 1209600
SESSION_SAVE_EVERY_REQUEST = True
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# Remove X-XSS-Protection header (modern browsers handle this)
# Note: We'll handle CSP via custom middleware
SECURE_BROWSER_XSS_FILTER = False

# Cache Control for Static Files
if not DEBUG:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# Celery Configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutos
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutos

# Authentication Settings (tela de login correta = core em /login/)
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/select-system/'
LOGOUT_REDIRECT_URL = '/login/'

# E-mail (recuperação de senha): em desenvolvimento o link sai no console do servidor
# Em produção, configure SMTP (EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
# Remetente das mensagens enviadas pelo sistema (notificações, diários, etc.). Contato para dúvidas: suporte@lplan.com.br
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'sistema@lplan.com.br')
# URL base do sistema (para links em e-mails). Ex.: https://sistema.empresa.com
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:8000').rstrip('/')

# Logging: arquivo + console para quem for dar suporte conseguir diagnosticar sem o desenvolvedor
LOG_DIR = BASE_DIR / 'logs'
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'lplan.log',
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 3,
            'formatter': 'simple',
        },
        'file_errors': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'lplan_errors.log',
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console'],
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'file_errors'],
            'level': 'INFO',
            'propagate': False,
        },
        'core': {
            'handlers': ['file', 'file_errors', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'gestao_aprovacao': {
            'handlers': ['file', 'file_errors', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
# Garantir que o diretório de logs existe (evita erro ao subir o servidor)
if not LOG_DIR.exists():
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass  # em alguns ambientes read-only, logging em arquivo pode falhar
