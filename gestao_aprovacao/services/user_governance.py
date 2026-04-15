"""
Agregação de dados para o painel de governança operacional do usuário (administração).
Somente leitura sobre modelos existentes; sem efeitos colaterais.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.db.models import Count, Max
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserLoginLog
from core.models import ConstructionDiary, ProjectMember
from gestao_aprovacao.models import (
    Approval,
    Attachment,
    Comment,
    Empresa,
    Obra,
    StatusHistory,
    UserEmpresa,
    WorkOrder,
    WorkOrderPermission,
)

# Rótulos curtos para painel (códigos desconhecidos mostram o código cru)
AUDIT_ACTION_LABELS_PT: dict[str, str] = {
    'user_created': 'Utilizador criado',
    'user_updated': 'Cadastro alterado',
    'user_deleted': 'Utilizador excluído',
    'user_signup_request_internal': 'Pedido de cadastro (interno)',
    'user_signup_request_public': 'Pedido de cadastro (público)',
    'user_signup_approved': 'Cadastro aprovado',
    'user_signup_rejected': 'Cadastro rejeitado',
    'obra_workorder_perm_add': 'Permissão na obra concedida',
    'obra_workorder_perm_remove': 'Permissão na obra removida',
    'obra_workorder_perm_toggle': 'Permissão na obra ativada/desativada',
    'empresa_created': 'Empresa criada',
    'empresa_updated': 'Empresa alterada',
    'obra_created': 'Obra criada',
    'obra_updated': 'Obra alterada',
    'diary_provisional_edit_granted': 'Edição provisória do RDO liberada',
}


def audit_action_label_pt(action_code: str) -> str:
    if not action_code:
        return '—'
    return AUDIT_ACTION_LABELS_PT.get(action_code, action_code)


def _whole_days_since(dt) -> int | None:
    if not dt:
        return None
    return max(0, (timezone.now() - dt).days)


def viewer_can_see_target_user(viewer, target_user) -> bool:
    """Mesmo recorte conceitual da listagem: admin vê todos; responsável vê só vínculos às suas empresas."""
    from gestao_aprovacao.utils import is_admin, is_responsavel_empresa

    if not viewer.is_authenticated:
        return False
    if is_admin(viewer):
        return True
    if is_responsavel_empresa(viewer) and not is_admin(viewer):
        empresas = Empresa.objects.filter(responsavel=viewer, ativo=True)
        return UserEmpresa.objects.filter(
            usuario=target_user,
            empresa__in=empresas,
            ativo=True,
        ).exists()
    return False


def _date_from_period(days: int | None):
    if days is None or days <= 0:
        return None
    return timezone.now() - timedelta(days=days)


def build_scope(target_user) -> dict[str, Any]:
    perms = (
        WorkOrderPermission.objects.filter(usuario=target_user, ativo=True)
        .select_related('obra', 'obra__empresa')
        .order_by('obra__nome', 'obra__codigo', 'tipo_permissao')
    )
    empresas_v = (
        UserEmpresa.objects.filter(usuario=target_user, ativo=True)
        .select_related('empresa')
        .order_by('empresa__codigo')
    )
    diario_members = (
        ProjectMember.objects.filter(user=target_user)
        .select_related('project')
        .order_by('project__code')
    )
    return {
        'permissoes_obra': list(perms),
        'empresas': list(empresas_v),
        'projetos_diario': list(diario_members),
    }


def build_kpis(target_user, days_window: int = 30) -> dict[str, Any]:
    since = _date_from_period(days_window)
    log_qs = UserLoginLog.objects.filter(user=target_user)
    log_qs_window = log_qs.filter(created_at__gte=since) if since else log_qs

    first_log = log_qs.order_by('created_at').first()
    last_log = log_qs.order_by('-created_at').first()

    def _count_qs(qs, field='created_at'):
        if since:
            qs = qs.filter(**{f'{field}__gte': since})
        return qs.count()

    n_login_window = log_qs_window.count()
    n_wo_created = _count_qs(WorkOrder.objects.filter(criado_por=target_user))
    n_approvals = _count_qs(Approval.objects.filter(aprovado_por=target_user))
    n_comments = _count_qs(Comment.objects.filter(autor=target_user))
    n_status = _count_qs(StatusHistory.objects.filter(alterado_por=target_user))
    n_attach = _count_qs(Attachment.objects.filter(enviado_por=target_user))
    n_diary_created = _count_qs(ConstructionDiary.objects.filter(created_by=target_user), 'created_at')
    n_diary_reviewed = 0
    if since:
        n_diary_reviewed = ConstructionDiary.objects.filter(
            reviewed_by=target_user,
            approved_at__gte=since,
        ).count()
    else:
        n_diary_reviewed = ConstructionDiary.objects.filter(reviewed_by=target_user).exclude(
            approved_at__isnull=True
        ).count()

    actions_window = (
        n_wo_created + n_approvals + n_comments + n_status + n_attach + n_diary_created + n_diary_reviewed
    )

    breakdown_window = {
        'pedidos_criados': n_wo_created,
        'aprovacoes_decisoes': n_approvals,
        'comentarios': n_comments,
        'mudancas_status': n_status,
        'anexos': n_attach,
        'diarios_criados': n_diary_created,
        'diarios_revisados': n_diary_reviewed,
    }
    breakdown_pct: dict[str, float] = {}
    if actions_window > 0:
        for k, v in breakdown_window.items():
            breakdown_pct[k] = round(100.0 * v / actions_window, 1)
    else:
        for k in breakdown_window:
            breakdown_pct[k] = 0.0

    dominant_key = None
    dominant_val = 0
    if actions_window > 0:
        for k, v in breakdown_window.items():
            if v > dominant_val:
                dominant_val = v
                dominant_key = k

    active_login_days = 0
    if log_qs.exists():
        login_day_qs = log_qs
        if since:
            login_day_qs = login_day_qs.filter(created_at__gte=since)
        active_login_days = (
            login_day_qs.annotate(d=TruncDate('created_at')).values('d').distinct().count()
        )
    avg_logins_per_active_day: float | None = None
    if active_login_days > 0 and since:
        avg_logins_per_active_day = round(n_login_window / active_login_days, 2)

    dominant_label_pt = ''
    if dominant_key:
        _dl = {
            'pedidos_criados': 'criação de pedidos',
            'aprovacoes_decisoes': 'decisões de aprovação/reprovação',
            'comentarios': 'comentários em pedidos',
            'mudancas_status': 'mudanças de status',
            'anexos': 'anexos enviados',
            'diarios_criados': 'diários criados',
            'diarios_revisados': 'diários revisados',
        }
        dominant_label_pt = _dl.get(dominant_key, dominant_key)

    total_actions_lifetime = (
        WorkOrder.objects.filter(criado_por=target_user).count()
        + Approval.objects.filter(aprovado_por=target_user).count()
        + Comment.objects.filter(autor=target_user).count()
        + StatusHistory.objects.filter(alterado_por=target_user).count()
        + Attachment.objects.filter(enviado_por=target_user).count()
        + ConstructionDiary.objects.filter(created_by=target_user).count()
        + ConstructionDiary.objects.filter(reviewed_by=target_user).exclude(approved_at__isnull=True).count()
    )

    return {
        'window_days': days_window,
        'logins_window': n_login_window,
        'actions_window': actions_window,
        'total_logins': log_qs.count(),
        'total_actions_lifetime': total_actions_lifetime,
        'first_login_at': first_log.created_at if first_log else None,
        'last_login_at': last_log.created_at if last_log else None,
        'breakdown_window': breakdown_window,
        'breakdown_pct': breakdown_pct,
        'breakdown_dominant_key': dominant_key,
        'breakdown_dominant_count': dominant_val,
        'active_login_days': active_login_days,
        'avg_logins_per_active_day': avg_logins_per_active_day,
        'breakdown_dominant_label_pt': dominant_label_pt,
    }


def build_audit_insights(
    target_user,
    *,
    audit_window_days: int = 90,
    ip_window_days: int = 30,
    recent_audit_limit: int = 5,
    top_actions_limit: int = 5,
) -> dict[str, Any]:
    """
    Resumo para o painel: alvo vs ator na auditoria, módulos, recência, IPs com contexto.
    """
    from audit.models import AuditEvent

    now = timezone.now()
    audit_since = now - timedelta(days=max(audit_window_days, 1))
    ip_since = now - timedelta(days=max(ip_window_days, 1))

    as_subject = AuditEvent.objects.filter(subject_user=target_user, created_at__gte=audit_since)
    n_audit_subject = as_subject.count()
    top_actions_subject = list(
        as_subject.values('action_code')
        .annotate(c=Count('id'))
        .order_by('-c')[:top_actions_limit]
    )

    as_actor = AuditEvent.objects.filter(actor=target_user, created_at__gte=audit_since)
    n_audit_actor = as_actor.count()
    top_actions_actor = list(
        as_actor.values('action_code')
        .annotate(c=Count('id'))
        .order_by('-c')[:top_actions_limit]
    )

    modules_subject = list(
        as_subject.values('module').annotate(c=Count('id')).order_by('-c')[:10]
    )
    _mod_pt = {
        'gestao': 'GestControll',
        'accounts': 'Contas / cadastro',
        'core': 'Diário / Central',
        'admin': 'Administração',
    }
    modules_subject_fmt = [
        {'module': r['module'], 'module_label': _mod_pt.get(r['module'], r['module'] or '—'), 'count': r['c']}
        for r in modules_subject
    ]

    last_log = UserLoginLog.objects.filter(user=target_user).order_by('-created_at').first()
    last_audit_subj = (
        AuditEvent.objects.filter(subject_user=target_user).order_by('-created_at').first()
    )
    last_audit_actor = AuditEvent.objects.filter(actor=target_user).order_by('-created_at').first()

    ip_base = UserLoginLog.objects.filter(user=target_user, created_at__gte=ip_since)
    n_logins_ip_window = ip_base.count()
    distinct_ips = ip_base.exclude(ip_address__isnull=True).values_list('ip_address', flat=True).distinct().count()
    logins_missing_ip = ip_base.filter(ip_address__isnull=True).count()

    ip_ranking = list(
        ip_base.exclude(ip_address__isnull=True)
        .values('ip_address')
        .annotate(n=Count('id'), last_seen=Max('created_at'))
        .order_by('-n', '-last_seen')[:8]
    )

    active_ip_days = (
        ip_base.annotate(d=TruncDate('created_at')).values('d').distinct().count()
        if ip_base.exists()
        else 0
    )

    recent_qs = (
        AuditEvent.objects.filter(subject_user=target_user)
        .select_related('actor')
        .order_by('-created_at')[:recent_audit_limit]
    )
    recent_audit_events: list[dict[str, Any]] = []
    for ev in recent_qs:
        recent_audit_events.append(
            {
                'id': ev.pk,
                'at': ev.created_at,
                'action_code': ev.action_code,
                'action_label': audit_action_label_pt(ev.action_code),
                'module': ev.module,
                'summary': (ev.summary or '')[:240],
                'actor': ev.actor.get_username() if ev.actor_id else '—',
                'detail_url': reverse('central_audit_event_detail', kwargs={'pk': ev.pk}),
            }
        )

    recent_as_actor_qs = (
        AuditEvent.objects.filter(actor=target_user)
        .select_related('subject_user')
        .order_by('-created_at')[:recent_audit_limit]
    )
    recent_audit_as_actor: list[dict[str, Any]] = []
    for ev in recent_as_actor_qs:
        subj = ev.subject_user.get_username() if ev.subject_user_id else '—'
        recent_audit_as_actor.append(
            {
                'id': ev.pk,
                'at': ev.created_at,
                'action_code': ev.action_code,
                'action_label': audit_action_label_pt(ev.action_code),
                'module': ev.module,
                'summary': (ev.summary or '')[:200],
                'subject': subj,
                'detail_url': reverse('central_audit_event_detail', kwargs={'pk': ev.pk}),
            }
        )

    top_actions_subject_fmt = [
        {
            'action_code': r['action_code'],
            'action_label': audit_action_label_pt(r['action_code']),
            'count': r['c'],
        }
        for r in top_actions_subject
    ]
    top_actions_actor_fmt = [
        {
            'action_code': r['action_code'],
            'action_label': audit_action_label_pt(r['action_code']),
            'count': r['c'],
        }
        for r in top_actions_actor
    ]

    return {
        'audit_window_days': audit_window_days,
        'audit_as_subject_count': n_audit_subject,
        'audit_as_actor_count': n_audit_actor,
        'audit_top_actions': top_actions_subject_fmt,
        'audit_top_actions_as_actor': top_actions_actor_fmt,
        'audit_modules_subject': modules_subject_fmt,
        'ip_window_days': ip_window_days,
        'distinct_login_ips': distinct_ips,
        'logins_in_ip_window': n_logins_ip_window,
        'logins_missing_ip': logins_missing_ip,
        'active_ip_days': active_ip_days,
        'ip_ranking': [
            {
                'ip': row['ip_address'],
                'count': row['n'],
                'last_seen': row['last_seen'],
            }
            for row in ip_ranking
        ],
        'recent_audit_events': recent_audit_events,
        'recent_audit_as_actor': recent_audit_as_actor,
        'days_since_last_login_log': _whole_days_since(last_log.created_at) if last_log else None,
        'days_since_last_audit_as_subject': _whole_days_since(last_audit_subj.created_at)
        if last_audit_subj
        else None,
        'days_since_last_audit_as_actor': _whole_days_since(last_audit_actor.created_at)
        if last_audit_actor
        else None,
    }


def build_pending_queues(target_user) -> dict[str, Any]:
    obras_aprovador = list(
        WorkOrderPermission.objects.filter(
            usuario=target_user,
            tipo_permissao='aprovador',
            ativo=True,
        ).values_list('obra_id', flat=True)
    )
    fila_aprovacao = []
    if obras_aprovador:
        fila_aprovacao = list(
            WorkOrder.objects.filter(
                obra_id__in=obras_aprovador,
                status__in=['pendente', 'reaprovacao'],
            )
            .select_related('obra', 'criado_por')
            .order_by('data_envio', 'created_at')[:80]
        )

    rascunhos_solicitante = list(
        WorkOrder.objects.filter(
            criado_por=target_user,
            status__in=['rascunho', 'reprovado'],
        )
        .select_related('obra')
        .order_by('-updated_at')[:40]
    )

    exclusao_solicitada = list(
        WorkOrder.objects.filter(
            solicitado_exclusao=True,
            solicitado_exclusao_por=target_user,
        )
        .select_related('obra')
        .order_by('-solicitado_exclusao_em')[:20]
    )

    return {
        'fila_aprovacao': fila_aprovacao,
        'rascunhos_ou_reprovados': rascunhos_solicitante,
        'exclusoes_solicitadas': exclusao_solicitada,
    }


def build_critical_highlights(target_user, limit: int = 25) -> list[dict[str, Any]]:
    """Reprovações e solicitações de exclusão recentes (dados objetivos)."""
    out: list[dict[str, Any]] = []
    for ap in (
        Approval.objects.filter(aprovado_por=target_user, decisao='reprovado')
        .select_related('work_order', 'work_order__obra')
        .order_by('-created_at')[:limit]
    ):
        out.append(
            {
                'at': ap.created_at,
                'kind': 'reprovacao',
                'label': f"Reprovação no pedido {ap.work_order.codigo}",
                'detail': (ap.comentario or '')[:200],
                'severity': 'danger',
                'reverse': ('gestao:detail_workorder', {'pk': ap.work_order_id}),
            }
        )
    for wo in (
        WorkOrder.objects.filter(solicitado_exclusao_por=target_user, solicitado_exclusao=True)
        .select_related('obra')
        .order_by('-solicitado_exclusao_em')[:limit]
    ):
        if wo.solicitado_exclusao_em:
            out.append(
                {
                    'at': wo.solicitado_exclusao_em,
                    'kind': 'exclusao_solicitada',
                    'label': f"Solicitou exclusão do pedido {wo.codigo}",
                    'detail': (wo.motivo_exclusao or '')[:200],
                    'severity': 'warning',
                    'reverse': ('gestao:detail_workorder', {'pk': wo.pk}),
                }
            )
    out.sort(key=lambda x: x['at'], reverse=True)
    return out[:limit]


def _obra_to_project_id(obra_id: int | None) -> int | None:
    if not obra_id:
        return None
    try:
        o = Obra.objects.only('project_id').get(pk=obra_id)
        return o.project_id
    except Obra.DoesNotExist:
        return None


@dataclass
class TimelineOptions:
    period_days: int  # 0 = sem limite inferior (usa cap por fonte)
    module: str  # '', 'gestao', 'diario', 'contas', 'admin'
    obra_id: int | None
    max_merged: int = 2000
    per_source_cap: int = 400


def build_timeline_events(target_user, opts: TimelineOptions) -> list[dict[str, Any]]:
    date_from = _date_from_period(opts.period_days) if opts.period_days else None
    project_id_filter = _obra_to_project_id(opts.obra_id)

    events: list[dict[str, Any]] = []

    def _append(ev: dict):
        events.append(ev)

    # —— Contas / login ——
    if opts.module in ('', 'contas'):
        qs = UserLoginLog.objects.filter(user=target_user)
        if date_from:
            qs = qs.filter(created_at__gte=date_from)
        qs = qs.order_by('-created_at')[: opts.per_source_cap]
        for row in qs:
            bits = []
            if getattr(row, 'ip_address', None):
                bits.append(f'IP {row.ip_address}')
            ua = (getattr(row, 'user_agent', None) or '').strip()
            if ua:
                bits.append(ua[:120] + ('…' if len(ua) > 120 else ''))
            _append(
                {
                    'at': row.created_at,
                    'module': 'contas',
                    'kind': 'login',
                    'label': 'Login no sistema',
                    'detail': ' · '.join(bits),
                    'severity': 'info',
                    'success': True,
                    'reverse': None,
                }
            )

    # —— Auditoria administrativa (usuário como alvo do evento) ——
    if opts.module in ('', 'admin'):
        from audit.models import AuditEvent

        aqs = AuditEvent.objects.filter(subject_user=target_user).select_related('actor')
        if date_from:
            aqs = aqs.filter(created_at__gte=date_from)
        for row in aqs.order_by('-created_at')[: opts.per_source_cap]:
            actor_l = row.actor.get_username() if row.actor_id else '—'
            if row.action_code == 'user_deleted':
                sev = 'danger'
            elif row.action_code in (
                'obra_workorder_perm_remove',
                'user_signup_request_internal',
                'user_signup_rejected',
            ):
                sev = 'warning'
            elif row.action_code == 'user_signup_approved':
                sev = 'success'
            else:
                sev = 'info'
            _append(
                {
                    'at': row.created_at,
                    'module': 'admin',
                    'kind': row.action_code,
                    'label': row.summary,
                    'detail': f'Registrado por {actor_l} · módulo {row.module}',
                    'severity': sev,
                    'success': True,
                    'reverse': ('central_audit_event_detail', {'pk': row.pk}),
                }
            )

    # —— Gestão ——
    if opts.module in ('', 'gestao'):
        wo_base = WorkOrder.objects.filter(criado_por=target_user).select_related('obra')
        if date_from:
            wo_base = wo_base.filter(created_at__gte=date_from)
        if opts.obra_id:
            wo_base = wo_base.filter(obra_id=opts.obra_id)
        for wo in wo_base.order_by('-created_at')[: opts.per_source_cap]:
            _append(
                {
                    'at': wo.created_at,
                    'module': 'gestao',
                    'kind': 'pedido_criado',
                    'label': f"Pedido {wo.codigo} criado",
                    'detail': wo.obra.nome if wo.obra_id else '',
                    'severity': 'info',
                    'success': True,
                    'reverse': ('gestao:detail_workorder', {'pk': wo.pk}),
                }
            )

        ap_base = Approval.objects.filter(aprovado_por=target_user).select_related('work_order', 'work_order__obra')
        if date_from:
            ap_base = ap_base.filter(created_at__gte=date_from)
        if opts.obra_id:
            ap_base = ap_base.filter(work_order__obra_id=opts.obra_id)
        for ap in ap_base.order_by('-created_at')[: opts.per_source_cap]:
            sev = 'danger' if ap.decisao == 'reprovado' else 'success'
            _append(
                {
                    'at': ap.created_at,
                    'module': 'gestao',
                    'kind': f"aprovacao_{ap.decisao}",
                    'label': f"{'Reprovou' if ap.decisao == 'reprovado' else 'Aprovou'} pedido {ap.work_order.codigo}",
                    'detail': (ap.comentario or '')[:300],
                    'severity': sev,
                    'success': ap.decisao == 'aprovado',
                    'reverse': ('gestao:detail_workorder', {'pk': ap.work_order_id}),
                }
            )

        sh_base = StatusHistory.objects.filter(alterado_por=target_user).select_related(
            'work_order', 'work_order__obra'
        )
        if date_from:
            sh_base = sh_base.filter(created_at__gte=date_from)
        if opts.obra_id:
            sh_base = sh_base.filter(work_order__obra_id=opts.obra_id)
        for sh in sh_base.order_by('-created_at')[: opts.per_source_cap]:
            _append(
                {
                    'at': sh.created_at,
                    'module': 'gestao',
                    'kind': 'mudanca_status',
                    'label': f"Status {sh.work_order.codigo}: {sh.status_anterior or '—'} → {sh.status_novo}",
                    'detail': (sh.observacao or '')[:300],
                    'severity': 'warning',
                    'success': True,
                    'reverse': ('gestao:detail_workorder', {'pk': sh.work_order_id}),
                }
            )

        c_base = Comment.objects.filter(autor=target_user).select_related('work_order', 'work_order__obra')
        if date_from:
            c_base = c_base.filter(created_at__gte=date_from)
        if opts.obra_id:
            c_base = c_base.filter(work_order__obra_id=opts.obra_id)
        for c in c_base.order_by('-created_at')[: opts.per_source_cap]:
            _append(
                {
                    'at': c.created_at,
                    'module': 'gestao',
                    'kind': 'comentario',
                    'label': f"Comentário no pedido {c.work_order.codigo}",
                    'detail': (c.texto or '')[:300],
                    'severity': 'info',
                    'success': True,
                    'reverse': ('gestao:detail_workorder', {'pk': c.work_order_id}),
                }
            )

        at_base = Attachment.objects.filter(enviado_por=target_user).select_related('work_order', 'work_order__obra')
        if date_from:
            at_base = at_base.filter(created_at__gte=date_from)
        if opts.obra_id:
            at_base = at_base.filter(work_order__obra_id=opts.obra_id)
        for a in at_base.order_by('-created_at')[: opts.per_source_cap]:
            _append(
                {
                    'at': a.created_at,
                    'module': 'gestao',
                    'kind': 'anexo',
                    'label': f"Anexo no pedido {a.work_order.codigo}",
                    'detail': a.get_nome_display(),
                    'severity': 'info',
                    'success': True,
                    'reverse': ('gestao:detail_workorder', {'pk': a.work_order_id}),
                }
            )

        ex_base = WorkOrder.objects.filter(solicitado_exclusao_por=target_user, solicitado_exclusao=True).select_related(
            'obra'
        )
        if date_from:
            ex_base = ex_base.filter(solicitado_exclusao_em__gte=date_from)
        if opts.obra_id:
            ex_base = ex_base.filter(obra_id=opts.obra_id)
        for wo in ex_base.order_by('-solicitado_exclusao_em')[: opts.per_source_cap]:
            if wo.solicitado_exclusao_em:
                _append(
                    {
                        'at': wo.solicitado_exclusao_em,
                        'module': 'gestao',
                        'kind': 'exclusao_solicitada',
                        'label': f"Solicitou exclusão — {wo.codigo}",
                        'detail': (wo.motivo_exclusao or '')[:300],
                        'severity': 'warning',
                        'success': True,
                        'reverse': ('gestao:detail_workorder', {'pk': wo.pk}),
                    }
                )

    # —— Diário ——
    if opts.module in ('', 'diario'):
        d_created = ConstructionDiary.objects.filter(created_by=target_user).select_related('project')
        if date_from:
            d_created = d_created.filter(created_at__gte=date_from)
        if project_id_filter:
            d_created = d_created.filter(project_id=project_id_filter)
        for d in d_created.order_by('-created_at')[: opts.per_source_cap]:
            _append(
                {
                    'at': d.created_at,
                    'module': 'diario',
                    'kind': 'diario_criado',
                    'label': f"Diário de obra ({d.project.code}) — {d.date}",
                    'detail': '',
                    'severity': 'info',
                    'success': True,
                    'reverse': ('diary-detail', {'pk': d.pk}),
                }
            )

        d_rev = ConstructionDiary.objects.filter(reviewed_by=target_user).select_related('project')
        if date_from:
            d_rev = d_rev.filter(approved_at__gte=date_from)
        if project_id_filter:
            d_rev = d_rev.filter(project_id=project_id_filter)
        for d in d_rev.order_by('-approved_at')[: opts.per_source_cap]:
            if d.approved_at:
                _append(
                    {
                        'at': d.approved_at,
                        'module': 'diario',
                        'kind': 'diario_revisado',
                        'label': f"Revisão/aprovação de diário ({d.project.code}) — {d.date}",
                        'detail': '',
                        'severity': 'success',
                        'success': True,
                        'reverse': ('diary-detail', {'pk': d.pk}),
                    }
                )

    events.sort(key=lambda x: x['at'], reverse=True)
    return events[: opts.max_merged]


def operational_alerts(target_user, kpis: dict) -> list[dict[str, str]]:
    """Alertas conservadores baseados só em dados presentes."""
    alerts: list[dict[str, str]] = []
    if target_user.is_active and kpis['total_logins'] == 0 and (timezone.now() - target_user.date_joined).days > 7:
        alerts.append(
            {
                'level': 'warning',
                'text': 'Conta ativa sem nenhum login registrado na base de logins (além do possível registro anterior à coleta).',
            }
        )
    if kpis['window_days'] and kpis['logins_window'] == 0 and kpis['actions_window'] == 0:
        alerts.append(
            {
                'level': 'info',
                'text': f"Sem logins nem ações de domínio nos últimos {kpis['window_days']} dias (no escopo rastreado).",
            }
        )
    return alerts


def build_strategic_insights(target_user, kpis: dict, audit: dict) -> list[dict[str, str]]:
    """
    Leitura em linguagem natural a partir dos números (sem previsões nem ML).
    """
    out: list[dict[str, str]] = []
    age_days = (timezone.now() - target_user.date_joined).days

    if kpis.get('actions_window', 0) > 0 and kpis.get('breakdown_dominant_label_pt'):
        out.append(
            {
                'level': 'info',
                'title': 'Onde está o foco operacional',
                'text': (
                    f"Nos últimos {kpis['window_days']} dias, a maior parte da atividade rastreada no GestControll/Diário "
                    f"foi em «{kpis['breakdown_dominant_label_pt']}» "
                    f"({kpis.get('breakdown_dominant_count', 0)} de {kpis['actions_window']} ações)."
                ),
            }
        )

    al = kpis.get('active_login_days') or 0
    if al > 0 and kpis.get('avg_logins_per_active_day'):
        out.append(
            {
                'level': 'info',
                'title': 'Padrão de sessões',
                'text': (
                    f"Em {al} dia(s) distinto(s) com login registrado na janela de {kpis['window_days']} dias, "
                    f"média de {kpis['avg_logins_per_active_day']} login(s) por dia ativo."
                ),
            }
        )

    dlog = audit.get('days_since_last_login_log')
    if dlog is not None and target_user.is_active:
        if dlog > 45:
            out.append(
                {
                    'level': 'warning',
                    'title': 'Trilho de login',
                    'text': f"O último login registado na trilha foi há {dlog} dias — vale confirmar se a conta ainda é usada.",
                }
            )
        elif dlog <= 3 and kpis.get('logins_window', 0) > 0:
            out.append(
                {
                    'level': 'success',
                    'title': 'Presença recente',
                    'text': 'Há registo de login na trilha nos últimos dias.',
                }
            )

    if audit.get('distinct_login_ips', 0) >= 6:
        out.append(
            {
                'level': 'info',
                'title': 'Endereços IP',
                'text': (
                    'Vários IPs distintos no período: comum com teletrabalho, VPN ou mudança de rede. '
                    'Se não for esperado, pode ser sinal de partilha de credenciais.'
                ),
            }
        )

    if audit.get('logins_missing_ip', 0) and audit.get('logins_in_ip_window', 0):
        out.append(
            {
                'level': 'info',
                'title': 'Logins sem IP',
                'text': (
                    f"{audit['logins_missing_ip']} login(s) no período sem IP gravado (registos antigos ou exceção na recolha). "
                    'Os totais de IP só refletem entradas completas.'
                ),
            }
        )

    na = audit.get('audit_as_actor_count', 0)
    ns = audit.get('audit_as_subject_count', 0)
    if na > 15 and age_days > 14:
        out.append(
            {
                'level': 'info',
                'title': 'Papel administrativo',
                'text': (
                    f"Este utilizador executou {na} ação(ões) de auditoria nos últimos {audit.get('audit_window_days', 90)} dias "
                    '(alterações em contas, obras, permissões, etc.). Perfil com impacto administrativo elevado.'
                ),
            }
        )
    if ns > 8:
        out.append(
            {
                'level': 'info',
                'title': 'Mudanças no cadastro',
                'text': (
                    f"Nos últimos {audit.get('audit_window_days', 90)} dias houve {ns} evento(s) de auditoria "
                    'em que este utilizador foi o alvo — convém rever o histórico se houver dúvidas de acesso.'
                ),
            }
        )

    if age_days <= 14 and kpis.get('total_logins', 0) <= 2:
        out.append(
            {
                'level': 'info',
                'title': 'Conta recente',
                'text': 'Cadastro recente: poucos dados acumulados; as métricas ficam mais úteis após algumas semanas de uso.',
            }
        )

    return out


def usage_by_obra_gestao(target_user, limit: int = 12) -> list[dict[str, Any]]:
    """Contagem de interações Gestão por obra (pedidos criados + aprovações + comentários)."""
    from django.db.models import Count

    rows = []
    # Pedidos criados por obra
    for r in (
        WorkOrder.objects.filter(criado_por=target_user)
        .values('obra_id', 'obra__nome', 'obra__codigo')
        .annotate(n=Count('id'))
        .order_by('-n')[:limit]
    ):
        rows.append(
            {
                'obra_id': r['obra_id'],
                'nome': r['obra__nome'],
                'codigo': r['obra__codigo'],
                'pedidos_criados': r['n'],
                'aprovacoes': 0,
                'comentarios': 0,
            }
        )
    by_id = {x['obra_id']: x for x in rows}
    for r in (
        Approval.objects.filter(aprovado_por=target_user)
        .values('work_order__obra_id', 'work_order__obra__nome', 'work_order__obra__codigo')
        .annotate(n=Count('id'))
    ):
        oid = r['work_order__obra_id']
        if oid not in by_id:
            by_id[oid] = {
                'obra_id': oid,
                'nome': r['work_order__obra__nome'],
                'codigo': r['work_order__obra__codigo'],
                'pedidos_criados': 0,
                'aprovacoes': 0,
                'comentarios': 0,
            }
        by_id[oid]['aprovacoes'] += r['n']
    for r in (
        Comment.objects.filter(autor=target_user)
        .values('work_order__obra_id', 'work_order__obra__nome', 'work_order__obra__codigo')
        .annotate(n=Count('id'))
    ):
        oid = r['work_order__obra_id']
        if oid not in by_id:
            by_id[oid] = {
                'obra_id': oid,
                'nome': r['work_order__obra__nome'],
                'codigo': r['work_order__obra__codigo'],
                'pedidos_criados': 0,
                'aprovacoes': 0,
                'comentarios': 0,
            }
        by_id[oid]['comentarios'] += r['n']

    merged = list(by_id.values())
    merged.sort(
        key=lambda x: x['pedidos_criados'] + x['aprovacoes'] + x['comentarios'],
        reverse=True,
    )
    return merged[:limit]
