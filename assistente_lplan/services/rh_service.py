from datetime import timedelta

from django.utils import timezone

from assistente_lplan.schemas import AssistantResponse
from recursos_humanos.models import Colaborador, DocumentoColaborador
from recursos_humanos.services.admissao_actions import queryset_fluxo_admissao
from recursos_humanos.services.alerts import gerar_alertas, resumo_alertas
from recursos_humanos.services.prazo_contrato import prazos_vencendo


class RhAssistantService:
    """Consultas RH sem expor CPF, salario ou dados sensiveis."""

    def __init__(self, user):
        self.user = user

    def resumo_alertas(self, entities: dict) -> AssistantResponse:
        alertas = gerar_alertas()
        resumo = resumo_alertas(alertas)

        return AssistantResponse(
            summary=(
                f"Alertas RH: {resumo.get('total', len(alertas))} no total; "
                f"{resumo.get('vencidos', 0)} vencidos; "
                f"{resumo.get('vencendo', 0)} vencendo; "
                f"{resumo.get('admissoes', 0)} admissoes em fluxo; "
                f"{resumo.get('contratos', 0)} prazos de contrato."
            ),
            cards=[
                {"title": "Total alertas", "value": str(resumo.get("total", len(alertas))), "tone": "warning"},
                {"title": "Vencidos", "value": str(resumo.get("vencidos", 0)), "tone": "danger"},
                {"title": "Vencendo", "value": str(resumo.get("vencendo", 0)), "tone": "warning"},
                {"title": "Urgentes", "value": str(resumo.get("urgentes", 0)), "tone": "danger"},
            ],
            badges=["RH", "Alertas"],
            actions=[{"label": "Abrir Alertas RH", "url": "/rh/alertas/", "style": "primary"}],
            links=[{"label": "Recursos Humanos", "url": "/rh/"}],
        )

    def admissoes_em_andamento(self, entities: dict) -> AssistantResponse:
        qs = queryset_fluxo_admissao(self.user).filter(status=Colaborador.Status.EM_ADMISSAO)[:25]
        rows = []
        for colab in qs:
            nome = (colab.nome_completo or colab.nome_social or "Colaborador")[:60]
            rows.append(
                {
                    "nome": nome,
                    "etapa": str(colab.etapa_admissao or "-"),
                    "cargo": (colab.cargo.nome if colab.cargo_id else "-")[:40],
                    "obra": (colab.obra_local.nome if colab.obra_local_id else "-")[:40],
                }
            )

        if not rows:
            return AssistantResponse(
                summary="Nenhuma admissao em andamento no fluxo visivel.",
                badges=["RH", "Admissao"],
                alerts=[{"level": "info", "message": "Todas as admissoes podem estar concluidas."}],
            )

        return AssistantResponse(
            summary=f"{len(rows)} admissao(oes) em andamento.",
            table={
                "caption": "Fluxo de admissao",
                "columns": ["nome", "etapa", "cargo", "obra"],
                "rows": rows,
            },
            badges=["RH", "Admissao"],
            actions=[{"label": "Abrir Admissoes", "url": "/rh/admissao/", "style": "primary"}],
        )

    def documentos_vencendo(self, entities: dict) -> AssistantResponse:
        hoje = timezone.localdate()
        limite_dias = 30
        if entities.get("dias"):
            try:
                limite_dias = max(1, min(90, int(entities["dias"])))
            except (TypeError, ValueError):
                pass

        docs = (
            DocumentoColaborador.objects.select_related("colaborador", "tipo")
            .filter(tipo__tem_validade=True, vencimento__isnull=False)
            .filter(vencimento__lte=hoje + timedelta(days=limite_dias))
            .order_by("vencimento")[:30]
        )
        rows = []
        for doc in docs:
            nome = (doc.colaborador.nome_completo or doc.colaborador.nome_social or "Colaborador")[:50]
            dias = (doc.vencimento - hoje).days if doc.vencimento else 0
            rows.append(
                {
                    "colaborador": nome,
                    "documento": (doc.tipo.nome if doc.tipo_id else "-")[:40],
                    "vencimento": doc.vencimento.strftime("%d/%m/%Y") if doc.vencimento else "-",
                    "dias": str(dias),
                }
            )

        if not rows:
            return AssistantResponse(
                summary=f"Nenhum documento vencendo nos proximos {limite_dias} dias.",
                badges=["RH", "Documentos"],
            )

        return AssistantResponse(
            summary=f"{len(rows)} documento(s) vencendo ou vencidos (janela {limite_dias} dias).",
            table={
                "caption": "Documentos com validade",
                "columns": ["colaborador", "documento", "vencimento", "dias"],
                "rows": rows,
            },
            badges=["RH", "Documentos"],
            actions=[{"label": "Abrir RH", "url": "/rh/", "style": "primary"}],
        )

    def prazos_contrato(self, entities: dict) -> AssistantResponse:
        dias = 30
        if entities.get("dias"):
            try:
                dias = max(1, min(90, int(entities["dias"])))
            except (TypeError, ValueError):
                pass

        qs = prazos_vencendo(dias_antecedencia=dias)[:30]
        rows = []
        hoje = timezone.localdate()
        for prazo in qs:
            nome = (
                prazo.colaborador.nome_completo or prazo.colaborador.nome_social or "Colaborador"
            )[:50]
            dias_rest = (prazo.data_fim - hoje).days if prazo.data_fim else 0
            rows.append(
                {
                    "colaborador": nome,
                    "tipo": prazo.get_tipo_display() if hasattr(prazo, "get_tipo_display") else prazo.tipo,
                    "data_fim": prazo.data_fim.strftime("%d/%m/%Y") if prazo.data_fim else "-",
                    "dias": str(dias_rest),
                }
            )

        if not rows:
            return AssistantResponse(
                summary=f"Nenhum prazo de contrato vencendo em {dias} dias.",
                badges=["RH", "Contratos"],
            )

        return AssistantResponse(
            summary=f"{len(rows)} prazo(s) de contrato vencendo ou vencidos.",
            table={
                "caption": "Prazos contratuais",
                "columns": ["colaborador", "tipo", "data_fim", "dias"],
                "rows": rows,
            },
            badges=["RH", "Contratos"],
            actions=[{"label": "Abrir Colaboradores", "url": "/rh/colaboradores/", "style": "primary"}],
        )
