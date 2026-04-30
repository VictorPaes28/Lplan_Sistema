import calendar
import json
import os
import re
from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, IntegerField, Q, Value
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import login_required, require_group
from accounts.groups import GRUPOS
from core.models import Project, ProjectDiaryApprover, ProjectMember, ProjectOwner
from gestao_aprovacao.models import Obra

from .attachment_utils import (
    MAX_ARQUIVOS,
    apply_impedimento_attachments_from_request,
    validate_arquivo_upload,
)
from .forms import (
    CategoriaImpedimentoForm,
    ImpedimentoForm,
    StatusImpedimentoForm,
)
from .models import (
    ArquivoImpedimento,
    AtividadeImpedimento,
    CategoriaImpedimento,
    ComentarioImpedimento,
    Impedimento,
    StatusImpedimento,
)
from .pdf_export import build_impedimentos_list_pdf_bytes


MAX_IMPEDIMENTOS_EXPORT_ROWS = 3000

PRIORIDADE_BADGE_CLASS = {
    Impedimento.PRIORIDADE_BAIXA: "imp-priority-baixa",
    Impedimento.PRIORIDADE_NORMAL: "imp-priority-normal",
    Impedimento.PRIORIDADE_ALTA: "imp-priority-alta",
    Impedimento.PRIORIDADE_CRITICA: "imp-priority-critica",
}

MESES_LABEL = [
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
]

def _ultimo_status_obra(obra):
    """Status com maior ordem (finalização típica da obra)."""
    return StatusImpedimento.objects.filter(obra=obra).order_by("-ordem").first()


def _annotate_subtarefas_counts(queryset, ultimo_status):
    qs = queryset.annotate(subtarefas_count=Count("subtarefas", distinct=True))
    if ultimo_status:
        return qs.annotate(
            subtarefas_concluidas=Count(
                "subtarefas",
                filter=Q(subtarefas__status_id=ultimo_status.id),
                distinct=True,
            )
        )
    return qs.annotate(subtarefas_concluidas=Value(0, output_field=IntegerField()))


def _has_descendant_not_final(impedimento, ultimo_status):
    """Filhos e netos (até 2 níveis) que não estão no status final."""
    if not ultimo_status:
        return False
    uid = ultimo_status.id
    return (
        Impedimento.objects.filter(obra=impedimento.obra)
        .filter(
            Q(parent_id=impedimento.id) | Q(parent__parent_id=impedimento.id)
        )
        .exclude(status_id=uid)
        .exists()
    )


MESES_ABREV = [
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
]


def _user_nome_iniciais(user):
    nome = user.get_full_name().strip() or user.username
    iniciais = "".join(
        [parte[0] for parte in nome.split()[:2] if parte]
    ).upper() or nome[:2].upper()
    return nome, iniciais


def _format_comentario_datetime_pt(dt):
    if dt is None:
        return ""
    local = timezone.localtime(dt)
    mes = MESES_ABREV[local.month]
    return f"{local.day} {mes} {local.year} às {local.strftime('%H:%M')}"


def _serialize_comentario(comentario):
    nome, iniciais = _user_nome_iniciais(comentario.autor)
    return {
        "id": comentario.id,
        "texto": comentario.texto,
        "autor_nome": nome,
        "autor_iniciais": iniciais,
        "criado_em": _format_comentario_datetime_pt(comentario.criado_em),
    }


def _prioridade_label(code):
    return dict(Impedimento.PRIORIDADE_CHOICES).get(code, code or "")


def _format_date_pt_br(d):
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")


def _registrar_atividade_impedimento(impedimento, usuario, descricao, tipo="geral"):
    AtividadeImpedimento.objects.create(
        impedimento=impedimento,
        usuario=usuario,
        tipo=tipo,
        descricao=descricao,
    )


def _serialize_atividade(atividade):
    nome, _ = _user_nome_iniciais(atividade.usuario)
    return {
        "usuario": nome,
        "descricao": atividade.descricao,
        "criado_em": _format_comentario_datetime_pt(atividade.criado_em),
    }


def _absolute_file_url(request, file_field):
    try:
        relative = file_field.url
    except ValueError:
        return ""
    return request.build_absolute_uri(relative)


def _get_projects_for_user(user):
    if user.is_staff or user.is_superuser:
        return Project.objects.filter(is_active=True).order_by("-created_at")

    owner_project_ids = list(
        ProjectOwner.objects.filter(user=user).values_list("project_id", flat=True)
    )
    member_project_ids = list(
        ProjectMember.objects.filter(user=user).values_list("project_id", flat=True)
    )
    approver_project_ids = list(
        ProjectDiaryApprover.objects.filter(user=user, is_active=True).values_list(
            "project_id", flat=True
        )
    )

    linked_ids = sorted(set(owner_project_ids + member_project_ids + approver_project_ids))
    return Project.objects.filter(pk__in=linked_ids, is_active=True).order_by("-created_at")


def _attachments_payload_by_impedimento(obra):
    payload = {}
    qs = Impedimento.objects.filter(obra=obra).prefetch_related("arquivos")
    for imp in qs:
        arqs = []
        for ar in imp.arquivos.all():
            try:
                if ar.arquivo:
                    arqs.append(
                        {
                            "id": ar.pk,
                            "nome": ar.nome_original
                            or os.path.basename(ar.arquivo.name),
                            "url": ar.arquivo.url,
                        }
                    )
            except (ValueError, OSError):
                continue
        payload[str(imp.pk)] = {"arquivos": arqs}
    return payload


def _user_can_access_project(user, project):
    if user.is_staff or user.is_superuser:
        return True
    if ProjectOwner.objects.filter(user=user, project=project).exists():
        return True
    if ProjectDiaryApprover.objects.filter(user=user, project=project, is_active=True).exists():
        return True
    return ProjectMember.objects.filter(user=user, project=project).exists()


