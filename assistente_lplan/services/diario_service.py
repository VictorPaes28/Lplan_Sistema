import re
from datetime import datetime, timedelta
from urllib.parse import quote

from django.core import signing
from django.urls import reverse
from django.utils import timezone

from assistente_lplan.schemas import AssistantResponse
from assistente_lplan.services.messages import MessageCatalog
from core.models import ConstructionDiary, DiaryStatus, Project


class DiarioAssistantService:
    RDO_PERIOD_SIGN_SALT = "assistente.rdo-period-pdf.v1"

    def __init__(self, scope, user=None):
        self.scope = scope
        self.user = user

    def _user_id(self) -> int:
        if not self.user or not getattr(self.user, "is_authenticated", False):
            return 0
        return int(self.user.pk)

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

    def consultar_rdo_por_data(self, entities: dict) -> AssistantResponse:
        target_date = self._resolve_target_date(entities)
        if not target_date:
            msg = MessageCatalog.resolve("assistant.diario.date_missing", {"domain": "obras"})
            return AssistantResponse(
                summary=msg["text"],
                alerts=[{"level": "warning", "message": msg["next_steps"][0]}],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )

        qs = ConstructionDiary.objects.select_related("project", "created_by").filter(date=target_date)
        project = None
        if entities.get("obra") or entities.get("project_id"):
            project = self._resolve_project(entities)
            if not project:
                msg = MessageCatalog.resolve("assistant.obras.project_missing", {"domain": "obras"})
                return AssistantResponse(
                    summary=msg["text"],
                    alerts=[{"level": "warning", "message": msg["next_steps"][0]}],
                    raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
                )
            qs = qs.filter(project=project)
        elif self.scope.role != "admin":
            qs = qs.filter(project_id__in=self.scope.project_ids)

        diaries = list(qs.order_by("-report_number", "project__code")[:30])
        if not diaries:
            date_label = target_date.strftime("%d/%m/%Y")
            msg = MessageCatalog.resolve("assistant.diario.date_empty", {"domain": "obras", "data": date_label})
            return AssistantResponse(
                summary=msg["text"],
                badges=["Sem dados suficientes", "RDO"],
                alerts=[{"level": "info", "message": msg["next_steps"][0]}],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"], "data": target_date.isoformat()},
            )

        rows = []
        for d in diaries:
            rows.append(
                {
                    "obra": d.project.code if d.project else "-",
                    "projeto": d.project.name if d.project else "-",
                    "data": d.date.strftime("%d/%m/%Y") if d.date else "-",
                    "rdo": f"#{d.report_number}" if d.report_number else "-",
                    "status": d.get_status_display(),
                    "responsavel": (d.created_by.get_full_name() or d.created_by.username) if d.created_by else "-",
                }
            )

        obra_label = project.code if project else "seu escopo"
        date_label = target_date.strftime("%d/%m/%Y")
        return AssistantResponse(
            summary=f"Foram encontrados {len(rows)} RDO(s) em {date_label} para {obra_label}.",
            cards=[
                {"title": "RDOs na data", "value": str(len(rows)), "tone": "info"},
                {"title": "Obras com RDO", "value": str(len({r['obra'] for r in rows})), "tone": "secondary"},
            ],
            table={
                "caption": f"RDOs de {date_label}",
                "columns": ["obra", "projeto", "data", "rdo", "status", "responsavel"],
                "rows": rows,
            },
            badges=["Diario de Obras", "RDO por data"],
            raw_data={"data": target_date.isoformat(), "project_id": getattr(project, "id", None)},
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

    @staticmethod
    def _resolve_target_date(entities: dict):
        raw_date = str((entities or {}).get("data") or "").strip()
        if not raw_date:
            return None

        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(raw_date, fmt).date()
            except ValueError:
                continue
        return None

    def relatorio_rdo_periodo_pdf(self, entities: dict, user_question: str = "") -> AssistantResponse:
        """Prepara link assinado para PDF consolidado dos últimos N dias (1–30) de RDO."""
        project = self._resolve_project(entities)
        if not project:
            msg = MessageCatalog.resolve("assistant.obras.project_missing", {"domain": "obras"})
            return AssistantResponse(
                summary=msg["text"],
                alerts=[{"level": "warning", "message": msg["next_steps"][0]}],
                raw_data={"message_code": msg["code"], "message_kind": msg["kind"]},
            )

        nd = self._resolve_ndias(entities, user_question)
        date_to = timezone.now().date()
        date_from = date_to - timedelta(days=max(1, nd) - 1)

        diaries_n = ConstructionDiary.objects.filter(
            project=project, date__gte=date_from, date__lte=date_to
        ).count()
        if diaries_n == 0:
            return AssistantResponse(
                summary=(
                    f"Nao ha diarios (RDO) registrados entre {date_from.strftime('%d/%m/%Y')} e "
                    f"{date_to.strftime('%d/%m/%Y')} na obra {project.code}."
                ),
                badges=["RDO", "Sem registros"],
                alerts=[{"level": "info", "message": "Crie ou aprove RDOs nesse intervalo para gerar o PDF."}],
                actions=[{"label": "Abrir relatorios", "url": "/reports/", "style": "primary"}],
                links=[{"label": "Relatorios da obra", "url": "/reports/"}],
                raw_data={"project_id": project.id, "date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
            )

        uid = self._user_id()
        if not uid:
            return AssistantResponse(
                summary="Sessao invalida para gerar link de download do PDF.",
                badges=["Erro"],
                alerts=[{"level": "error", "message": "Faca login novamente."}],
            )

        token = signing.dumps(
            {"u": uid, "p": project.id, "d0": date_from.isoformat(), "d1": date_to.isoformat()},
            salt=self.RDO_PERIOD_SIGN_SALT,
        )
        download_path = f"{reverse('assistente_lplan:rdo_period_pdf')}?t={quote(token, safe='')}"

        return AssistantResponse(
            summary=(
                f"PDF consolidado do RDO da obra {project.code}: ultimos {nd} dia(s) "
                f"({date_from.strftime('%d/%m/%Y')} a {date_to.strftime('%d/%m/%Y')}), "
                f"{diaries_n} dia(s) com registro. Clique para baixar. "
                "O documento reune textos e atividades; fotos e anexos seguem nos PDFs por dia."
            ),
            cards=[
                {"title": "Janela (dias)", "value": str(nd), "tone": "info"},
                {"title": "Dias com RDO", "value": str(diaries_n), "tone": "success"},
            ],
            badges=["RDO", "PDF", project.code],
            actions=[{"label": "Baixar PDF consolidado", "url": download_path, "style": "primary"}],
            links=[
                {"label": "Relatorios da obra", "url": "/reports/"},
                {"label": "Baixar PDF", "url": download_path},
            ],
            raw_data={
                "project_id": project.id,
                "dias": nd,
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "diarios_no_periodo": diaries_n,
            },
        )

    def _resolve_ndias(self, entities: dict, user_question: str) -> int:
        raw = (entities or {}).get("dias") or (entities or {}).get("ndias")
        if raw is not None and str(raw).strip().isdigit():
            return max(1, min(30, int(str(raw).strip())))
        text = (user_question or "").lower()
        m = re.search(r"(?:últimos?|ultimos?)\s*(\d{1,2})\s*dias?", text)
        if m:
            return max(1, min(30, int(m.group(1))))
        m = re.search(r"\b(\d{1,2})\s*dias?\b", text)
        if m:
            return max(1, min(30, int(m.group(1))))
        if "duas semanas" in text or "2 semanas" in text:
            return 14
        if "uma semana" in text or "1 semana" in text:
            return 7
        if "mes" in text and "um" in text:
            return 30
        return 15

