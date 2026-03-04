"""
Testes da importação Sienge via Excel (XLSX).

Garante que o fluxo Excel → detecção de cabeçalho → forward-fill → CSV → import
funciona para linhas e colunas no formato típico do Sienge.

Rodar: python manage.py test suprimentos.tests.test_import_excel -v 2
"""
from datetime import date
from io import BytesIO
import pandas as pd
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from mapa_obras.models import Obra
from core.models import Project, ProjectMember
from suprimentos.models import Insumo, RecebimentoObra

User = get_user_model()


def _criar_xlsx_sienge_minimo():
    """
    Cria um XLSX mínimo no formato Sienge:
    - Linhas 0-1: título (cabeçalho real na linha 2)
    - Linha 2: nomes das colunas
    - Linhas 3+: dados, com uma linha de "continuação" (SC/Obra em branco para testar forward-fill)
    """
    import numpy as np
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        # Aba única: título nas 2 primeiras linhas, cabeçalho na 3ª, dados a seguir
        # Usar np.nan para células vazias (como o Excel do Sienge com células mescladas)
        rows = [
            ['Mapa de Controle - Exportação Sienge'],
            [],  # linha vazia
            [
                'Nº DA SC', 'Cód. Obra', 'Cód. Insumo', 'Descrição do Insumo',
                'Qt. Solicitada', 'Quant. Entregue', 'Nº do PC', 'Previsão de Entrega', 'Fornecedor',
                'Saldo a Entregar'
            ],
            [
                'SC-2026-001', 'OBR-IMP-TEST', 'INS-TEST-1', 'Cimento CP II',
                '100', '60', 'PC-001', '15/03/2026', 'Fornecedor Alpha',
                '40'
            ],
            [
                np.nan, np.nan, 'INS-TEST-2', 'Areia Média',  # SC e Obra vazios (forward-fill)
                '50', '25', np.nan, np.nan, np.nan,
                '25'
            ],
            [
                'SC-2026-002', 'OBR-IMP-TEST', 'INS-TEST-3', 'Brita 1',
                '200', '0', np.nan, np.nan, np.nan,
                '200'
            ],
        ]
        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name='Plan1', index=False, header=False)
    buf.seek(0)
    return buf.getvalue()


class TestImportExcelSienge(TestCase):
    """Testa importação de arquivo Excel (XLSX) no formato Sienge."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.grupo_eng, _ = Group.objects.get_or_create(name='Mapa de Suprimentos')

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='teste_import_excel',
            password='senha123',
        )
        self.user.groups.add(self.grupo_eng)
        # Obra e projeto para o usuário ter acesso
        self.obra = Obra.objects.create(
            codigo_sienge='OBR-IMP-TEST',
            nome='Obra Teste Import Excel',
            ativa=True,
        )
        self.project = Project.objects.create(
            name='Projeto Teste Import',
            code='OBR-IMP-TEST',
            start_date=date(2024, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        ProjectMember.objects.get_or_create(user=self.user, project=self.project)
        # Insumos que aparecem no XLSX (sem eles o comando ignora a linha)
        for cod, desc in [
            ('INS-TEST-1', 'Cimento CP II'),
            ('INS-TEST-2', 'Areia Média'),
            ('INS-TEST-3', 'Brita 1'),
        ]:
            Insumo.objects.get_or_create(
                codigo_sienge=cod,
                defaults={'descricao': desc, 'unidade': 'KG', 'ativo': True, 'eh_macroelemento': True}
            )

    def test_upload_xlsx_aceito_e_retorna_200(self):
        """Upload de arquivo .xlsx na tela de importar deve ser aceito (formato válido)."""
        self.client.login(username='teste_import_excel', password='senha123')
        xlsx_content = _criar_xlsx_sienge_minimo()
        arquivo = SimpleUploadedFile(
            'mapa_sienge.xlsx',
            xlsx_content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response = self.client.post(reverse('engenharia:importar_sienge'), {'arquivo': arquivo}, follow=True)
        self.assertEqual(response.status_code, 200, 'Resposta deve ser 200 após processar importação')

    def test_import_xlsx_cria_recebimentos_obra(self):
        """
        Após importar o XLSX de teste, deve existir pelo menos um RecebimentoObra
        para a obra OBR-IMP-TEST (confirma que detecção de colunas e linhas funcionou).
        """
        self.client.login(username='teste_import_excel', password='senha123')
        antes = RecebimentoObra.objects.filter(obra=self.obra).count()
        xlsx_content = _criar_xlsx_sienge_minimo()
        arquivo = SimpleUploadedFile(
            'mapa_sienge.xlsx',
            xlsx_content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.client.post(reverse('engenharia:importar_sienge'), {'arquivo': arquivo}, follow=True)
        depois = RecebimentoObra.objects.filter(obra=self.obra).count()
        self.assertGreater(
            depois, antes,
            'A importação do XLSX deve criar pelo menos um RecebimentoObra para a obra de teste. '
            'Antes=%s, Depois=%s. Verifique detecção de cabeçalho e colunas (Nº DA SC, Cód. Obra, Cód. Insumo).'
            % (antes, depois)
        )

    def test_import_xlsx_forward_fill_linha_sem_sc(self):
        """
        A segunda linha do XLSX tem SC e Obra em branco (simula célula mesclada).
        O import deve fazer forward-fill e criar recebimento para as 3 linhas (3 insumos).
        """
        self.client.login(username='teste_import_excel', password='senha123')
        xlsx_content = _criar_xlsx_sienge_minimo()
        arquivo = SimpleUploadedFile(
            'mapa_sienge.xlsx',
            xlsx_content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.client.post(reverse('engenharia:importar_sienge'), {'arquivo': arquivo}, follow=True)
        total = RecebimentoObra.objects.filter(obra=self.obra).count()
        self.assertEqual(
            total, 3,
            'As 3 linhas de dados do XLSX devem gerar 3 RecebimentoObra (forward-fill na linha com SC/Obra em branco). Obtido: %s.'
            % total
        )
        # O comando normaliza numero_sc (remove hífens): SC-2026-001 -> SC2026001
        numero_sc_normalizado = 'SC2026001'
        rec_ins2 = RecebimentoObra.objects.filter(
            obra=self.obra,
            insumo__codigo_sienge='INS-TEST-2',
            numero_sc=numero_sc_normalizado
        ).first()
        self.assertIsNotNone(
            rec_ins2,
            'Linha com SC em branco deve ter sido preenchida por forward-fill (SC-2026-001) para INS-TEST-2. '
            'Numero no banco é normalizado (sem hífen): %s.' % numero_sc_normalizado
        )
