from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.db.models import Count, Q, Max
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta, date
from django.http import HttpResponse
import csv
from mapa_obras.models import Obra
from suprimentos.models import ItemMapa, Insumo
from .groups import GRUPOS


def is_staff_or_superuser(user):
    """Verifica se o usuário é staff ou superusuário."""
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_staff_or_superuser)
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
    
    # Grupos organizados por sistema com descricoes
    _grupo_descs = {
        GRUPOS.ADMINISTRADOR: 'Acesso total',
        GRUPOS.RESPONSAVEL_EMPRESA: 'Gerencia empresa',
        GRUPOS.APROVADOR: 'Aprova pedidos',
        GRUPOS.SOLICITANTE: 'Cria pedidos',
        GRUPOS.GERENTES: 'Aprova diarios',
        GRUPOS.ENGENHARIA: 'Edita planejamento',
    }
    _grupos_raw = Group.objects.annotate(count=Count('user')).values('name', 'count').order_by('name')
    _grupos_dict = {g['name']: g['count'] for g in _grupos_raw}
    
    def _make_grupo_list(nomes):
        return [{'name': n, 'count': _grupos_dict.get(n, 0), 'desc': _grupo_descs.get(n, '')} for n in nomes]
    
    grupos_gestao = _make_grupo_list([GRUPOS.ADMINISTRADOR, GRUPOS.RESPONSAVEL_EMPRESA, GRUPOS.APROVADOR, GRUPOS.SOLICITANTE])
    grupos_diario = _make_grupo_list([GRUPOS.GERENTES])
    grupos_mapa = _make_grupo_list([GRUPOS.ENGENHARIA])
    
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

    context = {
        'total_usuarios': total_usuarios,
        'usuarios_ativos': usuarios_ativos,
        'novos_usuarios_30d': novos_usuarios_30d,
        'stats_diario': stats_diario,
        'stats_gestao': stats_gestao,
        'stats_mapa': stats_mapa,
        'grupos_gestao': grupos_gestao,
        'grupos_diario': grupos_diario,
        'grupos_mapa': grupos_mapa,
        'ultimos_usuarios': ultimos_usuarios,
        'obras_ativas': obras_ativas,
        'stats_email_logs': stats_email_logs,
    }

    return render(request, 'accounts/admin_central.html', context)


