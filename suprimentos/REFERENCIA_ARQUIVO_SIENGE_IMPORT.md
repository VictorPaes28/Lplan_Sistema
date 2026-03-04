# Referência: formato do arquivo Sienge para importação

Este documento descreve **exatamente** o que o sistema espera do arquivo exportado do Sienge (Mapa de Controle). Use para conferir com um arquivo real antes de confiar 100% na importação.

---

## 1. Formatos aceitos

| Formato | Aceito? | Observação |
|--------|---------|------------|
| **CSV** (separador `;`) | Sim | Cabeçalho na **primeira linha** (ou use `--skiprows` no comando). |
| **XLSX** (Excel 2007+) | Sim | Cabeçalho **detectado automaticamente** (pode estar em qualquer linha até ~120). Requer `openpyxl`. |
| **XLS** (Excel 97–2003) | Sim no formulário | Leitura depende do pandas; pode exigir `xlrd` para .xls. Em dúvida, exporte como **XLSX** ou **CSV**. |
| **PDF** | Não | Não é suportado. Exporte do Sienge em CSV ou Excel. |

---

## 2. Colunas reconhecidas (nomes que o sistema procura)

O sistema **normaliza** os nomes das colunas (maiúsculas, sem alterar acentos) e aceita **várias variações** para cada campo. Abaixo está o mapeamento usado no comando `importar_mapa_controle` (e na conversão Excel→CSV).

### Obrigatórias para importar

- **Nº da SC** (número da solicitação de compra)  
  Variações: `Nº DA SC`, `N DA SC`, `NUMERO SC`, `NUMERO_DA_SC`, `SC`, `NSC`, `N. DA SC`, `N. SC`

- **Cód. Insumo** (código do insumo no Sienge)  
  Variações: `CÓD. INSUMO`, `COD INSUMO`, `CODIGO INSUMO`, `CODIGO_DO_INSUMO`, `COD_INSUMO`, `CÓD INSUMO`

### Recomendadas (segregação por obra e dados completos)

- **Cód. Obra** (código da obra no Sienge)  
  Variações: `CÓD. OBRA`, `COD OBRA`, `CODIGO OBRA`, `CODIGO_DA_OBRA`, `COD_OBRA`, `OBRA`, `CÓD OBRA`  
  Se não existir, é obrigatório informar a obra no sistema (ex.: selecionar uma obra antes) ou usar parâmetro `--obra-codigo` no comando.

### Opcionais (enriquecimento)

- **Descrição do Insumo**: `DESCRIÇÃO DO INSUMO`, `DESCRICAO DO INSUMO`, `DESCRIÇÃO`, `DESCRICAO`, `DESC INSUMO`, `DESC. INSUMO`
- **Qt. Solicitada**: `QT. SOLICITADA`, `QT SOLICITADA`, `QUANTIDADE SOLICITADA`, `QTD SOLICITADA`, etc.
- **Quant. Entregue**: `QUANT. ENTREGUE`, `QUANT ENTREGUE`, `QTD ENTREGUE`, `QUANTIDADE ENTREGUE`, etc.
- **Nº do PC**: `Nº DO PC`, `N DO PC`, `NUMERO PC`, `NUMERO_DO_PC`, `PC`, `NPC`, etc.
- **Previsão de Entrega**: `PREVISÃO DE ENTREGA`, `PREVISAO DE ENTREGA`, `PRAZO ENTREGA`, `PRAZO_RECEBIMENTO`, etc.
- **Saldo a Entregar**: `SALDO`, `SALDO A ENTREGAR`, `SALDO_A_ENTREGAR`, `SALDO ENTREGAR`
- **Data da SC**, **Data da NF**, **Data Emissão do PC**, **Fornecedor/Empresa**, **Nº da NF**, etc. (várias variações por campo)

---

## 3. Como o sistema encontra o cabeçalho no Excel (XLSX/XLS)

1. Lê a planilha **sem** considerar a primeira linha como cabeçalho (`header=None`).
2. Percorre as **primeiras 120 linhas** procurando uma linha que contenha:
   - ao menos um nome de coluna de **SC** (ex.: "Nº DA SC", "NUMERO SC") **e**
   - ao menos um nome de coluna de **Insumo** (ex.: "CÓD. INSUMO", "CODIGO INSUMO").
3. Se achar, essa linha é tratada como **cabeçalho**; as linhas abaixo são os dados.
4. Se houver **várias abas**, o sistema escolhe a aba que tiver **mais linhas** com SC preenchida (após aplicar as regras abaixo).

