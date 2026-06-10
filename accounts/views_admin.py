from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Max
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from datetime import timedelta, date
from django.http import HttpResponse
import csv
from mapa_obras.models import Obra
from suprimentos.models import ItemMapa, Insumo
from .groups import GRUPOS, usuario_tem_administracao_global_na_plataforma
from .painel_sistema_access import user_is_painel_sistema_admin


@login_required
@user_passes_test(user_is_painel_sistema_admin)
def admin_central(request):
    """Página central de administração - Sistema Unificado LPLAN."""
    from core.models import Project, ConstructionDiary, Activity
    from gestao_aprovacao.models import WorkOrder, Approval
    
    now = timezone.now()
    last_30_days = now - timedelta(days=30)
    
    # Stats gerais
    total_usuarios = User.objects.count()
    usuarios_ativos = User.objects.filter(is_active=True).count()
    novos_usuarios_30d = User.objects.filter(date_joined__gte=last_30_days).count()
    
    # Stats por sistema
    stats_diario = {
        'projetos': Project.objects.count(),
        'projetos_ativos': Project.objects.filter(is_active=True).count(),
        'diarios': ConstructionDiary.objects.count(),
        'diarios_30d': ConstructionDiary.objects.filter(created_at__gte=last_30_days).count(),
    }
    
    stats_gestao = {
        'ordens': WorkOrder.objects.count(),
        'aprovacoes': Approval.objects.count(),
    }
    
    stats_mapa = {
        'obras': Obra.objects.count(),
        'obras_ativas': Obra.objects.filter(ativa=True).count(),
        'insumos': Insumo.objects.count(),
        'itens_mapa': ItemMapa.objects.count(),
    }

    stats_workflow = {'processos': 0, 'aguardando': 0}
    try:
        from workflow_aprovacao.models import ApprovalProcess, ProcessStatus

        stats_workflow = {
            'processos': ApprovalProcess.objects.count(),
            'aguardando': ApprovalProcess.objects.filter(
                status=ProcessStatus.AWAITING_STEP,
            ).count(),
        }
    except Exception:
        pass

    stats_trackhub = {'pendencias': 0, 'em_aberto': 0}
    try:
        from trackhub.models import Pendencia

        stats_trackhub = {
            'pendencias': Pendencia.objects.count(),
            'em_aberto': Pendencia.objects.exclude(
                status__in=('concluida', 'cancelada'),
            ).count(),
        }
    except Exception:
        pass

    stats_impedimentos = {'total': 0, 'em_aberto': 0}
    try:
        from impedimentos.models import Impedimento

        stats_impedimentos = {
            'total': Impedimento.objects.count(),
            'em_aberto': Impedimento.objects.filter(
                ultima_conclusao_em__isnull=True,
            ).count(),
        }
    except Exception:
        pass

    stats_rh = {'colaboradores': 0, 'alertas': 0}
    try:
        from recursos_humanos.models import Colaborador
        from recursos_humanos.services.alerts import gerar_alertas

        stats_rh = {
            'colaboradores': Colaborador.objects.count(),
            'alertas': len(gerar_alertas()),
        }
    except Exception:
        pass
    
    # Grupos organizados por sistema com descricoes
    _grupo_descs = {
        GRUPOS.ADMINISTRADOR: 'Administrador da plataforma',
        GRUPOS.APROVADOR: 'Aprova pedidos',
        GRUPOS.SOLICITANTE: 'Cria pedidos',
        GRUPOS.GERENTES: 'Aprova diarios',
        GRUPOS.ENGENHARIA: 'Edita planejamento',
        GRUPOS.CENTRAL_APROVACOES_APROVADOR: 'Fila de aprovacoes',
        GRUPOS.CENTRAL_APROVACOES_EXTERNO: 'Acesso externo',
    }
    _grupos_raw = Group.objects.annotate(count=Count('user')).values('name', 'count').order_by('name')
    _grupos_dict = {g['name']: g['count'] for g in _grupos_raw}
    
    def _make_grupo_list(nomes):
        return [{'name': n, 'count': _grupos_dict.get(n, 0), 'desc': _grupo_descs.get(n, '')} for n in nomes]
    
    grupos_gestao = _make_grupo_list([GRUPOS.ADMINISTRADOR, GRUPOS.APROVADOR, GRUPOS.SOLICITANTE])
    grupos_diario = _make_grupo_list([GRUPOS.GERENTES])
    grupos_mapa = _make_grupo_list([GRUPOS.ENGENHARIA])
    grupos_central = _make_grupo_list([
        GRUPOS.CENTRAL_APROVACOES_APROVADOR,
        GRUPOS.CENTRAL_APROVACOES_EXTERNO,
    ])
    
    # Últimos usuários
    ultimos_usuarios = User.objects.select_related().prefetch_related('groups').order_by('-date_joined')[:8]
    
    # Obras ativas
    obras_ativas = Obra.objects.filter(ativa=True).order_by('nome')

    # Logs de e-mail (GestControll) — importante para acompanhar envios e falhas
    stats_email_logs = None
    try:
        from gestao_aprovacao.models import EmailLog
        total_emails = EmailLog.objects.count()
        enviados = EmailLog.objects.filter(status='enviado').count()
        falhados = EmailLog.objects.filter(status='falhou').count()
        pendentes = EmailLog.objects.filter(status='pendente').count()
        taxa_sucesso = round((enviados / total_emails * 100), 1) if total_emails > 0 else 0
        stats_email_logs = {
            'total': total_emails,
            'enviados': enviados,
            'falhados': falhados,
            'pendentes': pendentes,
            'taxa_sucesso': taxa_sucesso,
        }
    except Exception:
        pass

    # Logs do sistema (backend) — erros recentes para ação rápida
    stats_system_logs = None
    try:
        from core.central_views import get_log_health_snapshot
        stats_system_logs = get_log_health_snapshot(hours=24)
    except Exception:
        pass

    # Pedidos de correção em RDO (diário aprovado → pedido pendente de liberação)
    pending_diary_edit_requests_count = 0
    try:
        pending_diary_edit_requests_count = ConstructionDiary.objects.filter(
            edit_requested_at__isnull=False,
            provisional_edit_granted_at__isnull=True,
        ).count()
    except Exception:
        pass

    signup_pendentes_count = 0
    try:
        from accounts.models import UserSignupRequest

        signup_pendentes_count = UserSignupRequest.objects.filter(
            status=UserSignupRequest.STATUS_PENDENTE,
        ).count()
    except Exception:
        pass

    pendencias_acao_total = signup_pendentes_count + pending_diary_edit_requests_count
    if signup_pendentes_count > 0:
        pendencias_acao_url = reverse('central_signup_requests')
    elif pending_diary_edit_requests_count > 0:
        pendencias_acao_url = reverse('central_diary_edit_requests')
    else:
        pendencias_acao_url = reverse('accounts:user_panel')

    # Usuários ativos sem produção no período (Diário ou GestControll) — adoção
    usuarios_sem_atividade_30d = 0
    try:
        qs_ativos_plataforma = User.objects.filter(is_active=True).exclude(is_staff=True)
        com_diario = set(
            ConstructionDiary.objects.filter(created_at__gte=last_30_days).values_list(
                'created_by_id', flat=True,
            ),
        )
        com_diario |= set(
            ConstructionDiary.objects.filter(
                approved_at__gte=last_30_days,
                reviewed_by_id__isnull=False,
            ).values_list('reviewed_by_id', flat=True),
        )
        com_pedido = set(
            WorkOrder.objects.filter(created_at__gte=last_30_days).values_list(
                'criado_por_id', flat=True,
            ),
        )
        com_pedido |= set(
            Approval.objects.filter(created_at__gte=last_30_days).values_list(
                'aprovado_por_id', flat=True,
            ),
        )
        produziram = {x for x in (com_diario | com_pedido) if x}
        if produziram:
            usuarios_sem_atividade_30d = qs_ativos_plataforma.exclude(id__in=produziram).count()
        else:
            usuarios_sem_atividade_30d = qs_ativos_plataforma.count()
    except Exception:
        pass

    context = {
        'total_usuarios': total_usuarios,
        'usuarios_ativos': usuarios_ativos,
        'novos_usuarios_30d': novos_usuarios_30d,
        'stats_diario': stats_diario,
        'stats_gestao': stats_gestao,
        'stats_mapa': stats_mapa,
        'stats_workflow': stats_workflow,
        'stats_trackhub': stats_trackhub,
        'stats_impedimentos': stats_impedimentos,
        'stats_rh': stats_rh,
        'grupos_gestao': grupos_gestao,
        'grupos_diario': grupos_diario,
        'grupos_mapa': grupos_mapa,
        'grupos_central': grupos_central,
        'ultimos_usuarios': ultimos_usuarios,
        'obras_ativas': obras_ativas,
        'stats_email_logs': stats_email_logs,
        'stats_system_logs': stats_system_logs,
        'pending_diary_edit_requests_count': pending_diary_edit_requests_count,
        'signup_pendentes_count': signup_pendentes_count,
        'pendencias_acao_total': pendencias_acao_total,
        'pendencias_acao_url': pendencias_acao_url,
        'usuarios_sem_atividade_30d': usuarios_sem_atividade_30d,
        'painel_comunicados': usuario_tem_administracao_global_na_plataforma(request.user),
    }
    from accounts.modulos_integrados import build_modulos_cards_for_admin

    context['modulos_integrados_cards'] = build_modulos_cards_for_admin(
        {
            'stats_diario': stats_diario,
            'stats_gestao': stats_gestao,
            'stats_mapa': stats_mapa,
            'stats_workflow': stats_workflow,
            'stats_trackhub': stats_trackhub,
            'stats_impedimentos': stats_impedimentos,
        'stats_rh': stats_rh,
        }
    )

    return render(request, 'accounts/admin_central.html', context)


