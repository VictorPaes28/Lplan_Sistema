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
        return False, False, False, False, False, False, False, False, False
    from accounts.groups import GRUPOS, usuario_tem_acesso_mapa_geografico, usuario_tem_administracao_global_na_plataforma
    from accounts.painel_sistema_access import user_is_painel_sistema_admin

    user_groups = set(user.groups.values_list('name', flat=True))
    adminish = user.is_superuser or user.is_staff
    has_diario = adminish or GRUPOS.GERENTES in user_groups
    has_mapa_geo = adminish or usuario_tem_acesso_mapa_geografico(user)
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
    has_rh = adminish or plat_admin or (GRUPOS.RECURSOS_HUMANOS in user_groups)
    return has_diario, has_mapa_geo, has_gestao, has_impedimentos, has_mapa_suprimentos, has_central, has_workflow, has_trackhub, has_rh


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
            'has_mapa_geo': z,
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
            'has_rh': z,
            'has_bi_obra': z,
            'has_comunicados_painel': False,
            'sidebar_show_assistente': False,
            'can_manage_central_projects': False,
        }

    has_diario, has_mapa_geo, has_gestao, has_impedimentos, has_mapa_suprimentos, has_central, has_workflow_cp, has_trackhub, has_rh = (
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
        'has_mapa_geo': has_mapa_geo,
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
        'has_rh': has_rh,
        'has_bi_obra': eng['has_bi_obra'],
        'has_comunicados_painel': has_comunicados_painel,
        'sidebar_show_assistente': True,
        'can_manage_central_projects': user_can_central_obras_diario_e_mapa(request.user),
    }


def sidebar_counters(request):
    """
    Context processor para adicionar contadores da sidebar em todas as páginas.
    """
    zeros = {
        'total_reports_count': 0,
        'total_photos_count': 0,
        'total_videos_count': 0,
        'total_activities_count': 0,
        'total_occurrences_count': 0,
        'total_comments_count': 0,
        'total_attachments_count': 0,
    }
    if not request.user.is_authenticated:
        return zeros

    project_id = request.session.get('selected_project_id')
    if not project_id:
        return zeros

    from django.core.cache import cache
    from django.db.models import Count, Q

    cache_key = f'core:sidebar_counters:v1:{project_id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        diary_agg = ConstructionDiary.objects.filter(project_id=project_id).aggregate(
            total_reports=Count('id'),
            total_comments=Count(
                'id',
                filter=~Q(general_notes='') & ~Q(general_notes__isnull=True),
            ),
        )
        total_photos = DiaryImage.objects.filter(
            diary__project_id=project_id,
            is_approved_for_report=True,
        ).count()
        total_videos = DiaryVideo.objects.filter(
            diary__project_id=project_id,
        ).count()
        total_activities = Activity.objects.filter(project_id=project_id).count()
        total_occurrences = DiaryOccurrence.objects.filter(
            diary__project_id=project_id,
        ).count()
        total_attachments = DiaryAttachment.objects.filter(
            diary__project_id=project_id,
        ).count()

        result = {
            'total_reports_count': diary_agg['total_reports'] or 0,
            'total_photos_count': total_photos,
            'total_videos_count': total_videos,
            'total_activities_count': total_activities,
            'total_occurrences_count': total_occurrences,
            'total_comments_count': diary_agg['total_comments'] or 0,
            'total_attachments_count': total_attachments,
        }
        cache.set(cache_key, result, 60)
        return result
    except Exception:
        return zeros


def obra_inativa_sessao(request):
    """
    Indica se o projeto em selected_project_id está inativo (modo consulta no Diário e módulos que usam a mesma sessão).
    """
    if not request.user.is_authenticated:
        return {'lplan_obra_sessao_inativa': False, 'lplan_obra_inativa_msg': ''}
    pid = request.session.get('selected_project_id')
    if not pid:
        return {'lplan_obra_sessao_inativa': False, 'lplan_obra_inativa_msg': ''}
    try:
        from .models import Project
        from .obras_readonly import OBRA_INATIVA_CONSULTA_MSG

        row = Project.objects.filter(pk=pid).values_list('is_active', flat=True).first()
        if row is None:
            return {'lplan_obra_sessao_inativa': False, 'lplan_obra_inativa_msg': ''}
        inactive = not bool(row)
        return {
            'lplan_obra_sessao_inativa': inactive,
            'lplan_obra_inativa_msg': OBRA_INATIVA_CONSULTA_MSG if inactive else '',
        }
    except Exception:
        return {'lplan_obra_sessao_inativa': False, 'lplan_obra_inativa_msg': ''}


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
            base / 'core' / 'static' / 'core' / 'css' / 'page-transitions.css',
            base / 'core' / 'static' / 'core' / 'css' / 'ux-improvements.css',
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
