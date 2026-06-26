"""Consultas RH / DP."""
from __future__ import annotations

from datetime import date, datetime

from assistente_lplan.services.permissions import UserScope


def _json_safe_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe_value(v) for v in value]
    return value


def resumo_rh(user, scope: UserScope) -> dict:
    from recursos_humanos.models import Colaborador
    from recursos_humanos.services.alerts import gerar_alertas, resumo_alertas

    alertas = gerar_alertas()
    resumo = _json_safe_value(resumo_alertas(alertas))
    criticos = sum(1 for a in alertas if a.urgencia in ("red", "yellow"))
    return {
        "ok": True,
        "colaboradores_ativos": Colaborador.objects.filter(status=Colaborador.Status.ATIVO).count(),
        "em_admissao": Colaborador.objects.filter(status=Colaborador.Status.EM_ADMISSAO).count(),
        "alertas_total": len(alertas),
        "alertas_criticos": criticos,
        "resumo": resumo,
        "summary_hint": (
            f"RH: {Colaborador.objects.filter(status=Colaborador.Status.ATIVO).count()} ativos, "
            f"{criticos} alerta(s) critico(s)/atencao."
        ),
    }


def documentos_vencendo(user, scope: UserScope, *, dias: int = 30) -> dict:
    from recursos_humanos.services.alerts import gerar_alertas

    alertas = [a for a in gerar_alertas() if a.tipo in ("documento_vencendo", "documento_vencido")]
    rows = [
        {
            "colaborador": a.colaborador_nome,
            "tipo": a.tipo,
            "descricao": a.descricao[:80],
            "urgencia": a.urgencia,
            "dias_restantes": getattr(a, "dias_restantes", None),
        }
        for a in alertas[:30]
    ]
    return {
        "ok": True,
        "total": len(alertas),
        "rows": rows,
        "summary_hint": f"{len(alertas)} colaborador(es) com documento vencendo ou vencido.",
    }


def admissoes_andamento(user, scope: UserScope) -> dict:
    from recursos_humanos.models import Colaborador

    qs = Colaborador.objects.filter(status=Colaborador.Status.EM_ADMISSAO).order_by("-id")[:30]
    rows = [
        {
            "nome": c.nome,
            "cargo": c.cargo or "-",
            "etapa": c.etapa_admissao or "-",
            "status": c.status,
        }
        for c in qs
    ]
    return {
        "ok": True,
        "total": qs.count(),
        "rows": rows,
        "summary_hint": f"{qs.count()} admissao(oes) em andamento.",
    }


def quick_rh_alertas_count(user, scope: UserScope) -> int:
    from recursos_humanos.services.alerts import gerar_alertas

    return sum(1 for a in gerar_alertas() if a.urgencia in ("red", "yellow") and "documento" in a.tipo)
