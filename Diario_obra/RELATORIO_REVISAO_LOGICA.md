# Revisão lógica – Diário de Obra e sistema

Revisão feita em fluxos críticos (formulário do diário, formsets, validações e persistência). Testes lógicos, não automatizados.

---

## 1. Correções aplicadas

### 1.1 Formulário principal inválido: perda de dados (CORRIGIDO)

**Problema:** Quando o usuário enviava o formulário do diário e o **formulário principal** (ConstructionDiaryForm) era inválido (ex.: data duplicada, data futura, fora do período do projeto), a view apenas exibia `messages.error()` e **não fazia `return render()`**. O fluxo seguia para o bloco `else` do `if request.method == 'POST'`, que não é executado em POST, e em seguida para o `else` do método (tratamento de GET). O resultado era a exibição do formulário **vazio** (como em GET), com perda de todo o conteúdo preenchido.

**Correção:** No bloco em que o form principal está inválido, passamos a montar o contexto com os dados do POST (e arquivos preservados em `files_dict`), recriar formsets com `request.POST` / `normalized_post` e **retornar `render(request, 'core/daily_log_form.html', context)`**. Assim o usuário vê os erros e mantém os dados digitados.

### 1.2 Form válido e formsets com erro: formulário vazio (CORRIGIDO)

**Problema:** Quando o **formulário principal era válido** e o diário era salvo na transação, mas algum **formset** (imagens, atividades ou ocorrências) falhava na validação, a view exibia `messages.warning()` e **não retornava**. O fluxo saía do `if form.is_valid()` e caía no `else` do `if request.method == 'POST'`, ou seja, no tratamento de **GET**. A resposta era a tela de novo diário **em branco**, mesmo com o diário já salvo e a mensagem de aviso exibida.

**Correção:** No ramo “diário salvo mas alguns formsets falharam”, passamos a recriar o form e os formsets com `normalized_post` e `preserved_files`, montar o mesmo contexto da view e fazer **`return render(request, 'core/daily_log_form.html', context)`**. O usuário continua na tela de edição do mesmo diário, com os erros dos formsets visíveis.

---

## 2. Pontos verificados (sem alteração)

### 2.1 Unicidade projeto + data

- **Form (ConstructionDiaryForm.clean):** Há validação explícita de unicidade `(project, date)`. Em edição, o próprio diário é excluído da consulta (`existing.exclude(pk=instance_pk)`). Mensagem de erro clara.
- **Modelo:** `unique_together = [['project', 'date']]` no `ConstructionDiary`. Em caso de falha da validação no form, o `IntegrityError` não seria a primeira linha de defesa; o form já evita isso.

### 2.2 Projeto e permissão

- Projeto vem da sessão (`get_selected_project(request)`). O form recebe `project` no `__init__` e usa `HiddenInput` para o campo `project`, garantindo que o valor submetido seja o da obra selecionada.
- Em edição, `diary.can_be_edited_by(request.user)` é verificado antes de processar o POST e ao carregar o diário.

### 2.3 Assinatura obrigatória

- A checagem “assinatura do responsável pelo preenchimento obrigatória” ocorre **dentro** do `transaction.atomic()`, **após** salvar diário, imagens, worklogs, ocorrências, mão de obra e equipamentos.
- Se `not is_partial_save` e `signature_inspection` estiver vazio, é lançado `ValueError`, a transação é revertida e o usuário vê a mensagem de erro. Comportamento correto.

### 2.4 Preservação de arquivos (FILES)

- No início do POST, os arquivos de `request.FILES` são copiados para `files_dict` (objetos em memória), pois `request.FILES` pode ser consumido uma única vez.
- Depois, `preserved_files` (MultiValueDict) é montado a partir de `files_dict` e usado nos formsets de imagens e no processamento manual de fotos/vídeos/anexos. O re-render em caso de form inválido usa `files_dict` para reutilizar os arquivos.

### 2.5 Prefixo do formset de atividades (work_logs)

- O formset usa o prefixo `work_logs` (DailyWorkLogFormSet).
- A view normaliza o POST quando existe o prefixo antigo `dailyworklog_set`: copia os management form e os campos para `work_logs-*`. O template/JS usa `work_logs-` ao adicionar linhas. Consistente.

### 2.6 Worklogs e Activity

