from datetime import timedelta

from django.utils import timezone

from assistente_lplan.schemas import AssistantResponse
from core.models import ConstructionDiary, DiaryStatus, Project


class DiarioAssistantService:
    def __init__(self, scope):
        self.scope = scope

    def listar_pendencias_obra(self, entities: dict) -> AssistantResponse:
        project = self._resolve_project(entities)
        if not project:
            return AssistantResponse(
                summary="Nao foi possivel identificar uma obra do seu escopo.",
                alerts=[{"level": "warning", "message": "Informe o nome/codigo da obra na pergunta."}],
            )

        qs = (
            ConstructionDiary.objects.filter(project=project)
            .exclude(status=DiaryStatus.APROVADO)
            .order_by("-date")[:20]
        )
        rows = []
        for d in qs:
            rows.append(
                {
                    "data": d.date.strftime("%d/%m/%Y"),
                    "relatorio": d.report_number or "-",
                    "status": d.get_status_display(),
                    "responsavel": (d.created_by.get_full_name() or d.created_by.username) if d.created_by else "-",
                }
            )

        total = ConstructionDiary.objects.filter(project=project).exclude(status=DiaryStatus.APROVADO).count()
        return AssistantResponse(
            summary=f"A obra {project.code} possui {total} diarios pendentes/nao aprovados.",
            cards=[
                {"title": "Diarios pendentes", "value": str(total), "tone": "warning"},
                {
                    "title": "Ultimos 7 dias",
                    "value": str(
                        ConstructionDiary.objects.filter(project=project, date__gte=timezone.now().date() - timedelta(days=7))
                        .exclude(status=DiaryStatus.APROVADO)
                        .count()
                    ),
                    "tone": "info",
                },
            ],
            table={"caption": f"Pendencias do diario - {project.name}", "columns": ["data", "relatorio", "status", "responsavel"], "rows": rows},
            badges=["Diario de Obras"],
            actions=[{"label": "Abrir relatorios", "url": "/reports/", "style": "primary"}],
            links=[{"label": "Relatorios da obra", "url": "/reports/"}],
        )

    def gargalos_obra(self, entities: dict) -> AssistantResponse:
        project = self._resolve_project(entities)
        if not project:
            return AssistantResponse(
                summary="Nao encontrei a obra no seu escopo para analisar gargalos.",
                alerts=[{"level": "warning", "message": "Tente: gargalos da obra <nome/codigo>."}],
            )

        base = ConstructionDiary.objects.filter(project=project)
        stoppages = base.exclude(stoppages="").count()
        riscos = base.exclude(imminent_risks="").count()
        acidentes = base.exclude(accidents="").count()

        alerts = []
        if stoppages:
            alerts.append({"level": "warning", "message": "Foram registradas paralisacoes nesta obra."})
        if riscos or acidentes:
            alerts.append({"level": "error", "message": "Ha ocorrencias de seguranca que exigem atencao."})

        return AssistantResponse(
            summary=f"Gargalos da obra {project.code} compilados a partir do Diario de Obras.",
            cards=[
                {"title": "Paralisacoes", "value": str(stoppages), "tone": "warning"},
                {"title": "Riscos", "value": str(riscos), "tone": "danger"},
                {"title": "Acidentes", "value": str(acidentes), "tone": "danger"},
            ],
            timeline=[{"date": "-", "label": "Paralisacoes registradas", "value": str(stoppages)}],
            alerts=alerts,
            badges=["Diario", "Gargalos"],
            actions=[{"label": "Ver detalhes da obra", "url": "/reports/", "style": "secondary"}],
            links=[{"label": "Diario - Relatorios", "url": "/reports/"}],
            raw_data={"project_id": project.id},
        )

    def _resolve_project(self, entities: dict):
        project_id = entities.get("project_id")
        if project_id:
            try:
                pid = int(project_id)
            except (TypeError, ValueError):
                pid = None
            if pid:
                qs_by_id = Project.objects.filter(is_active=True, id=pid)
                if self.scope.role != "admin":
                    qs_by_id = qs_by_id.filter(id__in=self.scope.project_ids)
                p = qs_by_id.first()
                if p:
                    return p

        term = (entities.get("obra") or "").strip()
        qs = Project.objects.filter(is_active=True)
        if self.scope.role != "admin":
            qs = qs.filter(id__in=self.scope.project_ids)
        if term:
            project = qs.filter(name__icontains=term).first() or qs.filter(code__icontains=term).first()
            return project
        return qs.order_by("-created_at").first()

