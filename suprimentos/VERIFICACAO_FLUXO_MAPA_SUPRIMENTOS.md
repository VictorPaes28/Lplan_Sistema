# Verificação do fluxo Mapa de Suprimentos (pontos citados pelo GPT)

Este documento confirma onde cada ponto levantado está tratado no código após a junção dos sistemas.

---

## 1. Importação gerando RecebimentoObra para a obra e para a SC

**Onde:** `suprimentos/management/commands/importar_mapa_controle.py`

- **Criação:** `RecebimentoObra.objects.update_or_create(obra=obra, numero_sc=numero_sc, insumo=insumo, item_sc='', defaults={...})` (linhas ~549-567).
- **Condição:** Só cria/atualiza quando `quantidade_solicitada > 0` (linha 548).
- **Resumo no final:** O comando exibe `[NEW] RecebimentoObra criados` e `[UPD] RecebimentoObra atualizados` (linhas ~708-716).
- **Grupos com qtd = 0:** Contador `grupos_sem_qtd_solicitada` e mensagem explicando que esses grupos não geram RecebimentoObra (linhas ~721-726).

**Conclusão:** A importação realmente gera/atualiza RecebimentoObra por (obra, numero_sc, insumo) e o resumo deixa isso explícito.

---

## 2. Linhas ignoradas na importação (código do insumo / formatação Excel)

**Onde:** `importar_mapa_controle.py`

- **Código da obra:** Normalizado com `str(int(float(codigo_obra)))` para "224.0" → "224" (linhas 334-338).
- **Código do insumo:** Normalizado da mesma forma para "15666.0" → "15666" (linhas 356-361).
- **Número da SC:** Normalizado para "85", "085", "85.0" (linhas 312-319).
- **Obras não cadastradas:** Linhas com obra que não existe no banco são ignoradas e listadas em `obras_ignoradas` com aviso (linhas 366-369, 364-369, 358-363).
- **Insumos não encontrados:** Linhas cujo insumo não existe são ignoradas e entram em `insumos_nao_encontrados` com exemplos no log (linhas 364-365, 381-390).
- **Filtro macroelemento:** Com `--incluir-pequenos` desativado, insumos pequenos/cimentos são ignorados (linhas 373-374, 368-372).

**Conclusão:** Formatação numérica (obra, insumo, SC) é normalizada; linhas ignoradas por obra/insumo/filtro são reportadas no resumo e em avisos.

---

## 3. Comparação consistente (código insumo e número da solicitação)

**Onde:** `views_api.py` e `models.py`

- **API – `_normalizar_numero_sc`:** Remove espaços, pontos, hífens; se só dígitos, usa `str(int(s))` (ex.: 085 → 85).
- **API – `_normalizar_codigo_insumo`:** Código numérico vira inteiro em string (ex.: 15666.0 → 15666).
- **`_aplicar_dados_recebimento_obra`:** Busca RecebimentoObra por obra e filtra em Python por `numero_sc` e `codigo_insumo` normalizados (views_api, linhas ~31-62).
- **Bloco `numero_sc` em `item_atualizar_campo`:** Usa a mesma comparação por código normalizado (views_api, linhas ~632-638).
- **Modelo – `recebimento_vinculado`:** Usa `_normalizar_numero_sc_model` e `_normalizar_codigo_insumo_model` para comparar SC e código do insumo (models.py, linhas ~468-502).

**Conclusão:** Código do insumo e número da solicitação são sempre comparados em formato normalizado (obra, SC e insumo), evitando falhas por diferença de formatação.

---

## 4. Obra na sessão ao editar/salvar

**Onde:** `views_api.py` – `item_atualizar_campo`

- **Verificação:** `obra_sessao_id = request.session.get('obra_id')` (linha 384).
- **Sem obra na sessão:** Retorna 403 com mensagem: "Selecione uma obra no dropdown do Mapa (canto superior) e recarregue a página antes de editar." (linhas 386-390).
- **Obra diferente do item:** Se `int(obra_sessao_id) != item.obra_id`, retorna 403: "Sem permissão para editar itens desta obra." (linhas 392-395).
- **Outras views (detalhe, excluir, alocar):** Também validam obra da sessão quando aplicável (linhas 107, 294, 343, 791).

