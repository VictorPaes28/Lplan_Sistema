"""Acesso à listagem global de auditoria na Central."""

from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.groups import GRUPOS
from audit.action_codes import AuditAction
from audit.models import AuditEvent
from gestao_aprovacao.models import Empresa


class CentralAuditEventsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username="aud_list_admin", password="x", email="a@t.com")
        g, _ = Group.objects.get_or_create(name=GRUPOS.ADMINISTRADOR)
        self.admin.groups.add(g)
        AuditEvent.objects.create(
            actor=self.admin,
            action_code="user_created",
            module="gestao",
            summary="Teste listagem",
            payload={},
        )

    def test_painel_admin_gets_200(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("central_audit_events"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "user_created")

    def test_non_painel_user_forbidden(self):
        u = User.objects.create_user(username="plain", password="x")
        self.client.force_login(u)
        r = self.client.get(reverse("central_audit_events"))
        self.assertEqual(r.status_code, 403)

    def test_csv_export(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("central_audit_events"), {"format": "csv"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r["Content-Type"])
        body = r.content.decode("utf-8-sig")
        self.assertIn("user_created", body)
        self.assertIn("Teste listagem", body)


class CentralAuditResponsavelScopedTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.resp = User.objects.create_user(username="aud_resp_sc", password="x")
        g, _ = Group.objects.get_or_create(name=GRUPOS.RESPONSAVEL_EMPRESA)
        self.resp.groups.add(g)
        self.other = User.objects.create_user(username="aud_resp_other", password="x")
        self.emp_a = Empresa.objects.create(codigo="EAUD", nome="Emp A")
        self.emp_a.responsavel = self.resp
        self.emp_a.save()
        self.emp_b = Empresa.objects.create(codigo="EBUD", nome="Emp B")
        self.emp_b.responsavel = self.other
        self.emp_b.save()
        AuditEvent.objects.create(
            actor=self.resp,
            action_code="empresa_updated",
            module="gestao",
            summary="Evento empresa A",
            payload={"empresa_id": self.emp_a.pk},
        )
        AuditEvent.objects.create(
            actor=self.other,
            action_code="empresa_updated",
            module="gestao",
            summary="Evento empresa B",
            payload={"empresa_id": self.emp_b.pk},
        )

    def test_responsavel_sees_only_scoped_rows(self):
        self.client.force_login(self.resp)
        r = self.client.get(reverse("central_audit_events"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Evento empresa A")
        self.assertNotContains(r, "Evento empresa B")

    def test_responsavel_sem_empresa_403(self):
        lone = User.objects.create_user(username="resp_sem_emp", password="x")
        g, _ = Group.objects.get_or_create(name=GRUPOS.RESPONSAVEL_EMPRESA)
        lone.groups.add(g)
        self.client.force_login(lone)
        r = self.client.get(reverse("central_audit_events"))
        self.assertEqual(r.status_code, 403)

    def test_responsavel_sees_user_deleted_when_empresa_in_snapshot(self):
        self.client.force_login(self.resp)
        AuditEvent.objects.create(
            actor=self.other,
            subject_user=None,
            action_code=AuditAction.USER_DELETED,
            module="gestao",
            summary="Utilizador excluído",
            payload={"username": "gone", "empresa_ids_vinculadas": [self.emp_a.pk]},
        )
        AuditEvent.objects.create(
            actor=self.other,
            subject_user=None,
            action_code=AuditAction.USER_DELETED,
            module="gestao",
            summary="Outro",
            payload={"username": "x", "empresa_ids_vinculadas": [self.emp_b.pk]},
        )
        r = self.client.get(reverse("central_audit_events"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Utilizador excluído")
        self.assertNotContains(r, "Outro")


class CentralAuditEventDetailTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username="aud_det_adm", password="x")
        g, _ = Group.objects.get_or_create(name=GRUPOS.ADMINISTRADOR)
        self.admin.groups.add(g)
        self.ev = AuditEvent.objects.create(
            actor=self.admin,
            action_code="user_created",
            module="gestao",
            summary="Detalhe teste",
            payload={"empresa_id": 1},
        )

    def test_admin_detail_200(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("central_audit_event_detail", kwargs={"pk": self.ev.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Detalhe teste")
        self.assertContains(r, "user_created")

    def test_responsavel_cannot_open_foreign_event(self):
        resp = User.objects.create_user(username="aud_det_resp", password="x")
        g, _ = Group.objects.get_or_create(name=GRUPOS.RESPONSAVEL_EMPRESA)
        resp.groups.add(g)
        emp = Empresa.objects.create(codigo="EDET", nome="Emp det")
        emp.responsavel = resp
        emp.save()
        foreign = AuditEvent.objects.create(
            actor=self.admin,
            action_code="empresa_updated",
            module="gestao",
            summary="Outra empresa",
            payload={"empresa_id": 99999},
        )
        self.client.force_login(resp)
        r = self.client.get(reverse("central_audit_event_detail", kwargs={"pk": foreign.pk}))
        self.assertEqual(r.status_code, 403)


class PurgeAuditRetentionCommandTests(TestCase):
    def test_dry_run_counts_old_audit_events(self):
        ev = AuditEvent.objects.create(
            actor=None,
            action_code="user_created",
            module="gestao",
            summary="Velho",
            payload={},
        )
        AuditEvent.objects.filter(pk=ev.pk).update(
            created_at=timezone.now() - timedelta(days=5000)
        )
        call_command("purge_audit_retention", "--dry-run", "--only-audit", "--audit-days", "3650")
        self.assertEqual(AuditEvent.objects.filter(pk=ev.pk).count(), 1)
        call_command("purge_audit_retention", "--only-audit", "--audit-days", "3650")
        self.assertEqual(AuditEvent.objects.filter(pk=ev.pk).count(), 0)
