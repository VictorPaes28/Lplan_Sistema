from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class MessageTemplate:
    kind: str
    variants: tuple[str, ...]
    next_steps: tuple[str, ...] = ()


class MessageCatalog:
    """Catálogo central para mensagens contextuais do Assistente LPLAN."""

    _TEMPLATES: dict[str, MessageTemplate] = {
        "assistant.api.invalid_json": MessageTemplate(
            kind="validation",
            variants=(
                "Formato da requisicao invalido. Envie um JSON valido para continuar.",
                "Nao foi possivel ler sua requisicao. Verifique o JSON enviado.",
            ),
            next_steps=(
                "Confirme se o corpo da requisicao esta em JSON valido.",
                "Tente enviar novamente com os campos obrigatorios.",
            ),
        ),
        "assistant.api.question_required": MessageTemplate(
            kind="validation",
            variants=(
                "A pergunta e obrigatoria para consultar o assistente.",
                "Informe uma pergunta para eu analisar o contexto operacional.",
            ),
            next_steps=(
                "Descreva o que deseja consultar (obra, usuario, insumo ou aprovacao).",
                "Exemplo: 'Quais aprovacoes estao pendentes?'",
            ),
        ),
        "assistant.api.processing_failed": MessageTemplate(
            kind="technical_error",
            variants=(
                "Nao foi possivel processar sua pergunta neste momento.",
                "Ocorreu uma falha temporaria ao processar sua consulta.",
            ),
            next_steps=(
                "Tente novamente em instantes.",
                "Se o erro persistir, acione o suporte informando o horario da falha.",
            ),
        ),
        "assistant.api.feedback_question_log_required": MessageTemplate(
            kind="validation",
            variants=(
                "question_log_id e obrigatorio para registrar feedback.",
                "Nao consegui vincular o feedback: informe question_log_id.",
            ),
        ),
        "assistant.api.feedback_helpful_required": MessageTemplate(
            kind="validation",
            variants=(
                "Campo helpful e obrigatorio para registrar feedback.",
                "Informe se a resposta ajudou (helpful true/false).",
            ),
        ),
        "assistant.api.feedback_entities_type": MessageTemplate(
            kind="validation",
            variants=(
                "corrected_entities deve ser um objeto JSON.",
                "As entidades corrigidas precisam estar no formato objeto JSON.",
            ),
        ),
        "assistant.api.feedback_not_found": MessageTemplate(
            kind="business_error",
            variants=(
                "Pergunta nao encontrada para registrar feedback.",
                "Nao localizei a pergunta informada para este feedback.",
            ),
        ),
        "assistant.api.feedback_forbidden": MessageTemplate(
            kind="permission_error",
            variants=(
                "Sem permissao para registrar feedback nesta pergunta.",
                "Voce nao tem acesso para alterar o feedback dessa consulta.",
            ),
        ),
        "assistant.api.feedback_invalid_id": MessageTemplate(
            kind="validation",
            variants=(
                "question_log_id invalido.",
                "O identificador da pergunta e invalido.",
            ),
        ),
        "assistant.intent.ambiguous_summary": MessageTemplate(
            kind="guidance",
            variants=(
                "Nao consegui interpretar sua pergunta com confianca suficiente. Para evitar resposta meio certa, preciso que voce detalhe melhor.",
                "Nao consegui interpretar com seguranca porque sua pergunta ficou ambigua. Me passe mais contexto para eu orientar melhor.",
            ),
            next_steps=(
                "Informe explicitamente obra, usuario ou insumo.",
                "Exemplo: 'Resuma a situacao da obra ALFA'.",
            ),
        ),
        "assistant.intent.ambiguous_alert": MessageTemplate(
            kind="guidance",
            variants=(
                "Informe explicitamente obra, usuario ou insumo para uma resposta confiavel.",
                "Inclua os dados principais da consulta para evitar interpretacao ambigua.",
            ),
        ),
        "assistant.intent.unsupported": MessageTemplate(
            kind="business_error",
            variants=(
                "Intencao ainda nao suportada pelo assistente.",
                "Essa consulta ainda nao esta disponivel neste modulo do assistente.",
            ),
            next_steps=(
                "Tente perguntar sobre insumos, aprovacoes, pendencias da obra ou status de usuario.",
            ),
        ),
        "assistant.suprimentos.insumo_missing": MessageTemplate(
            kind="validation",
            variants=(
                "Dados insuficientes para localizar insumo com seguranca.",
                "Dados insuficientes: informe o insumo para uma localizacao confiavel.",
            ),
            next_steps=("Informe nome ou codigo do insumo e, se possivel, o bloco/obra.",),
        ),
        "assistant.suprimentos.insumo_not_found": MessageTemplate(
            kind="empty_state",
            variants=(
                "Nao encontrei dados suficientes para o insumo '{insumo}' no seu escopo.",
                "Nao localizei registros do insumo '{insumo}' no escopo permitido.",
            ),
            next_steps=(
                "Confirme o nome/codigo do insumo.",
                "Se possivel, informe tambem obra ou bloco para refinar a busca.",
            ),
        ),
        "assistant.suprimentos.unallocated_empty": MessageTemplate(
            kind="empty_state",
            variants=(
                "Nao ha dados suficientes de itens sem alocacao no escopo atual.",
                "Nenhum item sem alocacao foi localizado no escopo consultado.",
            ),
            next_steps=("Verifique filtros/escopo e atualize os dados de mapa se necessario.",),
        ),
        "assistant.aprovacoes.pending_empty": MessageTemplate(
            kind="empty_state",
            variants=(
                "Nao ha dados suficientes de aprovacoes pendentes no seu escopo.",
                "Nenhum pedido pendente foi localizado no escopo permitido.",
            ),
            next_steps=("Revise o escopo ou consulte outro periodo/modulo.",),
        ),
        "assistant.aprovacoes.rejected_empty": MessageTemplate(
            kind="empty_state",
            variants=(
                "Nao ha dados suficientes de solicitacoes reprovadas no seu escopo.",
                "Nenhuma reprovacao foi localizada no escopo permitido.",
            ),
            next_steps=("Revise o escopo de consulta e o periodo analisado.",),
        ),
        "assistant.obras.project_missing": MessageTemplate(
            kind="validation",
            variants=(
                "Dados insuficientes para listar pendencias da obra com seguranca.",
                "Dados insuficientes: nao consegui identificar a obra para listar pendencias.",
            ),
            next_steps=("Informe nome ou codigo da obra explicitamente.",),
        ),
        "assistant.obras.pending_empty": MessageTemplate(
            kind="empty_state",
            variants=(
                "Nao ha dados de pendencia para a obra {obra} no escopo consultado.",
                "Nenhuma pendencia operacional foi localizada para a obra {obra}.",
            ),
            next_steps=("Acompanhe a obra pelos relatorios para manter esse status.",),
        ),
        "assistant.obras.summary_project_missing": MessageTemplate(
            kind="validation",
            variants=(
                "Dados insuficientes para resumo: a obra nao foi identificada no seu escopo.",
                "Dados insuficientes: nao consegui identificar a obra para gerar resumo no escopo atual.",
            ),
            next_steps=("Informe nome/codigo da obra ou selecione uma obra ativa no contexto.",),
        ),
        "assistant.obras.summary_empty": MessageTemplate(
            kind="empty_state",
            variants=(
                "Nao ha dados operacionais suficientes para resumir a obra {obra}.",
                "Dados insuficientes para resumo da obra {obra}: sem diarios ou pedidos para consolidar.",
            ),
            next_steps=("Inclua registros de diario/pedidos e tente novamente.",),
        ),
        "assistant.usuarios.out_of_scope": MessageTemplate(
            kind="permission_error",
            variants=(
                "Usuario fora do seu escopo de acesso.",
                "Nao e permitido consultar este usuario: ele esta fora do seu escopo.",
            ),
            next_steps=("Consulte apenas usuarios permitidos pelo seu papel.",),
        ),
        "assistant.usuarios.not_identified": MessageTemplate(
            kind="validation",
            variants=(
                "Nao consegui identificar o usuario solicitado.",
                "Dados insuficientes para identificar o usuario da consulta.",
            ),
            next_steps=("Exemplo: Como Joao esta nos ultimos 30 dias?",),
        ),
        "assistant.usuarios.empty_30d": MessageTemplate(
            kind="empty_state",
            variants=(
                "Nao ha dados suficientes para avaliar o status de {usuario} nos ultimos 30 dias.",
                "Sem atividade suficiente para avaliar {usuario} nos ultimos 30 dias.",
            ),
            next_steps=("Revise o periodo ou confirme se ha atividades registradas.",),
        ),
        "assistant.cross.project_missing": MessageTemplate(
            kind="validation",
            variants=(
                "Dados insuficientes para analise de gargalos.",
                "Dados insuficientes: nao consegui identificar a obra para analise de gargalos.",
            ),
            next_steps=("Informe claramente nome ou codigo da obra.",),
        ),
        "assistant.cross.bottlenecks_empty": MessageTemplate(
            kind="empty_state",
            variants=(
                "Nao ha dados suficientes de gargalo para a obra {obra}.",
                "Nenhum gargalo operacional foi identificado para a obra {obra}.",
            ),
            next_steps=("Mantenha monitoramento por diario, aprovacoes e suprimentos.",),
        ),
    }

    @classmethod
    def resolve(cls, code: str, context: dict | None = None) -> dict:
        template = cls._TEMPLATES.get(code)
        if not template:
            return {
                "code": code,
                "kind": "generic",
                "text": "Nao foi possivel concluir a acao com os dados atuais.",
                "next_steps": [],
            }
        context = context or {}
        idx = cls._variant_index(code=code, variants_count=len(template.variants), context=context)
        text = template.variants[idx]
        try:
            text = text.format(**context)
        except Exception:  # noqa: BLE001
            pass
        return {
            "code": code,
            "kind": template.kind,
            "text": text,
            "next_steps": list(template.next_steps),
        }

    @staticmethod
    def _variant_index(code: str, variants_count: int, context: dict) -> int:
        if variants_count <= 1:
            return 0
        seed = {
            "code": code,
            "intent": context.get("intent"),
            "domain": context.get("domain"),
            "role": context.get("role"),
            "question": context.get("question"),
            "path": context.get("path"),
            "status": context.get("status"),
        }
        raw = json.dumps(seed, sort_keys=True, ensure_ascii=False, default=str)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % variants_count

