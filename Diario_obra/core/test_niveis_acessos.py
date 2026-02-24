"""
Testes de níveis e acessos: login, seleção de sistema, Central, GestControll.

Simula usuários por perfil (superuser, staff, Gerentes, Solicitante, Aprovador,
Administrador, Responsável Empresa, ENGENHARIA, sem grupo) e verifica:
- Redirecionamento quando não autenticado
- Quem vê Diário, GestControll, Mapa e Central na tela de seleção
- Acesso ao Central (apenas staff/superuser)
- Acesso à lista de usuários no GestControll (admin ou responsável)
- Redirecionamento de staff do GestControll para o Central
- Decorators gestor_required e admin_required (redirect para login ou home)

Testes de filtro por obra (GestControll e Diário):
  - TestFiltroSolicitantePorObra: solicitante só vê pedidos das obras em que está vinculado
  - TestFiltroAprovadorPorObra: aprovador só vê e só aprova nas obras onde tem permissão
  - TestSolicitanteSemObraVeSoSeusPedidos: solicitante sem obra vê só os pedidos que criou
  - TestDiarioSoProjetosVinculados: no Diário, usuário só vê projetos (ProjectMember) vinculados
  - TestAdminVeTodosPedidos: admin vê todos os pedidos

Como rodar (na pasta Diario_obra):
  python manage.py test core.test_niveis_acessos -v 2
  python manage.py test core.test_niveis_acessos.TestFiltroSolicitantePorObra -v 2  # só filtro solicitante
"""
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth.models import User, Group, AnonymousUser
from accounts.groups import GRUPOS
from gestao_aprovacao.utils import (
    get_user_profile,
    is_admin,
    is_aprovador,
    is_responsavel_empresa,
    is_engenheiro,
    is_gestor,
)
from gestao_aprovacao.models import Empresa, Obra, WorkOrder, WorkOrderPermission
from core.models import Project, ProjectMember


def _create_group(name):
    g, _ = Group.objects.get_or_create(name=name)
    return g


def _user(username, password='testpass123', is_staff=False, is_superuser=False, groups=None):
    u = User.objects.create_user(username=username, password=password, is_staff=is_staff, is_superuser=is_superuser)
    if groups:
        for g in groups:
            u.groups.add(_create_group(g))
    return u


class TestNiveisAcessosNaoAutenticado(TestCase):
    """Usuário não logado: deve ser redirecionado para o login onde aplicável."""

    def setUp(self):
        self.client = Client()

    def test_login_retorna_200(self):
        r = self.client.get(reverse('login'))
        self.assertEqual(r.status_code, 200)

    def test_select_system_redireciona_para_login(self):
        r = self.client.get(reverse('select-system'))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].endswith(reverse('login')) or '/login/' in r['Location'])

    def test_central_hub_redireciona_para_login(self):
        r = self.client.get(reverse('central_hub'))
        self.assertEqual(r.status_code, 302)
        self.assertTrue('/login/' in r['Location'] or r['Location'].endswith(reverse('login')))

    def test_central_usuarios_redireciona_para_login(self):
        r = self.client.get(reverse('central_list_users'))
        self.assertEqual(r.status_code, 302)
        self.assertTrue('/login/' in r['Location'] or r['Location'].endswith(reverse('login')))

    def test_gestao_home_redireciona_para_login(self):
        r = self.client.get(reverse('gestao:home'))
        self.assertEqual(r.status_code, 302)
        self.assertTrue('/login/' in r['Location'] or r['Location'].endswith(reverse('login')))

    def test_gestao_usuarios_redireciona_para_login(self):
        r = self.client.get(reverse('gestao:list_users'))
        self.assertEqual(r.status_code, 302)
        self.assertTrue('/login/' in r['Location'] or r['Location'].endswith(reverse('login')))

    def test_project_list_redireciona_para_login(self):
        self.client.logout()  # garante anônimo
        r = self.client.get(reverse('central_project_list'))
        self.assertEqual(r.status_code, 302, 'Anônimo deve ser redirecionado ao login, não 403')
        self.assertTrue('/login/' in r.get('Location', '') or r.get('Location', '').endswith(reverse('login')))


