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
            + '. Extraia entidades (obra, usuario, insumo, local, referencia_local, apartamento, bloco, pavimento, dias, data, credor). '
            + 'Ignore pontuacao final (? ! .) para classificar. '
            + 'listar_aprovacoes_pendentes: fila de pedidos no GestControll (aprovacoes, pedidos pendentes, gestao de compras). '
            + 'listar_pendencias_obra: pendencias operacionais do diario de obra (RDO nao aprovado, falta de registro), NAO use para "aprovacoes". '
            + 'gargalos_obra: gargalos, problemas, dificuldades, travamentos na obra. '
            + 'relatorio_local_mapa: pergunta sobre situacao de apartamento/unidade/bloco/pavimento/setor no mapa de controle ou suprimentos. '
            + 'relatorio_rdo_periodo: PDF ou relatorio dos ultimos N dias do RDO/diario. '
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

    def clarify_missing_obra(self, user_question: str, intent_key: str, projects: list[dict]) -> str | None:
        """Uma pergunta de esclarecimento curta, sem inventar dados; lista obras vem de projects."""
        if not self.can_use() or not projects:
            return None
        lines = [f"- {p.get('code', '')} ({p.get('name', '')[:60]})" for p in projects[:12]]
        system = (
            "Voce e o assistente operacional LPLAN. O usuario fez uma pergunta que exige escolher UMA obra, "
            "mas ele tem varias obras no acesso. Escreva em portugues-BR: (1) uma frase reconhecendo a intencao, "
            "(2) explique em uma linha que no Lplan Diario, Mapa e GestControll sao amarrados ao codigo da obra, "
            "(3) peca para escolher uma obra. Nao invente codigos — use apenas a lista fornecida. Maximo 500 caracteres."
        )
        user = (
            f"Pergunta: {user_question}\nIntencao tecnica: {intent_key}\n"
            f"Obras permitidas:\n" + "\n".join(lines)
        )
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "text", "text": system}]},
                {"role": "user", "content": [{"type": "text", "text": user}]},
            ],
            "temperature": 0.15,
        }
        text = self._call_openai(payload, expect_json=False)
        if isinstance(text, str) and text.strip():
            return text.strip()[:600]
        return None

    def narrate_obra_intelligence(self, facts: dict) -> str | None:
        """
        Gera texto explicativo a partir de fatos já calculados (ex.: RadarObraService).
        Não deve inventar números — apenas reorganizar e priorizar o que veio em `facts`.
        """
        if not self.can_use() or not facts:
            return None
        system = (
            "Voce e um analista operacional de obras. Escreva em portugues-BR, tom profissional e direto. "
            "Use APENAS os numeros e fatos do JSON fornecido. Nao invente indicadores, datas ou quantidades. "
            "Se faltar dado, diga que o indicador nao esta disponivel. "
            "Estruture em: (1) situacao em 2 frases, (2) ate 4 bullets com os principais pontos de atencao, "
            "(3) uma linha de prioridade do que olhar primeiro. Maximo 900 caracteres."
        )
        user = "Dados consolidados (fonte unica, confiavel):\n" + json.dumps(facts, ensure_ascii=False)
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "text", "text": system}]},
                {"role": "user", "content": [{"type": "text", "text": user}]},
            ],
            "temperature": 0.2,
        }
        text = self._call_openai(payload, expect_json=False)
        if isinstance(text, str) and text.strip():
            return text.strip()[:1200]
        return None

    def narrate_local_mapa_report(self, facts: dict) -> str | None:
        """
        Texto a partir de fatos do LocalMapaRelatorioService (sem inventar numeros).
        """
        if not self.can_use() or not facts:
            return None
        system = (
            "Voce e um analista de suprimentos em obra. Escreva em portugues-BR, objetivo. "
            "Use APENAS numeros e nomes do JSON (local, obra, percentuais, contadores, comparativo). "
            "Inclua: (1) situacao do local vs media da obra, (2) o que esta mais critico, (3) o que esta ok. "
            "Maximo 950 caracteres. Nao invente linhas nem datas."
        )
        user = "Relatorio por local (fonte unica):\n" + json.dumps(facts, ensure_ascii=False)
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "text", "text": system}]},
                {"role": "user", "content": [{"type": "text", "text": user}]},
            ],
            "temperature": 0.2,
        }
        text = self._call_openai(payload, expect_json=False)
        if isinstance(text, str) and text.strip():
            return text.strip()[:1100]
        return None

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

