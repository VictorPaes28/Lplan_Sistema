from __future__ import annotations

import io
import json

from typing import Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponseForbidden, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from workflow_aprovacao.access import (
    user_can_act_on_workflow_processes,
    user_can_configure_workflow,
    user_should_use_minimal_workflow_shell,
)
from workflow_aprovacao.decorators import (
    require_workflow_act,
    require_workflow_configure,
    require_workflow_module_access,
)
from workflow_aprovacao.exceptions import InvalidTransitionError
from workflow_aprovacao.forms import DecisionForm, NewFlowForm
from core.models import Project
from workflow_aprovacao.models import (
    ApprovalConfigBacklog,
    ApprovalConfigBacklogStatus,
    ApprovalFlowDefinition,
    ApprovalIntegrationOutbox,
    ApprovalProcess,
    ProcessCategory,
    ProcessStatus,
    SiengeCentralSyncState,
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
from workflow_aprovacao.services.outbound_dispatch import dispatch_outbox_entry_now
from workflow_aprovacao.services.signing import (
    build_signature_evidence,
    latest_final_signature_event,
    render_signature_receipt_pdf,
)
from workflow_aprovacao.services.sienge_display import beautify_stored_summary_for_display, sienge_payload_display_rows
from workflow_aprovacao.services.sync_trigger import trigger_sienge_sync_if_due

User = get_user_model()


def _sienge_document_number_from_process(process: ApprovalProcess) -> tuple[str, str]:
    """Extrai documentId e contractNumber do ``external_id`` (prefixo ``c|`` ou ``m|``)."""
    ext = (process.external_id or '').strip()
    parts = ext.split('|')
    if ext.startswith('c|') and len(parts) >= 3:
        return parts[1].strip(), parts[2].strip()
    if ext.startswith('m|') and len(parts) >= 3:
        return parts[1].strip(), parts[2].strip()
    return '', ''


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


def render_workflow_dashboard(request):
    """Painel inicial da Central — contadores, atalhos e estado do sync."""
    pending_qs = processes_pending_for_user(request.user)
    sync_state = SiengeCentralSyncState.objects.filter(pk=1).first()
    return render(
        request,
        'workflow_aprovacao/dashboard.html',
        _workflow_context(
            request,
            {
                'pending_count': pending_qs.count(),
                'page_title': 'Central de Aprovações',
                'page_subtitle': 'Resumo',
                'sienge_beat_enabled': getattr(settings, 'SIENGE_CENTRAL_BEAT_ENABLED', False),
                'sienge_sync_state': sync_state,
            },
        ),
    )


@require_workflow_module_access
def home(request):
    """
    Entrada em ``/aprovacoes/`` — mesma página que ``/painel/`` (visão geral),
    antes de navegar para a fila de pendências ou configurações.
    """
    return render_workflow_dashboard(request)


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
        form = DecisionForm(request.POST)
        action = request.POST.get('action')
        if form.is_valid() and action in ('approve', 'reject'):
            form.validate_for_action(action=action, user=request.user, process_id=process.pk)
        if form.is_valid() and action in ('approve', 'reject'):
            comment = form.cleaned_data.get('comment') or ''
            signer_name = (form.cleaned_data.get('signer_name') or '').strip()
            evidence = build_signature_evidence(
                request=request,
                process=process,
                action=action,
                comment=comment,
                signer_name=signer_name,
            )
            try:
                if action == 'approve':
                    ApprovalEngine.approve(
                        process,
                        user=request.user,
                        comment=comment,
                        decision_payload={'signature_evidence': evidence},
                    )
                    messages.success(request, 'Assinatura de aprovação registrada com sucesso.')
                else:
                    ApprovalEngine.reject(
                        process,
                        user=request.user,
                        comment=comment,
                        decision_payload={'signature_evidence': evidence},
                    )
                    messages.warning(request, 'Assinatura de reprovação registrada com sucesso.')
                return redirect('workflow_aprovacao:process_detail', pk=process.pk)
            except InvalidTransitionError as e:
                messages.error(request, str(e))
        elif not form.is_valid():
            pass
        else:
            messages.error(request, 'Ação inválida.')
    else:
        form = DecisionForm(
            initial={
                'signer_name': (request.user.get_full_name() or '').strip() or request.user.username,
            }
        )

    sienge_attachments: list[dict] = []
    sienge_display_rows: list[dict] = []
    sienge_is_inbound = process.external_entity_type in (
        'sienge_supply_contract',
        'sienge_supply_contract_measurement',
    )
    if sienge_is_inbound:
        sienge_display_rows = sienge_payload_display_rows(
            process.external_payload or {},
            external_entity_type=process.external_entity_type or '',
        )
        doc_id, ctr_num = _sienge_document_number_from_process(process)
        if doc_id and ctr_num:
            try:
                from workflow_aprovacao.services.sienge_api import SiengeCentralApiClient

                api = SiengeCentralApiClient()
                sienge_attachments = api.fetch_supply_contract_attachments_index(
                    document_id=doc_id, contract_number=ctr_num
                )[:25]
            except Exception:
                sienge_attachments = []

    if sienge_is_inbound and (process.summary or '').strip():
        sienge_resumo_exibicao = beautify_stored_summary_for_display(str(process.summary))
    else:
        sienge_resumo_exibicao = process.summary or ''

    latest_outbox = (
        ApprovalIntegrationOutbox.objects.filter(process=process)
        .order_by('-created_at')
        .first()
    )

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
                'sienge_attachments': sienge_attachments,
                'sienge_display_rows': sienge_display_rows,
                'sienge_is_inbound': sienge_is_inbound,
                'sienge_resumo_exibicao': sienge_resumo_exibicao,
                'latest_outbox': latest_outbox,
            },
        ),
    )


