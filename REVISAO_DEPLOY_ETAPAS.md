# Revisão e deploy – Lplan Sistema (15 etapas)

Checklist para revisar o sistema, remover código não usado e preparar deploy (GitHub + cPanel/banco).

---

## Etapa 1 – Segurança: remover senhas e valores sensíveis do código
- [x] **Gestao_aprovacao**: remover default `'Gestao#2025!'` em `DB_PASSWORD`; exigir `.env`.
- [ ] **Todos os settings**: garantir que `SECRET_KEY` em produção venha só de variável de ambiente (sem fallback inseguro em prod).
- [ ] **DEBUG**: em produção sempre `False` (via `DEBUG=False` no `.env` do cPanel).

---

## Etapa 2 – DEBUG e ALLOWED_HOSTS por ambiente
- [x] **Diario_obra (lplan_central)**: ler `DEBUG` e `ALLOWED_HOSTS` de variáveis de ambiente.
- [x] **Gestao_aprovacao**: remover `'*'` de `ALLOWED_HOSTS`; usar lista explícita ou variável de ambiente; DEBUG por env.
- [x] **Mapa_Controle**: já usa env para `ALLOWED_HOSTS` e `DEBUG`.

---

## Etapa 3 – .gitignore e arquivos que não devem ir para o repositório
- [x] Confirmar que `.env`, `db.sqlite3`, `venv/`, `staticfiles/`, `media/`, `*.log` estão em todos os `.gitignore` (raiz, Diario_obra, Gestao_aprovacao, Mapa_Controle).
- [ ] Garantir que nenhum `.env` com dados reais seja commitado (só `.env.example` sem valores reais).

---

## Etapa 4 – .env.example em cada projeto
- [x] **Diario_obra**: já possui `.env.example` completo (SECRET_KEY, DEBUG, ALLOWED_HOSTS, USE_POSTGRES, DB_*, CELERY_*, EMAIL_*, SITE_URL).
- [x] **Gestao_aprovacao**: criado `.env.example` (SECRET_KEY, DEBUG, ALLOWED_HOSTS, USE_LOCAL_DB, DB_* para MySQL).
- [x] **Mapa_Controle**: criado `.env.example` (SECRET_KEY, DEBUG, ALLOWED_HOSTS, DATABASE_URL, SIENGE_*).

---

## Etapa 5 – Código morto e legado (Diario_obra/core)
- [x] **equipmentList** e **laborList**: já marcados como legado no código; ainda são usados no submit do formulário de diário — não remover.
- [ ] Revisar `console.log`/`console.error` desnecessários em produção (opcional: envolver em `if (DEBUG)` ou remover).
- [ ] Manter TODOs apenas como comentários úteis; não remover funcionalidade em uso.

---

## Etapa 6 – Comandos seed/sample e scripts de teste
- [ ] Garantir que comandos `add_sample_occurrence_tags`, `seed_*` não contenham senhas ou dados reais.
- [ ] Documentar que seeds são para desenvolvimento/dados iniciais; não rodar em produção com dados sensíveis.
- [ ] Scripts `test_*.py` e `run_verificacao_mapa.py`: manter fora do fluxo de deploy automático (não executar em produção).

---

## Etapa 7 – Banco de dados para produção (cPanel)
- [ ] **Diario_obra**: em produção usar PostgreSQL (USE_POSTGRES=True). Criar banco no cPanel (MySQL/PostgreSQL conforme oferta) e preencher `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` no `.env`.
- [ ] **Gestao_aprovacao**: já preparado para MySQL; configurar credenciais do cPanel no `.env`.
- [ ] **Mapa_Controle**: decidir se usa SQLite ou Postgres/MySQL; se remoto, configurar `DATABASE_URL` ou variáveis DB_*.

---

## Etapa 8 – Migrations e static files
- [ ] Rodar `python manage.py migrate` em cada projeto após conectar o banco de produção.
- [ ] Rodar `python manage.py collectstatic --noinput` (Diario_obra e demais que usam admin/static).
- [ ] Configurar no cPanel/Apache/Passenger o alias para `staticfiles` e `media` conforme `STATIC_ROOT` e `MEDIA_ROOT`.

---

## Etapa 9 – GitHub: repositório e primeiro push
- [ ] Inicializar git na raiz desejada (ex.: `Lplan_Sistema` ou `Diario_obra` como repo principal) se ainda não houver.
- [ ] Adicionar remote `origin` apontando para o repositório GitHub.
- [ ] Fazer commit apenas de código e configuração documentada; sem `.env`, `db.sqlite3`, `venv`.
- [ ] Push para `main` ou `master`; proteger branch se for equipe.

---

## Etapa 10 – WSGI e entrada da aplicação (cPanel)
- [ ] **Diario_obra**: apontar Passenger/WSGI para `lplan_central.wsgi.application` e o diretório onde está `manage.py`.
- [ ] **Gestao_aprovacao**: já tem `passenger_wsgi.py` e `.htaccess`; conferir caminhos.
- [ ] Definir no cPanel o Application Root e Python version (ex.: 3.10+).

---

## Etapa 11 – Variáveis de ambiente no cPanel
- [ ] No cPanel (Setup Python App ou variáveis de ambiente do servidor), configurar todas as variáveis do `.env.example` com valores reais (SECRET_KEY, DB_*, DEBUG=False, ALLOWED_HOSTS com o domínio real).

---

## Etapa 12 – E-mail e domínio
- [ ] Configurar `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` para envio de e-mails (recuperação de senha, etc.).
- [ ] Definir `SITE_URL` com a URL final (ex.: `https://sistema.lplan.com.br`).
- [ ] Garantir que `ALLOWED_HOSTS` inclua o domínio/host usado no cPanel.

---

## Etapa 13 – Celery e Redis (se usados em produção)
- [ ] **Diario_obra**: se usar Celery em produção, configurar `CELERY_BROKER_URL` e `CELERY_RESULT_BACKEND` (ex.: Redis no cPanel ou serviço externo).
- [ ] Configurar worker Celery no cPanel (cron ou processo gerenciado) se necessário.

---

## Etapa 14 – Testes pós-deploy
- [ ] Acessar a URL do site; conferir login, redirecionamentos e ausência de 500.
- [ ] Testar criação/edição de diário, ocorrências, atividades; salvar rascunho e reabrir.
- [ ] Verificar se estáticos (CSS/JS/imagens) carregam (collectstatic e alias corretos).
- [ ] Verificar logs em `logs/` ou no painel do cPanel em caso de erro.

---

## Etapa 15 – Documentação final
- [ ] Atualizar `DEPLOY.md` (Diario_obra) e `GITHUB_E_DEPLOY.md` com passos específicos do cPanel (onde colar variáveis, onde apontar WSGI, etc.).
- [ ] Registrar no README principal: qual projeto é o “LPLAN Central” (Diario_obra com lplan_central), como rodar localmente e como fazer deploy.

---

## Resumo de arquivos críticos

| Projeto        | Settings principal      | WSGI              | Observação                    |
|----------------|-------------------------|-------------------|-------------------------------|
| Diario_obra    | lplan_central/settings.py | lplan_central/wsgi.py | Projeto unificado (Central)   |
| Gestao_aprovacao | gestao_aprovacao/settings.py | gestao_aprovacao/wsgi.py, passenger_wsgi.py | Remover senha default; ALLOWED_HOSTS |
| Mapa_Controle  | supplymap/settings.py   | supplymap/wsgi.py  | DEBUG/ALLOWED_HOSTS por env   |

---

*Documento gerado para revisão e deploy. Marque cada item ao concluir.*
