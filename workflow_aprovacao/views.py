from __future__ import annotations

import io
import json

from typing import Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponseForbidden, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, NoReverseMatch
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.groups import GRUPOS
from accounts.models import UserSignupRequest
from accounts.signup_services import create_signup_request, notify_signup_request_created
from workflow_aprovacao.access import (
    user_can_act_on_workflow_processes,
    user_can_configure_workflow,
    user_can_view_workflow_geolocation,
    user_can_see_central_monitoring_queue,
    user_can_view_process,
    user_is_approver_on_current_step,
    user_is_external_workflow_profile,
    user_should_use_minimal_workflow_shell,
)
from workflow_aprovacao.decorators import (
    require_workflow_act,
    require_workflow_configure,
    require_workflow_module_access,
    workflow_login_required,
)
from workflow_aprovacao.exceptions import InvalidTransitionError
from workflow_aprovacao.forms import DecisionForm, ExternalSignupReviewForm, ManualRequestForm, NewFlowForm
from core.models import Project
from workflow_aprovacao.models import (
    ApprovalConfigBacklog,
    ApprovalConfigBacklogStatus,
    ApprovalFlowDefinition,
    ApprovalIntegrationOutbox,
    ApprovalProcess,
    ApprovalProcessAttachment,
    ApprovalProcessParticipant,
    ApprovalStepParticipant,
    ExternalParticipantSignupRequest,
    ExternalSignupStatus,
    ParticipantRole,
    ProcessCategory,
    ProcessStatus,
    SyncStatus,
)
from workflow_aprovacao.querysets import processes_pending_for_user
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
    build_final_signature_audit,
    latest_final_signature_event,
    render_signature_receipt_pdf,
)
from workflow_aprovacao.services.share import build_process_share_payload
from workflow_aprovacao.services.sienge_display import beautify_stored_summary_for_display, sienge_payload_display_rows
from workflow_aprovacao.services.sync_trigger import trigger_sienge_sync_if_due
from workflow_aprovacao.services.participants import VariableParticipantInput, bind_external_user_to_process_step
from workflow_aprovacao.services.external_signup import (
    ExternalCandidate,
    approve_external_signup_request,
    create_external_signup_request,
    reject_external_signup_request,
)

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
    eligible_group_names = (
        GRUPOS.CENTRAL_APROVACOES_APROVADOR,
        GRUPOS.CENTRAL_APROVACOES_ADMIN,
        GRUPOS.CENTRAL_APROVACOES_EXTERNO,
        GRUPOS.ADMINISTRADOR,
    )
    internal_group_names = {
        GRUPOS.CENTRAL_APROVACOES_APROVADOR,
        GRUPOS.CENTRAL_APROVACOES_ADMIN,
        GRUPOS.ADMINISTRADOR,
    }
    external_group_name = GRUPOS.CENTRAL_APROVACOES_EXTERNO
    users_qs = (
        User.objects.filter(is_active=True, groups__name__in=eligible_group_names)
        .distinct()
        .prefetch_related('groups')
        .order_by('first_name', 'last_name', 'username')
    )

    def _is_technical_account(user) -> bool:
        username = (getattr(user, 'username', '') or '').strip().lower()
        email = (getattr(user, 'email', '') or '').strip().lower()
        first_name = (getattr(user, 'first_name', '') or '').strip().lower()
        last_name = (getattr(user, 'last_name', '') or '').strip().lower()
        full_name = f'{first_name} {last_name}'.strip()
        token = ' '.join([username, email, first_name, last_name]).strip()

        blocked_exact_usernames = {
            'check_embed_header_user',
            'system',
            'sistema',
            'noreply',
            'bot',
        }
        blocked_fragments = (
            'check_',
            'embed_header',
            'system',
            'sistema',
            'noreply',
            'do-not-reply',
            'donotreply',
            'bot',
            'daemon',
            'service',
            '_svc',
            'healthcheck',
            'monitor',
            'dummy',
            'fixture',
            'seed',
            'test',
            'teste',
            'qa',
            'homolog',
        )

        if username in blocked_exact_usernames:
            return True
        if any(frag in token for frag in blocked_fragments):
            return True
        # Conta sem identificação mínima tende a ser técnica/sistema.
        if not full_name and not email:
            return True
        return False

    users_list = []
    for u in users_qs:
        if _is_technical_account(u):
            continue
        group_names = {g.name for g in u.groups.all()}
        is_external = external_group_name in group_names
        is_internal = bool(group_names.intersection(internal_group_names))
        if not is_external and not is_internal:
            continue

        if is_external and not is_internal:
            badge = 'Terceirizado'
        elif GRUPOS.CENTRAL_APROVACOES_ADMIN in group_names or GRUPOS.ADMINISTRADOR in group_names:
            badge = 'Admin'
        else:
            badge = 'Interno'
        full_name = (u.get_full_name() or '').strip()
        if full_name:
            label = full_name
        elif (u.email or '').strip():
            local = u.email.split('@', 1)[0].replace('.', ' ').replace('_', ' ').strip()
            label = local.title() if local else (u.username or '').strip()
        else:
            label = (u.username or '').strip()
        secondary = (u.email or '').strip() or 'Sem e-mail cadastrado'
        users_list.append(
            {
                'id': u.pk,
                'label': label,
                'secondary': secondary,
                'badge': badge,
                'scope': 'external' if is_external and not is_internal else 'internal',
                'sort': (label or u.username).lower(),
            }
        )
    users_list.sort(key=lambda x: x['sort'])
    for item in users_list:
        item.pop('sort', None)
    groups_list = [
        {'id': g.pk, 'label': g.name}
        for g in Group.objects.filter(name__in=internal_group_names).order_by('name')
    ]
    return users_list, groups_list


