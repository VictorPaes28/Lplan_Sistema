"""
Utilitários para texto vindo de Excel/CSV Sienge antes de persistir no MySQL.
"""
import math
import unicodedata


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
