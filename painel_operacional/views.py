import json
from uuid import uuid4

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_http_methods

from accounts.decorators import login_required, require_group
from accounts.groups import GRUPOS
from mapa_obras.models import Obra
from mapa_obras.views import _get_obras_for_user, _user_can_access_obra

from .models import (
    AmbienteCelula,
    AmbienteElemento,
    AmbienteHistorico,
    AmbienteOperacional,
    AmbienteTipo,
    AmbienteVersao,
    SemanticaIndicador,
    VersaoEstado,
)


def _resolver_obra(request):
    obras = _get_obras_for_user(request)
    obra = None
    obra_param = request.GET.get("obra") or request.POST.get("obra")

    if obra_param:
        try:
            obra = Obra.objects.get(id=int(obra_param), ativa=True)
            if not _user_can_access_obra(request, obra):
                obra = None
        except (Obra.DoesNotExist, ValueError):
            obra = None

    if not obra:
        obra_sessao_id = request.session.get("obra_id")
        if obra_sessao_id:
            try:
                obra = Obra.objects.get(id=int(obra_sessao_id), ativa=True)
                if not _user_can_access_obra(request, obra):
                    obra = None
            except (Obra.DoesNotExist, ValueError):
                obra = None

    if not obra:
        obra = obras.first()

    if obra:
        request.session["obra_id"] = obra.id
        request.session.modified = True

    return obras, obra


def _parse_json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def _preset_layout(tipo: str):
    if tipo == AmbienteTipo.MAPA_CONTROLE:
        return {
            "title": "Mapa de Controle",
            "sections": [
                {
                    "id": "resumo",
                    "kind": "kpi_strip",
                    "title": "Resumo",
                    "x": 80,
                    "y": 80,
                    "width": 340,
                    "height": 180,
                    "layer": {},
                },
                {
                    "id": "matriz",
                    "kind": "matrix_table",
                    "title": "Matriz de Controle",
                    "x": 460,
                    "y": 80,
                    "width": 560,
                    "height": 320,
                    "layer": {},
                    "data": {"rows": [["Atividade", "Bloco A", "Bloco B"], ["Fundação", "", ""], ["Estrutura", "", ""]]},
                },
                {
                    "id": "detalhe",
                    "kind": "detail_panel",
                    "title": "Detalhamento",
                    "x": 80,
                    "y": 300,
                    "width": 340,
                    "height": 200,
                    "layer": {},
                },
            ],
        }
    return {"title": "Ambiente Operacional", "sections": []}


def _serializar_ambiente(ambiente: AmbienteOperacional):
    versao_publicada = ambiente.versoes.filter(estado=VersaoEstado.PUBLISHED).order_by("-numero").first()
    versao_draft = ambiente.versoes.filter(estado=VersaoEstado.DRAFT).order_by("-numero").first()
    return {
        "id": ambiente.id,
        "nome": ambiente.nome,
        "tipo": ambiente.tipo,
        "descricao": ambiente.descricao,
        "obra_id": ambiente.obra_id,
        "ativo": ambiente.ativo,
        "updated_at": ambiente.updated_at.isoformat(),
        "versao_publicada": versao_publicada.numero if versao_publicada else None,
        "versao_rascunho": versao_draft.numero if versao_draft else None,
    }


def _serializar_versao(versao: AmbienteVersao | None):
    if not versao:
        return None
    return {
        "id": versao.id,
        "numero": versao.numero,
        "estado": versao.estado,
        "layout": versao.layout,
        "metadados": versao.metadados,
        "updated_at": versao.updated_at.isoformat(),
    }


def _validar_layout_publicacao(layout: dict):
    sections = layout.get("sections", []) if isinstance(layout, dict) else []
    if not sections:
        return "Adicione pelo menos uma seção antes de publicar."
    if not isinstance(sections, list):
        return "Formato de seções inválido."
    for idx, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            return f"Seção {idx} inválida."
        title = (section.get("title") or "").strip()
        kind = (section.get("kind") or "").strip()
        if not title:
            return f"Seção {idx} sem título."
        if not kind:
            return f"Seção {idx} sem tipo."
    return None


