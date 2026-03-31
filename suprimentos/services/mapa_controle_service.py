from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Q, Sum

from mapa_obras.models import LocalObra, Obra
from suprimentos.models import ItemMapa


@dataclass
class MapaControleFilters:
    categoria: str = ""
    local_id: str = ""
    prioridade: str = ""
    status: str = ""
    search: str = ""
    limit: int = 200


class MapaControleService:
    """
    Serviço de agregação do Mapa de Controle (MVP suprimentos).

    Contrato do summary:
    - obra: metadados da obra selecionada
    - kpis: indicadores numéricos do painel
    - ranking: top pendências por local/categoria/fornecedor
    - distribuicao_status: total por status textual da etapa
    - quem_cobrar: total por responsável da ação
    - filtros: valores atuais + opções de dropdown

    Contrato do items:
    - items: lista detalhada de pendências/itens filtrados
    - total: total da lista antes de truncar
    - limit: limite aplicado
    """

    STATUS_CHOICES = [
        ("", "Todos"),
        ("sem_sc", "Sem SC"),
        ("sem_pc", "Com SC e sem PC"),
        ("sem_entrega", "Com PC e sem entrega"),
        ("sem_alocacao", "Recebido sem alocação"),
        ("atrasado", "Atrasados"),
        ("parcial", "Alocação parcial"),
        ("entregue", "Entregues"),
    ]

    def __init__(self, obra: Obra, filters: MapaControleFilters):
        self.obra = obra
        self.filters = filters

    def _base_queryset(self):
        queryset = (
            ItemMapa.objects.filter(obra=self.obra, nao_aplica=False)
            .select_related("obra", "insumo", "local_aplicacao")
            .annotate(quantidade_alocada_annotated=Sum("alocacoes__quantidade_alocada"))
        )

        if self.filters.categoria:
            queryset = queryset.filter(categoria=self.filters.categoria)
        if self.filters.local_id:
            queryset = queryset.filter(local_aplicacao_id=self.filters.local_id)
        if self.filters.prioridade:
            queryset = queryset.filter(prioridade=self.filters.prioridade)
        if self.filters.search:
            s = self.filters.search.strip()
            queryset = queryset.filter(
                Q(insumo__descricao__icontains=s)
                | Q(insumo__codigo_sienge__icontains=s)
                | Q(descricao_override__icontains=s)
                | Q(numero_sc__icontains=s)
                | Q(numero_pc__icontains=s)
                | Q(empresa_fornecedora__icontains=s)
                | Q(responsavel__icontains=s)
                | Q(local_aplicacao__nome__icontains=s)
            )
        return queryset.order_by("categoria", "insumo__descricao")

    @staticmethod
    def _matches_status(item: ItemMapa, status: str) -> bool:
        if not status:
            return True
        if status == "sem_sc":
            return not (item.numero_sc or "").strip()
        if status == "sem_pc":
            return bool((item.numero_sc or "").strip()) and not (item.numero_pc or "").strip()
        if status == "sem_entrega":
            return bool((item.numero_pc or "").strip()) and item.quantidade_recebida_obra <= 0
        if status == "sem_alocacao":
            return item.quantidade_recebida_obra > 0 and item.quantidade_alocada_local <= 0
        if status == "atrasado":
            return item.is_atrasado
        if status == "parcial":
            return item.status_etapa == "5) ALOCAÇÃO PARCIAL"
        if status == "entregue":
            return item.status_etapa == "ENTREGUE"
        return True

    def _filtered_items(self) -> list[ItemMapa]:
        items = list(self._base_queryset())
        if self.filters.status:
            items = [i for i in items if self._matches_status(i, self.filters.status)]
        return items

    @staticmethod
    def _to_float(value: Decimal | float | int | None) -> float:
        if value is None:
            return 0.0
        return float(value)

    def build_summary_payload(self) -> dict[str, Any]:
        items = self._filtered_items()
        total = len(items)
        sem_sc = sum(1 for i in items if not (i.numero_sc or "").strip())
        sem_pc = sum(1 for i in items if (i.numero_sc or "").strip() and not (i.numero_pc or "").strip())
        sem_entrega = sum(1 for i in items if (i.numero_pc or "").strip() and i.quantidade_recebida_obra <= 0)
        sem_alocacao = sum(1 for i in items if i.quantidade_recebida_obra > 0 and i.quantidade_alocada_local <= 0)
        atrasados = sum(1 for i in items if i.is_atrasado)
        percentual_medio_alocacao = round(
            (sum(self._to_float(i.percentual_alocado_porcentagem) for i in items) / total) if total else 0.0, 2
        )

        ranking_local: dict[str, int] = {}
        ranking_categoria: dict[str, int] = {}
        ranking_fornecedor: dict[str, int] = {}
        distribuicao_status: dict[str, int] = {}
        quem_cobrar: dict[str, int] = {}

        for item in items:
            local_nome = item.local_aplicacao.nome if item.local_aplicacao else "Sem local"
            categoria = item.categoria or "A CLASSIFICAR"
            fornecedor = item.empresa_fornecedora or "Sem fornecedor"
            status = item.status_etapa or "INDEFINIDO"
            owner = item.quem_cobrar or "SEM AÇÃO"

            pendente = status != "ENTREGUE"
            if pendente:
                ranking_local[local_nome] = ranking_local.get(local_nome, 0) + 1
                ranking_categoria[categoria] = ranking_categoria.get(categoria, 0) + 1
                ranking_fornecedor[fornecedor] = ranking_fornecedor.get(fornecedor, 0) + 1

            distribuicao_status[status] = distribuicao_status.get(status, 0) + 1
            quem_cobrar[owner] = quem_cobrar.get(owner, 0) + 1

        categorias = list(
            ItemMapa.objects.filter(obra=self.obra, nao_aplica=False)
            .values_list("categoria", flat=True)
            .distinct()
            .order_by("categoria")
        )
        locais = list(LocalObra.objects.filter(obra=self.obra).order_by("tipo", "nome").values("id", "nome"))

        return {
            "obra": {
                "id": self.obra.id,
                "nome": self.obra.nome,
                "codigo_sienge": self.obra.codigo_sienge,
            },
            "kpis": {
                "total_itens": total,
                "sem_sc": sem_sc,
                "sem_pc": sem_pc,
                "sem_entrega": sem_entrega,
                "sem_alocacao": sem_alocacao,
                "atrasados": atrasados,
                "percentual_medio_alocacao": percentual_medio_alocacao,
            },
            "ranking": {
                "locais": sorted(ranking_local.items(), key=lambda x: x[1], reverse=True)[:5],
                "categorias": sorted(ranking_categoria.items(), key=lambda x: x[1], reverse=True)[:5],
                "fornecedores": sorted(ranking_fornecedor.items(), key=lambda x: x[1], reverse=True)[:5],
            },
            "distribuicao_status": sorted(distribuicao_status.items(), key=lambda x: x[1], reverse=True),
            "quem_cobrar": sorted(quem_cobrar.items(), key=lambda x: x[1], reverse=True),
            "filtros": {
                "values": {
                    "categoria": self.filters.categoria,
                    "local_id": self.filters.local_id,
                    "prioridade": self.filters.prioridade,
                    "status": self.filters.status,
                    "search": self.filters.search,
                },
                "options": {
                    "categorias": [c for c in categorias if c],
                    "locais": locais,
                    "prioridades": [{"id": c[0], "label": c[1]} for c in ItemMapa.PRIORIDADE_CHOICES],
                    "status": [{"id": s[0], "label": s[1]} for s in self.STATUS_CHOICES],
                },
            },
        }

    def build_items_payload(self) -> dict[str, Any]:
        items = self._filtered_items()
        total = len(items)
        limit = max(1, min(self.filters.limit, 500))
        rows = []
        for item in items[:limit]:
            rows.append(
                {
                    "id": item.id,
                    "insumo_codigo": item.insumo.codigo_sienge,
                    "insumo_descricao": item.descricao_override or item.insumo.descricao,
                    "categoria": item.categoria,
                    "local": item.local_aplicacao.nome if item.local_aplicacao else "Sem local",
                    "responsavel": item.responsavel or "-",
                    "numero_sc": item.numero_sc or "-",
                    "numero_pc": item.numero_pc or "-",
                    "fornecedor": item.empresa_fornecedora or "-",
                    "status_etapa": item.status_etapa,
                    "status_css": item.status_css,
                    "quem_cobrar": item.quem_cobrar or "SEM AÇÃO",
                    "atrasado": bool(item.is_atrasado),
                    "qtd_planejada": self._to_float(item.quantidade_planejada),
                    "qtd_recebida_obra": self._to_float(item.quantidade_recebida_obra),
                    "qtd_alocada_local": self._to_float(item.quantidade_alocada_local),
                    "saldo_pendente_alocacao": self._to_float(item.saldo_pendente_alocacao),
                    "percentual_alocado": round(self._to_float(item.percentual_alocado_porcentagem), 2),
                }
            )
        return {"items": rows, "total": total, "limit": limit}
