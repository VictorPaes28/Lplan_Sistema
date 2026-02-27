# Unificação LPLAN – Monolito e instruções de deploy

Este documento descreve a unificação dos três sistemas (Diário de Obra, Gestão de Aprovação, Mapa de Controle) em um único monolito Django e o que **não pode ser revertido** em produção (cPanel).

**Regras detalhadas de deploy (cPanel/MariaDB):** ver **[REGRAS_DEPLOY_CPANEL.md](REGRAS_DEPLOY_CPANEL.md)** — contém os erros que já ocorreram e como não repeti-los.

---

## 1. Estrutura unificada (único ponto de entrada)

| O que | Onde |
|-------|------|
| **Projeto Django** | `Diario_obra/` |
| **Settings** | `Diario_obra/lplan_central/settings.py` (único ativo) |
| **URLs** | `Diario_obra/lplan_central/urls.py` |
| **manage.py** | `Diario_obra/manage.py` |
| **WSGI (Django)** | `Diario_obra/lplan_central/wsgi.py` |
| **Passenger (raiz do app no cPanel)** | `passenger_wsgi.py` na raiz do repositório (= `sistema_lplan` no servidor) |

**Apps instalados em `lplan_central/settings.py`:**  
`core`, `gestao_aprovacao`, `mapa_obras`, `accounts`, `suprimentos`.

**Rotas principais:**

- `/` → Core (Diário de Obra)
- `/gestao/` → Gestão de Aprovação
- `/mapa/` → Mapa de Suprimentos
- `/accounts/` → Autenticação / admin central
- `/engenharia/` e `/api/` → Suprimentos e APIs

---

## 2. O que NÃO pode ser revertido (produção cPanel)

O servidor usa **Python 3.11** e tem restrições de compilação (sem `Python.h`, sem meson). As soluções abaixo são obrigatórias.

### 2.1 Driver MySQL: PyMySQL

- **Problema:** `mysqlclient` não compila no cPanel.
- **Solução:** uso de **pymysql** com `pymysql.install_as_MySQLdb()`.
- **Onde está:**
  - `passenger_wsgi.py` (raiz): antes de importar o Django.
  - `Diario_obra/manage.py`: no topo, em `try/except`, para comandos via terminal.
- **Não remover** esses blocos; sem eles o deploy quebra.

### 2.2 WeasyPrint

- **Versão fixada no cPanel:** `WeasyPrint>=52.5,<53` (em `requirements-cpanel.txt`).
- Versões mais novas usam meson e falham no servidor.
- **Não subir** WeasyPrint para >= 60 no ambiente cPanel.

### 2.3 Passenger WSGI (raiz)

- **Arquivo:** `passenger_wsgi.py` na raiz de `sistema_lplan` (ao lado de `Diario_obra`).
- **Faz:**
  1. Coloca `Diario_obra` no `sys.path`.
  2. Chama `pymysql.install_as_MySQLdb()`.
  3. Importa `application` de `lplan_central.wsgi`.
- **Não trocar** por um stub que use apenas `imp.load_source('wsgi', 'wsgi.py')` sem o path e sem o PyMySQL; o que está no repositório é o correto para produção.

### 2.4 Variáveis de ambiente

- **Fonte da verdade:** arquivo `.env` em `Diario_obra/` (no servidor: dentro de `sistema_lplan/Diario_obra/`).
- `lplan_central/settings.py` usa `python-dotenv` e lê:
  - `ALLOWED_HOSTS`, `SECRET_KEY`, `DEBUG`
  - `USE_MYSQL`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
  - `EMAIL_*`, `SITE_URL`, `CSRF_TRUSTED_ORIGINS`
  - `EMAIL_DEPARTAMENTOS_APROVACAO` (Gestão de Aprovação)
  - `SIENGE_API_BASE_URL`, `SIENGE_API_CLIENT_ID`, `SIENGE_API_CLIENT_SECRET`, `SIENGE_WEBHOOK_SECRET` (Mapa/Suprimentos)

---

## 3. Erros que já ocorreram – não repetir

Durante o deploy no cPanel/MariaDB estes problemas apareceram e foram corrigidos. **Em refatorações futuras, não reverter nem remover as soluções abaixo.**

