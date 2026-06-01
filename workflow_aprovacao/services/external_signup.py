from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone

from accounts.groups import GRUPOS
from accounts.models import UserSignupRequest
from workflow_aprovacao.models import (
    ExternalParticipantSignupRequest,
    ExternalSignupStatus,
)
from workflow_aprovacao.services.notifications import notify_external_invite
from workflow_aprovacao.services.participants import bind_external_user_to_variable_slot

User = get_user_model()


@dataclass(frozen=True)
class ExternalCandidate:
    full_name: str
    company_name: str
    email: str
    phone_whatsapp: str
    cnpj: str = ''
    note: str = ''


def find_existing_external_user(*, email: str, phone_whatsapp: str):
    email_norm = (email or '').strip().lower()
    phone_norm = ''.join(ch for ch in (phone_whatsapp or '') if ch.isdigit())
    qs = User.objects.filter(is_active=True).order_by('id')
    if email_norm:
        hit = qs.filter(email__iexact=email_norm).first()
        if hit:
            return hit
    if phone_norm:
        hit = qs.filter(perfil__telefone__icontains=phone_norm).first()
        if hit:
            return hit
    return None


def _ensure_external_group(user):
    group, _ = Group.objects.get_or_create(name=GRUPOS.CENTRAL_APROVACOES_EXTERNO)
    user.groups.add(group)


def _build_central_signup_notes(*, process, candidate: ExternalCandidate) -> str:
    lines = [
        'Tipo de solicitação: Terceirizado externo (Central de Aprovações)',
        f'Pedido workflow #{process.pk}: {(process.title or "").strip() or "Sem título"}',
        f'Obra: {process.project.code} — {process.project.name}',
    ]
    if candidate.company_name:
        lines.append(f'Empresa: {candidate.company_name}')
    if candidate.cnpj:
        lines.append(f'CNPJ: {candidate.cnpj}')
    if candidate.note:
        lines.append(f'Observação: {candidate.note}')
    return '\n'.join(lines)


def _ensure_central_signup_request(*, process, candidate: ExternalCandidate, requester):
    """Cria ou reutiliza solicitação pendente na Central de Cadastros."""
    from accounts.signup_services import create_signup_request, notify_signup_request_created

    email = (candidate.email or '').strip().lower()
    pending = UserSignupRequest.objects.filter(
        email__iexact=email,
        status=UserSignupRequest.STATUS_PENDENTE,
    ).first()
    if pending:
        if not ExternalParticipantSignupRequest.objects.filter(central_signup_request=pending).exists():
            return pending

    central = create_signup_request(
        full_name=(candidate.full_name or '').strip(),
        email=email,
        phone=(candidate.phone_whatsapp or '').strip(),
        notes=_build_central_signup_notes(process=process, candidate=candidate),
        requested_groups=[GRUPOS.CENTRAL_APROVACOES_EXTERNO],
        requested_project_ids=[process.project_id] if process.project_id else [],
        origem=UserSignupRequest.ORIGEM_INTERNO,
        requested_by=requester,
    )
    try:
        notify_signup_request_created(central)
    except Exception:
        pass
    return central


def _sync_central_signup_approved(*, request_obj, linked, reviewer):
    central = request_obj.central_signup_request
    if not central or central.status != UserSignupRequest.STATUS_PENDENTE:
        return
    central.status = UserSignupRequest.STATUS_APROVADO
    central.approved_by = reviewer
    central.approved_user = linked
    central.approved_at = timezone.now()
    central.rejected_at = None
    central.rejection_reason = ''
    central.save(
        update_fields=[
            'status',
            'approved_by',
            'approved_user',
            'approved_at',
            'rejected_at',
            'rejection_reason',
            'updated_at',
        ]
    )


def _sync_central_signup_rejected(*, request_obj, reviewer, reason: str):
    central = request_obj.central_signup_request
    if not central or central.status != UserSignupRequest.STATUS_PENDENTE:
        return
    central.status = UserSignupRequest.STATUS_REJEITADO
    central.approved_by = reviewer
    central.approved_user = None
    central.rejection_reason = (reason or '').strip()
    central.rejected_at = timezone.now()
    central.save(
        update_fields=[
            'status',
            'approved_by',
            'approved_user',
            'rejection_reason',
            'rejected_at',
            'updated_at',
        ]
    )


@transaction.atomic
def create_external_signup_request(
    *,
    process,
    step,
    requester,
    variable_key: str,
    candidate: ExternalCandidate,
):
    central = _ensure_central_signup_request(
        process=process,
        candidate=candidate,
        requester=requester,
    )
    req = ExternalParticipantSignupRequest.objects.create(
        process=process,
        step=step,
        requester=requester,
        variable_key=(variable_key or '').strip().lower(),
        full_name=(candidate.full_name or '').strip(),
        company_name=(candidate.company_name or '').strip(),
        email=(candidate.email or '').strip().lower(),
        phone_whatsapp=(candidate.phone_whatsapp or '').strip(),
        cnpj=(candidate.cnpj or '').strip(),
        note=(candidate.note or '').strip(),
        status=ExternalSignupStatus.PENDING,
        central_signup_request=central,
    )
    return req