- `DailyWorkLogForm` não expõe o FK `activity`; usa o campo de texto `activity_description`.
- No `save()` do form, a atividade é obtida ou criada por nome no projeto (Treebeard, `add_root`), e `instance.activity` é preenchido antes de salvar. Uso de `get_or_create` e tratamento de `IntegrityError` para evitar duplicidade de worklog (activity + diary).

### 2.7 Mão de obra e equipamentos (legado e novo)

- **Novo:** `diary_labor_data` (JSON) preenche `DiaryLaborEntry` (cargos/categorias). Limpa entradas antigas do diário e recria a partir do payload.
- **Legado:** `labor_data` e `equipment_data` (JSON) criam/associam `Labor` e `Equipment` e são vinculados aos worklogs (incluindo worklog padrão “Registro Geral”) quando o formset de worklogs não tem itens mas há mão de obra ou equipamentos. Fluxo coerente.

### 2.8 Ocorrências e tags

- Formset de ocorrências com `save_m2m()` para as tags (M2M). Tags enviadas como múltiplos inputs no template; o backend substitui corretamente (clear + add).

### 2.9 Rollback em caso de erro

- Todo o processamento crítico (diário, formsets, fotos, vídeos, anexos, worklogs, ocorrências, assinaturas) está dentro de `transaction.atomic()`. Qualquer `ValueError` ou exceção não tratada causa rollback. No `except ValueError`, a view recria o form e os formsets com os dados do POST e retorna o render com erros.

---

## 3. Recomendações

1. **Testes automatizados:** Incluir testes para:
   - POST com form principal inválido (ex.: data duplicada) → resposta 200, form re-renderizado com erros e dados do POST.
   - POST com form válido e formset de atividades inválido → resposta 200, mensagem de aviso e formulário de edição do diário com erros do formset.
2. **Logs em produção:** Os `logger.info` do fluxo do diário ajudam no diagnóstico; considerar nível DEBUG em produção apenas onde for necessário.
3. **Diário novo sem PK:** Nos blocos de re-render (form inválido ou formsets com erro), quando o diário é novo (`diary` sem `pk`), os formsets são instanciados com `instance=diary` (None ou instância não persistida). A view já trata isso; manter atenção em futuras alterações para não assumir `diary.pk` em diário novo.

---

## 4. Resumo

| Item | Status |
|------|--------|
| Form inválido → re-render com POST e erros | Corrigido |
| Form válido + formset inválido → re-render com aviso e erros | Corrigido |
| Unicidade projeto + data | OK (form + model) |
| Assinatura obrigatória (não parcial) | OK (dentro da transação) |
| Preservação de FILES e uso em re-render | OK |
| Prefixo work_logs e normalização | OK |
| Worklogs e criação de Activity | OK |
| Mão de obra / equipamentos e worklog padrão | OK |
| Rollback em ValueError | OK |

Documento gerado após revisão lógica do fluxo do diário de obra.

---

## 5. Revisão: salvamento parcial, edição, apagar e lista de relatórios

Revisão focada no dia a dia do engenheiro: rascunho, editar, remover itens e visualização na lista.

### 5.1 Correções aplicadas nesta fase

#### 5.1.1 Status real na lista de relatórios (CORRIGIDO)

**Problema:** Na lista de relatórios (`report_list.html` e `report_list_partial.html`), o status exibido era sempre "Preenchido", independentemente do status real do diário (Rascunho, Preenchido, Em revisão, Aprovado). O engenheiro não conseguia distinguir rascunhos de relatórios finalizados.

**Correção:** Foram criados os template filters `report_status_label` e `report_status_css` em `core/templatetags/core_tags.py`, mapeando `DiaryStatus` para rótulo e classe CSS. Os templates passaram a usar `{{ diary|report_status_label }}` e `{{ diary|report_status_css }}`, exibindo Rascunho (SALVAMENTO_PARCIAL), Preenchido (PREENCHENDO), Em revisão (REVISAR) e Aprovado (APROVADO), com as classes já existentes (`report-status--draft`, `report-status--approved`, `report-status--review`).

#### 5.1.2 Ocorrências marcadas para DELETE na validação (CORRIGIDO)

**Problema:** Na revalidação dos formsets (após o diário ter PK), a lógica que define `has_occurrence_data` não ignorava ocorrências marcadas para exclusão (`occurrences-{i}-DELETE=on`). Isso era inconsistente com o formset de worklogs, que já desconsidera itens com DELETE.

