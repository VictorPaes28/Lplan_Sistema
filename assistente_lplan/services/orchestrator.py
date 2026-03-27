import logging

from assistente_lplan.schemas import AssistantResponse

from .aprovacoes_service import AprovacoesAssistantService
from .cross_domain_service import CrossDomainAssistantService
from .diario_service import DiarioAssistantService
from .intents import (
    INTENT_FALLBACK,
    INTENT_LIST_OBRA_PENDING,
    INTENT_LIST_PENDING_APPROVALS,
    INTENT_LOCATE_SUPPLY,
    INTENT_OBRA_BOTTLENECKS,
    INTENT_OBRA_SUMMARY,
    INTENT_REJECTED_REQUESTS,
    INTENT_UNALLOCATED_ITEMS,
    INTENT_USER_STATUS,
)
from .llm_provider import LLMProvider
from .obras_service import ObrasAssistantService
from .parser import RuleBasedIntentParser
from .permissions import AssistantPermissionService
from .suprimentos_service import SuprimentosAssistantService
from .usuarios_service import UsuariosAssistantService
from .messages import MessageCatalog

logger = logging.getLogger(__name__)


class AssistantOrchestrator:
    """Orquestra intenção, escopo e resposta estruturada."""

    def __init__(self, user):
        self.user = user
        self.llm_provider = LLMProvider()
        self.fallback_parser = RuleBasedIntentParser()
        self.permission_service = AssistantPermissionService(user)
        self.scope = self.permission_service.build_scope()

        self.suprimentos = SuprimentosAssistantService(self.scope)
        self.aprovacoes = AprovacoesAssistantService(user, self.scope)
        self.diario = DiarioAssistantService(self.scope)
        self.obras = ObrasAssistantService(self.scope)
        self.usuarios = UsuariosAssistantService(user, self.scope, self.permission_service)
        self.cross = CrossDomainAssistantService(self.scope)

    def handle(self, question: str, context: dict | None = None) -> tuple[AssistantResponse, dict]:
        context = context or {}
        intent, entities, used_llm, confidence, candidates, reason = self._detect_intent(question)
        selected_project_id = context.get("selected_project_id")
        if selected_project_id and not entities.get("obra"):
            entities["project_id"] = selected_project_id
        domain = self._domain_for_intent(intent)

        if intent == INTENT_FALLBACK:
            response = self._clarification_response(candidates=candidates, reason=reason)
            response = self._ensure_actionability(response, domain=domain)
            response = self._apply_primary_action_highlight(response=response, intent=intent, domain=domain)
            response.raw_data.update(
                {
                    "intent": intent,
                    "entities": entities,
                    "domain": domain,
                    "role": self.scope.role,
                    "used_llm": used_llm,
                    "confidence": confidence,
                    "reason": reason,
                }
            )
            meta = {
                "intent": intent,
                "entities": entities,
                "domain": domain,
                "used_llm": used_llm,
                "context": context,
                "confidence": confidence,
                "reason": reason,
            }
            return response, meta

        response = self._dispatch(intent, entities)
        response = self._ensure_actionability(response, domain=domain)
        response = self._apply_primary_action_highlight(response=response, intent=intent, domain=domain)
        if response.summary:
            response.summary = self.llm_provider.improve_summary(response.summary, domain=domain)
        response.raw_data.update(
            {
                "intent": intent,
                "entities": entities,
                "domain": domain,
                "role": self.scope.role,
                "used_llm": used_llm,
                "confidence": confidence,
                "reason": reason,
            }
        )
        meta = {
            "intent": intent,
            "entities": entities,
            "domain": domain,
            "used_llm": used_llm,
            "context": context,
            "confidence": confidence,
            "reason": reason,
        }
        return response, meta

    def _detect_intent(self, question: str) -> tuple[str, dict, bool, float, list, str]:
        llm_result = self.llm_provider.detect_intent(question)
        if llm_result:
            intent, entities, confidence = llm_result
            if confidence >= 0.6:
                return intent, entities, True, confidence, [(intent, confidence)], "llm_match"
            parse = self.fallback_parser.parse(question)
            return (
                parse.intent,
                parse.entities,
                False,
                parse.confidence,
                parse.candidates,
                "llm_baixa_confianca_fallback_regra",
            )
        parse = self.fallback_parser.parse(question)
        return parse.intent, parse.entities, False, parse.confidence, parse.candidates, parse.reason

    def _dispatch(self, intent: str, entities: dict) -> AssistantResponse:
        if intent == INTENT_LOCATE_SUPPLY:
            return self.suprimentos.localizar_insumo(entities)
        if intent == INTENT_LIST_OBRA_PENDING:
            return self.obras.listar_pendencias_obra(entities)
        if intent == INTENT_LIST_PENDING_APPROVALS:
            return self.aprovacoes.listar_aprovacoes_pendentes(entities)
        if intent == INTENT_OBRA_SUMMARY:
            return self.obras.resumo_obra(entities)
        if intent == INTENT_USER_STATUS:
            return self.usuarios.status_usuario(entities)
        if intent == INTENT_UNALLOCATED_ITEMS:
            return self.suprimentos.itens_sem_alocacao(entities)
        if intent == INTENT_REJECTED_REQUESTS:
            return self.aprovacoes.solicitacoes_reprovadas(entities)
        if intent == INTENT_OBRA_BOTTLENECKS:
            return self.cross.gargalos_obra(entities)
        if intent == INTENT_FALLBACK:
            fallback_summary = MessageCatalog.resolve(
                "assistant.intent.ambiguous_summary",
                {"domain": "fallback", "intent": INTENT_FALLBACK},
            )
            fallback_alert = MessageCatalog.resolve(
                "assistant.intent.ambiguous_alert",
                {"domain": "fallback", "intent": INTENT_FALLBACK},
            )
            return AssistantResponse(
                summary=fallback_summary["text"],
                badges=["Fallback", "Assistente LPLAN"],
                alerts=[{"level": "info", "message": fallback_alert["text"]}],
                raw_data={
                    "message_code": fallback_summary["code"],
                    "message_kind": fallback_summary["kind"],
                    "next_steps": fallback_summary["next_steps"],
                },
            )
        logger.warning("Intent não suportada recebida: %s", intent)
        unsupported = MessageCatalog.resolve("assistant.intent.unsupported", {"domain": "unknown", "intent": intent})
        return AssistantResponse(
            summary=unsupported["text"],
            badges=["Nao suportado"],
            alerts=[{"level": "info", "message": step} for step in unsupported["next_steps"][:1]],
            raw_data={"message_code": unsupported["code"], "message_kind": unsupported["kind"]},
        )

    @staticmethod
    def _clarification_response(candidates: list | None = None, reason: str = "") -> AssistantResponse:
        sugestoes = []
        if candidates:
            sugestoes = [f"{intent} ({score:.2f})" for intent, score in candidates[:3]]
        summary_msg = MessageCatalog.resolve("assistant.intent.ambiguous_summary", {"domain": "fallback"})
        alert_msg = MessageCatalog.resolve("assistant.intent.ambiguous_alert", {"domain": "fallback"})
        return AssistantResponse(
            summary=summary_msg["text"],
            badges=["Interpretacao ambigua"],
            alerts=[
                {
                    "level": "warning",
                    "message": alert_msg["text"],
                }
            ],
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
                "candidates": sugestoes,
                "reason": reason,
                "message_code": summary_msg["code"],
                "message_kind": summary_msg["kind"],
                "next_steps": summary_msg["next_steps"],
            },
        )

    @staticmethod
    def _domain_for_intent(intent: str) -> str:
        mapping = {
            INTENT_LOCATE_SUPPLY: "suprimentos",
            INTENT_UNALLOCATED_ITEMS: "suprimentos",
            INTENT_LIST_PENDING_APPROVALS: "aprovacoes",
            INTENT_REJECTED_REQUESTS: "aprovacoes",
            INTENT_LIST_OBRA_PENDING: "obras",
            INTENT_OBRA_SUMMARY: "obras",
            INTENT_USER_STATUS: "usuarios",
            INTENT_OBRA_BOTTLENECKS: "cross_domain",
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
            "cross_domain": {
                "actions": [{"label": "Abrir Relatorios", "url": "/reports/", "style": "primary"}],
                "links": [
                    {"label": "Diario - Relatorios", "url": "/reports/"},
                    {"label": "GestControll - Pedidos", "url": "/gestao/pedidos/"},
                    {"label": "Mapa de Suprimentos", "url": "/engenharia/mapa/"},
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
        if not response.actions:
            return response

        for action in response.actions:
            action["style"] = "secondary"
            action["is_primary"] = False

        labels = [(idx, (a.get("label", "") + " " + a.get("url", "")).lower()) for idx, a in enumerate(response.actions)]
        alerts = response.alerts or []
        has_error_alert = any((a.get("level") == "error") for a in alerts)
        has_warning_alert = any((a.get("level") == "warning") for a in alerts)

        def find_idx(*tokens: str):
            for idx, text in labels:
                if all(t in text for t in tokens):
                    return idx
            for idx, text in labels:
                if any(t in text for t in tokens):
                    return idx
            return None

        card_values: dict[str, int] = {}
        for card in response.cards or []:
            title = str(card.get("title", "")).lower()
            raw_val = str(card.get("value", "0"))
            digits = "".join(ch for ch in raw_val if ch.isdigit())
            card_values[title] = int(digits) if digits else 0

        chosen_idx = 0
        if domain == "cross_domain":
            itens_risco = max((v for k, v in card_values.items() if "item" in k), default=0)
            aprov_risco = max((v for k, v in card_values.items() if "aprova" in k), default=0)
            diario_risco = max((v for k, v in card_values.items() if "diario" in k), default=0)
            if itens_risco > 0:
                chosen_idx = find_idx("mapa") or find_idx("suprimento") or 0
            elif aprov_risco > 0:
                chosen_idx = find_idx("pedido") or find_idx("aprova") or 0
            elif diario_risco > 0:
                chosen_idx = find_idx("relatorio") or find_idx("pedido") or 0
        elif intent in (INTENT_LOCATE_SUPPLY, INTENT_UNALLOCATED_ITEMS) or domain == "suprimentos":
            chosen_idx = find_idx("mapa") or find_idx("aloca") or 0
        elif intent in (INTENT_LIST_PENDING_APPROVALS, INTENT_REJECTED_REQUESTS) or domain == "aprovacoes":
            chosen_idx = find_idx("pedido") or find_idx("aprova") or 0
        elif intent in (INTENT_LIST_OBRA_PENDING, INTENT_OBRA_SUMMARY) or domain == "obras":
            if has_warning_alert or has_error_alert:
                chosen_idx = find_idx("relatorio") or find_idx("pedido") or 0
            else:
                chosen_idx = find_idx("relatorio") or 0
        elif intent == INTENT_USER_STATUS or domain == "usuarios":
            chosen_idx = find_idx("desempenho") or 0
        elif domain == "fallback":
            if has_error_alert:
                chosen_idx = find_idx("pedido") or find_idx("mapa") or 0
            elif has_warning_alert:
                chosen_idx = find_idx("relatorio") or 0
            else:
                chosen_idx = 0

        if chosen_idx is None:
            chosen_idx = 0

        response.actions[chosen_idx]["style"] = "primary"
        response.actions[chosen_idx]["is_primary"] = True
        return response

