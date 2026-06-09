import calendar
import json
from collections import defaultdict
from datetime import date, time, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Max, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from accounts.decorators import login_required
from core.models import ProjectDiaryApprover, ProjectMember, ProjectOwner
from core.notification_utils import criar_notificacao as core_criar_notificacao
from mapa_obras.models import Obra

from accounts.groups import GRUPOS, usuario_tem_administracao_global_na_plataforma
from .decorators import require_trackhub
from .forms import (
    AnexoPendenciaUploadForm,
    EtapaFormSet,
    NotificacaoEtapaForm,
    ObraFilterForm,
    PendenciaForm,
    RecorrenciaPendenciaForm,
    inicio_efetiva_pendencia_para_validacao,
    tipo_anexo_por_nome,
    validar_data_fim_pendencia,
)
from .models import (
    AnexoComentario,
    AnexoEtapa,
    AnexoPendencia,
    AssinaturaEtapa,
    AtividadePendencia,
    ComentarioPendencia,
    EtapaPendencia,
    NotificacaoPendencia,
    Pendencia,
    PendenciaRecorrente,
    TipoCustom,
)
from .recurrence_jobs import (
    etapas_snapshot_from_pendencia,
    ref_date_para_etapas_snapshot,
    sync_recorrencia_etapas_snapshot_if_linked,
)
from .utils.html_sanitize import (
    rich_text_is_empty,
    rich_text_to_plain_preview,
    sanitize_rich_text,
)

_MAX_ANEXOS_ETAPA = 5

User = get_user_model()

_MESES_ABREV = (
    "",
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
)

ALLOWED_PENDENCIA_UPDATE_FIELDS = frozenset(
    {
        "titulo",
        "descricao",
        "status",
        "prioridade",
        "tipo",
        "data_inicio",
        "prazo",
        "hora_inicio",
        "hora_fim",
        "responsavel_interno",
    }
)


def _hora_pendencia_para_str(valor) -> str:
    if not valor:
        return ""
    return valor.strftime("%H:%M")


