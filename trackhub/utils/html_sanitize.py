"""Sanitização de HTML rico (TrackHub pendências)."""
from __future__ import annotations

import re
from html import unescape

import bleach

ALLOWED_TAGS = ["b", "strong", "i", "em", "u", "ul", "ol", "li", "br", "p"]
ALLOWED_ATTRIBUTES: dict[str, list[str]] = {}


def sanitize_rich_text(html: str | None) -> str:
    """Remove tags/atributos não permitidos. Retorna string HTML segura."""
    if not html:
        return ""
    cleaned = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )
    return cleaned.strip()


def rich_text_is_empty(html: str | None) -> bool:
    if not html or not html.strip():
        return True
    text = bleach.clean(html, tags=[], strip=True)
    return not unescape(text).strip()


def rich_text_to_plain_preview(html: str | None, max_len: int = 120) -> str:
    """Texto plano para logs/atividades (sem markup)."""
    if not html:
        return ""
    text = bleach.clean(html, tags=[], strip=True)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text