Ou seja: **títulos e subtítulos** acima do cabeçalho são ignorados; apenas a primeira linha que “parece” cabeçalho (SC + Insumo) é usada.

---

## 4. Células “mescladas” / linhas de continuação (forward-fill)

No Excel, quando a mesma **SC** (ou **Obra**, **Insumo**, **Item**) se repete em várias linhas, o Sienge às vezes deixa só a primeira célula preenchida (células “mescladas” visualmente). O sistema faz **forward-fill** nas colunas:

- **Nº DA SC**
- **Cód. Obra**
- **Cód. Insumo**
- **Item** (se existir: N. ITEM, NUMERO ITEM, etc.)

Assim, uma linha com SC e Obra em branco recebe os valores da linha anterior. Isso é aplicado **antes** de gerar o CSV interno; o comando de importação recebe já com essas colunas preenchidas.

---

## 5. CSV gerado a partir do Excel

O fluxo é:

1. Detectar aba e linha do cabeçalho.
2. Aplicar forward-fill nas colunas acima.
3. Remover linhas que forem “repetição de cabeçalho” no meio do arquivo (linha em que o valor da coluna SC está entre os nomes de cabeçalho de SC).
4. Converter para **CSV** com separador `;`, encoding `utf-8-sig`, e enviar para o mesmo comando que processa CSV.

Ou seja: **a lógica de colunas e linhas** é a mesma do CSV; o Excel só muda a forma de achar o cabeçalho e de preencher células vazias (forward-fill).

---

## 6. Número da SC e código da Obra no banco

- **SC**: O comando **normaliza** o número da SC ao processar: remove espaços, pontos, hífens e underscores. Ex.: `SC-2026-001` vira `SC2026001` no banco. Isso evita duplicar recebimentos por diferença de formatação.
- **Obra**: O código da obra é **normalizado** na busca: aceita tanto `224` quanto `0224` (zeros à esquerda). Cadastre a obra em Mapa de Obras com o código Sienge como no arquivo (ex.: `224`, `242`, `259`). Se todas as linhas forem de obras não cadastradas, o resultado será "Grupos únicos processados: 0".

---

## 7. O que **não** foi validado com arquivo real

- **Não tivemos em mãos** um export real do Sienge (XLS/XLSX/CSV) durante a revisão. O comportamento foi garantido por:
  - testes automatizados com um XLSX **sintético** (cabeçalho na 3ª linha, 3 linhas de dados, uma com SC/Obra em branco);
  - e pelo código já existente em `importar_mapa_controle` e em `views_engenharia` (detecção de cabeçalho e forward-fill).

Recomendação: **exporte um arquivo real** do Sienge (XLSX ou CSV), faça uma importação de teste e confira:

1. A mensagem na tela: *"Excel detectado: aba X, header na linha Y. Linhas lidas: Z"* (ou equivalente para CSV).
2. Se as colunas listadas no log do comando batem com o que você vê no arquivo (obra, SC, insumo, PC, etc.).
3. Se o número de linhas/registros importados faz sentido (sem sumir linhas nem duplicar de forma estranha).

Se o arquivo real tiver **nomes de coluna diferentes** (ex.: “Nº Solicitação” em vez de “Nº DA SC”), basta incluir essa variante na lista do campo correspondente em `importar_mapa_controle.py` (`col_mapping`) e, se for usado no Excel, em `views_engenharia.py` (`sc_headers`, `obra_headers`, `insumo_headers`). Não é preciso mudar a lógica de linhas/colunas; só acrescentar mais um nome possível por campo.

---

## 8. Resumo rápido para conferência

| Item | Esperado |
|------|----------|
| **Títulos/subtítulos** | Podem existir acima do cabeçalho; o sistema procura a primeira linha que tenha SC + Insumo. |
| **Número da obra** | Coluna “Cód. Obra” (ou variação); se não houver, obra tem que ser definida de outra forma. |
| **Código do insumo** | Coluna “Cód. Insumo” (ou variação); obrigatório para criar recebimento. |
| **SC** | Coluna “Nº DA SC” (ou variação); obrigatória. |
| **PC** | Coluna “Nº do PC” (ou variação); opcional. |
| **Linhas com SC/Obra em branco** | Preenchidas pela linha anterior (forward-fill) antes de importar. |
| **.xls** | Aceito no formulário; leitura pode exigir `xlrd`. Preferir **.xlsx** ou **CSV** para evitar surpresas. |

Com isso você pode abrir o arquivo do Sienge, conferir linhas e colunas contra esta referência e, se algo não bater, ajustar só os nomes de coluna (ou nos avisar o nome exato que o Sienge exporta) sem “ferrar” o resto do sistema.
