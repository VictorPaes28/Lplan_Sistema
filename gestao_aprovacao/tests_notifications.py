from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from gestao_aprovacao.models import Notificacao


class NotificacaoRedirectTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="notif_user",
            password="testpass123",
            email="notif@test.com",
        )
        Notificacao.objects.create(
            usuario=self.user,
            tipo="pedido_criado",
            titulo="Novo pedido",
            mensagem="Pedido criado para teste",
            lida=False,
        )

    def test_mark_all_read_preserves_filters_without_reverse_error(self):
        self.client.force_login(self.user)
        url = reverse("gestao:list_notificacoes")

        response = self.client.get(
            url,
            {
                "marcar_todas_lidas": "true",
                "lida": "false",
                "tipo": "pedido_criado",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("lida=false", response.url)
        self.assertIn("tipo=pedido_criado", response.url)
        self.assertEqual(Notificacao.objects.filter(usuario=self.user, lida=False).count(), 0)