@transaction.atomic
def approve_external_signup_request(*, request_obj, reviewer, access_url_builder):
    if request_obj.status != ExternalSignupStatus.PENDING:
        raise ValueError('Solicitação não está pendente.')
    created_new_user = False
    plain_password = ''
    linked = find_existing_external_user(
        email=request_obj.email,
        phone_whatsapp=request_obj.phone_whatsapp,
    )
    if not linked:
        from accounts.signup_services import build_default_password, build_unique_username

        username = build_unique_username('', request_obj.email)
        first_name = ''
        last_name = ''
        if request_obj.full_name:
            parts = request_obj.full_name.split()
            first_name = parts[0]
            last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
        plain_password = build_default_password(first_name, last_name)
        linked = User.objects.create_user(
            username=username,
            email=request_obj.email,
            password=plain_password,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        created_new_user = True
    _ensure_external_group(linked)
    central = request_obj.central_signup_request
    if central:
        from accounts.signup_services import apply_signup_access_bindings

        apply_signup_access_bindings(
            linked,
            requested_groups=central.requested_groups,
            requested_project_ids=central.requested_project_ids,
        )
    bind_external_user_to_variable_slot(request_obj=request_obj, user=linked)
    request_obj.status = ExternalSignupStatus.APPROVED
    request_obj.reviewed_by = reviewer
    request_obj.review_reason = ''
    request_obj.linked_user = linked
    request_obj.created_linked_user = created_new_user
    request_obj.approved_at = timezone.now()
    request_obj.rejected_at = None
    request_obj.save(
        update_fields=[
            'status',
            'reviewed_by',
            'review_reason',
            'linked_user',
            'created_linked_user',
            'approved_at',
            'rejected_at',
            'updated_at',
        ]
    )
    _sync_central_signup_approved(request_obj=request_obj, linked=linked, reviewer=reviewer)
    access_url = access_url_builder(linked, request_obj.process)
    if created_new_user and plain_password and (request_obj.email or '').strip():
        try:
            from gestao_aprovacao.email_utils import enviar_email_credenciais_novo_usuario

            enviar_email_credenciais_novo_usuario(
                email_destino=request_obj.email,
                username=linked.username,
                senha_plana=plain_password,
                nome_completo=request_obj.full_name or linked.get_full_name(),
            )
        except Exception:
            pass
    notify_external_invite(
        process=request_obj.process,
        target_name=request_obj.full_name or linked.username,
        email=request_obj.email,
        phone_whatsapp=request_obj.phone_whatsapp,
        access_url=access_url,
        skip_whatsapp=True,
    )
    return linked


@transaction.atomic
def complete_workflow_external_from_central(*, workflow_request, user, reviewer, access_url_builder, user_was_created=True):
    """Conclui vínculo no pedido workflow após aprovação na Central de Cadastros."""
    if workflow_request.status != ExternalSignupStatus.PENDING:
        return workflow_request
    _ensure_external_group(user)
    bind_external_user_to_variable_slot(request_obj=workflow_request, user=user)
    workflow_request.status = ExternalSignupStatus.APPROVED
    workflow_request.reviewed_by = reviewer
    workflow_request.review_reason = ''
    workflow_request.linked_user = user
    workflow_request.created_linked_user = bool(user_was_created)
    workflow_request.approved_at = timezone.now()
    workflow_request.rejected_at = None
    workflow_request.save(
        update_fields=[
            'status',
            'reviewed_by',
            'review_reason',
            'linked_user',
            'created_linked_user',
            'approved_at',
            'rejected_at',
            'updated_at',
        ]
    )
    access_url = access_url_builder(user, workflow_request.process)
    notify_external_invite(
        process=workflow_request.process,
        target_name=workflow_request.full_name or user.username,
        email=workflow_request.email,
        phone_whatsapp=workflow_request.phone_whatsapp,
        access_url=access_url,
        skip_whatsapp=True,
    )
    return workflow_request


@transaction.atomic
def reject_external_signup_request(*, request_obj, reviewer, reason: str, skip_central_sync: bool = False):
    if request_obj.status != ExternalSignupStatus.PENDING:
        raise ValueError('Solicitação não está pendente.')
    request_obj.status = ExternalSignupStatus.REJECTED
    request_obj.reviewed_by = reviewer
    request_obj.review_reason = (reason or '').strip()
    request_obj.rejected_at = timezone.now()
    request_obj.save(
        update_fields=[
            'status',
            'reviewed_by',
            'review_reason',
            'rejected_at',
            'updated_at',
        ]
    )
    if not skip_central_sync:
        _sync_central_signup_rejected(request_obj=request_obj, reviewer=reviewer, reason=reason)


def reject_workflow_external_from_central(*, signup_request, reviewer, reason: str):
    """Rejeita pedido workflow vinculado após rejeição na Central de Cadastros."""
    workflow_request = getattr(signup_request, 'workflow_external_signup', None)
    if not workflow_request or workflow_request.status != ExternalSignupStatus.PENDING:
        return
    reject_external_signup_request(
        request_obj=workflow_request,
        reviewer=reviewer,
        reason=reason,
        skip_central_sync=True,
    )
