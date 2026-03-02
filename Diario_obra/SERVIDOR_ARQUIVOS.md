# Arquivos relacionados ao servidor – LPLAN Central

Resumo: onde está cada coisa e o que cada arquivo faz.

---

## 1. Lista de arquivos (caminhos)

| Arquivo | Função |
|---------|--------|
| `Diario_obra/manage.py` | Ponto de entrada: `python manage.py runserver` / `runserver_plus` |
| `Diario_obra/lplan_central/settings.py` | Configuração do Django (DEBUG, ALLOWED_HOSTS, DB, HTTPS, etc.) |
| `Diario_obra/lplan_central/urls.py` | Roteamento principal: /, /gestao/, /mapa/, /accounts/, /admin/, etc. |
| `Diario_obra/lplan_central/wsgi.py` | Aplicação WSGI usada em produção (ex.: cPanel/gunicorn) |
| `Diario_obra/core/middleware.py` | Middleware de segurança (CSP, cache, headers) |
| `Diario_obra/run_https.bat` | Sobe o servidor em **HTTPS** (dentro de Diario_obra) |
| `run_https.bat` (raiz Lplan_Sistema) | Mesmo que o anterior, mas pode ser rodado da raiz do projeto |
| `Diario_obra/scripts/generate_dev_cert.py` | Gera certificado SSL para localhost (usado pelo run_https.bat) |
| `Diario_obra/requirements.txt` | Dependências (Django, django-extensions, Werkzeug, pyOpenSSL, etc.) |
| `Diario_obra/.env` (não versionado) | Variáveis de ambiente (SECRET_KEY, DEBUG, DB_*, etc.) – ver .env.example |
| `Diario_obra/.env.example` | Exemplo do que colocar no .env |

---

## 2. Conteúdo dos arquivos

### 2.1 `Diario_obra/manage.py`

```python
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

# cPanel: limita threads do OpenBLAS/numpy (evita pthread_create failed em hospedagem compartilhada)
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'

# INÍCIO DO AJUSTE cPanel – PyMySQL como substituto de mysqlclient (não remover)
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass
# FIM DO AJUSTE cPanel


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lplan_central.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
```

- Define `DJANGO_SETTINGS_MODULE = 'lplan_central.settings'`.
- Ajustes para cPanel (OpenBLAS, PyMySQL).
- Comandos como `runserver` e `runserver_plus` são do Django/django-extensions, chamados via `manage.py`.

---

### 2.2 `Diario_obra/lplan_central/wsgi.py`

```python
"""
WSGI config for Sistema LPLAN Central project.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lplan_central.settings')

application = get_wsgi_application()
```

- Usado em produção (ex.: cPanel, gunicorn) para servir a aplicação.
- Não define porta nem HTTP/HTTPS; isso é feito pelo servidor (Apache/Nginx) ou pelo comando que sobe o app.

---

### 2.3 `Diario_obra/lplan_central/urls.py`

```python
"""
URL configuration for Sistema LPLAN Central - Unificado.

Estrutura de URLs:
  /               -> Core (Diário de Obra) - app principal
  /gestao/        -> Gestão de Aprovação (namespace: gestao)
  /mapa/          -> Mapa de Suprimentos (namespace: mapa_obras)
  /accounts/      -> Autenticação e Admin Central (namespace: accounts)
  /engenharia/    -> Suprimentos/Engenharia (namespace: engenharia)
  /api/           -> APIs internas
  /admin/         -> Django Admin
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),

    # === Core (Diário de Obra) - app principal no root ===
    path('', include('core.urls')),
    path('api/diario/', include('core.api_urls')),

    # === Gestão de Aprovação ===
    path('gestao/', include('gestao_aprovacao.urls')),

    # === Mapa de Suprimentos ===
    path('mapa/', include('mapa_obras.urls')),

    # === Autenticação e Admin Central ===
    path('accounts/', include('accounts.urls')),

    # === Suprimentos / Engenharia ===
    path('engenharia/', include('suprimentos.urls_engenharia')),
    path('api/internal/', include('suprimentos.urls_api')),
    path('api/webhook/sienge/', include('suprimentos.urls_webhook')),

    # Redirect legado: /diario/xxx -> /xxx
    path('diario/', RedirectView.as_view(url='/', permanent=True)),
]

# Em DEBUG: servir /static/ e /media/ ANTES do path('', include('core.urls'))
# senão o core engole /static/... e devolve 404 (CSS e imagens não carregam)
if settings.DEBUG:
    urlpatterns = static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + urlpatterns
    urlpatterns = static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + urlpatterns
```

