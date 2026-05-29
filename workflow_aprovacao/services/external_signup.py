from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string

from accounts.groups import GRUPOS
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


@transaction.atomic
def create_external_signup_request(
    *,
    process,
    step,
    requester,
    variable_key: str,
    candidate: ExternalCandidate,
):
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
    )
    return req


@transaction.atomic
def approve_external_signup_request(*, request_obj, reviewer, access_url_builder):
    if request_obj.status != ExternalSignupStatus.PENDING:
        raise ValueError('Solicitação não está pendente.')
    linked = find_existing_external_user(
        email=request_obj.email,
        phone_whatsapp=request_obj.phone_whatsapp,
    )
    if not linked:
        username_base = (request_obj.email.split('@')[0] if request_obj.email else 'externo').strip() or 'externo'
        username = username_base[:120]
        suffix = 1
        while User.objects.filter(username=username).exists():
            suffix += 1
            username = f'{username_base[:110]}_{suffix}'
        linked = User.objects.create_user(
            username=username,
            email=request_obj.email,
            password=get_random_string(20),
            first_name='',
            last_name='',
            is_active=True,
        )
        if request_obj.full_name:
            parts = request_obj.full_name.split()
            linked.first_name = parts[0]
            linked.last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
            linked.save(update_fields=['first_name', 'last_name'])
    _ensure_external_group(linked)
    bind_external_user_to_variable_slot(request_obj=request_obj, user=linked)
    request_obj.status = ExternalSignupStatus.APPROVED
    request_obj.reviewed_by = reviewer
    request_obj.review_reason = ''
    request_obj.linked_user = linked
    request_obj.approved_at = timezone.now()
    request_obj.rejected_at = None
    request_obj.save(
        update_fields=[
            'status',
            'reviewed_by',
            'review_reason',
            'linked_user',
            'approved_at',
            'rejected_at',
            'updated_at',
        ]
    )
    access_url = access_url_builder(linked, request_obj.process)
    notify_external_invite(
        process=request_obj.process,
        target_name=request_obj.full_name or linked.username,
        email=request_obj.email,
        phone_whatsapp=request_obj.phone_whatsapp,
        access_url=access_url,
    )
    return linked


@transaction.atomic
def reject_external_signup_request(*, request_obj, reviewer, reason: str):
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