@login_required
def modulo_indisponivel(request, codigo):
    """Página exibida quando o módulo está temporariamente inativo."""
    from accounts.modulos_integrados import MODULO_BY_CODIGO, load_modulos_status_map

    meta = MODULO_BY_CODIGO.get(codigo)
    if not meta:
        return redirect('select-system')
    status = load_modulos_status_map().get(codigo, {})
    if status.get('ativo', True) and not user_is_painel_sistema_admin(request.user):
        try:
            return redirect(reverse(meta.url_name))
        except Exception:
            return redirect('select-system')
    return render(
        request,
        'accounts/modulo_indisponivel.html',
        {
            'modulo': meta,
            'status': status,
            'pode_gerenciar': user_is_painel_sistema_admin(request.user),
        },
    )


@login_required
@user_passes_test(user_is_painel_sistema_admin)
@require_http_methods(['POST'])
def modulo_integrado_inativar(request, codigo):
    from accounts.models import ModuloIntegradoStatus
    from accounts.modulos_integrados import MODULO_BY_CODIGO, invalidate_modulos_cache

    if codigo not in MODULO_BY_CODIGO:
        raise PermissionDenied
    mensagem = (request.POST.get('mensagem') or '').strip()
    if len(mensagem) < 10:
        messages.error(request, 'Informe uma justificativa com pelo menos 10 caracteres.')
        return redirect('accounts:admin_central')

    previsao_raw = (request.POST.get('previsao_retorno') or '').strip()
    previsao = None
    if previsao_raw:
        try:
            previsao = date.fromisoformat(previsao_raw)
        except ValueError:
            messages.error(request, 'Data de previsão de retorno inválida.')
            return redirect('accounts:admin_central')
        if previsao < timezone.localdate():
            messages.error(request, 'A previsão de retorno não pode ser anterior a hoje.')
            return redirect('accounts:admin_central')

    meta = MODULO_BY_CODIGO[codigo]
    row, _ = ModuloIntegradoStatus.objects.get_or_create(
        codigo=codigo,
        defaults={'nome': meta.nome, 'ativo': True},
    )
    row.nome = meta.nome
    row.ativo = False
    row.mensagem = mensagem
    row.previsao_retorno = previsao
    row.atualizado_por = request.user
    row.save()
    invalidate_modulos_cache()
    messages.warning(request, f'«{meta.nome}» foi inativado. Usuários verão o aviso ao tentar acessar.')
    return redirect('accounts:admin_central')