def _parse_hora_pendencia(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("formato inválido")
    s = value.strip()
    if not s:
        return None
    parts = s.split(":")
    if len(parts) < 2:
        raise ValueError("formato inválido")
    h, m = int(parts[0]), int(parts[1])
    return time(h, m)


def _wants_json_response(request):
    acc = (request.headers.get("Accept") or "").lower()
    if "application/json" in acc:
        return True
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _json_no_cache(data, status=200):
    resp = JsonResponse(data, status=status)
    resp["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp["Pragma"] = "no-cache"
    return resp


def _format_trackhub_datetime(dt):
    if dt is None:
        return ""
    local = timezone.localtime(dt)
    mes = _MESES_ABREV[local.month]
    return f"{local.day} {mes} {local.year} às {local.strftime('%H:%M')}"


def _user_display_name(user):
    if not user:
        return "—"
    return user.get_full_name().strip() or user.username


def _registrar_atividade_pendencia(pendencia, usuario, descricao, tipo=AtividadePendencia.TIPO_GERAL):
    AtividadePendencia.objects.create(
        pendencia=pendencia,
        usuario=usuario,
        tipo=tipo,
        descricao=descricao,
    )


def _criar_notificacao_trackhub(
    usuario, titulo, mensagem, notification_type="system", url="", event_key=""
):
    if not usuario or not getattr(usuario, "is_active", False):
        return
    try:
        default_url = reverse("trackhub:fila")
    except Exception:
        default_url = "/trackhub/"
    core_criar_notificacao(
        usuario,
        notification_type,
        titulo,
        mensagem,
        url=url or default_url,
        event_key=event_key or "",
    )


def _usuarios_responsaveis_da_pendencia(pendencia):
    return list(
        User.objects.filter(
            pk__in=pendencia.etapas.filter(
                responsavel_interno__isnull=False
            ).values_list("responsavel_interno_id", flat=True)
        )
        .filter(is_active=True)
        .distinct()
    )


def _notificar_criacao_pendencia(pendencia, autor):
    prioridade = pendencia.get_prioridade_display()
    titulo = f"[TrackHub] Nova pendência ({prioridade})"
    mensagem = (
        f'Pendência "{pendencia.titulo}" criada na obra "{pendencia.obra.nome}" '
        f'com prioridade {prioridade}.'
    )
    try:
        dest_url = reverse("trackhub:pendencia_detalhe", args=[pendencia.pk])
    except Exception:
        dest_url = reverse("trackhub:fila")
    for usuario in _usuarios_responsaveis_da_pendencia(pendencia):
        if autor and usuario.pk == autor.pk:
            continue
        _criar_notificacao_trackhub(
            usuario,
            titulo,
            mensagem,
            url=dest_url,
            event_key=f"trackhub:pend:{pendencia.pk}",
        )


def _notificar_criacao_etapa(etapa, autor):
    usuario = etapa.responsavel_interno
    if not usuario or not usuario.is_active:
        return
    if autor and usuario.pk == autor.pk:
        return
    prioridade = etapa.pendencia.get_prioridade_display()
    titulo = f"[TrackHub] Nova etapa ({prioridade})"
    mensagem = (
        f'Você foi definido como responsável pela etapa "{etapa.titulo}" '
        f'da pendência "{etapa.pendencia.titulo}" na obra "{etapa.pendencia.obra.nome}".'
    )
    try:
        dest_url = reverse("trackhub:pendencia_detalhe", args=[etapa.pendencia_id])
    except Exception:
        dest_url = reverse("trackhub:fila")
    _criar_notificacao_trackhub(
        usuario,
        titulo,
        mensagem,
        url=dest_url,
        event_key=f"trackhub:pend:{etapa.pendencia_id}",
    )


def _serialize_atividade_pendencia(atividade):
    return {
        "usuario": _user_display_name(atividade.usuario),
        "descricao": atividade.descricao,
        "tipo": atividade.tipo,
        "criado_em": _format_trackhub_datetime(atividade.criado_em),
    }


def _serialize_comentario_pendencia(comentario, request):
    autor = comentario.autor
    nome = _user_display_name(autor)
    iniciais = _iniciais(nome)
    anexos_out = []
    for an in comentario.anexos.all():
        try:
            if an.arquivo:
                anexos_out.append(
                    {
                        "id": an.pk,
                        "nome": an.nome_original,
                        "url": _absolute_media_url(request, an.arquivo),
                        "eh_imagem": an.eh_imagem,
                    }
                )
        except (ValueError, OSError):
            continue
    return {
        "id": comentario.id,
        "texto": comentario.texto or "",
        "autor_nome": nome,
        "autor_iniciais": iniciais,
        "criado_em": _format_trackhub_datetime(comentario.created_at),
        "anexos": anexos_out,
    }


def _absolute_media_url(request, file_field):
    try:
        relative = file_field.url
    except ValueError:
        return ""
    return request.build_absolute_uri(relative)


def _pendencia_detail_payload(pendencia, request):
    etapas_out = []
    for numero, e in enumerate(pendencia.etapas.order_by("ordem"), start=1):
        ass = getattr(e, "assinatura", None)
        tem_assinatura = bool(
            ass and getattr(ass, "signature_data", "").strip()
        )
        arquivos_etapa = list(e.arquivos.all())
        etapas_out.append(
            {
                "id": e.pk,
                "titulo": e.titulo,
                "ordem": e.ordem,
                "numero": numero,
                "status": e.status,
                "status_display": e.get_status_display(),
                "responsavel_nome": e.responsavel_nome,
                "responsavel_interno_id": e.responsavel_interno_id,
                "prazo": e.prazo.isoformat() if e.prazo else "",
                "requer_assinatura": e.requer_assinatura,
                "tem_assinatura": tem_assinatura,
                "signature_data": getattr(ass, "signature_data", "") if ass else "",
                "observacao": e.observacao or "",
                "anexos_count": len(arquivos_etapa),
                "anexos": [
                    {
                        "id": a.pk,
                        "nome": a.nome_original,
                        "url": _absolute_media_url(request, a.arquivo),
                        "tipo": a.tipo,
                        "eh_imagem": a.eh_imagem,
                    }
                    for a in arquivos_etapa
                    if a.arquivo
                ],
                "precisa_ficha_para_concluir": e.status == "pendente"
                and e.requer_assinatura
                and not tem_assinatura,
                "responsavel_whatsapp": e.responsavel_whatsapp,
                "responsavel_email": e.responsavel_email,
                "pode_assinar": bool(
                    request.user
                    and request.user.is_authenticated
                    and e.responsavel_interno_id == request.user.id
                ),
                "pode_concluir_etapa": _user_can_conclude_etapa(
                    request.user, e, pendencia
                ),
            }
        )

    anexos_out = []
    for an in pendencia.anexos.all():
        try:
            if an.arquivo:
                anexos_out.append(
                    {
                        "id": an.pk,
                        "nome": an.nome_original,
                        "url": _absolute_media_url(request, an.arquivo),
                        "tipo": an.tipo,
                        "eh_imagem": an.eh_imagem,
                    }
                )
        except (ValueError, OSError):
            continue

    comentarios_out = [
        _serialize_comentario_pendencia(c, request) for c in pendencia.comentarios.all()
    ]

    etapas_pendentes_count = sum(1 for e in pendencia.etapas.all() if e.status == "pendente")
    perms = _pendencia_permission_flags(request.user, pendencia)
    pode_editar = perms["pode_editar"]
    pode_comentar = perms["pode_comentar"]
    pode_concluir = perms["pode_concluir"]
    responsaveis_obra = (
        _responsaveis_por_obra_payload(Obra.objects.filter(pk=pendencia.obra_id))
        if pendencia.obra_id
        else []
    )
    usuarios_modal = responsaveis_obra[0]["pessoas"] if responsaveis_obra else []
    usuarios_outros = _todos_usuarios_ativos_payload()

    rec_payload = None
    serie = getattr(pendencia, "recorrencia_serie", None)
    if serie is not None:
        pe = serie.proxima_execucao
        rec_payload = {
            "proxima_execucao": pe.isoformat() if pe else "",
            "proxima_execucao_display": pe.strftime("%d/%m/%Y") if pe else "",
        }

    return {
        "id": pendencia.pk,
        "titulo": pendencia.titulo,
        "descricao": pendencia.descricao or "",
        "status": pendencia.status,
        "status_display": pendencia.get_status_display(),
        "prioridade": pendencia.prioridade,
        "prioridade_display": pendencia.get_prioridade_display(),
        "tipo": pendencia.tipo,
        "tipo_display": pendencia.get_tipo_display(),
        "origem": pendencia.origem,
        "origem_display": pendencia.get_origem_display(),
        "data_inicio": pendencia.data_inicio.isoformat() if pendencia.data_inicio else "",
        "data_inicio_efetiva": pendencia.data_inicio_efetiva.isoformat(),
        "prazo": pendencia.prazo.isoformat() if pendencia.prazo else "",
        "hora_inicio": _hora_pendencia_para_str(pendencia.hora_inicio),
        "hora_fim": _hora_pendencia_para_str(pendencia.hora_fim),
        "responsavel_interno_id": pendencia.responsavel_interno_id,
        "responsavel_nome": pendencia.responsavel_nome,
        "responsavel_email": pendencia.responsavel_email,
        "responsavel_whatsapp": pendencia.responsavel_whatsapp,
        "obra_id": pendencia.obra_id,
        "obra_nome": pendencia.obra.nome,
        "created_at": _format_trackhub_datetime(pendencia.created_at),
        "updated_at": _format_trackhub_datetime(pendencia.updated_at),
        "criado_por_nome": _user_display_name(pendencia.criado_por),
        "pode_editar": pode_editar,
        "pode_comentar": pode_comentar,
        "pode_concluir": pode_concluir,
        "etapas_pendentes_count": etapas_pendentes_count,
        "esta_vencida": pendencia.esta_vencida,
        "etapas": etapas_out,
        "anexos": anexos_out,
        "comentarios": comentarios_out,
        "status_choices": [
            {"value": c[0], "label": c[1]} for c in Pendencia.STATUS_CHOICES
        ],
        "prioridade_choices": [
            {"value": c[0], "label": c[1]} for c in Pendencia.PRIORIDADE_CHOICES
        ],
        "tipo_choices": [{"value": c[0], "label": c[1]} for c in Pendencia.TIPO_CHOICES],
        "usuarios": usuarios_modal,
        "usuarios_outros": usuarios_outros,
        "recorrencia": rec_payload,
    }


def _pendencia_detail_prefetch_queryset():
    return (
        Pendencia.objects.select_related(
            "obra", "criado_por", "recorrencia_serie", "responsavel_interno"
        )
        .prefetch_related(
            Prefetch(
                "etapas",
                queryset=EtapaPendencia.objects.select_related(
                    "assinatura",
                    "assinatura__assinado_por",
                    "responsavel_interno",
                )
                .order_by("ordem")
                .prefetch_related(
                    Prefetch(
                        "arquivos",
                        queryset=AnexoEtapa.objects.order_by("created_at"),
                    ),
                ),
            ),
            Prefetch(
                "comentarios",
                queryset=ComentarioPendencia.objects.select_related("autor")
                .order_by("created_at")
                .prefetch_related(
                    Prefetch(
                        "anexos",
                        queryset=AnexoComentario.objects.order_by("enviado_em"),
                    )
                ),
            ),
            Prefetch(
                "anexos",
                queryset=AnexoPendencia.objects.order_by("created_at"),
            ),
        )
    )


def _pendencia_prefetched_for_detail(user, pk):
    return get_object_or_404(
        _pendencia_detail_prefetch_queryset().filter(
            pk__in=_pendencia_queryset_for_user(user).values("pk")
        ),
        pk=pk,
    )


def _pendencia_prefetched_by_pk(pk):
    """
    Recarrega pendência após edição sem filtro de visibilidade do usuário.
    Necessário quando a alteração remove o vínculo que dava acesso (ex.: trocar
    responsável interno da pendência), alinhado ao fluxo de edição de etapa.
    """
    return get_object_or_404(_pendencia_detail_prefetch_queryset(), pk=pk)


_PRIORIDADE_ORDER = {"urgente": 0, "alta": 1, "normal": 2, "baixa": 3}

_MONTHS_PT = (
    "",
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)


def _project_ids_for_user(user):
    if user.is_staff or user.is_superuser:
        return None
    owner = ProjectOwner.objects.filter(user=user).values_list("project_id", flat=True)
    member = ProjectMember.objects.filter(user=user).values_list("project_id", flat=True)
    approver = ProjectDiaryApprover.objects.filter(
        user=user, is_active=True
    ).values_list("project_id", flat=True)
    return sorted(set(list(owner) + list(member) + list(approver)))


def _trackhub_has_full_access(user):
    """Admin legado, administrador global, staff ou superuser — acesso total."""
    if user.is_superuser or user.is_staff:
        return True
    return _trackhub_roles(user)["admin"]


def _trackhub_roles(user):
    if user.is_superuser or user.is_staff:
        return {"admin": True, "aprovador": True, "solicitante": True}
    gset = set(user.groups.values_list("name", flat=True))
    legacy_admin = GRUPOS.TRACKHUB in gset
    plat_admin = usuario_tem_administracao_global_na_plataforma(user)
    return {
        "admin": plat_admin or legacy_admin,
        "aprovador": GRUPOS.TRACKHUB_APROVADOR in gset,
        "solicitante": GRUPOS.TRACKHUB_SOLICITANTE in gset,
    }


def _obra_pks_designadas(user):
    """PKs de obras ativas nos projetos vinculados ao usuário. None = todas (admin)."""
    if _trackhub_has_full_access(user):
        return None
    ids = _project_ids_for_user(user)
    if not ids:
        return frozenset()
    return frozenset(
        Obra.objects.filter(
            project_id__in=ids, ativa=True, project__is_active=True
        ).values_list("pk", flat=True)
    )


def _pendencia_in_obra_designada(user, pendencia):
    obra_pks = _obra_pks_designadas(user)
    if obra_pks is None:
        return True
    return pendencia.obra_id in obra_pks


def _user_is_responsavel_em_pendencia(user, pendencia):
    if pendencia.responsavel_interno_id == user.id:
        return True
    return pendencia.etapas.filter(responsavel_interno_id=user.id).exists()


def _obras_queryset_for_user(user):
    """Escopo de obras conforme papéis TrackHub e vínculos de projeto."""
    if _trackhub_has_full_access(user):
        return (
            Obra.objects.filter(ativa=True, project__is_active=True)
            .select_related("project")
            .order_by("nome")
        )
    ids = _project_ids_for_user(user)
    if not ids:
        return Obra.objects.none()
    return (
        Obra.objects.filter(project_id__in=ids, ativa=True, project__is_active=True)
        .select_related("project")
        .order_by("nome")
    )


def _usuarios_designados_por_projeto_ids(project_ids):
    if not project_ids:
        return {}
    members = ProjectMember.objects.filter(project_id__in=project_ids).values_list(
        "project_id", "user_id"
    )
    owners = ProjectOwner.objects.filter(project_id__in=project_ids).values_list(
        "project_id", "user_id"
    )
    approvers = ProjectDiaryApprover.objects.filter(
        project_id__in=project_ids, is_active=True
    ).values_list("project_id", "user_id")

    by_project = {}
    for pid, uid in list(members) + list(owners) + list(approvers):
        by_project.setdefault(pid, set()).add(uid)
    return by_project


def _usuario_responsavel_dict(usr):
    nome = usr.get_full_name().strip() or usr.username
    return {
        "id": usr.pk,
        "nome": nome,
        "iniciais": _iniciais(nome),
    }


def _todos_usuarios_ativos_payload():
    return [
        _usuario_responsavel_dict(u)
        for u in User.objects.filter(is_active=True).order_by(
            "first_name", "last_name", "username"
        )
    ]


def _responsaveis_por_obra_payload(obras_qs):
    obras = list(obras_qs.select_related("project"))
    project_ids = [o.project_id for o in obras if o.project_id]
    users_by_project = _usuarios_designados_por_projeto_ids(project_ids)
    all_user_ids = sorted(
        {
            uid
            for uids in users_by_project.values()
            for uid in uids
            if uid is not None
        }
    )
    users = {
        u.pk: u
        for u in User.objects.filter(pk__in=all_user_ids, is_active=True).order_by(
            "first_name", "last_name", "username"
        )
    }

    out = []
    for obra in obras:
        ids = sorted(users_by_project.get(obra.project_id, set()))
        pessoas = []
        for uid in ids:
            usr = users.get(uid)
            if not usr:
                continue
            pessoas.append(_usuario_responsavel_dict(usr))
        codigo = getattr(obra, "codigo_sienge", None) or getattr(obra, "codigo", None)
        obra_nome = f"{codigo} - {obra.nome}" if codigo else str(obra.nome)
        out.append(
            {
                "obra_id": obra.pk,
                "obra_nome": obra_nome,
                "pessoas": pessoas,
            }
        )
    return out


def _pendencias_qs_for_user(user):
    if _trackhub_has_full_access(user):
        return Pendencia.objects.all()
    roles = _trackhub_roles(user)
    if not (roles["aprovador"] or roles["solicitante"]):
        return Pendencia.objects.none()
    obra_pks = _obra_pks_designadas(user)
    resp_q = Q(etapas__responsavel_interno=user) | Q(responsavel_interno=user)
    if not obra_pks:
        return Pendencia.objects.filter(resp_q).distinct()
    return Pendencia.objects.filter(Q(obra_id__in=obra_pks) | resp_q).distinct()


def _pendencia_queryset_for_user(user):
    return _pendencias_qs_for_user(user)


def _user_can_comment_pendencia(user, pendencia):
    return _pendencias_qs_for_user(user).filter(pk=pendencia.pk).exists()


def _user_can_edit_pendencia(user, pendencia):
    if _trackhub_has_full_access(user):
        return True
    roles = _trackhub_roles(user)
    if roles["aprovador"]:
        if _pendencia_in_obra_designada(user, pendencia):
            return True
        return pendencia.responsavel_interno_id == user.id
    if roles["solicitante"]:
        return pendencia.criado_por_id == user.id
    return False


def _user_can_conclude_pendencia(user, pendencia):
    if not _user_can_comment_pendencia(user, pendencia):
        return False
    if _trackhub_has_full_access(user):
        return True
    roles = _trackhub_roles(user)
    if roles["aprovador"]:
        if _pendencia_in_obra_designada(user, pendencia):
            return True
        return pendencia.responsavel_interno_id == user.id
    if roles["solicitante"]:
        return pendencia.criado_por_id == user.id
    return False


def _user_can_conclude_etapa(user, etapa, pendencia=None):
    """Quem pode concluir uma etapa específica (assinatura exige responsável da etapa)."""
    if pendencia is None:
        pendencia = etapa.pendencia
    if not _user_can_comment_pendencia(user, pendencia):
        return False
    if _trackhub_has_full_access(user):
        return True
    roles = _trackhub_roles(user)
    if roles["aprovador"]:
        if _pendencia_in_obra_designada(user, pendencia):
            return True
        if pendencia.responsavel_interno_id == user.id:
            return True
        if etapa.responsavel_interno_id == user.id:
            return True
        return False
    if roles["solicitante"]:
        return etapa.responsavel_interno_id == user.id
    return False


def _pendencia_permission_flags(user, pendencia):
    etapas_pendentes_count = pendencia.etapas.filter(status="pendente").count()
    pode_editar = _user_can_edit_pendencia(user, pendencia)
    pode_comentar = _user_can_comment_pendencia(user, pendencia)
    pode_concluir_perm = _user_can_conclude_pendencia(user, pendencia)
    pode_concluir = (
        pode_concluir_perm
        and etapas_pendentes_count == 0
        and pendencia.status not in ("concluida", "cancelada")
    )
    return {
        "pode_editar": pode_editar,
        "pode_comentar": pode_comentar,
        "pode_concluir": pode_concluir,
        "etapas_pendentes_count": etapas_pendentes_count,
    }


def _pks_pode_editar_trackhub(user, pendencias):
    """PKs de pendências que o usuário pode alterar na UI."""
    return {p.pk for p in pendencias if _user_can_edit_pendencia(user, p)}


def _pks_pode_concluir_trackhub(user, pendencias):
    """PKs de pendências em que o usuário pode tentar concluir (permissão, sem checar etapas)."""
    return {p.pk for p in pendencias if _user_can_conclude_pendencia(user, p)}


def _iniciais(nome: str) -> str:
    nome = (nome or "").strip()
    if not nome or nome == "—":
        return "?"
    parts = nome.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return nome[:2].upper()


def _prev_next_month(year: int, month: int):
    if month == 1:
        py, pm = year - 1, 12
    else:
        py, pm = year, month - 1
    if month == 12:
        ny, nm = year + 1, 1
    else:
        ny, nm = year, month + 1
    return py, pm, ny, nm


def _nav_tab_context(user):
    abertas = _pendencias_qs_for_user(user).exclude(
        status__in=["concluida", "cancelada"]
    )
    return {
        "total_pendencias": abertas.count(),
    }


def _salvar_anexos_geral_pendencia(request, pendencia, user):
    pendencia_pk = pendencia.pk
    arquivos = request.FILES.getlist("anexos_geral")
    for arquivo in arquivos:
        total_existente = AnexoPendencia.objects.filter(
            pendencia_id=pendencia_pk
        ).count()
        if total_existente >= AnexoPendenciaUploadForm.MAX_ANEXOS:
            break
        nome_lower = (arquivo.name or "").lower()
        partes = nome_lower.rsplit(".", 1)
        ext = partes[-1] if len(partes) >= 2 else ""
        if ext in ("jpg", "jpeg", "png", "gif", "webp"):
            tipo = "imagem"
        elif ext in ("pdf", "doc", "docx", "xls", "xlsx"):
            tipo = "documento"
        else:
            tipo = "outro"
        AnexoPendencia.objects.create(
            pendencia_id=pendencia_pk,
            arquivo=arquivo,
            nome_original=arquivo.name,
            tipo=tipo,
            tamanho=getattr(arquivo, "size", 0) or 0,
            enviado_por=user,
            )


def _renumber_etapas_ordem(pendencia):
    for idx, etapa_id in enumerate(
        pendencia.etapas.order_by("ordem").values_list("pk", flat=True),
        start=1,
    ):
        pendencia.etapas.filter(pk=etapa_id).update(ordem=idx)


def _parse_etapa_form_post(request):
    """Campos comuns ao criar/editar etapa. Retorna (data_dict, error_msg)."""
    titulo = (request.POST.get("titulo") or "").strip()
    if not titulo:
        return None, "Informe o título da etapa."

    responsavel = None
    rid = (request.POST.get("responsavel_interno") or "").strip()
    if rid:
        try:
            uid = int(rid)
        except ValueError:
            return None, "Responsável inválido."
        responsavel = User.objects.filter(pk=uid, is_active=True).first()
        if not responsavel:
            return None, "Responsável não encontrado."

    if not responsavel:
        return None, "Informe o responsável interno da etapa."

    prazo = None
    prazo_raw = (request.POST.get("prazo") or "").strip()
    if prazo_raw:
        try:
            prazo = date.fromisoformat(prazo_raw)
        except ValueError:
            return None, "Prazo inválido."

    requer_assinatura = request.POST.get("requer_assinatura") in (
        "1",
        "on",
        "true",
        "True",
    )
    observacao = sanitize_rich_text(request.POST.get("observacao"))
    return {
        "titulo": titulo,
        "responsavel": responsavel,
        "prazo": prazo,
        "requer_assinatura": requer_assinatura,
        "observacao": observacao,
    }, None


def _fmt_data_trackhub(d):
    return d.strftime("%d/%m/%Y") if d else ""


def _fmt_prazo_etapa_log(d):
    """Data curta no log de edição de etapa (ex.: 09/05 -> 10/05)."""
    return d.strftime("%d/%m") if d else ""


def _nome_usuario_trackhub(user):
    if not user:
        return "—"
    return user.get_full_name() or user.username or "—"


def _descricoes_edicao_etapa(etapa, parsed):
    """
    Uma mensagem de atividade por campo alterado.
    Formato: Editou etapa: {nome} -> {detalhe do que mudou}
    etapa: estado anterior (antes do save); parsed: valores novos do formulário.
    """
    ant_titulo = (etapa.titulo or "").strip() or "etapa"
    ref = ant_titulo
    msgs = []

    novo_titulo = parsed["titulo"]
    if novo_titulo != ant_titulo:
        msgs.append(f"Editou etapa: {ant_titulo} -> título: {ant_titulo} -> {novo_titulo}")

    ant_resp_id = etapa.responsavel_interno_id
    novo_resp = parsed["responsavel"]
    novo_resp_id = novo_resp.pk if novo_resp else None
    if novo_resp_id != ant_resp_id:
        ant_nome = _nome_usuario_trackhub(etapa.responsavel_interno)
        novo_nome = _nome_usuario_trackhub(novo_resp)
        msgs.append(
            f"Editou etapa: {ref} -> Usuário responsável: {ant_nome} -> {novo_nome}"
        )

    ant_prazo = etapa.prazo
    novo_prazo = parsed["prazo"]
    if novo_prazo != ant_prazo:
        if ant_prazo and novo_prazo:
            msgs.append(
                f"Editou etapa: {ref} -> prazo: {_fmt_prazo_etapa_log(ant_prazo)} "
                f"-> {_fmt_prazo_etapa_log(novo_prazo)}"
            )
        elif not ant_prazo and novo_prazo:
            msgs.append(
                f"Editou etapa: {ref} -> prazo: {_fmt_prazo_etapa_log(novo_prazo)}"
            )
        elif ant_prazo and not novo_prazo:
            msgs.append(
                f"Editou etapa: {ref} -> removeu prazo (era {_fmt_prazo_etapa_log(ant_prazo)})"
            )

    if parsed["requer_assinatura"] != etapa.requer_assinatura:
        if parsed["requer_assinatura"]:
            msgs.append(f"Editou etapa: {ref} -> passou a exigir assinatura")
        else:
            msgs.append(f"Editou etapa: {ref} -> deixou de exigir assinatura")

    ant_obs = (etapa.observacao or "").strip()
    novo_obs = (parsed["observacao"] or "").strip()
    if novo_obs != ant_obs:
        if not ant_obs and novo_obs:
            msgs.append(f"Editou etapa: {ref} -> adicionou observação")
        elif ant_obs and not novo_obs:
            msgs.append(f"Editou etapa: {ref} -> removeu observação")
        else:
            msgs.append(f"Editou etapa: {ref} -> alterou observação")

    return msgs


def _salvar_anexos_etapa_nova(request, etapa, user):
    """Anexos enviados junto com criação de etapa na ficha (campo anexos_etapa)."""
    for arq in request.FILES.getlist("anexos_etapa"):
        if not arq or not getattr(arq, "name", None):
            continue
        if (
            AnexoEtapa.objects.filter(etapa_id=etapa.pk).count()
            >= _MAX_ANEXOS_ETAPA
        ):
            break
        tipo = tipo_anexo_por_nome(arq.name) or "outro"
        AnexoEtapa.objects.create(
            etapa_id=etapa.pk,
            arquivo=arq,
            nome_original=arq.name,
            tipo=tipo,
            tamanho=getattr(arq, "size", 0) or 0,
            enviado_por=user,
        )


def _salvar_anexos_etapas_form(request, formset, user):
    prefix = formset.prefix
    for index, frm in enumerate(formset.forms):
        if not frm.is_bound:
            continue
        try:
            cd = frm.cleaned_data
        except AttributeError:
            continue
        if cd is None:
            continue
        if cd.get("DELETE"):
            continue
        etapa = frm.instance
        if not etapa.pk:
            continue
        field_name = f"{prefix}-{index}-anexos_etapa"
        uploaded = list(request.FILES.getlist(field_name))
        for arq in uploaded:
            if not arq or not getattr(arq, "name", None):
                continue
            if (
                AnexoEtapa.objects.filter(etapa_id=etapa.pk).count()
                >= _MAX_ANEXOS_ETAPA
            ):
                break
            tipo = tipo_anexo_por_nome(arq.name) or "outro"
            AnexoEtapa.objects.create(
                etapa_id=etapa.pk,
                arquivo=arq,
                nome_original=arq.name,
                tipo=tipo,
                tamanho=getattr(arq, "size", 0) or 0,
                enviado_por=user,
            )


def _fila_stats_for_user(user):
    hoje = timezone.localdate()
    mes_inicio = hoje.replace(day=1)
    pendencias_base = _pendencias_qs_for_user(user)
    etapas_pendentes = EtapaPendencia.objects.filter(
        pendencia__in=pendencias_base,
        status="pendente",
    ).exclude(pendencia__status="cancelada").count()
    return {
        "urgentes_vencidas": pendencias_base.filter(
            Q(prioridade="urgente") | Q(prazo__lt=hoje)
        )
        .exclude(status__in=["concluida", "cancelada"])
        .count(),
        "em_andamento": pendencias_base.filter(status="em_andamento").count(),
        "etapas_pendentes": etapas_pendentes,
        "concluidas_mes": pendencias_base.filter(
            status="concluida", updated_at__gte=mes_inicio
        ).count(),
    }


def _pagination_qs(request):
    q = request.GET.copy()
    q.pop("page", None)
    return urlencode(q)


def _th_prazo_class(p, hoje=None):
    hoje = hoje or timezone.localdate()
    if not p.prazo:
        return ""
    # Encerradas: prazo só informativo (cinza), não alerta de atraso.
    if p.encerrada_na_fila:
        return "neutral"
    if p.esta_vencida:
        return "vencida"
    if p.prazo <= hoje + timedelta(days=7):
        return "soon"
    return "ok"


def _fila_sort_key(p):
    """
    Fila ativa: vencidas → urgentes (não vencidas) → demais por prazo e prioridade.
    Encerradas (concluída/cancelada) por último, também por prazo.
    """
    enc = 1 if p.encerrada_na_fila else 0
    if enc:
        return (enc, 2, 2, p.prazo or date.max, _PRIORIDADE_ORDER.get(p.prioridade, 9), p.created_at)
    vencida = 0 if p.esta_vencida else 1
    urgente_abaixo_vencidas = (
        0 if p.prioridade == "urgente" and not p.esta_vencida else 1
    )
    return (
        enc,
        vencida,
        urgente_abaixo_vencidas,
        p.prazo or date.max,
        _PRIORIDADE_ORDER.get(p.prioridade, 9),
        p.created_at,
    )


def recalcular_status_pendencia(pendencia):
    etapas = pendencia.etapas.all()
    if not etapas.exists():
        # Sem etapas — manter status atual, não alterar
        return
    total = etapas.count()
    concluidas = etapas.filter(status="concluida").count()
    if concluidas == total:
        pendencia.status = "concluida"
    elif concluidas > 0:
        pendencia.status = "em_andamento"
    else:
        pendencia.status = "aberta"
    pendencia.save(update_fields=["status", "updated_at"])


def _modal_criar_pendencia_context(obras_qs):
    """Formulário e formset para o modal de nova pendência (fila e calendário)."""
    return {
        "modal_form": PendenciaForm(obras_queryset=obras_qs),
        "modal_formset": EtapaFormSet(),
        "modal_responsaveis_por_obra": _responsaveis_por_obra_payload(obras_qs),
        "modal_todos_usuarios": _todos_usuarios_ativos_payload(),
        "modal_tipos_custom": TipoCustom.objects.order_by("nome"),
    }


def _fila_list_render(request, template_name, origem=None):
    obras_qs = _obras_queryset_for_user(request.user)
    qs = _pendencias_qs_for_user(request.user).select_related("obra", "criado_por").prefetch_related(
        "etapas"
    )
    if origem:
        qs = qs.filter(origem=origem)

    obra_id = request.GET.get("obra")
    tipo = (request.GET.get("tipo") or "").strip()
    prioridade = (request.GET.get("prioridade") or "").strip()
    status = (request.GET.get("status") or "").strip()
    q = (request.GET.get("q") or "").strip()
    responsavel_id = (request.GET.get("responsavel") or "").strip()

    if obra_id and str(obra_id).isdigit():
        qs = qs.filter(obra_id=int(obra_id))
    if tipo:
        qs = qs.filter(tipo=tipo)
    if prioridade:
        qs = qs.filter(prioridade=prioridade)
    if status:
        if status == 'em_aberto':
            qs = qs.filter(status__in=['aberta', 'em_andamento'])
        elif status == 'vencida':
            hoje = timezone.localdate()
            qs = qs.exclude(status__in=['concluida', 'cancelada']).filter(prazo__lt=hoje)
        else:
            qs = qs.filter(status=status)
    if q:
        qs = qs.filter(titulo__icontains=q)
    if responsavel_id and str(responsavel_id).isdigit():
        qs = qs.filter(responsavel_interno_id=int(responsavel_id))

    hoje = timezone.localdate()
    items = list(qs)
    for p in items:
        p.th_prazo_class = _th_prazo_class(p, hoje)
        etqs = list(p.etapas.all())
        p.th_etapas_total = len(etqs)
        p.th_etapas_concluidas = sum(1 for e in etqs if e.status == "concluida")
    items.sort(key=_fila_sort_key)

    paginator = Paginator(items, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    pode_editar_trackhub_pks = _pks_pode_editar_trackhub(request.user, page_obj.object_list)
    pode_concluir_trackhub_pks = _pks_pode_concluir_trackhub(request.user, page_obj.object_list)

    resp_nome = ""
    resp_iniciais = ""
    if responsavel_id and str(responsavel_id).isdigit():
        _usr = User.objects.filter(pk=int(responsavel_id), is_active=True).first()
        if _usr:
            resp_nome = _usr.get_full_name().strip() or _usr.username
            resp_iniciais = _iniciais(resp_nome)

    filtros = {
        "obra": obra_id or "",
        "tipo": tipo,
        "prioridade": prioridade,
        "status": status,
        "q": q,
        "responsavel": responsavel_id,
        "responsavel_nome": resp_nome,
        "responsavel_iniciais": resp_iniciais,
    }

    roles = _trackhub_roles(request.user)
    if roles["admin"]:
        responsaveis_payload = _todos_usuarios_ativos_payload()
    else:
        obra_payloads = _responsaveis_por_obra_payload(obras_qs)
        seen: set = set()
        responsaveis_payload = []
        for op in obra_payloads:
            for p in op["pessoas"]:
                if p["id"] not in seen:
                    seen.add(p["id"])
                    responsaveis_payload.append(p)
        responsaveis_payload.sort(key=lambda p: (p.get("nome") or "").lower())

    tipos_custom_nomes = list(TipoCustom.objects.order_by("nome").values_list("nome", flat=True))
    tipos = [(v, l) for v, l in Pendencia.TIPO_CHOICES if v != "outro"] + [(n, n) for n in tipos_custom_nomes]

    ctx = {
        "obras": obras_qs,
        "page_obj": page_obj,
        "filtros": filtros,
        "tipos": tipos,
        "stats": _fila_stats_for_user(request.user),
        "pagination_qs": _pagination_qs(request),
        "pode_editar_trackhub_pks": pode_editar_trackhub_pks,
        "pode_concluir_trackhub_pks": pode_concluir_trackhub_pks,
        "responsaveis_json": json.dumps(responsaveis_payload, ensure_ascii=False),
    }
    ctx.update(_modal_criar_pendencia_context(obras_qs))
    ctx.update(_nav_tab_context(request.user))
    return render(request, template_name, ctx)


@login_required
@require_trackhub
def fila_view(request):
    return _fila_list_render(request, "trackhub/fila.html")


@login_required
@require_trackhub
def importados_view(request):
    return redirect("trackhub:fila")


@login_required
@require_trackhub
def criadas_view(request):
    return redirect("trackhub:fila")


@login_required
@require_trackhub
def por_obra_view(request):
    obras_qs = _obras_queryset_for_user(request.user)
    form = ObraFilterForm(request.GET or None, obras_queryset=obras_qs)

    obra = None
    pendencias = []

    if form.is_valid():
        obra = form.cleaned_data.get("obra")
        if obra:
            pendencias = list(
                _pendencia_queryset_for_user(request.user)
                .filter(obra=obra)
                .select_related("obra", "criado_por")
                .prefetch_related("etapas")
                .order_by("-updated_at")
            )

    status_counts = {
        "aberta": 0,
        "em_andamento": 0,
        "aguardando": 0,
        "concluida": 0,
        "cancelada": 0,
    }
    for p in pendencias:
        if p.status in status_counts:
            status_counts[p.status] += 1

    ctx = {
        "obras": obras_qs,
        "obra_form": form,
        "obra": obra,
        "pendencias": pendencias,
        "status_counts": status_counts,
    }
    ctx.update(_nav_tab_context(request.user))
    return render(request, "trackhub/por_obra.html", ctx)


@login_required
@require_trackhub
def por_responsavel_view(request):
    qs = (
        _pendencias_qs_for_user(request.user)
        .filter(status__in=["aberta", "em_andamento", "aguardando"])
        .select_related("obra", "criado_por")
        .prefetch_related("etapas")
    )

    by_resp = defaultdict(list)
    for p in qs:
        et = p.etapa_atual
        nome = "Sem responsável"
        if et:
            rn = et.responsavel_nome
            nome = "Sem responsável" if rn == "—" else rn
        by_resp[nome].append(p)

    grupos = []
    for nome in sorted(by_resp.keys(), key=lambda x: (x == "Sem responsável", x.lower())):
        lista = by_resp[nome]
        grupos.append(
            {
                "nome": nome,
                "iniciais": _iniciais(nome),
                "count": len(lista),
                "pendencias": lista,
            }
        )

    ctx = {"grupos": grupos}
    ctx.update(_nav_tab_context(request.user))
    return render(request, "trackhub/por_responsavel.html", ctx)


def _pendencia_intervalo_calendario(pendencia):
    """Intervalo [início, fim] da pendência no calendário (fim = data fim ou mesmo dia)."""
    inicio = pendencia.data_inicio_efetiva
    fim = pendencia.prazo or inicio
    if fim < inicio:
        fim = inicio
    return inicio, fim


def _pendencias_intervalo_no_mes(qs, mes_inicio, mes_fim):
    """Pendências que intersectam o mês visível (data início → data fim)."""
    out = []
    for p in qs:
        di, df = _pendencia_intervalo_calendario(p)
        if di <= mes_fim and df >= mes_inicio:
            out.append((p, di, df))
    out.sort(key=lambda x: (x[1], x[2], x[0].titulo or ""))
    return out


CALENDARIO_MAX_LINHAS_DIA = 4
CALENDARIO_VISIVEIS_ANTES_MAIS = 3
_CALENDARIO_WEEKDAY_SHORT = ("Dom.", "Seg.", "Ter.", "Qua.", "Qui.", "Sex.", "Sáb.")


def _assign_calendario_lanes(events):
    """Aloca faixas (tracks) por data de início e colunas ocupadas na semana."""

    def _lane_sort_key(ev):
        p = ev["pendencia"]
        di, _ = _pendencia_intervalo_calendario(p)
        return (di, -ev["span"], p.pk)

    ordenados = sorted(events, key=_lane_sort_key)
    lane_cols = []
    max_lane = 0
    for ev in ordenados:
        cols = set(range(ev["col_start"], ev["col_start"] + ev["span"]))
        lane = None
        for idx, occupied in enumerate(lane_cols):
            if not cols & occupied:
                lane = idx
                occupied.update(cols)
                break
        if lane is None:
            lane = len(lane_cols)
            lane_cols.append(set(cols))
        ev["lane"] = lane
        max_lane = max(max_lane, lane)
    return ordenados, max_lane + 1


def _calendario_metadados_por_dia(week_events, week_start):
    """Por coluna do dia: faixas visíveis, '+N mais' e lista completa para o popover."""
    metas = []
    for col in range(7):
        day_date = week_start + timedelta(days=col)
        touching = [
            e
            for e in week_events
            if e["col_start"] <= col < e["col_start"] + e["span"]
        ]
        touching.sort(key=lambda e: (e["lane"], e["pendencia"].pk))
        total = len(touching)
        max_lane = max((e["lane"] for e in touching), default=-1)
        visible_count = sum(
            1 for e in touching if e["lane"] < CALENDARIO_VISIVEIS_ANTES_MAIS
        )
        overflow = (
            max_lane >= CALENDARIO_VISIVEIS_ANTES_MAIS
            or total > CALENDARIO_MAX_LINHAS_DIA
        )
        if overflow:
            visible_lanes = set(range(CALENDARIO_VISIVEIS_ANTES_MAIS))
            more_count = total - visible_count
        else:
            visible_lanes = {e["lane"] for e in touching}
            more_count = 0
        pendencias = []
        seen = set()
        for e in touching:
            p = e["pendencia"]
            if p.pk in seen:
                continue
            seen.add(p.pk)
            di, df = _pendencia_intervalo_calendario(p)
            pendencias.append(
                {
                    "id": p.pk,
                    "titulo": p.titulo or "",
                    "prioridade": p.prioridade,
                    "status": p.status,
                    "continues_before": di < day_date,
                    "continues_after": df > day_date,
                }
            )
        metas.append(
            {
                "visible_lanes": visible_lanes,
                "more_count": more_count,
                "pendencias": pendencias,
                "weekday_short": _CALENDARIO_WEEKDAY_SHORT[col],
                "day_num": day_date.day,
            }
        )
    return metas


def _calendario_aplicar_visibilidade_semana(week_events, day_metas):
    for ev in week_events:
        ev["show_title"] = True
        ev["hidden"] = False
        for col in range(ev["col_start"], ev["col_start"] + ev["span"]):
            if ev["lane"] not in day_metas[col]["visible_lanes"]:
                ev["hidden"] = True
                break
    visiveis = [e for e in week_events if not e["hidden"]]
    max_lane = max((e["lane"] for e in visiveis), default=-1)
    linhas_eventos = max_lane + 1 if visiveis else 0
    tem_mais = any(m["more_count"] > 0 for m in day_metas)
    linhas_totais = linhas_eventos + (1 if tem_mais else 0)
    return linhas_totais, linhas_eventos + 1 if tem_mais else 0, tem_mais


CAL_TIME_GRID_START = 6
CAL_TIME_GRID_END = 22
_CALENDARIO_WEEKDAY_FULL = (
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
)


def _parse_cal_view(request):
    v = (request.GET.get("view") or "mensal").strip().lower()
    return v if v in ("mensal", "semanal", "diario") else "mensal"


def _parse_cal_anchor_date(request, today):
    raw = (request.GET.get("date") or "").strip()
    if raw:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            pass
    return today


def _week_start_sunday(d):
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _calendario_filter_query_dict(request):
    q = {}
    for key in ("obra", "tipo", "status", "responsavel", "prioridade"):
        val = (request.GET.get(key) or "").strip()
        if val:
            q[key] = val
    return q


def _calendario_nav_url(request, view, *, year=None, month=None, anchor=None):
    params = {"view": view, **_calendario_filter_query_dict(request)}
    if view == "mensal":
        params["year"] = str(year)
        params["month"] = str(month)
    else:
        params["date"] = anchor.isoformat()
    return "?" + urlencode(params)


def _calendario_period_label_semanal(week_start, week_end):
    if week_start.month == week_end.month:
        return f"{week_start.day} – {week_end.day} de {_MONTHS_PT[week_end.month]} {week_end.year}"
    return (
        f"{week_start.day} de {_MONTHS_PT[week_start.month]} – "
        f"{week_end.day} de {_MONTHS_PT[week_end.month]} {week_end.year}"
    )


def _calendario_period_label_diario(d):
    wd = _CALENDARIO_WEEKDAY_FULL[d.weekday()]
    return f"{wd}, {d.day} de {_MONTHS_PT[d.month]} {d.year}"


def _cal_timed_layout(pendencia):
    if not pendencia.hora_inicio:
        return None
    start = pendencia.hora_inicio.hour * 60 + pendencia.hora_inicio.minute
    if pendencia.hora_fim:
        end = pendencia.hora_fim.hour * 60 + pendencia.hora_fim.minute
        if end <= start:
            end = start + 60
    else:
        end = start + 60
    grid_start = CAL_TIME_GRID_START * 60
    grid_end = CAL_TIME_GRID_END * 60
    start = max(start, grid_start)
    end = min(end, grid_end)
    if start >= grid_end:
        return None
    total = grid_end - grid_start
    top_pct = (start - grid_start) / total * 100
    height_pct = max((end - start) / total * 100, 100 / 16)
    return {"top_pct": round(top_pct, 2), "height_pct": round(height_pct, 2)}


def _pendencias_intervalo_periodo(qs, period_start, period_end, today, status_val):
    if status_val == "vencida":
        out = []
        for p in qs:
            di, df = _pendencia_intervalo_calendario(p)
            df_efetivo = max(df, today)
            if di <= period_end and df_efetivo >= period_start:
                out.append((p, di, df_efetivo))
        out.sort(key=lambda x: (x[1], x[2], x[0].titulo or ""))
        return out
    return _pendencias_intervalo_no_mes(qs, period_start, period_end)


def _calendario_popover_pendencias_dia(pendencias_periodo, day_date):
    items = []
    seen = set()
    for p, di, df in pendencias_periodo:
        if p.pk in seen:
            continue
        if di <= day_date <= df:
            seen.add(p.pk)
            items.append(
                {
                    "id": p.pk,
                    "titulo": p.titulo or "",
                    "prioridade": p.prioridade,
                    "status": p.status,
                    "continues_before": di < day_date,
                    "continues_after": df > day_date,
                }
            )
    return items


def _calendario_build_time_view(
    pendencias_periodo, range_start, range_end, num_cols, col_for_date, today
):
    span_raw = []
    chips_by_col = [[] for _ in range(num_cols)]
    timed_by_col = [[] for _ in range(num_cols)]

    for p, di, df in pendencias_periodo:
        seg_start = max(di, range_start)
        seg_end = min(df, range_end)
        if seg_start > seg_end:
            continue
        span_days = (seg_end - seg_start).days + 1
        if span_days > 1:
            col_start = col_for_date(seg_start)
            if col_start < 0 or col_start >= num_cols:
                continue
            span = min(span_days, num_cols - col_start)
            span_raw.append(
                {
                    "pendencia": p,
                    "col_start": col_start,
                    "span": span,
                    "lane": 0,
                    "continues_before": di < range_start,
                    "continues_after": df > range_end,
                }
            )
        elif p.hora_inicio:
            layout = _cal_timed_layout(p)
            if layout:
                col = col_for_date(seg_start)
                if 0 <= col < num_cols:
                    timed_by_col[col].append({"pendencia": p, **layout})
        else:
            col = col_for_date(seg_start)
            if 0 <= col < num_cols:
                chips_by_col[col].append(p)

    span_events, _ = _assign_calendario_lanes(span_raw)
    max_span_lane = max((e["lane"] for e in span_events), default=-1)
    lane_base = max_span_lane + 1

    nodate_events = list(span_events)
    for col_idx, chip_list in enumerate(chips_by_col):
        for lane_offset, p in enumerate(chip_list):
            nodate_events.append(
                {
                    "pendencia": p,
                    "col_start": col_idx,
                    "span": 1,
                    "lane": lane_base + lane_offset,
                    "continues_before": False,
                    "continues_after": False,
                }
            )

    hour_slots = [
        {"label": f"{h:02d}:00", "value": f"{h:02d}:00"}
        for h in range(CAL_TIME_GRID_START, CAL_TIME_GRID_END)
    ]
    nodate_rows = max((e["lane"] for e in nodate_events), default=-1) + 1
    nodate_rows = max(nodate_rows, 1)
    return nodate_events, timed_by_col, hour_slots, nodate_rows


def _calendario_build_mensal(year, month, pendencias_mes, today):
    cal = calendar.Calendar(firstweekday=calendar.SUNDAY)
    calendar_weeks = []
    calendar_day_data = {}
    for week_dates in cal.monthdatescalendar(year, month):
        week_start = week_dates[0]
        week_end = week_dates[6]
        days = []
        for d in week_dates:
            days.append(
                {
                    "date": d,
                    "current_month": d.month == month,
                    "is_today": d == today,
                }
            )
        week_events = []
        for p, di, df in pendencias_mes:
            seg_start = max(di, week_start)
            seg_end = min(df, week_end)
            if seg_start > seg_end:
                continue
            col_start = (seg_start - week_start).days
            span = (seg_end - seg_start).days + 1
            week_events.append(
                {
                    "pendencia": p,
                    "col_start": col_start,
                    "span": span,
                    "lane": 0,
                    "continues_before": di < week_start,
                    "continues_after": df > week_end,
                    "show_title": True,
                    "hidden": False,
                }
            )
        week_events, _ = _assign_calendario_lanes(week_events)
        day_metas = _calendario_metadados_por_dia(week_events, week_start)
        _lane_count, more_row, has_more_row = _calendario_aplicar_visibilidade_semana(
            week_events, day_metas
        )
        lane_count = CALENDARIO_MAX_LINHAS_DIA
        if has_more_row:
            more_row = CALENDARIO_MAX_LINHAS_DIA
        for idx, d in enumerate(days):
            meta = day_metas[idx]
            d["more_count"] = meta["more_count"]
            iso = d["date"].isoformat()
            calendar_day_data[iso] = {
                "weekday": meta["weekday_short"],
                "day": meta["day_num"],
                "pendencias": meta["pendencias"],
            }
        calendar_weeks.append(
            {
                "days": days,
                "events": week_events,
                "lane_count": lane_count,
                "more_row": more_row,
                "has_more_row": has_more_row,
            }
        )
    return {
        "calendar_weeks": calendar_weeks,
        "calendar_day_data_json": json.dumps(calendar_day_data, ensure_ascii=False),
    }


def _calendario_build_semanal(pendencias_periodo, week_start, today):
    week_end = week_start + timedelta(days=6)
    num_cols = 7

    def col_for(d):
        return (d - week_start).days

    nodate_events, timed_by_col, hour_slots, nodate_rows = _calendario_build_time_view(
        pendencias_periodo, week_start, week_end, num_cols, col_for, today
    )

    cal_time_days = []
    calendar_day_data = {}
    for i in range(7):
        d = week_start + timedelta(days=i)
        timed_sorted = sorted(timed_by_col[i], key=lambda x: x["top_pct"])
        cal_time_days.append(
            {
                "iso": d.isoformat(),
                "date": d,
                "is_today": d == today,
                "day_num": d.day,
                "weekday_short": _CALENDARIO_WEEKDAY_SHORT[i],
                "timed_events": timed_sorted,
            }
        )
        calendar_day_data[d.isoformat()] = {
            "weekday": _CALENDARIO_WEEKDAY_SHORT[i],
            "day": d.day,
            "pendencias": _calendario_popover_pendencias_dia(pendencias_periodo, d),
        }

    return {
        "cal_time_days": cal_time_days,
        "cal_time_cols": num_cols,
        "cal_span_events": nodate_events,
        "cal_hour_slots": hour_slots,
        "cal_nodate_rows": nodate_rows,
        "calendar_day_data_json": json.dumps(calendar_day_data, ensure_ascii=False),
    }


def _calendario_build_diario(pendencias_periodo, day_date, today):
    num_cols = 1

    def col_for(_d):
        return 0

    nodate_events, timed_by_col, hour_slots, nodate_rows = _calendario_build_time_view(
        pendencias_periodo, day_date, day_date, num_cols, col_for, today
    )

    timed_sorted = sorted(timed_by_col[0], key=lambda x: x["top_pct"])
    wd_idx = day_date.weekday()
    cal_time_days = [
        {
            "iso": day_date.isoformat(),
            "date": day_date,
            "is_today": day_date == today,
            "day_num": day_date.day,
            "weekday_full": _CALENDARIO_WEEKDAY_FULL[wd_idx],
            "timed_events": timed_sorted,
        }
    ]
    calendar_day_data = {
        day_date.isoformat(): {
            "weekday": _CALENDARIO_WEEKDAY_SHORT[(day_date.weekday() + 1) % 7],
            "day": day_date.day,
            "pendencias": _calendario_popover_pendencias_dia(pendencias_periodo, day_date),
        }
    }

    return {
        "cal_time_days": cal_time_days,
        "cal_time_cols": num_cols,
        "cal_span_events": nodate_events,
        "cal_hour_slots": hour_slots,
        "cal_nodate_rows": nodate_rows,
        "calendar_day_data_json": json.dumps(calendar_day_data, ensure_ascii=False),
    }


@login_required
@require_trackhub
def calendario_view(request):
    today = timezone.localdate()
    cal_view = _parse_cal_view(request)
    anchor = _parse_cal_anchor_date(request, today)

    year = today.year
    month = today.month
    raw_y = request.GET.get("year")
    raw_m = request.GET.get("month")
    if raw_y and str(raw_y).isdigit():
        year = int(raw_y)
    if raw_m and str(raw_m).isdigit():
        m = int(raw_m)
        if 1 <= m <= 12:
            month = m

    if cal_view in ("semanal", "diario"):
        year, month = anchor.year, anchor.month

    prev_year, prev_month, next_year, next_month = _prev_next_month(year, month)

    obras_qs = _obras_queryset_for_user(request.user)
    obra_id = request.GET.get("obra", "")
    tipo_val = request.GET.get("tipo", "")
    status_val = request.GET.get("status", "")
    responsavel_id = request.GET.get("responsavel", "")
    prioridade_raw = request.GET.get("prioridade", "")
    _valid_prioridades = {"urgente", "alta", "normal", "baixa"}
    prioridade_vals = [
        v.strip() for v in prioridade_raw.split(",")
        if v.strip() in _valid_prioridades
    ] if prioridade_raw else []
    qs = (
        _pendencias_qs_for_user(request.user)
        .select_related("obra")
        .exclude(status__in=["concluida", "cancelada"])
        .order_by("titulo")
    )
    if obra_id and str(obra_id).isdigit():
        qs = qs.filter(obra_id=int(obra_id))
    if tipo_val:
        qs = qs.filter(tipo=tipo_val)
    if status_val:
        if status_val == 'em_aberto':
            qs = qs.filter(status__in=['aberta', 'em_andamento'])
        elif status_val == 'vencida':
            qs = qs.filter(prazo__lt=today)
    if responsavel_id and str(responsavel_id).isdigit():
        qs = qs.filter(responsavel_interno_id=int(responsavel_id))
    if prioridade_vals and set(prioridade_vals) != _valid_prioridades:
        qs = qs.filter(prioridade__in=prioridade_vals)

    if cal_view == "semanal":
        week_start = _week_start_sunday(anchor)
        week_end = week_start + timedelta(days=6)
        period_start, period_end = week_start, week_end
        period_label = _calendario_period_label_semanal(week_start, week_end)
        nav_prev_url = _calendario_nav_url(
            request, cal_view, anchor=week_start - timedelta(days=7)
        )
        nav_next_url = _calendario_nav_url(
            request, cal_view, anchor=week_start + timedelta(days=7)
        )
    elif cal_view == "diario":
        period_start = period_end = anchor
        period_label = _calendario_period_label_diario(anchor)
        nav_prev_url = _calendario_nav_url(request, cal_view, anchor=anchor - timedelta(days=1))
        nav_next_url = _calendario_nav_url(request, cal_view, anchor=anchor + timedelta(days=1))
    else:
        _, last_day = calendar.monthrange(year, month)
        period_start = date(year, month, 1)
        period_end = date(year, month, last_day)
        period_label = f"{_MONTHS_PT[month]} {year}"
        nav_prev_url = _calendario_nav_url(
            request, "mensal", year=prev_year, month=prev_month
        )
        nav_next_url = _calendario_nav_url(
            request, "mensal", year=next_year, month=next_month
        )

    pendencias_periodo = _pendencias_intervalo_periodo(
        qs, period_start, period_end, today, status_val
    )

    view_ctx = {}
    if cal_view == "semanal":
        view_ctx = _calendario_build_semanal(pendencias_periodo, week_start, today)
    elif cal_view == "diario":
        view_ctx = _calendario_build_diario(pendencias_periodo, anchor, today)
    else:
        view_ctx = _calendario_build_mensal(year, month, pendencias_periodo, today)

    month_label = period_label

    tipo_labels = dict(Pendencia.TIPO_CHOICES)
    status_labels = dict(Pendencia.STATUS_CHOICES)
    prioridade_label_map = dict(Pendencia.PRIORIDADE_CHOICES)
    _order_prio = ["urgente", "alta", "normal", "baixa"]
    if prioridade_vals and set(prioridade_vals) != _valid_prioridades:
        prioridade_label = ", ".join(
            prioridade_label_map[v] for v in _order_prio if v in set(prioridade_vals)
        )
    else:
        prioridade_label = ""

    obra_nome = ""
    if obra_id and str(obra_id).isdigit():
        obra_nome = obras_qs.filter(pk=int(obra_id)).values_list("nome", flat=True).first() or ""

    resp_nome = ""
    resp_iniciais = ""
    if responsavel_id and str(responsavel_id).isdigit():
        usr = User.objects.filter(pk=int(responsavel_id), is_active=True).first()
        if usr:
            resp_nome = usr.get_full_name().strip() or usr.username
            resp_iniciais = _iniciais(resp_nome)

    filtros = {
        "obra": obra_id,
        "obra_nome": obra_nome,
        "tipo": tipo_val,
        "tipo_label": tipo_labels.get(tipo_val, tipo_val) if tipo_val else "",
        "status": status_val,
        "status_label": {"em_aberto": "Em aberto", "vencida": "Vencida"}.get(status_val, ""),
        "responsavel": responsavel_id,
        "responsavel_nome": resp_nome,
        "responsavel_iniciais": resp_iniciais,
        "prioridade": prioridade_raw,
        "prioridade_vals": prioridade_vals,
        "prioridade_label": prioridade_label,
    }

    roles = _trackhub_roles(request.user)
    if roles["admin"]:
        responsaveis_payload = _todos_usuarios_ativos_payload()
    else:
        obra_payloads = _responsaveis_por_obra_payload(obras_qs)
        seen: set = set()
        responsaveis_payload = []
        for op in obra_payloads:
            for p in op["pessoas"]:
                if p["id"] not in seen:
                    seen.add(p["id"])
                    responsaveis_payload.append(p)
        responsaveis_payload.sort(key=lambda p: (p.get("nome") or "").lower())

    tipos_custom_nomes = list(TipoCustom.objects.order_by("nome").values_list("nome", flat=True))
    tipos = [(v, l) for v, l in Pendencia.TIPO_CHOICES if v != "outro"] + [(n, n) for n in tipos_custom_nomes]

    filtros_clear_url = _calendario_nav_url(
        request,
        cal_view,
        year=year,
        month=month,
        anchor=anchor if cal_view != "mensal" else today,
    )

    ctx = {
        "cal_view": cal_view,
        "cal_anchor_date": anchor.isoformat(),
        "nav_prev_url": nav_prev_url,
        "nav_next_url": nav_next_url,
        "url_view_mensal": _calendario_nav_url(request, "mensal", year=year, month=month),
        "url_view_semanal": _calendario_nav_url(
            request, "semanal", anchor=_week_start_sunday(anchor)
        ),
        "url_view_diario": _calendario_nav_url(request, "diario", anchor=anchor),
        "filtros_clear_url": filtros_clear_url,
        "responsaveis_json": json.dumps(responsaveis_payload, ensure_ascii=False),
        "pendencia_detalhe_url_pattern": reverse(
            "trackhub:pendencia_detalhe", kwargs={"pk": 0}
        ).replace("/0/", "/{id}/"),
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "month_label": month_label,
        "year": year,
        "month": month,
        "obras": obras_qs,
        "filtros": filtros,
        "tipos": tipos,
    }
    ctx.update(view_ctx)
    ctx.update(_modal_criar_pendencia_context(obras_qs))
    ctx.update(_nav_tab_context(request.user))
    return render(request, "trackhub/calendario.html", ctx)


@login_required
@require_trackhub
@require_POST
def tipo_custom_criar_view(request):
    nome = (request.POST.get("nome") or "").strip()[:100]
    if not nome:
        return JsonResponse({"success": False, "error": "Nome é obrigatório."}, status=400)
    obj, _ = TipoCustom.objects.get_or_create(nome=nome, defaults={"criado_por": request.user})
    return JsonResponse({"success": True, "nome": obj.nome})


@login_required
@require_trackhub
@require_POST
def pendencia_criar_ajax_view(request):
    """Cria pendência via AJAX (modal do calendário). Retorna JSON."""
    from .recurrence import legacy_scalar_fields_for_db, proxima_data_estrita_depois

    obras_qs = _obras_queryset_for_user(request.user)
    hoje = timezone.localdate()

    form = PendenciaForm(request.POST, request.FILES, obras_queryset=obras_qs)
    rec_form = RecorrenciaPendenciaForm(request.POST)

    form_ok = form.is_valid()
    rec_ok = rec_form.is_valid()

    if not (form_ok and rec_ok):
        errors = {}
        for field, err_list in form.errors.items():
            errors[field] = [str(e) for e in err_list]
        if not rec_ok:
            for field, err_list in rec_form.errors.items():
                errors[f"rec_{field}"] = [str(e) for e in err_list]
        return JsonResponse({"ok": False, "errors": errors}, status=422)

    saved_pk = None
    with transaction.atomic():
        p = form.save(commit=False)
        p.criado_por = request.user
        p.status = "aberta"
        p.origem = "manual"
        p.save()
        fs = EtapaFormSet(request.POST, request.FILES, instance=p)
        if fs.is_valid():
            fs.save()
            _salvar_anexos_geral_pendencia(request, p, request.user)
            _salvar_anexos_etapas_form(request, fs, request.user)
            prazo_max_etapa = p.etapas.filter(prazo__isnull=False).aggregate(m=Max("prazo"))["m"]
            if prazo_max_etapa and (p.prazo is None or prazo_max_etapa > p.prazo):
                p.prazo = prazo_max_etapa
                p.save(update_fields=["prazo"])
            recalcular_status_pendencia(p)
            _notificar_criacao_pendencia(p, request.user)
            saved_pk = p.pk

            rcd = rec_form.cleaned_data
            regra = rcd.get("recorrencia_regra") or PendenciaRecorrente.REGRA_NONE
            if regra != PendenciaRecorrente.REGRA_NONE:
                p.refresh_from_db()
                dc = timezone.localtime(p.created_at).date()
                di = p.data_inicio_efetiva
                po = (p.prazo - dc).days if p.prazo else None
                ref_snap = ref_date_para_etapas_snapshot(p, po)
                snap = etapas_snapshot_from_pendencia(p, ref_snap)
                pm = rcd.get("recorrencia_parametros") or {}
                prox = proxima_data_estrita_depois(hoje, regra, parametros=pm)
                leg_wd, leg_dm, leg_m = legacy_scalar_fields_for_db(regra, pm)
                rec = PendenciaRecorrente.objects.create(
                    obra=p.obra,
                    criado_por=request.user,
                    titulo=p.titulo,
                    descricao=p.descricao or "",
                    tipo=p.tipo,
                    prioridade=p.prioridade,
                    prazo_offset_dias=po,
                    prazo_original=p.prazo,
                    data_inicio_original=di,
                    data_criacao_original=dc,
                    hora_inicio_original=p.hora_inicio,
                    hora_fim_original=p.hora_fim,
                    regra=regra,
                    dia_semana=leg_wd,
                    dia_mes=leg_dm,
                    mes=leg_m,
                    parametros_json=pm,
                    etapas_snapshot=snap,
                    proxima_execucao=prox,
                )
                Pendencia.objects.filter(pk=p.pk).update(recorrencia_serie_id=rec.pk)
        else:
            transaction.set_rollback(True)

    if saved_pk:
        return JsonResponse({"ok": True, "pk": saved_pk})
    return JsonResponse(
        {"ok": False, "errors": {"__all__": ["Erro ao salvar. Tente novamente."]}},
        status=422,
    )


@login_required
@require_trackhub
def pendencia_criar_view(request):
    from .recurrence import legacy_scalar_fields_for_db, proxima_data_estrita_depois

    if request.method == "GET":
        qs = request.GET.copy()
        qs["nova"] = "1"
        return redirect(f"{reverse('trackhub:fila')}?{qs.urlencode()}")

    obras_qs = _obras_queryset_for_user(request.user)
    responsaveis_por_obra = _responsaveis_por_obra_payload(obras_qs)
    hoje = timezone.localdate()

    if request.method == "POST":
        form = PendenciaForm(request.POST, request.FILES, obras_queryset=obras_qs)
        rec_form = RecorrenciaPendenciaForm(request.POST)
        saved_pk = None
        form_ok = form.is_valid()
        rec_ok = rec_form.is_valid()
        if form_ok and rec_ok:
            with transaction.atomic():
                p = form.save(commit=False)
                p.criado_por = request.user
                p.status = "aberta"
                p.origem = "manual"
                p.save()
                fs = EtapaFormSet(request.POST, request.FILES, instance=p)
                if fs.is_valid():
                    fs.save()
                    _salvar_anexos_geral_pendencia(request, p, request.user)
                    _salvar_anexos_etapas_form(request, fs, request.user)
                    prazo_max_etapa = p.etapas.filter(prazo__isnull=False).aggregate(m=Max("prazo"))["m"]
                    if prazo_max_etapa and (p.prazo is None or prazo_max_etapa > p.prazo):
                        p.prazo = prazo_max_etapa
                        p.save(update_fields=["prazo"])
                    recalcular_status_pendencia(p)
                    _notificar_criacao_pendencia(p, request.user)
                    saved_pk = p.pk

                    rcd = rec_form.cleaned_data
                    regra = rcd.get("recorrencia_regra") or PendenciaRecorrente.REGRA_NONE
                    if regra != PendenciaRecorrente.REGRA_NONE:
                        p.refresh_from_db()
                        dc = timezone.localtime(p.created_at).date()
                        di = p.data_inicio_efetiva
                        po = (p.prazo - dc).days if p.prazo else None
                        ref_snap = ref_date_para_etapas_snapshot(p, po)
                        snap = etapas_snapshot_from_pendencia(p, ref_snap)
                        pm = rcd.get("recorrencia_parametros") or {}
                        prox = proxima_data_estrita_depois(
                            hoje,
                            regra,
                            parametros=pm,
                        )
                        leg_wd, leg_dm, leg_m = legacy_scalar_fields_for_db(regra, pm)
                        rec = PendenciaRecorrente.objects.create(
                            obra=p.obra,
                            criado_por=request.user,
                            titulo=p.titulo,
                            descricao=p.descricao or "",
                            tipo=p.tipo,
                            prioridade=p.prioridade,
                            prazo_offset_dias=po,
                            prazo_original=p.prazo,
                            data_inicio_original=di,
                            data_criacao_original=dc,
                            hora_inicio_original=p.hora_inicio,
                            hora_fim_original=p.hora_fim,
                            regra=regra,
                            dia_semana=leg_wd,
                            dia_mes=leg_dm,
                            mes=leg_m,
                            parametros_json=pm,
                            etapas_snapshot=snap,
                            proxima_execucao=prox,
                        )
                        Pendencia.objects.filter(pk=p.pk).update(
                            recorrencia_serie_id=rec.pk
                        )
                else:
                    transaction.set_rollback(True)
            if saved_pk:
                messages.success(request, "Pendência criada.")
                return redirect(reverse("trackhub:fila") + f"?abrir={saved_pk}")
            messages.error(request, "Corrija os erros nas etapas.")
            formset = EtapaFormSet(request.POST, request.FILES)
        else:
            formset = EtapaFormSet(request.POST, request.FILES)
    else:
        form = PendenciaForm(obras_queryset=obras_qs)
        formset = EtapaFormSet()
        rec_form = RecorrenciaPendenciaForm(
            initial={
                "recorrencia_regra": PendenciaRecorrente.REGRA_NONE,
                "recorrencia_parametros_json": "{}",
            }
        )

    ctx = {
        "form": form,
        "formset": formset,
        "rec_form": rec_form,
        "form_title": "Nova pendência",
        "form_subtitle": "Cadastro",
        "responsaveis_por_obra": responsaveis_por_obra,
        "todos_usuarios": _todos_usuarios_ativos_payload(),
        "tipos_custom": TipoCustom.objects.all(),
        "tipo_selecionado": request.POST.get("tipo", "") if request.method == "POST" else "",
    }
    ctx.update(_nav_tab_context(request.user))
    return render(request, "trackhub/pendencia_form.html", ctx)


@login_required
@require_trackhub
def pendencia_editar_view(request, pk):
    """Descontinuada: edição inline no modal da fila."""
    get_object_or_404(_pendencia_queryset_for_user(request.user), pk=pk)
    messages.info(
        request,
        "A edição é feita ao abrir a pendência na fila. Esta página foi descontinuada.",
    )
    return redirect("trackhub:fila")


@login_required
@require_trackhub
def pendencia_detalhe_view(request, pk):
    pendencia = get_object_or_404(
        _pendencia_queryset_for_user(request.user)
        .select_related(
            "obra",
            "criado_por",
            "recorrencia_serie",
            "responsavel_interno",
        )
        .prefetch_related(
            Prefetch(
                "etapas",
                queryset=EtapaPendencia.objects.select_related(
                    "assinatura", "assinatura__assinado_por"
                )
                .order_by("ordem")
                .prefetch_related(
                    "notificacoes",
                    Prefetch(
                        "arquivos",
                        queryset=AnexoEtapa.objects.order_by("created_at"),
                    ),
                ),
            ),
            Prefetch(
                "comentarios",
                queryset=ComentarioPendencia.objects.select_related("autor")
                .order_by("created_at")
                .prefetch_related(
                    Prefetch(
                        "anexos",
                        queryset=AnexoComentario.objects.order_by("enviado_em"),
                    ),
                ),
            ),
            Prefetch(
                "anexos",
                queryset=AnexoPendencia.objects.order_by("created_at"),
            ),
        ),
        pk=pk,
    )

    try:
        from core.notification_utils import marcar_lidas_para_usuario_event_key

        marcar_lidas_para_usuario_event_key(
            request.user,
            f"trackhub:pend:{pendencia.pk}",
        )
    except Exception:
        pass

    etapas = list(pendencia.etapas.all())
    comentarios = list(pendencia.comentarios.all())
    anexos_list = list(pendencia.anexos.all())
    etapas_concluidas_count = sum(1 for e in etapas if e.status == "concluida")
    etapas_pendentes_count = sum(1 for e in etapas if e.status == "pendente")
    total_notificacoes = sum(len(list(e.notificacoes.all())) for e in etapas)
    ficha_resp_blocos = []
    if pendencia.obra_id:
        ficha_resp_blocos = _responsaveis_por_obra_payload(
            Obra.objects.filter(pk=pendencia.obra_id)
        )
    perms = _pendencia_permission_flags(request.user, pendencia)
    for e in etapas:
        e.pode_concluir_etapa = _user_can_conclude_etapa(request.user, e, pendencia)
    ctx = {
        "pendencia": pendencia,
        "etapas": etapas,
        "comentarios": comentarios,
        "anexos_list": anexos_list,
        "num_anexos": len(anexos_list),
        "pode_editar": perms["pode_editar"],
        "pode_comentar": perms["pode_comentar"],
        "pode_concluir": perms["pode_concluir"],
        "etapas_concluidas_count": etapas_concluidas_count,
        "etapas_pendentes_count": etapas_pendentes_count,
        "total_notificacoes": total_notificacoes,
        "ficha_resp_blocos": ficha_resp_blocos,
        "todos_usuarios": _todos_usuarios_ativos_payload(),
    }
    ctx.update(_nav_tab_context(request.user))
    return render(request, "trackhub/pendencia_detalhe.html", ctx)


@login_required
@require_trackhub
@require_POST
def pendencia_concluir_view(request, pk):
    pendencia = get_object_or_404(_pendencia_queryset_for_user(request.user), pk=pk)
    if not _user_can_conclude_pendencia(request.user, pendencia):
        msg = "Sem permissão para concluir esta pendência."
        if _wants_json_response(request):
            return _json_no_cache({"ok": False, "error": msg}, status=403)
        messages.error(request, msg)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)
    etapas_pendentes = pendencia.etapas.filter(status="pendente").count()
    if etapas_pendentes > 0:
        msg = (
            f"Não é possível concluir esta pendência. Ainda há {etapas_pendentes} "
            "etapa(s) pendente(s)."
        )
        if _wants_json_response(request):
            return _json_no_cache({"ok": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)
    pendencia.status = "concluida"
    pendencia.save(update_fields=["status", "updated_at"])
    try:
        from core.notification_utils import marcar_lidas_por_event_key

        marcar_lidas_por_event_key(f"trackhub:pend:{pendencia.pk}")
    except Exception:
        pass
    _registrar_atividade_pendencia(
        pendencia,
        request.user,
        "Marcou a pendência como concluída",
        AtividadePendencia.TIPO_STATUS,
    )
    try:
        fila_url = reverse("trackhub:fila")
    except Exception:
        fila_url = "/trackhub/"
    if pendencia.criado_por_id and pendencia.criado_por_id != request.user.id:
        core_criar_notificacao(
            pendencia.criado_por,
            "trackhub_etapa_concluida",
            "Pendência concluída",
            f'A pendência "{pendencia.titulo}" foi marcada como concluída.',
            url=fila_url,
            event_key=f"trackhub:pend:{pendencia.pk}",
        )
    if _wants_json_response(request):
        return _json_no_cache({"ok": True})
    messages.success(request, "Pendência concluída.")
    return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)


@login_required
@require_trackhub
@require_POST
def anexo_upload_view(request, pk):
    pendencia = get_object_or_404(_pendencia_queryset_for_user(request.user), pk=pk)
    if not _user_can_edit_pendencia(request.user, pendencia):
        return JsonResponse({"error": "Sem permissão para enviar arquivos."}, status=403)
    arquivos = request.FILES.getlist("arquivos")
    form = AnexoPendenciaUploadForm(
        pendencia.anexos.count(),
        files_list=arquivos,
        data=request.POST,
    )
    if not form.is_valid():
        if form.non_field_errors():
            msg = form.non_field_errors()[0]
        else:
            msg = next(
                (m for msgs in form.errors.values() for m in msgs),
                "Não foi possível validar os arquivos.",
            )
        return JsonResponse({"error": str(msg)}, status=400)

    criados = []
    with transaction.atomic():
        for arquivo, tipo in form.cleaned_data["validated_files"]:
            anexo = AnexoPendencia.objects.create(
                pendencia=pendencia,
                arquivo=arquivo,
                nome_original=arquivo.name,
                tipo=tipo,
                tamanho=getattr(arquivo, "size", 0) or 0,
                enviado_por=request.user,
            )
            _registrar_atividade_pendencia(
                pendencia,
                request.user,
                f'Adicionou arquivo "{anexo.nome_original}"',
                AtividadePendencia.TIPO_ARQUIVO,
            )
            criados.append(
                {
                    "id": anexo.pk,
                    "nome": anexo.nome_original,
                    "tipo": anexo.tipo,
                    "tamanho": anexo.tamanho_formatado,
                    "url": anexo.arquivo.url,
                    "eh_imagem": anexo.eh_imagem,
                }
            )

    return JsonResponse({"success": True, "anexos": criados})


@login_required
@require_trackhub
@require_POST
def anexo_deletar_view(request, pk):
    anexo = get_object_or_404(
        AnexoPendencia.objects.select_related("pendencia"), pk=pk
    )
    if not _pendencia_queryset_for_user(request.user).filter(
        pk=anexo.pendencia_id
    ).exists():
        return JsonResponse({"error": "Acesso negado."}, status=403)
    if not _user_can_edit_pendencia(request.user, anexo.pendencia):
        return JsonResponse({"error": "Sem permissão."}, status=403)

    pend = anexo.pendencia
    nome_orig = anexo.nome_original or ""
    if anexo.arquivo:
        anexo.arquivo.delete(save=False)
    anexo.delete()
    _registrar_atividade_pendencia(
        pend,
        request.user,
        f'Removeu arquivo "{nome_orig}"',
        AtividadePendencia.TIPO_ARQUIVO,
    )
    return JsonResponse({"success": True})


@login_required
@require_trackhub
@require_POST
def pendencia_cancelar_view(request, pk):
    p = get_object_or_404(_pendencia_queryset_for_user(request.user), pk=pk)
    if not _user_can_edit_pendencia(request.user, p):
        messages.error(request, "Você não pode cancelar esta pendência.")
        return redirect("trackhub:pendencia_detalhe", pk=p.pk)
    p.status = "cancelada"
    p.save(update_fields=["status", "updated_at"])
    try:
        from core.notification_utils import marcar_lidas_por_event_key

        marcar_lidas_por_event_key(f"trackhub:pend:{p.pk}")
    except Exception:
        pass
    _registrar_atividade_pendencia(
        p,
        request.user,
        "Marcou a pendência como cancelada",
        AtividadePendencia.TIPO_STATUS,
    )
    messages.success(request, "Pendência cancelada.")
    return redirect("trackhub:fila")


@login_required
@require_trackhub
@require_POST
def pendencia_reativar_view(request, pk):
    p = get_object_or_404(_pendencia_queryset_for_user(request.user), pk=pk)
    if not _user_can_edit_pendencia(request.user, p):
        messages.error(request, "Você não pode reativar esta pendência.")
        return redirect("trackhub:fila")
    if p.status != "cancelada":
        messages.warning(request, "Somente pendências canceladas podem ser reativadas.")
        return redirect("trackhub:fila")
    if p.etapas.exists():
        recalcular_status_pendencia(p)
    else:
        p.status = "aberta"
        p.save(update_fields=["status", "updated_at"])
    _registrar_atividade_pendencia(
        p,
        request.user,
        "Reativou a pendência",
        AtividadePendencia.TIPO_STATUS,
    )
    messages.success(request, "Pendência reativada.")
    return redirect("trackhub:fila")


@login_required
@require_trackhub
@require_POST
def pendencia_deletar_view(request, pk):
    pendencia = get_object_or_404(_pendencia_queryset_for_user(request.user), pk=pk)
    if not _user_can_edit_pendencia(request.user, pendencia):
        messages.error(request, "Você não pode excluir esta pendência.")
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)
    pendencia_pk = pendencia.pk
    try:
        from core.notification_utils import marcar_lidas_por_event_key

        marcar_lidas_por_event_key(f"trackhub:pend:{pendencia_pk}")
    except Exception:
        pass
    with transaction.atomic():
        for anexo in AnexoPendencia.objects.filter(pendencia_id=pendencia_pk):
            if anexo.arquivo:
                anexo.arquivo.delete(save=False)
        etapa_ids = EtapaPendencia.objects.filter(pendencia_id=pendencia_pk).values_list(
            "pk", flat=True
        )
        for arq in AnexoEtapa.objects.filter(etapa_id__in=list(etapa_ids)):
            if arq.arquivo:
                arq.arquivo.delete(save=False)
        coment_ids = ComentarioPendencia.objects.filter(pendencia_id=pendencia_pk).values_list(
            "pk", flat=True
        )
        for ax in AnexoComentario.objects.filter(comentario_id__in=list(coment_ids)):
            if ax.arquivo:
                ax.arquivo.delete(save=False)
        pendencia.delete()
    messages.success(request, "Pendência excluída.")
    return redirect("trackhub:fila")


@login_required
@require_trackhub
@require_POST
def etapa_concluir_view(request, pk):
    e = get_object_or_404(
        EtapaPendencia.objects.select_related("pendencia", "pendencia__obra", "assinatura"),
        pk=pk,
    )
    if not _pendencia_queryset_for_user(request.user).filter(pk=e.pendencia_id).exists():
        if _wants_json_response(request):
            return _json_no_cache({"ok": False, "error": "Acesso negado."}, status=403)
        messages.error(request, "Acesso negado.")
        return redirect("trackhub:fila")
    if not _user_can_conclude_etapa(request.user, e):
        msg = "Sem permissão para concluir esta etapa."
        if _wants_json_response(request):
            return _json_no_cache({"ok": False, "error": msg}, status=403)
        messages.error(request, msg)
        return redirect("trackhub:pendencia_detalhe", pk=e.pendencia_id)

    if e.requer_assinatura:
        if not e.responsavel_interno_id:
            msg = "Esta etapa exige assinatura, mas não possui responsável definido."
            if _wants_json_response(request):
                return _json_no_cache({"ok": False, "error": msg}, status=400)
            messages.error(request, msg)
            return redirect("trackhub:pendencia_detalhe", pk=e.pendencia_id)
        if request.user.id != e.responsavel_interno_id:
            msg = "Somente o responsável da etapa pode assinar e concluir esta etapa."
            if _wants_json_response(request):
                return _json_no_cache({"ok": False, "error": msg}, status=403)
            messages.error(request, msg)
            return redirect("trackhub:pendencia_detalhe", pk=e.pendencia_id)

    if e.requer_assinatura:
        signature_data = (
            request.POST.get(f"signature_etapa_{e.pk}") or ""
        ).strip()
        if signature_data:
            AssinaturaEtapa.objects.update_or_create(
                etapa=e,
                defaults={
                    "signature_data": signature_data,
                    "assinado_por": request.user,
                    "assinado_em": timezone.now(),
                },
            )
        else:
            ass = getattr(e, "assinatura", None)
            if not (ass and getattr(ass, "signature_data", "").strip()):
                msg = "Esta etapa requer assinatura para ser concluída"
                if _wants_json_response(request):
                    return _json_no_cache({"ok": False, "error": msg}, status=400)
                messages.error(request, msg)
                return redirect("trackhub:pendencia_detalhe", pk=e.pendencia_id)

    titulo_etapa = e.titulo
    e.status = "concluida"
    e.concluida_em = timezone.now()
    e.concluida_por = request.user
    e.save(update_fields=["status", "concluida_em", "concluida_por"])

    try:
        from core.notification_utils import marcar_lidas_por_event_key_etapa_trackhub

        marcar_lidas_por_event_key_etapa_trackhub(e.pk)
    except Exception:
        pass

    pend = Pendencia.objects.get(pk=e.pendencia_id)
    status_antes = pend.status
    recalcular_status_pendencia(pend)
    pend.refresh_from_db()

    _registrar_atividade_pendencia(
        pend,
        request.user,
        f'Concluiu a etapa "{titulo_etapa}"',
        AtividadePendencia.TIPO_ETAPA,
    )

    try:
        fila_url = reverse("trackhub:fila")
    except Exception:
        fila_url = "/trackhub/"
    nome_quem = request.user.get_full_name() or request.user.username
    if pend.criado_por_id and pend.criado_por_id != request.user.id:
        core_criar_notificacao(
            pend.criado_por,
            "trackhub_etapa_concluida",
            f"Etapa concluída: {titulo_etapa}",
            f'A etapa "{titulo_etapa}" da pendência "{pend.titulo}" foi concluída por {nome_quem}.',
            url=fila_url,
            event_key=f"trackhub:pend:{pend.pk}",
        )
    if pend.status == "concluida" and status_antes != "concluida":
        if pend.criado_por_id and pend.criado_por_id != request.user.id:
            core_criar_notificacao(
                pend.criado_por,
                "trackhub_etapa_concluida",
                "Pendência concluída",
                f'A pendência "{pend.titulo}" foi totalmente concluída.',
                url=fila_url,
                event_key=f"trackhub:pend:{pend.pk}",
            )
        try:
            from core.notification_utils import marcar_lidas_por_event_key

            marcar_lidas_por_event_key(f"trackhub:pend:{pend.pk}")
        except Exception:
            pass

    if _wants_json_response(request):
        return _json_no_cache({"ok": True, "pendencia_id": e.pendencia_id})
    messages.success(request, "Etapa concluída.")
    return redirect("trackhub:pendencia_detalhe", pk=e.pendencia_id)


@login_required
@require_trackhub
@require_POST
def etapa_reabrir_view(request, pk):
    etapa = get_object_or_404(
        EtapaPendencia.objects.select_related("pendencia"),
        pk=pk,
    )
    pendencia = etapa.pendencia
    if not _pendencia_queryset_for_user(request.user).filter(pk=pendencia.pk).exists():
        msg = "Acesso negado."
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": msg}, status=403)
        messages.error(request, msg)
        return redirect("trackhub:fila")
    if not _user_can_edit_pendencia(request.user, pendencia):
        msg = "Sem permissão para editar esta pendência."
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": msg}, status=403)
        messages.error(request, msg)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)
    if pendencia.status == "cancelada":
        msg = "Não é possível reabrir etapas de uma pendência cancelada."
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)
    if etapa.status != "concluida":
        msg = "Só é possível reabrir etapas concluídas."
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)

    titulo_et = etapa.titulo
    etapa.status = "pendente"
    etapa.concluida_em = None
    etapa.concluida_por = None
    etapa.save(update_fields=["status", "concluida_em", "concluida_por"])

    recalcular_status_pendencia(pendencia)
    pendencia.refresh_from_db()

    _registrar_atividade_pendencia(
        pendencia,
        request.user,
        f'Reabriu a etapa "{titulo_et}"',
        AtividadePendencia.TIPO_ETAPA,
    )
    sync_recorrencia_etapas_snapshot_if_linked(pendencia.pk)

    if _wants_json_response(request):
        return JsonResponse(
            {
                "success": True,
                "pendencia": _pendencia_detail_payload(pendencia, request),
            }
        )
    messages.success(request, "Etapa reaberta.")
    return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)


