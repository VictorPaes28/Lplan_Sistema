"""
Catálogo e colaboradores de demonstração do módulo RH.

Usado por: python manage.py resetar_demo_rh
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from accounts.groups import GRUPOS
from recursos_humanos.models import (
    AdmissaoHistorico,
    CargoCatalogo,
    CargoRH,
    Colaborador,
    ContratoAdmissao,
    DocumentoColaborador,
    ObraLocal,
    PrazoContrato,
    TipoDocumento,
)
from recursos_humanos.services.admissao_actions import instanciar_documentos

OBRAS = ('Obra Paulista', 'Obra Lapa', 'Obra ABC', 'Obra Tatuapé', 'Obra Morumbi')

CARGOS_RH = (
    'Eletricista',
    'Pedreiro',
    'Servente',
    'Assistente Administrativo',
    'Mestre de Obras',
    'Ajudante de Produção',
    'Engenheiro Civil',
    'Técnico de Segurança',
    'Assistente de Compras',
    'Encarregado de Obras',
)

# nome, aplica_a, tem_validade, dias, obrigatorio, ordem, categoria, cargos (nomes)
TIPOS_CFG = (
    ('RG', 'todos', False, None, True, 1, 'pessoais', ()),
    ('CPF', 'todos', False, None, True, 2, 'pessoais', ()),
    ('Título de Eleitor', 'todos', False, None, True, 3, 'pessoais', ()),
    ('Certidão de Nascimento/Casamento', 'todos', False, None, True, 4, 'pessoais', ()),
    ('Comprovante Bancário', 'todos', False, None, True, 5, 'comprovantes', ()),
    ('Comprovante de Endereço', 'todos', True, 90, True, 6, 'comprovantes', ()),
    ('Certificado de Escolaridade', 'por_cargo', False, None, False, 7, 'pessoais', ('Assistente Administrativo', 'Assistente de Compras', 'Engenheiro Civil')),
    ('PIS', 'todos', False, None, True, 8, 'pessoais', ()),
    ('CTPS (Carteira de Trabalho)', 'todos', False, None, True, 9, 'pessoais', ()),
    ('Documentos dos Filhos', 'todos', False, None, False, 10, 'pessoais', ()),
    ('ASO – Atestado de Saúde Ocupacional', 'todos', True, 365, True, 11, 'saude', ()),
    ('NR-35 – Trabalho em Altura', 'por_cargo', True, 365, True, 12, 'treinamentos', ('Eletricista', 'Servente', 'Pedreiro', 'Ajudante de Produção', 'Mestre de Obras')),
    ('NR-10 – Segurança em Eletricidade', 'por_cargo', True, 730, False, 13, 'treinamentos', ('Eletricista',)),
    ('FGTS – Extrato', 'todos', True, 30, False, 14, 'outros', ()),
)


def _aware(dt: datetime) -> datetime:
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


def _rh_user() -> User | None:
    return (
        User.objects.filter(is_active=True, groups__name=GRUPOS.RECURSOS_HUMANOS)
        .order_by('pk')
        .first()
        or User.objects.filter(is_active=True, is_superuser=True).order_by('pk').first()
    )


def limpar_dados_operacionais_rh() -> dict:
    """Remove colaboradores e dados ligados a eles (simulações anteriores)."""
    stats = {
        'colaboradores': Colaborador.objects.count(),
        'contratos': ContratoAdmissao.objects.count(),
        'prazos': PrazoContrato.objects.count(),
    }
    ContratoAdmissao.objects.all().delete()
    PrazoContrato.objects.all().delete()
    Colaborador.objects.all().delete()
    return stats


def garantir_catalogo_base() -> dict:
    """Obras, cargos RH, catálogo e tipos de documento."""
    obras = {}
    for nome in OBRAS:
        obras[nome], _ = ObraLocal.objects.get_or_create(nome=nome)

    cargos = {}
    for nome in CARGOS_RH:
        cargos[nome], _ = CargoRH.objects.get_or_create(nome=nome)
        CargoCatalogo.objects.get_or_create(nome=nome)

    tipos = {}
    for nome, aplica, val, dias, obrig, ordem, cat, cargos_nomes in TIPOS_CFG:
        tipo, created = TipoDocumento.objects.update_or_create(
            nome=nome,
            defaults={
                'aplica_a': aplica,
                'tem_validade': val,
                'dias_validade': dias,
                'obrigatorio': obrig,
                'ordem': ordem,
                'categoria': cat,
                'ativo': True,
            },
        )
        if aplica == TipoDocumento.AplicaA.POR_CARGO and cargos_nomes:
            tipo.cargos_aplicaveis.set([cargos[c] for c in cargos_nomes])
        tipos[nome] = tipo

    return {'obras': obras, 'cargos': cargos, 'tipos': tipos}


def _criar_colab(
    *,
    obras: dict,
    cargos: dict,
    responsavel: User | None,
    rh_user: User | None,
    autor_rh: str,
    **fields,
) -> Colaborador:
    obra_nomes = fields.pop('obra_nomes', ())
    cargo_rh_nome = fields.pop('cargo_rh_nome', fields.get('cargo'))
    historico = fields.pop('historico', ())
    docs_spec = fields.pop('docs_spec', None)

    colab = Colaborador.objects.create(
        cargo_rh=cargos.get(cargo_rh_nome),
        gestor_aprovador_user=responsavel,
        gestor_aprovador=(
            (responsavel.get_full_name() or responsavel.username) if responsavel else 'Responsável RH'
        ),
        requisicao_criada_por=rh_user,
        empresa='Lplan Engenharia',
        tipo_contrato=fields.pop('tipo_contrato', 'CLT'),
        salario=fields.pop('salario', '3.500,00'),
        motivo_admissao=fields.pop('motivo_admissao', 'Nova contratação'),
        requisicao_aprovada_gestor=fields.pop('requisicao_aprovada_gestor', True),
        **fields,
    )
    colab.obras.set([obras[n] for n in obra_nomes])

    if docs_spec is not None:
        instanciar_documentos(colab)
        tipos_map = {d.tipo.nome: d for d in colab.documentos.select_related('tipo')}
        for spec in docs_spec:
            nome_tipo = spec[0]
            doc = tipos_map.get(nome_tipo)
            if not doc:
                continue
            doc.status = spec[1]
            if len(spec) > 2 and spec[2]:
                doc.vencimento = spec[2]
            if len(spec) > 3 and spec[3]:
                doc.data_emissao = spec[3]
            doc.save()
    elif colab.etapa_admissao >= 2 or colab.status == Colaborador.Status.ATIVO:
        instanciar_documentos(colab)

    if colab.etapa_admissao >= 2 and colab.status == Colaborador.Status.EM_ADMISSAO:
        colab.gerar_token_portal()

    for ev in historico:
        AdmissaoHistorico.objects.create(
            colaborador=colab,
            etapa=ev[0],
            descricao=ev[1],
            data_hora=_aware(ev[2]),
            autor=ev[3],
            concluido=ev[4],
        )

    return colab


@transaction.atomic
def popular_demo_rh() -> dict:
    from recursos_humanos.services.contrato import obter_ou_criar_contrato
    from recursos_humanos.services.prazo_contrato import aplicar_data_admissao_oficial

    hoje = timezone.localdate()
    gestor = _rh_user()
    rh_user = gestor
    autor_rh = f'RH — {(rh_user.get_full_name() or rh_user.username) if rh_user else "Sistema"}'

    limpar_dados_operacionais_rh()
    ctx = garantir_catalogo_base()
    obras, cargos = ctx['obras'], ctx['cargos']

    criados = []

    # ── Fluxo de admissão ──────────────────────────────────────────────

    patricia = _criar_colab(
        obras=obras, cargos=cargos, responsavel=gestor, rh_user=rh_user, autor_rh=autor_rh,
        nome='Patrícia Gomes',
        cpf='111.000.999-88',
        email='patricia.gomes@email.com',
        telefone='11987654321',
        cargo='Assistente de Compras',
        cargo_rh_nome='Assistente de Compras',
        status=Colaborador.Status.EM_ADMISSAO,
        etapa_admissao=2,
        data_admissao=hoje - timedelta(days=3),
        obra_nomes=('Obra Lapa',),
        historico=[
            (1, 'Requisição criada', datetime.combine(hoje - timedelta(days=3), datetime.min.time().replace(hour=10, minute=30)), autor_rh, True),
            (1, 'Coleta de documentos iniciada automaticamente', datetime.combine(hoje - timedelta(days=3), datetime.min.time().replace(hour=10, minute=31)), autor_rh, True),
            (2, f'Link do portal enviado por e-mail para patricia.gomes@email.com', datetime.combine(hoje - timedelta(days=3), datetime.min.time().replace(hour=10, minute=32)), autor_rh, True),
        ],
        docs_spec=[
            ('RG', DocumentoColaborador.Status.FALTANDO),
            ('CPF', DocumentoColaborador.Status.FALTANDO),
            ('Título de Eleitor', DocumentoColaborador.Status.FALTANDO),
            ('Certidão de Nascimento/Casamento', DocumentoColaborador.Status.FALTANDO),
            ('Comprovante Bancário', DocumentoColaborador.Status.PENDENTE),
            ('Comprovante de Endereço', DocumentoColaborador.Status.FALTANDO),
            ('PIS', DocumentoColaborador.Status.FALTANDO),
            ('CTPS (Carteira de Trabalho)', DocumentoColaborador.Status.FALTANDO),
            ('ASO – Atestado de Saúde Ocupacional', DocumentoColaborador.Status.FALTANDO),
            ('FGTS – Extrato', DocumentoColaborador.Status.FALTANDO),
        ],
    )
    criados.append(patricia.nome)

    rafael = _criar_colab(
        obras=obras, cargos=cargos, responsavel=gestor, rh_user=rh_user, autor_rh=autor_rh,
        nome='Rafael Mendes',
        cpf='222.111.000-99',
        email='rafael.mendes@email.com',
        telefone='11976543210',
        cargo='Servente',
        cargo_rh_nome='Servente',
        status=Colaborador.Status.EM_ADMISSAO,
        etapa_admissao=2,
        data_admissao=hoje - timedelta(days=8),
        obra_nomes=('Obra ABC',),
        historico=[
            (1, 'Requisição criada', datetime.combine(hoje - timedelta(days=8), datetime.min.time().replace(hour=9)), autor_rh, True),
            (1, 'Coleta de documentos iniciada automaticamente', datetime.combine(hoje - timedelta(days=8), datetime.min.time().replace(hour=9, minute=1)), autor_rh, True),
            (2, 'RG, CPF e comprovante de endereço recebidos', datetime.combine(hoje - timedelta(days=5), datetime.min.time().replace(hour=14)), 'Rafael Mendes (portal)', True),
        ],
        docs_spec=[
            ('RG', DocumentoColaborador.Status.RECEBIDO),
            ('CPF', DocumentoColaborador.Status.RECEBIDO),
            ('Título de Eleitor', DocumentoColaborador.Status.FALTANDO),
            ('Certidão de Nascimento/Casamento', DocumentoColaborador.Status.RECEBIDO),
            ('Comprovante Bancário', DocumentoColaborador.Status.PENDENTE),
            ('Comprovante de Endereço', DocumentoColaborador.Status.RECEBIDO, hoje + timedelta(days=60)),
            ('PIS', DocumentoColaborador.Status.FALTANDO),
            ('CTPS (Carteira de Trabalho)', DocumentoColaborador.Status.FALTANDO),
            ('ASO – Atestado de Saúde Ocupacional', DocumentoColaborador.Status.FALTANDO),
            ('NR-35 – Trabalho em Altura', DocumentoColaborador.Status.FALTANDO),
        ],
    )
    criados.append(rafael.nome)

    juliana = _criar_colab(
        obras=obras, cargos=cargos, responsavel=gestor, rh_user=rh_user, autor_rh=autor_rh,
        nome='Juliana Costa',
        cpf='333.222.111-00',
        email='juliana.costa@email.com',
        telefone='11965432109',
        rg='45.678.901-2',
        data_nascimento=date(1995, 4, 12),
        endereco='Rua das Flores, 120 – São Paulo/SP',
        dados_bancarios='Itaú – Ag. 1234 / CC 56789-0',
        escolaridade='Ensino Médio Completo',
        tamanho_camisa='M',
        tamanho_bota='38',
        cargo='Assistente Administrativo',
        cargo_rh_nome='Assistente Administrativo',
        status=Colaborador.Status.EM_ADMISSAO,
        etapa_admissao=3,
        data_admissao=hoje - timedelta(days=14),
        obra_nomes=('Obra Paulista',),
        historico=[
            (1, 'Requisição criada', datetime.combine(hoje - timedelta(days=14), datetime.min.time().replace(hour=11)), autor_rh, True),
            (1, 'Coleta de documentos iniciada automaticamente', datetime.combine(hoje - timedelta(days=14), datetime.min.time().replace(hour=11, minute=1)), autor_rh, True),
            (2, 'Documentação conferida', datetime.combine(hoje - timedelta(days=7), datetime.min.time().replace(hour=16)), autor_rh, True),
            (3, 'Aguardando validação final do RH', datetime.combine(hoje - timedelta(days=6), datetime.min.time().replace(hour=9)), autor_rh, False),
        ],
    )
    for doc in juliana.documentos.all():
        doc.status = DocumentoColaborador.Status.RECEBIDO
        if doc.tipo.tem_validade and doc.tipo.dias_validade:
            doc.data_emissao = hoje - timedelta(days=30)
            doc.vencimento = hoje + timedelta(days=doc.tipo.dias_validade - 30)
        doc.save()
    criados.append(juliana.nome)

    diego = _criar_colab(
        obras=obras, cargos=cargos, responsavel=gestor, rh_user=rh_user, autor_rh=autor_rh,
        nome='Diego Martins',
        cpf='000.999.888-77',
        email='diego.martins@email.com',
        telefone='11954321098',
        rg='12.345.678-9',
        data_nascimento=date(1990, 8, 20),
        endereco='Av. Brasil, 500 – São Paulo/SP',
        dados_bancarios='Bradesco – Ag. 4321 / CC 11223-4',
        pis='123.45678.90-1',
        escolaridade='Ensino Fundamental',
        tamanho_camisa='G',
        tamanho_bota='42',
        cargo='Ajudante de Produção',
        cargo_rh_nome='Ajudante de Produção',
        status=Colaborador.Status.EM_ADMISSAO,
        etapa_admissao=4,
        data_admissao=hoje - timedelta(days=21),
        obra_nomes=('Obra Tatuapé',),
        historico=[
            (1, 'Requisição criada', datetime.combine(hoje - timedelta(days=21), datetime.min.time().replace(hour=10)), autor_rh, True),
            (2, 'Documentos conferidos', datetime.combine(hoje - timedelta(days=12), datetime.min.time().replace(hour=15)), autor_rh, True),
            (3, 'Validação final concluída', datetime.combine(hoje - timedelta(days=8), datetime.min.time().replace(hour=9)), autor_rh, True),
            (4, 'Contrato enviado para assinatura (ZapSign)', datetime.combine(hoje - timedelta(days=5), datetime.min.time().replace(hour=14)), 'Sistema', False),
        ],
    )
    for doc in diego.documentos.all():
        doc.status = DocumentoColaborador.Status.RECEBIDO
        if doc.tipo.tem_validade and doc.tipo.dias_validade:
            doc.data_emissao = hoje - timedelta(days=15)
            doc.vencimento = hoje + timedelta(days=doc.tipo.dias_validade - 15)
        doc.save()
    criados.append(diego.nome)

    # ── Ativos ─────────────────────────────────────────────────────────

    carlos = _criar_colab(
        obras=obras, cargos=cargos, responsavel=gestor, rh_user=rh_user, autor_rh=autor_rh,
        nome='Carlos Eduardo Mendes',
        cpf='423.891.047-55',
        email='carlos.mendes@lplan.com.br',
        telefone='11943210987',
        rg='32.456.789-0',
        data_nascimento=date(1988, 3, 15),
        endereco='Rua das Acácias, 234 – São Paulo/SP',
        dados_bancarios='Caixa – Ag. 0043 / CC 12345-6',
        pis='127.45678.90-1',
        escolaridade='Ensino Médio Completo',
        tamanho_camisa='G',
        tamanho_bota='42',
        cargo='Encarregado de Obras',
        cargo_rh_nome='Encarregado de Obras',
        status=Colaborador.Status.ATIVO,
        etapa_admissao=5,
        data_admissao=hoje - timedelta(days=41),
        obra_nomes=('Obra Paulista', 'Obra Morumbi'),
    )
    aplicar_data_admissao_oficial(carlos, hoje - timedelta(days=41), rh_user)
    for doc in carlos.documentos.all():
        doc.status = DocumentoColaborador.Status.RECEBIDO
        if doc.tipo.nome == 'ASO – Atestado de Saúde Ocupacional':
            doc.vencimento = hoje + timedelta(days=120)
        elif doc.tipo.nome == 'NR-35 – Trabalho em Altura':
            doc.vencimento = hoje + timedelta(days=200)
        elif doc.tipo.tem_validade:
            doc.vencimento = hoje + timedelta(days=90)
        doc.save()
    criados.append(carlos.nome)

    roberto = _criar_colab(
        obras=obras, cargos=cargos, responsavel=gestor, rh_user=rh_user, autor_rh=autor_rh,
        nome='Roberto Silva',
        cpf='987.654.321-00',
        email='roberto.silva@lplan.com.br',
        telefone='11932109876',
        rg='41.234.567-8',
        data_nascimento=date(1985, 7, 22),
        endereco='Av. Paulista, 1000 – São Paulo/SP',
        dados_bancarios='Bradesco – Ag. 1234 / CC 56789-0',
        pis='234.56789.01-2',
        escolaridade='Ensino Médio',
        tamanho_camisa='GG',
        tamanho_bota='43',
        cargo='Pedreiro',
        cargo_rh_nome='Pedreiro',
        status=Colaborador.Status.ATIVO,
        etapa_admissao=5,
        data_admissao=date(2021, 9, 1),
        obra_nomes=('Obra Paulista',),
    )
    contrato_roberto = obter_ou_criar_contrato(roberto)
    contrato_roberto.data_admissao_oficial = date(2021, 9, 1)
    contrato_roberto.status = ContratoAdmissao.Status.CONCLUIDO
    contrato_roberto.save(update_fields=['data_admissao_oficial', 'status'])
    prazo_roberto = PrazoContrato.objects.filter(
        colaborador=roberto,
        tipo=PrazoContrato.Tipo.EXPERIENCIA,
        status=PrazoContrato.Status.ATIVO,
    ).first()
    if prazo_roberto:
        prazo_roberto.status = PrazoContrato.Status.CONVERTIDO
        prazo_roberto.save(update_fields=['status'])
    for doc in roberto.documentos.all():
        doc.status = DocumentoColaborador.Status.RECEBIDO
        if doc.tipo.nome == 'ASO – Atestado de Saúde Ocupacional':
            doc.vencimento = hoje + timedelta(days=22)
        elif doc.tipo.nome == 'NR-35 – Trabalho em Altura':
            doc.vencimento = hoje + timedelta(days=150)
        elif doc.tipo.tem_validade:
            doc.vencimento = hoje + timedelta(days=60)
        doc.save()
    criados.append(roberto.nome)

    camila = _criar_colab(
        obras=obras, cargos=cargos, responsavel=gestor, rh_user=rh_user, autor_rh=autor_rh,
        nome='Camila Rocha',
        cpf='999.888.777-55',
        email='camila.rocha@lplan.com.br',
        telefone='11921098765',
        rg='98.765.432-1',
        data_nascimento=date(1998, 12, 14),
        endereco='Av. Interlagos, 333 – São Paulo/SP',
        dados_bancarios='Nubank – CC 11111-1',
        escolaridade='Superior em Engenharia Civil',
        tamanho_camisa='P',
        tamanho_bota='36',
        cargo='Estagiária de Engenharia',
        cargo_rh_nome='Engenheiro Civil',
        status=Colaborador.Status.ATIVO,
        etapa_admissao=5,
        data_admissao=hoje - timedelta(days=75),
        obra_nomes=('Obra Paulista', 'Obra Lapa'),
        tipo_contrato='Estágio',
    )
    for doc in camila.documentos.all():
        doc.status = DocumentoColaborador.Status.RECEBIDO
        if doc.tipo.tem_validade and doc.tipo.dias_validade:
            doc.vencimento = hoje + timedelta(days=90)
        doc.save()
    PrazoContrato.objects.create(
        colaborador=camila,
        tipo='estagio',
        data_inicio=hoje - timedelta(days=75),
        data_fim=hoje + timedelta(days=12),
        status='ativo',
    )
    criados.append(camila.nome)

    sandra = _criar_colab(
        obras=obras, cargos=cargos, responsavel=gestor, rh_user=rh_user, autor_rh=autor_rh,
        nome='Sandra Mendes',
        cpf='777.666.555-33',
        email='sandra.mendes@email.com',
        cargo='Técnica de Segurança',
        cargo_rh_nome='Técnico de Segurança',
        status=Colaborador.Status.DESLIGADO,
        etapa_admissao=5,
        data_admissao=date(2020, 6, 1),
        obra_nomes=('Obra Tatuapé',),
    )
    for doc in sandra.documentos.all():
        doc.status = DocumentoColaborador.Status.RECEBIDO
        doc.save()
    criados.append(sandra.nome)

    return {
        'colaboradores': len(criados),
        'nomes': criados,
        'obras': len(obras),
        'cargos': len(cargos),
        'tipos_documento': TipoDocumento.objects.filter(ativo=True).count(),
    }
