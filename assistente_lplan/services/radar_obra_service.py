from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.models import ConstructionDiary, DiaryOccurrence, DiaryStatus, Project
from gestao_aprovacao.models import Approval, StatusHistory, WorkOrder
from mapa_obras.models import Obra as MapaObra
from suprimentos.models import ItemMapa, RecebimentoObra


@dataclass
class RadarResult:
    score: int
    level: str
    trend: str
    causes: list[str]
    recommended_action: dict
    secondary_actions: list[dict]
    links: list[dict]
    cards: list[dict]
    timeline: list[dict]
    alerts: list[dict]
    raw_components: dict


class RadarObraService:
    def __init__(self, project: Project):
        self.project = project

    def build(self) -> RadarResult:
        now = timezone.now().date()
        period_7_start = now - timedelta(days=7)
        period_14_start = now - timedelta(days=14)
        period_30_start = now - timedelta(days=30)
        period_60_start = now - timedelta(days=60)

        mapa_obra = MapaObra.objects.filter(codigo_sienge=self.project.code, ativa=True).first()
        suprimentos = self._calc_suprimentos(mapa_obra, period_7_start, now)
        aprovacoes = self._calc_aprovacoes(period_7_start, period_30_start, now)
        diario = self._calc_diario(period_7_start, period_30_start, now)
        historico = self._calc_historico(period_7_start, period_14_start, period_30_start, period_60_start, now, mapa_obra)

        score = self._weighted_score(
            suprimentos=suprimentos["score"],
            aprovacoes=aprovacoes["score"],
            diario=diario["score"],
            historico=historico["score"],
        )
        level = self.classify_risk(score)
        current_index = historico.get("current_index", 0.0)
        previous_index = historico.get("previous_index", 0.0)
        month_index = historico.get("month_index", 0.0)
        trend = self.determine_trend(current_index, previous_index, month_index)

        causes = [
            {"cause": f"Suprimentos: {suprimentos.get('cause', '')}", "score": suprimentos["score"]},
            {"cause": f"Aprovacoes: {aprovacoes.get('cause', '')}", "score": aprovacoes["score"]},
            {"cause": f"Diario: {diario.get('cause', '')}", "score": diario["score"]},
            {"cause": f"Historico: {historico.get('cause', '')}", "score": historico["score"]},
        ]
        causes.sort(key=lambda x: x["score"], reverse=True)
        top_causes = [c["cause"] for c in causes if c["score"] > 0][:3]

        recommended_action, secondary_actions, links = self._build_actions(causes[0]["cause"] if causes else "")
        alerts = self._build_alerts(level, trend, top_causes)

        cards = [
            {"title": "Radar de risco", "value": str(score), "tone": self._tone_by_risk(level)},
            {"title": "Nivel", "value": level, "tone": self._tone_by_risk(level)},
            {"title": "Tendencia", "value": trend, "tone": "warning" if trend == "Piorando" else "info"},
        ]
        timeline = [
            {"date": "7 dias", "label": "Indice de problemas", "value": str(round(current_index, 2))},
            {"date": "7 dias anteriores", "label": "Indice comparativo", "value": str(round(previous_index, 2))},
            {"date": "30 dias", "label": "Media de problemas", "value": str(round(month_index, 2))},
        ]

        return RadarResult(
            score=score,
            level=level,
            trend=trend,
            causes=top_causes,
            recommended_action=recommended_action,
            secondary_actions=secondary_actions,
            links=links,
            cards=cards,
            timeline=timeline,
            alerts=alerts,
            raw_components={
                "project": self.project.code,
                "mapa_obra": mapa_obra.codigo_sienge if mapa_obra else None,
                "critical": causes,
                "approvals": aprovacoes,
                "diary": diario,
                "history": historico,
                "suprimentos": suprimentos,
            },
        )

    @staticmethod
    def classify_risk(score: int) -> str:
        if score <= 30:
            return "BAIXO"
        if score <= 60:
            return "MEDIO"
        return "ALTO"

    @staticmethod
    def determine_trend(current_index: float, previous_index: float, month_index: float) -> str:
        previous_index = max(previous_index, 1.0)
        month_index = max(month_index, 1.0)
        if current_index >= previous_index * 1.15 or current_index >= month_index * 1.2:
            return "Piorando"
        if current_index <= previous_index * 0.85 and current_index <= month_index * 0.9:
            return "Melhorando"
        return "Estavel"

    @staticmethod
    def _weighted_score(suprimentos: int, aprovacoes: int, diario: int, historico: int) -> int:
        weights = {"suprimentos": 0.3, "aprovacoes": 0.25, "diario": 0.25, "historico": 0.2}
        score = (
            float(suprimentos) * weights.get("suprimentos", 0.3)
            + float(aprovacoes) * weights.get("aprovacoes", 0.25)
            + float(diario) * weights.get("diario", 0.25)
            + float(historico) * weights.get("historico", 0.2)
        )
        return max(0, min(int(round(score)), 100))

    def _calc_suprimentos(self, mapa_obra, period_7_start, now):
        if not mapa_obra:
            return {"score": 0, "cause": "", "itens_sem_aloc": 0, "entregue_nao_distrib": 0, "prazo_vencido": 0}

        items = ItemMapa.objects.filter(obra=mapa_obra, quantidade_planejada__gt=0).annotate(
            total_alocado=Coalesce(
                Sum("alocacoes__quantidade_alocada"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        itens_sem_aloc = items.filter(total_alocado__lte=0).count()
        prazo_vencido = items.filter(prazo_necessidade__lt=now, total_alocado__lt=F("quantidade_planejada")).count()
        prazo_proximo = items.filter(
            prazo_necessidade__gte=now,
            prazo_necessidade__lte=now + timedelta(days=7),
            total_alocado__lt=F("quantidade_planejada"),
        ).count()
        recebimentos = RecebimentoObra.objects.filter(obra=mapa_obra).annotate(
            total_alocado=Coalesce(Sum("alocacoes__quantidade_alocada"), Value(Decimal("0.00")))
        )
        entregue_nao_distrib = recebimentos.filter(quantidade_recebida__gt=0, total_alocado__lt=F("quantidade_recebida")).count()
        itens_7d = items.filter(criado_em__date__gte=period_7_start).count()

        score = min(100, int(itens_sem_aloc * 8 + entregue_nao_distrib * 10 + prazo_vencido * 4 + prazo_proximo * 2))
        cause = (
            f"{itens_sem_aloc} itens sem alocacao, {entregue_nao_distrib} recebimentos nao distribuidos, "
            f"{prazo_vencido} itens com prazo vencido."
        )
        return {
            "score": score,
            "cause": cause,
            "itens_sem_aloc": itens_sem_aloc,
            "entregue_nao_distrib": entregue_nao_distrib,
            "prazo_vencido": prazo_vencido,
            "prazo_proximo": prazo_proximo,
            "itens_7d": itens_7d,
        }

    def _calc_aprovacoes(self, period_7_start, period_30_start, now):
        orders = WorkOrder.objects.filter(obra__project=self.project)
        pendentes = orders.filter(status="pendente").count()
        reprov_recent = Approval.objects.filter(
            work_order__obra__project=self.project,
            decisao="reprovado",
            created_at__date__gte=period_30_start,
        ).count()
        # Aprovacao final fica no WorkOrder.data_aprovacao neste sistema.
        done_approvals = list(
            WorkOrder.objects.filter(obra__project=self.project)
            .exclude(data_aprovacao__isnull=True)
            .values_list("created_at", "data_aprovacao")
        )
        avg_days = 0.0
        if done_approvals:
            days = [max((aprov - created).total_seconds() / 86400.0, 0.0) for created, aprov in done_approvals]
            avg_days = sum(days) / len(days)

        prev_avg_days = (
            StatusHistory.objects.filter(created_at__date__gte=period_30_start, created_at__date__lt=period_7_start).count() or 0
        )
        score = min(100, int(pendentes * 7 + avg_days * 8 + reprov_recent * 3 + max(prev_avg_days, 0) * 0.1))
        cause = f"{pendentes} aprovacoes pendentes, media de {avg_days:.1f} dias para aprovar, {reprov_recent} reprovacoes recentes."
        return {
            "score": score,
            "cause": cause,
            "pendentes": pendentes,
            "avg_days": round(avg_days, 2),
            "prev_avg_days": round(float(prev_avg_days), 2),
            "reprov_recent": reprov_recent,
        }

    def _calc_diario(self, period_7_start, period_30_start, now):
        diaries_30 = ConstructionDiary.objects.filter(project=self.project, date__gte=period_30_start)
        critical_diaries_30 = diaries_30.filter(
            Q(stoppages__gt="") | Q(imminent_risks__gt="") | Q(accidents__gt="") | Q(incidents__gt="")
        ).count()
        critical_diaries_7 = ConstructionDiary.objects.filter(project=self.project, date__gte=period_7_start).filter(
            Q(stoppages__gt="") | Q(imminent_risks__gt="") | Q(accidents__gt="") | Q(incidents__gt="")
        ).count()

        occurrences_30 = DiaryOccurrence.objects.filter(diary__project=self.project, created_at__date__gte=period_30_start).count()
        occurrences_critical_30 = DiaryOccurrence.objects.filter(
            diary__project=self.project,
            created_at__date__gte=period_30_start,
        ).filter(Q(tags__name__icontains="atraso") | Q(tags__name__icontains="risco") | Q(tags__name__icontains="paralisa")).distinct().count()
        freq = min(int(occurrences_30 / 3), 40)
        score = min(100, int(critical_diaries_30 * 6 + occurrences_critical_30 * 4 + freq))
        cause = f"{critical_diaries_30} diarios com ocorrencias criticas em 30 dias, {occurrences_critical_30} ocorrencias criticas tagueadas."
        return {
            "score": score,
            "cause": cause,
            "critical_diaries_30": critical_diaries_30,
            "critical_diaries_7": critical_diaries_7,
            "occurrences_30": occurrences_30,
            "occurrences_critical_30": occurrences_critical_30,
            "freq": freq,
        }

    def _calc_historico(self, period_7_start, period_14_start, period_30_start, period_60_start, now, mapa_obra):
        pend_7 = WorkOrder.objects.filter(obra__project=self.project, status="pendente", created_at__date__gte=period_7_start).count()
        pend_prev7 = WorkOrder.objects.filter(
            obra__project=self.project,
            status="pendente",
            created_at__date__gte=period_14_start,
            created_at__date__lt=period_7_start,
        ).count()
        crit_7 = ConstructionDiary.objects.filter(project=self.project, date__gte=period_7_start).filter(
            Q(stoppages__gt="") | Q(imminent_risks__gt="") | Q(accidents__gt="")
        ).count()
        crit_prev7 = ConstructionDiary.objects.filter(project=self.project, date__gte=period_14_start, date__lt=period_7_start).filter(
            Q(stoppages__gt="") | Q(imminent_risks__gt="") | Q(accidents__gt="")
        ).count()
        sem_aloc_7 = 0
        sem_aloc_prev7 = 0
        if mapa_obra:
            items = ItemMapa.objects.filter(obra=mapa_obra, quantidade_planejada__gt=0).annotate(
                total_alocado=Coalesce(
                    Sum("alocacoes__quantidade_alocada"),
                    Value(Decimal("0.00")),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )
            sem_aloc_7 = items.filter(total_alocado__lte=0, atualizado_em__date__gte=period_7_start).count()
            sem_aloc_prev7 = items.filter(
                total_alocado__lte=0,
                atualizado_em__date__gte=period_14_start,
                atualizado_em__date__lt=period_7_start,
            ).count()

        status_events = StatusHistory.objects.filter(work_order__obra__project=self.project, created_at__date__gte=period_30_start).values(
            "status_novo"
        ).annotate(total=Count("id")).order_by("-total")
        top_status_sum = sum(row.get("total", 0) for row in status_events[:3])
        reprov_30 = Approval.objects.filter(work_order__obra__project=self.project, decisao="reprovado", created_at__date__gte=period_30_start).count()
        critical_tags = (
            Approval.objects.filter(work_order__obra__project=self.project, created_at__date__gte=period_30_start)
            .values("tags_erro__nome")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        top_tags = [row.get("tags_erro__nome") for row in critical_tags[:3] if row.get("tags_erro__nome")]

        current_index = float(pend_7 + crit_7 + sem_aloc_7 + reprov_30)
        previous_index = float(pend_prev7 + crit_prev7 + sem_aloc_prev7)
        month_index = float(max((current_index + previous_index) / 2.0, 1.0))
        score = min(100, int(current_index * 4.0 + top_status_sum * 0.2))
        cause = f"Indice de problemas 7d: {current_index} (vs {previous_index} na semana anterior), recorrencias de fluxo e tags."
        return {
            "score": score,
            "cause": cause,
            "current_index": current_index,
            "previous_index": previous_index,
            "month_index": month_index,
            "reprov_30": reprov_30,
            "top_tags": top_tags,
        }

    def _build_actions(self, principal_cause: str):
        diario_url = "/reports/"
        aprov_url = "/gestao/pedidos/"
        mapa_url = "/engenharia/mapa/"

        if "Suprimentos" in principal_cause:
            recommended = {
                "label": "Alocar itens pendentes no mapa de suprimentos",
                "url": mapa_url,
                "style": "primary",
                "is_primary": True,
            }
            secondary = [
                {"label": "Revisar itens com prazo vencido", "url": mapa_url, "style": "secondary"},
                {"label": "Ver pendencias da obra", "url": diario_url, "style": "secondary"},
                {"label": "Analisar pedidos pendentes", "url": aprov_url, "style": "secondary"},
            ]
        elif "Aprovacoes" in principal_cause:
            recommended = {
                "label": "Priorizar aprovacao dos pedidos pendentes criticos",
                "url": aprov_url,
                "style": "primary",
                "is_primary": True,
            }
            secondary = [
                {"label": "Revisar causas de reprovacao recorrente", "url": aprov_url, "style": "secondary"},
                {"label": "Ver impacto no diario", "url": diario_url, "style": "secondary"},
                {"label": "Checar suprimentos pendentes", "url": mapa_url, "style": "secondary"},
            ]
        elif "Diario" in principal_cause:
            recommended = {
                "label": "Tratar ocorrencias criticas no Diario de Obras",
                "url": diario_url,
                "style": "primary",
                "is_primary": True,
            }
            secondary = [
                {"label": "Validar pendencias de aprovacao ligadas", "url": aprov_url, "style": "secondary"},
                {"label": "Revisar material nao alocado", "url": mapa_url, "style": "secondary"},
                {"label": "Atualizar responsaveis da obra", "url": diario_url, "style": "secondary"},
            ]
        else:
            recommended = {
                "label": "Executar plano de contencao da obra (top pendencias)",
                "url": diario_url,
                "style": "primary",
                "is_primary": True,
            }
            secondary = [
                {"label": "Abrir pendencias de aprovacao", "url": aprov_url, "style": "secondary"},
                {"label": "Abrir mapa de suprimentos", "url": mapa_url, "style": "secondary"},
                {"label": "Revisar historico de ocorrencias", "url": diario_url, "style": "secondary"},
            ]

        links = [
            {"label": "Diario de Obras - Relatorios", "url": diario_url},
            {"label": "GestControll - Pedidos", "url": aprov_url},
            {"label": "Mapa de Suprimentos", "url": mapa_url},
        ]
        return recommended, secondary[:3], links

    @staticmethod
    def _build_alerts(level: str, trend: str, top_causes: list[str]) -> list[dict]:
        alerts = []
        if level == "ALTO":
            alerts.append({"level": "error", "message": "Risco alto exige acao imediata."})
        elif level == "MEDIO":
            alerts.append({"level": "warning", "message": "Risco medio: monitore os gargalos e execute plano de acao."})
        else:
            alerts.append({"level": "info", "message": "Risco baixo no momento."})
        if trend == "Piorando":
            alerts.append({"level": "warning", "message": "Tendencia piorando nos ultimos dias."})
        if top_causes:
            alerts.append({"level": "info", "message": f"Principal causa: {top_causes[0]}"})
        return alerts

    @staticmethod
    def _tone_by_risk(level: str) -> str:
        if level == "ALTO":
            return "danger"
        if level == "MEDIO":
            return "warning"
        return "success"

