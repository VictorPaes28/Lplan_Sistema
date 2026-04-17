"""
Context processors para disponibilizar dados globais em todos os templates.
"""
from .models import (
    ConstructionDiary,
    DiaryImage,
    Activity,
    DiaryVideo,
    DiaryAttachment,
    DiaryOccurrence,
)


def _get_system_access(user):
    """Retorna has_diario, has_gestao, has_mapa, has_central, has_workflow para o usuário."""
    if not user or not user.is_authenticated:
        return False, False, False, False, False
    from accounts.groups import GRUPOS
    from accounts.painel_sistema_access import user_is_painel_sistema_admin

    user_groups = set(user.groups.values_list('name', flat=True))
    has_diario = user.is_superuser or user.is_staff or GRUPOS.GERENTES in user_groups
    has_gestao = user.is_superuser or user.is_staff or bool(
        user_groups & {GRUPOS.ADMINISTRADOR, GRUPOS.RESPONSAVEL_EMPRESA, GRUPOS.APROVADOR, GRUPOS.SOLICITANTE}
    )
    has_mapa = user.is_superuser or user.is_staff or GRUPOS.ENGENHARIA in user_groups
    has_central = user_is_painel_sistema_admin(user)
    has_workflow = user.is_superuser or user.is_staff or bool(
        user_groups
        & {
            GRUPOS.CENTRAL_APROVACOES_ADMIN,
            GRUPOS.CENTRAL_APROVACOES_APROVADOR,
            GRUPOS.CENTRAL_APROVACOES_EXTERNO,
        }
    )
    return has_diario, has_gestao, has_mapa, has_central, has_workflow


def sidebar_systems(request):
    """
    Disponibiliza has_diario, has_gestao, has_mapa, has_central em todos os templates
    para exibir os links dos sistemas na sidebar.
    """
    if not request.user.is_authenticated:
        return {
            'has_diario': False,
            'has_gestao': False,
            'has_mapa': False,
            'has_central': False,
            'has_workflow': False,
            'can_manage_central_projects': False,
        }
    has_diario, has_gestao, has_mapa, has_central, has_workflow_cp = _get_system_access(request.user)
    from accounts.painel_sistema_access import user_can_central_obras_diario_e_mapa

    return {
        'has_diario': has_diario,
        'has_gestao': has_gestao,
        'has_mapa': has_mapa,
        'has_central': has_central,
        'has_workflow': has_workflow_cp,
        'can_manage_central_projects': user_can_central_obras_diario_e_mapa(request.user),
    }


def sidebar_counters(request):
    """
    Context processor para adicionar contadores da sidebar em todas as páginas.
    """
    # Se não houver projeto selecionado, retorna contadores zerados
    if not request.user.is_authenticated:
        return {
            'total_reports_count': 0,
            'total_photos_count': 0,
            'total_videos_count': 0,
            'total_activities_count': 0,
            'total_occurrences_count': 0,
            'total_comments_count': 0,
            'total_attachments_count': 0,
        }
    
    project_id = request.session.get('selected_project_id')
    
    if not project_id:
        return {
            'total_reports_count': 0,
            'total_photos_count': 0,
            'total_videos_count': 0,
            'total_activities_count': 0,
            'total_occurrences_count': 0,
            'total_comments_count': 0,
            'total_attachments_count': 0,
        }
    
    try:
        # Total de relatórios
        total_reports = ConstructionDiary.objects.filter(project_id=project_id).count()
        
        # Total de fotos
        total_photos = DiaryImage.objects.filter(
            diary__project_id=project_id,
            is_approved_for_report=True
        ).count()
        
        # Total de vídeos
        total_videos = DiaryVideo.objects.filter(
            diary__project_id=project_id
        ).count()
        
        # Total de atividades
        total_activities = Activity.objects.filter(project_id=project_id).count()
        
        # Total de ocorrências (modelo DiaryOccurrence – mesmo do dashboard e aba Ocorrências)
        total_occurrences = DiaryOccurrence.objects.filter(
            diary__project_id=project_id
        ).count()
        
        # Total de comentários (diários com general_notes)
        total_comments = ConstructionDiary.objects.filter(
            project_id=project_id
        ).exclude(general_notes='').exclude(general_notes__isnull=True).count()
        
        # Total de anexos
        total_attachments = DiaryAttachment.objects.filter(
            diary__project_id=project_id
        ).count()
        
        return {
            'total_reports_count': total_reports,
            'total_photos_count': total_photos,
            'total_videos_count': total_videos,
            'total_activities_count': total_activities,
            'total_occurrences_count': total_occurrences,
            'total_comments_count': total_comments,
            'total_attachments_count': total_attachments,
        }
    except Exception:
        # Em caso de erro, retorna contadores zerados
        return {
            'total_reports_count': 0,
            'total_photos_count': 0,
            'total_videos_count': 0,
            'total_activities_count': 0,
            'total_occurrences_count': 0,
            'total_comments_count': 0,
            'total_attachments_count': 0,
        }

