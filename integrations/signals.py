from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from accounts.models import UserSignupRequest
from core.models import ConstructionDiary, DiaryStatus, Project
from gestao_aprovacao.models import Attachment, WorkOrder
from integrations.services import dispatch_event_on_commit


def _site_url() -> str:
    return (getattr(settings, "SITE_URL", "") or "").rstrip("/")


@receiver(pre_save, sender=WorkOrder)
def _track_workorder_previous_status(sender, instance: WorkOrder, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    previous = WorkOrder.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    instance._previous_status = previous


@receiver(post_save, sender=WorkOrder)
def _workorder_event_handler(sender, instance: WorkOrder, created: bool, **kwargs):
    status = instance.status
    previous = getattr(instance, "_previous_status", None)
    if created:
        dispatch_event_on_commit(
            event_type="workorder_created",
            source="workorder_signal",
            actor_id=instance.criado_por_id,
            payload={
                "title": f"Novo pedido {instance.codigo}",
                "details": f"Status inicial: {instance.get_status_display()}",
                "reference_type": "workorder",
                "reference_id": instance.id,
                "link": f"{_site_url()}/gestao/pedidos/{instance.id}/" if _site_url() else "",
            },
        )
        return
    if previous == status:
        return
    event_type = f"workorder_status_{status}"
    dispatch_event_on_commit(
        event_type=event_type,
        source="workorder_signal",
        actor_id=instance.criado_por_id,
        payload={
            "title": f"Pedido {instance.codigo} atualizado",
            "details": f"Status: {previous or 'n/a'} -> {status}",
            "reference_type": "workorder",
            "reference_id": instance.id,
            "link": f"{_site_url()}/gestao/pedidos/{instance.id}/" if _site_url() else "",
            "ponto": {"codigo": instance.codigo},
            "geo": {"obra_id": instance.obra_id},
        },
    )


@receiver(pre_save, sender=UserSignupRequest)
def _track_signup_previous_status(sender, instance: UserSignupRequest, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    previous = UserSignupRequest.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    instance._previous_status = previous


@receiver(post_save, sender=UserSignupRequest)
def _signup_event_handler(sender, instance: UserSignupRequest, created: bool, **kwargs):
    if created:
        dispatch_event_on_commit(
            event_type="signup_request_created",
            source="signup_signal",
            actor_id=instance.requested_by_id,
            payload={
                "title": "Nova solicitação de cadastro",
                "details": f"{instance.full_name} ({instance.email})",
                "reference_type": "signup_request",
                "reference_id": instance.id,
                "link": f"{_site_url()}/central/cadastros/" if _site_url() else "",
            },
        )
        return
    previous = getattr(instance, "_previous_status", None)
    if previous == instance.status:
        return
    dispatch_event_on_commit(
        event_type=f"signup_request_{instance.status}",
        source="signup_signal",
        actor_id=instance.approved_by_id or instance.requested_by_id,
        payload={
            "title": f"Solicitação de cadastro {instance.status}",
            "details": f"{instance.full_name} ({instance.email})",
            "reference_type": "signup_request",
            "reference_id": instance.id,
        },
    )


@receiver(pre_save, sender=ConstructionDiary)
def _track_diary_previous_status(sender, instance: ConstructionDiary, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    previous = ConstructionDiary.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    instance._previous_status = previous


@receiver(post_save, sender=ConstructionDiary)
def _diary_event_handler(sender, instance: ConstructionDiary, created: bool, **kwargs):
    if instance.status != DiaryStatus.APROVADO:
        return
    previous = getattr(instance, "_previous_status", None)
    if not created and previous == DiaryStatus.APROVADO:
        return
    dispatch_event_on_commit(
        event_type="construction_diary_approved",
        source="diary_signal",
        actor_id=instance.reviewed_by_id or instance.created_by_id,
        payload={
            "title": f"Diário aprovado #{instance.report_number or instance.id}",
            "details": f"Projeto: {instance.project.name} - Data: {instance.date}",
            "reference_type": "construction_diary",
            "reference_id": instance.id,
            "link": f"{_site_url()}/diaries/{instance.id}/" if _site_url() else "",
            "file_name": f"RDO_{instance.project.code}_{instance.date}.pdf",
        },
    )


@receiver(post_save, sender=Project)
def _project_event_handler(sender, instance: Project, created: bool, **kwargs):
    dispatch_event_on_commit(
        event_type="project_created" if created else "project_updated",
        source="project_signal",
        payload={
            "title": f"Obra {'criada' if created else 'atualizada'}",
            "details": f"{instance.code} - {instance.name}",
            "reference_type": "project",
            "reference_id": instance.id,
        },
    )


@receiver(post_save, sender=Attachment)
def _attachment_event_handler(sender, instance: Attachment, created: bool, **kwargs):
    if not created:
        return
    file_name = instance.nome or ""
    if not file_name and getattr(instance, "arquivo", None):
        file_name = instance.arquivo.name.rsplit("/", 1)[-1]
    if not file_name:
        return
    dispatch_event_on_commit(
        event_type="workorder_attachment_uploaded",
        source="attachment_signal",
        actor_id=instance.enviado_por_id,
        payload={
            "title": f"Novo anexo no pedido {instance.work_order.codigo}",
            "details": file_name,
            "reference_type": "workorder",
            "reference_id": instance.work_order_id,
            "file_name": file_name,
            "version_label": f"r{instance.versao_reaprovacao}",
        },
    )

