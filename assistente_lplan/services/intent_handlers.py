"""Despacho de intenções → queries → AssistantResponse."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from django.utils import timezone

from assistente_lplan.schemas import AssistantResponse
from assistente_lplan.services import (
    aprovacoes_service,
    cross_domain_service,
    diario_service,
    obras_service,
    suprimentos_service,
)
from assistente_lplan.services.intents import (
    INTENT_FALLBACK,
    INTENT_FRENTES_OBRA,
    INTENT_INTELIGENCIA_INTEGRADA,
    INTENT_LIST_OBRA_PENDING,
    INTENT_LIST_PENDING_APPROVALS,
    INTENT_LOCATE_SUPPLY,
    INTENT_MAPA_CONTROLE_GERAL,
    INTENT_MAPA_GEO,
    INTENT_OBRA_BOTTLENECKS,
    INTENT_OBRA_SUMMARY,
    INTENT_PANORAMA_GERAL,
    INTENT_PEDIDOS_APROVADOR,
    INTENT_PEDIDOS_ATRASADOS,
    INTENT_PESSOA_PERFIL,
    INTENT_RDO_BY_DATE,
    INTENT_RDO_FREQUENCIA,
    INTENT_RELATORIO_LOCAL_MAPA,
    INTENT_RELATORIO_RDO_PERIOD,
    INTENT_REJECTED_REQUESTS,
    INTENT_RESTRICOES_OBRA,
    INTENT_RESTRICOES_RESPONSAVEL,
    INTENT_RH_GERAL,
    INTENT_TRACKHUB_PENDENCIAS,
    INTENT_TRACKHUB_RESPONSAVEL,
    INTENT_UNALLOCATED_ITEMS,
    INTENT_USER_STATUS,
    INTENTS_MODULE_PERMISSION,
    normalize_intent_key,
)
from assistente_lplan.services.permissions import AssistantPermissionService, UserScope
from assistente_lplan.services.queries import (
    mapa_controle_queries,
    mapa_geo_queries,
    pedidos_queries,
    pessoas_queries,
    panorama_queries,
    rdo_queries,
    restricoes_queries,
    rh_queries,
    suprimentos_queries,
    trackhub_queries,
)
from assistente_lplan.services.queries._scope import resolve_project
from assistente_lplan.services.response_builder import from_error, from_query, permission_denied


class IntentHandlers:
    def __init__(self, user, scope: UserScope, perm: AssistantPermissionService):
        self.user = user
        self.scope = scope
        self.perm = perm
        self._legacy = {
            "obras": obras_service.ObrasAssistantService(scope),
            "diario": diario_service.DiarioAssistantService(scope, user=user),
            "suprimentos": suprimentos_service.SuprimentosAssistantService(scope),
            "aprovacoes": aprovacoes_service.AprovacoesAssistantService(user, scope),
            "cross": cross_domain_service.CrossDomainAssistantService(scope),
        }

    def dispatch(self, intent: str, entities: dict, question: str = "") -> AssistantResponse:
        intent = normalize_intent_key(intent)
        mod = INTENTS_MODULE_PERMISSION.get(intent)
        if mod and not self._check_module(mod):
            return permission_denied(mod)

        handlers = {
            INTENT_LOCATE_SUPPLY: self._localizar_insumo,
            INTENT_UNALLOCATED_ITEMS: self._itens_sem_alocacao,
            INTENT_RELATORIO_LOCAL_MAPA: lambda e, q: self._legacy["suprimentos"].relatorio_local_mapa(e, user_question=q),
            INTENT_LIST_PENDING_APPROVALS: self._aprovacoes_pendentes,
            INTENT_REJECTED_REQUESTS: self._reprovados,
            INTENT_PEDIDOS_ATRASADOS: self._pedidos_atrasados,
            INTENT_PEDIDOS_APROVADOR: self._pedidos_aprovador,
            INTENT_RDO_BY_DATE: self._rdo_data,
            INTENT_RELATORIO_RDO_PERIOD: lambda e, q: self._legacy["diario"].relatorio_rdo_periodo_pdf(e, user_question=q),
            INTENT_RDO_FREQUENCIA: self._rdo_frequencia,
            INTENT_LIST_OBRA_PENDING: lambda e, q: self._legacy["obras"].listar_pendencias_obra(e),
            INTENT_OBRA_SUMMARY: lambda e, q: self._legacy["obras"].resumo_obra(e),
            INTENT_OBRA_BOTTLENECKS: lambda e, q: self._legacy["cross"].gargalos_obra(e),
            INTENT_INTELIGENCIA_INTEGRADA: lambda e, q: self._legacy["cross"].inteligencia_integrada(e),
            INTENT_RESTRICOES_OBRA: self._restricoes_obra,
            INTENT_RESTRICOES_RESPONSAVEL: self._restricoes_responsavel,
            INTENT_TRACKHUB_PENDENCIAS: self._trackhub_pendencias,
            INTENT_TRACKHUB_RESPONSAVEL: self._trackhub_responsavel,
            INTENT_MAPA_GEO: self._mapa_geo,
            INTENT_MAPA_CONTROLE_GERAL: self._mapa_controle,
            INTENT_RH_GERAL: self._rh_geral,
            INTENT_PANORAMA_GERAL: self._panorama,
            INTENT_PESSOA_PERFIL: self._pessoa_perfil,
            INTENT_USER_STATUS: self._pessoa_perfil,
            INTENT_FRENTES_OBRA: self._frentes,
        }
        fn = handlers.get(intent)
        if not fn:
            return from_error("intent_nao_suportada", domain=intent)
        return fn(entities, question)

    def _check_module(self, mod: str) -> bool:
        checks = {
            "rh": self.perm.can_view_rh,
            "mapa_geo": self.perm.can_view_mapa_geo,
            "gerencial": self.perm.can_view_gerencial,
            "trackhub": self.perm.can_view_trackhub,
            "restricoes": self.perm.can_view_restricoes,
            "mapa_controle": self.perm.can_view_mapa_controle,
        }
        fn = checks.get(mod)
        return fn() if fn else True

    def _project(self, entities: dict):
        return resolve_project(self.scope, obra=entities.get("obra", ""), project_id=entities.get("project_id"))

    def _localizar_insumo(self, entities, _q=""):
        data = suprimentos_queries.localizar_insumo(
            self.user, self.scope, term=entities.get("insumo", ""), bloco=entities.get("bloco", "")
        )
        return from_query(data, domain="suprimentos", badges=["Suprimentos", "Localizacao"])

    def _itens_sem_alocacao(self, entities, _q=""):
        data = suprimentos_queries.itens_sem_alocacao(
            self.user, self.scope, project=self._project(entities), obra=entities.get("obra", "")
        )
        return from_query(data, domain="suprimentos", badges=["Suprimentos", "Sem alocacao"])

    def _aprovacoes_pendentes(self, entities, _q=""):
        data = pedidos_queries.pedidos_pendentes(
            self.user, self.scope, project=self._project(entities), obra=entities.get("obra", "")
        )
        return from_query(data, domain="aprovacoes", badges=["GestControll", "Pendentes"])

    def _reprovados(self, entities, _q=""):
        data = pedidos_queries.pedidos_reprovados(self.user, self.scope, project=self._project(entities))
        return from_query(data, domain="aprovacoes", badges=["GestControll", "Reprovados"])

    def _pedidos_atrasados(self, entities, _q=""):
        dias = 30
        raw = entities.get("dias")
        if raw:
            try:
                dias = int(raw)
            except (TypeError, ValueError):
                pass
        data = pedidos_queries.pedidos_atrasados(
            self.user, self.scope, dias_limite=max(1, min(dias, 90)), project=self._project(entities), obra=entities.get("obra", "")
        )
        return from_query(
            data,
            domain="aprovacoes",
            badges=["GestControll", "Atrasados"],
            suggested_replies=["Quais aprovacoes estao pendentes?"],
        )

    def _pedidos_aprovador(self, entities, _q=""):
        data = pedidos_queries.pedidos_por_aprovador(self.user, self.scope, usuario_term=entities.get("usuario", ""))
        return from_query(data, domain="aprovacoes", badges=["GestControll", "Aprovador"])

    def _parse_date(self, entities) -> date | None:
        raw = entities.get("data")
        if not raw:
            return None
        try:
            return date.fromisoformat(str(raw)[:10])
        except ValueError:
            return None

    def _rdo_data(self, entities, _q=""):
        target = self._parse_date(entities) or timezone.localdate()
        data = rdo_queries.rdos_por_data(self.user, self.scope, target_date=target, project=self._project(entities))
        return from_query(data, domain="obras", badges=["RDO", "Diario"])

    def _rdo_frequencia(self, entities, _q=""):
        data = rdo_queries.frequencia_rdos(
            self.user, self.scope, project=self._project(entities), obra=entities.get("obra", "")
        )
        if not data.get("ok"):
            data = rdo_queries.obras_sem_rdo(self.user, self.scope)
        return from_query(
            data,
            domain="obras",
            badges=["RDO", "Frequencia"],
            suggested_replies=["RDO do dia de hoje", "PDF dos ultimos 15 dias de RDO"],
        )

    def _restricoes_obra(self, entities, _q=""):
        data = restricoes_queries.restricoes_obra(
            self.user, self.scope, obra=entities.get("obra", ""), project=self._project(entities)
        )
        return from_query(data, domain="restricoes", badges=["Restricoes", "Impedimentos"])

    def _restricoes_responsavel(self, entities, _q=""):
        limit = not self.perm.can_view_gerencial()
        data = restricoes_queries.restricoes_por_responsavel(
            self.user,
            self.scope,
            responsavel_nome=entities.get("usuario", ""),
            limit_self=limit,
        )
        return from_query(data, domain="restricoes", badges=["Restricoes", "Responsaveis"])

    def _trackhub_pendencias(self, entities, _q=""):
        data = trackhub_queries.pendencias_obra(self.user, self.scope, obra_nome=entities.get("obra", ""))
        return from_query(data, domain="trackhub", badges=["TrackHub", "Pendencias"])

    def _trackhub_responsavel(self, entities, _q=""):
        limit = not self.perm.can_view_gerencial()
        data = trackhub_queries.pendencias_por_responsavel(
            self.user, self.scope, responsavel_nome=entities.get("usuario", ""), limit_self=limit
        )
        return from_query(data, domain="trackhub", badges=["TrackHub", "Responsaveis"])

    def _mapa_geo(self, entities, _q=""):
        proj = self._project(entities)
        if proj:
            data = mapa_geo_queries.elementos_obra(self.user, self.scope, project=proj)
        else:
            data = mapa_geo_queries.panorama_mapa_geo(self.user, self.scope)
        return from_query(data, domain="mapa_geo", badges=["Mapa Geografico"])

    def _mapa_controle(self, entities, _q=""):
        data = mapa_controle_queries.execucao_fisica_obra(
            self.user, self.scope, project=self._project(entities), obra=entities.get("obra", "")
        )
        return from_query(data, domain="mapa_controle", badges=["Mapa de Controle", "Execucao fisica"])

    def _rh_geral(self, entities, _q=""):
        qlower = (_q or "").lower()
        if "admiss" in qlower:
            data = rh_queries.admissoes_andamento(self.user, self.scope)
        elif "document" in qlower or "venc" in qlower:
            data = rh_queries.documentos_vencendo(self.user, self.scope)
        else:
            data = rh_queries.resumo_rh(self.user, self.scope)
        return from_query(data, domain="rh", badges=["RH", "DP"])

    def _panorama(self, entities, _q=""):
        data = panorama_queries.situacao_geral(self.user, self.scope, self.perm)
        rows = data.get("obras_criticas") or []
        resp = from_query(
            {**data, "rows": rows, "summary": data.get("summary_hint")},
            domain="panorama",
            badges=["Panorama", "Multi-obra"],
            suggested_replies=[
                "Qual obra esta mais critica hoje?",
                "Pedidos parados ha mais de 30 dias",
                "Pendencias TrackHub atrasadas",
            ],
        )
        return resp

    def _pessoa_perfil(self, entities, _q=""):
        data = pessoas_queries.perfil_usuario(
            self.user, self.scope, self.perm, usuario_term=entities.get("usuario", "")
        )
        return from_query(data, domain="usuarios", badges=["Usuario", "Perfil"])

    def _frentes(self, entities, _q=""):
        data = rdo_queries.frentes_obra(
            self.user, self.scope, project=self._project(entities), obra=entities.get("obra", "")
        )
        return from_query(data, domain="obras", badges=["Frentes", "Subobra"])