| Erro | Causa | Solução (não remover) |
|------|--------|------------------------|
| **DisallowedHost / SQLite em produção** | `.env` não era lido (try/except engolia o erro) | Em `settings.py`: `load_dotenv(env_path)` no topo, **sem** try/except em volta; `python-dotenv` nos requirements. |
| **OpenBLAS pthread_create failed** | Pandas/Numpy abriam muitas threads; cPanel bloqueou | No **início** de `manage.py` e `passenger_wsgi.py`: `os.environ['OPENBLAS_NUM_THREADS']='1'` e `os.environ['OMP_NUM_THREADS']='1'` **antes** de qualquer import. |
| **MySQL 1064 na migração 0004** | SQL procedural (SET, PREPARE, EXECUTE) em um único `cursor.execute()` | Em migrações: só SQL atômico; lógica condicional em **Python** com try/except, nunca SQL procedural no MariaDB. |
| **Migrações gestao_aprovacao vs banco** | Histórico de migrações dessincronizado do banco real | Não criar migrações para “consertar” o passado; só novas migrações para mudanças **futuras** nos models. |

Detalhes e trechos de código: **[REGRAS_DEPLOY_CPANEL.md](REGRAS_DEPLOY_CPANEL.md)**.

---

## 4. Arquivos redundantes (outros sistemas)

Estes arquivos pertencem aos projetos **standalone** Gestão de Aprovação e Mapa de Controle. No monolito eles **não são usados**; podem ficar no repositório como referência ou ser removidos depois.

| Arquivo / Pasta | Observação |
|-----------------|------------|
| `Gestao_aprovacao/manage.py` | Redundante; o ativo é `Diario_obra/manage.py`. |
| `Gestao_aprovacao/gestao_aprovacao/urls.py`, `settings.py`, `wsgi.py` | Redundantes; uso é `lplan_central` em `Diario_obra`. |
| `Mapa_Controle/manage.py` | Redundante. |
| `Mapa_Controle/supplymap/urls.py`, `settings.py`, `wsgi.py` | Redundantes. |
| `Diario_obra/diario_obra/` (se existir) | Projeto antigo; o ativo é `lplan_central`. |

**Recomendação:** não apagar nada no servidor por enquanto. Se quiser limpar no repositório, faça em um branch, teste localmente e só então remova (por exemplo, `Gestao_aprovacao/`, `Mapa_Controle/` ou só os arquivos listados). O deploy atual usa apenas `sistema_lplan` (raiz) + `Diario_obra/` + `passenger_wsgi.py`.

---

## 5. Como aplicar as mudanças no servidor (sem quebrar)

1. **Backup (recomendado)**  
   - Copiar `passenger_wsgi.py` e `Diario_obra/.env` do servidor (ex.: para sua máquina).

2. **Atualizar código**  
   ```bash
   cd /home/lplan/sistema_lplan
   git pull
   ```

3. **Conferir `.env`**  
   - Garantir que `Diario_obra/.env` existe e tem pelo menos:  
     `ALLOWED_HOSTS`, `USE_MYSQL=True`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `SECRET_KEY`, `DEBUG`.

4. **Dependências (só se tiver mudado `requirements-cpanel.txt`)**  
   ```bash
   source /home/lplan/virtualenv/sistema_lplan/3.11/bin/activate
   cd /home/lplan/sistema_lplan/Diario_obra
   pip install -r requirements-cpanel.txt
   ```

5. **Migrações**  
   ```bash
   python manage.py migrate --noinput
   ```

6. **Arquivos estáticos**  
   ```bash
   python manage.py collectstatic --noinput
   ```

7. **Reiniciar o app**  
   ```bash
   cd /home/lplan/sistema_lplan
   mkdir -p tmp
   touch tmp/restart.txt
   ```  
   E no painel do cPanel (Setup Python App) clicar em **Restart**.

8. **Testar**  
   Abrir `https://sistema.lplan.com.br` e conferir login, Diário de Obra, Gestão (em `/gestao/`) e Mapa (em `/mapa/`).

---

## 6. Resumo do que foi feito no repositório

- **`lplan_central/settings.py`:** inclusão de `EMAIL_DEPARTAMENTOS_APROVACAO`, variáveis `SIENGE_*`, `CSRF_TRUSTED_ORIGINS` (tudo via `.env`) e loggers para `mapa_obras` e `suprimentos`.
- **`Diario_obra/manage.py`:** hook PyMySQL no topo (`try/except`) para uso no cPanel.
- **`passenger_wsgi.py` (raiz):** path para `Diario_obra`, PyMySQL e import de `lplan_central.wsgi.application`.

Com isso, o monolito fica alinhado ao que está em produção e você pode aplicar as mudanças no servidor seguindo a **seção 5**.
