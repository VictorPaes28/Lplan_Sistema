import calendar
import json
from collections import defaultdict
from datetime import date, timedelta
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
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from accounts.decorators import login_required
from core.models import ProjectDiaryApprover, ProjectMember, ProjectOwner
from core.models import Notification
from mapa_obras.models import Obra

from accounts.groups import GRUPOS, usuario_tem_administracao_global_na_plataforma
from .decorators import require_trackhub
from .forms import (
    AnexoPendenciaUploadForm,
    EtapaFormSet,
    NotificacaoEtapaForm,
    ObraFilterForm,
    PendenciaForm,
    tipo_anexo_por_nome,
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
    {"titulo", "descricao", "status", "prioridade", "tipo", "prazo"}
)


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


def _criar_notificacao_trackhub(usuario, titulo, mensagem):
    if not usuario or not getattr(usuario, "is_active", False):
        return
    Notification.objects.create(
        user=usuario,
        notification_type="system",
        title=titulo,
        message=mensagem,
        related_diary=None,
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
    for usuario in _usuarios_responsaveis_da_pendencia(pendencia):
        if autor and usuario.pk == autor.pk:
            continue
        _criar_notificacao_trackhub(usuario, titulo, mensagem)


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
    _criar_notificacao_trackhub(usuario, titulo, mensagem)


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
    for e in pendencia.etapas.all():
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
                "status": e.status,
                "status_display": e.get_status_display(),
                "responsavel_nome": e.responsavel_nome,
                "prazo": e.prazo.isoformat() if e.prazo else "",
                "requer_assinatura": e.requer_assinatura,
                "tem_assinatura": tem_assinatura,
                "observacao": e.observacao or "",
                "anexos_count": len(arquivos_etapa),
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
    pode_concluir = etapas_pendentes_count == 0 and pendencia.status not in (
        "concluida",
        "cancelada",
    )

    pode_editar = _user_can_edit_pendencia(request.user, pendencia)
    responsaveis_obra = (
        _responsaveis_por_obra_payload(Obra.objects.filter(pk=pendencia.obra_id))
        if pendencia.obra_id
        else []
    )
    usuarios_modal = responsaveis_obra[0]["pessoas"] if responsaveis_obra else []

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
        "prazo": pendencia.prazo.isoformat() if pendencia.prazo else "",
        "obra_id": pendencia.obra_id,
        "obra_nome": pendencia.obra.nome,
        "created_at": _format_trackhub_datetime(pendencia.created_at),
        "updated_at": _format_trackhub_datetime(pendencia.updated_at),
        "criado_por_nome": _user_display_name(pendencia.criado_por),
        "pode_editar": pode_editar,
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
    }


def _pendencia_prefetched_for_detail(user, pk):
    return get_object_or_404(
        _pendencia_queryset_for_user(user)
        .select_related("obra", "criado_por")
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
        ),
        pk=pk,
    )


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


def _trackhub_roles(user):
    if user.is_superuser or user.is_staff:
        return {"admin": True, "aprovador": True, "solicitante": True}
    gset = set(user.groups.values_list("name", flat=True))
    # Grupo legado TrackHub mantém acesso administrativo por compatibilidade.
    legacy_admin = GRUPOS.TRACKHUB in gset
    plat_admin = usuario_tem_administracao_global_na_plataforma(user)
    return {
        "admin": plat_admin or legacy_admin,
        "aprovador": GRUPOS.TRACKHUB_APROVADOR in gset,
        "solicitante": GRUPOS.TRACKHUB_SOLICITANTE in gset,
    }


def _obras_queryset_for_user(user):
    """Escopo de obras conforme papéis TrackHub e vínculos de projeto."""
    # Apenas superuser/staff têm visão global; demais papéis do TrackHub
    # devem enxergar somente obras ativas dentro dos projetos vinculados.
    if user.is_superuser or user.is_staff:
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
            nome = usr.get_full_name().strip() or usr.username
            pessoas.append(
                {
                    "id": usr.pk,
                    "nome": nome,
                    "iniciais": _iniciais(nome),
                }
            )
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
    roles = _trackhub_roles(user)
    obras = _obras_queryset_for_user(user)
    qs = Pendencia.objects.filter(obra__in=obras)
    if roles["admin"] or roles["aprovador"]:
        return qs
    if roles["solicitante"]:
        return (
            Pendencia.objects.filter(
                Q(pk__in=qs.values("pk"))
                | Q(criado_por=user)
                | Q(etapas__responsavel_interno=user)
            )
            .distinct()
        )
    return Pendencia.objects.none()