@login_required
@require_trackhub
@require_POST
def etapa_notificar_view(request, pk):
    etapa = get_object_or_404(
        EtapaPendencia.objects.select_related("pendencia", "pendencia__obra"),
        pk=pk,
    )
    if not _pendencia_queryset_for_user(request.user).filter(
        pk=etapa.pendencia_id
    ).exists():
        return JsonResponse(
            {"success": False, "error": "Acesso negado."},
            status=403,
        )
    if not _user_can_edit_pendencia(request.user, etapa.pendencia):
        return JsonResponse(
            {"success": False, "error": "Sem permissão para notificar nesta etapa."},
            status=403,
        )

    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse(
                {"success": False, "error": "JSON inválido."},
                status=400,
            )
        form = NotificacaoEtapaForm(payload)
    else:
        form = NotificacaoEtapaForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"success": False, "errors": form.errors}, status=400)

    n = NotificacaoPendencia.objects.create(
        etapa=etapa,
        enviado_por=request.user,
        canal=form.cleaned_data["canal"],
        destinatario_nome=form.cleaned_data["destinatario_nome"],
        destinatario_contato=form.cleaned_data["destinatario_contato"],
        mensagem=form.cleaned_data["mensagem"],
    )

    if n.canal == "email":
        dest_email = (form.cleaned_data["destinatario_contato"] or "").strip()
        try:
            from core.comunicacao_constants import TIPO_TRACKHUB_NOTIFICACAO_ETAPA_EMAIL
            from core.comunicacao_router import ComunicacaoPreferenciasService

            usuario_destino = User.objects.filter(
                email__iexact=dest_email,
                is_active=True,
            ).first()
            decisao = ComunicacaoPreferenciasService().pode_enviar_email(
                dest_email,
                TIPO_TRACKHUB_NOTIFICACAO_ETAPA_EMAIL,
                usuario=usuario_destino,
                contexto={
                    "modulo": "trackhub",
                    "objeto_tipo": "etapa_pendencia",
                    "objeto_id": etapa.pk,
                    "origem": "trackhub_notificacao_manual",
                },
            )
            if not decisao.enviar:
                return JsonResponse(
                    {
                        "success": True,
                        "blocked_by_preference": True,
                        "message": "E-mail não enviado por preferência do destinatário.",
                    }
                )
            send_mail(
                subject=f"Pendência: {etapa.pendencia.titulo}",
                message=n.mensagem,
                from_email=getattr(
                    settings,
                    "DEFAULT_FROM_EMAIL",
                    None,
                )
                or "noreply@example.com",
                recipient_list=[dest_email],
                fail_silently=False,
            )
        except Exception as exc:
            return JsonResponse(
                {"success": False, "error": str(exc)},
                status=500,
            )

    return JsonResponse({"success": True})