class TestSelectSystemContext(TestCase):
    """Lógica da tela 'Selecionar sistema': quem tem has_diario, has_gestao, has_mapa, has_central."""

    def setUp(self):
        self.client = Client()

    def test_superuser_tem_todos_os_acessos(self):
        u = _user('super', is_superuser=True)
        self.client.force_login(u)
        r = self.client.get(reverse('select-system'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['has_diario'], 'Superuser deve ter acesso ao Diário')
        self.assertTrue(r.context['has_gestao'], 'Superuser deve ter acesso ao GestControll')
        self.assertTrue(r.context['has_mapa'], 'Superuser deve ter acesso ao Mapa')
        self.assertTrue(r.context['has_central'], 'Superuser deve ter acesso ao Central')

    def test_staff_sem_grupos_tem_todos_os_acessos(self):
        u = _user('staff_user', is_staff=True)
        self.client.force_login(u)
        r = self.client.get(reverse('select-system'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['has_diario'])
        self.assertTrue(r.context['has_gestao'])
        self.assertTrue(r.context['has_mapa'])
        self.assertTrue(r.context['has_central'])

    def test_gerentes_so_diario(self):
        u = _user('gerente', groups=[GRUPOS.GERENTES])
        self.client.force_login(u)
        r = self.client.get(reverse('select-system'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['has_diario'], 'Gerentes deve ter Diário')
        self.assertFalse(r.context['has_gestao'], 'Gerentes não deve ter GestControll')
        self.assertFalse(r.context['has_mapa'], 'Gerentes não deve ter Mapa')
        self.assertFalse(r.context['has_central'], 'Gerentes não deve ter Central')

    def test_solicitante_so_gestao(self):
        u = _user('solic', groups=[GRUPOS.SOLICITANTE])
        self.client.force_login(u)
        r = self.client.get(reverse('select-system'))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context['has_diario'])
        self.assertTrue(r.context['has_gestao'])
        self.assertFalse(r.context['has_mapa'])
        self.assertFalse(r.context['has_central'])

    def test_aprovador_gestao(self):
        u = _user('aprov', groups=[GRUPOS.APROVADOR])
        self.client.force_login(u)
        r = self.client.get(reverse('select-system'))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context['has_diario'])
        self.assertTrue(r.context['has_gestao'])
        self.assertFalse(r.context['has_mapa'])
        self.assertFalse(r.context['has_central'])

    def test_administrador_gestao_sem_central(self):
        u = _user('admin_gr', groups=[GRUPOS.ADMINISTRADOR])
        self.client.force_login(u)
        r = self.client.get(reverse('select-system'))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context['has_diario'])
        self.assertTrue(r.context['has_gestao'])
        self.assertFalse(r.context['has_mapa'])
        self.assertFalse(r.context['has_central'], 'Administrador (sem staff) não vê Central')

    def test_responsavel_empresa_gestao(self):
        u = _user('resp_emp', groups=[GRUPOS.RESPONSAVEL_EMPRESA])
        self.client.force_login(u)
        r = self.client.get(reverse('select-system'))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context['has_diario'])
        self.assertTrue(r.context['has_gestao'])
        self.assertFalse(r.context['has_mapa'])
        self.assertFalse(r.context['has_central'])

    def test_engenharia_mapa(self):
        u = _user('eng', groups=[GRUPOS.ENGENHARIA])
        self.client.force_login(u)
        r = self.client.get(reverse('select-system'))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context['has_diario'])
        self.assertFalse(r.context['has_gestao'])
        self.assertTrue(r.context['has_mapa'])
        self.assertFalse(r.context['has_central'])

    def test_usuario_sem_grupo_nao_tem_nenhum_sistema(self):
        u = _user('sem_grupo')
        self.client.force_login(u)
        r = self.client.get(reverse('select-system'))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context['has_diario'])
        self.assertFalse(r.context['has_gestao'])
        self.assertFalse(r.context['has_mapa'])
        self.assertFalse(r.context['has_central'])


