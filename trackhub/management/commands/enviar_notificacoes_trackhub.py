from datetime import datetime, time

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone

from django.urls import reverse

from core.notification_utils import criar_notificacao as core_criar_notificacao
from trackhub.models import EtapaPendencia, NotificacaoPrazoTrackHub


DIAS_ALERTA = (2, 0)


def _prazo_to_deadline_local(prazo_date):
    if not prazo_date:
        return None
    dt = datetime.combine(prazo_date, time(23, 59, 59))
    return timezone.make_aware(dt, timezone.get_current_timezone())


def _deve_alertar_por_dia(prazo_date, hoje_local, dias_alvo):
    if not prazo_date:
        return False
    delta = (prazo_date - hoje_local).days
    return delta == dias_alvo


def _criar_notificacao(usuario, titulo, mensagem, event_key="", pendencia_pk=None):
    if not usuario or not usuario.is_active:
        return
    try:
        if pendencia_pk:
            url = reverse("trackhub:pendencia_detalhe", args=[pendencia_pk])
        else:
            url = reverse("trackhub:fila")
    except Exception:
        url = "/trackhub/"
    core_criar_notificacao(
        usuario,
        "trackhub_prazo",
        titulo,
        mensagem,
        url=url,
        event_key=event_key or "",
    )


class Command(BaseCommand):
    help = (
        "Envia notificações de prazo do TrackHub (faltam 2 dias e expira hoje) "
        "para responsáveis de etapas."
    )

    def handle(self, *args, **options):
        agora = timezone.localtime()
        hoje = agora.date()
        total = 0

        etapas = (
            EtapaPendencia.objects.filter(prazo__isnull=False, status="pendente")
            .select_related("pendencia", "pendencia__obra", "responsavel_interno")
        )
        for etapa in etapas:
            if not etapa.responsavel_interno_id:
                continue
            deadline = _prazo_to_deadline_local(etapa.prazo)
            if not deadline:
                continue
            for dias in DIAS_ALERTA:
                if not _deve_alertar_por_dia(etapa.prazo, hoje, dias):
                    continue
                try:
                    NotificacaoPrazoTrackHub.objects.create(
                        alvo_tipo="etapa",
                        alvo_id=etapa.pk,
                        usuario=etapa.responsavel_interno,
                        janela_horas=(dias * 24),
                        referencia_prazo=deadline,
                    )
                except IntegrityError:
                    continue
                if dias == 0:
                    titulo = "[TrackHub] Etapa expira hoje"
                    mensagem = (
                        f'A etapa "{etapa.titulo}" da pendência "{etapa.pendencia.titulo}" '
                        f"expira hoje."
                    )
                else:
                    titulo = "[TrackHub] Etapa expira em 2 dias"
                    mensagem = (
                        f'A etapa "{etapa.titulo}" da pendência "{etapa.pendencia.titulo}" '
                        f"expira em 2 dias."
                    )
                _criar_notificacao(
                    etapa.responsavel_interno,
                    titulo,
                    mensagem,
                    event_key=f"trackhub:etapa:{etapa.pk}",
                    pendencia_pk=etapa.pendencia_id,
                )
                total += 1

        self.stdout.write(
            self.style.SUCCESS(f"Notificações TrackHub enviadas: {total}")
        )