@login_required
@require_trackhub
@require_POST
def comentario_criar_view(request, pk):
    p = get_object_or_404(_pendencia_queryset_for_user(request.user), pk=pk)
    if not _user_can_comment_pendencia(request.user, p):
        messages.error(request, "Sem permissão para comentar nesta pendência.")
        return redirect("trackhub:pendencia_detalhe", pk=pk)
    texto = sanitize_rich_text(request.POST.get("texto"))
    arquivos = [
        f
        for f in request.FILES.getlist("arquivos_comentario")
        if f and getattr(f, "name", None)
    ]
    if rich_text_is_empty(texto) and not arquivos:
        messages.error(request, "Escreva um comentário ou anexe pelo menos um arquivo.")
        return redirect("trackhub:pendencia_detalhe", pk=pk)
    c = ComentarioPendencia.objects.create(
        pendencia=p,
        autor=request.user,
        texto=texto,
    )
    for arq in arquivos:
        AnexoComentario.objects.create(
            comentario=c,
            arquivo=arq,
            nome_original=arq.name,
            tamanho=getattr(arq, "size", 0) or 0,
        )
    messages.success(request, "Comentário adicionado.")
    return redirect("trackhub:pendencia_detalhe", pk=pk)


@login_required
@require_trackhub
@require_http_methods(["POST"])
def pendencia_etapas_reordenar_view(request, pk):
    pendencia = get_object_or_404(_pendencia_queryset_for_user(request.user), pk=pk)
    if not _user_can_edit_pendencia(request.user, pendencia):
        return _json_no_cache({"ok": False, "error": "Sem permissão para editar."}, status=403)
    if pendencia.status in ("concluida", "cancelada"):
        return _json_no_cache(
            {"ok": False, "error": "Não é possível reordenar etapas neste estado."},
            status=400,
        )
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_no_cache({"ok": False, "error": "JSON inválido."}, status=400)
    raw_ids = payload.get("ordem_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        return _json_no_cache(
            {"ok": False, "error": "Informe ordem_ids (lista de IDs das etapas)."},
            status=400,
        )
    ids = []
    for x in raw_ids:
        try:
            ids.append(int(x))
        except (TypeError, ValueError):
            return _json_no_cache({"ok": False, "error": "IDs de etapa inválidos."}, status=400)
    existing = list(
        pendencia.etapas.order_by("ordem").values_list("pk", flat=True)
    )
    if len(ids) != len(existing) or sorted(ids) != sorted(existing):
        return _json_no_cache(
            {"ok": False, "error": "A lista de etapas não corresponde a esta pendência."},
            status=400,
        )
    with transaction.atomic():
        for idx, etapa_id in enumerate(ids, start=1):
            pendencia.etapas.filter(pk=etapa_id).update(ordem=idx)
        _registrar_atividade_pendencia(
            pendencia,
            request.user,
            "Reordenou as etapas da pendência.",
            AtividadePendencia.TIPO_ETAPA,
        )
    sync_recorrencia_etapas_snapshot_if_linked(pendencia.pk)
    pendencia.refresh_from_db()
    return _json_no_cache(
        {"ok": True, "pendencia": _pendencia_detail_payload(pendencia, request)}
    )