def _workflow_context(request, extra=None):
    pending_nav_count = 0
    external_signup_pending_count = 0
    if request.user.is_authenticated:
        pending_nav_count = processes_pending_for_user(request.user).count()
        if user_can_configure_workflow(request.user):
            external_signup_pending_count = ExternalParticipantSignupRequest.objects.filter(
                status=ExternalSignupStatus.PENDING,
            ).count()
    ctx = {
        'workflow_show_config_nav': user_can_configure_workflow(request.user),
        'workflow_can_view_geolocation': user_can_view_workflow_geolocation(request.user),
        'workflow_can_act': user_can_act_on_workflow_processes(request.user),
        'workflow_minimal_shell': user_should_use_minimal_workflow_shell(request.user),
        'workflow_external_profile': user_is_external_workflow_profile(request.user),
        'workflow_pending_count': pending_nav_count,
        'workflow_external_signup_pending_count': external_signup_pending_count,
    }
    if extra:
        ctx.update(extra)
    return ctx


def render_workflow_dashboard(request):
    """Painel inicial da Central — indicadores da fila e atalhos."""
    if user_is_external_workflow_profile(request.user):
        return redirect('workflow_aprovacao:pending')
    from workflow_aprovacao.services.dashboard import dashboard_context_for_user

    return render(
        request,
        'workflow_aprovacao/dashboard.html',
        _workflow_context(
            request,
            {
                **dashboard_context_for_user(request.user),
                'page_title': 'Central de Aprovações',
            },
        ),
    )


@require_workflow_module_access
def home(request):
    """
    Entrada em ``/aprovacoes/`` — perfil externo vai direto à fila (Minhas pendências).
    """
    if user_should_use_minimal_workflow_shell(request.user) or user_is_external_workflow_profile(
        request.user
    ):
        return redirect('workflow_aprovacao:pending')
    return render_workflow_dashboard(request)


@require_workflow_module_access
def pending_list(request):
    from workflow_aprovacao.services.inbox import (
        INBOX_DISPLAY_LIMIT,
        TAB_AGUARDANDO,
        TAB_APROVADO,
        TAB_PENDENTE,
        TAB_REPROVADO,
        available_inbox_tabs,
        fetch_inbox_page,
        inbox_filter_options,
    )

    tab = (request.GET.get('aba') or '').strip()
    q = (request.GET.get('q') or '').strip()[:200]
    origin = (request.GET.get('origem') or '').strip()
    project_id = None
    category_id = None
    is_external = user_is_external_workflow_profile(request.user)
    if not is_external:
        if request.GET.get('project', '').strip().isdigit():
            project_id = int(request.GET['project'])
        if request.GET.get('category', '').strip().isdigit():
            category_id = int(request.GET['category'])
    else:
        tab = TAB_PENDENTE
        origin = ''
        q = ''

    processes, filtered_total, tab = fetch_inbox_page(
        request.user,
        tab=tab,
        project_id=project_id,
        category_id=category_id,
        q=q,
        origin=origin,
    )
    filters = inbox_filter_options(request.user)
    show_monitoring = user_can_see_central_monitoring_queue(request.user)

    tab_titles = {
        TAB_PENDENTE: 'Para assinar' if is_external else 'Minhas pendências',
        TAB_APROVADO: 'Aprovados',
        TAB_REPROVADO: 'Reprovados',
        TAB_AGUARDANDO: 'Aguardando na Central',
    }
    ctx = {
        'inbox_tab': tab,
        'inbox_tabs': available_inbox_tabs(request.user),
        'inbox_processes': processes,
        'inbox_filtered_total': filtered_total,
        'inbox_display_limit': INBOX_DISPLAY_LIMIT,
        'inbox_show_assigned_column': tab == TAB_AGUARDANDO,
        'inbox_show_step_column': tab in (TAB_PENDENTE, TAB_AGUARDANDO),
        'filter_q': q,
        'filter_origin': origin,
        'filter_project_id': project_id,
        'filter_category_id': category_id,
        'projects_for_filter': filters['projects'],
        'categories_for_filter': filters['categories'],
        'page_title': 'Assinaturas' if is_external else 'Central de Aprovações',
        'page_subtitle': tab_titles.get(tab, 'Fila'),
        'workflow_show_monitoring_queue': show_monitoring,
        'inbox_external_profile': is_external,
    }
    return render(
        request,
        'workflow_aprovacao/pending_list.html',
        _workflow_context(request, ctx),
    )


