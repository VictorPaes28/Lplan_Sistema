from __future__ import annotations

import json

from typing import Optional

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from workflow_aprovacao.access import (
    user_can_act_on_workflow_processes,
    user_can_configure_workflow,
    user_in_any_workflow_group,
    user_should_use_minimal_workflow_shell,
)
from workflow_aprovacao.decorators import (
    require_workflow_act,
    require_workflow_configure,
    require_workflow_module_access,
)
from workflow_aprovacao.exceptions import InvalidTransitionError
from workflow_aprovacao.forms import CommentForm, NewFlowForm
from core.models import Project
from workflow_aprovacao.models import (
    ApprovalConfigBacklog,
    ApprovalConfigBacklogStatus,
    ApprovalFlowDefinition,
    ApprovalProcess,
    ProcessCategory,
    ProcessStatus,
)
from workflow_aprovacao.querysets import processes_inbox_snapshot, processes_pending_for_user
from workflow_aprovacao.services.backlog import dismiss_backlog, reopen_backlog, try_start_from_backlog
from workflow_aprovacao.services.engine import ApprovalEngine
from workflow_aprovacao.services.flow_config import (
    FlowConfigError,
    apply_flow_configuration,
    flow_structure_locked,
    serialize_flow_for_editor,
)

User = get_user_model()


def _workflow_select_options():
    users_qs = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
    users_list = []
    for u in users_qs:
        label = (u.get_full_name() or '').strip() or u.username
        users_list.append({'id': u.pk, 'label': f'{label} ({u.username})'})
    groups_list = [{'id': g.pk, 'label': g.name} for g in Group.objects.order_by('name')]
    return users_list, groups_list


def _workflow_context(request, extra=None):
    ctx = {
        'workflow_show_config_nav': user_can_configure_workflow(request.user),
        'workflow_can_act': user_can_act_on_workflow_processes(request.user),
        'workflow_minimal_shell': user_should_use_minimal_workflow_shell(request.user),
    }
    if user_can_configure_workflow(request.user):
        ctx['workflow_backlog_pending_count'] = ApprovalConfigBacklog.objects.filter(
            status=ApprovalConfigBacklogStatus.PENDING
        ).count()
    if extra:
        ctx.update(extra)
    return ctx


@login_required(login_url='/accounts/login/')
def home(request):
    """Entrada: redireciona para a fila de pendentes."""
    if not user_in_any_workflow_group(request.user):
        return HttpResponseForbidden('Sem acesso à Central de Aprovações.')
    return redirect('workflow_aprovacao:pending')


@require_workflow_module_access
def pending_list(request):
    pending, recent = processes_inbox_snapshot(request.user, limit=30)
    pending_count = pending.count()
    ctx = {
        'pending': pending,
        'recent': recent,
        'pending_count': pending_count,
        'page_title': 'Central de Aprovações',
        'page_subtitle': 'Sua fila de aprovação e últimas movimentações',
    }
    if pending_count == 0 and user_can_configure_workflow(request.user):
        ctx['workflow_fila_empty_stats'] = {
            'awaiting_total': ApprovalProcess.objects.filter(
                status=ProcessStatus.AWAITING_STEP
            ).count(),
            'sienge_inbound_total': ApprovalProcess.objects.filter(
                external_entity_type__in=(
                    'sienge_supply_contract',
                    'sienge_supply_contract_measurement',
                )
            ).count(),
        }
    return render(
        request,
        'workflow_aprovacao/pending_list.html',
        _workflow_context(request, ctx),
    )


@require_workflow_module_access
def process_detail(request, pk):
    process = get_object_or_404(
        ApprovalProcess.objects.select_related(
            'project', 'category', 'current_step', 'flow_definition', 'initiated_by'
        ),
        pk=pk,
    )
    can_act = ApprovalEngine.user_can_act_on_current_step(process, request.user)
    history = process.history_entries.select_related('actor', 'step').order_by('created_at')

    if request.method == 'POST' and can_act:
        if not user_can_act_on_workflow_processes(request.user):
            return HttpResponseForbidden('Sem permissão para decidir neste processo.')
        form = CommentForm(request.POST)
        action = request.POST.get('action')
        if form.is_valid() and action in ('approve', 'reject'):
            comment = form.cleaned_data.get('comment') or ''
            try:
                if action == 'approve':
                    ApprovalEngine.approve(process, user=request.user, comment=comment)
                    messages.success(request, 'Aprovação registrada.')
                else:
                    ApprovalEngine.reject(process, user=request.user, comment=comment)
                    messages.warning(request, 'Reprovação registrada.')
                return redirect('workflow_aprovacao:process_detail', pk=process.pk)
            except InvalidTransitionError as e:
                messages.error(request, str(e))
        elif not form.is_valid():
            pass
        else:
            messages.error(request, 'Ação inválida.')
    else:
        form = CommentForm()

    return render(
        request,
        'workflow_aprovacao/process_detail.html',
        _workflow_context(
            request,
            {
                'process': process,
                'history': history,
                'form': form,
                'can_act': can_act,
                'page_title': process.title or f'Processo #{process.pk}',
                'page_subtitle': f'{process.project.code} · {process.category.name}',
            },
        ),
    )