@login_required
@require_trackhub
@require_http_methods(["GET"])
def pendencia_detail_ajax(request, pk):
    pendencia = _pendencia_prefetched_for_detail(request.user, pk)
    return _json_no_cache(
        {"ok": True, "pendencia": _pendencia_detail_payload(pendencia, request)}
    )


@login_required
@require_trackhub
@require_http_methods(["POST"])
@transaction.atomic
def pendencia_update_field(request, pk):
    pendencia = get_object_or_404(_pendencia_queryset_for_user(request.user), pk=pk)
    if not _user_can_edit_pendencia(request.user, pendencia):
        return _json_no_cache({"ok": False, "error": "Sem permissão para editar."}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_no_cache({"ok": False, "error": "JSON inválido."}, status=400)
    field = (payload.get("field") or "").strip()
    value = payload.get("value")
    if field not in ALLOWED_PENDENCIA_UPDATE_FIELDS:
        return _json_no_cache({"ok": False, "error": "Campo não suportado."}, status=400)

    actor = request.user
    status_labels = dict(Pendencia.STATUS_CHOICES)
    prio_labels = dict(Pendencia.PRIORIDADE_CHOICES)
    tipo_labels = dict(Pendencia.TIPO_CHOICES)

    if field == "titulo":
        t = (value if isinstance(value, str) else "").strip()
        if not t:
            return _json_no_cache(
                {"ok": False, "error": "O título não pode ficar vazio."}, status=400
            )
        pendencia.titulo = t
        pendencia.save(update_fields=["titulo", "updated_at"])
        _registrar_atividade_pendencia(
            pendencia, actor, "Alterou título", AtividadePendencia.TIPO_TITULO
        )
    elif field == "descricao":
        pendencia.descricao = sanitize_rich_text(str(value) if value is not None else "")
        pendencia.save(update_fields=["descricao", "updated_at"])
        _registrar_atividade_pendencia(
            pendencia, actor, "Alterou descrição", AtividadePendencia.TIPO_DESCRICAO
        )
    elif field == "status":
        v = value if isinstance(value, str) else ""
        valid = {c[0] for c in Pendencia.STATUS_CHOICES}
        if v not in valid:
            return _json_no_cache({"ok": False, "error": "Status inválido."}, status=400)
        if v == "concluida" and pendencia.etapas.filter(status="pendente").exists():
            return _json_no_cache(
                {
                    "ok": False,
                    "error": "Existem etapas pendentes. Conclua todas antes de concluir.",
                },
                status=400,
            )
        old = pendencia.status
        pendencia.status = v
        pendencia.save(update_fields=["status", "updated_at"])
        _registrar_atividade_pendencia(
            pendencia,
            actor,
            f'Alterou status de "{status_labels.get(old, old)}" → "{status_labels.get(v, v)}"',
            AtividadePendencia.TIPO_STATUS,
        )
    elif field == "prioridade":
        v = value if isinstance(value, str) else ""
        valid = {c[0] for c in Pendencia.PRIORIDADE_CHOICES}
        if v not in valid:
            return _json_no_cache(
                {"ok": False, "error": "Prioridade inválida."}, status=400
            )
        old = pendencia.prioridade
        pendencia.prioridade = v
        pendencia.save(update_fields=["prioridade", "updated_at"])
        _registrar_atividade_pendencia(
            pendencia,
            actor,
            f'Alterou prioridade de "{prio_labels.get(old, old)}" → "{prio_labels.get(v, v)}"',
            AtividadePendencia.TIPO_PRIORIDADE,
        )
    elif field == "tipo":
        v = value if isinstance(value, str) else ""
        valid = {c[0] for c in Pendencia.TIPO_CHOICES}
        if v not in valid:
            return _json_no_cache({"ok": False, "error": "Tipo inválido."}, status=400)
        old = pendencia.tipo
        pendencia.tipo = v
        pendencia.save(update_fields=["tipo", "updated_at"])
        _registrar_atividade_pendencia(
            pendencia,
            actor,
            f'Alterou tipo de "{tipo_labels.get(old, old)}" → "{tipo_labels.get(v, v)}"',
            AtividadePendencia.TIPO_TIPO,
        )
    elif field == "data_inicio":
        old_di = pendencia.data_inicio
        new_di = None
        if value is None or value == "":
            new_di = None
        else:
            if not isinstance(value, str):
                return _json_no_cache(
                    {"ok": False, "error": "Data início inválida."}, status=400
                )
            try:
                new_di = date.fromisoformat(value.strip())
            except ValueError:
                return _json_no_cache(
                    {"ok": False, "error": "Use a data no formato YYYY-MM-DD."},
                    status=400,
                )
        if new_di is None:
            if pendencia.created_at:
                inicio_val = timezone.localtime(pendencia.created_at).date()
            else:
                inicio_val = timezone.localdate()
        else:
            inicio_val = new_di
        err = validar_data_fim_pendencia(pendencia.prazo, inicio_val)
        if err:
            return _json_no_cache({"ok": False, "error": err}, status=400)
        pendencia.data_inicio = new_di
        pendencia.save(update_fields=["data_inicio", "updated_at"])

        def _fmt_di(d):
            return d.strftime("%d/%m/%Y") if d else ""

        ant = _fmt_di(old_di) if old_di else _fmt_di(pendencia.data_inicio_efetiva)
        novo = _fmt_di(pendencia.data_inicio) if pendencia.data_inicio else _fmt_di(
            pendencia.data_inicio_efetiva
        )
        if old_di != pendencia.data_inicio:
            if pendencia.data_inicio:
                txt = f"Alterou data início de {ant} → {novo}"
            else:
                txt = f"Removeu data início definida (efetiva: {novo})"
            _registrar_atividade_pendencia(
                pendencia, actor, txt, AtividadePendencia.TIPO_PRAZO
            )
        sync_recorrencia_etapas_snapshot_if_linked(pendencia.pk)

    elif field == "prazo":
        old_prazo = pendencia.prazo
        new_prazo = None
        if value is None or value == "":
            new_prazo = None
        else:
            if not isinstance(value, str):
                return _json_no_cache(
                    {"ok": False, "error": "Data fim inválida."}, status=400
                )
            try:
                new_prazo = date.fromisoformat(value.strip())
            except ValueError:
                return _json_no_cache(
                    {"ok": False, "error": "Use a data no formato YYYY-MM-DD."},
                    status=400,
                )
        err = validar_data_fim_pendencia(
            new_prazo, pendencia.data_inicio, pendencia=pendencia
        )
        if err:
            return _json_no_cache({"ok": False, "error": err}, status=400)
        pendencia.prazo = new_prazo
        pendencia.save(update_fields=["prazo", "updated_at"])
        novo_p = pendencia.prazo

        def _fmt(d):
            return d.strftime("%d/%m/%Y") if d else ""

        if old_prazo and novo_p:
            txt = f"Alterou data fim de {_fmt(old_prazo)} → {_fmt(novo_p)}"
        elif not old_prazo and novo_p:
            txt = f"Definiu data fim para {_fmt(novo_p)}"
        elif old_prazo and not novo_p:
            txt = "Removeu a data fim"
        else:
            txt = None
        if txt:
            _registrar_atividade_pendencia(
                pendencia, actor, txt, AtividadePendencia.TIPO_PRAZO
            )
        sync_recorrencia_etapas_snapshot_if_linked(pendencia.pk)

    elif field == "hora_inicio":
        old_h = pendencia.hora_inicio
        try:
            new_h = _parse_hora_pendencia(value)
        except (ValueError, TypeError):
            return _json_no_cache(
                {"ok": False, "error": "Horário início inválido. Use HH:MM."},
                status=400,
            )

        def _fmt_h(t):
            return _hora_pendencia_para_str(t) if t else "—"

        pendencia.hora_inicio = new_h
        pendencia.save(update_fields=["hora_inicio", "updated_at"])
        if old_h != new_h:
            if new_h:
                txt = f"Alterou horário início de {_fmt_h(old_h)} → {_fmt_h(new_h)}"
            else:
                txt = f"Removeu horário início (era {_fmt_h(old_h)})"
            _registrar_atividade_pendencia(
                pendencia, actor, txt, AtividadePendencia.TIPO_PRAZO
            )
        sync_recorrencia_etapas_snapshot_if_linked(pendencia.pk)

    elif field == "hora_fim":
        old_h = pendencia.hora_fim
        try:
            new_h = _parse_hora_pendencia(value)
        except (ValueError, TypeError):
            return _json_no_cache(
                {"ok": False, "error": "Horário fim inválido. Use HH:MM."},
                status=400,
            )

        def _fmt_hf(t):
            return _hora_pendencia_para_str(t) if t else "—"

        pendencia.hora_fim = new_h
        pendencia.save(update_fields=["hora_fim", "updated_at"])
        if old_h != new_h:
            if old_h and new_h:
                txt = f"Alterou horário fim de {_fmt_hf(old_h)} → {_fmt_hf(new_h)}"
            elif not old_h and new_h:
                txt = f"Definiu horário fim para {_fmt_hf(new_h)}"
            elif old_h and not new_h:
                txt = "Removeu o horário fim"
            else:
                txt = None
            if txt:
                _registrar_atividade_pendencia(
                    pendencia, actor, txt, AtividadePendencia.TIPO_PRAZO
                )
        sync_recorrencia_etapas_snapshot_if_linked(pendencia.pk)

    elif field == "responsavel_interno":
        # Accept null/empty to clear, or numeric user id to set as internal responsible
        old_user = pendencia.responsavel_interno
        if value is None or value == "":
            pendencia.responsavel_interno = None
            pendencia.save(update_fields=["responsavel_interno", "updated_at"])
            _registrar_atividade_pendencia(
                pendencia,
                actor,
                f"Removeu responsável interno ({_user_display_name(old_user)})",
                AtividadePendencia.TIPO_GERAL,
            )
        else:
            try:
                uid = int(value)
            except (TypeError, ValueError):
                return _json_no_cache({"ok": False, "error": "Responsável inválido."}, status=400)
            try:
                u = User.objects.get(pk=uid)
            except User.DoesNotExist:
                return _json_no_cache({"ok": False, "error": "Usuário não encontrado."}, status=404)
            pendencia.responsavel_interno = u
            pendencia.save(update_fields=["responsavel_interno", "updated_at"])
            _registrar_atividade_pendencia(
                pendencia,
                actor,
                f'Alterou responsável interno de "{_user_display_name(old_user)}" → "{_user_display_name(u)}"',
                AtividadePendencia.TIPO_GERAL,
            )

    pendencia = _pendencia_prefetched_by_pk(pk)
    payload = _pendencia_detail_payload(pendencia, request)
    perdeu_acesso = not _pendencia_queryset_for_user(request.user).filter(pk=pk).exists()
    return _json_no_cache(
        {
            "ok": True,
            "field": field,
            "pendencia": payload,
            "perdeu_acesso": perdeu_acesso,
        }
    )


@login_required
@require_trackhub
@require_http_methods(["GET"])
def pendencia_atividades_ajax(request, pk):
    pendencia = get_object_or_404(_pendencia_queryset_for_user(request.user), pk=pk)
    qs = (
        AtividadePendencia.objects.filter(pendencia=pendencia)
        .select_related("usuario")
        .order_by("-criado_em")
    )
    return _json_no_cache(
        {
            "ok": True,
            "atividades": [_serialize_atividade_pendencia(a) for a in qs],
        }
    )


@login_required
@require_trackhub
@require_http_methods(["GET", "POST"])
def pendencia_comentarios_ajax(request, pk):
    pendencia = get_object_or_404(_pendencia_queryset_for_user(request.user), pk=pk)
    if request.method == "GET":
        qs = (
            ComentarioPendencia.objects.filter(pendencia=pendencia)
            .select_related("autor")
            .prefetch_related(
                Prefetch(
                    "anexos",
                    queryset=AnexoComentario.objects.order_by("enviado_em"),
                )
            )
            .order_by("created_at")
        )
        return _json_no_cache(
            {
                "ok": True,
                "comentarios": [_serialize_comentario_pendencia(c, request) for c in qs],
            }
        )
    if not _user_can_comment_pendencia(request.user, pendencia):
        return _json_no_cache(
            {"ok": False, "error": "Sem permissão para comentar nesta pendência."},
            status=403,
        )

    texto = sanitize_rich_text(request.POST.get("texto"))
    arquivos = [
        f
        for f in request.FILES.getlist("arquivos_comentario")
        if f and getattr(f, "name", None)
    ]
    if rich_text_is_empty(texto) and not arquivos:
        return _json_no_cache(
            {"ok": False, "error": "Escreva um comentário ou anexe pelo menos um arquivo."},
            status=400,
        )
    c = ComentarioPendencia.objects.create(
        pendencia=pendencia,
        autor=request.user,
        texto=texto,
    )
    for arq in arquivos:
        AnexoComentario.objects.create(
            comentario=c,
            arquivo=arq,
            nome_original=arq.name,
            tamanho=getattr(arq, "size", 0) or 0,
        )
    c = (
        ComentarioPendencia.objects.select_related("autor")
        .prefetch_related(
            Prefetch(
                "anexos",
                queryset=AnexoComentario.objects.order_by("enviado_em"),
            )
        )
        .get(pk=c.pk)
    )
    if not rich_text_is_empty(texto):
        prev = rich_text_to_plain_preview(texto, 120)
        descricao = f'Comentou: "{prev}"'
    else:
        descricao = f"Comentou com {len(arquivos)} arquivo(s)"
    _registrar_atividade_pendencia(
        pendencia,
        request.user,
        descricao,
        AtividadePendencia.TIPO_COMENTARIO,
    )
    return _json_no_cache(
        {"ok": True, "comentario": _serialize_comentario_pendencia(c, request)}
    )


@login_required
@require_trackhub
@require_POST
def etapa_adicionar_view(request, pk):
    pendencia = get_object_or_404(_pendencia_queryset_for_user(request.user), pk=pk)
    if not _user_can_edit_pendencia(request.user, pendencia):
        msg = "Sem permissão para editar esta pendência."
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": msg}, status=403)
        messages.error(request, msg)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)

    parsed, err = _parse_etapa_form_post(request)
    if err:
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": err}, status=400)
        messages.error(request, err)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)

    max_ordem = pendencia.etapas.aggregate(m=Max("ordem"))["m"] or 0
    nova_ordem = max_ordem + 1

    with transaction.atomic():
        et = EtapaPendencia.objects.create(
            pendencia=pendencia,
            titulo=parsed["titulo"],
            ordem=nova_ordem,
            responsavel_interno=parsed["responsavel"],
            prazo=parsed["prazo"],
            requer_assinatura=parsed["requer_assinatura"],
            observacao=parsed["observacao"],
        )
        _salvar_anexos_etapa_nova(request, et, request.user)
        _notificar_criacao_etapa(et, request.user)
        if et.prazo and (pendencia.prazo is None or et.prazo > pendencia.prazo):
            prazo_anterior = pendencia.prazo
            pendencia.prazo = et.prazo
            pendencia.save(update_fields=["prazo"])
            if prazo_anterior is None:
                msg_prazo = f'Prazo definido automaticamente para {et.prazo.strftime("%d/%m/%Y")} pela etapa "{et.titulo}"'
            else:
                msg_prazo = f'Prazo atualizado automaticamente de {prazo_anterior.strftime("%d/%m/%Y")} → {et.prazo.strftime("%d/%m/%Y")} pela etapa "{et.titulo}"'
            _registrar_atividade_pendencia(pendencia, request.user, msg_prazo, AtividadePendencia.TIPO_PRAZO)
        recalcular_status_pendencia(pendencia)
        _registrar_atividade_pendencia(
            pendencia,
            request.user,
            f'Adicionou etapa: "{parsed["titulo"]}"',
            AtividadePendencia.TIPO_ETAPA,
        )

    sync_recorrencia_etapas_snapshot_if_linked(pendencia.pk)

    if _wants_json_response(request):
        pendencia.refresh_from_db()
        return JsonResponse(
            {
                "success": True,
                "pendencia": _pendencia_detail_payload(pendencia, request),
            }
        )
    messages.success(request, "Etapa adicionada.")
    return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)