@require_workflow_module_access
def process_detail(request, pk):
    from django.db.models import Prefetch

    from workflow_aprovacao.models import ApprovalStepParticipant
    from workflow_aprovacao.services.step_display import build_current_step_display

    process = get_object_or_404(
        ApprovalProcess.objects.select_related(
            'project', 'category', 'current_step', 'flow_definition', 'initiated_by'
        ).prefetch_related(
            'gestao_dispatch__work_order__obra',
            Prefetch(
                'current_step__participants',
                queryset=ApprovalStepParticipant.objects.select_related(
                    'user', 'django_group'
                ).order_by('role', 'pk'),
            ),
        ),
        pk=pk,
    )
    current_step_display = build_current_step_display(process, viewer=request.user)
    if not user_can_view_process(request.user, process):
        return HttpResponseForbidden('Sem permissão para visualizar este processo.')
    can_act = (
        user_can_act_on_workflow_processes(request.user)
        and user_is_approver_on_current_step(request.user, process)
    )
    history = process.history_entries.select_related('actor', 'step').order_by('created_at')

    if request.method == 'POST':
        from django.db import transaction

        from workflow_aprovacao.services.step_access import user_can_decide_on_process

        if not user_can_act_on_workflow_processes(request.user):
            return HttpResponseForbidden('Sem permissão para decidir neste processo.')
        with transaction.atomic():
            process = (
                ApprovalProcess.objects.select_for_update()
                .select_related('current_step', 'flow_definition', 'project', 'category')
                .get(pk=process.pk)
            )
            if not user_can_decide_on_process(request.user, process):
                return HttpResponseForbidden(
                    'Sem permissão para decidir nesta alçada. '
                    'Só pode aprovar ou reprovar se for participante da etapa atual do processo.'
                )
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
                signature_data=form.cleaned_data.get('signature_data') or '',
                geolocation_data=form.cleaned_data.get('geolocation_data') or '',
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
            },
        )

    sienge_attachments: list[dict] = []
    sienge_display_rows: list[dict] = []
    sienge_is_inbound = process.external_entity_type in (
        'sienge_supply_contract',
        'sienge_supply_contract_measurement',
    )
    gestao_dispatch = getattr(process, 'gestao_dispatch', None)
    gestao_is_origin = process.external_entity_type == 'gestao_workorder' or gestao_dispatch is not None
    gestao_snapshot = {}
    gestao_workorder = None
    gestao_detail_url = None
    gestao_attachments: list[dict] = []
    manual_is_origin = process.external_entity_type == 'manual_request'
    manual_attachments: list[dict] = []
    if manual_is_origin:
        from workflow_aprovacao.services.manual_attachments import manual_attachments_for_ui

        manual_attachments = manual_attachments_for_ui(process)
    if gestao_is_origin:
        if gestao_dispatch:
            gestao_snapshot = gestao_dispatch.snapshot_payload or {}
            gestao_workorder = gestao_dispatch.work_order
        elif isinstance(process.external_payload, dict):
            gestao_snapshot = process.external_payload
        from workflow_aprovacao.services.gestao_display import gestao_snapshot_attachments_for_ui

        gestao_attachments = gestao_snapshot_attachments_for_ui(
            gestao_snapshot.get('anexos') if isinstance(gestao_snapshot, dict) else None
        )
        if gestao_workorder:
            from accounts.groups import GRUPOS

            if request.user.is_superuser or request.user.groups.filter(
                name__in=GRUPOS.GESTAO_TODOS
            ).exists():
                gestao_detail_url = reverse('gestao:detail_workorder', kwargs={'pk': gestao_workorder.pk})
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
    external_signup_requests = list(
        ExternalParticipantSignupRequest.objects.filter(process=process)
        .select_related('requester', 'reviewed_by', 'linked_user', 'step')
        .order_by('-created_at')
    )
    final_signature_event = None
    final_signature_audit = None
    if process.status in (ProcessStatus.APPROVED, ProcessStatus.REJECTED):
        final_signature_event = latest_final_signature_event(process)
        final_signature_audit = build_final_signature_audit(final_signature_event)

    process_share = build_process_share_payload(request=request, process=process)

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
                'external_signup_requests': external_signup_requests,
                'gestao_is_origin': gestao_is_origin,
                'gestao_dispatch': gestao_dispatch,
                'gestao_snapshot': gestao_snapshot,
                'gestao_workorder': gestao_workorder,
                'gestao_detail_url': gestao_detail_url,
                'gestao_attachments': gestao_attachments,
                'manual_is_origin': manual_is_origin,
                'manual_attachments': manual_attachments,
                'current_step_display': current_step_display,
                'final_signature_audit': final_signature_audit,
                'process_share': process_share,
                'view_only_not_approver': (
                    process.status == ProcessStatus.AWAITING_STEP
                    and not can_act
                    and user_can_view_process(request.user, process)
                ),
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
    if not user_can_view_process(request.user, process):
        return HttpResponseForbidden('Sem permissão para visualizar este processo.')
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
def manual_process_attachment_download(request, pk, attachment_pk):
    """Descarrega anexo enviado na criação manual do processo."""
    process = get_object_or_404(ApprovalProcess.objects.select_related('project'), pk=pk)
    if not user_can_view_process(request.user, process):
        return HttpResponseForbidden('Sem permissão para visualizar este processo.')
    if process.external_entity_type != 'manual_request':
        raise Http404()
    att = get_object_or_404(
        ApprovalProcessAttachment.objects.filter(process=process),
        pk=attachment_pk,
    )
    if not att.file:
        raise Http404()
    filename = (att.original_name or '').strip() or att.file.name.rsplit('/', 1)[-1] or 'anexo'
    return FileResponse(att.file.open('rb'), as_attachment=True, filename=filename)


