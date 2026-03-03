"""
Sincroniza core.Project com GestControll (Obra) e Mapa (Obra).
Ao criar/editar uma obra no central (core), as mesmas obras ficam disponíveis nos outros sistemas.
"""
import logging

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
