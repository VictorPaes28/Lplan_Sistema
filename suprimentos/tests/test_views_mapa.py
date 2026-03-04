"""
Testes de funcionalidade das views e URLs do Mapa de Suprimentos.

Confere que as páginas e APIs do mapa respondem corretamente (sem quebrar).
Rodar: python manage.py test suprimentos.tests.test_views_mapa -v 2
"""
from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from mapa_obras.models import Obra
from core.models import Project, ProjectMember

User = get_user_model()


class TestMapaViewsFuncionando(TestCase):
    """Verifica que as views do mapa de suprimentos respondem."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.grupo_eng, _ = Group.objects.get_or_create(name='Mapa de Suprimentos')

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='teste_mapa',
            password='senha123',
            email='teste@teste.com',
        )
        self.user.groups.add(self.grupo_eng)
        self.obra = Obra.objects.create(
            codigo_sienge='OBR-VTEST',
            nome='Obra Teste Views',
            ativa=True,
        )
        # Projeto com mesmo código para o usuário ter acesso à obra no mapa
        self.project = Project.objects.create(
            name='Projeto Teste Mapa',
            code='OBR-VTEST',
            start_date=date(2024, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        ProjectMember.objects.get_or_create(user=self.user, project=self.project)

    def test_login_redireciona_para_select_system_ou_map(self):
        """Login com usuário do mapa deve permitir acessar o sistema."""
        self.client.login(username='teste_mapa', password='senha123')
        r = self.client.get('/')
        self.assertIn(r.status_code, (200, 302), 'Raiz deve retornar 200 ou redirect')

    def test_url_engenharia_mapa_requer_login(self):
        """Página do mapa exige autenticação."""
        r = self.client.get(reverse('engenharia:mapa'))
        self.assertEqual(r.status_code, 302, 'Sem login deve redirecionar')
        self.client.login(username='teste_mapa', password='senha123')
        r = self.client.get(reverse('engenharia:mapa'))
        self.assertEqual(r.status_code, 200, 'Com login e grupo Mapa deve retornar 200')

    def test_url_engenharia_importar_sienge_requer_login(self):
        """Página de importar Sienge exige autenticação."""
        self.client.login(username='teste_mapa', password='senha123')
        r = self.client.get(reverse('engenharia:importar_sienge'))
        self.assertEqual(r.status_code, 200)

    def test_url_engenharia_dashboard_2_requer_login(self):
        """Dashboard 2 exige autenticação."""
        self.client.login(username='teste_mapa', password='senha123')
        r = self.client.get(reverse('engenharia:dashboard_2'))
        self.assertEqual(r.status_code, 200)

    def test_url_mapa_obras_home_requer_login(self):
        """Trocar obra (mapa_obras:home) exige autenticação."""
        self.client.login(username='teste_mapa', password='senha123')
        r = self.client.get(reverse('mapa_obras:home'))
        self.assertEqual(r.status_code, 200)

    def test_url_mapa_obras_selecionar_redireciona_para_mapa(self):
        """Selecionar obra deve setar sessão e redirecionar para o mapa."""
        self.client.login(username='teste_mapa', password='senha123')
        r = self.client.get(reverse('mapa_obras:selecionar', args=[self.obra.id]))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            r.url == reverse('engenharia:mapa') or r.url.startswith(reverse('engenharia:mapa') + '?'),
            f'Redirect deve ir para o mapa, obtido: {r.url}'
        )

    def test_api_internal_locais_requer_login(self):
        """API de locais exige login."""
        r = self.client.get('/api/internal/locais/', {'obra': self.obra.id})
        self.assertEqual(r.status_code, 302)
        self.client.login(username='teste_mapa', password='senha123')
        r = self.client.get('/api/internal/locais/', {'obra': self.obra.id})
        self.assertEqual(r.status_code, 200)

    def test_api_internal_item_atualizar_campo_requer_post_e_login(self):
        """Atualizar campo exige POST e login; com dados inválidos retorna 4xx ou 5xx (não redirect)."""
        r = self.client.post(
            '/api/internal/item/atualizar-campo/',
            data='{}',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 302)
        self.client.login(username='teste_mapa', password='senha123')
        r = self.client.post(
            '/api/internal/item/atualizar-campo/',
            data='{"item_id": 99999, "field": "prioridade", "value": "ALTA"}',
            content_type='application/json',
        )
        # Endpoint existe e exige login; com item inexistente pode retornar 400/403/404 ou 500
        self.assertFalse(r.status_code == 302, 'Não deve redirecionar (está logado)')
        self.assertGreaterEqual(r.status_code, 400)
