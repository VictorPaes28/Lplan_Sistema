"""
Reconhecimento e resolução de obra por código, nome ou sigla no escopo do usuário.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from core.models import Project

from assistente_lplan.services.permissions import UserScope


def obra_display_name(source=None, *, fallback: str = "OBRA") -> str:
    """Nome da obra em maiúsculas para textos exibidos ao usuário (sem código)."""
    if source is None:
        return fallback
    if isinstance(source, str):
        text = source.strip()
        return text.upper() if text else fallback
    if isinstance(source, dict):
        raw = (
            source.get("name")
            or source.get("nome")
            or source.get("project_name")
            or source.get("obra_nome")
            or ""
        ).strip()
        return raw.upper() if raw else fallback
    name = getattr(source, "name", None) or getattr(source, "nome", None)
    if name and str(name).strip():
        return str(name).strip().upper()
    return fallback


def normalize_obra_lookup(value: str) -> str:
    raw = (value or "").lower().strip()
    raw = unicodedata.normalize("NFD", raw)
    raw = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", raw).strip()


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize_obra_lookup(value))


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


@dataclass(frozen=True)
class ObraCatalogEntry:
    id: int
    code: str
    name: str
    sigla: str
    code_norm: str
    name_norm: str
    sigla_norm: str


def projects_catalog(scope: UserScope) -> list[ObraCatalogEntry]:
    qs = Project.objects.filter(is_active=True).order_by("code")
    if scope.role != "admin":
        if not scope.project_ids:
            return []
        qs = qs.filter(id__in=scope.project_ids)

    rows: list[ObraCatalogEntry] = []
    for p in qs:
        code = (p.code or "").strip()
        name = (p.name or "").strip()
        sigla = (p.sigla or "").strip()
        rows.append(
            ObraCatalogEntry(
                id=p.id,
                code=code,
                name=name,
                sigla=sigla,
                code_norm=normalize_obra_lookup(code),
                name_norm=normalize_obra_lookup(name),
                sigla_norm=normalize_obra_lookup(sigla),
            )
        )
    return rows


def _word_in_text(term_norm: str, text_norm: str) -> bool:
    if not term_norm or not text_norm:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(term_norm)}(?![a-z0-9])"
    return re.search(pattern, text_norm) is not None


def _score_term_match(term: str, entry: ObraCatalogEntry) -> tuple[float, str]:
    term_norm = normalize_obra_lookup(term)
    if not term_norm:
        return 0.0, ""

    if term_norm == entry.code_norm:
        return 1.0, "code"
    if entry.sigla_norm and term_norm == entry.sigla_norm:
        return 0.98, "sigla"
    if entry.code_norm and term_norm in entry.code_norm:
        return 0.92, "code"
    if entry.sigla_norm and term_norm in entry.sigla_norm:
        return 0.9, "sigla"
    if entry.name_norm and term_norm in entry.name_norm:
        return 0.88, "name"
    if entry.name_norm and entry.name_norm in term_norm:
        return 0.86, "name"

    best = 0.0
    field = ""
    for label, candidate in (
        ("code", entry.code_norm),
        ("sigla", entry.sigla_norm),
        ("name", entry.name_norm),
    ):
        if not candidate:
            continue
        ratio = _similarity(term_norm, candidate)
        if ratio > best:
            best = ratio
            field = label
    if best >= 0.82:
        return best, field
    return 0.0, ""


def _score_text_scan(text_norm: str, entry: ObraCatalogEntry) -> tuple[float, str]:
    best = 0.0
    field = ""

    if entry.name_norm and len(entry.name_norm) >= 4 and entry.name_norm in text_norm:
        return 0.94 + min(len(entry.name_norm) / 200.0, 0.05), "name"

    if entry.sigla_norm and len(entry.sigla_norm) >= 2 and _word_in_text(entry.sigla_norm, text_norm):
        score = 0.93 if len(entry.sigla_norm) >= 3 else 0.88
        return score, "sigla"

    if entry.code_norm and len(entry.code_norm) >= 2 and _word_in_text(entry.code_norm, text_norm):
        return 0.9, "code"

    tokens = _tokenize(text_norm)
    for token in tokens:
        for label, candidate in (
            ("code", entry.code_norm),
            ("sigla", entry.sigla_norm),
        ):
            if not candidate or len(candidate) < 2:
                continue
            if token == candidate:
                score = 0.91 if label == "code" else 0.9
                if score > best:
                    best = score
                    field = label
            elif len(token) >= 3 and len(candidate) >= 3:
                ratio = _similarity(token, candidate)
                if ratio >= 0.86 and ratio > best:
                    best = ratio
                    field = label

    return best, field


def find_obra_match(
    text: str,
    scope: UserScope,
    *,
    obra_term: str | None = None,
) -> dict | None:
    """
    Localiza obra no texto ou no termo explícito (ex.: após 'obra ...').
    Retorna {id, code, name, sigla, label, field, score} ou None.
    """
    catalog = projects_catalog(scope)
    if not catalog:
        return None

    text_norm = normalize_obra_lookup(text)
    best_entry: ObraCatalogEntry | None = None
    best_score = 0.0
    best_field = ""

    term = (obra_term or "").strip()
    if term and term.lower() not in {"atual", "selecionada", "selecionado", "corrente"}:
        for entry in catalog:
            score, field = _score_term_match(term, entry)
            if score > best_score:
                best_score = score
                best_entry = entry
                best_field = field

    if best_score < 0.82:
        for entry in catalog:
            score, field = _score_text_scan(text_norm, entry)
            if score > best_score:
                best_score = score
                best_entry = entry
                best_field = field

    if not best_entry or best_score < 0.82:
        return None

    return {
        "id": best_entry.id,
        "code": best_entry.code,
        "name": best_entry.name,
        "sigla": best_entry.sigla,
        "label": best_entry.code or best_entry.sigla or best_entry.name,
        "field": best_field,
        "score": round(best_score, 3),
    }


def enrich_obra_entities(entities: dict, text: str, scope: UserScope | None) -> dict:
    """Preenche project_id e obra quando reconhece código, nome ou sigla no escopo."""
    if not scope:
        return entities
    if entities.get("project_id"):
        return entities

    out = dict(entities)
    match = find_obra_match(text, scope, obra_term=out.get("obra"))
    if not match:
        return out

    out["project_id"] = match["id"]
    out["obra"] = match["label"]
    out["obra_match_field"] = match["field"]
    return out


def resolve_project_from_entities(
    entities: dict,
    scope: UserScope,
    *,
    allow_default: bool = True,
):
    """Resolve Project a partir de project_id ou termo obra (código, nome, sigla)."""
    project_id = entities.get("project_id")
    if project_id:
        try:
            pid = int(project_id)
        except (TypeError, ValueError):
            pid = None
        if pid:
            qs_by_id = Project.objects.filter(is_active=True, id=pid)
            if scope.role != "admin":
                qs_by_id = qs_by_id.filter(id__in=scope.project_ids)
            project = qs_by_id.first()
            if project:
                return project

    term = (entities.get("obra") or "").strip()
    if term:
        catalog = projects_catalog(scope)
        best_entry = None
        best_score = 0.0
        for entry in catalog:
            score, _ = _score_term_match(term, entry)
            if score > best_score:
                best_score = score
                best_entry = entry
        if best_entry and best_score >= 0.82:
            return Project.objects.filter(is_active=True, id=best_entry.id).first()

        qs = Project.objects.filter(is_active=True)
        if scope.role != "admin":
            qs = qs.filter(id__in=scope.project_ids)
        project = (
            qs.filter(code__iexact=term).first()
            or qs.filter(sigla__iexact=term).first()
            or qs.filter(name__icontains=term).first()
            or qs.filter(code__icontains=term).first()
            or qs.filter(sigla__icontains=term).first()
        )
        if project:
            return project

    if not allow_default:
        return None

    qs = Project.objects.filter(is_active=True)
    if scope.role != "admin":
        qs = qs.filter(id__in=scope.project_ids)
    return qs.order_by("-created_at").first()