@login_required
@user_passes_test(user_is_painel_sistema_admin)
@require_http_methods(['POST'])
def modulo_integrado_reativar(request, codigo):
    from accounts.models import ModuloIntegradoStatus
    from accounts.modulos_integrados import MODULO_BY_CODIGO, invalidate_modulos_cache

    if codigo not in MODULO_BY_CODIGO:
        raise PermissionDenied
    meta = MODULO_BY_CODIGO[codigo]
    row = get_object_or_404(ModuloIntegradoStatus, codigo=codigo)
    row.nome = meta.nome
    row.ativo = True
    row.mensagem = ''
    row.previsao_retorno = None
    row.atualizado_por = request.user
    row.save()
    invalidate_modulos_cache()
    messages.success(request, f'«{meta.nome}» foi reativado.')
    return redirect('accounts:admin_central')


@login_required
@user_passes_test(user_is_painel_sistema_admin)
def user_panel(request):
    """Painel do usuário: área nichada para gestão de usuários e acessos."""
    return render(request, 'core/central_user_panel.html')


@login_required
@user_passes_test(user_is_painel_sistema_admin)
def logs_panel(request):
    """Painel de logs: auditoria, logs técnicos e logs de e-mail."""
    return render(request, 'core/central_logs_panel.html')


def _obras_por_usuario(user_ids):
    if not user_ids:
        return {}
    try:
        from core.models import ProjectMember

        return {
            row['user_id']: row['count']
            for row in ProjectMember.objects.filter(user_id__in=user_ids)
            .values('user_id')
            .annotate(count=Count('id'))
        }
    except Exception:
        return {}