def _row_analise_usuario(u, prod_por_usuario):
    """Monta um dicionário de análise por usuário (produtividade, obras, última atividade, desempenho)."""
    p = prod_por_usuario.get(u.id, {})
    diarios_30 = p.get('diarios_criados_30d', 0)
    pedidos_30 = p.get('pedidos_30d', 0)
    aprov_30 = p.get('aprovacoes_30d', 0)
    soma = diarios_30 + pedidos_30 + aprov_30
    if soma >= 10:
        desempenho = 'alto'
    elif soma > 0:
        desempenho = 'medio'
    else:
        desempenho = 'baixo'
    return {
        'user': u,
        'diarios_criados_30d': p.get('diarios_criados_30d', 0),
        'diarios_revisados_30d': p.get('diarios_revisados_30d', 0),
        'pedidos_30d': p.get('pedidos_30d', 0),
        'aprovacoes_30d': p.get('aprovacoes_30d', 0),
        'reprovacoes_30d': p.get('reprovacoes_30d', 0),
        'taxa_reprovacao': round((p.get('reprovacoes_30d', 0) / p['pedidos_30d'] * 100), 1) if p.get('pedidos_30d') else None,
        'sem_producao': (p.get('diarios_criados_30d', 0) == 0 and p.get('pedidos_30d', 0) == 0),
        'obras_vinculadas': p.get('obras_vinculadas', 0),
        'ultima_atividade': p.get('ultima_atividade'),
        'diarios_90d': p.get('diarios_criados_90d', 0),
        'pedidos_90d': p.get('pedidos_90d', 0),
        'desempenho': desempenho,
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
            from gestao_aprovacao.models import WorkOrder
            last_30 = timezone.now() - timedelta(days=30)
            com_diario = set(ConstructionDiary.objects.filter(created_at__gte=last_30).values_list('created_by_id', flat=True))
            com_pedido = set(WorkOrder.objects.filter(created_at__gte=last_30).values_list('criado_por_id', flat=True))
            produziram = com_diario | com_pedido
            if produziram:
                usuarios = usuarios.exclude(id__in=produziram)
        except Exception:
            pass
    return usuarios


@login_required
@user_passes_test(is_staff_or_superuser)
def analise_usuarios(request):
    """Página de análise geral de usuários para o admin (visão única, métricas e filtros)."""
    now = timezone.now()
    last_7_days = now - timedelta(days=7)
    last_30_days = now - timedelta(days=30)
    last_90_days = now - timedelta(days=90)

    qs_all = User.objects.all()
    total_usuarios = qs_all.count()
    usuarios_ativos = qs_all.filter(is_active=True).count()
    usuarios_inativos = qs_all.filter(is_active=False).count()
    novos_7d = qs_all.filter(date_joined__gte=last_7_days).count()
    novos_30d = qs_all.filter(date_joined__gte=last_30_days).count()
    novos_90d = qs_all.filter(date_joined__gte=last_90_days).count()
    nunca_logaram = qs_all.filter(last_login__isnull=True).exclude(is_staff=True).count()
    sem_login_30d = qs_all.filter(
        Q(last_login__lt=last_30_days) | Q(last_login__isnull=True)
    ).filter(is_active=True).exclude(is_staff=True).count()
    sem_login_90d = qs_all.filter(
        Q(last_login__lt=last_90_days) | Q(last_login__isnull=True)
    ).filter(is_active=True).exclude(is_staff=True).count()

    # Retenção: % de ativos que logaram nos últimos 30 dias
    ativos_que_logaram_30d = qs_all.filter(is_active=True).filter(last_login__gte=last_30_days).count()
    taxa_retencao_pct = round((ativos_que_logaram_30d / usuarios_ativos * 100) if usuarios_ativos else 0, 1)

    # Distribuição do último acesso (para gráfico)
    dist_nunca = qs_all.filter(is_active=True, last_login__isnull=True).exclude(is_staff=True).count()
    dist_mais_90d = qs_all.filter(is_active=True, last_login__lt=last_90_days).exclude(last_login__isnull=True).exclude(is_staff=True).count()
    dist_30_90d = qs_all.filter(is_active=True, last_login__gte=last_90_days, last_login__lt=last_30_days).exclude(is_staff=True).count()
    dist_7_30d = qs_all.filter(is_active=True, last_login__gte=last_30_days, last_login__lt=last_7_days).exclude(is_staff=True).count()
    dist_ultimos_7d = qs_all.filter(is_active=True, last_login__gte=last_7_days).exclude(is_staff=True).count()
    _dist_counts = [dist_nunca, dist_mais_90d, dist_30_90d, dist_7_30d, dist_ultimos_7d]
    max_distrib_count = max(_dist_counts) if _dist_counts else 1
    distribuicao_ultimo_acesso = [
        {'label': 'Nunca', 'count': dist_nunca, 'cor': '#94a3b8'},
        {'label': 'Há mais de 90 dias', 'count': dist_mais_90d, 'cor': '#ef4444'},
        {'label': 'Entre 30 e 90 dias', 'count': dist_30_90d, 'cor': '#f59e0b'},
        {'label': 'Entre 7 e 30 dias', 'count': dist_7_30d, 'cor': '#eab308'},
        {'label': 'Últimos 7 dias', 'count': dist_ultimos_7d, 'cor': '#22c55e'},
    ]
    # Para o template calcular % da barra (evita divisão por zero)
    for d in distribuicao_ultimo_acesso:
        d['pct'] = round((d['count'] / max_distrib_count) * 100) if max_distrib_count else 0

    # Cadastros por dia (últimos 30 dias) para gráfico
    join_counts = (
        qs_all.filter(date_joined__gte=last_30_days)
        .annotate(d=TruncDate('date_joined'))
        .values('d')
        .annotate(count=Count('id'))
        .order_by('d')
    )
    join_by_date = {c['d']: c['count'] for c in join_counts if c['d']}
    cadastros_por_dia = []
    max_cadastros = 1
    for i in range(30):
        d = (now.date() - timedelta(days=29 - i))
        cnt = join_by_date.get(d, 0)
        cadastros_por_dia.append({'date': d.strftime('%d/%m'), 'count': cnt})
        if cnt > max_cadastros:
            max_cadastros = cnt

    # Logins (se o modelo existir)
    total_logins_30d = None
    logins_por_dia = []
    max_logins = 1
    has_login_log = False
    try:
        from .models import UserLoginLog
        total_logins_30d = UserLoginLog.objects.filter(created_at__gte=last_30_days).count()
        login_counts = (
            UserLoginLog.objects.filter(created_at__gte=last_30_days)
            .annotate(d=TruncDate('created_at'))
            .values('d')
            .annotate(count=Count('id'))
            .order_by('d')
        )
        login_by_date = {c['d']: c['count'] for c in login_counts if c['d']}
        max_logins = 1
        for i in range(30):
            d = (now.date() - timedelta(days=29 - i))
            cnt = login_by_date.get(d, 0)
            logins_por_dia.append({'date': d.strftime('%d/%m'), 'count': cnt})
            if cnt > max_logins:
                max_logins = cnt
        has_login_log = True
    except Exception:
        pass

    # Por grupo (com contagem)
    grupos_com_count = (
        Group.objects.annotate(count=Count('user'))
        .filter(count__gt=0)
        .order_by('-count')
        .values('id', 'name', 'count')
    )

    # Lista de usuários com filtros + busca
    usuarios = _analise_usuarios_queryset(request)
    grupo_id = request.GET.get('grupo')
    status_filtro = request.GET.get('status', 'ativos')
    uso_filtro = request.GET.get('uso', '')
    busca_query = (request.GET.get('busca') or '').strip()
    if busca_query:
        q_busca = Q(username__icontains=busca_query) | Q(first_name__icontains=busca_query) | Q(last_name__icontains=busca_query) | Q(email__icontains=busca_query)
        usuarios = usuarios.filter(q_busca)
    usuarios = list(usuarios[:200])
    user_ids = [u.id for u in usuarios]

    # Produtividade (Diário de Obra + Gestão de Aprovação) — não só login
    prod_por_usuario = {
        uid: {
            'diarios_criados_30d': 0, 'diarios_revisados_30d': 0, 'pedidos_30d': 0,
            'aprovacoes_30d': 0, 'reprovacoes_30d': 0,
            'diarios_criados_90d': 0, 'pedidos_90d': 0,
            'obras_vinculadas': 0, 'ultima_atividade': None,
        }
        for uid in user_ids
    }
    total_diarios_30d = 0
    total_diarios_90d = 0
    total_pedidos_90d = 0
    total_revisoes_30d = 0
    total_pedidos_30d = 0
    total_aprovacoes_30d = 0
    total_reprovacoes_30d = 0
    total_aprovacoes_ok_30d = 0
    taxa_reprovacao_pct = 0.0
    top10_reprovacoes_solicitante = []
    top10_reprovacoes_obra = []
    usuarios_sem_producao_30d_count = 0
    try:
        from core.models import ConstructionDiary
        if user_ids:
            for row in ConstructionDiary.objects.filter(created_by_id__in=user_ids, created_at__gte=last_30_days).values('created_by_id').annotate(count=Count('id')):
                prod_por_usuario[row['created_by_id']]['diarios_criados_30d'] = row['count']
            total_diarios_30d = ConstructionDiary.objects.filter(created_at__gte=last_30_days).count()
            for row in ConstructionDiary.objects.filter(reviewed_by_id__in=user_ids, approved_at__isnull=False, approved_at__gte=last_30_days).values('reviewed_by_id').annotate(count=Count('id')):
                prod_por_usuario[row['reviewed_by_id']]['diarios_revisados_30d'] = row['count']
            total_revisoes_30d = ConstructionDiary.objects.filter(reviewed_by_id__isnull=False, approved_at__gte=last_30_days).count()
            if user_ids:
                for row in ConstructionDiary.objects.filter(created_by_id__in=user_ids, created_at__gte=last_90_days).values('created_by_id').annotate(count=Count('id')):
                    prod_por_usuario[row['created_by_id']]['diarios_criados_90d'] = row['count']
            total_diarios_90d = ConstructionDiary.objects.filter(created_at__gte=last_90_days).count()
    except Exception:
        pass
    try:
        from gestao_aprovacao.models import WorkOrder, Approval, Obra
        if user_ids:
            for row in WorkOrder.objects.filter(criado_por_id__in=user_ids, created_at__gte=last_30_days).values('criado_por_id').annotate(count=Count('id')):
                prod_por_usuario[row['criado_por_id']]['pedidos_30d'] = row['count']
            total_pedidos_30d = WorkOrder.objects.filter(created_at__gte=last_30_days).count()
            total_pedidos_90d = WorkOrder.objects.filter(created_at__gte=last_90_days).count()
            if user_ids:
                for row in WorkOrder.objects.filter(criado_por_id__in=user_ids, created_at__gte=last_90_days).values('criado_por_id').annotate(count=Count('id')):
                    prod_por_usuario[row['criado_por_id']]['pedidos_90d'] = row['count']
            for row in Approval.objects.filter(aprovado_por_id__in=user_ids, created_at__gte=last_30_days).values('aprovado_por_id').annotate(count=Count('id')):
                prod_por_usuario[row['aprovado_por_id']]['aprovacoes_30d'] = row['count']
            total_aprovacoes_30d = Approval.objects.filter(created_at__gte=last_30_days).count()
            total_aprovacoes_ok_30d = Approval.objects.filter(decisao='aprovado', created_at__gte=last_30_days).count()
            total_reprovacoes_30d = Approval.objects.filter(decisao='reprovado', created_at__gte=last_30_days).count()
            _total_dec = total_aprovacoes_ok_30d + total_reprovacoes_30d
            taxa_reprovacao_pct = round((total_reprovacoes_30d / _total_dec * 100), 1) if _total_dec else 0.0
            for row in Approval.objects.filter(decisao='reprovado', created_at__gte=last_30_days).values('work_order__criado_por_id').annotate(count=Count('id')).order_by('-count')[:10]:
                if row['work_order__criado_por_id']:
                    u = User.objects.filter(pk=row['work_order__criado_por_id']).first()
                    if u:
                        top10_reprovacoes_solicitante.append({'user': u, 'count': row['count']})
            for row in Approval.objects.filter(decisao='reprovado', created_at__gte=last_30_days).values('work_order__obra_id').annotate(count=Count('id')).order_by('-count')[:10]:
                if row['work_order__obra_id']:
                    ob = Obra.objects.filter(pk=row['work_order__obra_id']).first()
                    top10_reprovacoes_obra.append({'obra': ob, 'obra_nome': ob.nome if ob else '—', 'count': row['count']})
            for row in Approval.objects.filter(decisao='reprovado', created_at__gte=last_30_days).values('work_order__criado_por_id').annotate(count=Count('id')):
                if row['work_order__criado_por_id'] and row['work_order__criado_por_id'] in prod_por_usuario:
                    prod_por_usuario[row['work_order__criado_por_id']]['reprovacoes_30d'] = row['count']
        # Usuários ativos que não produziram (0 diários e 0 pedidos em 30d)
        try:
            from core.models import ConstructionDiary
            from gestao_aprovacao.models import WorkOrder
            com_diario = set(ConstructionDiary.objects.filter(created_at__gte=last_30_days).values_list('created_by_id', flat=True))
            com_pedido = set(WorkOrder.objects.filter(created_at__gte=last_30_days).values_list('criado_por_id', flat=True))
            produziram = com_diario | com_pedido
            usuarios_sem_producao_30d_count = User.objects.filter(is_active=True).exclude(id__in=produziram).exclude(is_staff=True).count()
        except Exception:
            pass
    except Exception:
        pass

    # Obras vinculadas (ProjectMember) e última atividade por usuário
    if user_ids:
        try:
            from core.models import ProjectMember
            from django.db.models import Max
            for row in ProjectMember.objects.filter(user_id__in=user_ids).values('user_id').annotate(count=Count('id')):
                prod_por_usuario[row['user_id']]['obras_vinculadas'] = row['count']
        except Exception:
            pass
        try:
            from core.models import ConstructionDiary
            from gestao_aprovacao.models import WorkOrder
            for row in ConstructionDiary.objects.filter(created_by_id__in=user_ids).values('created_by_id').annotate(ultima=Max('created_at')):
                if row['ultima'] and (prod_por_usuario[row['created_by_id']]['ultima_atividade'] is None or row['ultima'] > prod_por_usuario[row['created_by_id']]['ultima_atividade']):
                    prod_por_usuario[row['created_by_id']]['ultima_atividade'] = row['ultima']
            for row in WorkOrder.objects.filter(criado_por_id__in=user_ids).values('criado_por_id').annotate(ultima=Max('created_at')):
                if row['ultima'] and (prod_por_usuario[row['criado_por_id']]['ultima_atividade'] is None or row['ultima'] > prod_por_usuario[row['criado_por_id']]['ultima_atividade']):
                    prod_por_usuario[row['criado_por_id']]['ultima_atividade'] = row['ultima']
        except Exception:
            pass

    # Resumo por sistema (quem usou Diário, Pedidos, ambos ou nenhum em 30d)
    resumo_sistema = {'só_diario': 0, 'só_pedido': 0, 'ambos': 0, 'nenhum': 0}
    try:
        from core.models import ConstructionDiary
        from gestao_aprovacao.models import WorkOrder
        com_diario_30d = set(ConstructionDiary.objects.filter(created_at__gte=last_30_days).values_list('created_by_id', flat=True))
        com_pedido_30d = set(WorkOrder.objects.filter(created_at__gte=last_30_days).values_list('criado_por_id', flat=True))
        ativos_nao_staff = set(User.objects.filter(is_active=True).exclude(is_staff=True).values_list('id', flat=True))
        for uid in ativos_nao_staff:
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

    # Top 5 aprovadores (30d)
    top5_aprovadores = []
    if user_ids:
        aprov_list = [(uid, prod_por_usuario[uid]['aprovacoes_30d']) for uid in user_ids if prod_por_usuario[uid]['aprovacoes_30d'] > 0]
        aprov_list.sort(key=lambda x: -x[1])
        _user_map = {u.id: u for u in User.objects.filter(id__in=[x[0] for x in aprov_list[:5]])}
        top5_aprovadores = [{'user': _user_map.get(uid), 'count': c} for uid, c in aprov_list[:5] if _user_map.get(uid)]

    # Top 5 produtividade (destaques)
    top5_diarios = []
    top5_pedidos = []
    try:
        from core.models import ConstructionDiary
        top5_diarios = list(
            ConstructionDiary.objects.filter(created_at__gte=last_30_days)
            .values('created_by_id')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
        # Resolver usuários
        _user_map = {u.id: u for u in User.objects.filter(id__in=[r['created_by_id'] for r in top5_diarios])}
        top5_diarios = [{'user': _user_map.get(r['created_by_id']), 'count': r['count']} for r in top5_diarios if _user_map.get(r['created_by_id'])]
    except Exception:
        pass
    try:
        from gestao_aprovacao.models import WorkOrder
        top5_pedidos = list(
            WorkOrder.objects.filter(created_at__gte=last_30_days)
            .values('criado_por_id')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
        _user_map = {u.id: u for u in User.objects.filter(id__in=[r['criado_por_id'] for r in top5_pedidos])}
        top5_pedidos = [{'user': _user_map.get(r['criado_por_id']), 'count': r['count']} for r in top5_pedidos if _user_map.get(r['criado_por_id'])]
    except Exception:
        pass

    context = {
        'total_usuarios': total_usuarios,
        'usuarios_ativos': usuarios_ativos,
        'usuarios_inativos': usuarios_inativos,
        'novos_7d': novos_7d,
        'novos_30d': novos_30d,
        'novos_90d': novos_90d,
        'nunca_logaram': nunca_logaram,
        'sem_login_30d': sem_login_30d,
        'sem_login_90d': sem_login_90d,
        'taxa_retencao_pct': taxa_retencao_pct,
        'ativos_que_logaram_30d': ativos_que_logaram_30d,
        'distribuicao_ultimo_acesso': distribuicao_ultimo_acesso,
        'cadastros_por_dia': cadastros_por_dia,
        'max_cadastros': max_cadastros,
        'total_logins_30d': total_logins_30d,
        'logins_por_dia': logins_por_dia,
        'max_logins': max_logins if has_login_log else 1,
        'has_login_log': has_login_log,
        'grupos_com_count': grupos_com_count,
        'usuarios': usuarios,
        'usuarios_com_prod': [
            _row_analise_usuario(u, prod_por_usuario)
            for u in usuarios
        ],
        'total_diarios_30d': total_diarios_30d,
        'total_diarios_90d': total_diarios_90d,
        'total_pedidos_90d': total_pedidos_90d,
        'total_revisoes_30d': total_revisoes_30d,
        'total_pedidos_30d': total_pedidos_30d,
        'total_aprovacoes_30d': total_aprovacoes_30d,
        'total_reprovacoes_30d': total_reprovacoes_30d,
        'total_aprovacoes_ok_30d': total_aprovacoes_ok_30d,
        'taxa_reprovacao_pct': taxa_reprovacao_pct,
        'top10_reprovacoes_solicitante': top10_reprovacoes_solicitante,
        'top10_reprovacoes_obra': top10_reprovacoes_obra,
        'usuarios_sem_producao_30d_count': usuarios_sem_producao_30d_count,
        'top5_diarios': top5_diarios,
        'top5_pedidos': top5_pedidos,
        'top5_aprovadores': top5_aprovadores,
        'resumo_sistema': resumo_sistema,
        'busca_query': busca_query,
        'grupo_id': grupo_id,
        'status_filtro': status_filtro,
        'uso_filtro': uso_filtro,
        'last_30_days_label': '30 dias',
        'last_90_days_label': '90 dias',
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
@user_passes_test(is_staff_or_superuser)
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
@user_passes_test(is_staff_or_superuser)
def criar_obra(request):
    """Cria uma nova obra."""
    if request.method == 'POST':
        codigo_sienge = request.POST.get('codigo_sienge')
        nome = request.POST.get('nome')
        ativa = request.POST.get('ativa') == 'on'
        
        if not codigo_sienge or not nome:
            messages.error(request, 'Código e nome são obrigatórios.')
            return render(request, 'accounts/criar_obra.html')
        
        if Obra.objects.filter(codigo_sienge=codigo_sienge).exists():
            messages.error(request, 'Já existe uma obra com este código.')
            return render(request, 'accounts/criar_obra.html')
        
        obra = Obra.objects.create(
            codigo_sienge=codigo_sienge,
            nome=nome,
            ativa=ativa
        )
        
        messages.success(request, f'Obra "{obra.nome}" criada!')
        return redirect('accounts:admin_central')
    
    return render(request, 'accounts/criar_obra.html')


@login_required
@user_passes_test(is_staff_or_superuser)
def gerenciar_obras(request):
    """Lista e gerencia obras."""
    obras = Obra.objects.all().order_by('nome')
    
    # Filtro
    ativa_filtro = request.GET.get('ativa')
    if ativa_filtro == '1':
        obras = obras.filter(ativa=True)
    elif ativa_filtro == '0':
        obras = obras.filter(ativa=False)
    
    context = {
        'obras': obras,
        'ativa_filtro': ativa_filtro,
    }
    
    return render(request, 'accounts/gerenciar_obras.html', context)

