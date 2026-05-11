"""Regras de acesso ao módulo Central de Aprovações."""

from django.contrib.auth.models import Group, User
from django.test import TestCase

from accounts.groups import GRUPOS
from workflow_aprovacao.access import user_should_use_minimal_workflow_shell


class WorkflowMinimalShellTests(TestCase):
    def _user_with_groups(self, *names):
        u = User.objects.create_user(username='t', password='x')
        for n in names:
            g, _ = Group.objects.get_or_create(name=n)
            u.groups.add(g)
        return u

    def test_only_workflow_group_uses_minimal_shell(self):
        u = self._user_with_groups(GRUPOS.CENTRAL_APROVACOES_APROVADOR)
        self.assertTrue(user_should_use_minimal_workflow_shell(u))

    def test_extra_module_group_disables_minimal_shell(self):
        for i, extra in enumerate(
            (
                GRUPOS.GESTAO_IMPEDIMENTOS,
                GRUPOS.TRACKHUB,
                GRUPOS.FERRAMENTA_OPERACIONAL,
                GRUPOS.SOLICITANTE,
                GRUPOS.BI_DA_OBRA,
            )
        ):
            with self.subTest(extra=extra):
                u = User.objects.create_user(username=f"t{i}", password="x")
                for n in (GRUPOS.CENTRAL_APROVACOES_APROVADOR, extra):
                    g, _ = Group.objects.get_or_create(name=n)
                    u.groups.add(g)
                self.assertFalse(user_should_use_minimal_workflow_shell(u))