@require_workflow_module_access
def process_signature_receipt_pdf(request, pk):
    process = get_object_or_404(
        ApprovalProcess.objects.select_related('project', 'category', 'initiated_by'),
        pk=pk,
    )
    if not user_can_view_process(request.user, process):
        return HttpResponseForbidden('Sem permissão para visualizar este processo.')
    event = latest_final_signature_event(process)
    if not event:
        raise Http404('Sem evento final de assinatura neste processo.')
    pdf = render_signature_receipt_pdf(
        process=process,
        event=event,
        include_geolocation=user_can_view_workflow_geolocation(request.user),
    )
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="comprovante_processo_{process.pk}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    return response


@require_workflow_module_access
def reverse_geocode_address(request):
    from django.http import JsonResponse

    if not user_can_view_workflow_geolocation(request.user):
        return JsonResponse({'error': 'Sem permissão para consultar endereço.'}, status=403)

    from workflow_aprovacao.services.geocoding import enrich_geolocation, google_maps_url
    from workflow_aprovacao.services.signing import _format_geolocation_label

    lat_raw = (request.GET.get('lat') or '').strip()
    lng_raw = (request.GET.get('lng') or '').strip()
    accuracy_raw = (request.GET.get('accuracy_m') or '').strip()
    try:
        latitude = float(lat_raw)
        longitude = float(lng_raw)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Coordenadas inválidas.'}, status=400)
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return JsonResponse({'error': 'Coordenadas fora do intervalo permitido.'}, status=400)

    geo: dict = {
        'latitude': round(latitude, 6),
        'longitude': round(longitude, 6),
        'source': 'browser',
    }
    if accuracy_raw:
        try:
            accuracy = float(accuracy_raw)
            if accuracy > 0:
                geo['accuracy_m'] = round(accuracy, 1)
        except (TypeError, ValueError):
            pass

    geo = enrich_geolocation(geo)
    label = _format_geolocation_label(geo)
    return JsonResponse(
        {
            'address': geo.get('address') or '',
            'maps_url': geo.get('maps_url') or google_maps_url(latitude=latitude, longitude=longitude),
            'label': label,
            'coords': f'{latitude:.6f}, {longitude:.6f}',
        }
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
                'page_subtitle': 'Fluxos',
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
    try:
        external_signup_request_url = reverse('workflow_aprovacao:external_signup_prefill_create')
    except NoReverseMatch:
        try:
            external_signup_request_url = reverse('external_signup_prefill_create')
        except NoReverseMatch:
            external_signup_request_url = '/aprovacoes/config/externos/pre-cadastro/'
    try:
        external_signup_list_url = reverse('workflow_aprovacao:external_signup_requests')
    except NoReverseMatch:
        try:
            external_signup_list_url = reverse('external_signup_requests')
        except NoReverseMatch:
            external_signup_list_url = '/aprovacoes/config/externos/'
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
                'external_signup_request_url': external_signup_request_url,
                'external_signup_list_url': external_signup_list_url,
                'page_title': f'Fluxo · {flow.project.code}',
                'page_subtitle': f'{flow.category.name} · {flow.project.name}',
            },
        ),
    )


@require_workflow_configure
@require_POST
def external_signup_prefill_create(request):
    """
    Pré-cadastro de terceirizado direto da configuração de fluxo.
    Gera solicitação administrativa (sem criar acesso automático).
    """
    payload: dict = {}
    if request.content_type and 'application/json' in request.content_type:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}
    if not isinstance(payload, dict) or not payload:
        payload = request.POST

    full_name = (payload.get('full_name') or '').strip()
    company_name = (payload.get('company_name') or '').strip()
    email = (payload.get('email') or '').strip().lower()
    phone = (payload.get('phone_whatsapp') or '').strip()
    cnpj = (payload.get('cnpj') or '').strip()
    note = (payload.get('note') or '').strip()
    flow_context = (payload.get('flow_context') or '').strip()
    project_id_raw = payload.get('project_id')
    project_code = (payload.get('project_code') or '').strip()
    project_name = (payload.get('project_name') or '').strip()
    category_name = (payload.get('category_name') or '').strip()

    project_id = None
    try:
        project_id = int(project_id_raw) if str(project_id_raw).strip() else None
    except Exception:
        project_id = None
    selected_project_ids: list[int] = []
    if project_id and Project.objects.filter(pk=project_id, is_active=True).exists():
        selected_project_ids = [project_id]

    if not full_name:
        return JsonResponse({'ok': False, 'message': 'Informe o nome completo do terceirizado.'}, status=400)
    if not email:
        return JsonResponse({'ok': False, 'message': 'Informe o e-mail do terceirizado.'}, status=400)

    existing_external = User.objects.filter(
        is_active=True,
        email__iexact=email,
        groups__name=GRUPOS.CENTRAL_APROVACOES_EXTERNO,
    ).first()
    if existing_external:
        display = (existing_external.get_full_name() or existing_external.username or '').strip()
        return JsonResponse(
            {
                'ok': False,
                'message': f'Já existe terceirizado cadastrado com este e-mail: {display}.',
            },
            status=409,
        )

    if UserSignupRequest.objects.filter(
        email__iexact=email,
        status=UserSignupRequest.STATUS_PENDENTE,
    ).exists():
        return JsonResponse(
            {
                'ok': True,
                'message': 'Já existe uma solicitação pendente para este e-mail. Aguarde a aprovação administrativa.',
                'already_pending': True,
            }
        )

    notes = []
    notes.append('Tipo de solicitação: Terceirizado externo (Central de Aprovações)')
    if project_code or project_name:
        notes.append(f'Obra de referência: {(project_code + " - " + project_name).strip(" -")}')
    if category_name:
        notes.append(f'Categoria do fluxo: {category_name}')
    if company_name:
        notes.append(f'Empresa: {company_name}')
    if cnpj:
        notes.append(f'CNPJ: {cnpj}')
    if note:
        notes.append(f'Observação: {note}')
    if flow_context:
        notes.append(f'Contexto do fluxo: {flow_context}')

    signup_request = create_signup_request(
        full_name=full_name,
        email=email,
        phone=phone,
        password='',
        username_suggestion='',
        notes='\n'.join(notes),
        requested_groups=[GRUPOS.CENTRAL_APROVACOES_EXTERNO],
        requested_project_ids=selected_project_ids,
        origem=UserSignupRequest.ORIGEM_INTERNO,
        requested_by=request.user,
    )
    notify_signup_request_created(signup_request)

    return JsonResponse(
        {
            'ok': True,
            'message': 'Solicitação enviada para a Central de Cadastros como terceirizado externo. O acesso só será liberado após aprovação administrativa.',
            'request_id': signup_request.pk,
            'project_id': project_id,
            'project_code': project_code,
            'project_name': project_name,
        }
    )