- Roteamento principal do servidor web (qual URL chama qual app).
- Em DEBUG, o próprio Django serve arquivos estáticos e de mídia.

---

### 2.4 `Diario_obra/core/middleware.py`

```python
"""
Custom middleware for security headers and cache control.
"""
from django.utils.deprecation import MiddlewareMixin


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers and cache control.
    Replaces X-Frame-Options with Content-Security-Policy.
    """
    
    def process_response(self, request, response):
        # Não alterar respostas de arquivos estáticos/media (evita interferência no carregamento)
        if request.path.startswith(('/static/', '/media/')):
            return response
        # Remove X-XSS-Protection header (not needed in modern browsers)
        if 'X-XSS-Protection' in response:
            del response['X-XSS-Protection']
        
        # Add Content-Security-Policy header (replaces X-Frame-Options)
        if 'Content-Security-Policy' not in response:
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://unpkg.com; "
                "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://fonts.googleapis.com; "
                "connect-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
                "img-src 'self' data: blob: https:; "
                "media-src 'self' blob: data: https:; "
                "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
                "frame-ancestors 'self';"
            )
            response['Content-Security-Policy'] = csp
        
        # Add cache-control headers for static files
        if request.path.startswith('/static/'):
            response['Cache-Control'] = 'public, max-age=31536000, immutable'
        elif request.path.startswith('/media/'):
            response['Cache-Control'] = 'public, max-age=86400'
        elif not request.path.startswith('/admin/') and response.get('Content-Type', '').startswith('text/html'):
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response
```

- Roda em toda resposta HTTP do servidor (exceto /static/ e /media/).
- Adiciona CSP e headers de cache; não define porta nem protocolo (HTTP/HTTPS).

---

### 2.5 `Diario_obra/lplan_central/settings.py`

(Resumo do que impacta o “servidor” – onde sobe, como sobe, segurança.)

- **BASE_DIR**: pasta do projeto (onde está `manage.py`).
- **.env**: carregado de `BASE_DIR/.env` (python-dotenv).
- **SECRET_KEY, DEBUG, ALLOWED_HOSTS**: lidos do ambiente; com DEBUG=True, ALLOWED_HOSTS vira `['*']` em dev.
- **INSTALLED_APPS**: inclui `django_extensions` (para `runserver_plus`).
- **ROOT_URLCONF**: `'lplan_central.urls'`.
- **WSGI_APPLICATION**: `'lplan_central.wsgi.application'`.
- **DATABASES**: SQLite por padrão; MySQL/Postgres se USE_MYSQL/USE_POSTGRES no .env.
- **Segurança HTTPS**:  
  `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` só ativos quando `DEBUG=False` e `SECURE_COOKIES_AND_REDIRECT=True` no .env (produção). Em dev (DEBUG=True) o servidor pode rodar em HTTP sem redirecionar.
- **STATIC_*, MEDIA_***: pastas e URLs de arquivos estáticos e uploads.
- **LOGIN_URL, LOGIN_REDIRECT_URL, LOGOUT_REDIRECT_URL**: rotas de login (usadas pelo servidor ao servir as páginas).
- **Celery, e-mail, Sienge, CSRF_TRUSTED_ORIGINS, LOGGING**: configuração de backend; não definem porta nem protocolo do servidor web.

O arquivo completo tem ~330 linhas; o trecho acima é o que está diretamente ligado ao “servidor” (comportamento de rede, segurança, onde o Django escuta).

---

### 2.6 `Diario_obra/run_https.bat`

Sobe o servidor em **HTTPS** a partir da pasta `Diario_obra`:

- Entra na pasta do script (`cd /d "%~dp0"`).
- Cria `certs` e, se não existir certificado, tenta OpenSSL (incluindo Git) ou `scripts\generate_dev_cert.py`.
- Roda:  
  `python manage.py runserver_plus 0.0.0.0:8000 --cert-file certs/cert.pem --key-file certs/key.pem`  
  Ou seja: servidor HTTPS na porta 8000, escutando em todas as interfaces.

Conteúdo atual:

```batch
@echo off
cd /d "%~dp0"
title LPLAN - Servidor HTTPS (dev)
if not exist "certs" mkdir certs
if not exist "certs\cert.pem" (
  echo Gerando certificado SSL para localhost...
  set "PATH=%PATH%;C:\Program Files\Git\usr\bin"
  where openssl >nul 2>&1
  if not errorlevel 1 (
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout certs/key.pem -out certs/cert.pem -subj "/CN=localhost"
  ) else (
    python "%~dp0scripts\generate_dev_cert.py"
    ...
  )
  ...
)
...
python manage.py runserver_plus 0.0.0.0:8000 --cert-file certs/cert.pem --key-file certs/key.pem
pause
```

