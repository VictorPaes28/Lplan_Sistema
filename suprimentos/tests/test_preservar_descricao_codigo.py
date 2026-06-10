"""Preserva descrição do levantamento ao vincular código Sienge existente."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, Client
from django.urls import reverse

from accounts.groups import GRUPOS
from core.models import Project, ProjectMember
from mapa_obras.models import Obra
from suprimentos.models import Insumo, ItemMapa

User = get_user_model()


class TestPreservarDescricaoAoVincularCodigo(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Group.objects.get_or_create(name=GRUPOS.ENGENHARIA)

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='preserva_desc',
            password='senha123',
            email='preserva@teste.com',
        )
        self.user.groups.add(Group.objects.get(name=GRUPOS.ENGENHARIA))
        self.obra = Obra.objects.create(
            codigo_sienge='OBR-PRES',
            nome='Obra Preserva Desc',
            ativa=True,
        )
        self.project = Project.objects.create(
            name='Proj Preserva',
            code='OBR-PRES',
            start_date=date(2024, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        ProjectMember.objects.get_or_create(user=self.user, project=self.project)
        self.insumo_lev = Insumo.objects.create(
            codigo_sienge='SM-LEV-TESTPRES01',
            descricao='Aço 6.3 mm',
            unidade='KG',
        )
        self.insumo_sienge = Insumo.objects.create(
            codigo_sienge='15959',
            descricao='FERRO 5.0 mm',
            unidade='KG',
        )
        self.item = ItemMapa.objects.create(
            obra=self.obra,
            insumo=self.insumo_lev,
            categoria='FUNDAÇÃO',
            quantidade_planejada=Decimal('100'),
            criado_por=self.user,
        )
        session = self.client.session
        session['obra_id'] = self.obra.id
        session.save()
        self.client.login(username='preserva_desc', password='senha123')

    def test_vincular_codigo_preserva_descricao_levantamento(self):
        url = reverse('suprimentos:item_atualizar_campo')
        r = self.client.post(
            url,
            data={
                'item_id': self.item.id,
                'field': 'insumo_codigo',
                'value': '15959',
            },
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(data.get('descricao_exibida'), 'Aço 6.3 mm')

        self.item.refresh_from_db()
        self.assertEqual(self.item.insumo_id, self.insumo_sienge.id)
        self.assertEqual(self.item.descricao_override, 'Aço 6.3 mm')
