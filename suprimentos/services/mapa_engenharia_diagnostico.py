"""
Diagnóstico na tela do Mapa de Suprimentos (sem assumir causa: import, cadastro ou vínculo).
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from suprimentos.models import ImportacaoSienge, RecebimentoObra


def descricao_visivel_item(item) -> str:
    override = (getattr(item, 'descricao_override', None) or '').strip()
    if override:
        return override
    insumo = getattr(item, 'insumo', None)
    if insumo:
        return (insumo.descricao or '').strip()
    return ''


def diagnostico_vinculo_sienge_item(item) -> dict:
    """
    Explica por que a coluna «Quantitativo (SC)» está vazia ou preenchida.
    Retorno: nivel (ok|info|aviso), mensagem, badge (texto curto).
    """
    insumo = getattr(item, 'insumo', None)
    cod = (insumo.codigo_sienge if insumo else '') or ''
    cod = str(cod).strip()
    sc = (item.numero_sc or '').strip()

    try:
        qtd_sienge = item.quantidade_solicitada_sienge or Decimal('0')
    except Exception:
        qtd_sienge = Decimal('0')
    if qtd_sienge > 0:
        return {
            'nivel': 'ok',
            'mensagem': '',
            'badge': 'Sienge',
        }

    if not sc:
        return {
            'nivel': 'info',
            'mensagem': 'Sem SC: o quantitativo do Sienge aparece depois de criar a solicitação, importar o mapa e informar a SC nesta linha.',
            'badge': 'Levantamento',
        }

    if not cod or cod.startswith('SM-LEV-'):
        return {
            'nivel': 'aviso',
            'mensagem': f'SC {sc}: informe o código do insumo (coluna 2) para vincular à linha importada do Sienge.',
            'badge': 'Sem código',
        }

    try:
        rec = item.recebimento_vinculado
    except Exception:
        rec = None

    if not rec:
        return {
            'nivel': 'aviso',
            'mensagem': (
                f'SC {sc} + código {cod}: nenhum recebimento nesta obra. '
                'Importe o MAPA do Sienge (menu Importar) ou confira SC/código no arquivo.'
            ),
            'badge': 'Sem vínculo',
        }

    try:
        q_sol = rec.quantidade_solicitada or Decimal('0')
    except Exception:
        q_sol = Decimal('0')
    if q_sol <= 0:
        return {
            'nivel': 'aviso',
            'mensagem': f'Linha Sienge encontrada (SC {sc}), mas quantidade solicitada está zerada no import.',
            'badge': 'Sienge zerado',
        }

    return {
        'nivel': 'aviso',
        'mensagem': (
            f'SC {sc} + código {cod}: há dados no Sienge, mas o quantitativo não apareceu. '
            'Salve novamente a SC ou o código; se persistir, reimporte o mapa.'
        ),
        'badge': 'Rever vínculo',
    }


def anexar_diagnostico_sienge_itens(itens_list) -> None:
    for item in itens_list:
        item.sienge_diagnostico = diagnostico_vinculo_sienge_item(item)


def build_ultima_importacao_info(obra_id) -> dict | None:
    if not obra_id:
        return None
    ultima = (
        ImportacaoSienge.objects.filter(obra_id=obra_id)
        .select_related('usuario')
        .order_by('-created_at')
        .first()
    )
    if not ultima:
        return {
            'tem_importacao': False,
            'recebimentos_obra': RecebimentoObra.objects.filter(obra_id=obra_id).count(),
        }
    usuario = ''
    if ultima.usuario_id:
        u = ultima.usuario
        usuario = (u.get_full_name() or u.username or '').strip()
    return {
        'tem_importacao': True,
        'created_at': ultima.created_at,
        'nome_arquivo': ultima.nome_arquivo,
        'usuario': usuario,
        'recebimentos_obra': RecebimentoObra.objects.filter(obra_id=obra_id).count(),
    }


def alertas_codigo_descricao_duplicada(itens_list) -> list[str]:
    """
    Mesmo código Sienge com descrições diferentes na mesma lista (possível uso incorreto do código).
    """
    por_codigo: dict[str, set[str]] = defaultdict(set)
    for item in itens_list:
        insumo = getattr(item, 'insumo', None)
        if not insumo:
            continue
        cod = (insumo.codigo_sienge or '').strip()
        if not cod or cod.startswith('SM-LEV-'):
            continue
        desc = descricao_visivel_item(item)
        if desc:
            por_codigo[cod].add(desc)

    alertas = []
    for cod, descricoes in sorted(por_codigo.items()):
        if len(descricoes) > 1:
            amostra = '; '.join(sorted(descricoes)[:4])
            extra = f' (+{len(descricoes) - 4})' if len(descricoes) > 4 else ''
            alertas.append(
                f'Código {cod} aparece com descrições diferentes na planilha ({amostra}{extra}). '
                'No Sienge, um código corresponde a um produto — confira se o cadastro está correto.'
            )
    return alertas
