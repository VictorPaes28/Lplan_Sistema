from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from gestao_aprovacao.models import Obra

from .models import AtividadeImpedimento, Impedimento, StatusImpedimento


STATUS_PADRAO = [
    {"nome": "Não iniciado", "cor": "#6B7280", "ordem": 1},
    {"nome": "Em progresso", "cor": "#3B82F6", "ordem": 2},
    {"nome": "Finalizado", "cor": "#16A34A", "ordem": 3},
]


@receiver(post_save, sender=Obra)
def criar_status_padrao_obra(sender, instance, created, **kwargs):
    if not created:
        return

    for idx, payload in enumerate(STATUS_PADRAO):
        StatusImpedimento.objects.get_or_create(
            obra=instance,
            nome=payload["nome"],
            defaults={
                "cor": payload["cor"],
                "ordem": payload["ordem"],
                "is_default": idx == 0,
            },
        )


@receiver(pre_save, sender=Impedimento)
def impedimento_presave_status_track(sender, instance, **kwargs):
    if instance.pk:
        prev = (
            Impedimento.objects.filter(pk=instance.pk)
            .values_list("status_id", flat=True)
            .first()
        )
        instance._imp_prev_status_id = prev
    else:
        instance._imp_prev_status_id = None


@receiver(post_save, sender=Impedimento)
def impedimento_postsave_ultima_conclusao(sender, instance, created, **kwargs):
    ultimo = (
        StatusImpedimento.objects.filter(obra_id=instance.obra_id)
        .order_by("-ordem")
        .first()
    )
    if not ultimo:
        return
    old_id = getattr(instance, "_imp_prev_status_id", None)
    new_id = instance.status_id
    if new_id != ultimo.id:
        return
    if not created and old_id == ultimo.id:
        return
    Impedimento.objects.filter(pk=instance.pk).update(
        ultima_conclusao_em=timezone.now()
    )


@receiver(post_save, sender=Impedimento)
def registrar_criacao_impedimento(sender, instance, created, **kwargs):
    if not created:
        return
    if not instance.criado_por_id:
        return
    AtividadeImpedimento.objects.create(
        impedimento=instance,
        usuario=instance.criado_por,
        tipo="criacao",
        descricao="Criou esta restrição",
    )
