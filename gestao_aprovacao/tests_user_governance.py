from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.groups import GRUPOS
from gestao_aprovacao.models import Empresa, UserEmpresa


class UserGovernanceAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="gov_admin",
            password="pass12345",
            email="gov_admin@test.com",
        )
        g, _ = Group.objects.get_or_create(name=GRUPOS.ADMINISTRADOR)
        self.admin_user.groups.add(g)

        self.target = User.objects.create_user(
            username="gov_target",
            password="pass12345",
            email="gov_target@test.com",
        )

        self.other = User.objects.create_user(
            username="gov_other",
            password="pass12345",
            email="gov_other@test.com",
        )

    def test_admin_can_open_gestao_panel(self):
        self.client.force_login(self.admin_user)
        url = reverse("gestao:user_governance", kwargs={"pk": self.target.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "gov_target")

    def test_regular_user_denied(self):
        self.client.force_login(self.target)
        url = reverse("gestao:user_governance", kwargs={"pk": self.other.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_responsavel_only_sees_linked_users(self):
        resp_user = User.objects.create_user(
            username="gov_resp",
            password="pass12345",
            email="gov_resp@test.com",
        )
        g, _ = Group.objects.get_or_create(name=GRUPOS.RESPONSAVEL_EMPRESA)
        resp_user.groups.add(g)

        empresa = Empresa.objects.create(codigo="EMP-GOV", nome="Empresa Gov")
        empresa.responsavel = resp_user
        empresa.save()

        linked = User.objects.create_user(
            username="gov_linked",
            password="pass12345",
            email="linked@test.com",
        )
        UserEmpresa.objects.create(usuario=linked, empresa=empresa, ativo=True)

        self.client.force_login(resp_user)
        ok_url = reverse("gestao:user_governance", kwargs={"pk": linked.pk})
        self.assertEqual(self.client.get(ok_url).status_code, 200)

        deny_url = reverse("gestao:user_governance", kwargs={"pk": self.target.pk})
        self.assertEqual(self.client.get(deny_url).status_code, 302)


class AuditTimelineTests(TestCase):
    def test_audit_event_appears_in_timeline(self):
        from audit.recording import record_audit_event
        from gestao_aprovacao.services.user_governance import TimelineOptions, build_timeline_events

        actor = User.objects.create_user(username="aud_actor", password="x")
        subject = User.objects.create_user(username="aud_subject", password="x")
        record_audit_event(
            actor=actor,
            subject_user=subject,
            action_code="user_updated",
            summary="Teste de auditoria",
            payload={"k": 1},
            module="gestao",
            request=None,
        )
        opts = TimelineOptions(period_days=30, module="admin", obra_id=None, max_merged=50, per_source_cap=20)
        evs = build_timeline_events(subject, opts)
        self.assertTrue(any(e.get("kind") == "user_updated" for e in evs))

    def test_signup_approved_on_user_timeline(self):
        from accounts.audit_signup import record_signup_approved
        from accounts.models import UserSignupRequest
        from gestao_aprovacao.services.user_governance import TimelineOptions, build_timeline_events

        actor = User.objects.create_user(username="approver_x", password="x")
        new_user = User.objects.create_user(username="new_from_signup", password="x", email="ns@test.com")
        req = UserSignupRequest.objects.create(
            full_name="Novo User",
            email="ns@test.com",
            status=UserSignupRequest.STATUS_APROVADO,
        )
        record_signup_approved(
            None,
            actor,
            req,
            new_user,
            ["Solicitante"],
            [1, 2],
        )
        opts = TimelineOptions(period_days=30, module="admin", obra_id=None, max_merged=50, per_source_cap=20)
        evs = build_timeline_events(new_user, opts)
        self.assertTrue(any(e.get("kind") == "user_signup_approved" for e in evs))


class UserGovernanceServiceTests(TestCase):
    def test_viewer_can_see_target_admin(self):
        from gestao_aprovacao.services.user_governance import viewer_can_see_target_user

        admin = User.objects.create_user(username="a1", password="x")
        g, _ = Group.objects.get_or_create(name=GRUPOS.ADMINISTRADOR)
        admin.groups.add(g)
        target = User.objects.create_user(username="t1", password="x")
        self.assertTrue(viewer_can_see_target_user(admin, target))

    def test_timeline_includes_login_log(self):
        from accounts.models import UserLoginLog
        from gestao_aprovacao.services.user_governance import TimelineOptions, build_timeline_events

        u = User.objects.create_user(username="logu", password="x")
        UserLoginLog.objects.create(user=u)
        opts = TimelineOptions(period_days=30, module="", obra_id=None, max_merged=100, per_source_cap=50)
        evs = build_timeline_events(u, opts)
        self.assertTrue(any(e["kind"] == "login" for e in evs))

    def test_audit_insights_counts_and_recent(self):
        from audit.models import AuditEvent
        from gestao_aprovacao.services.user_governance import build_audit_insights

        actor = User.objects.create_user(username="aud_act", password="x")
        target = User.objects.create_user(username="aud_tgt", password="x")
        AuditEvent.objects.create(
            actor=actor,
            subject_user=target,
            action_code="user_updated",
            module="gestao",
            summary="Atualização teste",
            payload={},
        )
        from accounts.models import UserLoginLog

        UserLoginLog.objects.create(user=target, ip_address="192.168.1.10", user_agent="TestUA")
        UserLoginLog.objects.create(user=target, ip_address="192.168.1.20", user_agent="TestUA")

        ins = build_audit_insights(target)
        self.assertEqual(ins["audit_as_subject_count"], 1)
        self.assertEqual(ins["audit_top_actions"][0]["action_code"], "user_updated")
        self.assertNotIn("ip_ranking", ins)
        self.assertEqual(len(ins["recent_audit_events"]), 1)
        self.assertIn("central/auditoria/", ins["recent_audit_events"][0]["detail_url"])