def _with_no_cache_headers(response):
    response["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response["Pragma"] = "no-cache"
    return response


def _parse_cat_ids(get_params, obra):
    raw = (get_params.get("cat") or "").strip()
    if not raw:
        return []
    id_list = []
    for part in raw.split(","):
        p = part.strip()
        if p.isdigit():
            id_list.append(int(p))
    if not id_list:
        return []
    valid = set(
        CategoriaImpedimento.objects.filter(obra=obra, pk__in=id_list).values_list(
            "pk", flat=True
        )
    )
    return [pk for pk in id_list if pk in valid]


def _filter_impedimentos_by_cat_ids(qs, cat_ids):
    if not cat_ids:
        return qs
    return qs.filter(categorias__id__in=cat_ids).distinct()


def _list_redirect_url(request, path, view_mode):
    """Preserva querystring (incl. cat) em GET; em POST usar _preserve_cat no body."""
    if request.method == "GET" and request.GET:
        q = request.GET.copy()
        q["view"] = view_mode
        return f"{path}?{q.urlencode()}"
    cat = (request.POST.get("_preserve_cat") or "").strip()
    u = f"{path}?view={view_mode}"
    if cat:
        u += f"&cat={cat}"
    return u


def _impedimentos_table_queryset(obra, get_params):
    q = (get_params.get("q") or "").strip()
    filter_status = (get_params.get("status") or "").strip()
    filter_prioridade = (get_params.get("prioridade") or "").strip()
    filter_responsavel = (get_params.get("responsavel") or "").strip()
    sort_key = (get_params.get("sort") or "criado_em").strip()
    sort_dir = (get_params.get("dir") or "desc").strip().lower()
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "desc"

    table_qs = (
        Impedimento.objects.filter(obra=obra, parent__isnull=True)
        .select_related("status", "criado_por")
        .prefetch_related("responsaveis")
    )
    if q:
        table_qs = table_qs.filter(titulo__icontains=q)
    if filter_status.isdigit():
        table_qs = table_qs.filter(status_id=int(filter_status))
    if filter_prioridade in {
        Impedimento.PRIORIDADE_BAIXA,
        Impedimento.PRIORIDADE_NORMAL,
        Impedimento.PRIORIDADE_ALTA,
        Impedimento.PRIORIDADE_CRITICA,
    }:
        table_qs = table_qs.filter(prioridade=filter_prioridade)
    if filter_responsavel.isdigit():
        table_qs = table_qs.filter(responsaveis__id=int(filter_responsavel))

    cat_ids = _parse_cat_ids(get_params, obra)
    table_qs = _filter_impedimentos_by_cat_ids(table_qs, cat_ids)

    sort_field_map = {
        "titulo": "titulo",
        "status": "status__nome",
        "prioridade": "prioridade",
        "prazo": "prazo",
        "criado_em": "criado_em",
    }
    sort_field = sort_field_map.get(sort_key, "criado_em")
    order_expression = sort_field if sort_dir == "asc" else f"-{sort_field}"
    return table_qs.order_by(order_expression, "-id").distinct()


def _impedimentos_export_metadata_lines(*, total_count, max_rows):
    now_s = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")
    reg = f"Registros: {total_count}"
    if total_count > max_rows:
        reg = f"Registros: {total_count} (exportando até {max_rows})"
    return ["Restrições · Gerado em " + now_s + " · " + reg]


def _prazo_urgencia_label(prazo):
    """Classes do Kanban / payload: vencido, próximo (≤7 dias) ou vazio."""
    if not prazo:
        return ""
    hoje = date.today()
    if prazo < hoje:
        return "vencido"
    delta = (prazo - hoje).days
    if delta <= 7:
        return "proximo"
    return ""


_AVATAR_COLORS = (
    "#2563EB",
    "#7c3aed",
    "#db2777",
    "#ea580c",
    "#16a34a",
    "#0891b2",
)


def _avatar_color_for_nome(nome):
    """Mesma paleta que o JS avatarColor() na lista."""
    s = (nome or "").strip()
    h = 0
    for ch in s:
        h = ord(ch) + ((h << 5) - h)
    return _AVATAR_COLORS[abs(h) % len(_AVATAR_COLORS)]


def _breadcrumb_ancestors_payload(impedimento):
    """
    Ancestrais do topo até o pai direto (exclui o próprio item).
    Até 2 níveis de subtarefa: [avô, pai] ou [pai] ou [].
    """
    if not impedimento.parent_id:
        return []
    par = getattr(impedimento, "parent", None)
    if par is None:
        return []
    out = []
    gp = getattr(par, "parent", None)
    if gp is not None:
        out.append({"id": gp.pk, "titulo": gp.titulo})
    out.append({"id": par.pk, "titulo": par.titulo})
    return out


def _parent_titulo(impedimento):
    if not impedimento.parent_id:
        return None
    p = getattr(impedimento, "parent", None)
    return p.titulo if p else None


def _build_impedimentos_items(impedimentos, comentarios_por_id=None):
    items = []
    comentarios_por_id = comentarios_por_id or {}
    for impedimento in impedimentos:
        responsaveis = []
        for user in impedimento.responsaveis.all():
            nome = user.get_full_name().strip() or user.username
            iniciais = "".join(
                [parte[0] for parte in nome.split()[:2] if parte]
            ).upper() or nome[:2].upper()
            responsaveis.append(
                {
                    "nome": nome,
                    "iniciais": iniciais,
                    "cor": _avatar_color_for_nome(nome),
                }
            )

        categorias = []
        for cat in impedimento.categorias.all():
            categorias.append({"id": cat.pk, "nome": cat.nome, "cor": cat.cor})

        criado_por = getattr(impedimento, "criado_por", None)
        if criado_por:
            criado_por_nome, criado_por_iniciais = _user_nome_iniciais(criado_por)
        else:
            criado_por_nome, criado_por_iniciais = "—", "?"
        criado_em_label = _format_comentario_datetime_pt(impedimento.criado_em)

        rid_list = list(impedimento.responsaveis.values_list("id", flat=True))
        st_count = int(getattr(impedimento, "subtarefas_count", 0) or 0)
        st_ok = int(getattr(impedimento, "subtarefas_concluidas", 0) or 0)
        subtarefas_pct = (
            int(round((st_ok / st_count) * 100)) if st_count > 0 else 0
        )

        prio_slug = str(impedimento.prioridade or "").lower()
        resp_txt_parts = [r["nome"] for r in responsaveis]
        nresp = len(resp_txt_parts)
        if nresp == 0:
            responsaveis_texto = ""
        elif nresp == 1:
            responsaveis_texto = resp_txt_parts[0]
        elif nresp == 2:
            responsaveis_texto = f"{resp_txt_parts[0]}, {resp_txt_parts[1]}"
        else:
            responsaveis_texto = (
                f"{resp_txt_parts[0]}, {resp_txt_parts[1]} e +{nresp - 2}"
            )

        items.append(
            {
                "id": impedimento.id,
                "titulo": impedimento.titulo,
                "status_id": impedimento.status_id,
                "status_nome": impedimento.status.nome,
                "status_cor": impedimento.status.cor,
                "prioridade_value": impedimento.prioridade,
                "prioridade": impedimento.get_prioridade_display(),
                "prioridade_label": impedimento.get_prioridade_display(),
                "prioridade_class": prio_slug,
                "prioridade_badge_class": PRIORIDADE_BADGE_CLASS.get(
                    impedimento.prioridade, "imp-priority-normal"
                ),
                "responsaveis": responsaveis,
                "responsaveis_ids": rid_list,
                "responsaveis_ids_csv": ",".join(str(i) for i in rid_list),
                "responsaveis_texto": responsaveis_texto,
                "categorias": categorias,
                "categorias_ids": list(impedimento.categorias.values_list("id", flat=True)),
                "prazo": impedimento.prazo,
                "prazo_iso": (
                    impedimento.prazo.strftime("%Y-%m-%d")
                    if impedimento.prazo
                    else ""
                ),
                "descricao": impedimento.descricao or "",
                "criado_em": impedimento.criado_em,
                "ultima_conclusao_em": getattr(
                    impedimento, "ultima_conclusao_em", None
                ),
                "criado_em_label": criado_em_label,
                "criado_por_nome": criado_por_nome,
                "criado_por_iniciais": criado_por_iniciais,
                "comentarios_count": int(
                    comentarios_por_id.get(impedimento.id, 0)
                ),
                "prazo_urgencia": _prazo_urgencia_label(impedimento.prazo),
                "parent_id": impedimento.parent_id,
                "parent_titulo": _parent_titulo(impedimento),
                "breadcrumb_ancestors": _breadcrumb_ancestors_payload(impedimento),
                "subtarefas_count": st_count,
                "subtarefas_concluidas": st_ok,
                "subtarefas_pct": subtarefas_pct,
            }
        )
    return items


def _project_member_user_ids(project):
    return set(
        ProjectMember.objects.filter(project=project, user__is_active=True).values_list(
            "user_id", flat=True
        )
    )


def _row_payload_impedimento(impedimento_id, obra):
    ultimo = _ultimo_status_obra(obra)
    impedimento = (
        _annotate_subtarefas_counts(
            Impedimento.objects.filter(pk=impedimento_id, obra=obra), ultimo
        )
        .select_related("status", "criado_por", "parent", "parent__parent")
        .prefetch_related("responsaveis", "categorias")
        .first()
    )
    if not impedimento:
        return None
    cnt = ComentarioImpedimento.objects.filter(impedimento_id=impedimento_id).count()
    return _build_impedimentos_items(
        [impedimento], comentarios_por_id={impedimento_id: cnt}
    )[0]


ALLOWED_UPDATE_FIELDS = frozenset(
    {
        "titulo",
        "descricao",
        "status",
        "prioridade",
        "responsaveis",
        "prazo",
        "categorias",
    }
)


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
def home(request):
    return redirect("impedimentos:select_obra")


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
def select_obra(request):
    projects = _get_projects_for_user(request.user)

    if request.method == "POST":
        project_id = request.POST.get("project_id")
        if project_id:
            try:
                project = Project.objects.get(pk=project_id, is_active=True)
            except (Project.DoesNotExist, ValueError, TypeError):
                response = render(
                    request,
                    "impedimentos/select_obra.html",
                    {
                        "projects": projects,
                        "selected_project_id": request.session.get("selected_project_id"),
                        "error": "Obra não encontrada ou inativa.",
                    },
                )
                return _with_no_cache_headers(response)

            if not _user_can_access_project(request.user, project):
                response = render(
                    request,
                    "impedimentos/select_obra.html",
                    {
                        "projects": projects,
                        "selected_project_id": request.session.get("selected_project_id"),
                        "error": "Você não está vinculado a esta obra.",
                    },
                )
                return _with_no_cache_headers(response)

            return redirect("impedimentos:list_impedimentos", obra_id=project.id)

    response = render(
        request,
        "impedimentos/select_obra.html",
        {
            "projects": projects,
            "selected_project_id": request.session.get("selected_project_id"),
        },
    )
    return _with_no_cache_headers(response)


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
def list_impedimentos(request, obra_id):
    project = get_object_or_404(Project, pk=obra_id, is_active=True)
    if not _user_can_access_project(request.user, project):
        messages.error(request, "Você não está vinculado a esta obra.")
        return redirect("impedimentos:select_obra")

    obra = get_object_or_404(Obra, project=project)
    cat_ids = _parse_cat_ids(request.GET, obra)
    cat_param = ",".join(str(i) for i in cat_ids) if cat_ids else ""
    status_list = list(StatusImpedimento.objects.filter(obra=obra).order_by("ordem", "nome"))
    view_mode = request.GET.get("view", "lista").lower()
    if view_mode not in {"lista", "quadro", "calendario", "tabela"}:
        view_mode = "lista"

    if view_mode == "tabela" and not (request.user.is_staff or request.user.is_superuser):
        return redirect(f"{request.path}?view=lista")

    show_modal = False
    edit_item_id = None
    query_view = request.GET.get("view", "lista")

    if request.method == "POST":
        action = (request.POST.get("action") or "create").strip().lower()

        if action == "delete":
            impedimento_id = request.POST.get("impedimento_id")
            try:
                impedimento_delete = Impedimento.objects.get(pk=impedimento_id, obra=obra)
                impedimento_delete.delete()
                messages.success(request, "Restrição excluída com sucesso.")
            except (Impedimento.DoesNotExist, ValueError, TypeError):
                messages.error(request, "Não foi possível excluir a restrição.")
            cat_post = (request.POST.get("cat") or "").strip()
            del_url = f"{request.path}?view={query_view}"
            if cat_post:
                del_url += f"&cat={cat_post}"
            return redirect(del_url)

        if action == "update":
            impedimento_id = request.POST.get("impedimento_id")
            try:
                impedimento_edit = Impedimento.objects.get(pk=impedimento_id, obra=obra)
            except (Impedimento.DoesNotExist, ValueError, TypeError):
                impedimento_edit = None

            if not impedimento_edit:
                messages.error(request, "Restrição não encontrada para edição.")
                form = ImpedimentoForm(obra=obra, project=project)
            else:
                form = ImpedimentoForm(
                    request.POST,
                    request.FILES,
                    obra=obra,
                    project=project,
                    instance=impedimento_edit,
                )
                if form.is_valid():
                    try:
                        with transaction.atomic():
                            atualizado = form.save(commit=False)
                            atualizado.obra = obra
                            atualizado.save()
                            form.save_m2m()
                            apply_impedimento_attachments_from_request(
                                request, atualizado
                            )
                    except ValueError as exc:
                        messages.error(request, str(exc))
                        show_modal = True
                        edit_item_id = impedimento_edit.id
                    else:
                        messages.success(
                            request, "Restrição atualizada com sucesso."
                        )
                        return redirect(
                            _list_redirect_url(request, request.path, query_view)
                        )
                else:
                    show_modal = True
                    edit_item_id = impedimento_edit.id
        else:
            form = ImpedimentoForm(
                request.POST, request.FILES, obra=obra, project=project
            )
            if form.is_valid():
                status_padrao = (
                    StatusImpedimento.objects.filter(obra=obra, is_default=True)
                    .order_by("ordem", "nome")
                    .first()
                    or StatusImpedimento.objects.filter(obra=obra)
                    .order_by("ordem", "nome")
                    .first()
                )
                if not status_padrao:
                    messages.error(
                        request,
                        "Não há status configurado para esta obra. Cadastre um status antes de criar restrições.",
                    )
                    show_modal = True
                else:
                    parent_ref = None
                    parent_raw = (request.POST.get("parent_id") or "").strip()
                    try:
                        with transaction.atomic():
                            novo_impedimento = form.save(commit=False)
                            novo_impedimento.obra = obra
                            escolhido = status_padrao
                            rid = (
                                request.POST.get("initial_status_id") or ""
                            ).strip()
                            if rid.isdigit():
                                st_req = StatusImpedimento.objects.filter(
                                    pk=int(rid), obra=obra
                                ).first()
                                if st_req:
                                    escolhido = st_req
                            novo_impedimento.status = escolhido
                            novo_impedimento.criado_por = request.user
                            if parent_raw.isdigit():
                                parent_ref = get_object_or_404(
                                    Impedimento.objects.select_related(
                                        "parent__parent"
                                    ),
                                    pk=int(parent_raw),
                                    obra=obra,
                                )
                                if (
                                    parent_ref.parent_id is not None
                                    and parent_ref.parent.parent_id is not None
                                ):
                                    raise ValueError(
                                        "Máximo 2 níveis de subtarefas."
                                    )
                                novo_impedimento.parent = parent_ref
                                novo_impedimento.obra = parent_ref.obra
                            novo_impedimento.full_clean()
                            novo_impedimento.save()
                            form.save_m2m()
                            apply_impedimento_attachments_from_request(
                                request, novo_impedimento
                            )
                    except ValidationError as exc:
                        messages.error(
                            request,
                            next(iter(exc.messages), str(exc)),
                        )
                        show_modal = True
                    except ValueError as exc:
                        messages.error(request, str(exc))
                        show_modal = True
                    else:
                        messages.success(request, "Restrição criada com sucesso.")
                        redir = _list_redirect_url(request, request.path, query_view)
                        if parent_ref is not None:
                            sep = "&" if "?" in redir else "?"
                            redir = f"{redir}{sep}open_detail={parent_ref.pk}"
                        return redirect(redir)
            else:
                show_modal = True
    else:
        form = ImpedimentoForm(obra=obra, project=project)

    ultimo_status_obra = _ultimo_status_obra(obra)
    impedimentos_qs = (
        Impedimento.objects.filter(obra=obra, parent__isnull=True)
        .select_related("status", "criado_por")
        .prefetch_related("responsaveis", "categorias")
        .order_by("-criado_em")
    )
    impedimentos_qs = _annotate_subtarefas_counts(impedimentos_qs, ultimo_status_obra)
    impedimentos_qs = _filter_impedimentos_by_cat_ids(impedimentos_qs, cat_ids)
    impedimento_ids = list(impedimentos_qs.values_list("pk", flat=True))
    comentarios_count_by_id = {}
    if impedimento_ids:
        comentarios_count_by_id = {
            row["impedimento_id"]: row["count"]
            for row in ComentarioImpedimento.objects.filter(
                impedimento_id__in=impedimento_ids
            )
            .values("impedimento_id")
            .annotate(count=Count("id"))
        }
    impedimentos_items = _build_impedimentos_items(
        impedimentos_qs, comentarios_por_id=comentarios_count_by_id
    )
    impedimentos_por_status = {}
    for item in impedimentos_items:
        impedimentos_por_status.setdefault(item["status_id"], []).append(item)

    kanban_columns = []
    for status in status_list:
        col_items = impedimentos_por_status.get(status.id, [])
        kanban_columns.append(
            {
                "id": status.id,
                "nome": status.nome,
                "cor": status.cor,
                "count": len(col_items),
                "items": col_items,
            }
        )

    q = (request.GET.get("q") or "").strip()
    filter_status = (request.GET.get("status") or "").strip()
    filter_prioridade = (request.GET.get("prioridade") or "").strip()
    filter_responsavel = (request.GET.get("responsavel") or "").strip()
    sort_key = (request.GET.get("sort") or "criado_em").strip()
    sort_dir = (request.GET.get("dir") or "desc").strip().lower()
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "desc"

    table_qs = _impedimentos_table_queryset(obra, request.GET)
    table_qs = _annotate_subtarefas_counts(table_qs, ultimo_status_obra)

    paginator = Paginator(table_qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_ids = [obj.pk for obj in page_obj.object_list]
    table_comentarios_by_id = {}
    if page_ids:
        table_comentarios_by_id = {
            row["impedimento_id"]: row["count"]
            for row in ComentarioImpedimento.objects.filter(
                impedimento_id__in=page_ids
            )
            .values("impedimento_id")
            .annotate(count=Count("id"))
        }
    table_items = _build_impedimentos_items(
        page_obj.object_list, comentarios_por_id=table_comentarios_by_id
    )

    responsaveis_options = (
        ProjectMember.objects.filter(project=project, user__is_active=True)
        .select_related("user")
        .order_by("user__first_name", "user__last_name", "user__username")
    )
    responsaveis_choices = []
    for pm in responsaveis_options:
        nome = pm.user.get_full_name().strip() or pm.user.username
        iniciais = "".join(
            [parte[0] for parte in nome.split()[:2] if parte]
        ).upper() or nome[:2].upper()
        responsaveis_choices.append(
            {"id": pm.user_id, "nome": nome, "iniciais": iniciais}
        )

    categorias_obra = list(
        CategoriaImpedimento.objects.filter(obra=obra).order_by("nome")
    )
    categorias_choices = [
        {"id": c.pk, "nome": c.nome, "cor": c.cor} for c in categorias_obra
    ]

    today = date.today()
    try:
        current_month = int(request.GET.get("month", today.month))
    except (TypeError, ValueError):
        current_month = today.month
    try:
        current_year = int(request.GET.get("year", today.year))
    except (TypeError, ValueError):
        current_year = today.year

    if current_month < 1 or current_month > 12:
        current_month = today.month
    if current_year < 1900 or current_year > 2100:
        current_year = today.year

    first_day = date(current_year, current_month, 1)
    month_days_count = calendar.monthrange(current_year, current_month)[1]
    last_day = date(current_year, current_month, month_days_count)
    grid_start = first_day - timedelta(days=first_day.weekday())
    grid_end = last_day + timedelta(days=(6 - last_day.weekday()))

    prev_month = 12 if current_month == 1 else current_month - 1
    prev_year = current_year - 1 if current_month == 1 else current_year
    next_month = 1 if current_month == 12 else current_month + 1
    next_year = current_year + 1 if current_month == 12 else current_year

    calendar_qs = (
        Impedimento.objects.filter(
            obra=obra,
            parent__isnull=True,
            prazo__isnull=False,
            prazo__year=current_year,
            prazo__month=current_month,
        )
        .select_related("status", "criado_por")
        .prefetch_related("responsaveis", "categorias")
        .order_by("prazo", "-criado_em")
    )
    calendar_qs = _filter_impedimentos_by_cat_ids(calendar_qs, cat_ids)
    calendar_items_raw = _build_impedimentos_items(calendar_qs)
    calendar_items_by_day = {}
    for item in calendar_items_raw:
        if not item.get("prazo"):
            continue
        iso_key = item["prazo"].isoformat()
        calendar_items_by_day.setdefault(iso_key, []).append(item)

    calendar_days = []
    cursor = grid_start
    while cursor <= grid_end:
        iso = cursor.isoformat()
        calendar_days.append(
            {
                "date": cursor,
                "iso": iso,
                "day": cursor.day,
                "is_current_month": cursor.month == current_month,
                "items": calendar_items_by_day.get(iso, []),
            }
        )
        cursor += timedelta(days=1)

    calendar_meta = {
        "month": current_month,
        "year": current_year,
        "label": f"{MESES_LABEL[current_month]} {current_year}",
        "prev_month": prev_month,
        "prev_year": prev_year,
        "next_month": next_month,
        "next_year": next_year,
    }

    def _tab_q(view_name, **extra):
        p = {"view": view_name, **extra}
        if cat_param:
            p["cat"] = cat_param
        return urlencode(p)

    tab_q_lista = _tab_q("lista")
    tab_q_quadro = _tab_q("quadro")
    tab_q_calendario = _tab_q("calendario", month=current_month, year=current_year)
    tab_q_tabela = _tab_q("tabela")
    cal_prev_q = _tab_q("calendario", month=prev_month, year=prev_year)
    cal_next_q = _tab_q("calendario", month=next_month, year=next_year)

    if view_mode in {"tabela"}:
        pass

    lista_finalizado_status_id = (
        ultimo_status_obra.id if ultimo_status_obra else None
    )

    context = {
        "title": "Restrições",
        "obra": obra,
        "project": project,
        "impedimentos": impedimentos_items,
        "kanban_columns": kanban_columns,
        "status_list": status_list,
        "form": form,
        "active_view": view_mode,
        "show_modal": show_modal,
        "calendar_meta": calendar_meta,
        "calendar_days": calendar_days,
        "table_items": table_items,
        "table_page_obj": page_obj,
        "table_filters": {
            "q": q,
            "status": filter_status,
            "prioridade": filter_prioridade,
            "responsavel": filter_responsavel,
        },
        "table_sort": {"key": sort_key, "dir": sort_dir},
        "responsaveis_choices": responsaveis_choices,
        "is_admin_export": request.user.is_staff or request.user.is_superuser,
        "edit_item_id": edit_item_id,
        "prioridade_choices": Impedimento.PRIORIDADE_CHOICES,
        "attachments_by_impedimento_id": _attachments_payload_by_impedimento(obra),
        "categorias_obra": categorias_obra,
        "categorias_choices": categorias_choices,
        "selected_cat_ids": cat_ids,
        "cat_param": cat_param,
        "table_cat_suffix": (f"&cat={cat_param}" if cat_param else ""),
        "tab_q_lista": tab_q_lista,
        "tab_q_quadro": tab_q_quadro,
        "tab_q_calendario": tab_q_calendario,
        "tab_q_tabela": tab_q_tabela,
        "cal_prev_q": cal_prev_q,
        "cal_next_q": cal_next_q,
        "comentarios_count_by_id": comentarios_count_by_id,
        "lista_finalizado_status_id": lista_finalizado_status_id,
        "status_list_json": [
            {"id": s.id, "nome": s.nome, "cor": s.cor} for s in status_list
        ],
    }
    response = render(request, "impedimentos/list_impedimentos.html", context)
    return _with_no_cache_headers(response)


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
@require_POST
def criar_categoria_ajax(request, obra_id):
    project = get_object_or_404(Project, pk=obra_id, is_active=True)
    if not _user_can_access_project(request.user, project):
        return JsonResponse({"ok": False, "error": "Sem acesso a esta obra."}, status=403)
    obra = get_object_or_404(Obra, project=project)
    form = CategoriaImpedimentoForm(request.POST, obra=obra)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.obra = obra
        obj.criado_por = request.user
        obj.save()
        return JsonResponse({"ok": True, "id": obj.pk, "nome": obj.nome, "cor": obj.cor})
    errs = form.errors.get("__all__") or next(iter(form.errors.values()), None)
    msg = errs[0] if errs else "Dados inválidos."
    return JsonResponse({"ok": False, "error": str(msg)}, status=400)


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
@require_POST
def remover_categoria_ajax(request, obra_id, categoria_id):
    project = get_object_or_404(Project, pk=obra_id, is_active=True)
    if not _user_can_access_project(request.user, project):
        return JsonResponse({"ok": False, "erro": "Sem acesso."}, status=403)
    if not request.user.is_staff and not request.user.is_superuser:
        return JsonResponse(
            {
                "ok": False,
                "erro": "Apenas administradores podem remover categorias.",
            },
            status=403,
        )
    obra = get_object_or_404(Obra, project=project)
    categoria = get_object_or_404(CategoriaImpedimento, pk=categoria_id, obra=obra)
    impedimentos_so_nessa = categoria.impedimentos.annotate(
        n_cats=Count("categorias")
    ).filter(n_cats=1)
    if impedimentos_so_nessa.exists():
        return JsonResponse(
            {
                "ok": False,
                "erro": "Existem restrições vinculadas apenas a esta categoria. Remova-as ou mova-as para outra categoria antes.",
            }
        )
    categoria.delete()
    return JsonResponse({"ok": True})


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
def export_impedimentos_pdf(request, obra_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden("Apenas administradores podem exportar o PDF.")

    project = get_object_or_404(Project, pk=obra_id, is_active=True)
    if not _user_can_access_project(request.user, project):
        return HttpResponseForbidden("Sem acesso a esta obra.")

    obra = get_object_or_404(Obra, project=project)

    table_qs = _impedimentos_table_queryset(obra, request.GET)
    table_qs = _annotate_subtarefas_counts(table_qs, _ultimo_status_obra(obra))
    total_count = table_qs.count()
    slice_qs = list(table_qs[:MAX_IMPEDIMENTOS_EXPORT_ROWS])
    items = _build_impedimentos_items(slice_qs)

    metadata_lines = _impedimentos_export_metadata_lines(
        total_count=total_count,
        max_rows=MAX_IMPEDIMENTOS_EXPORT_ROWS,
    )
    ultimo_status = _ultimo_status_obra(obra)

    pdf_bytes = build_impedimentos_list_pdf_bytes(
        obra_nome=obra.nome or "",
        obra_sigla=(obra.sigla or "").strip(),
        project_code=(project.code or "").strip(),
        metadata_lines=metadata_lines,
        items=items,
        total_count=total_count,
        exported_count=len(items),
        max_rows=MAX_IMPEDIMENTOS_EXPORT_ROWS,
        lista_finalizado_status_id=ultimo_status.id if ultimo_status else None,
    )

    safe_code = re.sub(r"[^\w\-]+", "_", (project.code or str(project.id)))[:48]
    fname = f"impeditivos_{safe_code}_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{fname}"'
    response["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response["Pragma"] = "no-cache"
    return response


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
@require_POST
def update_status_ajax(request, obra_id):
    project = get_object_or_404(Project, pk=obra_id, is_active=True)
    if not _user_can_access_project(request.user, project):
        return JsonResponse(
            {"ok": False, "error": "Você não tem acesso a esta obra."}, status=403
        )

    obra = get_object_or_404(Obra, project=project)
    impedimento_id = request.POST.get("impedimento_id")
    status_id = request.POST.get("status_id")

    if not impedimento_id or not status_id:
        return JsonResponse({"ok": False, "error": "Parâmetros inválidos."}, status=400)

    try:
        impedimento = Impedimento.objects.get(pk=impedimento_id, obra=obra)
        novo_status = StatusImpedimento.objects.get(pk=status_id, obra=obra)
    except (Impedimento.DoesNotExist, StatusImpedimento.DoesNotExist, ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Item ou status inválido."}, status=404)

    ultimo = _ultimo_status_obra(obra)
    if ultimo and novo_status.id == ultimo.id:
        if _has_descendant_not_final(impedimento, ultimo):
            return JsonResponse(
                {
                    "ok": False,
                    "error": "Existem subtarefas não finalizadas. Conclua todas antes de finalizar esta restrição.",
                },
                status=400,
            )

    impedimento.status = novo_status
    impedimento.save(update_fields=["status", "atualizado_em"])
    return JsonResponse({"ok": True, "status_id": novo_status.id})


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
@require_http_methods(["GET", "POST"])
def comentarios_impedimento_ajax(request, obra_id, impedimento_id):
    project = get_object_or_404(Project, pk=obra_id, is_active=True)
    if not _user_can_access_project(request.user, project):
        return JsonResponse(
            {"ok": False, "error": "Você não tem acesso a esta obra."}, status=403
        )

    obra = get_object_or_404(Obra, project=project)
    impedimento = Impedimento.objects.filter(pk=impedimento_id, obra=obra).first()
    if not impedimento:
        return JsonResponse(
            {"ok": False, "error": "Restrição não encontrada."}, status=404
        )

    if request.method == "GET":
        comentarios = (
            ComentarioImpedimento.objects.filter(impedimento=impedimento)
            .select_related("autor")
            .order_by("criado_em")
        )
        return JsonResponse(
            {
                "ok": True,
                "comentarios": [_serialize_comentario(c) for c in comentarios],
            }
        )

    texto = (request.POST.get("texto") or "").strip()
    if not texto:
        return JsonResponse(
            {"ok": False, "error": "O comentário não pode estar vazio."}, status=400
        )

    comentario = ComentarioImpedimento.objects.create(
        impedimento=impedimento,
        autor=request.user,
        texto=texto,
    )
    comentario = ComentarioImpedimento.objects.select_related("autor").get(pk=comentario.pk)
    return JsonResponse({"ok": True, "comentario": _serialize_comentario(comentario)})


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
@require_http_methods(["GET"])
def impedimento_detail_ajax(request, obra_id, impedimento_id):
    project = get_object_or_404(Project, pk=obra_id, is_active=True)
    if not _user_can_access_project(request.user, project):
        return JsonResponse(
            {"ok": False, "error": "Sem acesso a esta obra."}, status=403
        )
    obra = get_object_or_404(Obra, project=project)
    ultimo = _ultimo_status_obra(obra)
    impedimento = (
        _annotate_subtarefas_counts(
            Impedimento.objects.filter(pk=impedimento_id, obra=obra), ultimo
        )
        .select_related("status", "criado_por", "parent", "parent__parent")
        .prefetch_related("responsaveis", "categorias", "arquivos")
        .first()
    )
    if not impedimento:
        return JsonResponse(
            {"ok": False, "error": "Restrição não encontrada."}, status=404
        )

    cnt = ComentarioImpedimento.objects.filter(impedimento=impedimento).count()
    item = _build_impedimentos_items(
        [impedimento], comentarios_por_id={impedimento.pk: cnt}
    )[0]

    arquivos = []
    for ar in impedimento.arquivos.all():
        try:
            if ar.arquivo:
                arquivos.append(
                    {
                        "id": ar.pk,
                        "nome": ar.nome_original or os.path.basename(ar.arquivo.name),
                        "url": _absolute_file_url(request, ar.arquivo),
                    }
                )
        except (ValueError, OSError):
            continue

    comentarios_qs = (
        ComentarioImpedimento.objects.filter(impedimento=impedimento)
        .select_related("autor")
        .order_by("criado_em")
    )
    item["arquivos"] = arquivos
    item["comentarios"] = [_serialize_comentario(c) for c in comentarios_qs]

    response = JsonResponse({"ok": True, "item": item})
    response["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
@require_http_methods(["GET"])
def impedimento_atividades_ajax(request, obra_id, impedimento_id):
    project = get_object_or_404(Project, pk=obra_id, is_active=True)
    if not _user_can_access_project(request.user, project):
        return JsonResponse(
            {"ok": False, "error": "Sem acesso a esta obra."}, status=403
        )
    obra = get_object_or_404(Obra, project=project)
    impedimento = Impedimento.objects.filter(pk=impedimento_id, obra=obra).first()
    if not impedimento:
        return JsonResponse(
            {"ok": False, "error": "Restrição não encontrada."}, status=404
        )

    qs = (
        AtividadeImpedimento.objects.filter(impedimento=impedimento)
        .select_related("usuario")
        .order_by("-criado_em")
    )
    out = JsonResponse(
        {
            "ok": True,
            "atividades": [_serialize_atividade(a) for a in qs],
        }
    )
    out["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return out


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
@require_http_methods(["GET"])
def impedimento_subtarefas_ajax(request, obra_id, impedimento_id):
    project = get_object_or_404(Project, pk=obra_id, is_active=True)
    if not _user_can_access_project(request.user, project):
        return JsonResponse(
            {"ok": False, "error": "Sem acesso a esta obra."}, status=403
        )
    obra = get_object_or_404(Obra, project=project)
    parent_imp = get_object_or_404(
        Impedimento.objects.select_related("parent"),
        pk=impedimento_id,
        obra=obra,
    )
    ultimo = _ultimo_status_obra(obra)
    children = (
        Impedimento.objects.filter(parent_id=impedimento_id, obra=obra)
        .select_related("status", "criado_por", "parent", "parent__parent")
        .prefetch_related("responsaveis", "categorias")
        .order_by("-criado_em")
    )
    children = _annotate_subtarefas_counts(children, ultimo)
    child_ids = list(children.values_list("pk", flat=True))
    comentarios_by_id = {}
    if child_ids:
        comentarios_by_id = {
            row["impedimento_id"]: row["count"]
            for row in ComentarioImpedimento.objects.filter(
                impedimento_id__in=child_ids
            )
            .values("impedimento_id")
            .annotate(count=Count("id"))
        }
    items = _build_impedimentos_items(children, comentarios_por_id=comentarios_by_id)
    list_level = 1 if parent_imp.parent_id is None else 2
    for it in items:
        it["list_subtask_level"] = list_level
    response = JsonResponse({"ok": True, "subtarefas": items})
    response["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
@require_POST
@transaction.atomic
def impedimento_update_field(request, obra_id, impedimento_id):
    project = get_object_or_404(Project, pk=obra_id, is_active=True)
    if not _user_can_access_project(request.user, project):
        return JsonResponse(
            {"ok": False, "error": "Sem acesso a esta obra."}, status=403
        )
    obra = get_object_or_404(Obra, project=project)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "JSON inválido."}, status=400)

    field = (payload.get("field") or "").strip()
    value = payload.get("value")

    if field not in ALLOWED_UPDATE_FIELDS:
        return JsonResponse({"ok": False, "error": "Campo não suportado."}, status=400)

    impedimento = Impedimento.objects.filter(pk=impedimento_id, obra=obra).first()
    if not impedimento:
        return JsonResponse(
            {"ok": False, "error": "Restrição não encontrada."}, status=404
        )

    member_ids = _project_member_user_ids(project)
    old_status_id = impedimento.status_id
    actor = request.user

    try:
        if field == "titulo":
            t = (value if isinstance(value, str) else "").strip()
            if not t:
                return JsonResponse(
                    {"ok": False, "error": "O título não pode ficar vazio."},
                    status=400,
                )
            impedimento.titulo = t
            impedimento.save(update_fields=["titulo", "atualizado_em"])
            _registrar_atividade_impedimento(
                impedimento, actor, "Alterou título", "titulo"
            )

        elif field == "descricao":
            if value is None:
                impedimento.descricao = ""
            else:
                impedimento.descricao = str(value)
            impedimento.save(update_fields=["descricao", "atualizado_em"])
            _registrar_atividade_impedimento(
                impedimento, actor, "Alterou descrição", "descricao"
            )

        elif field == "status":
            try:
                sid = int(value)
            except (TypeError, ValueError):
                return JsonResponse(
                    {"ok": False, "error": "Status inválido."}, status=400
                )
            status_anterior = impedimento.status
            novo = StatusImpedimento.objects.filter(pk=sid, obra=obra).first()
            if not novo:
                return JsonResponse(
                    {"ok": False, "error": "Status não encontrado nesta obra."},
                    status=400,
                )
            ultimo = _ultimo_status_obra(obra)
            if ultimo and novo.id == ultimo.id:
                if _has_descendant_not_final(impedimento, ultimo):
                    return JsonResponse(
                        {
                            "ok": False,
                            "error": "Existem subtarefas não finalizadas. Conclua todas antes de finalizar esta restrição.",
                        },
                        status=400,
                    )
            impedimento.status = novo
            impedimento.save(update_fields=["status", "atualizado_em"])
            _registrar_atividade_impedimento(
                impedimento,
                actor,
                f'Alterou status de "{status_anterior.nome}" → "{novo.nome}"',
                "status",
            )

        elif field == "prioridade":
            pv = value if isinstance(value, str) else ""
            valid_codes = {c[0] for c in Impedimento.PRIORIDADE_CHOICES}
            if pv not in valid_codes:
                return JsonResponse(
                    {"ok": False, "error": "Prioridade inválida."}, status=400
                )
            label_anterior = _prioridade_label(impedimento.prioridade)
            impedimento.prioridade = pv
            impedimento.save(update_fields=["prioridade", "atualizado_em"])
            label_nova = _prioridade_label(impedimento.prioridade)
            _registrar_atividade_impedimento(
                impedimento,
                actor,
                f'Alterou prioridade de "{label_anterior}" → "{label_nova}"',
                "prioridade",
            )

        elif field == "responsaveis":
            raw_ids = value if isinstance(value, list) else []
            uid_list = []
            for x in raw_ids:
                try:
                    uid_list.append(int(x))
                except (TypeError, ValueError):
                    continue
            allowed = [uid for uid in uid_list if uid in member_ids]
            old_ids = set(impedimento.responsaveis.values_list("id", flat=True))
            impedimento.responsaveis.set(allowed)
            new_ids = set(allowed)
            User = get_user_model()
            for uid in sorted(new_ids - old_ids):
                u = User.objects.filter(pk=uid).first()
                if u:
                    nome_u = u.get_full_name().strip() or u.username
                    _registrar_atividade_impedimento(
                        impedimento,
                        actor,
                        f"Adicionou responsável {nome_u}",
                        "responsaveis",
                    )
            for uid in sorted(old_ids - new_ids):
                u = User.objects.filter(pk=uid).first()
                if u:
                    nome_u = u.get_full_name().strip() or u.username
                    _registrar_atividade_impedimento(
                        impedimento,
                        actor,
                        f"Removeu responsável {nome_u}",
                        "responsaveis",
                    )

        elif field == "prazo":
            old_prazo = impedimento.prazo
            if value is None or value == "":
                impedimento.prazo = None
            else:
                if not isinstance(value, str):
                    return JsonResponse(
                        {"ok": False, "error": "Prazo inválido."}, status=400
                    )
                try:
                    impedimento.prazo = date.fromisoformat(value.strip())
                except ValueError:
                    return JsonResponse(
                        {"ok": False, "error": "Use a data no formato YYYY-MM-DD."},
                        status=400,
                    )
            impedimento.save(update_fields=["prazo", "atualizado_em"])
            novo_prazo = impedimento.prazo
            anterior_fmt = _format_date_pt_br(old_prazo)
            novo_fmt = _format_date_pt_br(novo_prazo)
            if old_prazo and novo_prazo:
                txt = f"Alterou prazo de {anterior_fmt} → {novo_fmt}"
            elif not old_prazo and novo_prazo:
                txt = f"Definiu prazo para {novo_fmt}"
            elif old_prazo and not novo_prazo:
                txt = "Removeu o prazo"
            else:
                txt = None
            if txt:
                _registrar_atividade_impedimento(impedimento, actor, txt, "prazo")

        elif field == "categorias":
            raw_ids = value if isinstance(value, list) else []
            parsed = []
            for x in raw_ids:
                try:
                    parsed.append(int(x))
                except (TypeError, ValueError):
                    continue
            uniq = list(dict.fromkeys(parsed))
            valid_ids = list(
                CategoriaImpedimento.objects.filter(obra=obra, pk__in=uniq).values_list(
                    "pk", flat=True
                )
            )
            if len(valid_ids) != len(uniq):
                return JsonResponse(
                    {
                        "ok": False,
                        "error": "Uma ou mais categorias são inválidas para esta obra.",
                    },
                    status=400,
                )
            if not valid_ids:
                return JsonResponse(
                    {
                        "ok": False,
                        "error": "Selecione pelo menos uma categoria.",
                    },
                    status=400,
                )
            old_cat_ids = set(impedimento.categorias.values_list("id", flat=True))
            impedimento.categorias.set(valid_ids)
            new_cat_ids = set(valid_ids)
            for cid in sorted(new_cat_ids - old_cat_ids):
                cat = CategoriaImpedimento.objects.filter(pk=cid, obra=obra).first()
                if cat:
                    _registrar_atividade_impedimento(
                        impedimento,
                        actor,
                        f'Adicionou categoria "{cat.nome}"',
                        "categorias",
                    )
            for cid in sorted(old_cat_ids - new_cat_ids):
                cat = CategoriaImpedimento.objects.filter(pk=cid, obra=obra).first()
                if cat:
                    _registrar_atividade_impedimento(
                        impedimento,
                        actor,
                        f'Removeu categoria "{cat.nome}"',
                        "categorias",
                    )

    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    row = _row_payload_impedimento(impedimento.pk, obra)
    resp = {
        "ok": True,
        "field": field,
        "row": row,
        "status_changed": field == "status" and old_status_id != impedimento.status_id,
        "old_status_id": old_status_id,
        "new_status_id": impedimento.status_id,
    }
    out = JsonResponse(resp)
    out["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return out


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
@require_POST
def impedimento_arquivo_upload(request, obra_id, impedimento_id):
    project = get_object_or_404(Project, pk=obra_id, is_active=True)
    if not _user_can_access_project(request.user, project):
        return JsonResponse(
            {"ok": False, "error": "Sem acesso a esta obra."}, status=403
        )
    obra = get_object_or_404(Obra, project=project)
    impedimento = Impedimento.objects.filter(pk=impedimento_id, obra=obra).first()
    if not impedimento:
        return JsonResponse(
            {"ok": False, "error": "Restrição não encontrada."}, status=404
        )

    f = request.FILES.get("arquivo")
    if not f:
        return JsonResponse({"ok": False, "error": "Nenhum arquivo enviado."}, status=400)

    current = ArquivoImpedimento.objects.filter(impedimento=impedimento).count()
    if current >= MAX_ARQUIVOS:
        return JsonResponse(
            {"ok": False, "error": f"No máximo {MAX_ARQUIVOS} arquivos por restrição."},
            status=400,
        )

    try:
        validate_arquivo_upload(f)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    nome = os.path.basename(getattr(f, "name", "") or "")
    ar = ArquivoImpedimento.objects.create(
        impedimento=impedimento,
        arquivo=f,
        nome_original=nome[:255],
    )
    _registrar_atividade_impedimento(
        impedimento,
        request.user,
        f'Adicionou arquivo "{ar.nome_original or nome}"',
        "arquivo",
    )
    url = _absolute_file_url(request, ar.arquivo)

    return JsonResponse(
        {
            "ok": True,
            "arquivo": {"id": ar.pk, "nome": ar.nome_original or nome, "url": url},
        }
    )


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
@require_POST
def impedimento_arquivo_remover(request, obra_id, impedimento_id, arquivo_id):
    project = get_object_or_404(Project, pk=obra_id, is_active=True)
    if not _user_can_access_project(request.user, project):
        return JsonResponse(
            {"ok": False, "error": "Sem acesso a esta obra."}, status=403
        )
    obra = get_object_or_404(Obra, project=project)
    impedimento = Impedimento.objects.filter(pk=impedimento_id, obra=obra).first()
    if not impedimento:
        return JsonResponse(
            {"ok": False, "error": "Restrição não encontrada."}, status=404
        )

    ar = ArquivoImpedimento.objects.filter(
        pk=arquivo_id, impedimento=impedimento
    ).first()
    if not ar:
        return JsonResponse(
            {"ok": False, "error": "Arquivo não encontrado."}, status=404
        )
    nome_orig = ar.nome_original or ""
    ar.delete()
    _registrar_atividade_impedimento(
        impedimento,
        request.user,
        f'Removeu arquivo "{nome_orig}"',
        "arquivo",
    )

    return JsonResponse({"ok": True})


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
def legacy_list_impedimentos(request):
    return redirect("impedimentos:select_obra")


@login_required
@require_group(GRUPOS.ADMINISTRADOR, GRUPOS.GESTAO_IMPEDIMENTOS)
def legacy_list_status_redirect(request):
    messages.info(
        request,
        "Selecione uma obra para configurar os status das restrições.",
    )
    return redirect("impedimentos:select_obra")


def _ensure_one_default_status(obra):
    qs = StatusImpedimento.objects.filter(obra=obra).order_by("ordem", "id")
    if not qs.exists():
        return
    defaults = list(qs.filter(is_default=True))
    if len(defaults) == 0:
        first = qs.first()
        StatusImpedimento.objects.filter(pk=first.pk).update(is_default=True)
    elif len(defaults) > 1:
        keeper = min(defaults, key=lambda s: (s.ordem, s.pk))
        StatusImpedimento.objects.filter(obra=obra, is_default=True).exclude(
            pk=keeper.pk
        ).update(is_default=False)


def _reorder_status_adjacent(obra, status_id, direction):
    statuses = list(
        StatusImpedimento.objects.filter(obra=obra).order_by("ordem", "id")
    )
    try:
        sid = int(status_id)
    except (TypeError, ValueError):
        return False
    try:
        idx = next(i for i, s in enumerate(statuses) if s.id == sid)
    except StopIteration:
        return False
    if direction == "up" and idx > 0:
        statuses[idx - 1], statuses[idx] = statuses[idx], statuses[idx - 1]
    elif direction == "down" and idx < len(statuses) - 1:
        statuses[idx + 1], statuses[idx] = statuses[idx], statuses[idx + 1]
    else:
        return False
    with transaction.atomic():
        for i, s in enumerate(statuses, start=1):
            s.ordem = i
        StatusImpedimento.objects.bulk_update(statuses, ["ordem"])
    return True


@login_required
def list_status(request, obra_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden(
            "Apenas administradores podem configurar os status."
        )

    project = get_object_or_404(Project, pk=obra_id, is_active=True)
    if not _user_can_access_project(request.user, project):
        messages.error(request, "Você não está vinculado a esta obra.")
        return redirect("impedimentos:select_obra")

    obra = get_object_or_404(Obra, project=project)
    count_status = StatusImpedimento.objects.filter(obra=obra).count()
    next_ordem = count_status + 1

    show_modal = False

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()

        if action == "delete":
            sid = request.POST.get("status_id")
            try:
                st = StatusImpedimento.objects.get(pk=sid, obra=obra)
            except (StatusImpedimento.DoesNotExist, ValueError, TypeError):
                messages.error(request, "Status não encontrado.")
            else:
                if Impedimento.objects.filter(status=st).exists():
                    messages.error(
                        request,
                        "Não é possível excluir: existem restrições vinculadas a este status.",
                    )
                else:
                    st.delete()
                    _ensure_one_default_status(obra)
                    messages.success(request, "Status excluído.")
            return redirect("impedimentos:list_status", obra_id=project.id)

        if action == "reorder":
            direction = (request.POST.get("direction") or "").strip().lower()
            sid = request.POST.get("status_id")
            if direction in {"up", "down"} and _reorder_status_adjacent(obra, sid, direction):
                messages.success(request, "Ordem atualizada.")
            else:
                messages.error(request, "Não foi possível alterar a ordem.")
            return redirect("impedimentos:list_status", obra_id=project.id)

        if action == "update":
            sid = request.POST.get("status_id")
            try:
                instance = StatusImpedimento.objects.get(pk=sid, obra=obra)
            except (StatusImpedimento.DoesNotExist, ValueError, TypeError):
                instance = None
            if not instance:
                messages.error(request, "Status não encontrado para edição.")
                return redirect("impedimentos:list_status", obra_id=project.id)
            form = StatusImpedimentoForm(request.POST, obra=obra, instance=instance)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.obra = obra
                obj.save()
                if obj.is_default:
                    StatusImpedimento.objects.filter(obra=obra).exclude(pk=obj.pk).update(
                        is_default=False
                    )
                _ensure_one_default_status(obra)
                messages.success(request, "Status atualizado.")
                return redirect("impedimentos:list_status", obra_id=project.id)
            show_modal = True
        elif action == "create":
            form = StatusImpedimentoForm(request.POST, obra=obra)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.obra = obra
                obj.save()
                if obj.is_default:
                    StatusImpedimento.objects.filter(obra=obra).exclude(pk=obj.pk).update(
                        is_default=False
                    )
                _ensure_one_default_status(obra)
                messages.success(request, "Status criado.")
                return redirect("impedimentos:list_status", obra_id=project.id)
            show_modal = True
        else:
            messages.error(request, "Ação inválida.")
            return redirect("impedimentos:list_status", obra_id=project.id)
    else:
        form = StatusImpedimentoForm(
            obra=obra,
            initial={"ordem": next_ordem},
        )

    status_list = list(
        StatusImpedimento.objects.filter(obra=obra).order_by("ordem", "nome")
    )
    context = {
        "title": "Status das restrições",
        "obra": obra,
        "project": project,
        "status_list": status_list,
        "form": form,
        "show_modal": show_modal,
        "next_ordem": len(status_list) + 1,
    }
    response = render(request, "impedimentos/list_status.html", context)
    return _with_no_cache_headers(response)