def _serializar_semanticas():
    return [
        {
            "id": item.id,
            "nome_canonico": item.nome_canonico,
            "descricao_operacional": item.descricao_operacional,
            "dominio": item.dominio,
            "origem_dado": item.origem_dado,
        }
        for item in SemanticaIndicador.objects.filter(ativo=True).order_by("dominio", "nome_canonico")
    ]


def _map_kind_to_element_type(kind: str):
    if kind == "matrix_table":
        return "table"
    if kind == "kpi_strip":
        return "kpi"
    if kind == "detail_panel":
        return "area"
    return "block"


def _map_element_type_to_kind(element_type: str):
    if element_type == "table":
        return "matrix_table"
    if element_type == "kpi":
        return "kpi_strip"
    if element_type == "area":
        return "detail_panel"
    return "block"


def _sync_layout_to_elementos(ambiente: AmbienteOperacional, versao: AmbienteVersao):
    layout = versao.layout if isinstance(versao.layout, dict) else {}
    sections = layout.get("sections", [])
    if not isinstance(sections, list):
        return

    keys = []
    for idx, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        section_id = (section.get("id") or "").strip() or f"sec_{uuid4().hex[:8]}"
        keys.append(section_id)
        elemento, _ = AmbienteElemento.objects.get_or_create(
            ambiente=ambiente,
            chave_externa=section_id,
            defaults={"titulo": section.get("title") or "", "tipo": _map_kind_to_element_type(section.get("kind") or "")},
        )
        elemento.versao = versao
        elemento.titulo = (section.get("title") or "").strip()
        elemento.tipo = _map_kind_to_element_type((section.get("kind") or "").strip())
        elemento.x = int(section.get("x") or 0)
        elemento.y = int(section.get("y") or 0)
        elemento.width = int(section.get("width") or 320)
        elemento.height = int(section.get("height") or 180)
        elemento.z_index = idx
        camada = section.get("layer")
        if not isinstance(camada, dict):
            camada = {}
        elemento.camada = camada
        elemento.dados = {
            "kind": section.get("kind"),
            "semantica": section.get("semantica"),
        }
        elemento.ativo = True
        elemento.origem_layout = True
        elemento.save()

        if elemento.tipo == "table":
            matrix_data = section.get("data") if isinstance(section.get("data"), dict) else {}
            rows = matrix_data.get("rows", [])
            if isinstance(rows, list):
                elemento.celulas.all().delete()
                new_cells = []
                for r_idx, row in enumerate(rows):
                    if not isinstance(row, list):
                        continue
                    for c_idx, value in enumerate(row):
                        new_cells.append(
                            AmbienteCelula(
                                elemento=elemento,
                                linha_idx=r_idx,
                                coluna_idx=c_idx,
                                valor=str(value) if value is not None else "",
                                tipo="texto",
                            )
                        )
                if new_cells:
                    AmbienteCelula.objects.bulk_create(new_cells, batch_size=500)

    AmbienteElemento.objects.filter(ambiente=ambiente, origem_layout=True).exclude(chave_externa__in=keys).update(ativo=False)


@login_required
@require_group(GRUPOS.ENGENHARIA)
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def ferramenta_shell(request):
    obras, obra = _resolver_obra(request)
    ambientes = []
    if obra:
        ambientes = [
            _serializar_ambiente(amb)
            for amb in AmbienteOperacional.objects.filter(obra=obra, ativo=True).order_by("-updated_at")[:20]
        ]

    return render(
        request,
        "painel_operacional/ferramenta_shell.html",
        {
            "obras": obras,
            "obra_selecionada": obra,
            "ambientes_json": json.dumps(ambientes),
            "tipos_ambiente": AmbienteTipo.choices,
        },
    )


