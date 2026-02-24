# Contexto do sistema LPLAN – resumo para novos chats

Documento de referência para qualquer assistente continuar o trabalho sem perder detalhes que conversas longas já conhecem.

---

## 1. O que é o sistema

- **LPLAN** é um sistema unificado com vários módulos:
  - **Diário de Obra (core):** relatórios/diários de obra, EAP, atividades, projetos.
  - **GestControll (gestao_aprovacao):** pedidos de obra (solicitação → aprovação), obras, empresas, usuários por obra.
  - **Mapa de Suprimentos (mapa_obras / suprimentos):** mapa de obras e suprimentos.
  - **Central:** ponto único para **obras** e **usuários**; só staff/superuser. Obras são criadas/editadas no Central e refletidas nos outros módulos.

- **Pasta principal do projeto:** `Diario_obra` (Django); `manage.py` está em `Diario_obra/`. O workspace pode ser `Lplan_Sistema` (contém `Diario_obra`, `Mapa_Controle`, etc.).

---

## 2. Login e autenticação

- **Uma única tela de login:** `/login/` (view do **core**; nome da URL: `login`). Não usar `accounts:login` nem `/accounts/login/` para login.
- **Settings:** `LOGIN_URL = '/login/'`, `LOGIN_REDIRECT_URL = '/select-system/'`.
- **Logout:** URL nome `logout` (core); templates e decorators usam `redirect('login')` e `redirect('logout')`.
- **Decorators em gestao_aprovacao:** `gestor_required` e `admin_required` redirecionam para `redirect('login')` (não `accounts:login`).

---

## 3. Grupos e perfis (accounts.groups)

- **Constante:** `from accounts.groups import GRUPOS`.
- **Grupos:**
  - **GestControll:** `ADMINISTRADOR`, `RESPONSAVEL_EMPRESA`, `APROVADOR`, `SOLICITANTE`.
  - **Diário:** `GERENTES` (valor: "Diário de Obra").
  - **Mapa:** `ENGENHARIA` (valor: "Mapa de Suprimentos").
- **Perfil no GestControll** (`gestao_aprovacao.utils`): `get_user_profile(user)` → `'admin' | 'responsavel_empresa' | 'aprovador' | 'solicitante' | None`. Prioridade: admin > responsavel_empresa > aprovador > solicitante.
- **Funções importantes:**
  - `is_admin(user)` = grupo Administrador ou superuser.
  - `is_gestor(user)` = **alias de `is_aprovador(user)`** = grupo Aprovador ou superuser. **Administrador (só grupo) NÃO é `is_gestor`**; o decorator `gestor_required` deixa admin entrar via `is_admin`.
  - `is_engenheiro(user)` = grupo Solicitante ou superuser.
  - `is_responsavel_empresa(user)` = grupo Responsavel Empresa ou superuser.

---

## 4. Tela “Selecionar sistema” (select-system)

- **Quem vê o quê:**
  - **Diário:** `has_diario` = superuser OU staff OU grupo "Diário de Obra" (GRUPOS.GERENTES).
  - **GestControll:** `has_gestao` = superuser OU staff OU qualquer um de (Administrador, Responsavel Empresa, Aprovador, Solicitante).
  - **Mapa:** `has_mapa` = superuser OU staff OU grupo "Mapa de Suprimentos" (GRUPOS.ENGENHARIA).
  - **Central:** `has_central` = **apenas** superuser OU staff (Administrador sem staff não vê Central).

---

## 5. Painel do sistema (hub único)

- **Ponto único para staff:** o **Painel do sistema** (`/accounts/admin-central/`, URL name `accounts:admin_central`) é o hub de onde saem todos os caminhos: obras, usuários, manutenção, ajuda, dashboard e Mapa. Quem acessa `/central/` (nome `central_hub`) é **redirecionado** para o Painel.
- **No Painel:** (1) KPIs (usuários, diários, pedidos, Mapa); (2) seção **“Obras e usuários”** com card de Ajuda e quatro cards (Obras, Usuários, Atualizar listas, Ajuda) apontando para as URLs do Central; (3) **“Mapa, análise e navegação”** (Criar obra no Mapa, Gerenciar obras no Mapa, Análise de usuários, Selecionar sistema). Obras do Mapa = `mapa_obras.Obra`; obras do Central = `core.Project` (fonte única que sincroniza).