@require_workflow_module_access
def sienge_process_attachment_download(request, pk):
    """
    Descarrega anexo do contrato no Sienge (mesmo acesso ao módulo que ver o processo).

    Query: ``attachment_id`` (inteiro Sienge). Se omitido, tenta o primeiro anexo listado.
    """
    process = get_object_or_404(ApprovalProcess.objects.select_related('project'), pk=pk)
    if process.external_entity_type not in (
        'sienge_supply_contract',
        'sienge_supply_contract_measurement',
    ):
        raise Http404()
    doc_id, ctr_num = _sienge_document_number_from_process(process)
    if not doc_id or not ctr_num:
        raise Http404()

    from workflow_aprovacao.services.sienge_api import (
        SiengeCentralApiClient,
        attachment_id_from_normalized_row,
    )

    client = SiengeCentralApiClient()
    meta = client.fetch_supply_contract_attachments_index(
        document_id=doc_id, contract_number=ctr_num
    )
    raw_aid = (request.GET.get('attachment_id') or '').strip()
    chosen_id: int | None = None
    if raw_aid.isdigit():
        want = int(raw_aid)
        for row in meta:
            got = attachment_id_from_normalized_row(row)
            if got is not None and got == want:
                chosen_id = got
                break
        if chosen_id is None:
            raise Http404('Anexo não encontrado para este contrato.')
    else:
        for row in meta:
            got = attachment_id_from_normalized_row(row)
            if got is not None:
                chosen_id = got
                break
        if chosen_id is None:
            raise Http404('Nenhum anexo listado no Sienge para este contrato.')

    try:
        content, ctype, fname = client.download_supply_contract_attachment(
            document_id=doc_id,
            contract_number=ctr_num,
            attachment_id=chosen_id,
        )
    except Exception:
        raise Http404('Não foi possível obter o ficheiro no Sienge.')

    resp = FileResponse(io.BytesIO(content), content_type=ctype, as_attachment=True, filename=fname)
    resp['Cache-Control'] = 'private, no-store'
    return resp


@require_workflow_module_access
def process_signature_receipt_pdf(request, pk):
    process = get_object_or_404(
        ApprovalProcess.objects.select_related('project', 'category'),
        pk=pk,
    )
    event = latest_final_signature_event(process)
    if not event:
        raise Http404('Sem evento final de assinatura neste processo.')
    pdf = render_signature_receipt_pdf(process=process, event=event)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="comprovante_processo_{process.pk}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    return response


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
    """Resumo — alias explícito em ``/aprovacoes/painel/``."""
    return render_workflow_dashboard(request)


