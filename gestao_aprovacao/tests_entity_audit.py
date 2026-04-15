from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.groups import GRUPOS
from audit.action_codes import AuditAction
from audit.models import AuditEvent
from gestao_aprovacao.models import Empresa, Obra
from gestao_aprovacao.services import entity_audit


class EntityAuditSnapshotsTests(TestCase):
    def test_snapshot_empresa_shape(self):
        e = Empresa.objects.create(codigo="E-SNAP", nome="Snap SA", email="a@b.c")
        d = entity_audit.snapshot_empresa(e)
        self.assertEqual(d["schema"], "empresa_v1")
        self.assertEqual(d["entity"], "empresa")
        self.assertEqual(d["empresa_id"], e.pk)
        self.assertEqual(d["codigo"], "E-SNAP")

    def test_snapshot_obra_shape(self):
        e = Empresa.objects.create(codigo="E-OBR", nome="Emp Obra")
        o = Obra.objects.create(empresa=e, codigo="O1", nome="Obra Um", ativo=True)
        d = entity_audit.snapshot_obra(o)
        self.assertEqual(d["schema"], "obra_v1")
        self.assertEqual(d["entity"], "obra")
        self.assertEqual(d["obra_id"], o.pk)
        self.assertEqual(d["empresa_id"], e.pk)


class EntityAuditRecordingTests(TestCase):
    def test_record_obra_created_persists_event(self):
        actor = User.objects.create_user(username="aud_cr", password="x")
        e = Empresa.objects.create(codigo="E-CR", nome="Emp")
        o = Obra.objects.create(empresa=e, codigo="OC", nome="Obra C", ativo=True)
        entity_audit.record_obra_created(None, actor, o)
        ev = AuditEvent.objects.order_by("-pk").first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.action_code, AuditAction.OBRA_CREATED)
        self.assertEqual(ev.module, "gestao")
        self.assertEqual(ev.actor_id, actor.pk)
        self.assertIsNone(ev.subject_user_id)
        self.assertEqual(ev.payload.get("obra_id"), o.pk)
        self.assertEqual(ev.payload.get("schema"), "obra_v1")

    def test_record_obra_updated_includes_changed_fields(self):
        actor = User.objects.create_user(username="aud_up", password="x")
        e = Empresa.objects.create(codigo="E-UP", nome="Emp")
        o = Obra.objects.create(empresa=e, codigo="OU", nome="Antes", ativo=True)
        before = entity_audit.snapshot_obra(o)
        o.nome = "Depois"
        o.save()
        after = entity_audit.snapshot_obra(o)
        entity_audit.record_obra_updated(None, actor, before, after)
        ev = AuditEvent.objects.order_by("-pk").first()
        self.assertEqual(ev.action_code, AuditAction.OBRA_UPDATED)
        self.assertIn("nome", ev.payload.get("changed_fields", []))


class CreateObraAuditIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="adm_obra_aud",
            password="pass12345",
        )
        g, _ = Group.objects.get_or_create(name=GRUPOS.ADMINISTRADOR)
        self.admin.groups.add(g)
        self.empresa = Empresa.objects.create(codigo="E-AUD", nome="Empresa Audit")

    def test_post_create_obra_writes_audit_event(self):
        before = AuditEvent.objects.count()
        self.client.force_login(self.admin)
        url = reverse("gestao:create_obra")
        response = self.client.post(
            url,
            {
                "empresa": str(self.empresa.pk),
                "codigo": "OBRA-AUD-01",
                "nome": "Obra auditoria",
                "descricao": "",
                "email_obra": "",
                "ativo": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AuditEvent.objects.count(), before + 1)
        ev = AuditEvent.objects.order_by("-pk").first()
        self.assertEqual(ev.action_code, AuditAction.OBRA_CREATED)
        self.assertEqual(ev.actor_id, self.admin.pk)
        obra = Obra.objects.get(codigo="OBRA-AUD-01")
        self.assertEqual(ev.payload.get("obra_id"), obra.pk)
