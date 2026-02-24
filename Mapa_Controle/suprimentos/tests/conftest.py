"""
Fixtures compartilhadas para testes do módulo Mapa de Suprimentos.
"""
import pytest
from decimal import Decimal
from django.contrib.auth.models import User, Group
from django.utils import timezone
from datetime import date, timedelta
from obras.models import Obra, LocalObra
from suprimentos.models import Insumo, ItemMapa, RecebimentoObra, AlocacaoRecebimento, NotaFiscalEntrada


@pytest.fixture
def user_engenharia(db):
    """Cria um usuário do grupo ENGENHARIA."""
    user = User.objects.create_user(
        username='engenheiro_teste',
        email='eng@test.com',
        password='test123'
    )
    grupo, _ = Group.objects.get_or_create(name='ENGENHARIA')
    user.groups.add(grupo)
    return user


@pytest.fixture
def user_superuser(db):
    """Cria um superusuário."""
    return User.objects.create_superuser(
        username='admin_teste',
        email='admin@test.com',
        password='test123'
    )


@pytest.fixture
def obra(db):
    """Cria uma obra de teste."""
    return Obra.objects.create(
        nome='Obra Teste',
        ativa=True
    )


@pytest.fixture
def local_obra(db, obra):
    """Cria um local de obra."""
    return LocalObra.objects.create(
        obra=obra,
        nome='Bloco A',
        tipo='BLOCO'
    )


@pytest.fixture
def local_obra_b(db, obra):
    """Cria outro local de obra."""
    return LocalObra.objects.create(
        obra=obra,
        nome='Bloco B',
        tipo='BLOCO'
    )


@pytest.fixture
def insumo(db):
    """Cria um insumo de teste."""
    return Insumo.objects.create(
        codigo_sienge='5926',
        descricao='Cimento CP II-E-32',
        unidade='KG',
        ativo=True,
        eh_macroelemento=True
    )


@pytest.fixture
def insumo_pequeno(db):
    """Cria um insumo pequeno (não macroelemento)."""
    return Insumo.objects.create(
        codigo_sienge='1234',
        descricao='Parafuso 6x20',
        unidade='UND',
        ativo=True,
        eh_macroelemento=False
    )


@pytest.fixture
def recebimento_obra(db, obra, insumo):
    """Cria um recebimento na obra."""
    return RecebimentoObra.objects.create(
        obra=obra,
        insumo=insumo,
        numero_sc='12345',
        item_sc='',
        quantidade_solicitada=Decimal('1000.00'),
        quantidade_recebida=Decimal('800.00'),
        numero_pc='PC001',
        empresa_fornecedora='Fornecedor Teste'
    )


@pytest.fixture
def item_mapa(db, obra, insumo, local_obra, user_engenharia):
    """Cria um item do mapa."""
    return ItemMapa.objects.create(
        obra=obra,
        insumo=insumo,
        categoria='FUNDAÇÃO',
        local_aplicacao=local_obra,
        quantidade_planejada=Decimal('1000.00'),
        numero_sc='12345',
        criado_por=user_engenharia
    )


@pytest.fixture
def item_mapa_sem_sc(db, obra, insumo, local_obra):
    """Cria um item do mapa sem SC."""
    return ItemMapa.objects.create(
        obra=obra,
        insumo=insumo,
        categoria='FUNDAÇÃO',
        local_aplicacao=local_obra,
        quantidade_planejada=Decimal('500.00')
    )


@pytest.fixture
def alocacao(db, obra, insumo, local_obra, recebimento_obra, item_mapa, user_engenharia):
    """Cria uma alocação de recebimento."""
    return AlocacaoRecebimento.objects.create(
        obra=obra,
        insumo=insumo,
        local_aplicacao=local_obra,
        recebimento=recebimento_obra,
        item_mapa=item_mapa,
        quantidade_alocada=Decimal('400.00'),
        criado_por=user_engenharia
    )


@pytest.fixture
def nota_fiscal(db, obra, insumo, recebimento_obra):
    """Cria uma nota fiscal de entrada."""
    return NotaFiscalEntrada.objects.create(
        obra=obra,
        insumo=insumo,
        recebimento=recebimento_obra,
        numero_pc='PC001',
        numero_nf='NF001',
        data_entrada=date.today(),
        quantidade=Decimal('800.00')
    )