@login_required
@require_trackhub
@require_POST
def etapa_editar_view(request, pk):
    etapa = get_object_or_404(
        EtapaPendencia.objects.select_related("pendencia"),
        pk=pk,
    )
    pendencia = etapa.pendencia
    if not _pendencia_queryset_for_user(request.user).filter(pk=pendencia.pk).exists():
        msg = "Acesso negado."
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": msg}, status=403)
        messages.error(request, msg)
        return redirect("trackhub:fila")
    if not _user_can_edit_pendencia(request.user, pendencia):
        msg = "Sem permissão para editar esta pendência."
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": msg}, status=403)
        messages.error(request, msg)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)
    if pendencia.status in ("concluida", "cancelada"):
        msg = "Não é possível editar etapas neste estado da pendência."
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)
    if etapa.status == "concluida":
        msg = "Não é possível editar uma etapa já concluída."
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)

    parsed, err = _parse_etapa_form_post(request)
    if err:
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": err}, status=400)
        messages.error(request, err)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)

    descricoes_edicao = _descricoes_edicao_etapa(etapa, parsed)
    with transaction.atomic():
        etapa.titulo = parsed["titulo"]
        etapa.responsavel_interno = parsed["responsavel"]
        etapa.prazo = parsed["prazo"]
        etapa.requer_assinatura = parsed["requer_assinatura"]
        etapa.observacao = parsed["observacao"]
        etapa.save(
            update_fields=[
                "titulo",
                "responsavel_interno",
                "prazo",
                "requer_assinatura",
                "observacao",
            ]
        )
        if etapa.prazo and (pendencia.prazo is None or etapa.prazo > pendencia.prazo):
            prazo_anterior = pendencia.prazo
            pendencia.prazo = etapa.prazo
            pendencia.save(update_fields=["prazo"])
            if prazo_anterior is None:
                msg_prazo = f'Prazo definido automaticamente para {etapa.prazo.strftime("%d/%m/%Y")} pela etapa "{etapa.titulo}"'
            else:
                msg_prazo = f'Prazo atualizado automaticamente de {prazo_anterior.strftime("%d/%m/%Y")} → {etapa.prazo.strftime("%d/%m/%Y")} pela etapa "{etapa.titulo}"'
            _registrar_atividade_pendencia(pendencia, request.user, msg_prazo, AtividadePendencia.TIPO_PRAZO)
        for descricao in descricoes_edicao:
            _registrar_atividade_pendencia(
                pendencia,
                request.user,
                descricao,
                AtividadePendencia.TIPO_ETAPA,
            )
    sync_recorrencia_etapas_snapshot_if_linked(pendencia.pk)
    pendencia.refresh_from_db()

    if _wants_json_response(request):
        return JsonResponse(
            {
                "success": True,
                "pendencia": _pendencia_detail_payload(pendencia, request),
            }
        )
    messages.success(request, "Etapa atualizada.")
    return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)


