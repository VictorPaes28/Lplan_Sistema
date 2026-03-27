from __future__ import annotations

from assistente_lplan.models import AssistantEntityAlias, AssistantGuidedRule, AssistantLearningFeedback, AssistantQuestionLog


class GuidedLearningService:
    @staticmethod
    def match_guided_rule(question: str):
        text = (question or "").strip().lower()
        if not text:
            return None
        rules = AssistantGuidedRule.objects.filter(status=AssistantGuidedRule.STATUS_APPROVED).order_by("priority", "-created_at")
        for rule in rules:
            trigger = (rule.trigger_text or "").strip().lower()
            if trigger and trigger in text:
                return rule.intent, (rule.entities or {})
        return None

    @staticmethod
    def apply_entity_aliases(entities: dict) -> dict:
        if not isinstance(entities, dict):
            return {}
        normalized = dict(entities)
        aliases = AssistantEntityAlias.objects.filter(status=AssistantEntityAlias.STATUS_APPROVED)
        alias_map = {(a.entity_type, a.alias_text.lower().strip()): a.canonical_value for a in aliases}
        for entity_type in ("obra", "insumo", "usuario", "local"):
            value = (normalized.get(entity_type) or "").strip().lower()
            if not value:
                continue
            canonical = alias_map.get((entity_type, value))
            if canonical:
                normalized[entity_type] = canonical
        return normalized

    @staticmethod
    def detect_alias_mentions(text: str) -> dict:
        normalized_text = (text or "").strip().lower()
        if not normalized_text:
            return {}
        detected = {}
        aliases = AssistantEntityAlias.objects.filter(status=AssistantEntityAlias.STATUS_APPROVED).order_by("entity_type")
        for alias in aliases:
            alias_text = (alias.alias_text or "").strip().lower()
            if alias_text and alias_text in normalized_text and alias.entity_type not in detected:
                detected[alias.entity_type] = alias.canonical_value
        return detected

    @staticmethod
    def register_feedback(
        *,
        user,
        question_log_id: int,
        helpful: bool,
        corrected_intent: str = "",
        corrected_entities: dict | None = None,
        note: str = "",
    ) -> AssistantLearningFeedback:
        qlog = AssistantQuestionLog.objects.select_related("user").get(id=question_log_id)
        if qlog.user_id != user.id and not (user.is_staff or user.is_superuser):
            raise PermissionError("Sem permissao para registrar feedback desta pergunta.")

        feedback = AssistantLearningFeedback.objects.create(
            question_log=qlog,
            user=user,
            helpful=helpful,
            corrected_intent=(corrected_intent or "").strip(),
            corrected_entities=corrected_entities or {},
            note=(note or "").strip(),
            status=AssistantLearningFeedback.STATUS_PENDING,
        )

        # Gera sugestão de regra guiada somente quando há correção explícita.
        if (not helpful) and feedback.corrected_intent:
            AssistantGuidedRule.objects.create(
                source_feedback=feedback,
                trigger_text=qlog.question[:240],
                intent=feedback.corrected_intent,
                entities=feedback.corrected_entities or {},
                priority=10,
                status=AssistantGuidedRule.STATUS_PENDING,
                created_by=user,
            )
            # Também gera aliases sugeridos a partir das entidades corrigidas.
            for entity_type, canonical_value in (feedback.corrected_entities or {}).items():
                if entity_type not in {"obra", "insumo", "usuario", "local"}:
                    continue
                alias_text = ((qlog.entities or {}).get(entity_type) or "").strip()
                if not alias_text:
                    continue
                AssistantEntityAlias.objects.get_or_create(
                    entity_type=entity_type,
                    alias_text=alias_text[:160],
                    defaults={
                        "canonical_value": str(canonical_value)[:200],
                        "status": AssistantEntityAlias.STATUS_PENDING,
                        "created_by": user,
                    },
                )
        return feedback