def _ultima_atividade_por_usuario(user_ids):
    """Data mais recente de ação (Diário ou GestControll) por usuário."""
    if not user_ids:
        return {}
    result = {uid: None for uid in user_ids}

    def _merge(rows, uid_field, date_key='last'):
        for row in rows:
            uid = row.get(uid_field)
            dt = row.get(date_key)
            if not uid or not dt:
                continue
            prev = result.get(uid)
            if prev is None or dt > prev:
                result[uid] = dt

    try:
        from core.models import ConstructionDiary

        _merge(
            ConstructionDiary.objects.filter(created_by_id__in=user_ids)
            .values('created_by_id')
            .annotate(last=Max('created_at')),
            'created_by_id',
        )
        _merge(
            ConstructionDiary.objects.filter(
                reviewed_by_id__in=user_ids,
                approved_at__isnull=False,
            )
            .values('reviewed_by_id')
            .annotate(last=Max('approved_at')),
            'reviewed_by_id',
        )
    except Exception:
        pass
    try:
        from gestao_aprovacao.models import Approval, WorkOrder

        _merge(
            WorkOrder.objects.filter(criado_por_id__in=user_ids)
            .values('criado_por_id')
            .annotate(last=Max('created_at')),
            'criado_por_id',
        )
        _merge(
            Approval.objects.filter(aprovado_por_id__in=user_ids)
            .values('aprovado_por_id')
            .annotate(last=Max('created_at')),
            'aprovado_por_id',
        )
    except Exception:
        pass
    return result


def _uso_resumo_label(usa_diario, usa_gestao, diarios_rev, aprovacoes, sem_producao):
    if sem_producao:
        return 'Sem uso no período'
    partes = []
    if diarios_rev and not usa_diario:
        partes.append('Revisão de diário')
    elif usa_diario:
        partes.append('Diário de obra')
    if usa_gestao:
        if aprovacoes and not partes:
            partes.append('Aprovações')
        elif aprovacoes:
            partes.append('GestControll')
        else:
            partes.append('Pedidos')
    return ' + '.join(partes) if partes else 'Ativo'


def _row_analise_usuario(u, prod_por_usuario, obras_por_usuario, ultima_atividade, now):
    """Linha da tabela: uso em Diário e GestControll nos últimos 30 dias."""
    p = prod_por_usuario.get(u.id, {})
    diarios_30 = p.get('diarios_criados_30d', 0)
    diarios_rev_30 = p.get('diarios_revisados_30d', 0)
    pedidos_30 = p.get('pedidos_30d', 0)
    aprov_30 = p.get('aprovacoes_30d', 0)
    reprov_30 = p.get('reprovacoes_30d', 0)

    usa_diario = diarios_30 > 0 or diarios_rev_30 > 0
    usa_gestao = pedidos_30 > 0 or aprov_30 > 0 or reprov_30 > 0
    sem_producao = not usa_diario and not usa_gestao

    pct_reprov = round((reprov_30 / pedidos_30) * 100, 1) if pedidos_30 else None

    if u.last_login:
        dias_sem_login = (now - u.last_login).days
    else:
        dias_sem_login = None

    ultima_acao = ultima_atividade.get(u.id)

    return {
        'user': u,
        'diarios_criados_30d': diarios_30,
        'diarios_revisados_30d': diarios_rev_30,
        'pedidos_30d': pedidos_30,
        'aprovacoes_30d': aprov_30,
        'reprovacoes_30d': reprov_30,
        'pct_reprov': pct_reprov,
        'obras_count': obras_por_usuario.get(u.id, 0),
        'usa_diario': usa_diario,
        'usa_gestao': usa_gestao,
        'sem_producao': sem_producao,
        'uso_resumo': _uso_resumo_label(usa_diario, usa_gestao, diarios_rev_30, aprov_30, sem_producao),
        'dias_sem_login': dias_sem_login,
        'ultima_acao': ultima_acao,
        'nunca_logou': u.last_login is None,
        'login_antigo': dias_sem_login is not None and dias_sem_login > 30,
    }


