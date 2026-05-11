from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AtividadePendencia, Pendencia


@receiver(post_save, sender=Pendencia)
def registrar_criacao_pendencia(sender, instance, created, **kwargs):
    if not created:
        return
    AtividadePendencia.objects.create(
        pendencia=instance,
        usuario=instance.criado_por,
        tipo=AtividadePendencia.TIPO_CRIACAO,
        descricao="Criou esta pendência",
    )
