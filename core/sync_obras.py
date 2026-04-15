"""
Cadastro canónico de «obra» no produto LPLAN
============================================

**Fonte de verdade:** `core.Project` (Diário de Obra, URL /projects/).

**Réplicas derivadas** (mantidas sincronizadas por esta camada):
  - `gestao_aprovacao.Obra` — GestControll (pedidos, aprovações)
  - `mapa_obras.Obra` — Mapa de Suprimentos (itens, locais, importações Sienge)

A obra do mapa tem `codigo_sienge == project.code` e `obra.project` (OneToOne)
aponta para o projeto quando preenchido pela sincronização. O código continua
necessário para importações Sienge e legado; a FK evita resolver só por string.

Para obras operacionais do produto: criar/editar `Project` e chamar
`sync_project_to_gestao_and_mapa`; não duplicar cadastro só no mapa.
"""
from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)


def sync_project_to_gestao_and_mapa(project, return_result=False):
    """
    Cria ou atualiza a Obra no GestControll e no Mapa para o mesmo Project.
    Chamado após salvar um Project no core.

    Se return_result=True, retorna um dict com chaves 'gestao_ok', 'gestao_error',
    'mapa_ok', 'mapa_error' para uso em telas de manutenção/diagnóstico.
    """
    if not project:
        return {'gestao_ok': False, 'gestao_error': None, 'mapa_ok': False, 'mapa_error': None} if return_result else None

    result = {'gestao_ok': False, 'gestao_error': None, 'mapa_ok': False, 'mapa_error': None}

    # GestControll
    try:
        from gestao_aprovacao.models import Obra
        Obra.objects.update_or_create(
            project=project,
            defaults={
                'codigo': project.code,
                'nome': project.name,
                'ativo': project.is_active,
                'empresa': None,
            },
        )
        result['gestao_ok'] = True
    except Exception as e:
        result['gestao_error'] = str(e)
        logger.exception(
            'Erro ao sincronizar Project %s (id=%s) com GestControll: %s',
            project.code, getattr(project, 'pk', None), e
        )

    # Mapa
    try:
        from mapa_obras.models import Obra as ObraMapa
        ObraMapa.objects.update_or_create(
            codigo_sienge=project.code,
            defaults={
                'nome': project.name,
                'ativa': project.is_active,
                'project_id': project.pk,
                'codigos_sienge_alternativos': getattr(
                    project, 'sienge_codigos_alternativos', ''
                )
                or '',
            },
        )
        result['mapa_ok'] = True
    except Exception as e:
        result['mapa_error'] = str(e)
        logger.exception(
            'Erro ao sincronizar Project %s (id=%s) com Mapa: %s',
            project.code, getattr(project, 'pk', None), e
        )

    return result if return_result else None


def obra_mapa_for_project(project, sync: bool = True):
    """
    Obra do mapa (`mapa_obras.Obra`) para este projeto.

    Ordem: sincroniza se pedido; resolve por FK `project` (preferida) ou por
    `codigo_sienge`; repara FK quando o código coincide mas o vínculo estava vazio.
    """
    if not project or not getattr(project, 'pk', None):
        return None
    if sync:
        sync_project_to_gestao_and_mapa(project)

    from mapa_obras.models import Obra as ObraMapa

    obra = ObraMapa.objects.filter(project_id=project.pk).first()
    if obra is None:
        obra = ObraMapa.objects.filter(codigo_sienge=project.code).first()
    if obra is not None and obra.project_id != project.pk:
        ObraMapa.objects.filter(pk=obra.pk).update(project_id=project.pk)
        obra.project_id = project.pk
    return obra


def get_obra_mapa_for_project_or_404(project, sync: bool = True):
    """Para views: garante instância após sync ou 404."""
    from mapa_obras.models import Obra as ObraMapa

    obra = obra_mapa_for_project(project, sync=sync)
    if obra is not None:
        return obra
    return get_object_or_404(ObraMapa, codigo_sienge=project.code)
