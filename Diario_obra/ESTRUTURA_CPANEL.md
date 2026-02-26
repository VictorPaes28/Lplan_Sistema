# Estrutura do projeto no cPanel – LPLAN Sistema

Este documento descreve como o projeto está organizado no servidor (cPanel) e a relação com a pasta local, para facilitar o deploy e a manutenção.

---

## 1. Visão geral no servidor

| Caminho no servidor | Descrição |
|---------------------|-----------|
| `/home/lplan` | Raiz da conta cPanel (home do usuário `lplan`) |
| `/home/lplan/public_html` | Raiz web – o que é acessível pela URL do site |
| `/home/lplan/public_html/sistema_lplan` | **Raiz do projeto** – repositório Git, virtualenv e subpastas das aplicações |
| `/home/lplan/public_html/sistema_lplan/Diario_obra` | **Aplicação Django que roda** – onde estão `manage.py`, `lplan_central`, `core`, etc. |
| `/home/lplan/virtualenv` | Ambiente virtual Python (pode estar aqui ou dentro de `sistema_lplan`) |
| `/home/lplan/logs` | Logs da conta |
| `/home/lplan/public_html/sistema_lplan/virtualenv` | Ambiente virtual *dentro* do projeto (conforme captura) |

O **Passenger** (servidor de aplicação Python do cPanel) deve estar configurado com o **diretório da aplicação** apontando para:

```text
/home/lplan/public_html/sistema_lplan/Diario_obra
```

Assim, o `passenger_wsgi.py` que é executado é o que está **dentro de Diario_obra** (o mesmo que está no repositório local).

---

## 2. Estrutura em árvore (resumida)

```text
/home/lplan/
├── .cpanel, .ssh, logs, mail, public_ftp, ssl, tmp, etc.
├── gestao_aprovacao/          # (possível cópia ou link antigo)
├── lplan/                     # (pasta antiga/alternativa)
├── sistema_lplan/             # (possível cópia em outro nível)
├── public_html/
│   └── sistema_lplan/        # ← Raiz do projeto no cPanel
│       ├── .git
│       ├── __pycache__/
│       ├── passenger_wsgi.py  # Ponto de entrada se o app root for aqui
│       ├── requirements.txt
│       ├── virtualenv/
│       ├── Diario_obra/       # ← App Django (Lplan Central) – app root do Passenger
│       │   ├── accounts/, core/, diario_obra/, gestao_aprovacao/,
│       │   │   lplan_central/, mapa_obras/, suprimentos/, templates/
│       │   ├── env ou .env   # Variáveis de ambiente (no servidor aparece como "env")
│       │   ├── manage.py
│       │   ├── passenger_wsgi.py  # Este é o que o Passenger deve usar
│       │   ├── requirements.txt
│       │   └── ...
│       ├── Gestao_aprovacao/
│       ├── Lplan_Sistema/
│       └── Mapa_Controle/
```

---

## 3. Correspondência: servidor (cPanel) ↔ local (Windows)

| No cPanel | No seu PC (após transferência) |
|-----------|---------------------------------|
| `public_html/sistema_lplan` | Pasta raiz do repositório (pode ser `Lplan_Sistema` ou onde está o `.git` com Diario_obra, Gestao_aprovacao, etc.) |
| `public_html/sistema_lplan/Diario_obra` | `Lplan_Sistema/Diario_obra` ou `.../Diario_obra` (onde está `manage.py` e `lplan_central`) |
| `sistema_lplan/virtualenv` | Não versionado – no servidor é recriado com `pip install -r requirements.txt` |
| `Diario_obra/env` (no cPanel) | `Diario_obra/.env` (local) – no servidor o arquivo pode aparecer como `env` |

Importante: no cPanel o arquivo de ambiente aparece como **`env`** (sem ponto) em uma das capturas. Pode ser exibição do painel ou nome real. O Django normalmente usa **`.env`**; se no servidor estiver como `env`, o projeto só o carregará se usar `python-dotenv` com esse nome ou se você criar um `.env` (ou ajustar a leitura no código).

---

## 4. Onde o Passenger aponta

- O **Application Root** (ou “Document Root” da aplicação Python) no cPanel deve ser:
  - **`sistema_lplan/Diario_obra`** (e não apenas `sistema_lplan`).
