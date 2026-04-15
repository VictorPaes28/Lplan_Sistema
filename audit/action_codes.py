"""
Códigos estáveis de ação para auditoria (evitar typos nas views e relatórios).
"""


class AuditAction:
    USER_CREATED = 'user_created'
    USER_UPDATED = 'user_updated'
    USER_DELETED = 'user_deleted'
    USER_SIGNUP_REQUEST_INTERNAL = 'user_signup_request_internal'
    USER_SIGNUP_REQUEST_PUBLIC = 'user_signup_request_public'
    USER_SIGNUP_APPROVED = 'user_signup_approved'
    USER_SIGNUP_REJECTED = 'user_signup_rejected'

    OBRA_WORKORDER_PERM_ADD = 'obra_workorder_perm_add'
    OBRA_WORKORDER_PERM_REMOVE = 'obra_workorder_perm_remove'
    OBRA_WORKORDER_PERM_TOGGLE = 'obra_workorder_perm_toggle'

    EMPRESA_CREATED = 'empresa_created'
    EMPRESA_UPDATED = 'empresa_updated'
    OBRA_CREATED = 'obra_created'
    OBRA_UPDATED = 'obra_updated'

    DIARY_PROVISIONAL_EDIT_GRANTED = 'diary_provisional_edit_granted'