@require_workflow_module_access
def dashboard(request):
    """Resumo — alias explícito em ``/aprovacoes/painel/``."""
    return render_workflow_dashboard(request)


@require_workflow_module_access
@require_POST
def force_sync(request):
    if not getattr(settings, 'SIENGE_CENTRAL_MANUAL_SYNC_ENABLED', False):
        messages.info(
            request,
            'A importação do Sienge está desligada. Os processos passam a nascer no GestControll.',
        )
        return redirect('workflow_aprovacao:pending')
    if not user_can_configure_workflow(request.user):
        return HttpResponseForbidden('Sem permissão para importar do Sienge.')
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
                'page_subtitle': 'Retorno Sienge',
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
                'page_subtitle': 'Sem fluxo configurado',
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


def _manual_payload_from_form(form: ManualRequestForm) -> dict:
    import json

    payload = {
        'origin': 'manual_request',
        'notes': form.cleaned_data.get('notes') or '',
        'amount': str(form.cleaned_data.get('amount') or ''),
        'vendor_name': form.cleaned_data.get('vendor_name') or '',
    }
    raw = (form.cleaned_data.get('category_payload_json') or '').strip()
    if raw:
        try:
            payload['category_payload'] = json.loads(raw)
        except Exception:
            payload['category_payload'] = {}
    else:
        payload['category_payload'] = {}
    return payload


def _required_variable_slots(flow: ApprovalFlowDefinition):
    return list(
        ApprovalStepParticipant.objects.filter(
            step__flow=flow,
            is_variable=True,
            required_on_create=True,
        )
        .select_related('step')
        .order_by('step__sequence', 'pk')
    )


def _implicit_external_step_for_contract(flow: ApprovalFlowDefinition):
    """
    Fallback de UX: se contrato não tiver slot variável configurado,
    usa a primeira alçada para selecionar o terceirizado manualmente.
    """
    try:
        if (flow.category.code or '').strip().lower() != 'contrato':
            return None
    except Exception:
        return None
    return flow.steps.filter(is_active=True).order_by('sequence', 'pk').first()


def _external_access_url_for_user(user, process: ApprovalProcess) -> str:
    return reverse('workflow_aprovacao:process_detail', kwargs={'pk': process.pk})


def _external_users_for_select():
    """Terceirizados externos ativos com nome e empresa, para o seletor do pedido."""
    users = list(
        User.objects.filter(
            groups__name=GRUPOS.CENTRAL_APROVACOES_EXTERNO,
            is_active=True,
        )
        .order_by('first_name', 'last_name', 'username')
        .distinct()[:500]
    )
    company_by_user: dict = {}
    if users:
        rows = (
            ExternalParticipantSignupRequest.objects
            .filter(linked_user__in=users)
            .exclude(company_name='')
            .order_by('linked_user_id', '-created_at')
            .values_list('linked_user_id', 'company_name')
        )
        for uid, company in rows:
            company_by_user.setdefault(uid, (company or '').strip())
    out = []
    for u in users:
        name = (u.get_full_name() or '').strip() or u.username
        out.append({
            'id': u.pk,
            'name': name,
            'company': company_by_user.get(u.pk, ''),
            'email': (u.email or '').strip(),
        })
    return out