class TestCentralAcesso(TestCase):
    """Central (obras/usuários): apenas staff e superuser."""

    def setUp(self):
        self.client = Client()

    def test_superuser_acessa_central_hub(self):
        u = _user('super', is_superuser=True)
        self.client.force_login(u)
        r = self.client.get(reverse('central_hub'))
        # central_hub redireciona para accounts:admin_central
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse('accounts:admin_central'))

    def test_staff_acessa_central_hub(self):
        u = _user('staff_user', is_staff=True)
        self.client.force_login(u)
        r = self.client.get(reverse('central_hub'))
        # central_hub redireciona para accounts:admin_central
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse('accounts:admin_central'))

    def test_administrador_sem_staff_nao_acessa_central_hub(self):
        u = _user('admin_gr', groups=[GRUPOS.ADMINISTRADOR])
        self.client.force_login(u)
        r = self.client.get(reverse('central_hub'))
        self.assertEqual(r.status_code, 403)

    def test_solicitante_nao_acessa_central_hub(self):
        u = _user('solic', groups=[GRUPOS.SOLICITANTE])
        self.client.force_login(u)
        r = self.client.get(reverse('central_hub'))
        self.assertEqual(r.status_code, 403)

    def test_superuser_acessa_central_list_users(self):
        u = _user('super', is_superuser=True)
        self.client.force_login(u)
        r = self.client.get(reverse('central_list_users'))
        self.assertEqual(r.status_code, 200)

    def test_gerentes_nao_acessa_central_list_users(self):
        u = _user('gerente', groups=[GRUPOS.GERENTES])
        self.client.force_login(u)
        r = self.client.get(reverse('central_list_users'))
        self.assertEqual(r.status_code, 403)


class TestGestaoUsuariosListagem(TestCase):
    """Listagem de usuários no GestControll: admin ou responsável por empresa; staff redireciona ao Central."""

    def setUp(self):
        self.client = Client()

    def test_staff_redireciona_para_central_usuarios(self):
        u = _user('staff_user', is_staff=True)
        self.client.force_login(u)
        r = self.client.get(reverse('gestao:list_users'))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            'central/usuarios' in r['Location'] or r['Location'].endswith(reverse('central_list_users')),
            'Staff deve ser redirecionado para o Central'
        )

    def test_superuser_redireciona_para_central_usuarios(self):
        u = _user('super', is_superuser=True)
        self.client.force_login(u)
        r = self.client.get(reverse('gestao:list_users'))
        self.assertEqual(r.status_code, 302)
        self.assertTrue('central/usuarios' in r['Location'] or r['Location'].endswith(reverse('central_list_users')))

    def test_administrador_acessa_list_users_gestao(self):
        u = _user('admin_gr', groups=[GRUPOS.ADMINISTRADOR])
        self.client.force_login(u)
        r = self.client.get(reverse('gestao:list_users'))
        self.assertEqual(r.status_code, 200)

    def test_responsavel_empresa_acessa_list_users_gestao(self):
        u = _user('resp_emp', groups=[GRUPOS.RESPONSAVEL_EMPRESA])
        self.client.force_login(u)
        r = self.client.get(reverse('gestao:list_users'))
        self.assertEqual(r.status_code, 200)

    def test_solicitante_nao_acessa_list_users_redireciona_home(self):
        u = _user('solic', groups=[GRUPOS.SOLICITANTE])
        self.client.force_login(u)
        r = self.client.get(reverse('gestao:list_users'))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].endswith(reverse('gestao:home')) or 'gestao' in r['Location'])

    def test_aprovador_nao_acessa_list_users_redireciona_home(self):
        u = _user('aprov', groups=[GRUPOS.APROVADOR])
        self.client.force_login(u)
        r = self.client.get(reverse('gestao:list_users'))
        self.assertEqual(r.status_code, 302)
        self.assertTrue('gestao' in r['Location'] or r['Location'].endswith(reverse('gestao:home')))


