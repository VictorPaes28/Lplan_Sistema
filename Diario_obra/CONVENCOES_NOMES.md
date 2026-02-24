# Convenções de nomes – Diário de Obra

Documento único de referência para nomes usados no sistema. **Use sempre os mesmos nomes em todo o código** (views, templates, JS, formsets, POST).

---

## 1. Ocorrências (interrupções / ocorrências do dia)

| Onde | Nome a usar |
|------|----------------|
| **Formset prefix e chaves POST** | `ocorrencias` |
| **Exemplos** | `ocorrencias-TOTAL_FORMS`, `ocorrencias-0-description`, `ocorrencias-0-DELETE`, `ocorrencias-0-id` |
| **IDs/classes no HTML/JS** | `ocorrencias-formset-container`, `ocorrencias-count-display`, `ocorrencias-empty-message`, `ocorrencia-item` |
| **Parâmetro “copiar de relatório”** | `ocorrencias` (ex.: `?copy_from=123&copy=climate,ocorrencias`) |
| **Label na interface** | **Ocorrências** |
| **Modelo Django** | `DiaryOccurrence` (related_name no `ConstructionDiary`: `occurrences` – não alterar, é do ORM) |

**Importante:** O formset deve ser instanciado sempre com `prefix='ocorrencias'` em `frontend_views.py`. O JavaScript no template usa `occPrefix = 'ocorrencias'` e monta os nomes dos inputs com esse prefixo.

---

## 2. Atividades executadas (Fiscalizações e DDS)

**Não usar o termo “Eventos” na interface.** O termo correto é **Atividades executadas**.

| Onde | Nome a usar |
|------|----------------|
| **Seção na tela de detalhe e no formulário** | **Atividades executadas** |
| **Subcampos** | **Fiscalizações** (campo `inspections`) e **DDS (Discurso Diário de Segurança)** (campo `dds`) |
| **Modelo** | `ConstructionDiary.inspections`, `ConstructionDiary.dds` (nomes do banco – não alterar sem migração) |
| **Form** | `ConstructionDiaryForm`: campos `inspections` e `dds` |

Mensagem quando não há registro: *“Nenhuma atividade executada registrada para este dia”*.

---

## 3. Resumo rápido

- **Ocorrências:** prefix/chaves POST/IDs/JS = `ocorrencias`; label = **Ocorrências**.
- **Fiscalizações + DDS:** seção e conceito = **Atividades executadas**; não usar **Eventos**.

Manter essa padronização evita bugs de “não salva” e deixa o código organizado para crescimento do sistema.
