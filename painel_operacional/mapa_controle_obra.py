"""Regras de negócio do Mapa de Controle por obra (ambiente operacional)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from painel_operacional.models import AmbienteOperacional, AmbienteTipo, AmbienteVersao, VersaoEstado

if TYPE_CHECKING:
    from mapa_obras.models import Obra


def mapa_controle_ativos_qs(obra_id: int):
    return AmbienteOperacional.objects.filter(
        obra_id=obra_id,
        tipo=AmbienteTipo.MAPA_CONTROLE,
        ativo=True,
    )


def obra_ja_tem_mapa_controle(obra_id: int) -> bool:
    return mapa_controle_ativos_qs(obra_id).exists()


def versao_layout_atual(ambiente: AmbienteOperacional) -> AmbienteVersao | None:
    """
    Versão persistida do ambiente.

    O estado ``draft`` no banco é legado de nomenclatura: o fluxo atual é
    salvar direto no servidor (``api_salvar_rascunho``); publicação está desativada.
    """
    versao = ambiente.versoes.filter(estado=VersaoEstado.DRAFT).order_by("-numero").first()
    if versao:
        return versao
    return ambiente.versoes.filter(estado=VersaoEstado.PUBLISHED).order_by("-numero").first()


def resolver_mapa_controle_obra(obra: Obra | int) -> AmbienteOperacional | None:
    """
    Mapa de controle usado por consumidores automáticos (BI, integrações).

    Obras com mais de um mapa ativo (legado) mantêm a regra anterior:
    o ambiente com ``updated_at`` mais recente. Ambientes abertos na ferramenta
    continuam endereçados pelo ``id`` explícito.
    """
    obra_id = obra.id if hasattr(obra, "id") else int(obra)
    return mapa_controle_ativos_qs(obra_id).order_by("-updated_at", "-id").first()