class TestGestaoHomeEAprovar(TestCase):
    """Home do GestControll e view de aprovar (gestor_required)."""

    def setUp(self):
        self.client = Client()
        # Dados mínimos para approve_workorder
        self.empresa = Empresa.objects.create(codigo='EMP-TEST', nome='Empresa Teste')
        self.obra = Obra.objects.create(
            codigo='OBRA-TEST',
            nome='Obra Teste',
            empresa=self.empresa
        )
        self.pedido = WorkOrder.objects.create(
            obra=self.obra,
            codigo='OBRA-TEST-2025-1',
            nome_credor='Credor Teste',
            tipo_solicitacao='contrato',
            status='pendente',
            criado_por=User.objects.create_user(username='criador', password='x')
        )

    def test_qualquer_autenticado_acessa_gestao_home(self):
        u = _user('qualquer')
        self.client.force_login(u)
        r = self.client.get(reverse('gestao:home'))
        self.assertEqual(r.status_code, 200)

    def test_aprovador_acessa_aprovar_pedido(self):
        u = _user('aprov', groups=[GRUPOS.APROVADOR])
        # Aprovador precisa ter permissão na obra (WorkOrderPermission) para acessar o formulário de aprovar
        WorkOrderPermission.objects.create(
            obra=self.obra, usuario=u, tipo_permissao='aprovador', ativo=True
        )
        self.client.force_login(u)
        r = self.client.get(reverse('gestao:approve_workorder', kwargs={'pk': self.pedido.pk}))
        self.assertEqual(r.status_code, 200)

    def test_administrador_acessa_aprovar_pedido(self):
        u = _user('admin_gr', groups=[GRUPOS.ADMINISTRADOR])
        self.client.force_login(u)
        r = self.client.get(reverse('gestao:approve_workorder', kwargs={'pk': self.pedido.pk}))
        self.assertEqual(r.status_code, 200)

    def test_solicitante_nao_acessa_aprovar_redireciona_home(self):
        u = _user('solic', groups=[GRUPOS.SOLICITANTE])
        self.client.force_login(u)
        r = self.client.get(reverse('gestao:approve_workorder', kwargs={'pk': self.pedido.pk}))
        self.assertEqual(r.status_code, 302)
        self.assertTrue('gestao' in r['Location'] or r['Location'].endswith(reverse('gestao:home')))

    def test_nao_autenticado_aprovar_redireciona_login(self):
        r = self.client.get(reverse('gestao:approve_workorder', kwargs={'pk': self.pedido.pk}))
        self.assertEqual(r.status_code, 302)
        self.assertTrue('/login/' in r['Location'] or r['Location'].endswith(reverse('login')))


class TestGestaoAdminRequired(TestCase):
    """Views com @admin_required: ex. list_email_logs."""

    def setUp(self):
        self.client = Client()

    def test_nao_autenticado_admin_view_redireciona_login(self):
        r = self.client.get(reverse('gestao:list_email_logs'))
        self.assertEqual(r.status_code, 302)
        self.assertTrue('/login/' in r['Location'] or r['Location'].endswith(reverse('login')))

    def test_solicitante_admin_view_redireciona_home(self):
        u = _user('solic', groups=[GRUPOS.SOLICITANTE])
        self.client.force_login(u)
        r = self.client.get(reverse('gestao:list_email_logs'))
        self.assertEqual(r.status_code, 302)
        self.assertTrue('gestao' in r['Location'] or r['Location'].endswith(reverse('gestao:home')))

    def test_administrador_acessa_admin_view(self):
        u = _user('admin_gr', groups=[GRUPOS.ADMINISTRADOR])
        self.client.force_login(u)
        r = self.client.get(reverse('gestao:list_email_logs'))
        self.assertEqual(r.status_code, 200)


class TestProjectListStaffOnly(TestCase):
    """Listagem de projetos (obras no core): apenas staff/superuser."""

    def setUp(self):
        self.client = Client()

    def test_nao_autenticado_redireciona_login(self):
        self.client.logout()  # garante anônimo
        r = self.client.get(reverse('central_project_list'))
        self.assertEqual(r.status_code, 302, 'Anônimo deve ser redirecionado ao login')
        self.assertTrue('/login/' in r.get('Location', '') or r.get('Location', '').endswith(reverse('login')))

    def test_superuser_acessa_project_list(self):
        u = _user('super', is_superuser=True)
        self.client.force_login(u)
        r = self.client.get(reverse('central_project_list'))
        self.assertEqual(r.status_code, 200)

    def test_gerentes_sem_staff_nao_acessa_project_list(self):
        u = _user('gerente', groups=[GRUPOS.GERENTES])  # is_staff=False por padrão
        self.assertFalse(u.is_staff, 'Teste exige usuário não-staff')
        self.client.force_login(u)
        r = self.client.get(reverse('central_project_list'))
        self.assertEqual(r.status_code, 403, 'Listagem de projetos é só staff/superuser; Gerentes sem staff devem receber 403')