@workflow_login_required
def manual_request_new(request):
    if user_is_external_workflow_profile(request.user):
        return HttpResponseForbidden('Perfil externo não pode criar pedidos manuais.')

    gestao_workorder = None
    gestao_category_payload = {}
    gestao_wo_raw = (request.POST.get('gestao_workorder_id') or request.GET.get('gestao_workorder') or '').strip()

    if gestao_wo_raw.isdigit():
        from gestao_aprovacao.gestao_central_access import user_can_send_workorder_to_central
        from gestao_aprovacao.models import WorkOrder as GestaoWorkOrder
        from gestao_aprovacao.services.central_dispatch import (
            GestaoCentralDispatchDuplicateError,
            GestaoCentralDispatchError,
            build_manual_request_initial,
            link_workorder_to_central_process,
            workorder_dispatch_block_reason,
        )

        gestao_workorder = GestaoWorkOrder.objects.select_related(
            'obra', 'obra__project', 'criado_por'
        ).filter(pk=int(gestao_wo_raw)).first()
        if gestao_workorder and not user_can_send_workorder_to_central(request.user):
            gestao_workorder = None

    from workflow_aprovacao.access import user_in_any_workflow_group

    if gestao_workorder:
        pass
    elif not user_in_any_workflow_group(request.user):
        return HttpResponseForbidden('Sem acesso à Central de Aprovações.')

    form = ManualRequestForm(request.POST or None)
    if request.method != 'POST':
        project_raw = (request.GET.get('project') or '').strip()
        category_raw = (request.GET.get('category') or '').strip()
        initial = {}
        if gestao_workorder:
            prefill = build_manual_request_initial(gestao_workorder)
            initial.update(prefill['initial'])
            gestao_category_payload = prefill.get('category_payload') or {}
            if not project_raw.isdigit() and prefill.get('project'):
                project_raw = str(prefill['project'].pk)
            if not category_raw.isdigit() and prefill.get('category'):
                category_raw = str(prefill['category'].pk)
        if project_raw.isdigit():
            initial['project'] = int(project_raw)
        if category_raw.isdigit():
            initial['category'] = int(category_raw)
        if initial:
            form = ManualRequestForm(initial=initial)
    selected_flow = None
    required_slots = []
    if request.method == 'POST' and form.is_valid():
        selected_flow = ApprovalFlowDefinition.objects.filter(
            project=form.cleaned_data['project'],
            category=form.cleaned_data['category'],
            is_active=True,
        ).select_related('project', 'category').first()
    else:
        project_raw = (request.GET.get('project') or '').strip()
        category_raw = (request.GET.get('category') or '').strip()
        if project_raw.isdigit() and category_raw.isdigit():
            selected_flow = ApprovalFlowDefinition.objects.filter(
                project_id=int(project_raw),
                category_id=int(category_raw),
                is_active=True,
            ).select_related('project', 'category').first()
    if selected_flow:
        required_slots = _required_variable_slots(selected_flow)
    implicit_external_step = None
    if selected_flow and not required_slots:
        implicit_external_step = _implicit_external_step_for_contract(selected_flow)

    if request.method == 'POST':
        if gestao_workorder:
            block = workorder_dispatch_block_reason(gestao_workorder)
            if block:
                messages.error(request, block)
                return redirect('gestao:detail_workorder', pk=gestao_workorder.pk)

        def _manual_request_redirect_url(project_pk, category_pk):
            base = (
                f"{reverse('workflow_aprovacao:manual_request_new')}"
                f"?project={project_pk}&category={category_pk}"
            )
            if gestao_workorder:
                base += f"&gestao_workorder={gestao_workorder.pk}"
            return base

        if not form.is_valid():
            messages.error(request, 'Verifique os campos do formulário.')
        elif not selected_flow:
            messages.error(request, 'Sem fluxo ativo para a obra e categoria selecionadas.')
        else:
            variable_inputs: list[VariableParticipantInput] = []
            pending_candidates: list[tuple[ApprovalStepParticipant, ExternalCandidate]] = []
            implicit_existing_external = None
            implicit_pending_candidate = None
            for slot in required_slots:
                existing_user_raw = (request.POST.get(f'slot_{slot.pk}_existing_user') or '').strip()
                if existing_user_raw.isdigit():
                    user_id = int(existing_user_raw)
                    variable_inputs.append(
                        VariableParticipantInput(
                            step_participant_id=slot.pk,
                            subject_kind=slot.subject_kind,
                            user_id=user_id if slot.subject_kind == 'user' else None,
                            django_group_id=user_id if slot.subject_kind == 'django_group' else None,
                        )
                    )
                    continue
                full_name = (request.POST.get(f'slot_{slot.pk}_full_name') or '').strip()
                email = (request.POST.get(f'slot_{slot.pk}_email') or '').strip().lower()
                phone = (request.POST.get(f'slot_{slot.pk}_phone') or '').strip()
                company = (request.POST.get(f'slot_{slot.pk}_company') or '').strip()
                cnpj = (request.POST.get(f'slot_{slot.pk}_cnpj') or '').strip()
                note = (request.POST.get(f'slot_{slot.pk}_note') or '').strip()
                if not full_name or not email or not company:
                    messages.error(
                        request,
                        f'Para cadastrar um novo terceirizado na alçada {slot.step.sequence}, informe nome, empresa e e-mail.',
                    )
                    return redirect(
                        _manual_request_redirect_url(
                            form.cleaned_data['project'].pk,
                            form.cleaned_data['category'].pk,
                        )
                    )
                pending_candidates.append(
                    (
                        slot,
                        ExternalCandidate(
                            full_name=full_name,
                            company_name=company,
                            email=email,
                            phone_whatsapp=phone,
                            cnpj=cnpj,
                            note=note,
                        ),
                    )
                )
            if implicit_external_step:
                existing_user_raw = (request.POST.get('implicit_external_existing_user') or '').strip()
                if existing_user_raw.isdigit():
                    implicit_existing_external = User.objects.filter(
                        pk=int(existing_user_raw),
                        is_active=True,
                    ).first()
                else:
                    full_name = (request.POST.get('implicit_external_full_name') or '').strip()
                    email = (request.POST.get('implicit_external_email') or '').strip().lower()
                    phone = (request.POST.get('implicit_external_phone') or '').strip()
                    company = (request.POST.get('implicit_external_company') or '').strip()
                    cnpj = (request.POST.get('implicit_external_cnpj') or '').strip()
                    note = (request.POST.get('implicit_external_note') or '').strip()
                    if not full_name or not email or not company:
                        messages.error(request, 'Para o terceirizado responsável da 1ª alçada, informe nome, empresa e e-mail.')
                        return redirect(
                            _manual_request_redirect_url(
                                form.cleaned_data['project'].pk,
                                form.cleaned_data['category'].pk,
                            )
                        )
                    implicit_pending_candidate = ExternalCandidate(
                        full_name=full_name,
                        company_name=company,
                        email=email,
                        phone_whatsapp=phone,
                        cnpj=cnpj,
                        note=note,
                    )
            try:
                process = ApprovalEngine.start(
                    project=form.cleaned_data['project'],
                    category=form.cleaned_data['category'],
                    initiated_by=request.user,
                    title=(form.cleaned_data.get('title') or '').strip()[:300],
                    summary=(form.cleaned_data.get('summary') or '').strip()[:2000],
                    external_system='manual',
                    external_entity_type='manual_request',
                    external_id='',
                    sync_status=SyncStatus.NOT_APPLICABLE,
                    external_payload=_manual_payload_from_form(form),
                    variable_inputs=variable_inputs,
                    allow_missing_required_variables=bool(pending_candidates or implicit_pending_candidate),
                )
            except Exception as exc:
                messages.error(request, str(exc))
            else:
                if implicit_external_step:
                    ApprovalProcessParticipant.objects.filter(
                        process=process,
                        step=implicit_external_step,
                        role=ParticipantRole.APPROVER,
                    ).delete()
                    if implicit_existing_external:
                        bind_external_user_to_process_step(
                            process=process,
                            step=implicit_external_step,
                            user=implicit_existing_external,
                            label='Terceirizado responsável',
                        )
                    elif implicit_pending_candidate:
                        create_external_signup_request(
                            process=process,
                            step=implicit_external_step,
                            requester=request.user,
                            variable_key=f'implicit_step_{implicit_external_step.pk}',
                            candidate=implicit_pending_candidate,
                        )
                for slot, candidate in pending_candidates:
                    create_external_signup_request(
                        process=process,
                        step=slot.step,
                        requester=request.user,
                        variable_key=(slot.variable_key or f'slot_{slot.pk}'),
                        candidate=candidate,
                    )
                from workflow_aprovacao.services.manual_attachments import (
                    MAX_MANUAL_ATTACHMENTS,
                    save_manual_request_attachments,
                )

                uploaded_files = request.FILES.getlist('documento_referencia_files')
                if len(uploaded_files) > MAX_MANUAL_ATTACHMENTS:
                    messages.warning(
                        request,
                        f'Apenas os primeiros {MAX_MANUAL_ATTACHMENTS} documentos foram guardados.',
                    )
                    uploaded_files = uploaded_files[:MAX_MANUAL_ATTACHMENTS]
                if uploaded_files:
                    save_manual_request_attachments(process, uploaded_files, request.user)

                if gestao_workorder:
                    try:
                        manual_payload = _manual_payload_from_form(form)
                        link_workorder_to_central_process(
                            gestao_workorder,
                            process,
                            user=request.user,
                            send_comment=(form.cleaned_data.get('notes') or '').strip(),
                            request=request,
                            manual_payload=manual_payload,
                        )
                    except GestaoCentralDispatchDuplicateError as exc:
                        messages.warning(request, str(exc))
                    except GestaoCentralDispatchError as exc:
                        messages.error(
                            request,
                            f'Pedido #{process.pk} criado na Central, mas não foi possível vincular ao '
                            f'GestControll: {exc}',
                        )
                        return redirect('workflow_aprovacao:process_detail', pk=process.pk)

                pending_count = len(pending_candidates) + (1 if implicit_pending_candidate else 0)
                if gestao_workorder:
                    messages.success(
                        request,
                        f'Pedido GestControll {gestao_workorder.codigo} enviado à Central '
                        f'(processo #{process.pk}).',
                    )
                elif pending_count:
                    messages.warning(
                        request,
                        f'Pedido #{process.pk} criado. {pending_count} cadastro(s) externo(s) aguardam aprovação em '
                        f'«Solicitações externas».',
                    )
                else:
                    messages.success(request, f'Pedido manual #{process.pk} criado com sucesso.')
                return redirect('workflow_aprovacao:process_detail', pk=process.pk)

    page_subtitle = 'Criação manual na Central'
    if gestao_workorder:
        page_subtitle = f'Concluir envio — GestControll {gestao_workorder.codigo}'

    ctx = {
        'form': form,
        'selected_flow': selected_flow,
        'required_variable_slots': required_slots,
        'implicit_external_step': implicit_external_step,
        'category_code_map': {
            str(c.pk): c.code
            for c in ProcessCategory.objects.filter(is_active=True).only('pk', 'code')
        },
        'existing_external_users': _external_users_for_select(),
        'page_title': 'Novo pedido de assinatura',
        'page_subtitle': page_subtitle,
        'gestao_workorder': gestao_workorder,
        'gestao_category_payload': gestao_category_payload,
    }
    return render(
        request,
        'workflow_aprovacao/manual_request_new.html',
        _workflow_context(request, ctx),
    )