---

### 2.7 `run_https.bat` (raiz: Lplan_Sistema)

Faz a mesma coisa que o `Diario_obra/run_https.bat`, mas:

- Faz `cd /d "%~dp0Diario_obra"` para entrar em `Diario_obra`.
- Chama o script de certificado em `%~dp0Diario_obra\scripts\generate_dev_cert.py`.
- Depois roda o mesmo `manage.py runserver_plus ...` dentro de `Diario_obra`.

Assim você pode executar `.\run_https.bat` na raiz do repositório e o servidor HTTPS sobe na porta 8000.

---

### 2.8 `Diario_obra/scripts/generate_dev_cert.py`

- Gera certificado SSL autoassinado para `localhost` e `127.0.0.1`.
- Grava em `Diario_obra/certs/cert.pem` e `key.pem`.
- Usa a biblioteca `cryptography`; não depende de OpenSSL instalado no sistema.
- É chamado pelos dois `run_https.bat` quando ainda não existe certificado.

---

### 2.9 Dependências de servidor em `Diario_obra/requirements.txt`

Trecho relevante:

```text
# Dev: servidor com HTTPS (evita navegador forçar HTTPS e dar ERR_SSL_PROTOCOL_ERROR)
django-extensions>=3.2.0
Werkzeug>=3.0.0
pyOpenSSL>=24.0.0
cryptography>=42.0.0
```

- **Django** (em outro trecho): servidor de desenvolvimento e aplicação.
- **django-extensions**: fornece o comando `runserver_plus` (suporte a HTTPS no dev).
- **Werkzeug**: usado pelo `runserver_plus` para servir com SSL.
- **pyOpenSSL**: exigido pelo `runserver_plus` para suporte SSL.
- **cryptography**: usado por `generate_dev_cert.py` para gerar o certificado.

---

## 3. Como o servidor sobe na prática

- **Só HTTP (jeito “clássico”):**  
  `cd Diario_obra` → `python manage.py runserver`  
  Sobe em **http://127.0.0.1:8000**. Não usa certificado nem `run_https.bat`.

- **HTTP em outro host/porta:**  
  `python manage.py runserver 0.0.0.0:8080`  
  Escuta em todas as interfaces na porta 8080, ainda HTTP.

- **HTTPS (dev):**  
  `.\run_https.bat` (na raiz) ou `.\run_https.bat` dentro de `Diario_obra`.  
  Usa `runserver_plus`, certificado em `certs/` e sobe em **https://127.0.0.1:8000**.

- **Produção:**  
  O servidor “de verdade” é o Apache/Nginx (ou outro) no cPanel; ele chama a aplicação via WSGI (`lplan_central.wsgi.application`). Porta e HTTP/HTTPS são configurados no painel/servidor, não no Django.

---

## 4. Resumo rápido por arquivo

| Arquivo | O que você precisa saber |
|---------|---------------------------|
| `manage.py` | Comando para subir servidor: `python manage.py runserver` ou `runserver_plus`. |
| `lplan_central/settings.py` | DEBUG, ALLOWED_HOSTS, segurança HTTPS, DB, estáticos; lê .env. |
| `lplan_central/urls.py` | Define todas as URLs do site (/, /gestao/, /mapa/, etc.). |
| `lplan_central/wsgi.py` | Entrada da aplicação em produção (não sobe porta nem HTTP/HTTPS). |
| `core/middleware.py` | Headers de segurança e cache em cada resposta. |
| `Diario_obra/run_https.bat` | Sobe HTTPS na porta 8000 a partir da pasta Diario_obra. |
| `run_https.bat` (raiz) | Igual ao anterior, mas pode ser executado na raiz do projeto. |
| `scripts/generate_dev_cert.py` | Cria cert/key em `certs/` para HTTPS em dev. |
| `requirements.txt` | Django + django-extensions + Werkzeug + pyOpenSSL + cryptography para o servidor de desenvolvimento. |
| `.env` / `.env.example` | Variáveis que o `settings.py` usa (incluindo as que afetam servidor e HTTPS em produção). |

Se quiser, na próxima pergunta você pode dizer qual desses arquivos quer alterar (por exemplo só HTTP, só HTTPS, ou produção) que eu te digo exatamente o que mudar em cada um.
