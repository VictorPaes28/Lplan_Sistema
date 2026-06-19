"""Compatibilidade: redireciona para o serviço unificado de notificações de contrato."""
from recursos_humanos.services.notificacoes_contrato import (  # noqa: F401
    processar_notificacoes_contrato as processar_notificacoes_experiencia,
)
