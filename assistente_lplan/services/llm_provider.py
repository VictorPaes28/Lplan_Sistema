import json
import os
from urllib import error, request

from .intents import SUPPORTED_INTENTS


class LLMProvider:
    def __init__(self):
        self.enabled = os.environ.get("ASSISTENTE_LPLAN_AI_ENABLED", "False").lower() in ("1", "true", "yes")
        self.api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.model = os.environ.get("ASSISTENTE_LPLAN_AI_MODEL", "gpt-4o-mini")

    def can_use(self) -> bool:
        return bool(self.enabled and self.api_key)

    def detect_intent(self, input_text: str):
        if not self.can_use():
            return None

        prompt = (
            "Classifique a pergunta em UMA intencao desta lista: "
            + ", ".join(sorted(SUPPORTED_INTENTS))
            + '. Extraia entidades (obra, usuario, insumo, local). '
            + 'Retorne JSON puro: {"intent": "...", "entities": {...}, "confidence": 0.0-1.0}.'
        )
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "text", "text": prompt}]},
                {"role": "user", "content": [{"type": "text", "text": input_text}]},
            ],
            "temperature": 0,
        }
        result = self._call_openai(payload)
        if not isinstance(result, dict):
            return None
        intent = result.get("intent", "")
        entities = result.get("entities", {})
        try:
            confidence = float(result.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(confidence, 1.0))
        if intent not in SUPPORTED_INTENTS or not isinstance(entities, dict):
            return None
        return intent, entities, confidence

    def improve_summary(self, input_text: str, domain: str = "") -> str:
        if not self.can_use():
            return input_text
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Reescreva o resumo abaixo em portugues-BR tecnico, objetivo e confiavel, "
                                "mantendo o sentido e sem inventar dados. Maximo 240 caracteres."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": input_text + f" Dominio: {domain}"}],
                },
            ],
            "temperature": 0.2,
        }
        text = self._call_openai(payload, expect_json=False)
        if isinstance(text, str) and text.strip():
            return text.strip()
        return input_text

    def _call_openai(self, payload: dict, expect_json: bool = True):
        try:
            req = request.Request(
                url="https://api.openai.com/v1/responses",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            with request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
            return None

        text = self._extract_text(body)
        if not text:
            return None
        if not expect_json:
            return text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _extract_text(body: dict) -> str:
        output = body.get("output") or []
        for item in output:
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return content.get("text", "")
        return body.get("output_text", "")