@require_workflow_configure
def external_signup_requests_list(request):
    status = (request.GET.get('status') or ExternalSignupStatus.PENDING).strip().lower()
    allowed = {
        ExternalSignupStatus.PENDING,
        ExternalSignupStatus.APPROVED,
        ExternalSignupStatus.REJECTED,
        ExternalSignupStatus.CANCELLED,
        ExternalSignupStatus.INACTIVE,
        'all',
    }
    if status not in allowed:
        status = ExternalSignupStatus.PENDING
    qs = ExternalParticipantSignupRequest.objects.select_related(
        'process',
        'process__project',
        'step',
        'requester',
        'reviewed_by',
        'linked_user',
    )
    if status != 'all':
        qs = qs.filter(status=status)
    q = (request.GET.get('q') or '').strip()
    if q:
        from django.db.models import Q

        qs = qs.filter(
            Q(full_name__icontains=q)
            | Q(email__icontains=q)
            | Q(phone_whatsapp__icontains=q)
            | Q(cnpj__icontains=q)
            | Q(process__title__icontains=q)
            | Q(process__project__code__icontains=q)
        )
    rows = list(qs.order_by('-created_at')[:300])
    from workflow_aprovacao.services.external_credentials_share import build_external_credentials_whatsapp_url

    for row in rows:
        row.whatsapp_credentials_url = ''
        if row.status == ExternalSignupStatus.APPROVED and row.linked_user_id:
            row.whatsapp_credentials_url = build_external_credentials_whatsapp_url(
                request=request,
                signup_request=row,
            )

    signup_status_map = {
        ExternalSignupStatus.PENDING: UserSignupRequest.STATUS_PENDENTE,
        ExternalSignupStatus.APPROVED: UserSignupRequest.STATUS_APROVADO,
        ExternalSignupStatus.REJECTED: UserSignupRequest.STATUS_REJEITADO,
    }
    prefill_qs = (
        UserSignupRequest.objects.select_related('requested_by', 'approved_by', 'approved_user')
        .filter(origem=UserSignupRequest.ORIGEM_INTERNO, workflow_external_signup__isnull=True)
        .order_by('-created_at')
    )
    if status in signup_status_map:
        prefill_qs = prefill_qs.filter(status=signup_status_map[status])
    elif status in (ExternalSignupStatus.CANCELLED, ExternalSignupStatus.INACTIVE):
        prefill_qs = prefill_qs.none()

    prefill_rows = []
    q_norm = q.lower()
    for req in prefill_qs[:800]:
        groups = req.requested_groups or []
        if GRUPOS.CENTRAL_APROVACOES_EXTERNO not in groups:
            continue
        if q:
            hay = ' '.join(
                [
                    req.full_name or '',
                    req.email or '',
                    req.phone or '',
                    req.notes or '',
                ]
            ).lower()
            if q_norm not in hay:
                continue
        prefill_rows.append(req)
        if len(prefill_rows) >= 300:
            break

    return render(
        request,
        'workflow_aprovacao/external_signup_requests.html',
        _workflow_context(
            request,
            {
                'rows': rows,
                'prefill_rows': prefill_rows,
                'filter_status': status,
                'filter_q': q,
                'review_form': ExternalSignupReviewForm(),
                'page_title': 'Solicitações de usuários externos',
                'page_subtitle': 'Cadastro externo para alçadas variáveis',
            },
        ),
    )


