from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from django.contrib import messages


@dataclass(frozen=True)
class UiMessageTemplate:
    variants: tuple[str, ...]
    next_steps: tuple[str, ...] = ()


_CATALOG: dict[str, UiMessageTemplate] = {
    "gestao.create.not_allowed": UiMessageTemplate(
        variants=(
            "Você não pode criar pedidos com seu perfil atual.",
            "Criação de pedido indisponível para seu perfil de acesso.",
        ),
        next_steps=("Solicite perfil de solicitante ou use uma conta autorizada.",),
    ),
    "gestao.create.attachment_required": UiMessageTemplate(
        variants=(
            "Não foi possível enviar o pedido sem anexo obrigatório. Formatos permitidos: {extensoes}.",
            "Envio bloqueado: é obrigatório anexar pelo menos um arquivo válido ({extensoes}).",
        ),
        next_steps=("Anexe um arquivo e tente novamente.",),
    ),
    "gestao.create.permission_obra": UiMessageTemplate(
        variants=(
            "Você não tem permissão para criar pedidos na obra {obra}.",
            "Criação bloqueada na obra {obra}: seu usuário não possui vínculo de solicitante.",
        ),
        next_steps=("Escolha uma obra permitida ou peça liberação de acesso.",),
    ),
    "gestao.approval.not_allowed_now": UiMessageTemplate(
        variants=(
            "Este pedido não pode ser aprovado neste momento.",
            "A aprovação foi bloqueada porque o pedido já mudou de estado ou não está apto.",
        ),
        next_steps=("Atualize a página e valide o status atual do pedido.",),
    ),
    "gestao.approval.no_scope": UiMessageTemplate(
        variants=(
            "Você não tem permissão para aprovar pedidos desta obra.",
            "Aprovação negada: esta obra está fora do seu escopo de aprovação.",
        ),
        next_steps=("Verifique suas permissões de obra com um administrador.",),
    ),
    "gestao.approval.race_conflict": UiMessageTemplate(
        variants=(
            "Este pedido já foi aprovado/reprovado por outro usuário.",
            "Outro usuário já processou este pedido antes da sua confirmação.",
        ),
        next_steps=("Reabra o pedido para ver o status atualizado.",),
    ),
    "gestao.reject.not_allowed_now": UiMessageTemplate(
        variants=(
            "Este pedido não pode ser reprovado no momento.",
            "Reprovação indisponível: o pedido já mudou de estado ou não está apto.",
        ),
        next_steps=("Atualize a página e confirme o status do pedido.",),
    ),
    "gestao.reject.tags_or_comment_required": UiMessageTemplate(
        variants=(
            "Para reprovar, selecione ao menos uma tag de erro ou informe um comentário.",
            "Reprovação incompleta: informe motivo com tag de erro e/ou comentário.",
        ),
        next_steps=("Descreva o motivo principal da reprovação para orientar a correção.",),
    ),
    "gestao.delete_request.only_creator": UiMessageTemplate(
        variants=(
            "Você só pode solicitar exclusão de pedidos criados por você.",
            "Solicitação negada: apenas o criador do pedido pode pedir exclusão.",
        ),
    ),
    "gestao.delete_request.invalid_status": UiMessageTemplate(
        variants=(
            "A exclusão só pode ser solicitada para pedidos pendentes ou reprovados.",
            "Este status não permite solicitação de exclusão.",
        ),
    ),
    "gestao.delete_request.reason_required": UiMessageTemplate(
        variants=(
            "Informe o motivo da exclusão para continuar.",
            "Não foi possível solicitar exclusão sem um motivo.",
        ),
        next_steps=("Explique resumidamente o motivo da exclusão.",),
    ),
    "gestao.delete_approve.not_requested": UiMessageTemplate(
        variants=(
            "Este pedido não possui solicitação de exclusão pendente.",
            "Nenhuma solicitação de exclusão foi encontrada para este pedido.",
        ),
    ),
    "gestao.delete_approve.no_role": UiMessageTemplate(
        variants=(
            "Você não tem permissão para aprovar exclusões.",
            "Aprovação de exclusão indisponível para seu perfil.",
        ),
    ),
    "gestao.delete_approve.no_scope": UiMessageTemplate(
        variants=(
            "Você não tem permissão para aprovar exclusões desta obra.",
            "Aprovação negada: esta obra não está no seu escopo de exclusão.",
        ),
    ),
    "gestao.delete_reject.no_role": UiMessageTemplate(
        variants=(
            "Você não tem permissão para rejeitar exclusões.",
            "Rejeição de exclusão indisponível para seu perfil.",
        ),
    ),
    "gestao.delete_reject.no_scope": UiMessageTemplate(
        variants=(
            "Você não tem permissão para rejeitar exclusões desta obra.",
            "Rejeição negada: esta obra não está no seu escopo.",
        ),
    ),
    "mapa.select.no_scope": UiMessageTemplate(
        variants=(
            "Você não está vinculado à obra {obra}.",
            "A obra {obra} está fora do seu escopo no Mapa de Suprimentos.",
        ),
        next_steps=("Selecione uma obra vinculada ao seu usuário.",),
    ),
    "mapa.api.no_scope": UiMessageTemplate(
        variants=(
            "Sem permissão para acessar os locais desta obra.",
            "Acesso negado para listar locais da obra solicitada.",
        ),
        next_steps=("Confirme se a obra está vinculada ao seu perfil.",),
    ),
    "core.diary.edit.no_permission": UiMessageTemplate(
        variants=(
            "Você não tem permissão para editar este diário.",
            "Edição bloqueada: este diário não está disponível para seu usuário.",
        ),
        next_steps=("Abra o diário em modo leitura ou solicite liberação ao responsável.",),
    ),
    "core.diary.project_not_selected": UiMessageTemplate(
        variants=(
            "Nenhum projeto selecionado para continuar no diário.",
            "O diário depende de uma obra selecionada e não foi possível identificar esse contexto.",
        ),
        next_steps=("Selecione a obra na tela inicial e tente novamente.",),
    ),
    "core.diary.form_process_error": UiMessageTemplate(
        variants=(
            "Não foi possível processar o formulário do diário com os dados enviados.",
            "Falha ao preparar os dados do diário para salvamento.",
        ),
        next_steps=("Revise os campos obrigatórios e salve novamente.",),
    ),
    "core.form.fix_errors.profile": UiMessageTemplate(
        variants=(
            "Revise os campos do perfil e corrija os erros destacados.",
            "Não foi possível salvar o perfil enquanto houver campos inválidos.",
        ),
    ),
    "core.form.fix_errors.activity": UiMessageTemplate(
        variants=(
            "Revise os dados da atividade e corrija os campos destacados.",
            "A atividade não foi salva porque ainda há inconsistências no formulário.",
        ),
    ),
    "core.activity.delete.has_children": UiMessageTemplate(
        variants=(
            "Não é possível excluir a atividade \"{atividade}\" porque ela possui atividades filhas.",
            "Exclusão bloqueada para \"{atividade}\": remova ou mova as atividades filhas primeiro.",
        ),
        next_steps=("Remova os vínculos filhos antes de tentar excluir novamente.",),
    ),
    "core.form.fix_errors.labor": UiMessageTemplate(
        variants=(
            "Revise os dados da mão de obra e corrija os campos destacados.",
            "Não foi possível salvar a mão de obra enquanto houver campos inválidos.",
        ),
    ),
    "core.form.fix_errors.equipment": UiMessageTemplate(
        variants=(
            "Revise os dados do equipamento e corrija os campos destacados.",
            "Não foi possível salvar o equipamento enquanto houver campos inválidos.",
        ),
    ),
    "core.form.fix_errors.project": UiMessageTemplate(
        variants=(
            "Revise os dados da obra e corrija os campos destacados.",
            "Não foi possível salvar a obra enquanto houver inconsistências no formulário.",
        ),
    ),
    "central.diary_email.required": UiMessageTemplate(
        variants=(
            "Informe o e-mail para adicionar destinatário do diário.",
            "Não foi possível adicionar destinatário sem e-mail.",
        ),
    ),
    "central.diary_email.invalid": UiMessageTemplate(
        variants=(
            "E-mail inválido para recebimento do diário.",
            "O e-mail informado não é válido para cadastro de destinatário.",
        ),
        next_steps=("Revise o formato do e-mail e tente novamente.",),
    ),
    "central.signup.approve.groups_required": UiMessageTemplate(
        variants=(
            "Selecione pelo menos uma permissão (grupo) antes de aprovar.",
            "A aprovação exige ao menos um grupo de acesso selecionado.",
        ),
    ),
    "central.signup.approve.failed": UiMessageTemplate(
        variants=(
            "Não foi possível aprovar a solicitação no momento.",
            "A aprovação falhou com os dados atuais da solicitação.",
        ),
        next_steps=("Revise grupos/obras e tente novamente.",),
    ),
    "central.signup.reject.already_processed": UiMessageTemplate(
        variants=(
            "Esta solicitação já foi processada.",
            "Não é possível rejeitar porque esta solicitação já foi concluída.",
        ),
    ),
    "central.signup.reject.reason_required": UiMessageTemplate(
        variants=(
            "Informe o motivo da rejeição.",
            "A rejeição exige um motivo para registro e auditoria.",
        ),
    ),
    "central.clients.username_required": UiMessageTemplate(
        variants=(
            "Username é obrigatório para criar cliente.",
            "Não foi possível criar cliente sem username.",
        ),
    ),
    "central.clients.project_required": UiMessageTemplate(
        variants=(
            "Selecione pelo menos uma obra para vincular o cliente.",
            "Criação bloqueada: o cliente precisa estar vinculado a ao menos uma obra.",
        ),
    ),
    "central.clients.username_exists": UiMessageTemplate(
        variants=(
            "O username \"{username}\" já existe.",
            "Não foi possível usar \"{username}\": username já cadastrado.",
        ),
    ),
    "central.clients.email_invalid": UiMessageTemplate(
        variants=(
            "E-mail inválido para cadastro de cliente.",
            "Não foi possível salvar: o e-mail informado é inválido.",
        ),
    ),
    "central.clients.invalid_project": UiMessageTemplate(
        variants=(
            "Há obra inválida ou inativa selecionada.",
            "Os vínculos de obra informados contêm item inválido/inativo.",
        ),
        next_steps=("Atualize a página e selecione apenas obras ativas.",),
    ),
    "central.clients.password_min": UiMessageTemplate(
        variants=(
            "Senha obrigatória com no mínimo 8 caracteres.",
            "A senha informada é inválida: use ao menos 8 caracteres.",
        ),
    ),
    "central.clients.project_already_linked": UiMessageTemplate(
        variants=(
            "Este cliente já está vinculado a esta obra.",
            "Não houve alteração: o vínculo cliente-obra já existia.",
        ),
    ),
    "central.clients.self_delete_blocked": UiMessageTemplate(
        variants=(
            "Você não pode excluir seu próprio usuário por esta tela.",
            "Exclusão bloqueada para segurança: não é permitido remover sua própria conta aqui.",
        ),
    ),
    "central.diary_edit.no_pending_request": UiMessageTemplate(
        variants=(
            "Este relatório não tem pedido de correção pendente.",
            "A liberação de edição não pode ser feita: não há solicitação pendente.",
        ),
    ),
    "central.diary_edit.already_granted": UiMessageTemplate(
        variants=(
            "Este relatório já tem edição liberada.",
            "A edição provisória já foi concedida para este relatório.",
        ),
    ),
}


def resolve_message(code: str, context: dict | None = None) -> dict:
    template = _CATALOG.get(code)
    if not template:
        return {"code": code, "text": "Não foi possível concluir a ação com os dados atuais.", "next_steps": []}
    context = context or {}
    variant_idx = _variant_index(code, len(template.variants), context)
    text = template.variants[variant_idx]
    try:
        text = text.format(**context)
    except Exception:  # noqa: BLE001
        pass
    return {"code": code, "text": text, "next_steps": list(template.next_steps)}


def flash_message(request, level: str, code: str, context: dict | None = None) -> str:
    msg = resolve_message(code, context=context)
    text = msg["text"]
    if msg["next_steps"]:
        text = f"{text} Próximo passo: {msg['next_steps'][0]}"
    sender = getattr(messages, level, messages.info)
    sender(request, text)
    return msg["code"]


def _variant_index(code: str, variants_count: int, context: dict) -> int:
    if variants_count <= 1:
        return 0
    raw = json.dumps({"code": code, "context": context}, sort_keys=True, ensure_ascii=False, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % variants_count