@require_workflow_module_access
@require_POST
def force_sync(request):
    result = trigger_sienge_sync_if_due(initiated_by=request.user, force=True)
    status = result.get('status')
    if status == 'ok':
        messages.success(request, 'Sincronização com Sienge concluída com sucesso.')
    elif status == 'skipped_running':
        messages.info(request, 'Já existe uma sincronização em andamento. Aguarde alguns minutos.')
    else:
        messages.error(request, f'Falha ao sincronizar com Sienge: {result.get("error") or "erro desconhecido"}')

    target = (request.POST.get('next') or '').strip()
    if not target or not url_has_allowed_host_and_scheme(
        url=target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        target = reverse('workflow_aprovacao:dashboard')
    return redirect(target)


@require_workflow_configure
def outbox_list(request):
    status = (request.GET.get('status') or 'pending').strip().lower()
    allowed = {'pending', 'failed', 'sent', 'all'}
    if status not in allowed:
        status = 'pending'

    qs = ApprovalIntegrationOutbox.objects.select_related(
        'process',
        'process__project',
        'process__category',
    ).order_by('-created_at')
    if status != 'all':
        qs = qs.filter(status=status)
    entries = list(qs[:250])

    return render(
        request,
        'workflow_aprovacao/outbox_list.html',
        _workflow_context(
            request,
            {
                'entries': entries,
                'filter_status': status,
                'page_title': 'Retorno para Sienge',
                'page_subtitle': 'Fila de saída com revisão manual',
                'outbox_shadow_mode': getattr(settings, 'SIENGE_OUTBOUND_SHADOW_MODE', True),
                'outbox_enabled': getattr(settings, 'SIENGE_OUTBOUND_ENABLED', False),
            },
        ),
    )


@require_workflow_configure
@require_POST
def outbox_dispatch(request, pk):
    entry = get_object_or_404(ApprovalIntegrationOutbox, pk=pk)
    force = (request.POST.get('force') or '').strip() in ('1', 'true', 'on', 'yes')
    result = dispatch_outbox_entry_now(outbox_id=entry.pk, actor=request.user, force=force)

    status = result.get('status')
    if status == 'ok':
        mode = result.get('mode') or 'shadow'
        if mode == 'shadow':
            messages.success(request, 'Envio simulado concluído (shadow mode).')
        else:
            messages.success(request, 'Envio para o Sienge concluído.')
    elif status == 'skipped_sent':
        messages.info(request, result.get('message') or 'Este item já foi enviado.')
    else:
        messages.error(request, result.get('message') or 'Falha ao enviar para o Sienge.')

    target = (request.POST.get('next') or '').strip()
    if not target or not url_has_allowed_host_and_scheme(
        url=target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        target = reverse('workflow_aprovacao:outbox_list')
    return redirect(target)


def _flow_pk_for_project_category(project, category) -> Optional[int]:
    fdef = ApprovalFlowDefinition.objects.filter(
        project=project,
        category=category,
    ).first()
    return fdef.pk if fdef else None


BACKLOG_LIST_PAGE_SIZE = 250


@require_workflow_configure
def config_backlog_list(request):
    """Fila administrativa: pendências que precisam de fluxo/alçadas antes de virar processo."""
    status = (request.GET.get('status') or 'pending').strip().lower()
    if status not in ('pending', 'dismissed', 'resolved', 'all'):
        status = 'pending'

    backlog_counts_qs = ApprovalConfigBacklog.objects.values('status').annotate(n=Count('id'))
    backlog_counts_by_status = {row['status']: row['n'] for row in backlog_counts_qs}
    backlog_grand_total = sum(backlog_counts_by_status.values())

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

    backlog_filtered_total = qs.count()
    items = list(qs.order_by('-updated_at')[:BACKLOG_LIST_PAGE_SIZE])
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
                'backlog_filtered_total': backlog_filtered_total,
                'backlog_display_limit': BACKLOG_LIST_PAGE_SIZE,
                'backlog_counts_by_status': backlog_counts_by_status,
                'backlog_grand_total': backlog_grand_total,
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