def _analise_usuarios_queryset(request):
    """Aplica filtros GET à queryset de usuários (reutilizado na view e no CSV)."""
    usuarios = User.objects.prefetch_related('groups').order_by('-date_joined')
    grupo_id = request.GET.get('grupo')
    status_filtro = request.GET.get('status', 'ativos')
    uso_filtro = request.GET.get('uso', '')
    if grupo_id:
        try:
            g = Group.objects.get(pk=int(grupo_id))
            usuarios = usuarios.filter(groups=g)
        except (ValueError, Group.DoesNotExist):
            pass
    if status_filtro == 'ativos':
        usuarios = usuarios.filter(is_active=True)
    elif status_filtro == 'inativos':
        usuarios = usuarios.filter(is_active=False)
    if uso_filtro == 'nunca_logou':
        usuarios = usuarios.filter(last_login__isnull=True)
    elif uso_filtro == 'sem_login_30d':
        now = timezone.now()
        last_30 = now - timedelta(days=30)
        usuarios = usuarios.filter(Q(last_login__lt=last_30) | Q(last_login__isnull=True))
    elif uso_filtro == 'sem_login_90d':
        now = timezone.now()
        last_90 = now - timedelta(days=90)
        usuarios = usuarios.filter(Q(last_login__lt=last_90) | Q(last_login__isnull=True))
    elif uso_filtro == 'sem_producao':
        try:
            from core.models import ConstructionDiary
            from gestao_aprovacao.models import Approval, WorkOrder

            last_30 = timezone.now() - timedelta(days=30)
            com_diario = set(
                ConstructionDiary.objects.filter(created_at__gte=last_30).values_list(
                    'created_by_id', flat=True,
                ),
            )
            com_diario |= set(
                ConstructionDiary.objects.filter(
                    approved_at__gte=last_30,
                    reviewed_by_id__isnull=False,
                ).values_list('reviewed_by_id', flat=True),
            )
            com_pedido = set(
                WorkOrder.objects.filter(created_at__gte=last_30).values_list(
                    'criado_por_id', flat=True,
                ),
            )
            com_pedido |= set(
                Approval.objects.filter(created_at__gte=last_30).values_list(
                    'aprovado_por_id', flat=True,
                ),
            )
            produziram = {x for x in (com_diario | com_pedido) if x}
            if produziram:
                usuarios = usuarios.exclude(id__in=produziram)
        except Exception:
            pass
    elif uso_filtro == 'com_reprovacao':
        try:
            from gestao_aprovacao.models import Approval

            last_30 = timezone.now() - timedelta(days=30)
            ids = set(
                Approval.objects.filter(
                    decisao='reprovado',
                    created_at__gte=last_30,
                ).values_list('work_order__criado_por_id', flat=True),
            )
            ids.discard(None)
            if ids:
                usuarios = usuarios.filter(id__in=ids)
            else:
                usuarios = usuarios.none()
        except Exception:
            pass
    elif uso_filtro == 'mod_nenhum':
        try:
            from core.models import ConstructionDiary
            from gestao_aprovacao.models import Approval, WorkOrder

            last_30 = timezone.now() - timedelta(days=30)
            com_diario = set(
                ConstructionDiary.objects.filter(created_at__gte=last_30).values_list(
                    'created_by_id', flat=True,
                ),
            )
            com_pedido = set(
                WorkOrder.objects.filter(created_at__gte=last_30).values_list(
                    'criado_por_id', flat=True,
                ),
            )
            com_pedido |= set(
                Approval.objects.filter(created_at__gte=last_30).values_list(
                    'aprovado_por_id', flat=True,
                ),
            )
            com_diario |= set(
                ConstructionDiary.objects.filter(
                    approved_at__gte=last_30,
                    reviewed_by_id__isnull=False,
                ).values_list('reviewed_by_id', flat=True),
            )
            usaram = {x for x in (com_diario | com_pedido) if x}
            if usaram:
                usuarios = usuarios.filter(is_active=True).exclude(is_staff=True).exclude(id__in=usaram)
            else:
                usuarios = usuarios.filter(is_active=True).exclude(is_staff=True)
        except Exception:
            pass
    busca_query = (request.GET.get('busca') or '').strip()
    if busca_query:
        usuarios = usuarios.filter(
            Q(username__icontains=busca_query)
            | Q(first_name__icontains=busca_query)
            | Q(last_name__icontains=busca_query)
            | Q(email__icontains=busca_query)
        )
    return usuarios


