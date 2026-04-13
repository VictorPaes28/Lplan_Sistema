from decimal import Decimal

from django.db.models import Q, Sum, Value
from django.db.models.functions import Coalesce

from assistente_lplan.schemas import AssistantResponse
from assistente_lplan.services.llm_provider import LLMProvider
from assistente_lplan.services.obras_service import ObrasAssistantService
from mapa_obras.models import LocalObra, Obra
from suprimentos.models import ItemMapa
from suprimentos.services.local_mapa_relatorio_service import (
    LocalMapaRelatorioService,
    find_local_obra,
)
from .messages import MessageCatalog


class SuprimentosAssistantService:
    def __init__(self, scope):
        self.scope = scope

    def localizar_insumo(self, entities: dict) -> AssistantResponse:
        term = (entities.get("insumo") or "").strip()
        bloco = (entities.get("bloco") or "").strip()
        if not term:
            msg = MessageCatalog.resolve("assistant.suprimentos.insumo_missing", {"domain": "suprimentos"})
            return AssistantResponse(
                summary=msg["text"],
                alerts=[
                    {
                        "level": "warning",
                        "message": msg["next_steps"][0],
                    }
                ],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )

        obras_qs = self._obras_scope_qs()
        q = (
            ItemMapa.objects.select_related("obra", "insumo", "local_aplicacao")
            .filter(obra__in=obras_qs)
            .filter(
                Q(insumo__descricao__icontains=term)
                | Q(descricao_override__icontains=term)
                | Q(insumo__codigo_sienge__icontains=term)
            )
            .annotate(total_alocado=Coalesce(Sum("alocacoes__quantidade_alocada"), Value(Decimal("0"))))
        )
        if bloco:
            q = q.filter(Q(local_aplicacao__nome__icontains=bloco) | Q(local_aplicacao__tipo__icontains=bloco))

        rows = []
        for item in list(q[:20]):
            planejado = item.quantidade_planejada or Decimal("0")
            alocado = item.total_alocado or Decimal("0")
            rows.append(
                {
                    "obra": item.obra.nome if item.obra else "-",
                    "insumo": item.insumo.descricao if item.insumo else "-",
                    "local": (item.local_aplicacao.nome if item.local_aplicacao else "Sem local"),
                    "planejado": str(planejado),
                    "alocado": str(alocado),
                    "status": "OK" if alocado > 0 else "Sem alocacao",
                }
            )

        if not rows:
            msg = MessageCatalog.resolve(
                "assistant.suprimentos.insumo_not_found",
                {"domain": "suprimentos", "insumo": term},
            )
            return AssistantResponse(
                summary=msg["text"],
                alerts=[
                    {
                        "level": "warning",
                        "message": msg["next_steps"][0],
                    }
                ],
                badges=["Sem dados suficientes"],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"], "insumo": term},
            )

        return AssistantResponse(
            summary=f"Foram encontrados {len(rows)} registros para '{term}'.",
            cards=[{"title": "Registros", "value": str(len(rows)), "tone": "info"}],
            table={
                "caption": "Localizacao de insumos no mapa",
                "columns": ["obra", "insumo", "local", "planejado", "alocado", "status"],
                "rows": rows,
            },
            badges=["Suprimentos", "Localizacao"],
            actions=[{"label": "Abrir mapa", "url": "/engenharia/mapa/", "style": "primary"}],
            links=[{"label": "Mapa de Suprimentos", "url": "/engenharia/mapa/"}],
        )

    def itens_sem_alocacao(self, entities: dict) -> AssistantResponse:
        obras_qs = self._obras_scope_qs()
        qs = (
            ItemMapa.objects.select_related("obra", "insumo", "local_aplicacao")
            .filter(obra__in=obras_qs)
            .annotate(total_alocado=Coalesce(Sum("alocacoes__quantidade_alocada"), Value(Decimal("0"))))
            .filter(quantidade_planejada__gt=0, total_alocado__lte=0)
            .order_by("-prioridade", "prazo_necessidade")[:30]
        )
        rows = []
        for item in qs:
            rows.append(
                {
                    "obra": item.obra.nome if item.obra else "-",
                    "insumo": item.insumo.descricao if item.insumo else "-",
                    "local": item.local_aplicacao.nome if item.local_aplicacao else "Sem local",
                    "prioridade": item.prioridade,
                    "prazo": item.prazo_necessidade.strftime("%d/%m/%Y") if item.prazo_necessidade else "-",
                }
            )

        if not rows:
            msg = MessageCatalog.resolve("assistant.suprimentos.unallocated_empty", {"domain": "suprimentos"})
            return AssistantResponse(
                summary=msg["text"],
                badges=["Sem dados suficientes"],
                alerts=[{"level": "info", "message": msg["next_steps"][0]}],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )

        return AssistantResponse(
            summary=f"{len(rows)} itens estao sem alocacao no escopo atual.",
            cards=[
                {"title": "Itens sem alocacao", "value": str(len(rows)), "tone": "danger"},
                {"title": "Obras afetadas", "value": str(len({r['obra'] for r in rows})), "tone": "warning"},
            ],
            table={
                "caption": "Itens planejados sem alocacao",
                "columns": ["obra", "insumo", "local", "prioridade", "prazo"],
                "rows": rows,
            },
            alerts=[{"level": "error", "message": "Itens sem alocacao podem travar execucao da obra."}],
            badges=["Suprimentos", "Risco de execucao"],
            actions=[{"label": "Revisar alocacoes", "url": "/engenharia/mapa/", "style": "primary"}],
            links=[{"label": "Tela do mapa", "url": "/engenharia/mapa/"}],
        )

    def _obras_scope_qs(self):
        qs = Obra.objects.filter(ativa=True)
        if self.scope.role == "admin":
            return qs
        if self.scope.project_codes:
            return qs.filter(codigo_sienge__in=self.scope.project_codes)
        return qs.none()

    def _resolve_project(self, entities: dict):
        return ObrasAssistantService(self.scope)._resolve_project(entities)

    def _resolve_mapa_obra(self, project):
        """Obra do mapa (Sienge) a partir do Project do diario."""
        if not project:
            return None
        code = (project.code or "").strip()
        if not code:
            return None
        o = Obra.objects.filter(ativa=True, codigo_sienge=code).first()
        if o:
            return o
        for obra in Obra.objects.filter(ativa=True):
            if code in obra.chaves_sienge_busca_importacao():
                return obra
        return None

    def _projeto_autoriza_obra(self, project, obra: Obra) -> bool:
        if self.scope.role == "admin":
            return True
        code = (project.code or "").strip()
        return code in obra.chaves_sienge_busca_importacao()

    def relatorio_local_mapa(self, entities: dict, user_question: str = "") -> AssistantResponse:
        """
        Relatorio detalhado de um apartamento/local no Mapa de Controle (benchmark na obra).
        """
        project = self._resolve_project(entities)
        if not project:
            return AssistantResponse(
                summary="Nao foi possivel identificar a obra (projeto). Informe o codigo da obra ou selecione na sessao.",
                badges=["Suprimentos", "Mapa"],
                alerts=[{"level": "warning", "message": "Use Selecionar obra ou mencione o codigo na pergunta."}],
                raw_data={"reason": "sem_projeto"},
            )

        obra = self._resolve_mapa_obra(project)
        if not obra:
            return AssistantResponse(
                summary=(
                    f"O projeto {project.code} nao tem obra de mapa vinculada pelo codigo Sienge. "
                    "Confira se o codigo do projeto bate com o cadastro em Mapa de Suprimentos."
                ),
                badges=["Suprimentos", "Mapa"],
                alerts=[{"level": "warning", "message": "Ajuste codigo Sienge da obra ou cadastre a obra no mapa."}],
                raw_data={"project_code": project.code},
            )

        if not self._projeto_autoriza_obra(project, obra):
            return AssistantResponse(
                summary="Esta obra de mapa nao esta no seu escopo de acesso.",
                badges=["Sem permissao"],
                alerts=[{"level": "warning", "message": "Peça ao gestor liberacao ao projeto."}],
                raw_data={"obra": obra.codigo_sienge},
            )

        ref = (
            (entities.get("referencia_local") or "").strip()
            or (entities.get("local") or "").strip()
            or (entities.get("apartamento") or "").strip()
        )
        q = (user_question or "").strip()
        local = find_local_obra(
            obra,
            referencia=ref,
            texto_usuario=q,
            local_id=(entities.get("local_id") or ""),
        )

        if not local:
            locais = list(
                LocalObra.objects.filter(obra=obra)
                .order_by("tipo", "nome")
                .values_list("nome", flat=True)[:18]
            )
            chips = [
                f"Como esta o local {nome} no mapa de controle da obra {project.code}?"
                for nome in locais
                if nome
            ]
            return AssistantResponse(
                summary=(
                    f"Nao identifiquei qual local na obra {project.code}. "
                    "Diga o nome do apartamento ou unidade como aparece no mapa (ex.: Bloco A - Apto 302), "
                    "ou use um dos atalhos."
                ),
                badges=["Mapa", "Escolha o local"],
                suggested_replies=chips[:12],
                alerts=[{"level": "info", "message": "O nome deve coincidir com o cadastro de locais do mapa."}],
                actions=[{"label": "Abrir Mapa de Suprimentos", "url": "/engenharia/mapa/", "style": "primary"}],
                links=[{"label": "Mapa de Suprimentos", "url": "/engenharia/mapa/"}],
                raw_data={"project_code": project.code, "locais_disponiveis": locais},
            )

        svc = LocalMapaRelatorioService(obra)
        facts = svc.build_facts_for_local(local)

        kpis = facts["kpis"]
        comp = facts["comparativo_obra"]
        ver = facts["veredito"]

        llm = LLMProvider()
        narrative = llm.narrate_local_mapa_report(facts) if llm.can_use() else None

        if narrative:
            summary = narrative
        else:
            nivel = ver.get("nivel", "atencao")
            summary = (
                f"Local {local.nome} ({local.get_tipo_display()}) na obra {obra.codigo_sienge}. "
                f"Indice de saude operacional: {kpis['saude_score']}/100 (nivel: {nivel}). "
                f"Linhas no mapa: {kpis['total_itens']}; "
                f"{kpis['pendentes']} pendentes; "
                f"alocacao media {kpis['pct_medio_alocacao']:.1f}% "
                f"({kpis['pct_linhas_entregues']:.1f}% das linhas entregues). "
            )
            if comp.get("total_locais_com_itens", 0) > 1:
                summary += (
                    f"Na obra, a media de pendencias por local e {comp['media_pendentes_por_local']:.1f}; "
                    f"este local esta na posicao {comp['posicao_ranking_pendencias']} "
                    f"de {comp['total_locais_com_itens']} (quanto menor, mais pendencias). "
                )
            riscos = ver.get("fatores_risco") or []
            if riscos:
                summary += "Atencao: " + "; ".join(riscos[:4]) + "."
            else:
                summary += "Nenhum alerta critico automatico nos contadores atuais."

        rows = []
        qs_items = (
            ItemMapa.objects.filter(obra=obra, nao_aplica=False, local_aplicacao=local)
            .select_related("insumo")
            .annotate(quantidade_alocada_annotated=Coalesce(Sum("alocacoes__quantidade_alocada"), Value(Decimal("0"))))
            .order_by("-prioridade", "prazo_necessidade")[:12]
        )
        for item in qs_items:
            if (item.status_etapa or "") == "ENTREGUE":
                continue
            desc = (item.insumo.descricao if item.insumo else "")[:80]
            rows.append(
                {
                    "insumo": desc,
                    "status": (item.status_etapa or "")[:40],
                    "aloc_pct": f"{item.percentual_alocado_porcentagem:.0f}%",
                    "atraso": "sim" if item.is_atrasado else "nao",
                }
            )

        cards = [
            {"title": "Saude (0-100)", "value": str(kpis["saude_score"]), "tone": "info"},
            {"title": "Pendentes", "value": str(kpis["pendentes"]), "tone": "warning"},
            {"title": "Atrasados", "value": str(kpis["atrasados"]), "tone": "danger"},
            {"title": "Aloc. media", "value": f"{kpis['pct_medio_alocacao']:.1f}%", "tone": "info"},
        ]

        alerts = []
        if kpis["atrasados"]:
            alerts.append({"level": "error", "message": f"{kpis['atrasados']} linha(s) com indicio de atraso."})
        elif kpis["pendentes"]:
            alerts.append({"level": "warning", "message": f"{kpis['pendentes']} linha(s) ainda nao entregues no local."})

        return AssistantResponse(
            summary=summary,
            cards=cards,
            table={
                "caption": f"Pendencias no local {local.nome} (amostra ate 12 linhas)",
                "columns": ["insumo", "status", "aloc_pct", "atraso"],
                "rows": rows,
            },
            badges=["Mapa de controle", "Por local", obra.codigo_sienge],
            alerts=alerts,
            actions=[{"label": "Abrir mapa filtrado", "url": "/engenharia/mapa/", "style": "primary"}],
            links=[{"label": "Mapa de Suprimentos", "url": "/engenharia/mapa/"}],
            raw_data={"facts": facts, "project_id": project.id, "narrative_llm": bool(narrative)},
        )

