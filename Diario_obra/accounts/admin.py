"""
Accounts app - Django Admin

Este app usa o UserAdmin padrão do Django.
A configuração de admin customizada está em views_admin.py (Admin Central).
"""

from django.contrib import admin
from .models import UserLoginLog


@admin.register(UserLoginLog)
class UserLoginLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username',)
    readonly_fields = ('user', 'created_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

