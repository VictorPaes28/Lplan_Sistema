import logging
import re
import unicodedata
from difflib import SequenceMatcher

from assistente_lplan.schemas import AssistantResponse

from .clarification import (
    INTENTS_REQUIRING_OBRA_CHOICE,
    _has_obra_pointer,
    _has_usuario,
    accessible_projects_for_scope,
    build_obra_clarification_response,
    build_usuario_clarification_response,
    inject_single_project_if_unique,
    sample_users_for_clarification,
)
from .intent_handlers import IntentHandlers
from .intents import (
    INTENT_FALLBACK,
    INTENT_INTELIGENCIA_INTEGRADA,
    INTENT_LIST_OBRA_PENDING,
    INTENT_OBRA_BOTTLENECKS,
    INTENT_OBRA_SUMMARY,
    INTENT_PESSOA_PERFIL,
    INTENT_RELATORIO_LOCAL_MAPA,
    INTENT_RELATORIO_RDO_PERIOD,
    INTENT_USER_STATUS,
    normalize_intent_key,
)
from .messages import MessageCatalog
from .parser import RuleBasedIntentParser, normalize_intent_question
from .permissions import AssistantPermissionService

logger = logging.getLogger(__name__)


class AssistantOrchestrator:
    """Orquestra intenção (parser de regras), escopo e resposta estruturada."""

    def __init__(self, user):
        self.user = user
        self.fallback_parser = RuleBasedIntentParser()
        self.permission_service = AssistantPermissionService(user)
        self.scope = self.permission_service.build_scope()
        self.handlers = IntentHandlers(user, self.scope, self.permission_service)

    def handle(self, question: str, context: dict | None = None) -> tuple[AssistantResponse, dict]:
        context = context or {}
        intent, entities, confidence, candidates, reason = self._detect_intent(question)
        entities = dict(entities or {})

        selected_project_id = context.get("selected_project_id")
        if selected_project_id and not (entities.get("obra") or "").strip():
            entities["project_id"] = selected_project_id

        entities = inject_single_project_if_unique(entities, self.scope)
        intent = normalize_intent_key(intent)

        if intent in (INTENT_USER_STATUS, INTENT_PESSOA_PERFIL) and not _has_usuario(entities):
            samples = sample_users_for_clarification(self.permission_service, self.scope, limit=12)
            if len(samples) > 1:
                response = build_usuario_clarification_response(intent=intent, sample_users=samples)
                response = self._ensure_actionability(response, domain="clarification")
                response = self._apply_primary_action_highlight(response=response, intent=intent, domain="clarification")
                response.raw_data.update(
                    {
                        "intent": intent,
                        "entities": entities,
                        "domain": "clarification",
                        "role": self.scope.role,
                        "used_llm": False,
                        "confidence": confidence,
                        "reason": "precisa_usuario",
                    }
                )
                return response, self._meta(intent, entities, "clarification", context, confidence, "precisa_usuario")

        if intent in INTENTS_REQUIRING_OBRA_CHOICE and not _has_obra_pointer(entities):
            projects = accessible_projects_for_scope(self.scope)
            if not projects:
                response = self._sem_projeto_response(intent, entities, confidence, reason)
                return response, self._meta(intent, entities, "clarification", context, confidence, "sem_obra_escopo")
            if len(projects) > 1:
                response = build_obra_clarification_response(
                    intent=intent,
                    user_question=question,
                    scope=self.scope,
                    projects=projects,
                )
                response = self._ensure_actionability(response, domain="clarification")
                response = self._apply_primary_action_highlight(response=response, intent=intent, domain="clarification")
                response.raw_data.update(
                    {
                        "intent": intent,
                        "entities": entities,
                        "domain": "clarification",
                        "role": self.scope.role,
                        "used_llm": False,
                        "confidence": confidence,
                        "reason": "precisa_obra",
                    }
                )
                return response, self._meta(intent, entities, "clarification", context, confidence, "precisa_obra")

        domain = self._domain_for_intent(intent)

        if intent == INTENT_FALLBACK:
            response = self._clarification_response(question=question, candidates=candidates, reason=reason)
            response = self._ensure_actionability(response, domain=domain)
            response = self._apply_primary_action_highlight(response=response, intent=intent, domain=domain)
            response.raw_data.update(
                {
                    "intent": intent,
                    "entities": entities,
                    "domain": domain,
                    "role": self.scope.role,
                    "used_llm": False,
                    "confidence": confidence,
                    "reason": reason,
                }
            )
            return response, self._meta(intent, entities, domain, context, confidence, reason)

        response = self.handlers.dispatch(intent, entities, question=question)
        response = self._ensure_actionability(response, domain=domain)
        response = self._apply_primary_action_highlight(response=response, intent=intent, domain=domain)
        response.raw_data.update(
            {
                "intent": intent,
                "entities": entities,
                "domain": domain,
                "role": self.scope.role,
                "used_llm": False,
                "confidence": confidence,
                "reason": reason,
            }
        )
        return response, self._meta(intent, entities, domain, context, confidence, reason)

    def _detect_intent(self, question: str) -> tuple[str, dict, float, list, str]:
        parse = self.fallback_parser.parse(normalize_intent_question(question) or question)
        return parse.intent, parse.entities, parse.confidence, parse.candidates, parse.reason

    @staticmethod
    def _meta(intent, entities, domain, context, confidence, reason):
        return {
            "intent": intent,
            "entities": entities,
            "domain": domain,
            "used_llm": False,
            "context": context,
            "confidence": confidence,
            "reason": reason,
        }

    def _sem_projeto_response(self, intent, entities, confidence, reason):
        response = AssistantResponse(
            summary=(
                "Nao ha obra de projeto vinculada ao seu usuario. No Lplan, Diario, Mapa e GestControll "
                "usam a mesma obra (codigo de projeto). Peca ao gestor o vinculo ao projeto ou use Selecionar obra."
            ),
            badges=["Sem obra no escopo"],
            alerts=[{"level": "warning", "message": "Sem projeto associado nao da para cruzar os modulos."}],
            actions=[{"label": "Selecionar obra", "url": "/select-project/", "style": "primary"}],
            links=[
                {"label": "Relatorios do diario", "url": "/reports/"},
                {"label": "Selecionar obra", "url": "/select-project/"},
            ],
            raw_data={"clarification": "sem_projeto"},
        )
        response = self._ensure_actionability(response, domain="clarification")
        response = self._apply_primary_action_highlight(response=response, intent=intent, domain="clarification")
        response.raw_data.update(
            {
                "intent": intent,
                "entities": entities,
                "domain": "clarification",
                "role": self.scope.role,
                "used_llm": False,
                "confidence": confidence,
                "reason": reason,
            }
        )
        return response

    @classmethod
    def _clarification_response(cls, question: str = "", candidates: list | None = None, reason: str = "") -> AssistantResponse:
        suggested_questions = cls._suggest_similar_questions(question=question, candidates=candidates, limit=3)
        summary_msg = MessageCatalog.resolve("assistant.intent.ambiguous_summary", {"domain": "fallback"})
        alert_msg = MessageCatalog.resolve("assistant.intent.ambiguous_alert", {"domain": "fallback"})
        summary_text = summary_msg["text"]
        alerts = [{"level": "warning", "message": alert_msg["text"]}]
        if suggested_questions:
            summary_text = f"{summary_text} Talvez voce quis dizer: {suggested_questions[0]}"
            alerts.append({"level": "info", "message": f"Pergunta semelhante: {suggested_questions[0]}"})
        return AssistantResponse(
            summary=summary_text,
            badges=["Interpretacao ambigua"],
            alerts=alerts,
            suggested_replies=suggested_questions,
            actions=[
                {"label": "Abrir pendencias de aprovacao", "url": "/gestao/pedidos/", "style": "secondary"},
                {"label": "Abrir mapa de suprimentos", "url": "/engenharia/mapa/", "style": "secondary"},
                {"label": "Abrir relatorios da obra", "url": "/reports/", "style": "secondary"},
            ],
            links=[
                {"label": "GestControll - Pedidos", "url": "/gestao/pedidos/"},
                {"label": "Mapa de Suprimentos", "url": "/engenharia/mapa/"},
                {"label": "Diario - Relatorios", "url": "/reports/"},
            ],
            raw_data={
                "reason": reason,
                "suggested_questions": suggested_questions,
                "message_code": summary_msg["code"],
            },
        )

    @classmethod
    def _suggest_similar_questions(cls, question: str, candidates: list | None = None, limit: int = 3) -> list[str]:
        pools = cls._intent_example_questions()
        ordered_intents = [intent for intent, _score in (candidates or [])]
        candidate_questions: list[str] = []
        for intent in ordered_intents:
            candidate_questions.extend(pools.get(intent, []))
        if not candidate_questions:
            for values in pools.values():
                candidate_questions.extend(values)
        question_norm = cls._normalize_similarity_text(question)
        scored: list[tuple[str, float]] = []
        for phrase in candidate_questions:
            phrase_norm = cls._normalize_similarity_text(phrase)
            ratio = SequenceMatcher(None, question_norm, phrase_norm).ratio() if (question_norm and phrase_norm) else 0.0
            scored.append((phrase, ratio))
        scored.sort(key=lambda item: item[1], reverse=True)
        unique: list[str] = []
        seen = set()
        for phrase, _score in scored:
            key = phrase.strip().lower()
            if not key or key in seen:
                continue
            unique.append(phrase)
            seen.add(key)
            if len(unique) >= max(1, limit):
                break
        return unique

    @staticmethod
    def _intent_example_questions() -> dict[str, list[str]]:
        from .intents import (
            INTENT_MAPA_GEO,
            INTENT_PANORAMA_GERAL,
            INTENT_PEDIDOS_ATRASADOS,
            INTENT_RDO_FREQUENCIA,
            INTENT_RESTRICOES_RESPONSAVEL,
            INTENT_RH_GERAL,
            INTENT_TRACKHUB_PENDENCIAS,
            INTENT_LOCATE_SUPPLY,
            INTENT_UNALLOCATED_ITEMS,
            INTENT_LIST_PENDING_APPROVALS,
            INTENT_RDO_BY_DATE,
            INTENT_REJECTED_REQUESTS,
            INTENT_LIST_OBRA_PENDING,
            INTENT_OBRA_SUMMARY,
            INTENT_OBRA_BOTTLENECKS,
            INTENT_INTELIGENCIA_INTEGRADA,
            INTENT_RELATORIO_LOCAL_MAPA,
            INTENT_RELATORIO_RDO_PERIOD,
            INTENT_PESSOA_PERFIL,
        )

        return {
            INTENT_PANORAMA_GERAL: ["Qual obra esta mais critica hoje?", "Situacao geral das obras"],
            INTENT_RDO_FREQUENCIA: ["Quais obras estao sem RDO esta semana?", "Obras que nunca tiveram RDO"],
            INTENT_PEDIDOS_ATRASADOS: ["Quais pedidos estao parados ha mais de 30 dias?"],
            INTENT_RESTRICOES_RESPONSAVEL: ["Quem tem mais restricoes vencidas?"],
            INTENT_TRACKHUB_PENDENCIAS: ["Quantas pendencias TrackHub estao atrasadas?"],
            INTENT_RH_GERAL: ["Tem colaborador com documento vencendo?"],
            INTENT_MAPA_GEO: ["Quais obras tem elementos no mapa geografico?"],
            INTENT_LOCATE_SUPPLY: ["Onde esta o cimento do bloco C?"],
            INTENT_UNALLOCATED_ITEMS: ["Quais itens estao sem alocacao?"],
            INTENT_LIST_PENDING_APPROVALS: ["Quais aprovacoes estao pendentes?"],
            INTENT_RDO_BY_DATE: ["RDO de ontem da obra"],
            INTENT_REJECTED_REQUESTS: ["Solicitacoes reprovadas recentemente"],
            INTENT_LIST_OBRA_PENDING: ["Quais pendencias da obra?"],
            INTENT_OBRA_SUMMARY: ["Resumo operacional da obra atual"],
            INTENT_OBRA_BOTTLENECKS: ["Gargalos na obra selecionada"],
            INTENT_INTELIGENCIA_INTEGRADA: ["Visao integrada da obra atual"],
            INTENT_RELATORIO_LOCAL_MAPA: ["Como esta o apartamento 302 no mapa de controle?"],
            INTENT_RELATORIO_RDO_PERIOD: ["PDF dos ultimos 15 dias de RDO"],
            INTENT_PESSOA_PERFIL: ["Como esta o Joao nos ultimos 30 dias?"],
        }

    @staticmethod
    def _normalize_similarity_text(value: str) -> str:
        text = (value or "").lower().strip()
        text = unicodedata.normalize("NFD", text)
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        text = re.sub(r"[^a-z0-9 ]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _domain_for_intent(intent: str) -> str:
        from .intents import (
            INTENT_FRENTES_OBRA,
            INTENT_MAPA_CONTROLE_GERAL,
            INTENT_MAPA_GEO,
            INTENT_PANORAMA_GERAL,
            INTENT_PEDIDOS_APROVADOR,
            INTENT_PEDIDOS_ATRASADOS,
            INTENT_RDO_FREQUENCIA,
            INTENT_RESTRICOES_OBRA,
            INTENT_RESTRICOES_RESPONSAVEL,
            INTENT_RH_GERAL,
            INTENT_TRACKHUB_PENDENCIAS,
            INTENT_TRACKHUB_RESPONSAVEL,
            INTENT_LOCATE_SUPPLY,
            INTENT_UNALLOCATED_ITEMS,
            INTENT_LIST_PENDING_APPROVALS,
            INTENT_REJECTED_REQUESTS,
            INTENT_LIST_OBRA_PENDING,
            INTENT_RDO_BY_DATE,
            INTENT_OBRA_SUMMARY,
            INTENT_OBRA_BOTTLENECKS,
            INTENT_INTELIGENCIA_INTEGRADA,
            INTENT_RELATORIO_LOCAL_MAPA,
            INTENT_RELATORIO_RDO_PERIOD,
            INTENT_FALLBACK,
        )

        mapping = {
            INTENT_LOCATE_SUPPLY: "suprimentos",
            INTENT_UNALLOCATED_ITEMS: "suprimentos",
            INTENT_RELATORIO_LOCAL_MAPA: "suprimentos",
            INTENT_LIST_PENDING_APPROVALS: "aprovacoes",
            INTENT_REJECTED_REQUESTS: "aprovacoes",
            INTENT_PEDIDOS_ATRASADOS: "aprovacoes",
            INTENT_PEDIDOS_APROVADOR: "aprovacoes",
            INTENT_LIST_OBRA_PENDING: "obras",
            INTENT_RDO_BY_DATE: "obras",
            INTENT_RDO_FREQUENCIA: "obras",
            INTENT_FRENTES_OBRA: "obras",
            INTENT_OBRA_SUMMARY: "obras",
            INTENT_PESSOA_PERFIL: "usuarios",
            INTENT_USER_STATUS: "usuarios",
            INTENT_OBRA_BOTTLENECKS: "cross_domain",
            INTENT_INTELIGENCIA_INTEGRADA: "inteligencia",
            INTENT_RELATORIO_RDO_PERIOD: "obras",
            INTENT_RESTRICOES_OBRA: "restricoes",
            INTENT_RESTRICOES_RESPONSAVEL: "restricoes",
            INTENT_TRACKHUB_PENDENCIAS: "trackhub",
            INTENT_TRACKHUB_RESPONSAVEL: "trackhub",
            INTENT_MAPA_GEO: "mapa_geo",
            INTENT_MAPA_CONTROLE_GERAL: "mapa_controle",
            INTENT_RH_GERAL: "rh",
            INTENT_PANORAMA_GERAL: "panorama",
            INTENT_FALLBACK: "fallback",
        }
        return mapping.get(intent, "unknown")

    @staticmethod
    def _ensure_actionability(response: AssistantResponse, domain: str) -> AssistantResponse:
        domain_defaults = {
            "suprimentos": {
                "actions": [{"label": "Abrir Mapa de Suprimentos", "url": "/engenharia/mapa/", "style": "primary"}],
                "links": [{"label": "Mapa de Suprimentos", "url": "/engenharia/mapa/"}],
            },
            "aprovacoes": {
                "actions": [{"label": "Abrir Pedidos", "url": "/gestao/pedidos/", "style": "primary"}],
                "links": [{"label": "GestControll - Pedidos", "url": "/gestao/pedidos/"}],
            },
            "obras": {
                "actions": [{"label": "Abrir Relatorios da Obra", "url": "/reports/", "style": "primary"}],
                "links": [{"label": "Diario - Relatorios", "url": "/reports/"}],
            },
            "usuarios": {
                "actions": [{"label": "Abrir Desempenho", "url": "/gestao/desempenho-equipe/", "style": "primary"}],
                "links": [{"label": "GestControll - Desempenho", "url": "/gestao/desempenho-equipe/"}],
            },
            "restricoes": {
                "actions": [{"label": "Abrir Restricoes", "url": "/impedimentos/", "style": "primary"}],
                "links": [{"label": "Gestao de Impedimentos", "url": "/impedimentos/"}],
            },
            "trackhub": {
                "actions": [{"label": "Abrir TrackHub", "url": "/trackhub/", "style": "primary"}],
                "links": [{"label": "TrackHub", "url": "/trackhub/"}],
            },
            "mapa_geo": {
                "actions": [{"label": "Abrir Mapa Geografico", "url": "/mapa-geo/", "style": "primary"}],
                "links": [{"label": "Mapa Geografico", "url": "/mapa-geo/"}],
            },
            "rh": {
                "actions": [{"label": "Abrir RH", "url": "/rh/colaboradores/", "style": "primary"}],
                "links": [{"label": "Recursos Humanos", "url": "/rh/colaboradores/"}],
            },
            "panorama": {
                "actions": [{"label": "Abrir Relatorios", "url": "/reports/", "style": "primary"}],
                "links": [{"label": "Diario - Relatorios", "url": "/reports/"}],
            },
            "cross_domain": {
                "actions": [{"label": "Abrir Relatorios", "url": "/reports/", "style": "primary"}],
                "links": [
                    {"label": "Diario - Relatorios", "url": "/reports/"},
                    {"label": "GestControll - Pedidos", "url": "/gestao/pedidos/"},
                    {"label": "Mapa de Suprimentos", "url": "/engenharia/mapa/"},
                ],
            },
            "inteligencia": {
                "actions": [{"label": "Abrir Relatorios", "url": "/reports/", "style": "primary"}],
                "links": [
                    {"label": "Diario - Relatorios", "url": "/reports/"},
                    {"label": "GestControll - Pedidos", "url": "/gestao/pedidos/"},
                    {"label": "Mapa de Suprimentos", "url": "/engenharia/mapa/"},
                ],
            },
            "clarification": {
                "actions": [],
                "links": [
                    {"label": "Relatorios (definir obra)", "url": "/reports/"},
                    {"label": "Selecionar obra", "url": "/select-project/"},
                ],
            },
            "fallback": {
                "actions": [{"label": "Abrir Assistente", "url": "/assistente/", "style": "primary"}],
                "links": [{"label": "Assistente LPLAN", "url": "/assistente/"}],
            },
        }
        defaults = domain_defaults.get(domain, domain_defaults["fallback"])
        if not response.actions:
            response.actions = defaults["actions"]
        if not response.links:
            response.links = defaults["links"]
        return response

    @staticmethod
    def _apply_primary_action_highlight(response: AssistantResponse, intent: str, domain: str) -> AssistantResponse:
        if domain == "clarification" or not response.actions:
            return response
        for action in response.actions:
            action["style"] = "secondary"
        response.actions[0]["style"] = "primary"
        return response