@login_required
@user_passes_test(user_is_painel_sistema_admin)
def analise_usuarios(request):
    """Adoção de uso e reprovações no GestControll (30 dias) — lista filtrável + export CSV."""
    last_30_days = timezone.now() - timedelta(days=30)

    qs_ativos = User.objects.filter(is_active=True).exclude(is_staff=True)
    usuarios_ativos = qs_ativos.count()
    sem_login_30d = qs_ativos.filter(
        Q(last_login__lt=last_30_days) | Q(last_login__isnull=True),
    ).count()
    nunca_logaram = qs_ativos.filter(last_login__isnull=True).count()

    resumo_sistema = {'só_diario': 0, 'só_pedido': 0, 'ambos': 0, 'nenhum': 0}
    usuarios_sem_producao_30d_count = 0
    com_diario_30d = set()
    com_pedido_30d = set()
    try:
        from core.models import ConstructionDiary
        from gestao_aprovacao.models import WorkOrder

        com_diario_30d = set(
            ConstructionDiary.objects.filter(created_at__gte=last_30_days)
            .values_list('created_by_id', flat=True)
        )
        com_pedido_30d = set(
            WorkOrder.objects.filter(created_at__gte=last_30_days)
            .values_list('criado_por_id', flat=True)
        )
        produziram = com_diario_30d | com_pedido_30d
        usuarios_sem_producao_30d_count = qs_ativos.exclude(id__in=produziram).count()
        for uid in qs_ativos.values_list('id', flat=True):
            d = uid in com_diario_30d
            p = uid in com_pedido_30d
            if d and p:
                resumo_sistema['ambos'] += 1
            elif d:
                resumo_sistema['só_diario'] += 1
            elif p:
                resumo_sistema['só_pedido'] += 1
            else:
                resumo_sistema['nenhum'] += 1
    except Exception:
        pass

    total_pedidos_30d = 0
    total_diarios_30d = 0
    total_reprovacoes_30d = 0
    taxa_reprovacao_pct = 0.0
    usuarios_com_reprovacao_30d = 0  # solicitantes com pedido reprovado no período
    top_reprovacoes_solicitante = []
    top_reprovacoes_obra = []
    try:
        from core.models import ConstructionDiary
        from gestao_aprovacao.models import Approval, Obra, WorkOrder

        total_diarios_30d = ConstructionDiary.objects.filter(created_at__gte=last_30_days).count()
        total_pedidos_30d = WorkOrder.objects.filter(created_at__gte=last_30_days).count()
        total_aprov_ok = Approval.objects.filter(
            decisao='aprovado', created_at__gte=last_30_days,
        ).count()
        total_reprovacoes_30d = Approval.objects.filter(
            decisao='reprovado', created_at__gte=last_30_days,
        ).count()
        _total_dec = total_aprov_ok + total_reprovacoes_30d
        taxa_reprovacao_pct = round((total_reprovacoes_30d / _total_dec * 100), 1) if _total_dec else 0.0
        usuarios_com_reprovacao_30d = (
            Approval.objects.filter(decisao='reprovado', created_at__gte=last_30_days)
            .exclude(work_order__criado_por_id__isnull=True)
            .values('work_order__criado_por_id')
            .distinct()
            .count()
        )

        sol_rows = list(
            Approval.objects.filter(decisao='reprovado', created_at__gte=last_30_days)
            .values('work_order__criado_por_id')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
        sol_ids = [r['work_order__criado_por_id'] for r in sol_rows if r['work_order__criado_por_id']]
        sol_map = {u.id: u for u in User.objects.filter(pk__in=sol_ids)}
        top_reprovacoes_solicitante = [
            {'user': sol_map[r['work_order__criado_por_id']], 'count': r['count']}
            for r in sol_rows
            if r['work_order__criado_por_id'] and r['work_order__criado_por_id'] in sol_map
        ]

        obra_rows = list(
            Approval.objects.filter(decisao='reprovado', created_at__gte=last_30_days)
            .values('work_order__obra_id')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
        obra_ids = [r['work_order__obra_id'] for r in obra_rows if r['work_order__obra_id']]
        obra_map = {o.id: o for o in Obra.objects.filter(pk__in=obra_ids)}
        top_reprovacoes_obra = [
            {
                'obra_nome': obra_map[r['work_order__obra_id']].nome,
                'count': r['count'],
            }
            for r in obra_rows
            if r['work_order__obra_id'] and r['work_order__obra_id'] in obra_map
        ]
    except Exception:
        pass

    grupos_com_count = (
        Group.objects.annotate(count=Count('user'))
        .filter(count__gt=0)
        .order_by('-count')
        .values('id', 'name', 'count')
    )

    usuarios = _analise_usuarios_queryset(request)
    grupo_id = request.GET.get('grupo')
    status_filtro = request.GET.get('status', 'ativos')
    uso_filtro = request.GET.get('uso', '')
    busca_query = (request.GET.get('busca') or '').strip()
    usuarios = list(usuarios[:200])
    user_ids = [u.id for u in usuarios]
    prod_por_usuario = _produtividade_para_usuarios(user_ids, last_30_days)
    obras_map = _obras_por_usuario(user_ids)
    ultima_atividade = _ultima_atividade_por_usuario(user_ids)
    now = timezone.now()

    context = {
        'usuarios_ativos': usuarios_ativos,
        'sem_login_30d': sem_login_30d,
        'nunca_logaram': nunca_logaram,
        'usuarios_sem_producao_30d_count': usuarios_sem_producao_30d_count,
        'usuarios_com_reprovacao_30d': usuarios_com_reprovacao_30d,
        'resumo_sistema': resumo_sistema,
        'taxa_reprovacao_pct': taxa_reprovacao_pct,
        'total_reprovacoes_30d': total_reprovacoes_30d,
        'total_pedidos_30d': total_pedidos_30d,
        'total_diarios_30d': total_diarios_30d,
        'top_reprovacoes_solicitante': top_reprovacoes_solicitante,
        'top_reprovacoes_obra': top_reprovacoes_obra,
        'grupos_com_count': grupos_com_count,
        'usuarios_com_prod': [
            _row_analise_usuario(u, prod_por_usuario, obras_map, ultima_atividade, now)
            for u in usuarios
        ],
        'lista_total': len(usuarios),
        'busca_query': busca_query,
        'grupo_id': grupo_id,
        'status_filtro': status_filtro,
        'uso_filtro': uso_filtro,
    }
    return render(request, 'accounts/admin_analise_usuarios.html', context)


def _produtividade_para_usuarios(user_ids, last_30_days):
    """Retorna dict user_id -> { diarios_criados_30d, diarios_revisados_30d, pedidos_30d, aprovacoes_30d, reprovacoes_30d }."""
    prod = {uid: {'diarios_criados_30d': 0, 'diarios_revisados_30d': 0, 'pedidos_30d': 0, 'aprovacoes_30d': 0, 'reprovacoes_30d': 0} for uid in user_ids}
    if not user_ids:
        return prod
    try:
        from core.models import ConstructionDiary
        for row in ConstructionDiary.objects.filter(created_by_id__in=user_ids, created_at__gte=last_30_days).values('created_by_id').annotate(count=Count('id')):
            prod[row['created_by_id']]['diarios_criados_30d'] = row['count']
        for row in ConstructionDiary.objects.filter(reviewed_by_id__in=user_ids, approved_at__isnull=False, approved_at__gte=last_30_days).values('reviewed_by_id').annotate(count=Count('id')):
            prod[row['reviewed_by_id']]['diarios_revisados_30d'] = row['count']
    except Exception:
        pass
    try:
        from gestao_aprovacao.models import WorkOrder, Approval
        for row in WorkOrder.objects.filter(criado_por_id__in=user_ids, created_at__gte=last_30_days).values('criado_por_id').annotate(count=Count('id')):
            prod[row['criado_por_id']]['pedidos_30d'] = row['count']
        for row in Approval.objects.filter(aprovado_por_id__in=user_ids, created_at__gte=last_30_days).values('aprovado_por_id').annotate(count=Count('id')):
            prod[row['aprovado_por_id']]['aprovacoes_30d'] = row['count']
        for row in Approval.objects.filter(decisao='reprovado', created_at__gte=last_30_days).values('work_order__criado_por_id').annotate(count=Count('id')):
            if row['work_order__criado_por_id'] and row['work_order__criado_por_id'] in prod:
                prod[row['work_order__criado_por_id']]['reprovacoes_30d'] = row['count']
    except Exception:
        pass
    return prod


@login_required
@user_passes_test(user_is_painel_sistema_admin)
def analise_usuarios_export_csv(request):
    """Exporta a lista filtrada de usuários para CSV (com produtividade 30d)."""
    usuarios = list(_analise_usuarios_queryset(request))
    last_30_days = timezone.now() - timedelta(days=30)
    user_ids = [u.id for u in usuarios]
    prod = _produtividade_para_usuarios(user_ids, last_30_days)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="analise_usuarios.csv"'
    response.write('\ufeff')  # BOM para Excel
    writer = csv.writer(response, delimiter=';')
    # Obras vinculadas (ProjectMember) para o CSV
    obras_por_usuario = {}
    if user_ids:
        try:
            from core.models import ProjectMember
            for row in ProjectMember.objects.filter(user_id__in=user_ids).values('user_id').annotate(count=Count('id')):
                obras_por_usuario[row['user_id']] = row['count']
        except Exception:
            pass

    writer.writerow(['Usuário', 'Nome', 'E-mail', 'Grupos', 'Obras', 'Último login', 'Cadastro', 'Ativo', 'Diários (30d)', 'Revisões (30d)', 'Pedidos (30d)', 'Aprovações (30d)', 'Reprovações (30d)', '% Reprov.', 'Desempenho'])
    for u in usuarios:
        grupos = ', '.join(g.name for g in u.groups.all())
        p = prod.get(u.id, {})
        ped = p.get('pedidos_30d', 0)
        rep = p.get('reprovacoes_30d', 0)
        pct_rep = round((rep / ped * 100), 1) if ped else ''
        diarios_30 = p.get('diarios_criados_30d', 0)
        aprov_30 = p.get('aprovacoes_30d', 0)
        soma = diarios_30 + ped + aprov_30
        desempenho = 'Alto' if soma >= 10 else ('Médio' if soma > 0 else 'Baixo')
        writer.writerow([
            u.username,
            u.get_full_name() or '',
            u.email or '',
            grupos,
            obras_por_usuario.get(u.id, 0),
            u.last_login.strftime('%d/%m/%Y %H:%M') if u.last_login else 'Nunca',
            u.date_joined.strftime('%d/%m/%Y'),
            'Sim' if u.is_active else 'Não',
            p.get('diarios_criados_30d', 0),
            p.get('diarios_revisados_30d', 0),
            ped,
            p.get('aprovacoes_30d', 0),
            rep,
            pct_rep,
            desempenho,
        ])
    return response


# ========================================
# Gestão de usuários centralizada em:
# gestao_aprovacao/views.py (create_user, list_users, edit_user, delete_user)
# Acessível via namespace: gestao:create_user, gestao:list_users, etc.
# ========================================


@login_required
@user_passes_test(user_is_painel_sistema_admin)
def criar_obra(request):
    """
    Redirecionamento: cadastro unificado em /projects/new/ (sincroniza Diário + Mapa + Gestão).
    """
    if request.method == 'GET' and request.session.pop('_prevent_back_criar_obra', None):
        return redirect('accounts:admin_central')
    if request.method == 'POST':
        messages.info(
            request,
            'O cadastro de obras foi unificado em «Obras»: use Nova Obra — o Mapa de Suprimentos '
            'é atualizado automaticamente pelo código do projeto.',
        )
    return redirect('project-new')


@login_required
@user_passes_test(user_is_painel_sistema_admin)
def gerenciar_obras(request):
    """Redirecionamento: listagem única em /projects/."""
    return redirect('central_project_list')