- Assim, ao acessar o domínio, o cPanel executa:
  - `/home/lplan/public_html/sistema_lplan/Diario_obra/passenger_wsgi.py`
- Esse arquivo:
  - Define `project_home` = pasta onde está o `passenger_wsgi.py` (ou seja, `Diario_obra`)
  - Adiciona essa pasta ao `sys.path`
  - Usa `DJANGO_SETTINGS_MODULE = 'lplan_central.settings'`
  - Entrega a aplicação via `get_wsgi_application()`

Se o Application Root estiver em `sistema_lplan` (um nível acima), o Passenger executaria o `passenger_wsgi.py` de **sistema_lplan**, não o de **Diario_obra**. Nesse caso, ou se move o `passenger_wsgi.py` para cima e se ajusta o `sys.path` para apontar para `Diario_obra`, ou se mantém o Application Root em `sistema_lplan/Diario_obra` e usa o `passenger_wsgi.py` que está dentro de `Diario_obra` (recomendado).

---

## 5. Complexidade resumida

1. **Várias pastas “irmãs”** em `sistema_lplan`: `Diario_obra`, `Gestao_aprovacao`, `Lplan_Sistema`, `Mapa_Controle`. No repositório local você tem algo parecido (por exemplo `Lplan_Sistema` como raiz com `Diario_obra` dentro). No servidor, a aplicação que **roda** é a que está em **Diario_obra** (Django com `lplan_central.settings`).

2. **Dois `passenger_wsgi.py`**: um em `Gestao_aprovacao` e um em `Diario_obra`. O que importa para o site atual (Lplan Central / Diário de Obra) é o de **Diario_obra**. O de Gestao_aprovacao seria usado apenas se houver outra “Setup Application” no cPanel para outro subdomínio/pasta.

3. **Arquivo de ambiente**: no servidor aparece como **`env`** (sem ponto) em `Diario_obra`. O Django **não** carrega arquivos automaticamente; ele só lê `os.environ`. No cPanel você pode:
   - Definir as variáveis na interface **Setup Python App** → "Environment variables", ou
   - Fazer o projeto carregar um arquivo: adicionar no início de `lplan_central/settings.py` (antes de usar `os.environ.get`) o uso de `python-dotenv` para carregar `.env` ou, se existir, `env` (arquivo sem ponto). Assim tanto `.env` local quanto `env` no servidor funcionam.

4. **Banco de dados**: em produção no cPanel normalmente usa-se **MySQL** (conta `lplan_gestaoap2`, banco `lplan_Sistema`), configurado no `.env` com `USE_MYSQL=True` e `DB_*`. O `db.sqlite3` e a pasta `media/` que você tem no PC são da cópia local; no servidor, os dados ficam no MySQL e os uploads em `media/` dentro de `Diario_obra` (se existir e estiver configurado).

5. **Virtualenv**: pode estar em `/home/lplan/virtualenv` ou em `sistema_lplan/virtualenv`. O "Setup Python App" do cPanel define qual interpretador e qual pasta é o "application root"; o virtualenv precisa ter as dependências instaladas. **Use `requirements-cpanel.txt`** (veja seção 7).

---

## 6. Checklist rápido para deploy no cPanel

- [ ] Application Root da aplicação Python = `sistema_lplan/Diario_obra`
- [ ] Arquivo de entrada = `passenger_wsgi.py` (o que está dentro de `Diario_obra`)
- [ ] Variáveis de ambiente no `.env` (ou `env`) em `Diario_obra`: `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `USE_MYSQL=True`, `DB_*`, etc.
- [ ] Virtualenv com **`pip install -r requirements-cpanel.txt`** (não use `requirements.txt` – ver seção 7)
- [ ] Após atualizar código: `python manage.py migrate`, `python manage.py collectstatic --noinput`
- [ ] Pasta `media/` (e `staticfiles/` se usar) com permissões corretas para o usuário do Passenger

Se quiser, na próxima etapa podemos detalhar só o “Application Root” e o `passenger_wsgi.py` (incluindo um exemplo de conteúdo se o app root for `sistema_lplan` em vez de `Diario_obra`).
