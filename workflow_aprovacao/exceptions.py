class WorkflowError(Exception):
    """Erro de domínio do workflow de aprovações."""


class NoFlowConfigurationError(WorkflowError):
    """Não existe fluxo ativo para o par (obra, categoria)."""


class InvalidTransitionError(WorkflowError):
    """Transição de estado inválida ou usuário sem permissão."""


class UnsupportedPolicyError(WorkflowError):
    """Política de alçada ainda não implementada no motor."""