@require_workflow_configure
def config_flow_list(request):
    flows = (
        ApprovalFlowDefinition.objects.select_related('project', 'category')
        .order_by('project__code', 'category__sort_order')
    )
    form = NewFlowForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        flow = ApprovalFlowDefinition.objects.create(
            project=form.cleaned_data['project'],
            category=form.cleaned_data['category'],
            is_active=True,
        )
        messages.success(request, 'Fluxo criado. Configure as alçadas e participantes abaixo.')
        return redirect(reverse('workflow_aprovacao:flow_edit', args=[flow.pk]))

    return render(
        request,
        'workflow_aprovacao/config_flow_list.html',
        _workflow_context(
            request,
            {
                'flows': flows,
                'new_flow_form': form,
                'page_title': 'Configuração de fluxos',
                'page_subtitle': 'Obra, categoria, alçadas e aprovadores',
            },
        ),
    )


@require_workflow_configure
def flow_edit(request, pk):
    flow = get_object_or_404(
        ApprovalFlowDefinition.objects.select_related('project', 'category'),
        pk=pk,
    )
    locked = flow_structure_locked(flow)
    users_list, groups_list = _workflow_select_options()

    if request.method == 'POST':
        raw = (request.POST.get('config_payload') or '').strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            messages.error(request, 'Formato inválido. Recarregue a página e tente novamente.')
        else:
            try:
                apply_flow_configuration(flow, payload, structure_locked=locked)
            except FlowConfigError as e:
                messages.error(request, str(e))
            else:
                messages.success(request, 'Configuração gravada com sucesso.')
                return redirect('workflow_aprovacao:flow_edit', pk=flow.pk)

    initial = serialize_flow_for_editor(flow)
    return render(
        request,
        'workflow_aprovacao/flow_edit.html',
        _workflow_context(
            request,
            {
                'flow': flow,
                'structure_locked': locked,
                'initial_config': initial,
                'users_for_select': users_list,
                'groups_for_select': groups_list,
                'page_title': f'Fluxo · {flow.project.code}',
                'page_subtitle': f'{flow.category.name} · {flow.project.name}',
            },
        ),
    )


@require_workflow_module_access
def dashboard(request):
    """Resumo: contagem de pendentes e atalhos."""
    pending_qs = processes_pending_for_user(request.user)
    return render(
        request,
        'workflow_aprovacao/dashboard.html',
        _workflow_context(
            request,
            {
                'pending_count': pending_qs.count(),
                'page_title': 'Central de Aprovações',
                'page_subtitle': 'Resumo',
            },
        ),
    )


def _flow_pk_for_project_category(project, category) -> Optional[int]:
    fdef = ApprovalFlowDefinition.objects.filter(
        project=project,
        category=category,
    ).first()
    return fdef.pk if fdef else None


@require_workflow_configure
def config_backlog_list(request):
    """Fila administrativa: pendências que precisam de fluxo/alçadas antes de virar processo."""
    status = (request.GET.get('status') or 'pending').strip().lower()
    if status not in ('pending', 'dismissed', 'resolved', 'all'):
        status = 'pending'

    qs = ApprovalConfigBacklog.objects.select_related(
        'project', 'category', 'linked_process', 'resolved_by'
    )
    if status != 'all':
        qs = qs.filter(status=status)

    pid = (request.GET.get('project') or '').strip()
    if pid.isdigit():
        qs = qs.filter(project_id=int(pid))
    cid = (request.GET.get('category') or '').strip()
    if cid.isdigit():
        qs = qs.filter(category_id=int(cid))

    q = (request.GET.get('q') or '').strip()
    if q:
        from django.db.models import Q

        qs = qs.filter(
            Q(title__icontains=q)
            | Q(external_id__icontains=q)
            | Q(summary__icontains=q)
            | Q(project__code__icontains=q)
        )

    items = list(qs.order_by('-updated_at')[:250])
    for row in items:
        row.flow_edit_pk = _flow_pk_for_project_category(row.project, row.category)

    filter_project_id = int(pid) if pid.isdigit() else None
    filter_category_id = int(cid) if cid.isdigit() else None

    return render(
        request,
        'workflow_aprovacao/config_backlog_list.html',
        _workflow_context(
            request,
            {
                'backlog_items': items,
                'filter_status': status,
                'filter_project_id': filter_project_id,
                'filter_category_id': filter_category_id,
                'filter_q': q,
                'projects_for_filter': Project.objects.filter(is_active=True).order_by('code')[:400],
                'categories_for_filter': ProcessCategory.objects.filter(is_active=True).order_by(
                    'sort_order', 'name'
                ),
                'page_title': 'Pendências de configuração',
                'page_subtitle': 'Itens recebidos sem fluxo ativo na obra/categoria — fila para o administrador',
            },
        ),
    )


@require_workflow_configure
@require_POST
def config_backlog_dismiss(request, pk):
    backlog = get_object_or_404(ApprovalConfigBacklog, pk=pk)
    note = (request.POST.get('note') or '').strip()[:2000]
    dismiss_backlog(backlog, user=request.user, note=note)
    messages.success(request, 'Pendência marcada como dispensada.')
    return redirect('workflow_aprovacao:config_backlog_list')


@require_workflow_configure
@require_POST
def config_backlog_reopen(request, pk):
    backlog = get_object_or_404(ApprovalConfigBacklog, pk=pk)
    reopen_backlog(backlog)
    messages.success(request, 'Pendência reaberta para análise.')
    return redirect('workflow_aprovacao:config_backlog_list')


@require_workflow_configure
@require_POST
def config_backlog_retry(request, pk):
    backlog = get_object_or_404(ApprovalConfigBacklog, pk=pk)
    proc, err = try_start_from_backlog(backlog, initiated_by=request.user)
    if err:
        messages.error(request, err)
    else:
        messages.success(request, f'Processo #{proc.pk} criado com sucesso.')
    return redirect('workflow_aprovacao:config_backlog_list')