## 6. Central (obras e usuários) — URLs usadas pelo Painel

- **URLs:** `/central/` redireciona para o Painel. Demais: `/central/usuarios/`, `/central/usuarios/criar/`, `/projects/`, etc. Nomes: `central_hub`, `central_list_users`, `central_create_user`, `central_project_list`, `central_manutencao`, `central_ajuda`, …
- **Acesso:** só `is_staff` ou `is_superuser`. Quem não é staff recebe 403.
- **Listagem de projetos (obras do Central):** URL **nome** = `central_project_list` (rota `/projects/`). **Não usar nome `project-list`** no core para essa view: a API REST (DRF) em `core.api_urls` usa `router.register(r'projects', ...)` e gera um nome `project-list` para o ViewSet; se a view do Central também se chamasse `project-list`, o `reverse('project-list')` poderia resolver para a API e quebrar testes e links.
- **Templates:** links para obras usam `{% url 'central_project_list' %}`; `base.html` usa `central_project_list`. O template `central_hub.html` existe mas não é renderizado (a view `central_hub` redireciona staff para o Painel).
- **GestControll:** usuários em `/gestao/usuarios/` — se o usuário for staff/superuser, redireciona para o Central (`central_list_users`, etc.). Responsável por empresa e Administrador (não staff) usam as views do gestao normalmente.

---

## 7. Obras unificadas (lista única)

- **Fonte da verdade para “obras” no Diário:** `core.Project`.
- **GestControll:** `gestao_aprovacao.Obra` tem FK opcional `project` para `core.Project`. Ao salvar Project no core, `sync_project_to_gestao_and_mapa(project)` (em `core/sync_obras.py`) cria/atualiza Obra no GestControll e no Mapa.
- **Usuários:** no Central (ou no gestao para não-staff) ao salvar usuário, são criados/atualizados `ProjectMember` (Diário) e `WorkOrderPermission` (GestControll) a partir dos `project_ids` escolhidos. Quem tem obra no GestControll mas não tem ProjectMember pode ganhar ProjectMember por sync ao abrir seleção de obra do Diário.

---

## 8. Filtros por obra (quem vê o quê)

- **GestControll – lista de pedidos (`list_workorders`):**
  - **Admin:** vê todos os pedidos.
  - **Aprovador:** vê pedidos das **obras** em que tem `WorkOrderPermission` tipo `aprovador` (e das empresas dessas obras).
  - **Responsável por empresa:** vê pedidos das obras das empresas que gerencia.
  - **Solicitante:** vê pedidos **só das obras** em que tem `WorkOrderPermission` tipo `solicitante` (e dos solicitantes dessas obras). Se não tiver nenhuma obra vinculada, vê **só os pedidos que ele mesmo criou**.
- **Aprovar pedido:** aprovador precisa ter permissão na **obra** (ou ser admin). Sem permissão na obra, a view redireciona para o detalhe do pedido (não deixa aprovar).
- **Diário – seleção de obra:** `_get_projects_for_user(request)` retorna projetos em que o usuário é `ProjectMember` (ou staff/superuser vê todos). Se não tiver ProjectMember mas tiver obra no GestControll (Obra com `project` e permissão), o sync pode criar ProjectMember.
- **Listagem de projetos do Central (`project_list_view`):** só staff/superuser. Gerentes (sem staff) recebem 403. Anônimo deve receber 302 para login (não 403); há decorator e checagem explícita na view para isso.

---

## 9. Comandos de gestão

- **Zerar tudo:** `python manage.py zerar_tudo` (opção `--usuarios` apaga também usuários; depois rodar `createsuperuser`).
- **Reset e recriar dados:** `python manage.py reset_e_criar_dados` — limpa e recria 3 empresas (Entreaguas, Okena, Sunrise) e 3 obras (ENT-01, OKN-01, SUN-01) no core, gestao e mapa.
- Ordem de limpeza: GestControll, core, Suprimentos, Mapa (evitar ProtectedError).