class TestProjectListViewDireto(TestCase):
    """Chama project_list_view diretamente (RequestFactory) para isolar comportamento da view."""

    def setUp(self):
        self.factory = RequestFactory()
        from core.frontend_views import project_list_view
        self.view = project_list_view

    def test_view_anonimo_retorna_302(self):
        request = self.factory.get('/projects/')
        request.user = AnonymousUser()
        r = self.view(request)
        self.assertEqual(r.status_code, 302, 'View deve redirecionar anônimo (302)')
        self.assertTrue('/login/' in r.get('Location', ''))

    def test_view_gerente_sem_staff_retorna_403(self):
        u = _user('gerente_direto', groups=[GRUPOS.GERENTES])
        self.assertFalse(u.is_staff)
        request = self.factory.get('/projects/')
        request.user = u
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            self.view(request)


# ========== Simulação lógica (sem HTTP): funções de perfil e permissão ==========


class TestLogicaPerfisGestao(TestCase):
    """
    Testes de lógica: get_user_profile, is_admin, is_aprovador, is_responsavel_empresa, is_engenheiro.
    Garante que os níveis não se sobrepõem de forma errada e que superuser tem todos os papéis.
    """

    def test_superuser_perfil_admin(self):
        u = User.objects.create_superuser('super', 's@x.com', 'x')
        self.assertEqual(get_user_profile(u), 'admin')
        self.assertTrue(is_admin(u))
        self.assertTrue(is_aprovador(u))
        self.assertTrue(is_responsavel_empresa(u))
        self.assertTrue(is_engenheiro(u))
        self.assertTrue(is_gestor(u))

    def test_administrador_grupo_perfil_admin(self):
        u = _user('adm', groups=[GRUPOS.ADMINISTRADOR])
        self.assertEqual(get_user_profile(u), 'admin')
        self.assertTrue(is_admin(u))
        # is_gestor é alias de is_aprovador: só grupo Aprovador (ou superuser). Admin não é gestor pela função.
        self.assertFalse(is_gestor(u))

    def test_responsavel_empresa_perfil(self):
        u = _user('resp', groups=[GRUPOS.RESPONSAVEL_EMPRESA])
        self.assertEqual(get_user_profile(u), 'responsavel_empresa')
        self.assertFalse(is_admin(u))
        self.assertTrue(is_responsavel_empresa(u))

    def test_aprovador_perfil(self):
        u = _user('aprov', groups=[GRUPOS.APROVADOR])
        self.assertEqual(get_user_profile(u), 'aprovador')
        self.assertFalse(is_admin(u))
        self.assertTrue(is_aprovador(u))
        self.assertTrue(is_gestor(u))

    def test_solicitante_perfil(self):
        u = _user('solic', groups=[GRUPOS.SOLICITANTE])
        self.assertEqual(get_user_profile(u), 'solicitante')
        self.assertFalse(is_admin(u))
        self.assertFalse(is_aprovador(u))
        self.assertTrue(is_engenheiro(u))

    def test_usuario_sem_grupo_perfil_none(self):
        u = _user('nada')
        self.assertIsNone(get_user_profile(u))
        self.assertFalse(is_admin(u))
        self.assertFalse(is_aprovador(u))
        self.assertFalse(is_responsavel_empresa(u))
        self.assertFalse(is_engenheiro(u))

    def test_gerentes_nao_e_gestao_perfil_none(self):
        u = _user('gerente', groups=[GRUPOS.GERENTES])
        self.assertIsNone(get_user_profile(u))
        self.assertFalse(is_admin(u))
        self.assertFalse(is_gestor(u))

    def test_multiplos_grupos_prioridade_admin(self):
        u = _user('multi', groups=[GRUPOS.ADMINISTRADOR, GRUPOS.SOLICITANTE, GRUPOS.APROVADOR])
        self.assertEqual(get_user_profile(u), 'admin')
        self.assertTrue(is_admin(u))
        self.assertTrue(is_gestor(u))
        self.assertTrue(is_engenheiro(u))


# ========== Filtros por obra: solicitante só vê suas obras, aprovador só as suas, Diário só projetos vinculados ==========