@login_required
@require_trackhub
@require_POST
def etapa_deletar_view(request, pk):
    etapa = get_object_or_404(
        EtapaPendencia.objects.select_related("pendencia"),
        pk=pk,
    )
    pendencia = etapa.pendencia
    if not _pendencia_queryset_for_user(request.user).filter(pk=pendencia.pk).exists():
        msg = "Acesso negado."
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": msg}, status=403)
        messages.error(request, msg)
        return redirect("trackhub:fila")
    if not _user_can_edit_pendencia(request.user, pendencia):
        msg = "Sem permissão para editar esta pendência."
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": msg}, status=403)
        messages.error(request, msg)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)
    if pendencia.status in ("concluida", "cancelada"):
        msg = "Não é possível excluir etapas neste estado da pendência."
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)
    if etapa.status != "pendente":
        msg = "Só é possível excluir etapas pendentes."
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)

    titulo_et = etapa.titulo
    with transaction.atomic():
        etapa.delete()
        _renumber_etapas_ordem(pendencia)
        recalcular_status_pendencia(pendencia)
        _registrar_atividade_pendencia(
            pendencia,
            request.user,
            f'Excluiu etapa: "{titulo_et}"',
            AtividadePendencia.TIPO_ETAPA,
        )
    sync_recorrencia_etapas_snapshot_if_linked(pendencia.pk)
    pendencia.refresh_from_db()

    if _wants_json_response(request):
        return JsonResponse(
            {
                "success": True,
                "pendencia": _pendencia_detail_payload(pendencia, request),
            }
        )
    messages.success(request, "Etapa excluída.")
    return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)
