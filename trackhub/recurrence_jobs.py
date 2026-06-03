"""Criação de pendências a partir de modelos recorrentes (usado pelo comando agendado)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.db import transaction
from django.utils import timezone

from trackhub.models import EtapaPendencia, Pendencia, PendenciaRecorrente
from trackhub.recurrence import proxima_data_estrita_depois


def dias_intervalo_prazo_versus_criacao_serie(rec: PendenciaRecorrente) -> int | None:
    """Dias entre prazo e data de criação da pendência original; fallback legado `prazo_offset_dias`."""
    if rec.prazo_original and rec.data_criacao_original:
        return (rec.prazo_original - rec.data_criacao_original).days
    if rec.prazo_offset_dias is not None:
        return int(rec.prazo_offset_dias)
    return None


def ref_date_para_etapas_snapshot(pendencia, prazo_offset_dias_serie):
    """
    Data de referência para calcular prazo_offset_dias de cada etapa no snapshot.
    Preferência: data início efetiva da pendência; fallback legado via prazo da série.
    """
    try:
        return pendencia.data_inicio_efetiva
    except AttributeError:
        pass
    if pendencia.prazo is not None and prazo_offset_dias_serie is not None:
        try:
            return pendencia.prazo - timedelta(days=int(prazo_offset_dias_serie))
        except (TypeError, ValueError, OverflowError):
            pass
    if pendencia.prazo:
        return pendencia.prazo
    return timezone.localdate()


def etapas_snapshot_from_pendencia(pendencia, ref_date):
    out = []
    for e in pendencia.etapas.order_by("ordem"):
        off = None
        if e.prazo:
            off = (e.prazo - ref_date).days
        out.append(
            {
                "titulo": e.titulo,
                "responsavel_interno_id": e.responsavel_interno_id,
                "observacao": e.observacao or "",
                "requer_assinatura": bool(e.requer_assinatura),
                "prazo_offset_dias": off,
            }
        )
    return out


def sync_recorrencia_etapas_snapshot_if_linked(pendencia_id: int) -> None:
    """
    Atualiza `etapas_snapshot` na série quando a pendência está ligada por `recorrencia_serie`.
    Não altera pendências já geradas; só o modelo usado nas próximas execuções do comando.
    """
    p = (
        Pendencia.objects.filter(pk=pendencia_id)
        .select_related("recorrencia_serie")
        .prefetch_related("etapas")
        .first()
    )
    if not p or not p.recorrencia_serie_id:
        return
    rec = p.recorrencia_serie
    if not rec.ativo or rec.regra == PendenciaRecorrente.REGRA_NONE:
        return
    ref = ref_date_para_etapas_snapshot(p, dias_intervalo_prazo_versus_criacao_serie(rec))
    snap = etapas_snapshot_from_pendencia(p, ref)
    rec.etapas_snapshot = snap
    rec.prazo_original = p.prazo
    rec.data_inicio_original = p.data_inicio_efetiva
    rec.hora_inicio_original = p.hora_inicio
    rec.hora_fim_original = p.hora_fim
    if p.created_at:
        rec.data_criacao_original = timezone.localtime(p.created_at).date()
    rec.save(
        update_fields=[
            "etapas_snapshot",
            "prazo_original",
            "data_inicio_original",
            "data_criacao_original",
            "hora_inicio_original",
            "hora_fim_original",
            "updated_at",
        ]
    )


@transaction.atomic
def criar_ocorrencia_e_avancar(rec: PendenciaRecorrente, dia_execucao, notificar_fn) -> Pendencia | None:
    """
    Cria uma pendência a partir do snapshot e avança `proxima_execucao`.
    `notificar_fn(pendencia, autor)` — ex.: trackhub.views._notificar_criacao_pendencia
    """
    rec = PendenciaRecorrente.objects.select_for_update().get(pk=rec.pk)
    if not rec.ativo or rec.regra == PendenciaRecorrente.REGRA_NONE:
        return None

    # Data da ocorrência em processamento (sempre usar isto para prazo/etapas, nunca "hoje" nem proxima_execucao genérica)
    if isinstance(dia_execucao, datetime):
        data_ocorrencia = timezone.localtime(dia_execucao).date()
    else:
        data_ocorrencia = dia_execucao

    prazo = None
    if rec.prazo_original and rec.data_criacao_original:
        intervalo = rec.prazo_original - rec.data_criacao_original
        prazo = data_ocorrencia + intervalo
    elif rec.prazo_offset_dias is not None:
        prazo = data_ocorrencia + timedelta(days=int(rec.prazo_offset_dias))

    data_inicio = data_ocorrencia
    if rec.data_inicio_original and rec.data_criacao_original:
        data_inicio = data_ocorrencia + (rec.data_inicio_original - rec.data_criacao_original)

    p = Pendencia.objects.create(
        obra_id=rec.obra_id,
        titulo=rec.titulo,
        descricao=rec.descricao or "",
        tipo=rec.tipo,
        prioridade=rec.prioridade,
        data_inicio=data_inicio,
        prazo=prazo,
        hora_inicio=rec.hora_inicio_original,
        hora_fim=rec.hora_fim_original,
        criado_por=rec.criado_por,
        origem="manual",
        status="aberta",
        recorrencia_serie=rec,
    )

    for idx, snap in enumerate(rec.etapas_snapshot or []):
        ep_off = snap.get("prazo_offset_dias")
        ep_prazo = None
        if ep_off is not None:
            try:
                ep_prazo = data_ocorrencia + timedelta(days=int(ep_off))
            except (TypeError, ValueError):
                ep_prazo = None
        EtapaPendencia.objects.create(
            pendencia=p,
            titulo=(snap.get("titulo") or "Etapa")[:200],
            ordem=idx,
            responsavel_interno_id=snap.get("responsavel_interno_id") or None,
            observacao=(snap.get("observacao") or "")[:5000],
            requer_assinatura=bool(snap.get("requer_assinatura")),
            prazo=ep_prazo,
        )

    from trackhub.views import recalcular_status_pendencia

    recalcular_status_pendencia(p)
    if notificar_fn:
        notificar_fn(p, rec.criado_por)

    prox = proxima_data_estrita_depois(
        data_ocorrencia,
        rec.regra,
        parametros=rec.parametros_json or {},
        dia_semana=rec.dia_semana,
        dia_mes=rec.dia_mes,
        mes=rec.mes,
    )
    rec.proxima_execucao = prox
    rec.save(update_fields=["proxima_execucao", "updated_at"])
    return p


def processar_todas_recorrencias(hoje=None, max_burst_por_serie: int = 1):
    """Dispara todas as séries com proxima_execucao <= hoje (com recuperação de atrasos)."""
    from trackhub.views import _notificar_criacao_pendencia

    hoje = hoje or timezone.localdate()
    total = 0
    qs = (
        PendenciaRecorrente.objects.filter(ativo=True)
        .exclude(regra=PendenciaRecorrente.REGRA_NONE)
        .filter(proxima_execucao__lte=hoje)
        .select_related("obra", "criado_por")
    )
    for rec in qs.iterator():
        serie_pk = rec.pk
        burst = 0
        while burst < max_burst_por_serie:
            try:
                rec_atual = PendenciaRecorrente.objects.get(pk=serie_pk)
            except PendenciaRecorrente.DoesNotExist:
                break
            if not rec_atual.ativo or rec_atual.proxima_execucao > hoje:
                break
            dia_ref = rec_atual.proxima_execucao
            criar_ocorrencia_e_avancar(rec_atual, dia_ref, _notificar_criacao_pendencia)
            total += 1
            burst += 1
    return total
