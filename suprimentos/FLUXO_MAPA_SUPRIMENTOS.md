# Fluxo do Mapa de Suprimentos (Sienge → SC → Vinculação)

**Escopo atual:** tudo é **semi-automático**. Não há uso de API externa (ex.: Sienge API, webhooks de terceiros). O fluxo é: usuário exporta do Sienge → envia arquivo (CSV/Excel) → sistema importa e atualiza; edições no mapa são manuais (formulários e salvamento na própria tela).

---

## Ordem correta das etapas

1. **Cadastrar insumos** (se ainda não existirem)  
   - Em **Engenharia → Mapa** ou no modal "Criar Insumo": código Sienge, descrição, unidade.  
   - Insumos com código provisório `SM-LEV-*` criados no Levantamento podem ser reconciliados na importação (pela descrição).

2. **Criar itens no mapa (Levantamento)**  
   - **Engenharia → Mapa** → selecionar **obra** no dropdown → **Novo Levantamento**: insumo, local, categoria, quantidade etc.  
   - Esses itens ainda **não têm SC**; o código do insumo deve ser o que virá no arquivo do Sienge (ou será atualizado na importação).

3. **Importar arquivo do Sienge**  
   - **Engenharia → Importar** → enviar arquivo **CSV ou XLSX** exportado do Sienge (mapa de controle).  
   - O sistema cria/atualiza **RecebimentoObra** (SC, insumo, quantidades, PC, prazo).  
   - Em seguida, **atualiza os ItemMapa** que já existem e batem por (obra + insumo + mesmo número de SC ou SC vazia): preenche Nº SC, Nº PC, quantidades, prazos, empresa.  
   - **Não cria** ItemMapa novo na importação; só vincula/atualiza itens já criados no passo 2.

4. **Editar no mapa (se precisar)**  
   - No Mapa, é possível editar **Nº SC**, **Código do Insumo**, local, prioridade etc.  
   - Ao preencher o Nº SC, o backend pode vincular ao **RecebimentoObra** correspondente (mesma obra + SC + insumo) e atualizar PC, prazo, quantidades.

## Sobre o arquivo do Sienge

- **Formatos aceitos:** CSV (separador `;`) ou XLSX/XLS.  
- **Não é aceito:** PDF. O sistema não extrai tabelas de PDF; é preciso exportar do Sienge em **CSV** ou **Excel** e importar esse arquivo.  
- Colunas esperadas (nomes podem variar): Nº da SC, Cód. Obra, Cód. Insumo, Descrição do Insumo, Quantidade Solicitada, Quantidade Entregue, Nº do PC, Previsão de Entrega, Fornecedor etc.

## Se “não está sendo atualizado” ou “não consigo inserir dados”

- **Selecione a obra** no dropdown do Mapa (canto superior) antes de editar ou criar itens. A sessão guarda a obra; sem ela, a API bloqueia com “Selecione uma obra no Mapa de Suprimentos antes de editar.”  
- **Recarregue a página** (F5 ou Ctrl+F5) após trocar de obra, para garantir que o token de segurança e a sessão estejam corretos.  
- **Importação:** só atualiza itens que já existem no mapa com o **mesmo insumo** (e mesma obra). Crie antes os itens no Levantamento com o código/descrição do insumo que vem no arquivo; depois importe.  
- No **servidor (produção)**: verifique se o cookie de sessão está sendo enviado (mesmo domínio, HTTPS, configuração de cookies). Se estiver em outro domínio/subdomínio, pode ser necessário ajustar `SESSION_COOKIE_DOMAIN` e `CSRF_TRUSTED_ORIGINS`.

## Preenchimento manual dos campos (está certo?)

- **Backend:** a API valida obra na sessão, campos permitidos, local pertence à obra, quantidade não negativa, categoria na lista fechada. Mensagens de erro são devolvidas em JSON e exibidas no front.
- **Front:** cada campo editável dispara POST ao sair do campo (blur) ou ao mudar (select). Só envia se o valor **mudou** (evita requisições desnecessárias). CSRF no header; em caso de sessão inválida ou obra não selecionada, a mensagem do backend é mostrada.
- **Recomendação:** selecione sempre uma obra no filtro antes de editar; se aparecer o aviso "Selecione uma obra no filtro acima...", selecione a obra e recarregue se precisar.