**Correção:** No loop que calcula `has_occurrence_data`, passou a ser verificado `occurrences-{i}-DELETE == 'on'`; quando for o caso, o índice é ignorado (`continue`). Assim, um formulário em que todas as ocorrências foram "removidas" na tela é tratado como sem dados de ocorrência e o formset não é exigido.

### 5.2 Pontos verificados (sem alteração)

- **Salvamento parcial (rascunho):** `is_partial_save` por `partial_save=='1'` ou `as_partial_checkbox=='1'`; status `SALVAMENTO_PARCIAL`; assinatura não exigida; redirect para lista de relatórios. Dados (atividades, ocorrências, fotos, etc.) são persistidos na mesma transação.
- **Edição:** `can_be_edited_by()` no modelo permite edição apenas para o criador quando status é PREENCHENDO ou SALVAMENTO_PARCIAL; a lista usa o filter `can_edit` para mostrar o link "Editar" apenas quando permitido.
- **Remoção de atividades/ocorrências no front:** `removeActivity(index)` e `removeOccurrence(index)` definem o input `-DELETE` com valor `on` (ou marcam o checkbox) e escondem o item; o backend usa o formset com `can_delete=True` e processa os DELETEs no `save()`.
- **Remoção de fotos:** Processamento manual e formset tratam `diaryimage_set-{i}-DELETE`; vídeos usam `video_delete_{id}`; anexos usam `kept_attachment_ids`.
- **Formset de ocorrências:** `DiaryOccurrenceFormSet` com `can_delete=True`; uso de `normalized_post` garante que os DELETEs do POST cheguem ao formset; `save(commit=False)` + `save_m2m()` aplica exclusões e salva tags.

**Ponto de atenção (limitação atual):** No front, a função `editActivity(index)` ainda exibe um alerta informando que a edição de atividade "será implementada em breve" e orienta o usuário a remover e adicionar novamente. A edição de ocorrências (`editOccurrence`) pode ter fluxo completo via modal; para atividades, a edição inline/modal é um aprimoramento futuro.

### 5.3 Resumo desta fase

| Item | Status |
|------|--------|
| Lista de relatórios exibe status real (Rascunho, Preenchido, Em revisão, Aprovado) | Corrigido |
| has_occurrence_data ignora itens com DELETE | Corrigido |
| Rascunho persiste e reaparece na lista como editável | OK |
| Editar restrito por can_be_edited_by e link condicional | OK |
| DELETE de atividades/ocorrências no POST processado pelo formset | OK |

---

## 6. Revisão por etapas (telas e dependências)

Revisão da lógica tela a tela, na ordem das dependências.

### 6.1 Etapa 1 – Seleção de sistema e projeto

- **select_system_view:** Redireciona dono da obra (sem outros acessos) para `client-diary-list`. OK.
- **select_project_view:** POST com `project_id` – tratava apenas `Project.DoesNotExist`. **Correção:** passou a capturar também `ValueError` e `TypeError` (ex.: `project_id` inválido) e re-renderizar com a mesma mensagem "Obra não encontrada ou inativa.".
- **get_selected_project / project_required:** Limpeza de sessão quando projeto inexistente ou inativo; checagem de `_user_can_access_project` antes de acessar views com projeto. OK.

### 6.2 Etapa 2 – Lista de relatórios

- **report_list_view:** Filtros (search, date_start, date_end, status) e ordenação. **Correção:** o select do modal "Adicionar relatório" usava `Project.objects.filter(is_active=True)` (todas as obras). Passou a usar `_get_projects_for_user(request)`, exibindo apenas obras às quais o usuário tem acesso (dono, membro ou staff).
- **Fluxo modal → novo diário:** O formulário do modal envia GET para `diary-new` com `project` e `date`. **Correção:** na view do formulário (GET), quando existem `project` e `date` na query string, o sistema valida acesso ao projeto, atualiza a sessão com essa obra e redireciona para `diary-new` (ou `diary-new?date=...`), garantindo que o formulário abra já na obra escolhida e com a data preenchida.

### 6.3 Etapa 3 – Formulário do diário (novo e edição)

- Fluxo POST (form principal, formsets, salvamento parcial, DELETE) já coberto nas seções 1, 2 e 5. Nesta passagem não foi alterado.

### 6.4 Etapa 4 – Detalhe do diário

