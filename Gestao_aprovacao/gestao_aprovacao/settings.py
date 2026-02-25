"""
Django settings for gestao_aprovacao project.

CORRIGIDO: Sintaxe de listas, Middlewares e Banco de Dados.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables from .env file (UTF-8; se salvar no Notepad use "UTF-8")
try:
    load_dotenv(encoding='utf-8')
except (UnicodeDecodeError, TypeError):
    try:
        load_dotenv(encoding='utf-16')  # fallback Windows
    except Exception:
        load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Detectar se está em desenvolvimento local
# IMPORTANTE: Por padrão usa MySQL (produção). 
# Para usar SQLite localmente, crie um .env com: USE_LOCAL_DB=True
USE_LOCAL_DB = os.getenv('USE_LOCAL_DB', 'False').lower() == 'true'

# Se estiver usando MySQL (padrão/produção), importar pymysql
if not USE_LOCAL_DB:
    import pymysql
    # 1. Monkey Patch OBRIGATÓRIO para cPanel sem mysqlclient nativo
    pymysql.install_as_MySQLdb()


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-this-in-production-!@#$%^&*()')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')

# ALLOWED_HOSTS: em produção defina no .env (ex: ALLOWED_HOSTS=gestao.lplan.com.br,www.gestao.lplan.com.br)
_hosts = os.getenv('ALLOWED_HOSTS', '').strip()
ALLOWED_HOSTS = [h.strip() for h in _hosts.split(',') if h.strip()] if _hosts else [
    'gestao.lplan.com.br',
    'www.gestao.lplan.com.br',
    'lplan.com.br',
    'localhost',
    '127.0.0.1',
]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'obras',  # App principal
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Recomendado para servir estáticos
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gestao_aprovacao.urls'

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
                # Certifique-se que esses processadores existem no app 'obras'
                'obras.context_processors.notificacoes_count', 
                'obras.context_processors.user_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'gestao_aprovacao.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

# Database configuration
# Para desenvolvimento local: USE_LOCAL_DB=True (usa SQLite)
# Para produção: USE_LOCAL_DB=False (usa MySQL)

if USE_LOCAL_DB:
    # SQLite para desenvolvimento local - não precisa de servidor MySQL
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    # MySQL para produção
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('DB_NAME', 'lplan_gestaoap'),
            'USER': os.getenv('DB_USER', 'lplan_gestaoap2'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', '127.0.0.1'),
            'PORT': os.getenv('DB_PORT', '3306'),
            'OPTIONS': {
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"
            }
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (uploads)

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication settings
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

# Email settings
# Remetente das mensagens enviadas pelo sistema (notificações, pedidos, etc.). Contato para dúvidas: suporte@lplan.com.br
# Configuração para servidor LPLAN (mail.lplan.com.br)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'mail.lplan.com.br')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '465'))
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'True').lower() == 'true'  # Porta 465 usa SSL
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False').lower() == 'true'  # Porta 587 usa TLS
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'sistema@lplan.com.br')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)

# URL do site (usado nos links dos emails)
SITE_URL = os.getenv('SITE_URL', 'https://gestao.lplan.com.br')

# Emails de departamentos para notificações de aprovação
# Lista separada por vírgula (ex: "email1@lplan.com.br,email2@lplan.com.br")
# Padrão: luiz.henrique@lplan.com.br e luizdomingos@lplan.com.br
EMAIL_DEPARTAMENTOS_APROVACAO_DEFAULT = 'luiz.henrique@lplan.com.br,luizdomingos@lplan.com.br'
EMAIL_DEPARTAMENTOS_APROVACAO = os.getenv('EMAIL_DEPARTAMENTOS_APROVACAO', EMAIL_DEPARTAMENTOS_APROVACAO_DEFAULT).split(',')
# Remove espaços e emails vazios
EMAIL_DEPARTAMENTOS_APROVACAO = [email.strip() for email in EMAIL_DEPARTAMENTOS_APROVACAO if email.strip()]

# CSRF and Session settings

CSRF_TRUSTED_ORIGINS = [
    'https://gestao.lplan.com.br',
    'https://www.gestao.lplan.com.br',
]

CSRF_COOKIE_SECURE = False

SESSION_COOKIE_SECURE = False

SESSION_COOKIE_HTTPONLY = True

SESSION_SAVE_EVERY_REQUEST = True

# Sessão persiste ao fechar o navegador (não exige login novamente)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Sessão expira após 2 semanas de inatividade (renovada a cada requisição)
SESSION_COOKIE_AGE = 1209600  # 2 semanas = 1209600 segundos

