# Varredura completa – Backend do Diário de Obra

**Data:** 2025  
**Escopo:** `core/frontend_views.py` (diary_form_view), `core/forms.py`, `core/models.py`

---

## 1. Fluxo da view (POST)

1. **Primeira criação dos formsets** (antes de `form.is_valid()`): apenas para log/validação inicial; os que importam para salvar são os criados depois com `normalized_post`.
2. **`form.is_valid()`** – se falhar, vai para o bloco “Form principal inválido” (re-render com erros).
3. **Se válido:** `diary = form.save(commit=False)` → monta `normalized_post` (cópia do POST + normalizações) → cria formsets com `normalized_post` → entra em `transaction.atomic()` → `diary.save()` → recria formsets com `normalized_post` e `diary` com PK → valida formsets → salva image_formset, worklog_formset, occurrence_formset (e ocorrências com `created_by = request.user`).

**Conclusão:** A ordem está correta; não há sobrescrita indevida de `normalized_post` nem uso dos formsets “antigos” no lugar dos que são salvos.

---

## 2. Formulários e formsets

- **ConstructionDiaryForm:** campo `date` com `input_formats=['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']`; demais campos e `clean` consistentes.
- **DailyWorkLogFormSet:** sem prefixo na factory; a view passa sempre `prefix='work_logs'`.
- **DiaryOccurrenceFormSet:** sem prefixo na factory; a view passa sempre `prefix='ocorrencias'`.

---

## 3. Modelos

- **ConstructionDiary** → `work_logs` (related_name de DailyWorkLog) e `occurrences` (related_name de DiaryOccurrence).
- **DailyWorkLog:** FK para ConstructionDiary e Activity; formulário trata `activity_description` e cria/busca Activity.
- **DiaryOccurrence:** FK para ConstructionDiary e **created_by** (User, obrigatório); a view atribui `created_by = request.user` antes do `save()` em novas ocorrências.

---

## 4. Problemas encontrados e correções aplicadas

### 4.1 Bloco “Form principal inválido” (re-render com erros)

- **Problema:**  
  - `occurrence_formset` era construído com `request.POST` em vez de `normalized_post`.  
  - Se o cliente enviasse `occurrences-*`, o formset (que espera `ocorrencias-*`) não via os dados.  
  - Nesse bloco, `normalized_post` só tinha normalização `dailyworklog_set` → `work_logs`; faltava `occurrences` → `ocorrencias`.

- **Correção:**  
  - Incluída a normalização `occurrences-*` → `ocorrencias-*` em `normalized_post` nesse bloco.  
  - `occurrence_formset` passou a ser construído com `normalized_post` (e `instance=diary`, `prefix='ocorrencias'`).

### 4.2 Ramo GET (formulário vazio ou edição)

- **Problema:**  
  - `DailyWorkLogFormSet` era criado sem `prefix='work_logs'` (com diary e sem diary).  
  - O template/JS usam sempre o prefixo `work_logs`; o management form renderizado no GET ficava com outro prefixo (ex.: padrão do Django), gerando divergência no primeiro submit.

- **Correção:**  
  - Passado `prefix='work_logs'` em ambas as chamadas de `DailyWorkLogFormSet` no GET:  
    `DailyWorkLogFormSet(instance=diary, form_kwargs={'diary': diary}, prefix='work_logs')` e  
    `DailyWorkLogFormSet(form_kwargs={'diary': None}, prefix='work_logs')`.

---

## 5. Consistência após as correções

| Situação                         | work_logs data     | ocorrencias data   | prefix work_logs | prefix ocorrencias |
|---------------------------------|--------------------|--------------------|------------------|--------------------|
| Primeiro POST (antes validar)   | request.POST       | _post_occ          | sim              | sim                |
| Dentro do fluxo principal       | normalized_post    | normalized_post    | sim              | sim                |
| Re-render (form inválido)       | normalized_post    | normalized_post    | sim              | sim                |
| Re-render (ValueError/Exception)| normalized_post    | normalized_post    | sim              | sim                |
| Re-render (formset falhou)      | normalized_post    | normalized_post    | sim              | sim                |
| GET (com/sem diary)             | —                  | —                  | sim              | sim                |

Não há mais uso de `request.POST` para o formset de ocorrências em re-renders, e não há mais branch sem `prefix='work_logs'` para o formset de atividades.

---

## 6. Recomendações

- Manter sempre `prefix='work_logs'` e `prefix='ocorrencias'` em qualquer novo uso desses formsets na mesma view.
- Em qualquer novo bloco que monte `normalized_post` para re-render, repetir as mesmas normalizações: `dailyworklog_set` → `work_logs` e `occurrences` → `ocorrencias` quando aplicável.
- Os logs `[DIARY_DEBUG]` podem ser removidos ou reduzidos em produção após confirmação de que o fluxo está estável.