- **diary_detail_view:** Projeto da sessão vs. projeto do diário; registro de visualização; contexto com `owner_comments` e `can_add_owner_comment`. OK.
- **Correção:** O badge de status na página de detalhe era fixo "Preenchido". Passou a usar os mesmos filters da lista (`report_status_label` e `report_status_css`), exibindo Rascunho, Preenchido, Em revisão ou Aprovado conforme o status real.

### 6.5 Etapas 5 a 7 – Aprovação, portal cliente, PDF/Excel

- **Aprovar/Rejeitar:** Verificação de projeto e permissão; uso de `WorkflowService`; e-mail ao dono após aprovação com `sent_to_owner_at` e janela de 24h. OK.
- **Portal cliente:** Lista apenas diários aprovados e enviados; detalhe e comentário respeitam `_client_can_access_diary` e `_client_can_comment` (24h). OK.
- **PDF/Excel:** Projeto da sessão e `get_object_or_404(diary, project=project)`. OK.

### 6.6 Resumo das correções desta revisão (seção 6)

| Etapa | Correção |
|-------|----------|
| 1 | Tratamento de `project_id` inválido em `select_project_view` (ValueError, TypeError). |
| 2 | Modal "Adicionar relatório": select apenas com `_get_projects_for_user`. GET `diary-new?project=X&date=Y`: atualiza sessão e redireciona para abrir na obra e data corretas. |
| 4 | Badge de status na página de detalhe do diário passando a usar status real (filters `report_status_label` / `report_status_css`). |

---

## 7. Segunda revisão completa (nova varredura)

Nova passagem em todas as telas e fluxos para identificar mais pontos.

### 7.1 Correções aplicadas

#### 7.1.1 Logout: limpar todos os campos de obra na sessão

**Problema:** Em `logout_view` só era removido `selected_project_id`; `selected_project_name` e `selected_project_code` permaneciam na sessão, podendo vazar entre usuários ou exibir dados residuais na tela de login.

**Correção:** Passou a limpar os três campos com `request.session.pop(key, None)` para `selected_project_id`, `selected_project_name` e `selected_project_code`.

#### 7.1.2 get_selected_project: limpar nome e código ao invalidar projeto

**Problema:** Quando a obra não existia mais ou estava inativa, apenas `selected_project_id` era removido da sessão; nome e código continuavam, deixando a sessão inconsistente.

**Correção:** Ao detectar `Project.DoesNotExist`, a view agora remove da sessão os três campos (`selected_project_id`, `selected_project_name`, `selected_project_code`).

#### 7.1.3 Detalhe do diário com projeto None: checar acesso antes de usar obra do diário

**Problema:** No bloco “se não há projeto na sessão” (ex.: link direto), o código definia a sessão com o projeto do diário sem verificar se o usuário tinha permissão para acessar essa obra, permitindo ver diário de obra alheia.

**Correção:** Antes de atribuir o projeto do diário à sessão, passou a ser chamado `_user_can_access_project(request.user, diary.project)`; em caso negativo é lançado `Http404('Relatório não encontrado.')`.

#### 7.1.4 Redirect para diary-new com data: URL segura

**Problema:** O redirect usava concatenação `'?date=' + get_date`, o que poderia quebrar ou ser inseguro se a data tivesse caracteres especiais.

**Correção:** Uso de `urllib.parse.urlencode({'date': get_date})` para montar a query string e `.strip()` em `get_date` antes de usar.

#### 7.1.5 Exclusão de obra: limpar sessão quando a obra excluída é a selecionada

**Problema:** Ao excluir uma obra (view `project_delete_view`), se essa obra fosse a que estava selecionada na sessão, o usuário continuava com `selected_project_id` (e nome/código) apontando para registro inexistente, podendo gerar erro ou redirecionamento estranho nas próximas requisições.

**Correção:** Após `project.delete()`, verificar se `request.session.get('selected_project_id') == pk` e, em caso positivo, remover da sessão os três campos de obra selecionada.

### 7.2 Resumo da segunda revisão

| Item | Correção |
|------|----------|
| Logout | Limpar `selected_project_id`, `selected_project_name`, `selected_project_code`. |
| get_selected_project (DoesNotExist) | Limpar os três campos da sessão. |
| diary_detail (project None) | Verificar `_user_can_access_project` antes de usar projeto do diário. |
| Redirect diary-new?date= | Usar `urlencode` e trim no parâmetro. |
| project_delete_view | Limpar sessão quando a obra excluída é a selecionada. |

