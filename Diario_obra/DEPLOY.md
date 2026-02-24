# Deploy e fluxo de produção – LPLAN Central

Este guia cobre como deixar o sistema pronto para produção e **como evitar ficar editando arquivos manualmente no servidor** (especialmente no cPanel).

---

## 1. Configuração mínima para produção

- Crie um arquivo **`.env`** no servidor (copie do `.env.example`) e preencha:
  - `SECRET_KEY` (gere uma nova chave, nunca use a do exemplo)
  - `DEBUG=False`
  - `ALLOWED_HOSTS=seudominio.com.br,www.seudominio.com.br`
  - Banco (PostgreSQL recomendado: `USE_POSTGRES=True` + `DB_*`)
  - E-mail SMTP (para recuperação de senha)
- Rode uma vez no servidor:
  - `python manage.py migrate`
  - `python manage.py collectstatic --noinput`
  - `python manage.py createsuperuser` (se ainda não tiver)
- Servidor de aplicação: use **Gunicorn** (ou o que o cPanel exigir), não `runserver`.
- Celery (se usar PDF/ tarefas em background): `celery -A lplan_central worker -l info`

---

## 2. Por que não editar arquivos direto no cPanel

- Fácil sobrescrever alterações na próxima atualização.
- Difícil rastrear o que mudou e onde.
- Risco de erro ao copiar/colar e de expor dados sensíveis.

O ideal é: **código sempre vem do seu repositório ou do seu PC**, e o servidor só **recebe** esse código (e usa `.env` para segredos).

---

## 3. Opções para melhorar o entrosamento (do mais simples ao mais robusto)

### A) Manter cPanel mas parar de editar à mão

- **Use apenas o `.env` no servidor**  
  Toda configuração que muda entre ambientes (DEBUG, ALLOWED_HOSTS, DB, e-mail, etc.) fica no `.env`. Você **não** edita mais `settings.py` no cPanel; o `settings.py` que sobe no deploy é o mesmo do Git.

- **Deploy por upload só do que mudou**  
  Em vez de abrir arquivos no cPanel:
  - No seu PC: altere o código, teste, depois envie só as pastas/arquivos que mudaram (por FTP/SFTP ou “Arquivos” do cPanel).
  - Mantenha uma lista no DEPLOY.md: “arquivos que sempre preciso atualizar” (ex.: só a pasta do app `core`, `lplan_central/settings.py se mudar, etc.). Assim você não fica “mexendo em tudo” no servidor.

- **Git no cPanel (se disponível)**  
  Muitos cPanels têm “Git Version Control” ou terminal:
  - No servidor: clone o repositório numa pasta (ex.: `~/lplan`) e configure o app Python do cPanel para usar essa pasta.
  - Quando quiser atualizar: no cPanel, “Pull” do repositório (ou via SSH: `git pull`). Assim você **nunca** edita código à mão no servidor; só configuração (`.env`) e eventualmente `migrate`/`collectstatic` após o pull.

### B) Servidor com SSH (VPS) – bem melhor para Django

Se você puder usar um **VPS** (ex.: DigitalOcean, Contabo, Locaweb VPS, AWS Lightsail) em vez de hospedagem compartilhada:

- Você sobe o código por **Git** (`git clone` / `git pull`).
- Configuração fica em **`.env`** (nunca no Git).
- Deploy vira um script ou poucos comandos:
  - `git pull`
  - `pip install -r requirements.txt` (se mudou dependência)
  - `python manage.py migrate --noinput`
  - `python manage.py collectstatic --noinput`
  - Reiniciar Gunicorn (e Celery, se usar).

Nada de editar arquivo no painel; tudo versionado e repetível.

### C) Deploy automático (CI/CD) – o mais profissional

Com o código em **GitHub** (ou GitLab):

- Um **script de deploy** (ex.: GitHub Actions) pode:
  - Rodar testes.
  - Conectar no servidor por SSH (ou FTP/SFTP) e fazer `git pull`, `migrate`, `collectstatic`, reinício do app.

Assim você só dá “push” no repositório e a atualização cai no servidor sem você abrir cPanel nem editar arquivo lá.

### D) Plataformas que gerenciam deploy (sem cPanel)

Serviços que entendem Django e fazem deploy a partir do Git, **sem você configurar servidor**:

- **Render.com** – plano grátis para começar; conecta no GitHub e faz deploy a cada push.
- **Railway.app** – similar; deploy por Git.
- **PythonAnywhere** – bom para Django; você faz “pull” do Git e recarrega o app no painel.
- **Fly.io** – um pouco mais técnico, mas muito flexível.

Vantagem: sem lidar com cPanel, conexões externas, Gunicorn manual, etc.; eles cuidam de porta, SSL e processo.

---

## 4. Resumo prático

| Situação | Recomendaçao |
|----------|--------------|
| **Ficar no cPanel por enquanto** | Parar de editar código no servidor. Usar só `.env` para configuração. Atualizar enviando só os arquivos que mudaram (FTP/arquivos) ou usar Git no cPanel se tiver. |
| **Poder mudar de hospedagem** | Preferir um VPS com SSH e fazer deploy com `git pull` + script (migrate, collectstatic, restart). |
| **Querer menos dor de cabeça com servidor** | Considerar Render, Railway ou PythonAnywhere; deploy por Git, sem cPanel. |

O ponto central: **não mantenha o hábito de alterar arquivos manualmente no cPanel**. Use sempre o mesmo código que está no seu ambiente (e no Git) e só mude configuração via `.env` e, quando possível, deploy por Git ou script.

---

## 5. Comandos úteis no servidor (após cada deploy)

```bash
# Ativar ambiente virtual (caminho pode variar no cPanel)
source venv/bin/activate   # Linux
# ou: .\venv\Scripts\activate  # Windows no servidor

# Atualizar dependências (se requirements.txt mudou)
pip install -r requirements.txt

# Migrações
python manage.py migrate --noinput

# Arquivos estáticos (obrigatório com WhiteNoise)
python manage.py collectstatic --noinput

# Reiniciar aplicação (depende de como o cPanel/servidor roda o app)
# Ex.: touch /var/www/meuapp/tmp/restart.txt   (Passenger)
# Ou reiniciar serviço Gunicorn/systemd conforme sua hospedagem.
```

Se quiser, na próxima etapa podemos montar um **script único** (ex.: `deploy.sh`) que faz `git pull`, `migrate`, `collectstatic` e reinício, para você só rodar um comando após cada atualização.
