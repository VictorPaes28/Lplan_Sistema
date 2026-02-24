# 📘 Guia Completo de Integração - Sistema LPLAN Unificado

**Este é o guia único e completo para integrar os 3 sistemas Django em um único projeto central.**

---

## 📋 Índice

1. [Status Atual](#status-atual)
2. [Passo 1: Copiar Apps do Mapa_Controle](#passo-1-copiar-apps-do-mapa_controle)
3. [Passo 2: Atualizar apps.py do mapa_obras](#passo-2-atualizar-appspy-do-mapa_obras)
4. [Passo 3: Atualizar Referências do mapa_obras](#passo-3-atualizar-referências-do-mapa_obras)
5. [Passo 4: Configurar settings.py](#passo-4-configurar-settingspy)
6. [Passo 5: Configurar urls.py](#passo-5-configurar-urlspy)
7. [Passo 6: Unificar requirements.txt](#passo-6-unificar-requirementstxt)
8. [Passo 7: Executar Migrações](#passo-7-executar-migrações)
9. [Passo 8: Testar Sistema](#passo-8-testar-sistema)
10. [Checklist Final](#checklist-final)

---

## ✅ Status Atual

### O que já foi feito:
- ✅ Estrutura do projeto `lplan_central/` criada
- ✅ App `gestao_aprovacao` integrado e funcionando
- ✅ Todas as migrações de `gestao_aprovacao` atualizadas
- ✅ App `core` (Diario_obra) já está no sistema

### O que falta fazer:
- ⏳ Copiar apps do Mapa_Controle
- ⏳ Atualizar referências do mapa_obras
- ⏳ Configurar settings.py e urls.py
- ⏳ Unificar requirements.txt
- ⏳ Testar tudo

---

## Passo 1: Copiar Apps do Mapa_Controle

### 1.1. Copiar mapa_obras

**De:** `Mapa_Controle\obras\`  
**Para:** `Diario_obra\mapa_obras\`

**Como fazer:**
1. Abra o Windows Explorer
2. Navegue até: `Lplan_Sistema\Mapa_Controle\obras\`
3. Selecione TODA a pasta `obras` (Ctrl+A)
4. Copie (Ctrl+C)
5. Navegue até: `Lplan_Sistema\Diario_obra\`
6. Cole (Ctrl+V)
7. **IMPORTANTE:** Renomeie a pasta de `obras` para `mapa_obras`

### 1.2. Copiar accounts

**De:** `Mapa_Controle\accounts\`  
**Para:** `Diario_obra\accounts\`

**Como fazer:**
1. Navegue até: `Lplan_Sistema\Mapa_Controle\accounts\`
2. Selecione TODA a pasta `accounts`
3. Copie (Ctrl+C)
4. Navegue até: `Lplan_Sistema\Diario_obra\`
5. Cole (Ctrl+V)
6. A pasta já está com o nome correto

### 1.3. Copiar suprimentos

**De:** `Mapa_Controle\suprimentos\`  
**Para:** `Diario_obra\suprimentos\`

**Como fazer:**
1. Navegue até: `Lplan_Sistema\Mapa_Controle\suprimentos\`
2. Selecione TODA a pasta `suprimentos`
3. Copie (Ctrl+C)
4. Navegue até: `Lplan_Sistema\Diario_obra\`
5. Cole (Ctrl+V)
6. A pasta já está com o nome correto

---

## Passo 2: Atualizar apps.py do mapa_obras

**Arquivo:** `Diario_obra\mapa_obras\apps.py`

**O que fazer:**
1. Abra o arquivo no editor
2. Procure pela linha: `name = 'obras'`
3. Mude para: `name = 'mapa_obras'`

**Antes:**
```python
name = 'obras'
```

**Depois:**
```python
name = 'mapa_obras'
```

---

## Passo 3: Atualizar Referências do mapa_obras

Você precisa atualizar todas as referências de `obras` para `mapa_obras` nos arquivos do app.

### 3.1. Usando Busca e Substituição (Recomendado)

**No VS Code/Cursor:**
1. Abra a pasta `mapa_obras` no editor
2. Use Ctrl+Shift+H (Buscar e Substituir)
3. **Busque:** `from obras.`
4. **Substitua por:** `from mapa_obras.`
5. Clique em "Substituir Tudo"
6. Repita para:
   - `import obras` → `import mapa_obras`
   - `'obras'` → `'mapa_obras'` (em strings, mas cuidado com migrações)

### 3.2. Arquivos que precisam ser atualizados

Verifique estes arquivos:
- `views.py`
- `models.py`
- `context_processors.py`
- `urls.py`
- `admin.py` (se existir)
- Arquivos em `management/commands/` (se existir)

### 3.3. Migrações

**IMPORTANTE:** Nas migrações, você precisa atualizar:
- `('obras',` → `('mapa_obras',` (dependências)
- `to='obras.` → `to='mapa_obras.` (referências a modelos)

**Como fazer:**
1. Abra cada arquivo em `mapa_obras\migrations\`
2. Use busca e substituição para:
   - `('obras',` → `('mapa_obras',`
   - `to='obras.` → `to='mapa_obras.`

---

## Passo 4: Configurar settings.py

**Arquivo:** `Diario_obra\lplan_central\settings.py`

### 4.1. Adicionar apps no INSTALLED_APPS

Procure pela seção `INSTALLED_APPS` (linha ~19) e descomente (remova o `#`) estas linhas:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'rest_framework',
    'django_filters',
    'treebeard',
    # LPLAN Apps
    'core',  # Diario_obra
    'gestao_aprovacao',  # ← Remover o # desta linha
    'mapa_obras',  # ← Remover o # desta linha
    'accounts',  # ← Remover o # desta linha
    'suprimentos',  # ← Remover o # desta linha
]
```

### 4.2. Adicionar context processors

Procure pela seção `context_processors` (linha ~59) e descomente estas linhas:

```python
'context_processors': [
    'django.template.context_processors.debug',
    'django.template.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
    'core.context_processors.sidebar_counters',
    'gestao_aprovacao.context_processors.notificacoes_count',  # ← Remover o #
    'gestao_aprovacao.context_processors.user_context',  # ← Remover o #
    'mapa_obras.context_processors.obra_context',  # ← Remover o #
],
```

---

## Passo 5: Configurar urls.py

**Arquivo:** `Diario_obra\lplan_central\urls.py`

Descomente (remova o `#`) estas linhas:

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    # Diario_obra
    path('diario/', include('core.urls')),
    path('api/diario/', include('core.api_urls')),
    # Gestao_aprovacao
    path('gestao/', include('gestao_aprovacao.urls')),  # ← Remover o #
    # Mapa_Controle
    path('mapa/', include('mapa_obras.urls')),  # ← Remover o #
    path('accounts/', include('accounts.urls')),  # ← Remover o #
    path('engenharia/', include('suprimentos.urls_engenharia')),  # ← Remover o #
    path('api/internal/', include('suprimentos.urls_api')),  # ← Remover o #
    path('api/webhook/sienge/', include('suprimentos.urls_webhook')),  # ← Remover o #
    # Redirecionar raiz para diario (temporário)
    path('', include('core.urls')),
]
```

---

## Passo 6: Unificar requirements.txt

**Arquivo:** `Diario_obra\requirements.txt`

Você precisa combinar as dependências dos 3 sistemas. Abra os arquivos:
- `Diario_obra\requirements.txt`
- `Gestao_aprovacao\requirements.txt`
- `Mapa_Controle\requirements.txt`

E combine tudo em um único arquivo, removendo duplicatas.

### Dependências que devem estar presentes:

```txt
# Core Django
Django>=5.0,<6.0
djangorestframework>=3.15.0

# Database
psycopg2-binary>=2.9.0
mysqlclient>=2.2.0,<3.0.0  # Se usar MySQL
pymysql>=1.1.0,<2.0.0  # Se usar MySQL no cPanel

# Tree structure (EAP)
django-treebeard>=4.7

# PDF Generation
WeasyPrint>=60.0
xhtml2pdf>=0.2.11
reportlab>=4.0.0

# Image processing
Pillow>=10.0.0

# Task queue (Celery)
celery>=5.3.0
redis>=5.0.0

# Utilities
python-dateutil>=2.8.2
django-filter>=24.0
python-dotenv>=1.0.0

# Excel export
openpyxl>=3.1.0
pandas>=2.0.0,<3.0.0

# HTTP Requests
requests>=2.31.0,<3.0.0

# Static files
whitenoise>=6.6.0,<7.0.0

# Database URL
dj-database-url>=2.1.0,<3.0.0
```

**Dica:** Copie o conteúdo de cada arquivo e combine, removendo versões duplicadas (mantenha a versão mais recente).

---

## Passo 7: Executar Migrações

Abra o terminal/PowerShell no diretório `Diario_obra` e execute:

```powershell
cd "C:\Users\victo\OneDrive\Área de Trabalho\Lplan_Sistema\Diario_obra"
python manage.py makemigrations
python manage.py migrate
```

**O que isso faz:**
- `makemigrations`: Cria arquivos de migração para os novos apps
- `migrate`: Aplica as migrações no banco de dados

**Se houver erros:**
- Verifique se todos os apps estão no `INSTALLED_APPS`
- Verifique se as referências foram atualizadas corretamente
- Verifique se as migrações têm as dependências corretas

---

## Passo 8: Testar Sistema

### 8.1. Iniciar servidor

```powershell
python manage.py runserver
```

### 8.2. Testar URLs

Abra o navegador e teste:

- `http://localhost:8000/diario/` - Diario_obra ✅
- `http://localhost:8000/gestao/` - Gestao_aprovacao ✅
- `http://localhost:8000/mapa/` - Mapa_Controle ✅
- `http://localhost:8000/admin/` - Admin Django ✅

### 8.3. Verificar erros

- Verifique o terminal para erros
- Verifique o console do navegador (F12)
- Teste funcionalidades básicas de cada módulo

---

## Checklist Final

Use este checklist para garantir que tudo foi feito:

### Estrutura
- [ ] Pasta `mapa_obras` copiada e renomeada
- [ ] Pasta `accounts` copiada
- [ ] Pasta `suprimentos` copiada

### Configuração
- [ ] `mapa_obras/apps.py` atualizado (`name = 'mapa_obras'`)
- [ ] Referências `obras` → `mapa_obras` atualizadas
- [ ] Migrações do `mapa_obras` atualizadas
- [ ] `settings.py` atualizado (apps e context processors)
- [ ] `urls.py` atualizado (todas as rotas)

### Dependências
- [ ] `requirements.txt` unificado
- [ ] Dependências instaladas: `pip install -r requirements.txt`

### Migrações
- [ ] `python manage.py makemigrations` executado sem erros
- [ ] `python manage.py migrate` executado sem erros

### Testes
- [ ] Servidor inicia sem erros
- [ ] `/diario/` funciona
- [ ] `/gestao/` funciona
- [ ] `/mapa/` funciona
- [ ] `/admin/` funciona

---

## ⚠️ Problemas Comuns e Soluções

### Erro: "No module named 'obras'"
**Solução:** Verifique se atualizou todas as referências `obras` → `gestao_aprovacao` ou `mapa_obras`

### Erro: "App 'gestao_aprovacao' not found"
**Solução:** Verifique se o app está no `INSTALLED_APPS` do `settings.py`

### Erro nas migrações
**Solução:** Verifique se as dependências das migrações estão corretas (ex: `('gestao_aprovacao', '0001_initial')`)

### Erro 404 nas URLs
**Solução:** Verifique se as rotas estão descomentadas no `urls.py`

---

## 📝 Notas Finais

- Mantenha os sistemas originais (`Gestao_aprovacao`, `Mapa_Controle`) intactos até confirmar que tudo funciona
- Faça backup do banco de dados antes de executar migrações
- Teste em ambiente de desenvolvimento primeiro
- Se algo der errado, você pode voltar aos sistemas originais

---

## 🎉 Quando Terminar

Após completar todos os passos e testar, você terá:
- ✅ Sistema unificado funcionando
- ✅ Todos os 3 sistemas integrados
- ✅ URLs organizadas com prefixos claros
- ✅ Banco de dados unificado

**Boa sorte! 🚀**