class TestFiltroSolicitantePorObra(TestCase):
    """Solicitante só vê pedidos das obras em que está vinculado (WorkOrderPermission)."""

    def setUp(self):
        self.client = Client()
        self.empresa = Empresa.objects.create(codigo='EMP-F', nome='Empresa Filtro')
        self.obra_a = Obra.objects.create(codigo='OBRA-A', nome='Obra A', empresa=self.empresa, ativo=True)
        self.obra_b = Obra.objects.create(codigo='OBRA-B', nome='Obra B', empresa=self.empresa, ativo=True)
        self.solicitante = _user('solic_uma_obra', groups=[GRUPOS.SOLICITANTE])
        WorkOrderPermission.objects.create(obra=self.obra_a, usuario=self.solicitante, tipo_permissao='solicitante', ativo=True)
        outro = _user('outro_solic', groups=[GRUPOS.SOLICITANTE])
        WorkOrderPermission.objects.create(obra=self.obra_b, usuario=outro, tipo_permissao='solicitante', ativo=True)
        self.pedido_obra_a = WorkOrder.objects.create(
            obra=self.obra_a, codigo='A-2025-1', nome_credor='C1', tipo_solicitacao='contrato',
            status='pendente', criado_por=self.solicitante
        )
        self.pedido_obra_b = WorkOrder.objects.create(
            obra=self.obra_b, codigo='B-2025-1', nome_credor='C2', tipo_solicitacao='contrato',
            status='pendente', criado_por=outro
        )

    def test_solicitante_ve_so_pedidos_das_obras_em_que_esta_vinculado(self):
        self.client.force_login(self.solicitante)
        r = self.client.get(reverse('gestao:list_workorders'))
        self.assertEqual(r.status_code, 200)
        workorders = list(r.context['page_obj'])
        ids_vistos = {wo.id for wo in workorders}
        self.assertIn(self.pedido_obra_a.id, ids_vistos, 'Deve ver pedido da obra A (sua obra)')
        self.assertNotIn(self.pedido_obra_b.id, ids_vistos, 'Não deve ver pedido da obra B (não vinculado)')


class TestFiltroAprovadorPorObra(TestCase):
    """Aprovador só vê pedidos das obras/empresas em que tem permissão."""

    def setUp(self):
        self.client = Client()
        self.emp1 = Empresa.objects.create(codigo='E1', nome='Empresa 1')
        self.emp2 = Empresa.objects.create(codigo='E2', nome='Empresa 2')
        self.obra1 = Obra.objects.create(codigo='O1', nome='Obra E1', empresa=self.emp1, ativo=True)
        self.obra2 = Obra.objects.create(codigo='O2', nome='Obra E2', empresa=self.emp2, ativo=True)
        self.aprovador = _user('aprov_e1', groups=[GRUPOS.APROVADOR])
        WorkOrderPermission.objects.create(obra=self.obra1, usuario=self.aprovador, tipo_permissao='aprovador', ativo=True)
        criador = _user('criador', groups=[GRUPOS.SOLICITANTE])
        WorkOrderPermission.objects.create(obra=self.obra1, usuario=criador, tipo_permissao='solicitante', ativo=True)
        WorkOrderPermission.objects.create(obra=self.obra2, usuario=criador, tipo_permissao='solicitante', ativo=True)
        self.pedido_obra1 = WorkOrder.objects.create(
            obra=self.obra1, codigo='O1-2025-1', nome_credor='X', tipo_solicitacao='contrato',
            status='pendente', criado_por=criador
        )
        self.pedido_obra2 = WorkOrder.objects.create(
            obra=self.obra2, codigo='O2-2025-1', nome_credor='Y', tipo_solicitacao='contrato',
            status='pendente', criado_por=criador
        )

    def test_aprovador_ve_so_pedidos_das_obras_onde_tem_permissao(self):
        self.client.force_login(self.aprovador)
        r = self.client.get(reverse('gestao:list_workorders'))
        self.assertEqual(r.status_code, 200)
        workorders = list(r.context['page_obj'])
        ids_vistos = {wo.id for wo in workorders}
        self.assertIn(self.pedido_obra1.id, ids_vistos, 'Aprovador deve ver pedido da obra onde é aprovador')
        self.assertNotIn(self.pedido_obra2.id, ids_vistos, 'Aprovador não deve ver pedido de outra empresa/obra')

    def test_aprovador_nao_acessa_aprovar_pedido_de_obra_sem_permissao(self):
        """Aprovador que tenta aprovar pedido de obra onde não tem permissão é redirecionado."""
        self.client.force_login(self.aprovador)
        r = self.client.get(reverse('gestao:approve_workorder', kwargs={'pk': self.pedido_obra2.pk}))
        self.assertEqual(r.status_code, 302, 'Não deve conseguir acessar tela de aprovar pedido de outra obra')
        self.assertIn(str(self.pedido_obra2.pk), r.get('Location', ''), 'Redirect deve voltar ao detalhe do pedido')