def _pendencia_queryset_for_user(user):
    return _pendencias_qs_for_user(user)


def _user_can_edit_pendencia(user, pendencia):
    roles = _trackhub_roles(user)
    if roles["admin"] or roles["aprovador"]:
        return True
    if roles["solicitante"]:
        if pendencia.criado_por_id == user.id:
            return True
        return pendencia.etapas.filter(responsavel_interno_id=user.id).exists()
    return False


def _pks_pode_editar_trackhub(user, pendencias):
    """PKs de pendências que o usuário pode alterar na UI."""
    return {p.pk for p in pendencias if _user_can_edit_pendencia(user, p)}


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
    base = _pendencias_qs_for_user(user)
    return {
        "total_pendencias": base.count(),
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
    ).count()
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
    if p.esta_vencida or p.prazo < hoje:
        return "vencida"
    if p.prazo <= hoje + timedelta(days=7):
        return "soon"
    return "ok"


def _fila_sort_key(p):
    return (
        0 if p.esta_vencida else 1,
        _PRIORIDADE_ORDER.get(p.prioridade, 9),
        p.prazo or date.max,
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

    if obra_id and str(obra_id).isdigit():
        qs = qs.filter(obra_id=int(obra_id))
    if tipo:
        qs = qs.filter(tipo=tipo)
    if prioridade:
        qs = qs.filter(prioridade=prioridade)
    if status:
        qs = qs.filter(status=status)

    hoje = timezone.localdate()
    items = list(qs)
    for p in items:
        p.th_prazo_class = _th_prazo_class(p, hoje)
    items.sort(key=_fila_sort_key)

    paginator = Paginator(items, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    pode_editar_trackhub_pks = _pks_pode_editar_trackhub(request.user, page_obj.object_list)

    filtros = {
        "obra": obra_id or "",
        "tipo": tipo,
        "prioridade": prioridade,
        "status": status,
    }

    ctx = {
        "obras": obras_qs,
        "page_obj": page_obj,
        "filtros": filtros,
        "stats": _fila_stats_for_user(request.user),
        "pagination_qs": _pagination_qs(request),
        "pode_editar_trackhub_pks": pode_editar_trackhub_pks,
    }
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


@login_required
@require_trackhub
def calendario_view(request):
    today = timezone.localdate()
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

    prev_year, prev_month, next_year, next_month = _prev_next_month(year, month)

    _, last_day = calendar.monthrange(year, month)
    inicio = date(year, month, 1)
    fim = date(year, month, last_day)

    obras_qs = _obras_queryset_for_user(request.user)
    obra_id = request.GET.get("obra")
    qs = (
        Pendencia.objects.filter(
            obra__in=obras_qs,
            prazo__gte=inicio,
            prazo__lte=fim,
        )
        .select_related("obra")
        .order_by("prazo", "titulo")
    )
    if obra_id and str(obra_id).isdigit():
        qs = qs.filter(obra_id=int(obra_id))

    by_day = defaultdict(list)
    for p in qs:
        if p.prazo:
            by_day[p.prazo].append(p)

    cal = calendar.Calendar(firstweekday=calendar.SUNDAY)
    calendar_weeks = []
    for week in cal.monthdatescalendar(year, month):
        row = []
        for d in week:
            row.append(
                {
                    "date": d,
                    "current_month": d.month == month,
                    "is_today": d == today,
                    "pendencias": by_day.get(d, []),
                }
            )
        calendar_weeks.append(row)

    month_label = f"{_MONTHS_PT[month]} {year}"

    filtros = {"obra": obra_id or ""}

    ctx = {
        "calendar_weeks": calendar_weeks,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "month_label": month_label,
        "year": year,
        "month": month,
        "obras": obras_qs,
        "filtros": filtros,
    }
    ctx.update(_nav_tab_context(request.user))
    return render(request, "trackhub/calendario.html", ctx)


@login_required
@require_trackhub
def pendencia_criar_view(request):
    obras_qs = _obras_queryset_for_user(request.user)
    responsaveis_por_obra = _responsaveis_por_obra_payload(obras_qs)

    if request.method == "POST":
        form = PendenciaForm(request.POST, request.FILES, obras_queryset=obras_qs)
        saved_pk = None
        if form.is_valid():
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
                    recalcular_status_pendencia(p)
                    _notificar_criacao_pendencia(p, request.user)
                    saved_pk = p.pk
                else:
                    transaction.set_rollback(True)
            if saved_pk:
                messages.success(request, "Pendência criada.")
                return redirect("trackhub:pendencia_detalhe", pk=saved_pk)
            messages.error(request, "Corrija os erros nas etapas.")
            formset = EtapaFormSet(request.POST, request.FILES)
        else:
            formset = EtapaFormSet(request.POST, request.FILES)
    else:
        form = PendenciaForm(obras_queryset=obras_qs)
        formset = EtapaFormSet()

    ctx = {
        "form": form,
        "formset": formset,
        "form_title": "Nova pendência",
        "form_subtitle": "Cadastro",
        "responsaveis_por_obra": responsaveis_por_obra,
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
        .select_related("obra", "criado_por")
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

    etapas = list(pendencia.etapas.all())
    comentarios = list(pendencia.comentarios.all())
    anexos_list = list(pendencia.anexos.all())
    pode_editar = _user_can_edit_pendencia(request.user, pendencia)
    etapas_concluidas_count = sum(1 for e in etapas if e.status == "concluida")
    etapas_pendentes_count = sum(1 for e in etapas if e.status == "pendente")
    total_notificacoes = sum(len(list(e.notificacoes.all())) for e in etapas)
    ficha_resp_blocos = []
    if pendencia.obra_id:
        ficha_resp_blocos = _responsaveis_por_obra_payload(
            Obra.objects.filter(pk=pendencia.obra_id)
        )

    ctx = {
        "pendencia": pendencia,
        "etapas": etapas,
        "comentarios": comentarios,
        "anexos_list": anexos_list,
        "num_anexos": len(anexos_list),
        "pode_editar": pode_editar,
        "etapas_concluidas_count": etapas_concluidas_count,
        "etapas_pendentes_count": etapas_pendentes_count,
        "total_notificacoes": total_notificacoes,
        "ficha_resp_blocos": ficha_resp_blocos,
    }
    ctx.update(_nav_tab_context(request.user))
    return render(request, "trackhub/pendencia_detalhe.html", ctx)


@login_required
@require_trackhub
@require_POST
def pendencia_concluir_view(request, pk):
    pendencia = get_object_or_404(_pendencia_queryset_for_user(request.user), pk=pk)
    if not _user_can_edit_pendencia(request.user, pendencia):
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
    _registrar_atividade_pendencia(
        pendencia,
        request.user,
        "Marcou a pendência como concluída",
        AtividadePendencia.TIPO_STATUS,
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
    messages.success(request, "Pendência cancelada.")
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
        EtapaPendencia.objects.select_related("pendencia", "pendencia__obra"),
        pk=pk,
    )
    if not _pendencia_queryset_for_user(request.user).filter(pk=e.pendencia_id).exists():
        if _wants_json_response(request):
            return _json_no_cache({"ok": False, "error": "Acesso negado."}, status=403)
        messages.error(request, "Acesso negado.")
        return redirect("trackhub:fila")
    if not _user_can_edit_pendencia(request.user, e.pendencia):
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
        if not signature_data:
            msg = "Esta etapa requer assinatura para ser concluída"
            if _wants_json_response(request):
                return _json_no_cache({"ok": False, "error": msg}, status=400)
            messages.error(request, msg)
            return redirect("trackhub:pendencia_detalhe", pk=e.pendencia_id)

        AssinaturaEtapa.objects.update_or_create(
            etapa=e,
            defaults={
                "signature_data": signature_data,
                "assinado_por": request.user,
                "assinado_em": timezone.now(),
            },
        )

    titulo_etapa = e.titulo
    e.status = "concluida"
    e.concluida_em = timezone.now()
    e.concluida_por = request.user
    e.save(update_fields=["status", "concluida_em", "concluida_por"])

    pend = Pendencia.objects.get(pk=e.pendencia_id)
    recalcular_status_pendencia(pend)

    _registrar_atividade_pendencia(
        pend,
        request.user,
        f'Concluiu a etapa "{titulo_etapa}"',
        AtividadePendencia.TIPO_ETAPA,
    )

    if _wants_json_response(request):
        return _json_no_cache({"ok": True, "pendencia_id": e.pendencia_id})
    messages.success(request, "Etapa concluída.")
    return redirect("trackhub:pendencia_detalhe", pk=e.pendencia_id)


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
    if not _user_can_edit_pendencia(request.user, p):
        messages.error(request, "Sem permissão para comentar nesta pendência.")
        return redirect("trackhub:pendencia_detalhe", pk=pk)
    texto = (request.POST.get("texto") or "").strip()
    arquivos = [
        f
        for f in request.FILES.getlist("arquivos_comentario")
        if f and getattr(f, "name", None)
    ]
    if not texto and not arquivos:
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
        pendencia.descricao = str(value) if value is not None else ""
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
    elif field == "prazo":
        old_prazo = pendencia.prazo
        if value is None or value == "":
            pendencia.prazo = None
        else:
            if not isinstance(value, str):
                return _json_no_cache({"ok": False, "error": "Prazo inválido."}, status=400)
            try:
                pendencia.prazo = date.fromisoformat(value.strip())
            except ValueError:
                return _json_no_cache(
                    {"ok": False, "error": "Use a data no formato YYYY-MM-DD."},
                    status=400,
                )
        pendencia.save(update_fields=["prazo", "updated_at"])
        novo_p = pendencia.prazo

        def _fmt(d):
            return d.strftime("%d/%m/%Y") if d else ""

        if old_prazo and novo_p:
            txt = f"Alterou prazo de {_fmt(old_prazo)} → {_fmt(novo_p)}"
        elif not old_prazo and novo_p:
            txt = f"Definiu prazo para {_fmt(novo_p)}"
        elif old_prazo and not novo_p:
            txt = "Removeu o prazo"
        else:
            txt = None
        if txt:
            _registrar_atividade_pendencia(
                pendencia, actor, txt, AtividadePendencia.TIPO_PRAZO
            )

    pendencia = _pendencia_prefetched_for_detail(request.user, pk)
    return _json_no_cache(
        {
            "ok": True,
            "field": field,
            "pendencia": _pendencia_detail_payload(pendencia, request),
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
    if not _user_can_edit_pendencia(request.user, pendencia):
        return _json_no_cache(
            {"ok": False, "error": "Sem permissão para comentar nesta pendência."},
            status=403,
        )

    texto = (request.POST.get("texto") or "").strip()
    arquivos = [
        f
        for f in request.FILES.getlist("arquivos_comentario")
        if f and getattr(f, "name", None)
    ]
    if not texto and not arquivos:
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
    if texto:
        prev = texto[:120] + ("…" if len(texto) > 120 else "")
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

    titulo = (request.POST.get("titulo") or "").strip()
    if not titulo:
        msg = "Informe o título da etapa."
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)

    responsavel = None
    rid = (request.POST.get("responsavel_interno") or "").strip()
    if rid:
        try:
            uid = int(rid)
        except ValueError:
            msg = "Responsável inválido."
            if _wants_json_response(request):
                return JsonResponse({"success": False, "error": msg}, status=400)
            messages.error(request, msg)
            return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)
        responsavel = User.objects.filter(pk=uid, is_active=True).first()
        if not responsavel:
            msg = "Responsável não encontrado."
            if _wants_json_response(request):
                return JsonResponse({"success": False, "error": msg}, status=400)
            messages.error(request, msg)
            return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)

    if not responsavel:
        msg = "Informe o responsável interno da etapa."
        if _wants_json_response(request):
            return JsonResponse({"success": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)

    prazo = None
    prazo_raw = (request.POST.get("prazo") or "").strip()
    if prazo_raw:
        try:
            prazo = date.fromisoformat(prazo_raw)
        except ValueError:
            msg = "Prazo inválido."
            if _wants_json_response(request):
                return JsonResponse({"success": False, "error": msg}, status=400)
            messages.error(request, msg)
            return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)

    requer_assinatura = request.POST.get("requer_assinatura") in (
        "1",
        "on",
        "true",
        "True",
    )

    observacao = (request.POST.get("observacao") or "").strip()

    max_ordem = pendencia.etapas.aggregate(m=Max("ordem"))["m"] or 0
    nova_ordem = max_ordem + 1

    with transaction.atomic():
        et = EtapaPendencia.objects.create(
            pendencia=pendencia,
            titulo=titulo,
            ordem=nova_ordem,
            responsavel_interno=responsavel,
            prazo=prazo,
            requer_assinatura=requer_assinatura,
            observacao=observacao,
        )
        _salvar_anexos_etapa_nova(request, et, request.user)
        _notificar_criacao_etapa(et, request.user)
        recalcular_status_pendencia(pendencia)
        _registrar_atividade_pendencia(
            pendencia,
            request.user,
            f"Adicionou etapa: {titulo}",
            AtividadePendencia.TIPO_ETAPA,
        )

    if _wants_json_response(request):
        return JsonResponse({"success": True})
    messages.success(request, "Etapa adicionada.")
    return redirect("trackhub:pendencia_detalhe", pk=pendencia.pk)
