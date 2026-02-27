# Regras de Ouro – Deploy cPanel / MariaDB

**Contexto para o Cursor (e para qualquer refatoração futura):**  
O sistema unificado (Diário de Obras, Gestão de Aprovação, Mapa de Obras e Suprimentos) está em produção em hospedagem compartilhada cPanel com MariaDB. As restrições do ambiente exigiram ajustes que **não podem ser revertidos ou removidos** em futuras alterações de código.

---

## 1. Leitura forçada do `.env` (settings.py)

**Problema que ocorreu:** `try/except` silencioso na importação do `python-dotenv` fez o erro ser engolido, o `.env` foi ignorado, `ALLOWED_HOSTS` ficou vazio e o Django usou SQLite.

**Regra:** O topo de `Diario_obra/lplan_central/settings.py` deve manter sempre:

- `from dotenv import load_dotenv` (sem try/except em volta).
- `env_path = os.path.join(BASE_DIR, '.env')` e `load_dotenv(env_path)`.

**Não:** usar `try/except` em volta do `load_dotenv` de forma a esconder falhas. A biblioteca `python-dotenv` deve constar no `requirements.txt` / `requirements-cpanel.txt`.

---

## 2. Limite de threads OpenBLAS/OMP (manage.py e passenger_wsgi.py)

**Problema que ocorreu:** Pandas/Numpy ao serem importados (app suprimentos) abriam dezenas de threads; o cPanel bloqueou por excesso de uso de CPU (`pthread_create failed`, Resource temporarily unavailable).

**Regra:** Os arquivos **`Diario_obra/manage.py`** e **`passenger_wsgi.py`** (raiz do repo) devem **iniciar** com:

```python
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
```

Essas linhas devem vir **antes** de qualquer import que possa carregar Django ou apps (e portanto pandas/numpy). Em seguida, manter o bloco PyMySQL (ver regra 3).

**Não:** remover ou comentar essas duas variáveis de ambiente; não mover para depois de imports pesados.

---

## 3. PyMySQL no cPanel (manage.py e passenger_wsgi.py)

**Problema que ocorreu:** `mysqlclient` não compila no cPanel (falta Python.h, restrições de compilação).

**Regra:** Manter o uso de **PyMySQL** como substituto:

- Em **`manage.py`**: após OPENBLAS/OMP, bloco `try: import pymysql; pymysql.install_as_MySQLdb(); except ImportError: pass`.
- Em **`passenger_wsgi.py`**: após OPENBLAS/OMP e ajuste de path, `import pymysql` e `pymysql.install_as_MySQLdb()` (ou try/except se preferir consistência).

**Não:** remover esses blocos; não trocar por `mysqlclient` em ambiente cPanel.

---

## 4. Migrações: sem SQL procedural no MariaDB

**Problema que ocorreu:** Migração `gestao_aprovacao/0004_...` usava SQL procedural (variáveis `SET @exist`, `PREPARE`, `EXECUTE`). O conector PyMySQL no cPanel não executa bem múltiplos comandos complexos em um único `cursor.execute()` (erro 1064).

**Regra:** Em **migrações Django (RunPython / RunSQL)**:

- **Não** usar SQL procedural com variáveis MySQL/MariaDB (SET, PREPARE, EXECUTE, etc.) em um único `execute()`.
- Usar **Python** com `try/except` e comandos SQL **atómicos** e simples (ex.: um `ALTER TABLE ... DROP INDEX` por vez).

---

## 5. Histórico de migrações do app `gestao_aprovacao`

**Problema que ocorreu:** Unificação e renomeação de tabelas (ex.: `obras_*` → `gestao_aprovacao_*`) geraram dessincronia entre histórico de migrações e banco real. Migrações intermediárias (0004–0019) tentavam alterar índices/tabelas que já não existiam com aquele nome (erros 1050, 1146).

**Solução aplicada em produção:** Foi usado `migrate gestao_aprovacao --fake` onde necessário; o esquema físico do banco está correto e alinhado aos models atuais.

**Regra:** O **estado atual dos `models.py`** é a fonte da verdade. **Não** criar novas migrações para “corrigir” o passado do app `gestao_aprovacao`. Daqui para frente, criar migrações **apenas para alterações reais e futuras** nos modelos.

---

## Resumo para o Cursor

- **Não sobrescrever nem remover:** carregamento forçado do `.env` no `settings.py`, variáveis `OPENBLAS_NUM_THREADS` e `OMP_NUM_THREADS` no início de `manage.py` e `passenger_wsgi.py`, e o hook PyMySQL nesses dois arquivos.
- **Em migrações:** só SQL atômico e direto; lógica condicional em Python com try/except, nunca SQL procedural no MariaDB.
- **App gestao_aprovacao:** não “consertar” histórico de migrações; apenas novas migrações para mudanças futuras de modelos.

Documento gerado a partir do Relatório de Deploy e Ajustes de Infraestrutura (cPanel / MariaDB). Atualizado conforme necessário.
