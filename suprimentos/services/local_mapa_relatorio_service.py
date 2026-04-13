"""
Relatório operacional por local (apartamento/unidade) no Mapa de Controle.

Contrato reutilizável: agrega fatos numéricos + comparativo com outros locais da mesma obra,
sem depender de LLM para os números (a narrativa é opcional em cima deste dict).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from django.db.models import Sum

from mapa_obras.models import LocalObra, Obra
from suprimentos.models import ItemMapa
from suprimentos.services.mapa_controle_service import MapaControleService


def _to_float(value) -> float:
    if value is None:
        return 0.0
    return float(value)


@dataclass
class LocalMapaSnapshot:
    local_id: int
    nome: str
    tipo: str
    total: int
    entregues: int
    pendentes: int
    pct_medio_alocacao: float
    sem_sc: int
    sem_pc: int
    sem_entrega: int
    sem_alocacao: int
    atrasados: int
    parciais: int
    saude_score: float
    ranking_pendencias: int  # 1 = mais pendentes na obra


class LocalMapaRelatorioService:
    """Métricas de ItemMapa por local + benchmark na obra."""

    def __init__(self, obra: Obra):
        self.obra = obra

    def _items_annotated(self):
        return (
            ItemMapa.objects.filter(obra=self.obra, nao_aplica=False)
            .select_related("insumo", "local_aplicacao")
            .annotate(quantidade_alocada_annotated=Sum("alocacoes__quantidade_alocada"))
        )

    @staticmethod
    def _counts_for_items(items: list[ItemMapa]) -> dict[str, int]:
        m = MapaControleService
        total = len(items)
        entregues = sum(1 for i in items if i.status_etapa == "ENTREGUE")
        sem_sc = sum(1 for i in items if m._matches_status(i, "sem_sc"))
        sem_pc = sum(1 for i in items if m._matches_status(i, "sem_pc"))
        sem_entrega = sum(1 for i in items if m._matches_status(i, "sem_entrega"))
        sem_alocacao = sum(1 for i in items if m._matches_status(i, "sem_alocacao"))
        atrasados = sum(1 for i in items if m._matches_status(i, "atrasado"))
        parciais = sum(1 for i in items if m._matches_status(i, "parcial"))
        pendentes = sum(1 for i in items if (i.status_etapa or "") != "ENTREGUE")
        return {
            "total": total,
            "entregues": entregues,
            "pendentes": pendentes,
            "sem_sc": sem_sc,
            "sem_pc": sem_pc,
            "sem_entrega": sem_entrega,
            "sem_alocacao": sem_alocacao,
            "atrasados": atrasados,
            "parciais": parciais,
        }

    @staticmethod
    def _saude_score(c: dict[str, int], pct_medio_aloc: float) -> float:
        """0–100: entrega + alocação média, penaliza riscos operacionais."""
        tot = c["total"]
        if tot <= 0:
            return 0.0
        pct_ent = (c["entregues"] / tot) * 100.0
        # Penalidades proporcionais ao volume
        pen = (
            (c["atrasados"] / tot) * 28.0
            + (c["sem_sc"] / tot) * 18.0
            + (c["sem_pc"] / tot) * 12.0
            + (c["sem_entrega"] / tot) * 10.0
            + (c["sem_alocacao"] / tot) * 14.0
            + (c["parciais"] / tot) * 6.0
        )
        base = 0.55 * pct_ent + 0.45 * min(pct_medio_aloc, 100.0)
        return max(0.0, min(100.0, base - pen))

    def build_snapshots_por_local(self) -> dict[int, LocalMapaSnapshot]:
        by_local: dict[int, list[ItemMapa]] = {}
        for item in self._items_annotated():
            lid = item.local_aplicacao_id
            if not lid:
                continue
            by_local.setdefault(lid, []).append(item)

        snapshots: dict[int, LocalMapaSnapshot] = {}
        for lid, items in by_local.items():
            loc = items[0].local_aplicacao
            nome = loc.nome if loc else f"#{lid}"
            tipo = (loc.tipo if loc else "OUTRO") or "OUTRO"
            c = self._counts_for_items(items)
            pct_medio = (
                round(sum(_to_float(i.percentual_alocado_porcentagem) for i in items) / c["total"], 2)
                if c["total"]
                else 0.0
            )
            saude = self._saude_score(c, pct_medio)
            snapshots[lid] = LocalMapaSnapshot(
                local_id=lid,
                nome=nome,
                tipo=tipo,
                total=c["total"],
                entregues=c["entregues"],
                pendentes=c["pendentes"],
                pct_medio_alocacao=pct_medio,
                sem_sc=c["sem_sc"],
                sem_pc=c["sem_pc"],
                sem_entrega=c["sem_entrega"],
                sem_alocacao=c["sem_alocacao"],
                atrasados=c["atrasados"],
                parciais=c["parciais"],
                saude_score=round(saude, 1),
                ranking_pendencias=0,
            )

        # Ranking: mais pendentes = pior (1º lugar)
        ordered = sorted(snapshots.values(), key=lambda s: (-s.pendentes, -s.atrasados, s.nome))
        for idx, s in enumerate(ordered, start=1):
            snapshots[s.local_id].ranking_pendencias = idx

        return snapshots

    def build_facts_for_local(self, local: LocalObra) -> dict[str, Any]:
        all_snap = self.build_snapshots_por_local()
        items = [i for i in self._items_annotated() if i.local_aplicacao_id == local.id]
        c = self._counts_for_items(items)
        pct_medio = (
            round(sum(_to_float(i.percentual_alocado_porcentagem) for i in items) / c["total"], 2)
            if c["total"]
            else 0.0
        )
        saude = self._saude_score(c, pct_medio)

        cur = all_snap.get(local.id)
        rank = cur.ranking_pendencias if cur else 0
        n_locais = len(all_snap)

        # Médias na obra (apenas locais com itens)
        if all_snap:
            media_pend = sum(s.pendentes for s in all_snap.values()) / n_locais
            media_saude = sum(s.saude_score for s in all_snap.values()) / n_locais
            media_pct = sum(s.pct_medio_alocacao for s in all_snap.values()) / n_locais
        else:
            media_pend = media_saude = media_pct = 0.0

        piores = sorted(all_snap.values(), key=lambda s: (-s.pendentes, -s.atrasados))[:4]
        melhores = sorted(all_snap.values(), key=lambda s: (-s.saude_score, -s.entregues))[:3]

        def _snap_dict(s: LocalMapaSnapshot) -> dict[str, Any]:
            return {
                "nome": s.nome,
                "tipo": s.tipo,
                "pendentes": s.pendentes,
                "atrasados": s.atrasados,
                "saude_score": s.saude_score,
                "pct_medio_alocacao": s.pct_medio_alocacao,
            }

        comparativo = {
            "media_pendentes_por_local": round(media_pend, 2),
            "media_saude_score": round(media_saude, 1),
            "media_pct_alocacao": round(media_pct, 2),
            "total_locais_com_itens": n_locais,
            "posicao_ranking_pendencias": rank,
            "piores_locais": [_snap_dict(s) for s in piores if s.local_id != local.id][:3],
            "referencia_melhores": [_snap_dict(s) for s in melhores if s.local_id != local.id][:2],
        }

        pct_entregues = round((c["entregues"] / c["total"]) * 100, 1) if c["total"] else 0.0
        veredito = self._veredito(saude, c, pct_medio, media_pend, rank, n_locais)

        distrib = {}
        for i in items:
            st = i.status_etapa or "INDEFINIDO"
            distrib[st] = distrib.get(st, 0) + 1

        top_cats: dict[str, int] = {}
        for i in items:
            if (i.status_etapa or "") == "ENTREGUE":
                continue
            cat = i.categoria or "A CLASSIFICAR"
            top_cats[cat] = top_cats.get(cat, 0) + 1
        top_pend_categorias = sorted(top_cats.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "obra_codigo": self.obra.codigo_sienge,
            "obra_nome": self.obra.nome,
            "local": {
                "id": local.id,
                "nome": local.nome,
                "tipo": local.tipo,
            },
            "kpis": {
                "total_itens": c["total"],
                "pct_linhas_entregues": pct_entregues,
                "pct_medio_alocacao": pct_medio,
                "pendentes": c["pendentes"],
                "entregues": c["entregues"],
                "sem_sc": c["sem_sc"],
                "sem_pc": c["sem_pc"],
                "sem_entrega": c["sem_entrega"],
                "sem_alocacao": c["sem_alocacao"],
                "atrasados": c["atrasados"],
                "parciais": c["parciais"],
                "saude_score": round(saude, 1),
            },
            "distribuicao_status_etapa": sorted(distrib.items(), key=lambda x: -x[1]),
            "categorias_mais_pendentes": [{"categoria": a, "pendentes": b} for a, b in top_pend_categorias],
            "comparativo_obra": comparativo,
            "veredito": veredito,
        }

    @staticmethod
    def _veredito(
        saude: float,
        c: dict[str, int],
        pct_medio: float,
        media_pend: float,
        rank: int,
        n_locais: int,
    ) -> dict[str, Any]:
        nivel = "bom"
        if c["total"] == 0:
            nivel = "atencao"
        elif saude < 45 or (c["total"] and c["atrasados"] >= max(3, c["total"] // 4)):
            nivel = "critico"
        elif saude < 70 or c["sem_sc"] > 0 or c["atrasados"] > 0:
            nivel = "atencao"

        fatores_positivos = []
        fatores_risco = []
        if c["entregues"] == c["total"] and c["total"]:
            fatores_positivos.append("Todas as linhas do mapa estao entregues para este local.")
        if pct_medio >= 85:
            fatores_positivos.append(f"Alocacao media elevada ({pct_medio:.1f}%).")
        if c["atrasados"]:
            fatores_risco.append(f"{c['atrasados']} linha(s) em atraso operacional.")
        if c["sem_sc"]:
            fatores_risco.append(f"{c['sem_sc']} sem SC (levantamento/compra nao iniciada).")
        if c["sem_pc"] and not c["sem_sc"]:
            fatores_risco.append(f"{c['sem_pc']} com SC mas sem PC (compras).")
        if c["sem_entrega"]:
            fatores_risco.append(f"{c['sem_entrega']} aguardando entrega na obra.")
        if c["sem_alocacao"]:
            fatores_risco.append(f"{c['sem_alocacao']} recebido(s) sem alocacao no local.")
        if n_locais > 1 and rank <= 3 and c["pendentes"] > media_pend:
            fatores_risco.append(
                f"Entre os locais com mais pendencias na obra (posicao {rank} de {n_locais})."
            )
        if n_locais > 1 and rank >= n_locais - 1 and c["pendentes"] < media_pend and c["pendentes"] > 0:
            fatores_positivos.append("Menos pendencias que a media dos demais locais.")
        if c["total"] == 0:
            fatores_risco.append("Nao ha linhas do mapa vinculadas a este local (verifique cadastro ou importacao).")

        return {
            "nivel": nivel,
            "fatores_positivos": fatores_positivos,
            "fatores_risco": fatores_risco,
        }


def find_local_obra(
    obra: Obra,
    *,
    referencia: str = "",
    texto_usuario: str = "",
    local_id: str = "",
) -> LocalObra | None:
    """Resolve LocalObra por id, texto livre ou melhor match no texto do usuario."""
    if local_id:
        try:
            lid = int(local_id)
        except (TypeError, ValueError):
            lid = None
        if lid:
            return LocalObra.objects.filter(obra=obra, pk=lid).first()

    locais = list(LocalObra.objects.filter(obra=obra))
    if not locais:
        return None

    combined = f"{referencia} {texto_usuario}".strip().lower()
    if not combined:
        return None

    best: LocalObra | None = None
    best_score = 0.0

    for loc in locais:
        nome = (loc.nome or "").strip()
        if not nome:
            continue
        nl = nome.lower()
        score = 0.0
        if nl in combined:
            score = 80.0 + min(len(nl), 40)
        else:
            sm = SequenceMatcher(None, combined, nl).ratio()
            score = sm * 55.0
            ref_tokens = set(re.findall(r"[a-z0-9]+", referencia.lower())) if referencia else set()
            nome_tokens = set(re.findall(r"[a-z0-9]+", nl))
            inter = ref_tokens & nome_tokens
            if len(inter) >= 1:
                score += 12.0 * len(inter)
            ctokens = set(re.findall(r"[a-z0-9]+", combined))
            inter2 = nome_tokens & ctokens
            score += 5.0 * min(len(inter2), 6)

        if score > best_score:
            best_score = score
            best = loc

    if best_score < 22.0:
        return None
    return best
