"""
Context processors para disponibilizar dados globais em todos os templates.
"""
from django.conf import settings

from .models import (
    ConstructionDiary,
    DiaryImage,
    Activity,
    DiaryVideo,
    DiaryAttachment,
    DiaryOccurrence,
)


def _get_system_access(user):
    """Flags usados no seletor de sistema e na sidebar (exceto granularidade engenharia via _engenharia_groups)."""
    if not user or not user.is_authenticated:
        return False, False, False, False, False, False, False
    from accounts.groups import GRUPOS, usuario_tem_administracao_global_na_plataforma
    from accounts.painel_sistema_access import user_is_painel_sistema_admin

    user_groups = set(user.groups.values_list('name', flat=True))
    adminish = user.is_superuser or user.is_staff
    has_diario = adminish or GRUPOS.GERENTES in user_groups
    has_gestao = adminish or bool(
        user_groups & {GRUPOS.ADMINISTRADOR, GRUPOS.RESPONSAVEL_EMPRESA, GRUPOS.APROVADOR, GRUPOS.SOLICITANTE}
    )
    has_impedimentos = adminish or (GRUPOS.GESTAO_IMPEDIMENTOS in user_groups)
    has_mapa_suprimentos = adminish or (GRUPOS.ENGENHARIA in user_groups)
    has_central = user_is_painel_sistema_admin(user)
    plat_admin = usuario_tem_administracao_global_na_plataforma(user)
    has_workflow = adminish or plat_admin or bool(
        user_groups
        & {
            GRUPOS.CENTRAL_APROVACOES_ADMIN,
            GRUPOS.CENTRAL_APROVACOES_APROVADOR,
            GRUPOS.CENTRAL_APROVACOES_EXTERNO,
        }
    )
    has_trackhub = adminish or plat_admin or bool(
        user_groups
        & {
            GRUPOS.TRACKHUB,
            GRUPOS.TRACKHUB_ADMIN,
            GRUPOS.TRACKHUB_APROVADOR,
            GRUPOS.TRACKHUB_SOLICITANTE,
        }
    )
    return has_diario, has_gestao, has_impedimentos, has_mapa_suprimentos, has_central, has_workflow, has_trackhub


def _engenharia_groups(user):
    """Grupos independentes dos módulos Mapa/Bi/Ferramenta."""
    from accounts.groups import GRUPOS

    if not user or not user.is_authenticated:
        user_groups = set()
        adminish = False
    else:
        user_groups = set(user.groups.values_list('name', flat=True))
        adminish = user.is_superuser or user.is_staff

    hs = adminish or (GRUPOS.ENGENHARIA in user_groups)
    hmc = adminish or (GRUPOS.MAPA_CONTROLE in user_groups)
    hbi = adminish or (GRUPOS.BI_DA_OBRA in user_groups)
    hf = adminish or (GRUPOS.FERRAMENTA_OPERACIONAL in user_groups)
    hub = hs or hmc or hbi or hf
    return {'has_mapa_suprimentos': hs, 'has_mapa_controle': hmc, 'has_bi_obra': hbi, 'has_ferramenta_ambientes': hf, 'has_mapa_modules_any': hub}


def sidebar_systems(request):
    """
    Disponibiliza flags de sistemas em todos os templates
    para exibir os links dos sistemas na sidebar.
    """
    if not request.user.is_authenticated:
        z = False
        return {
            'has_diario': z,
            'has_gestao': z,
            'has_impedimentos': z,
            'has_mapa': z,
            'has_mapa_suprimentos': z,
            'has_mapa_controle': z,
            'has_ferramenta_ambientes': z,
            'has_mapa_modules_any': z,
            'has_central': z,
            'has_workflow': z,
            'has_trackhub': z,
            'has_bi_obra': z,
            'has_comunicados_painel': False,
            'sidebar_show_assistente': False,
            'can_manage_central_projects': False,
        }

    has_diario, has_gestao, has_impedimentos, has_mapa_suprimentos, has_central, has_workflow_cp, has_trackhub = (
        _get_system_access(request.user)
    )
    eng = _engenharia_groups(request.user)
    has_mapa_modules_any = eng['has_mapa_modules_any']

    from accounts.groups import GRUPOS, usuario_tem_administracao_global_na_plataforma
    from accounts.painel_sistema_access import user_can_central_obras_diario_e_mapa

    user_groups = set(request.user.groups.values_list('name', flat=True))
    has_comunicados_painel = request.user.is_superuser or usuario_tem_administracao_global_na_plataforma(
        request.user
    )

    return {
        'has_diario': has_diario,
        'has_gestao': has_gestao,
        'has_impedimentos': has_impedimentos,
        'has_mapa': has_mapa_suprimentos,
        'has_mapa_suprimentos': has_mapa_suprimentos,
        'has_mapa_controle': eng['has_mapa_controle'],
        'has_ferramenta_ambientes': eng['has_ferramenta_ambientes'],
        'has_mapa_modules_any': has_mapa_modules_any,
        'has_central': has_central,
        'has_workflow': has_workflow_cp,
        'has_trackhub': has_trackhub,
        'has_bi_obra': eng['has_bi_obra'],
        'has_comunicados_painel': has_comunicados_painel,
        'sidebar_show_assistente': True,
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


def static_assets_version(request):
    """
    Versão global para invalidar cache de estáticos quando necessário.

    Em DEBUG, acrescenta o mtime dos CSS principais à query ?v= dos links em
    base.html, para o browser não ficar com base.css antigo sem Ctrl+F5.
    """
    version = getattr(settings, 'LPLAN_STATIC_VERSION', '1')
    if getattr(settings, 'DEBUG', False):
        from pathlib import Path

        base = Path(getattr(settings, 'BASE_DIR', '.'))
        candidates = (
            base / 'core' / 'static' / 'core' / 'css' / 'base.css',
            base / 'core' / 'static' / 'core' / 'css' / 'tailwind-utilities.css',
            base / 'core' / 'static' / 'core' / 'css' / 'mobile.css',
        )
        newest = 0
        for path in candidates:
            try:
                if path.is_file():
                    newest = max(newest, int(path.stat().st_mtime))
            except OSError:
                continue
        if newest:
            version = f'{version}-d{newest}'
    return {'lplan_static_version': version}
