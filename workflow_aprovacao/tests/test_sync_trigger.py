from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings

from workflow_aprovacao.services.sync_trigger import maybe_trigger_sienge_sync_on_page_open


class SyncTriggerOnPageOpenTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user('u', password='x')

    @override_settings(SIENGE_CENTRAL_WEB_SYNC_ON_PAGE_OPEN=False)
    def test_maybe_trigger_noop_when_disabled(self):
        request = self.factory.get('/aprovacoes/')
        request.user = self.user
        maybe_trigger_sienge_sync_on_page_open(request)
