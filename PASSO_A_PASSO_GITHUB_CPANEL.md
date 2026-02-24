# Passo a passo: GitHub + cPanel (Lplan_Sistema)

Use este guia na ordem. Cada passo depende do anterior.

---

## Passo 1 – Criar o repositório no GitHub

1. Acesse [github.com](https://github.com) e faça login.
2. Clique em **“+”** (canto superior direito) → **“New repository”**.
3. Preencha:
   - **Repository name:** `Lplan_Sistema` (ou o nome que preferir).
   - **Description:** opcional (ex.: "Sistema LPlan - Diário de Obra, Gestão, Mapa").
   - **Visibility:** Private ou Public.
   - **Não** marque “Add a README”, “Add .gitignore” nem “Choose a license” (o projeto já existe).
4. Clique em **“Create repository”**.
5. Na página do repositório, copie a URL:
   - **HTTPS:** `https://github.com/VictorPaes28/Lplan_Sistema.git`
   - Ou **SSH:** `git@github.com:VictorPaes28/Lplan_Sistema.git`  
   Guarde essa URL para o Passo 3.

---

## Passo 2 – Preparar a pasta no seu PC

Abra o **PowerShell** e vá até a pasta raiz do projeto (onde estão as pastas `Diario_obra`, `Gestao_aprovacao`, `Mapa_Controle`).

```powershell
cd "C:\Users\victo\OneDrive\Área de Trabalho\Lplan_Sistema"
```

### 2.1 Conferir o que não vai para o Git

Na raiz do projeto existe o arquivo **`.gitignore`**. Ele já evita que estes itens entrem no repositório:

- `.env` (senhas e chaves)
- `db.sqlite3`, `*.sqlite3`
- `venv/`, `.venv/`, `env/`
- `__pycache__/`, `staticfiles/`, `media/`, `logs/`

**Importante:** se você tiver um arquivo `.env` com senhas, **não** o adicione ao Git. Ele já está no `.gitignore`.

### 2.2 (Opcional) Limpar cache do Python antes do primeiro commit

```powershell
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path . -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force
```

---

## Passo 3 – Inicializar o Git e enviar para o GitHub

Ainda na pasta **Lplan_Sistema** (raiz):

```powershell
# Inicializar repositório
git init

# Ver o que será commitado (confira: .env e db.sqlite3 NÃO devem aparecer)
git status

# Adicionar tudo (respeitando .gitignore)
git add .

# Primeiro commit
git commit -m "Initial commit: Lplan_Sistema (Diario_obra, Gestao_aprovacao, Mapa_Controle)"

# Conectar ao repositório (URL do repositório Lplan_Sistema)
git remote add origin https://github.com/VictorPaes28/Lplan_Sistema.git

# Garantir branch main e enviar
git branch -M main
git push -u origin main
```

Se pedir usuário/senha do GitHub, use seu **usuário** e um **Personal Access Token** (não a senha da conta).  
Para criar um token: GitHub → Settings → Developer settings → Personal access tokens → Generate new token (marque pelo menos `repo`).

Se o repositório tiver sido criado **com** README no Passo 1:

```powershell
git pull origin main --allow-unrelated-histories
# Resolver conflitos se aparecerem, depois:
git push -u origin main
```

---

## Passo 4 – Conectar o cPanel ao GitHub

O cPanel costuma ter uma ferramenta **“Git Version Control”** ou **“Git™ Version Control”**.

### 4.1 Criar o repositório no cPanel

1. Entre no **cPanel** da sua hospedagem.
2. Procure por **“Git Version Control”** ou **“Git™”** e abra.
3. Clique em **“Create”** (ou “Clone”).
4. Preencha:
   - **Repository URL:** `https://github.com/VictorPaes28/Lplan_Sistema.git` (ou use a URL SSH se preferir).
   - **Repository Path:** pasta onde o projeto ficará no servidor (ex.: `lplan` ou `repositories/Lplan_Sistema`). Anote esse caminho.
5. Se pedir **usuário/senha do GitHub**, use seu usuário e o **Personal Access Token** (não a senha da conta).
6. Clique em **“Create”** (ou **“Clone”**). O cPanel vai clonar o repositório para o servidor.

### 4.2 Atualizar o código no servidor (depois do primeiro clone)

Sempre que você der **push** no GitHub e quiser atualizar o servidor:

- Na mesma tela **Git Version Control** do cPanel, localize o repositório e clique em **“Pull”** ou **“Update”**.

Assim o servidor fica com o mesmo código do GitHub, sem precisar editar arquivos à mão no cPanel.

---

## Passo 5 – Configurar a aplicação no cPanel (Diario_obra)

O cPanel pode ter **“Setup Python App”** ou **“Application Manager”** para apps Python/Django.

1. Crie uma **Python App** apontando para a pasta do projeto no servidor (a pasta onde está o `manage.py` do Diario_obra).  
   Exemplo: se o clone ficou em `~/lplan`, a aplicação deve apontar para `~/lplan/Diario_obra` (onde está o `manage.py`).
2. Defina a **versão do Python** (ex.: 3.11).
3. Em **“Configuration”** ou **“Environment variables”**, configure as variáveis como no **`.env`** (nunca coloque o `.env` no Git; no servidor você preenche manualmente ou usa o painel):
   - `SECRET_KEY` (gere uma chave nova para produção)
   - `DEBUG=False`
   - `ALLOWED_HOSTS=seudominio.com.br,www.seudominio.com.br`
   - Se usar PostgreSQL: `USE_POSTGRES=True`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
4. **Passenger/Startup file:** normalmente o cPanel espera um arquivo de entrada (ex.: `passenger_wsgi.py` ou `wsgi.py`). Se o Diario_obra não tiver, será preciso criar um `passenger_wsgi.py` na pasta `Diario_obra` apontando para o `application` do Django (wsgi).

### 5.1 Comandos uma vez no servidor (SSH ou terminal do cPanel)

Se tiver acesso por **SSH** ou **Terminal** no cPanel:

```bash
cd ~/caminho/para/Diario_obra   # ajuste ao seu caminho

# Ambiente virtual (se o cPanel não criar automaticamente)
python -m venv venv
source venv/bin/activate   # Linux/macOS

# Dependências
pip install -r requirements.txt

# Banco e estáticos
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser   # se ainda não tiver usuário admin
```

Se não tiver SSH, o cPanel pode permitir rodar esses comandos por uma interface “Run script” ou similar (depende da hospedagem).

---

## Resumo do fluxo depois de tudo configurado

| Onde        | O que fazer |
|------------|-------------|
| **No seu PC** | Alterar código → `git add .` → `git commit -m "..."` → `git push` |
| **No cPanel** | Git Version Control → **Pull** no repositório |
| **No servidor** (se tiver SSH) | Opcional: depois do pull, rodar `migrate` e `collectstatic` se tiver mudado modelo ou estáticos |

---

## Arquivos úteis no projeto

- **`.gitignore`** (raiz) – O que não vai para o Git.
- **`Diario_obra/.env.example`** – Exemplo de variáveis; no servidor copie para `.env` (ou preencha no painel) e nunca commite o `.env`.
- **`Diario_obra/DEPLOY.md`** – Detalhes de deploy e produção.
- **`GITHUB_E_DEPLOY.md`** – Visão geral de GitHub e deploy.

Se em algum passo aparecer uma mensagem de erro (Git, cPanel ou Python), copie a mensagem e o passo em que parou para conseguir ajuda direcionada.