---

## 10. Testes

- **Módulo:** `core.test_niveis_acessos`.
- **Comando:** na pasta `Diario_obra`, `python manage.py test core.test_niveis_acessos -v 2`.
- **O que cobre:**
  - Não autenticado: redirect para login onde aplicável.
  - Select-system: has_diario, has_gestao, has_mapa, has_central por perfil.
  - Central e listagem de projetos: só staff; anônimo → 302; gerente sem staff → 403.
  - GestControll: list_users (admin/responsável); staff redireciona para Central; approve_workorder (gestor_required); admin_required (ex.: list_email_logs).
  - Lógica de perfis: get_user_profile, is_admin, is_gestor (alias is_aprovador), etc.
  - **Filtros por obra:** solicitante só vê pedidos das obras vinculadas; solicitante sem obra vê só os que criou; aprovador só vê e só aprova nas obras com permissão; Diário só projetos (ProjectMember); admin vê todos.
- **URL da listagem de projetos nos testes:** usar sempre `reverse('central_project_list')`, nunca `reverse('project-list')` para a view do Central.

---

## 11. Manutenção (operar o sistema sem o desenvolvedor)

- **Guia para quem vai operar:** `Diario_obra/MANUTENCAO.md` — comandos, onde ver logs, problemas comuns, uso do Central e do Painel do sistema.
- **Tela de diagnóstico (staff):** `/central/manutencao/` — acessível pelo Painel (card "Atualizar listas"). Status da sincronia de obras, botão para re-sincronizar todas, links para Admin e logs de e-mail do GestControll.
- **Logs:** diretório `logs/` na pasta do projeto (`lplan.log`, `lplan_errors.log`); em desenvolvimento também no console.

---

## 12. Arquivos importantes

| Função | Caminho |
|--------|--------|
| URLs raiz, core, login, select-system, central | `core/urls.py` |
| View select-system, central_hub, _get_projects_for_user, project_list_view | `core/frontend_views.py` |
| Central (views de usuário e manutenção) | `core/central_views.py` |
| Sync Project → GestControll/Mapa | `core/sync_obras.py` |
| Grupos | `accounts/groups.py` |
| Permissões e decorators gestao | `gestao_aprovacao/utils.py` |
| Views gestao (list_workorders, approve, list_users, etc.) | `gestao_aprovacao/views.py` |
| Zerar tudo | `core/management/commands/zerar_tudo.py` |
| Reset e recriar dados | `core/management/commands/reset_e_criar_dados.py` |
| Testes de níveis e filtros | `core/test_niveis_acessos.py` |

---

## 13. Armadilhas comuns

- **`project-list` vs API:** a listagem de projetos do Central usa nome `central_project_list`. O DRF em `api_urls` gera `project-list` para o ViewSet de projects. Não renomear a view do Central de volta para `project-list`.
- **Administrador e `is_gestor`:** no código, `is_gestor` = `is_aprovador`. Um usuário só com grupo Administrador tem `is_gestor == False`; mesmo assim pode acessar views de gestor porque `gestor_required` verifica `is_gestor OR is_admin`.
- **AnonymousUser:** importar de `django.contrib.auth.models`: `from django.contrib.auth.models import AnonymousUser` (não de `django.contrib.auth`).
- **Caminho do projeto no Windows:** pode haver problema de encoding com “Área de Trabalho” em comandos; o usuário costuma rodar os comandos a partir da pasta `Diario_obra` no terminal.

---

## 14. Resumo em uma frase

Sistema LPLAN: Diário de Obra (core), GestControll (gestao), Mapa e Central; um login em `/login/`; grupos definem acesso por sistema; Central (staff) para obras e usuários; obras unificadas via core.Project e sync; filtros por obra no GestControll (WorkOrderPermission) e por projeto no Diário (ProjectMember); testes em `core.test_niveis_acessos`; listagem de projetos do Central com nome de URL `central_project_list`.
