"""Handlers de log tolerantes a bloqueio de arquivo no Windows (runserver)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler


class SafeRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler que ignora falha de rename quando o arquivo está em uso."""

    def doRollover(self) -> None:
        try:
            super().doRollover()
        except PermissionError:
            # Comum no Windows: runserver e visualizador mantêm lplan.log aberto.
            pass
        except OSError:
            pass
