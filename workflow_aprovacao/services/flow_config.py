"""
Persistência da configuração de fluxos (alçadas e participantes) — UI interna.
"""
from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction

from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalPolicy,
    ApprovalProcess,
    ApprovalStep,
    ApprovalStepParticipant,
    ParticipantRole,
    SubjectKind,
)

User = get_user_model()


class FlowConfigError(Exception):
    """Erro de validação ao aplicar configuração."""


def serialize_flow_for_editor(flow: ApprovalFlowDefinition) -> dict[str, Any]:
    """Estado inicial para o editor (JSON)."""
    steps_out: list[dict[str, Any]] = []
    for st in flow.steps.order_by("sequence"):
        parts: list[dict[str, Any]] = []
        for p in st.participants.order_by("pk"):
            if p.subject_kind == SubjectKind.USER:
                parts.append(
                    {
                        "subject_kind": "user",
                        "user_id": p.user_id,
                        "group_id": None,
                    }
                )
            else:
                parts.append(
                    {
                        "subject_kind": "django_group",
                        "user_id": None,
                        "group_id": p.django_group_id,
                    }
                )
        steps_out.append(
            {
                "id": st.pk,
                "name": st.name,
                "is_active": st.is_active,
                "participants": parts
                or [{"subject_kind": "user", "user_id": None, "group_id": None}],
            }
        )
    if not steps_out:
        steps_out.append(
            {
                "id": None,
                "name": "1ª alçada",
                "is_active": True,
                "participants": [{"subject_kind": "user", "user_id": None, "group_id": None}],
            }
        )
    return {"is_active": flow.is_active, "steps": steps_out}


def flow_structure_locked(flow: ApprovalFlowDefinition) -> bool:
    """True se já existem processos ligados — estrutura de alçadas não deve mudar livremente."""
    return ApprovalProcess.objects.filter(flow_definition=flow).exists()


def _step_ids_in_use_by_processes(flow: ApprovalFlowDefinition) -> set[int]:
    qs = ApprovalProcess.objects.filter(flow_definition=flow).exclude(current_step__isnull=True)
    return set(qs.values_list("current_step_id", flat=True))


def _bump_sequences_temporarily(flow: ApprovalFlowDefinition) -> None:
    """Evita colisão na constraint única (flow, sequence) durante reordenação."""
    steps = list(flow.steps.order_by("sequence"))
    for i, st in enumerate(steps):
        ApprovalStep.objects.filter(pk=st.pk).update(sequence=10000 + i)