@require_workflow_configure
@require_POST
def external_signup_request_review(request, pk):
    row = get_object_or_404(ExternalParticipantSignupRequest, pk=pk)
    form = ExternalSignupReviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Ação inválida para solicitação externa.')
        return redirect('workflow_aprovacao:external_signup_requests')
    action = form.cleaned_data['action']
    reason = (form.cleaned_data.get('reason') or '').strip()
    try:
        if action == 'approve':
            linked = approve_external_signup_request(
                request_obj=row,
                reviewer=request.user,
                access_url_builder=_external_access_url_for_user,
            )
            messages.success(
                request,
                f'Solicitação aprovada e vinculada ao usuário {linked.username}. '
                f'E-mail de credenciais enviado automaticamente. '
                f'Use «Enviar login por WhatsApp» se o terceirizado não receber o e-mail. '
                f'A solicitação também foi atualizada em Central de Cadastros.',
            )
            return redirect(f'{reverse("workflow_aprovacao:external_signup_requests")}?status=aprovado')
        else:
            reject_external_signup_request(request_obj=row, reviewer=request.user, reason=reason)
            messages.warning(request, 'Solicitação externa rejeitada.')
            return redirect(f'{reverse("workflow_aprovacao:external_signup_requests")}?status=rejeitado')
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect('workflow_aprovacao:external_signup_requests')
