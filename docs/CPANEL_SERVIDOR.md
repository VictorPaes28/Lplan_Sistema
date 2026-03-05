# Verificações no servidor cPanel

Checklist para evitar erros de conexão, sessão e "Sessão inválida" no cPanel.

## 1. passenger_wsgi.py (obrigatório)

O arquivo **passenger_wsgi.py** na raiz do projeto deve:

- **Carregar o patch do PyMySQL** antes de importar Django (cPanel costuma ter só `pymysql`, não `mysqlclient`). Sem isso, toda requisição que usa o banco pode dar 500 ou falha silenciosa.
- **Fazer `os.chdir(project_root)`** para o diretório de trabalho ser a pasta do projeto; assim o `.env` e caminhos relativos funcionam.

Se o **passenger_wsgi.py** no servidor for antigo, atualize com o da raiz do repositório (com PyMySQL e `chdir`).

## 2. Arquivo .env

- Deve estar na **mesma pasta** que o `passenger_wsgi.py` (ex.: `/home/lplan/sistema_lplan/.env`).
- Nome exato: **`.env`** (com ponto no início).
- Permissões: leitura para o usuário do Passenger (ex.: `chmod 600 .env`).
- Variáveis mínimas para o mapa/sessão funcionarem:
  - `USE_MYSQL=True`
  - `DB_NAME=...`, `DB_USER=...`, `DB_PASSWORD=...`, `DB_HOST=localhost` (ou `127.0.0.1`)
  - `ALLOWED_HOSTS=sistema.lplan.com.br,www.sistema.lplan.com.br`
  - `DEBUG=True` ou `False` conforme o ambiente

## 3. Conexão MySQL

- No cPanel, **MySQL** costuma aceitar `DB_HOST=localhost` ou `DB_HOST=127.0.0.1`. Se der "Can't connect to MySQL server", teste o outro.
- Se o provedor usar **socket Unix**, no `lplan_central/settings.py` (bloco MySQL) descomente e ajuste a opção `unix_socket` em `OPTIONS` conforme a documentação do cPanel.
- O projeto usa **CONN_MAX_AGE=0** em produção para evitar reutilizar conexão que o servidor pode ter fechado (comum em hospedagem compartilhada).

## 4. Sessão no banco

- O sistema usa **SESSION_ENGINE = django.contrib.sessions.backends.db**. Se o MySQL estiver inacessível ou as tabelas de sessão não existirem, o login/sessão falha e pode aparecer "Sessão inválida" ou redirect para login.
- Garanta que as **migrations** foram aplicadas no servidor: `python manage.py migrate`.
- Tabela esperada: **django_session** (e outras do Django).

## 5. Logs no servidor

- **Passenger:** em geral em `/home/lplan/logs/passenger.log` (ou o path definido no .htaccess). Erros de import (ex.: "No module named 'MySQLdb'") aparecem aí.
- **Django:** `logs/lplan.log` e `logs/lplan_errors.log` na pasta do projeto (se LOG_DIR existir e tiver permissão de escrita). Erros de banco e CSRF 403 são logados aí.

## 6. Resumo rápido

| Onde            | O que verificar |
|-----------------|-----------------|
| passenger_wsgi  | Tem `pymysql.install_as_MySQLdb()` e `os.chdir(project_root)` |
| .env            | Na mesma pasta do passenger_wsgi; USE_MYSQL, DB_*, ALLOWED_HOSTS |
| MySQL           | localhost ou 127.0.0.1; usuário/senha do cPanel; migrate já rodou |
| Sessão          | SESSION_ENGINE=db; tabela django_session existe |
| Logs            | passenger.log e lplan_errors.log para ver 500 ou exceções de DB |