---

## 8. Simulação de usuário (erros e tratamento)

Revisão simulando ações de um usuário cometendo erros (dados inválidos, adulteração, acessos indevidos) para garantir que o sistema trata cada caso.

### 8.1 Correções aplicadas

#### 8.1.1 Formulário do diário: ignorar projeto vindo do POST (adulteração)

**Cenário:** Usuário envia POST com campo `project` alterado (ex.: projeto de outra obra) para tentar criar/editar diário em obra que não deveria.

**Problema:** O form usava `cleaned_data.get('project') or _project`; se o POST trouxesse um projeto válido (outra obra), esse valor era aceito e o diário poderia ser salvo na obra errada.

**Correção:** Em `ConstructionDiaryForm.clean()`, quando o servidor passou `_project` no `__init__`, o projeto do diário passou a ser **sempre** o `_project`; o valor do POST para `project` é ignorado. Assim o diário fica sempre na obra da sessão.

#### 8.1.2 Calendário (calendar_events_view): start/end ausentes ou inválidos

**Cenário:** Requisição sem `start`/`end` ou com valores inválidos (ex.: FullCalendar em falha ou URL manipulada).

**Problema:** No `except (ValueError, AttributeError)` o código fazia `start_date = timezone.now().date()` e `end_date = start_date + timedelta(days=30)` (objetos `date`). Em seguida usava `view_start = start_date.date()` e `view_end = end_date.date()`, o que gerava `AttributeError` porque `date` não tem método `.date()`.

**Correção:** No `except` passou a usar `start_date = timezone.now()` e `end_date = start_date + timedelta(days=30)` (objetos `datetime`), e incluído `TypeError` na exceção. Assim `view_start = start_date.date()` e `view_end = end_date.date()` funcionam em todos os caminhos.

### 8.2 Cenários verificados (comportamento correto, sem alteração)

| Cenário | Tratamento |
|--------|------------|
| Login com credenciais erradas | `authenticate` retorna None → render com `error: 'Credenciais inválidas'`. |
| Acesso a URL protegida sem login | `@login_required` redireciona para login. |
| Acesso com login mas sem obra selecionada | `@project_required` redireciona para seleção de obra. |
| Diário de outra obra (ex.: /diaries/123/ com obra B na sessão) | `get_object_or_404(..., project=project)` ou checagem `diary.project_id != project.id` → 404. |
| GET em rota que exige POST (ex.: /diaries/123/approve/) | `@require_http_methods(["POST"])` → 405. |
| Aprovar/Rejeitar com pk inexistente | `get_object_or_404(ConstructionDiary, pk=pk, project=project)` → 404. |
| Comentário vazio (LPLAN ou dono) | `if not text: messages.error(...); return redirect(...)`. |
| Comentário em diário não aprovado (LPLAN) | `if not diary.is_approved(): messages.error(...); return redirect(...)`. |
| Dono acessa diário de obra que não é dele | `_client_can_access_diary` → 404. |
| Dono comenta fora da janela de 24h | `_client_can_comment` → False → mensagem e redirect. |
| Marcar notificação de outro usuário como lida | `get_object_or_404(Notification, pk=pk, user=request.user)` → 404. |
| Filtros de data inválidos (lista, filtros) | `try/except ValueError` ao aplicar filtro; ignora valor inválido. |
| Paginação com `?page=xyz` | `paginator.get_page(page_number)` trata valor inválido e retorna primeira página. |
| Data futura no formulário do diário | `ConstructionDiaryForm.clean_date()` → ValidationError. |
| Data duplicada (mesmo projeto + data) | `ConstructionDiaryForm.clean()` → ValidationError com mensagem. |
| Seleção de obra com ID inexistente ou inativo | `select_project_view`: except `(DoesNotExist, ValueError, TypeError)` → re-render com erro. |

### 8.3 Resumo da simulação de usuário

| Item | Status |
|------|--------|
| Projeto do diário sempre do servidor (não confiar no POST) | Corrigido (form.clean) |
| Calendário com start/end ausentes ou inválidos | Corrigido (calendar_events_view) |
| Login, auth, projeto, método HTTP, comentários, notificações, filtros, paginação | Verificado (comportamento adequado) |
