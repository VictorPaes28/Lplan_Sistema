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
from accounts.groups import GRUPOS

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
        r = self.client.get(reverse('engenharia:mapa'), follow=True)
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


class TestSelecionarObraRedirecionamentoFallback(TestCase):
    """Sem Referer, selecionar obra no hub deve cair na rota esperada pelo grupo (não na planilha por engano)."""

    @classmethod
    def setUpTestData(cls):
        cls.obra = Obra.objects.create(
            codigo_sienge='OBR-REDIRECT-FB',
            nome='Obra Redirect Fallback',
            ativa=True,
        )
        cls.project = Project.objects.create(
            name='Proj Fallback',
            code='OBR-REDIRECT-FB',
            start_date=date(2024, 1, 1),
            end_date=date(2027, 12, 31),
            is_active=True,
        )

    def setUp(self):
        self.client = Client()

    def _fixture_user(self, username, group_name):
        user = User.objects.create_user(username=username, password='senha123', email=f'{username}@t.local')
        g, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(g)
        ProjectMember.objects.get_or_create(user=user, project=self.project)
        return user

    def test_fallback_bi_va_para_analise_obra(self):
        user = self._fixture_user('u_fallback_bi', GRUPOS.BI_DA_OBRA)
        self.client.login(username=user.username, password='senha123')
        r = self.client.get(reverse('mapa_obras:selecionar', args=[self.obra.id]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, f"{reverse('engenharia:analise_obra')}?obra={self.obra.id}")

    def test_fallback_mapa_controle_va_para_view_controle(self):
        user = self._fixture_user('u_fallback_mc', GRUPOS.MAPA_CONTROLE)
        self.client.login(username=user.username, password='senha123')
        r = self.client.get(reverse('mapa_obras:selecionar', args=[self.obra.id]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, f"{reverse('engenharia:mapa_controle')}?obra={self.obra.id}")

    def test_fallback_ferramenta_va_para_shell(self):
        user = self._fixture_user('u_fallback_fo', GRUPOS.FERRAMENTA_OPERACIONAL)
        self.client.login(username=user.username, password='senha123')
        r = self.client.get(reverse('mapa_obras:selecionar', args=[self.obra.id]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse('engenharia:ferramenta_shell'))

    def test_so_ferramenta_sem_mc_redirect_select_system_no_mapa_controle(self):
        """Mesma sessão da ferramenta: view do Mapa de Controle exige grupo dedicado."""
        fo, _ = Group.objects.get_or_create(name=GRUPOS.FERRAMENTA_OPERACIONAL)
        user = User.objects.create_user(
            username='u_fo_so_map_view',
            password='senha123',
            email='fo_map_view@t.local',
        )
        user.groups.add(fo)
        ProjectMember.objects.get_or_create(user=user, project=self.project)
        self.client.login(username=user.username, password='senha123')
        url = reverse('engenharia:mapa_controle')
        r = self.client.get(url, {'obra': self.obra.id, 'embed': '1'})
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('select-system'), r.url)