class TestSolicitanteSemObraVeSoSeusPedidos(TestCase):
    """Solicitante sem nenhuma obra vinculada vê só os pedidos que ele mesmo criou."""

    def setUp(self):
        self.client = Client()
        self.empresa = Empresa.objects.create(codigo='EMP', nome='Empresa')
        self.obra = Obra.objects.create(codigo='OB', nome='Obra', empresa=self.empresa, ativo=True)
        self.solicitante = _user('solic_sem_obra', groups=[GRUPOS.SOLICITANTE])
        outro = _user('outro', groups=[GRUPOS.SOLICITANTE])
        WorkOrderPermission.objects.create(obra=self.obra, usuario=outro, tipo_permissao='solicitante', ativo=True)
        self.meu_pedido = WorkOrder.objects.create(
            obra=self.obra, codigo='OB-2025-1', nome_credor='C', tipo_solicitacao='contrato',
            status='pendente', criado_por=self.solicitante
        )
        self.pedido_outro = WorkOrder.objects.create(
            obra=self.obra, codigo='OB-2025-2', nome_credor='D', tipo_solicitacao='contrato',
            status='pendente', criado_por=outro
        )

    def test_ve_so_pedidos_que_ele_criou(self):
        self.client.force_login(self.solicitante)
        r = self.client.get(reverse('gestao:list_workorders'))
        self.assertEqual(r.status_code, 200)
        workorders = list(r.context['page_obj'])
        ids_vistos = {wo.id for wo in workorders}
        self.assertIn(self.meu_pedido.id, ids_vistos)
        self.assertNotIn(self.pedido_outro.id, ids_vistos)


class TestDiarioSoProjetosVinculados(TestCase):
    """No Diário, usuário não-staff só vê projetos aos quais está vinculado (ProjectMember)."""

    def setUp(self):
        from datetime import date, timedelta
        self.client = Client()
        hoje = date.today()
        self.p1 = Project.objects.create(code='P1', name='Projeto 1', start_date=hoje, end_date=hoje + timedelta(days=365), is_active=True)
        self.p2 = Project.objects.create(code='P2', name='Projeto 2', start_date=hoje, end_date=hoje + timedelta(days=365), is_active=True)
        self.usuario = _user('user_diario')
        ProjectMember.objects.create(user=self.usuario, project=self.p1)

    def test_select_project_retorna_so_projetos_do_usuario(self):
        self.client.force_login(self.usuario)
        r = self.client.get(reverse('select-project'))
        self.assertEqual(r.status_code, 200)
        projects = list(r.context['projects'])
        codes = {p.code for p in projects}
        self.assertIn('P1', codes)
        self.assertNotIn('P2', codes)


class TestAdminVeTodosPedidos(TestCase):
    """Admin vê todos os pedidos de todas as obras."""

    def setUp(self):
        self.client = Client()
        self.empresa = Empresa.objects.create(codigo='EMP', nome='Empresa')
        self.obra = Obra.objects.create(codigo='OB', nome='Obra', empresa=self.empresa, ativo=True)
        self.admin = _user('adm_todos', groups=[GRUPOS.ADMINISTRADOR])
        criador = _user('criador', groups=[GRUPOS.SOLICITANTE])
        WorkOrderPermission.objects.create(obra=self.obra, usuario=criador, tipo_permissao='solicitante', ativo=True)
        self.pedido = WorkOrder.objects.create(
            obra=self.obra, codigo='OB-2025-1', nome_credor='C', tipo_solicitacao='contrato',
            status='pendente', criado_por=criador
        )

    def test_admin_ve_pedido_de_qualquer_obra(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse('gestao:list_workorders'))
        self.assertEqual(r.status_code, 200)
        workorders = list(r.context['page_obj'])
        ids_vistos = {wo.id for wo in workorders}
        self.assertIn(self.pedido.id, ids_vistos)