**Conclusão:** A API exige obra na sessão e que seja a mesma do item; sem isso, não permite editar/salvar e retorna erro claro.

---

## 5. Erros não descartados silenciosamente (import e vínculo)

**Import – `importar_mapa_controle.py`:**

- Exceções no loop por grupo são capturadas, mensagem em `erros.append(erro_msg)` e escrita com `self.stdout.write(self.style.ERROR(...))` (linhas 700-703).
- No final, exibe até 10 erros com `self.stdout.write(self.style.WARNING(...))` (linhas 728-731).
- Nenhum `except: pass` que esconda o erro.

**Vínculo (API – `item_atualizar_campo`):**

- No bloco de atualização ao editar `numero_sc`, exceções são logadas com `logger.warning(...)` e a atualização do SC segue (linhas 690-694).
- O restante da view está em `try/except` que retorna `JsonResponse` com `error: str(e)` (linhas 775-776), não engole o erro.

**Conclusão:** Import e vínculo não descartam erros silenciosamente; erros são mostrados no terminal (import) ou devolvidos na resposta JSON (API).

---

## 6. RecebimentoObra criado no import e vínculo ao preencher código + SC

**Criação no import:**  
Vide item 1: o comando cria/atualiza RecebimentoObra por (obra, numero_sc, insumo) quando `quantidade_solicitada > 0`.

**Vínculo ao preencher código e SC:**

- Ao editar **código do insumo:** após setar `item.insumo`, chama `_aplicar_dados_recebimento_obra(item)` (views_api, linha ~516). Se existir RecebimentoObra para (obra, numero_sc normalizado, código insumo normalizado), preenche PC, prazo, empresa, quantidades.
- Ao editar **Nº Solicitação:** normaliza `numero_sc`, busca RecebimentoObra por obra + numero_sc + código insumo (normalizados) e aplica os mesmos dados (views_api, linhas ~615-686).
- **Front:** Se a API retornar `filled_from_sienge: true`, a página recarrega para exibir os campos preenchidos (supplymap.js).
- **Quando não encontra:** A API retorna `debug_no_recebimento: true` e o front exibe: "Nenhum recebimento do Sienge para esta obra + SC + insumo. Reimporte o MAPA_CONTROLE com a obra correta ou confira em Admin > Recebimentos na Obra."

**Conclusão:** O fluxo está implementado: import gera RecebimentoObra; ao preencher código e SC na tela, a API busca por obra + SC + insumo (normalizados) e, se achar, preenche e sinaliza para o front recarregar; se não achar, informa o usuário.

---

## Resumo

| Ponto do GPT | Status no código |
|--------------|------------------|
| Import gera RecebimentoObra para obra e SC | Sim; resumo mostra criados/atualizados; grupos com qtd=0 contados e explicados |
| Linhas ignoradas (formatação/código) | Sim; obra/insumo/SC normalizados; obras e insumos não encontrados reportados |
| Comparação consistente (código + SC) | Sim; normalização em import, API e modelo |
| Obra na sessão ao editar | Sim; obrigatória e validada; 403 com mensagem clara se faltar ou for outra obra |
| Erros não silenciosos | Sim; import escreve erros no stdout; API retorna erro em JSON ou loga e continua onde for o caso |
| RecebimentoObra criado e vínculo ao preencher | Sim; criação no import; vínculo em _aplicar_dados_recebimento_obra e no bloco numero_sc; front recarrega quando filled_from_sienge |

Todos os pontos citados estão cobertos no código atual. Se algo ainda falhar na prática, o resumo do import e a mensagem "Nenhum recebimento do Sienge..." (com a dica de reimportar/Admin) indicam o próximo passo para diagnóstico.
