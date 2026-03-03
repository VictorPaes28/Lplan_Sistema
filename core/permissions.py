"""
Permissões customizadas para Diário de Obra V2.0.

Define permissões específicas para controle de acesso ao workflow
de aprovação de diários de obra.
"""
from rest_framework import permissions
from accounts.groups import GRUPOS


class CanApproveDiary(permissions.BasePermission):
    """
    Permissão para aprovar diários de obra.
    
    Usuários com esta permissão podem mover diários do status
    REVISAR para APROVADO.
    """
    def has_permission(self, request, view):
        """Verifica se o usuário tem permissão geral para aprovar diários."""
        return (
            request.user and
            request.user.is_authenticated and
            (
                request.user.is_staff or
                request.user.has_perm('core.can_approve_diary') or
                request.user.groups.filter(name=GRUPOS.GERENTES).exists()
            )
        )

    def has_object_permission(self, request, view, obj):
        """
        Verifica se o usuário pode aprovar um diário específico.
        
        Regras:
        - O diário deve estar no status REVISAR
        - O usuário deve ter a permissão can_approve_diary
        """
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Para aprovação, o diário deve estar em REVISAR
        if obj.status == 'RV':  # REVISAR
            return self.has_permission(request, view)
        
        return False


class CanEditDiary(permissions.BasePermission):
    """
    Permissão para editar diários de obra.
    
    Regras:
    - Apenas o criador pode editar quando status = PREENCHENDO ou SALVAMENTO_PARCIAL
    - Ninguém pode editar quando status = APROVADO
    """
    def has_object_permission(self, request, view, obj):
        """Verifica se o usuário pode editar um diário específico."""
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Diários aprovados são imutáveis
        if obj.is_approved():
            return False
        
        # Apenas o criador pode editar quando está preenchendo ou salvamento parcial
        if obj.status in ('PR', 'SP'):  # PREENCHENDO, SALVAMENTO_PARCIAL
            return obj.created_by == request.user
        
        return False

