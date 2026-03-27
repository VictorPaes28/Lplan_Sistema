"""
Exibição de atividades na UI.

O campo `Activity.code` existe só no banco (EAP/treebeard); não é exibido em telas/PDF/API.
"""
from __future__ import annotations


def activity_code_for_display(code: str | None) -> str:
    """Sempre vazio: código de atividade não é mostrado ao usuário."""
    return ""


def activity_name_for_display(name: str | None) -> str:
    """Nome para exibir; remove prefixo legado 'GEN-' se existir no texto do nome."""
    if not name:
        return "—"
    s = name.strip()
    if len(s) >= 4 and s[:4].upper() == "GEN-":
        s = s[4:].strip()
    return s or "—"
