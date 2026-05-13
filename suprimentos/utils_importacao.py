"""
Utilitários para texto vindo de Excel/CSV Sienge antes de persistir no MySQL.
"""
import math
import unicodedata
from decimal import Decimal


def sanitizar_texto_sienge(s, max_length=None):
    """
    Remove caracteres problemáticos comuns em exportações (Word/Excel), ex.:
    U+0096 (control), soft hyphen, e normaliza Unicode (NFKC) para evitar
    erro MySQL 1366 em colunas com charset restrito ou dados corrompidos.

    Preserva letras acentuadas e símbolos usuais em português (ç, ã, Ø, etc.).
    """
    if s is None:
        return ''
    if isinstance(s, float) and math.isnan(s):
        return ''
    # pandas NA/NaT e afins: em comparação com ele mesmo costuma resultar em "unknown"
    # ou False; se der exceção, segue fluxo normal para string.
    try:
        if s != s:  # NaN-like
            return ''
    except Exception:
        pass
    s = str(s)
    s = ' '.join(s.strip().split())
    if not s:
        return ''
    if s.lower() in ('nan', '<na>', 'none', 'nat'):
        return ''
    s = unicodedata.normalize('NFKC', s)
    out = []
    for ch in s:
        cat = unicodedata.category(ch)
        if cat == 'Cc':
            continue
        o = ord(ch)
        if 0xD800 <= o <= 0xDFFF:
            continue
        out.append(ch)
    s = ''.join(out)
    for old in ('\u2013', '\u2014', '\u2212', '\u00ad'):
        s = s.replace(old, '-')
    s = ' '.join(s.strip().split())
    if max_length is not None:
        s = s[:max_length]
    return s


def consolidar_quantidades_sienge_linhas_csv(valores_por_linha):
    """
    Consolida valores numéricos quando o CSV tem várias linhas para a mesma SC + insumo.

    Usado para qt. solicitada e qt. entregue no grupo consolidado.

    - Padrão Sienge comum: cada linha repete o **mesmo total** → devolve esse valor (não soma).
    - SC parcelada / entregas fracionadas: cada linha tem **parcela diferente** → devolve a **soma**.

    Args:
        valores_por_linha: lista de Decimal (uma entrada por linha incluída no grupo).

    Returns:
        Decimal consolidado ou 0 se a lista estiver vazia.
    """
    if not valores_por_linha:
        return Decimal('0.00')
    primeiro = valores_por_linha[0]
    if all(q == primeiro for q in valores_por_linha):
        return primeiro
    return sum(valores_por_linha, Decimal('0.00'))


def consolidar_quantidade_solicitada_sienge(valores_por_linha):
    """Alias semântico para uso no import MAPA_CONTROLE (qt. solicitada consolidada)."""
    return consolidar_quantidades_sienge_linhas_csv(valores_por_linha)


def consolidar_quantidade_entregue_sienge(valores_por_linha):
    """Mesma heurística da solicitada para qt. entregue no consolidado ``item_sc`` vazio."""
    return consolidar_quantidades_sienge_linhas_csv(valores_por_linha)