@transaction.atomic
def apply_flow_configuration(
    flow: ApprovalFlowDefinition,
    payload: dict[str, Any],
    *,
    structure_locked: bool,
) -> None:
    """
    Aplica payload JSON com is_active, steps[{id?, name, is_active, participants[{...}]}].
    """
    if not isinstance(payload, dict):
        raise FlowConfigError("Formato inválido.")

    is_active = payload.get("is_active")
    if not isinstance(is_active, bool):
        raise FlowConfigError("Indique se o fluxo está ativo.")

    steps_in = payload.get("steps")
    if not isinstance(steps_in, list) or len(steps_in) == 0:
        raise FlowConfigError("Defina pelo menos uma alçada.")

    if len(steps_in) > 40:
        raise FlowConfigError("Limite de 40 alçadas por fluxo.")

    normalized: list[dict[str, Any]] = []
    for i, raw in enumerate(steps_in):
        if not isinstance(raw, dict):
            raise FlowConfigError(f"Alçada {i + 1}: formato inválido.")
        name = (raw.get("name") or "").strip()
        if not name:
            raise FlowConfigError(f"Alçada {i + 1}: informe um nome.")
        if len(name) > 200:
            raise FlowConfigError(f"Alçada {i + 1}: nome muito longo.")
        step_active = raw.get("is_active")
        if not isinstance(step_active, bool):
            raise FlowConfigError(f"Alçada «{name}»: indique se está ativa.")
        sid = raw.get("id")
        if sid is not None and (not isinstance(sid, int) or sid < 1):
            raise FlowConfigError(f"Alçada «{name}»: identificador inválido.")

        parts = raw.get("participants")
        if not isinstance(parts, list) or len(parts) == 0:
            raise FlowConfigError(
                f"Alçada «{name}»: adicione pelo menos um aprovador (utilizador ou grupo)."
            )
        if len(parts) > 20:
            raise FlowConfigError(f"Alçada «{name}»: limite de 20 participadores.")

        plist: list[dict[str, Any]] = []
        for j, p in enumerate(parts):
            if not isinstance(p, dict):
                raise FlowConfigError(f"Alçada «{name}»: participante {j + 1} inválido.")
            sk = p.get("subject_kind")
            if sk not in (SubjectKind.USER, SubjectKind.DJANGO_GROUP):
                raise FlowConfigError(
                    f"Alçada «{name}»: cada participante deve ser utilizador ou grupo."
                )
            if sk == SubjectKind.USER:
                uid = p.get("user_id")
                if not isinstance(uid, int) or uid < 1:
                    raise FlowConfigError(f"Alçada «{name}»: selecione o utilizador em cada linha.")
                if not User.objects.filter(pk=uid, is_active=True).exists():
                    raise FlowConfigError(f"Alçada «{name}»: utilizador inválido ou inativo.")
                plist.append({"subject_kind": SubjectKind.USER, "user_id": uid, "group_id": None})
            else:
                gid = p.get("group_id")
                if not isinstance(gid, int) or gid < 1:
                    raise FlowConfigError(f"Alçada «{name}»: selecione o grupo em cada linha.")
                if not Group.objects.filter(pk=gid).exists():
                    raise FlowConfigError(f"Alçada «{name}»: grupo inválido.")
                plist.append({"subject_kind": SubjectKind.DJANGO_GROUP, "user_id": None, "group_id": gid})

        normalized.append(
            {
                "id": sid,
                "name": name,
                "is_active": step_active,
                "participants": plist,
            }
        )

    incoming_ids = {x["id"] for x in normalized if x["id"] is not None}
    existing = {s.pk: s for s in flow.steps.all()}
    in_use = _step_ids_in_use_by_processes(flow)

    expected_order = list(flow.steps.order_by("sequence").values_list("id", flat=True))
    incoming_order = [x["id"] for x in normalized if x["id"] is not None]

    if structure_locked:
        if set(expected_order) != set(incoming_order) or len(incoming_order) != len(expected_order):
            raise FlowConfigError(
                "Existem processos neste fluxo. Não é possível adicionar, remover ou reordenar alçadas. "
                "Apenas nomes, situação ativa e participantes podem ser alterados."
            )
        if incoming_order != expected_order:
            raise FlowConfigError(
                "Existem processos neste fluxo: mantenha a mesma ordem de alçadas."
            )
        for item in normalized:
            if item["id"] and item["id"] not in existing:
                raise FlowConfigError("Identificador de alçada inválido.")

    to_remove = [pk for pk in existing if pk not in incoming_ids]
    for pk in to_remove:
        if pk in in_use:
            raise FlowConfigError(
                "Não é possível remover uma alçada enquanto existir processo aguardando nela."
            )
        ApprovalStepParticipant.objects.filter(step_id=pk).delete()
        ApprovalStep.objects.filter(pk=pk).delete()

    existing = {s.pk: s for s in flow.steps.all()}
    _bump_sequences_temporarily(flow)

    for seq, item in enumerate(normalized, start=1):
        if item["id"] and item["id"] in existing:
            step = existing[item["id"]]
            step.sequence = seq
            step.name = item["name"]
            step.is_active = item["is_active"]
            step.approval_policy = ApprovalPolicy.SINGLE_ANY
            step.save(update_fields=["sequence", "name", "is_active", "approval_policy"])
        else:
            if structure_locked:
                raise FlowConfigError("Não é possível criar novas alçadas: já existem processos neste fluxo.")
            step = ApprovalStep.objects.create(
                flow=flow,
                sequence=seq,
                name=item["name"],
                is_active=item["is_active"],
                approval_policy=ApprovalPolicy.SINGLE_ANY,
            )

        ApprovalStepParticipant.objects.filter(step=step).delete()
        for p in item["participants"]:
            ApprovalStepParticipant.objects.create(
                step=step,
                role=ParticipantRole.APPROVER,
                subject_kind=p["subject_kind"],
                user_id=p["user_id"],
                django_group_id=p["group_id"],
            )

    flow.is_active = is_active
    flow.save(update_fields=["is_active", "updated_at"])
