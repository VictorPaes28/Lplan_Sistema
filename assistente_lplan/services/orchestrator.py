import logging
import re
import unicodedata
from difflib import SequenceMatcher

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
    INTENT_RDO_BY_DATE,
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
            response = self._clarification_response(question=question, candidates=candidates, reason=reason)
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
        if intent == INTENT_RDO_BY_DATE:
            return self.diario.consultar_rdo_por_data(entities)
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

    @classmethod
    def _clarification_response(cls, question: str = "", candidates: list | None = None, reason: str = "") -> AssistantResponse:
        sugestoes = []
        if candidates:
            sugestoes = [f"{intent} ({score:.2f})" for intent, score in candidates[:3]]
        suggested_questions = cls._suggest_similar_questions(question=question, candidates=candidates, limit=3)
        summary_msg = MessageCatalog.resolve("assistant.intent.ambiguous_summary", {"domain": "fallback"})
        alert_msg = MessageCatalog.resolve("assistant.intent.ambiguous_alert", {"domain": "fallback"})
        summary_text = summary_msg["text"]
        alerts = [
            {
                "level": "warning",
                "message": alert_msg["text"],
            }
        ]
        if suggested_questions:
            summary_text = f"{summary_text} Talvez voce quis dizer: {suggested_questions[0]}"
            alerts.append({"level": "info", "message": f"Pergunta semelhante: {suggested_questions[0]}"})
            if len(suggested_questions) > 1:
                alerts.append({"level": "info", "message": "Outras sugestoes: " + " | ".join(suggested_questions[1:])})
        return AssistantResponse(
            summary=summary_text,
            badges=["Interpretacao ambigua"],
            alerts=alerts,
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
                "suggested_questions": suggested_questions,
                "message_code": summary_msg["code"],
                "message_kind": summary_msg["kind"],
                "next_steps": summary_msg["next_steps"],
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
        return {
            INTENT_LOCATE_SUPPLY: [
                "Onde esta o cimento do bloco C?",
                "Localizar insumo vergalhao na obra X",
                "Onde esta o insumo areia fina na obra Y?",
            ],
            INTENT_UNALLOCATED_ITEMS: [
                "Quais itens dessa obra estao sem alocacao?",
                "Liste os itens nao alocados da obra X",
                "Itens sem alocacao com prioridade alta na obra Y",
            ],
            INTENT_LIST_PENDING_APPROVALS: [
                "Quais aprovacoes estao pendentes?",
                "Liste as aprovacoes pendentes da obra X",
                "Pedidos pendentes por solicitante Joao",
            ],
            INTENT_RDO_BY_DATE: [
                "Quero o RDO do dia 15/03/2026",
                "Mostre o diario da obra ALFA em 2026-03-15",
                "RDO de ontem da obra X",
            ],
            INTENT_REJECTED_REQUESTS: [
                "Tudo que ja foi reprovado",
                "Quais solicitacoes foram reprovadas na obra X?",
                "Reprovados por aprovador Stan nos ultimos 30 dias",
            ],
            INTENT_LIST_OBRA_PENDING: [
                "Quais pendencias da obra X?",
                "O que falta na obra atual?",
                "Pendencias operacionais da obra Y",
            ],
            INTENT_OBRA_SUMMARY: [
                "Resuma a situacao da obra atual",
                "Resumo operacional da obra X",
                "Como esta a obra Y hoje?",
            ],
            INTENT_USER_STATUS: [
                "Como Joao esta nos ultimos 30 dias?",
                "Status do usuario Stan nos ultimos 30 dias",
                "Desempenho do usuario Maria",
            ],
            INTENT_OBRA_BOTTLENECKS: [
                "Quais sao os gargalos da obra X?",
                "O que esta travando a obra Y?",
                "Gargalos atuais da obra selecionada",
            ],
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
        mapping = {
            INTENT_LOCATE_SUPPLY: "suprimentos",
            INTENT_UNALLOCATED_ITEMS: "suprimentos",
            INTENT_LIST_PENDING_APPROVALS: "aprovacoes",
            INTENT_REJECTED_REQUESTS: "aprovacoes",
            INTENT_LIST_OBRA_PENDING: "obras",
            INTENT_RDO_BY_DATE: "obras",
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
        elif intent in (INTENT_LIST_OBRA_PENDING, INTENT_OBRA_SUMMARY, INTENT_RDO_BY_DATE) or domain == "obras":
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