@login_required
@require_group(GRUPOS.ENGENHARIA)
def editor_ambiente(request, ambiente_id: int):
    _, obra = _resolver_obra(request)
    ambiente = get_object_or_404(AmbienteOperacional, id=ambiente_id, ativo=True)
    if not obra or ambiente.obra_id != obra.id:
        return render(
            request,
            "painel_operacional/editor_ambiente.html",
            {"erro_acesso": "Ambiente não pertence à obra ativa."},
            status=403,
        )

    draft = ambiente.versoes.filter(estado=VersaoEstado.DRAFT).order_by("-numero").first()
    published = ambiente.versoes.filter(estado=VersaoEstado.PUBLISHED).order_by("-numero").first()
    usar_beta = request.GET.get("beta") == "1"
    is_mapa_controle = ambiente.tipo == AmbienteTipo.MAPA_CONTROLE
    obra_id = obra.id
    mapa_url = f"{reverse('engenharia:mapa_controle')}?obra={obra_id}"
    importar_url = f"{reverse('engenharia:importar_mapa_controle')}?obra={obra_id}"

    return render(
        request,
        "painel_operacional/editor_ambiente.html",
        {
            "ambiente": ambiente,
            "obra_selecionada": obra,
            "draft_json": json.dumps(_serializar_versao(draft) or {}),
            "published_json": json.dumps(_serializar_versao(published) or {}),
            "semanticas_json": json.dumps(_serializar_semanticas()),
            "is_mapa_controle": is_mapa_controle,
            "usar_beta": usar_beta,
            "render_beta_editor": (not is_mapa_controle) or usar_beta,
            "mapa_atual_url": mapa_url,
            "importar_mapa_url": importar_url,
            "beta_editor_url": f"{reverse('engenharia:ferramenta_editor_ambiente', kwargs={'ambiente_id': ambiente.id})}?beta=1",
        },
    )


@login_required
@require_group(GRUPOS.ENGENHARIA)
@require_http_methods(["GET"])
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def api_listar_ambientes(request):
    obras, obra = _resolver_obra(request)
    if not obra:
        return JsonResponse({"success": True, "items": [], "message": "Nenhuma obra disponível."})

    items = [
        _serializar_ambiente(amb)
        for amb in AmbienteOperacional.objects.filter(obra=obra, ativo=True).order_by("-updated_at")[:100]
    ]
    return JsonResponse(
        {"success": True, "items": items, "obra": {"id": obra.id, "nome": obra.nome, "codigo": obra.codigo_sienge}}
    )


@login_required
@require_group(GRUPOS.ENGENHARIA)
@require_http_methods(["GET"])
def api_detalhe_ambiente(request, ambiente_id: int):
    _, obra = _resolver_obra(request)
    ambiente = get_object_or_404(AmbienteOperacional, id=ambiente_id, ativo=True)
    if not obra or ambiente.obra_id != obra.id:
        return JsonResponse({"success": False, "error": "Ambiente não pertence à obra ativa."}, status=403)

    draft = ambiente.versoes.filter(estado=VersaoEstado.DRAFT).order_by("-numero").first()
    published = ambiente.versoes.filter(estado=VersaoEstado.PUBLISHED).order_by("-numero").first()
    elementos = (
        AmbienteElemento.objects.filter(ambiente=ambiente, ativo=True)
        .order_by("z_index", "id")
        .values(
            "id",
            "chave_externa",
            "titulo",
            "tipo",
            "x",
            "y",
            "width",
            "height",
            "z_index",
            "camada",
            "dados",
        )
    )
    return JsonResponse(
        {
            "success": True,
            "ambiente": _serializar_ambiente(ambiente),
            "draft": _serializar_versao(draft),
            "published": _serializar_versao(published),
            "semanticas": _serializar_semanticas(),
            "elementos": list(elementos),
        }
    )


@login_required
@require_group(GRUPOS.ENGENHARIA)
@require_http_methods(["POST"])
def api_criar_ambiente(request):
    payload = _parse_json_body(request)
    _, obra = _resolver_obra(request)
    if not obra:
        return JsonResponse({"success": False, "error": "Selecione uma obra válida."}, status=400)

    nome = (payload.get("nome") or "").strip() or "Novo ambiente"
    tipo = (payload.get("tipo") or AmbienteTipo.MAPA_CONTROLE).strip()
    tipos_validos = {choice[0] for choice in AmbienteTipo.choices}
    if tipo not in tipos_validos:
        tipo = AmbienteTipo.CUSTOM

    with transaction.atomic():
        ambiente = AmbienteOperacional.objects.create(
            obra=obra,
            nome=nome,
            tipo=tipo,
            descricao=(payload.get("descricao") or "").strip(),
            criado_por=request.user,
        )
        versao = AmbienteVersao.objects.create(
            ambiente=ambiente,
            numero=1,
            estado=VersaoEstado.DRAFT,
            layout=_preset_layout(tipo),
            metadados={"preset": tipo},
        )
        AmbienteHistorico.objects.create(
            ambiente=ambiente,
            versao=versao,
            usuario=request.user,
            acao=AmbienteHistorico.ACAO_CRIAR,
            detalhes={"preset": tipo},
        )

    return JsonResponse({"success": True, "item": _serializar_ambiente(ambiente)})


