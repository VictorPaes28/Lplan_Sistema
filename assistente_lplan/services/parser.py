import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from difflib import SequenceMatcher

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
from .learning import GuidedLearningService


class RuleBasedIntentParser:
    """Fallback deterministico para intencao + entidades."""

    @dataclass
    class ParseResult:
        intent: str
        entities: dict
        confidence: float
        candidates: list[tuple[str, float]]
        reason: str

    def parse(self, question: str) -> ParseResult:
        text = (question or "").strip().lower()
        normalized_text = self._normalize(text)
        normalized_tokens = self._tokenize(normalized_text)
        entities = GuidedLearningService.apply_entity_aliases(self._extract_entities(text))
        entities.update(GuidedLearningService.detect_alias_mentions(text))
        if not text:
            return self.ParseResult(
                intent=INTENT_FALLBACK,
                entities=entities,
                confidence=0.0,
                candidates=[],
                reason="pergunta_vazia",
            )

        guided = GuidedLearningService.match_guided_rule(text)
        if guided:
            guided_intent, guided_entities = guided
            merged_entities = dict(entities)
            merged_entities.update(guided_entities or {})
            merged_entities = GuidedLearningService.apply_entity_aliases(merged_entities)
            return self.ParseResult(
                intent=guided_intent,
                entities=merged_entities,
                confidence=0.9,
                candidates=[(guided_intent, 0.9)],
                reason="match_regra_guiada_aprovada",
            )

        rules = [
            (
                INTENT_LOCATE_SUPPLY,
                ["onde esta", "onde está", "localizar", "localizacao", "localização", "insumo", "cimento"],
                0.0,
            ),
            (
                INTENT_UNALLOCATED_ITEMS,
                ["itens sem aloc", "sem alocacao", "sem alocação", "nao alocados", "não alocados"],
                0.0,
            ),
            (
                INTENT_LIST_PENDING_APPROVALS,
                ["aprova", "aprovacao", "aprovação", "pendente", "pendentes"],
                0.0,
            ),
            (
                INTENT_RDO_BY_DATE,
                ["rdo", "diario do dia", "diário do dia", "relatorio do dia", "relatório do dia", "rdo do dia"],
                0.0,
            ),
            (
                INTENT_REJECTED_REQUESTS,
                ["reprovad", "reprovado", "reprovadas", "solicitacoes reprovadas", "solicitações reprovadas"],
                0.0,
            ),
            (
                INTENT_OBRA_BOTTLENECKS,
                ["gargalo", "travando", "travado", "impedindo", "bloqueando"],
                0.0,
            ),
            (
                INTENT_OBRA_SUMMARY,
                [
                    "resumo da obra",
                    "resuma a situacao",
                    "resuma a situação",
                    "situacao da obra",
                    "situação da obra",
                    "obra atual",
                    "como esta a obra",
                    "como está a obra",
                    "como anda a obra",
                    "como esta o rdo",
                    "como está o rdo",
                    "como esta o diario",
                    "como está o diario",
                    "diario de obras",
                ],
                0.0,
            ),
            (
                INTENT_LIST_OBRA_PENDING,
                ["penden", "pendên", "pendencia da obra", "pendência da obra", "o que falta na obra"],
                0.0,
            ),
            (
                INTENT_USER_STATUS,
                ["ultimos 30 dias", "últimos 30 dias", "status do usuario", "status de usuário", "desempenho do"],
                0.0,
            ),
        ]

        scored: list[tuple[str, float]] = []
        for intent, keywords, _ in rules:
            score = 0.0
            for keyword in keywords:
                match_strength = self._contains_keyword_fuzzy(normalized_text, normalized_tokens, self._normalize(keyword))
                if match_strength > 0:
                    base = 0.22 if len(keyword) > 6 else 0.15
                    score += base * match_strength

            if intent == INTENT_USER_STATUS and "usuario" in entities:
                score += 0.25
            if intent == INTENT_USER_STATUS and "usuario" in entities and ("esta" in normalized_text):
                score += 0.25
            if intent == INTENT_RDO_BY_DATE and "data" in entities:
                score += 0.5
            if intent == INTENT_RDO_BY_DATE and any(tok in normalized_text for tok in ["rdo", "diario", "relatorio"]):
                score += 0.25
            if intent in (INTENT_OBRA_SUMMARY, INTENT_LIST_OBRA_PENDING, INTENT_OBRA_BOTTLENECKS) and "obra" in entities:
                score += 0.2
            if intent == INTENT_OBRA_SUMMARY and any(t in normalized_text for t in ["rdo", "diario", "obra atual"]):
                score += 0.35
            if intent == INTENT_LOCATE_SUPPLY and ("insumo" in entities or "bloco" in entities):
                score += 0.2

            if score > 0:
                scored.append((intent, min(score, 1.0)))

        scored.sort(key=lambda x: x[1], reverse=True)
        if not scored:
            return self.ParseResult(
                intent=INTENT_FALLBACK,
                entities=entities,
                confidence=0.0,
                candidates=[],
                reason="sem_regra_compativel",
            )

        top_intent, top_conf = scored[0]
        second_conf = scored[1][1] if len(scored) > 1 else 0.0
        if top_conf < 0.34 or abs(top_conf - second_conf) < 0.08:
            return self.ParseResult(
                intent=INTENT_FALLBACK,
                entities=entities,
                confidence=top_conf,
                candidates=scored[:3],
                reason="baixa_confianca_ou_ambiguidade",
            )

        return self.ParseResult(
            intent=top_intent,
            entities=entities,
            confidence=top_conf,
            candidates=scored[:3],
            reason="match_regra",
        )

    def _extract_entities(self, text: str) -> dict:
        entities: dict[str, str] = {}
        normalized_text = self._normalize(text)
        normalized_tokens = self._tokenize(normalized_text)

        obra_match = re.search(r"\bobra\s+([a-z0-9\-_/ ]+)", text)
        if obra_match:
            obra_value = obra_match.group(1).strip(" .,:;")
            if obra_value.startswith("atual "):
                obra_value = obra_value[6:].strip()
            if obra_value in {"atual", "selecionada", "selecionado", "corrente"}:
                obra_value = ""
            if obra_value:
                entities["obra"] = obra_value

        usuario_match = re.search(r"\b(?:usuario|usuário|desempenho do|status do)\s+([a-z0-9._@\- ]+)", text)
        if usuario_match:
            entities["usuario"] = usuario_match.group(1).strip(" .,:;")
        else:
            # Captura consultas do tipo "como joao esta nos ultimos 30 dias"
            como_match = re.search(r"\bcomo\s+([a-z0-9._@\-]+)\s+est", text)
            if como_match:
                entities["usuario"] = como_match.group(1).strip(" .,:;")

        bloco_match = re.search(r"\b(?:bloco|bloko)\s+([a-z0-9\-_/]+)", normalized_text)
        if bloco_match:
            entities["bloco"] = bloco_match.group(1).strip(" .,:;")

        if any(tok == "cimento" or self._token_similarity(tok, "cimento") >= 0.82 for tok in normalized_tokens):
            entities["insumo"] = "cimento"
        else:
            insumo_match = re.search(
                r"\binsumo\s+([a-z0-9\-_/ ]+?)(?=\s+do\s+bloco|\s+do\s+bloko|\s+na\s+obra|\?|$)",
                normalized_text,
            )
            if insumo_match:
                entities["insumo"] = insumo_match.group(1).strip(" .,:;")

        parsed_date = self._extract_date_entity(normalized_text)
        if parsed_date:
            entities["data"] = parsed_date

        return {k: v for k, v in entities.items() if v}

    def _extract_date_entity(self, normalized_text: str) -> str:
        if not normalized_text:
            return ""

        today = date.today()
        if "hoje" in normalized_text:
            return today.isoformat()
        if "anteontem" in normalized_text:
            return (today - timedelta(days=2)).isoformat()
        if "ontem" in normalized_text:
            return (today - timedelta(days=1)).isoformat()

        slash_match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", normalized_text)
        if slash_match:
            day = int(slash_match.group(1))
            month = int(slash_match.group(2))
            year = int(slash_match.group(3))
            if year < 100:
                year += 2000
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                return ""

        iso_match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", normalized_text)
        if iso_match:
            year = int(iso_match.group(1))
            month = int(iso_match.group(2))
            day = int(iso_match.group(3))
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                return ""

        return ""

    @staticmethod
    def _normalize(value: str) -> str:
        raw = (value or "").lower()
        raw = unicodedata.normalize("NFD", raw)
        raw = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")
        return re.sub(r"\s+", " ", raw).strip()

    @staticmethod
    def _tokenize(value: str) -> list[str]:
        return re.findall(r"[a-z0-9_/-]+", value or "")

    @staticmethod
    def _token_similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

    def _contains_keyword_fuzzy(self, normalized_text: str, normalized_tokens: list[str], keyword: str) -> float:
        if not keyword:
            return 0.0
        if keyword in normalized_text:
            return 1.0

        parts = self._tokenize(keyword)
        if not parts:
            return 0.0

        # Palavra única: aceita variação leve de digitação.
        if len(parts) == 1:
            best = 0.0
            for token in normalized_tokens:
                if abs(len(token) - len(parts[0])) > 2:
                    continue
                sim = self._token_similarity(token, parts[0])
                if sim > best:
                    best = sim
            if best >= 0.82:
                return 0.85
            return 0.0

        # Frases: exige maioria dos termos encontrados (direto ou fuzzy).
        matched = 0
        for part in parts:
            if part in normalized_tokens:
                matched += 1
                continue
            if any(self._token_similarity(tok, part) >= 0.84 for tok in normalized_tokens):
                matched += 1
        ratio = matched / len(parts)
        if ratio >= 0.75:
            return 0.8
        return 0.0

