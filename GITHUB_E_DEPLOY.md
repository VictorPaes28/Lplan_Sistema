# Limpar, conectar ao GitHub e fazer deploy

## 1. Limpar o sistema (antes do primeiro commit)

No PowerShell, na pasta **Lplan_Sistema** (raiz do projeto):

```powershell
cd "C:\Users\victo\OneDrive\Área de Trabalho\Lplan_Sistema"

# Remover __pycache__ em todos os subprojetos
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

# Remover arquivos .pyc
Get-ChildItem -Path . -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force
```

**Verificar que não vão para o Git:**
- `.env` (segredos) – já está no `.gitignore`
- `db.sqlite3` – já está no `.gitignore`
- `venv/` ou `.venv/` – já está no `.gitignore`

Se tiver um `.env` com senhas/chaves, **não** adicione ao repositório. Use `.env.example` (sem valores reais) e documente as variáveis necessárias.

---

## 2. Conectar ao GitHub

### 2.1 Criar repositório no GitHub
1. Acesse [github.com](https://github.com) e faça login.
2. **New repository** → nome, por exemplo: `Lplan_Sistema`.
3. **Não** marque "Add a README" se for subir um projeto existente.
4. Copie a URL do repositório (ex.: `https://github.com/SEU_USUARIO/Lplan_Sistema.git`).

### 2.2 Inicializar Git e primeiro commit (na pasta Lplan_Sistema)

```powershell
cd "C:\Users\victo\OneDrive\Área de Trabalho\Lplan_Sistema"

# Inicializar repositório (se ainda não existir)
git init

# Ver o que será commitado (confira se .env e db não aparecem)
git status

# Adicionar tudo (respeitando .gitignore)
git add .

# Primeiro commit
git commit -m "Initial commit: Lplan_Sistema (Diario_obra, Mapa_Controle, Gestao_aprovacao)"

# Conectar ao repositório remoto (troque pela sua URL)
git remote add origin https://github.com/SEU_USUARIO/Lplan_Sistema.git

# Enviar (branch main)
git branch -M main
git push -u origin main
```

Se o repositório já tiver sido criado com README/licença no GitHub, pode ser necessário:

```powershell
git pull origin main --allow-unrelated-histories
# Resolver conflitos se houver, depois:
git push -u origin main
```

---

## 3. Depois: Deploy

O deploy depende de **onde** você vai hospedar:

| Onde | Observação |
|------|------------|
| **Railway / Render / Fly.io** | Conecte o repositório GitHub; configure variáveis de ambiente (.env); defina comando de start (ex.: `gunicorn` para Django). |
| **VPS (Linux)** | Clone o repo no servidor, crie venv, instale dependências, configure Nginx + Gunicorn (ou similar). |
| **Azure / AWS** | Use o serviço de App Service / Elastic Beanstalk e conecte ao GitHub para deploy contínuo. |

**Para Django (ex.: Diario_obra):**
- Defina `ALLOWED_HOSTS`, `SECRET_KEY`, `DEBUG=False` e variáveis de banco (PostgreSQL em produção é recomendado).
- Rode `collectstatic` e configure o servidor para servir arquivos estáticos.
- Use um banco gerenciado (ex.: PostgreSQL na nuvem) em produção; não use apenas SQLite em produção.

Quando decidir a plataforma (Railway, Render, VPS, etc.), dá para detalhar os passos específicos para ela.