@login_required
@require_group(GRUPOS.ENGENHARIA)
@require_http_methods(["POST"])
def api_adicionar_secao(request, ambiente_id: int):
    payload = _parse_json_body(request)
    _, obra = _resolver_obra(request)
    ambiente = get_object_or_404(AmbienteOperacional, id=ambiente_id, ativo=True)
    if not obra or ambiente.obra_id != obra.id:
        return JsonResponse({"success": False, "error": "Ambiente não pertence à obra ativa."}, status=403)

    titulo = (payload.get("title") or "").strip()
    tipo = (payload.get("kind") or "").strip()
    if not titulo or not tipo:
        return JsonResponse({"success": False, "error": "Informe título e tipo da seção."}, status=400)

    with transaction.atomic():
        draft = ambiente.versoes.filter(estado=VersaoEstado.DRAFT).order_by("-numero").first()
        if not draft:
            draft = AmbienteVersao.objects.create(
                ambiente=ambiente,
                numero=AmbienteVersao.proximo_numero(ambiente.id),
                estado=VersaoEstado.DRAFT,
                layout=_preset_layout(ambiente.tipo),
                metadados={},
            )

        layout = draft.layout if isinstance(draft.layout, dict) else {}
        sections = layout.get("sections", [])
        if not isinstance(sections, list):
            sections = []
        section = {
            "id": payload.get("id") or f"sec_{uuid4().hex[:8]}",
            "title": titulo,
            "kind": tipo,
            "x": payload.get("x", 80 + ((len(sections) % 4) * 280)),
            "y": payload.get("y", 80 + ((len(sections) // 4) * 220)),
            "width": payload.get("width", 320 if tipo != "matrix_table" else 560),
            "height": payload.get("height", 180 if tipo != "matrix_table" else 320),
            "layer": payload.get("layer") if isinstance(payload.get("layer"), dict) else {},
        }
        semantica = (payload.get("semantica") or "").strip()
        if semantica:
            section["semantica"] = semantica
        if tipo == "matrix_table":
            section["data"] = {"rows": [["Coluna 1", "Coluna 2"], ["", ""], ["", ""]]}
        sections.append(section)
        layout["sections"] = sections
        draft.layout = layout
        draft.save(update_fields=["layout", "updated_at"])

        AmbienteHistorico.objects.create(
            ambiente=ambiente,
            versao=draft,
            usuario=request.user,
            acao=AmbienteHistorico.ACAO_SALVAR,
            detalhes={"acao_editor": "adicionar_secao", "secao_id": section["id"], "kind": tipo},
        )

    return JsonResponse({"success": True, "draft": _serializar_versao(draft)})


@login_required
@require_group(GRUPOS.ENGENHARIA)
@require_http_methods(["POST"])
def api_salvar_rascunho(request, ambiente_id: int):
    payload = _parse_json_body(request)
    _, obra = _resolver_obra(request)

    ambiente = get_object_or_404(AmbienteOperacional, id=ambiente_id, ativo=True)
    if not obra or ambiente.obra_id != obra.id:
        return JsonResponse({"success": False, "error": "Ambiente não pertence à obra ativa."}, status=403)

    with transaction.atomic():
        draft = ambiente.versoes.filter(estado=VersaoEstado.DRAFT).order_by("-numero").first()
        if not draft:
            draft = AmbienteVersao.objects.create(
                ambiente=ambiente,
                numero=AmbienteVersao.proximo_numero(ambiente.id),
                estado=VersaoEstado.DRAFT,
                layout={},
                metadados={},
            )

        layout = payload.get("layout")
        metadados = payload.get("metadados")
        if isinstance(layout, dict):
            draft.layout = layout
        if isinstance(metadados, dict):
            draft.metadados = metadados
        draft.save(update_fields=["layout", "metadados", "updated_at"])
        _sync_layout_to_elementos(ambiente, draft)

        AmbienteHistorico.objects.create(
            ambiente=ambiente,
            versao=draft,
            usuario=request.user,
            acao=AmbienteHistorico.ACAO_SALVAR,
            detalhes={"keys_layout": sorted(list(draft.layout.keys()))},
        )

    return JsonResponse({"success": True, "rascunho": {"numero": draft.numero, "updated_at": draft.updated_at.isoformat()}})


@login_required
@require_group(GRUPOS.ENGENHARIA)
@require_http_methods(["GET"])
def api_listar_elementos(request, ambiente_id: int):
    _, obra = _resolver_obra(request)
    ambiente = get_object_or_404(AmbienteOperacional, id=ambiente_id, ativo=True)
    if not obra or ambiente.obra_id != obra.id:
        return JsonResponse({"success": False, "error": "Ambiente não pertence à obra ativa."}, status=403)
    elementos = list(
        AmbienteElemento.objects.filter(ambiente=ambiente, ativo=True)
        .order_by("z_index", "id")
        .values(
            "id",
            "chave_externa",
            "titulo",
            "tipo",
            "x",
            "y",
            "width",
            "height",
            "z_index",
            "camada",
            "dados",
        )
    )
    return JsonResponse({"success": True, "items": elementos})


@login_required
@require_group(GRUPOS.ENGENHARIA)
@require_http_methods(["POST"])
def api_sync_elementos(request, ambiente_id: int):
    payload = _parse_json_body(request)
    _, obra = _resolver_obra(request)
    ambiente = get_object_or_404(AmbienteOperacional, id=ambiente_id, ativo=True)
    if not obra or ambiente.obra_id != obra.id:
        return JsonResponse({"success": False, "error": "Ambiente não pertence à obra ativa."}, status=403)

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return JsonResponse({"success": False, "error": "Payload inválido: items deve ser lista."}, status=400)

    with transaction.atomic():
        draft = ambiente.versoes.filter(estado=VersaoEstado.DRAFT).order_by("-numero").first()
        if not draft:
            draft = AmbienteVersao.objects.create(
                ambiente=ambiente,
                numero=AmbienteVersao.proximo_numero(ambiente.id),
                estado=VersaoEstado.DRAFT,
                layout=_preset_layout(ambiente.tipo),
                metadados={},
            )

        existing_by_id = {
            row.id: row for row in AmbienteElemento.objects.filter(ambiente=ambiente)
        }
        existing_by_key = {
            row.chave_externa: row
            for row in AmbienteElemento.objects.filter(ambiente=ambiente).exclude(chave_externa="")
        }

        kept_ids = []
        sections = []

        for idx, item in enumerate(raw_items):
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            raw_key = str(item.get("chave_externa") or item.get("key") or "").strip()
            key = raw_key or f"sec_{uuid4().hex[:8]}"
            titulo = str(item.get("titulo") or item.get("title") or "").strip()
            kind = str(item.get("kind") or item.get("tipo") or "block").strip()
            tipo = _map_kind_to_element_type(kind)

            elemento = None
            if raw_id:
                try:
                    elemento = existing_by_id.get(int(raw_id))
                except (TypeError, ValueError):
                    elemento = None
            if not elemento:
                elemento = existing_by_key.get(key)
            if not elemento:
                elemento = AmbienteElemento(ambiente=ambiente)

            elemento.versao = draft
            elemento.chave_externa = key
            elemento.titulo = titulo
            elemento.tipo = tipo
            elemento.x = int(item.get("x") or 0)
            elemento.y = int(item.get("y") or 0)
            elemento.width = max(80, int(item.get("width") or 320))
            elemento.height = max(60, int(item.get("height") or 180))
            elemento.z_index = idx
            layer = item.get("layer")
            elemento.camada = layer if isinstance(layer, dict) else {}
            data = item.get("data")
            element_data = data if isinstance(data, dict) else {}
            semantica = str(item.get("semantica") or element_data.get("semantica") or "").strip()
            element_data["semantica"] = semantica
            element_data["kind"] = kind
            elemento.dados = element_data
            elemento.ativo = True
            elemento.origem_layout = True
            elemento.save()
            kept_ids.append(elemento.id)

            if elemento.tipo == "table":
                rows = []
                if isinstance(element_data.get("rows"), list):
                    rows = element_data.get("rows")
                elemento.celulas.all().delete()
                cells = []
                for r_idx, row in enumerate(rows):
                    if not isinstance(row, list):
                        continue
                    for c_idx, value in enumerate(row):
                        cells.append(
                            AmbienteCelula(
                                elemento=elemento,
                                linha_idx=r_idx,
                                coluna_idx=c_idx,
                                valor=str(value) if value is not None else "",
                                tipo="texto",
                            )
                        )
                if cells:
                    AmbienteCelula.objects.bulk_create(cells, batch_size=500)

            sections.append(
                {
                    "id": key,
                    "title": titulo,
                    "kind": kind,
                    "x": elemento.x,
                    "y": elemento.y,
                    "width": elemento.width,
                    "height": elemento.height,
                    "layer": elemento.camada,
                    "semantica": semantica,
                    "data": element_data if elemento.tipo == "table" else {},
                }
            )

        AmbienteElemento.objects.filter(ambiente=ambiente).exclude(id__in=kept_ids).update(ativo=False)

        layout = draft.layout if isinstance(draft.layout, dict) else {}
        layout["sections"] = sections
        draft.layout = layout
        draft.save(update_fields=["layout", "updated_at"])

        AmbienteHistorico.objects.create(
            ambiente=ambiente,
            versao=draft,
            usuario=request.user,
            acao=AmbienteHistorico.ACAO_SALVAR,
            detalhes={"acao_editor": "sync_elementos", "qtd": len(sections)},
        )

    return JsonResponse(
        {
            "success": True,
            "items": sections,
            "rascunho": {"numero": draft.numero, "updated_at": draft.updated_at.isoformat()},
        }
    )


@login_required
@require_group(GRUPOS.ENGENHARIA)
@require_http_methods(["POST"])
def api_publicar_ambiente(request, ambiente_id: int):
    _, obra = _resolver_obra(request)
    ambiente = get_object_or_404(AmbienteOperacional, id=ambiente_id, ativo=True)
    if not obra or ambiente.obra_id != obra.id:
        return JsonResponse({"success": False, "error": "Ambiente não pertence à obra ativa."}, status=403)

    with transaction.atomic():
        draft = ambiente.versoes.filter(estado=VersaoEstado.DRAFT).order_by("-numero").first()
        if not draft:
            return JsonResponse({"success": False, "error": "Nenhum rascunho disponível para publicação."}, status=400)
        erro_layout = _validar_layout_publicacao(draft.layout if isinstance(draft.layout, dict) else {})
        if erro_layout:
            return JsonResponse({"success": False, "error": erro_layout}, status=400)

        ambiente.versoes.filter(estado=VersaoEstado.PUBLISHED).update(estado=VersaoEstado.ARCHIVED)
        draft.estado = VersaoEstado.PUBLISHED
        draft.publicado_em = timezone.now()
        draft.publicado_por = request.user
        draft.save(update_fields=["estado", "publicado_em", "publicado_por", "updated_at"])

        proxima = AmbienteVersao.objects.create(
            ambiente=ambiente,
            numero=AmbienteVersao.proximo_numero(ambiente.id),
            estado=VersaoEstado.DRAFT,
            layout=draft.layout,
            metadados=draft.metadados,
        )

        AmbienteHistorico.objects.create(
            ambiente=ambiente,
            versao=draft,
            usuario=request.user,
            acao=AmbienteHistorico.ACAO_PUBLICAR,
            detalhes={"versao_publicada": draft.numero, "rascunho_criado": proxima.numero},
        )

    return JsonResponse(
        {
            "success": True,
            "publicada": {"numero": draft.numero, "publicado_em": draft.publicado_em.isoformat()},
            "rascunho": {"numero": proxima.numero},
        }
    )

