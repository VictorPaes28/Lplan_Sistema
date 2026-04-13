"""
Regras compartilhadas para casar ItemMapa ↔ RecebimentoObra (import Sienge).

Usado em views_api (salvar SC/código) e no modelo ItemMapa.recebimento_vinculado.
Manter uma única implementação evita divergência e bugs sutis.

IMPORTANTE — não confundir com a importação do MAPA_CONTROLE:
- Várias linhas no Excel para o mesmo (obra, SC, insumo), quantidade em modo MÁXIMO
  (não somar linhas repetidas), pedido dividido em blocos no mapa, etc.:
  tudo isso é tratado em ``importar_mapa_controle`` e nos modelos de alocação.
- Este módulo só decide como um **ItemMapa** (levantamento) encontra **linhas já
  importadas** em RecebimentoObra, em especial quando o item ainda usa código
  provisório SM-LEV-* e o Sienge traz código numérico.
- Não altera quantidades importadas nem regras de negócio do CSV.
"""
import re


def descricao_item_compativel(alvo: str, receb_desc: str) -> bool:
    """
    Casa descrição do levantamento com descricao_item vinda do MAPA/Sienge.

    Ordem: igualdade (normalizada) → igualdade sem pontuação → substring em textos longos.
    Substring só com ambos >= 10 caracteres após normalizar, para evitar falso positivo.
    """
    a = (alvo or '').strip()
    b = (receb_desc or '').strip()
    if not a or not b:
        return False
    ca = ' '.join(a.split()).lower()
    cb = ' '.join(b.split()).lower()
    if ca == cb:
        return True
    ca2 = re.sub(r'[\s.,;:\-_/]+', ' ', ca).strip()
    cb2 = re.sub(r'[\s.,;:\-_/]+', ' ', cb).strip()
    if ca2 == cb2:
        return True
    if len(ca2) >= 10 and len(cb2) >= 10:
        if ca2 in cb2 or cb2 in ca2:
            return True
    return False
