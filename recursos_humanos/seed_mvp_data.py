"""Seed demo data from Figma MVP."""
from datetime import date, datetime

from django.utils import timezone


def seed_rh_demo(apps, schema_editor):
    ObraLocal = apps.get_model('recursos_humanos', 'ObraLocal')
    TipoDocumento = apps.get_model('recursos_humanos', 'TipoDocumento')
    Colaborador = apps.get_model('recursos_humanos', 'Colaborador')
    DocumentoColaborador = apps.get_model('recursos_humanos', 'DocumentoColaborador')
    AdmissaoHistorico = apps.get_model('recursos_humanos', 'AdmissaoHistorico')

    if Colaborador.objects.exists():
        return

    obras = {}
    for nome in ['Obra Paulista', 'Obra Morumbi', 'Obra Lapa', 'Obra ABC', 'Obra Tatuapé']:
        obras[nome], _ = ObraLocal.objects.get_or_create(nome=nome)

    tipos_cfg = [
        ('RG', 'todos', False, None, True, 1),
        ('CPF', 'todos', False, None, True, 2),
        ('Título de Eleitor', 'todos', False, None, True, 3),
        ('Certidão de Nascimento/Casamento', 'todos', False, None, True, 4),
        ('Comprovante Bancário', 'todos', False, None, True, 5),
        ('Comprovante de Endereço', 'todos', True, 90, True, 6),
        ('Certificado de Escolaridade', 'por_cargo', False, None, False, 7),
        ('PIS', 'todos', False, None, True, 8),
        ('CTPS (Carteira de Trabalho)', 'todos', False, None, True, 9),
        ('Documentos dos Filhos', 'todos', False, None, False, 10),
        ('ASO – Atestado de Saúde Ocupacional', 'todos', True, 365, True, 11),
        ('NR-35 – Trabalho em Altura', 'por_cargo', True, 365, True, 12),
        ('NR-10 – Segurança em Eletricidade', 'por_cargo', True, 730, False, 13),
        ('FGTS – Extrato', 'todos', True, 30, False, 14),
    ]
    tipos = {}
    for nome, aplica, val, dias, obrig, ordem in tipos_cfg:
        tipos[nome], _ = TipoDocumento.objects.get_or_create(
            nome=nome,
            defaults={
                'aplica_a': aplica,
                'tem_validade': val,
                'dias_validade': dias,
                'obrigatorio': obrig,
                'ordem': ordem,
            },
        )

    def add_docs(colab, specs):
        for tipo_nome, status, venc in specs:
            DocumentoColaborador.objects.create(
                colaborador=colab,
                tipo=tipos[tipo_nome],
                status=status,
                vencimento=venc,
            )

    def aware(dt):
        return timezone.make_aware(dt) if timezone.is_naive(dt) else dt

    c1 = Colaborador.objects.create(
        nome='Carlos Eduardo Mendes',
        cpf='423.891.047-55',
        rg='32.456.789-0',
        data_nascimento=date(1988, 3, 15),
        endereco='Rua das Acácias, 234, Apto 12 – São Paulo/SP',
        dados_bancarios='Caixa Econômica – Ag. 0043 / CC 12345-6',
        pis='127.45678.90-1',
        escolaridade='Ensino Médio Completo',
        tamanho_camisa='G',
        tamanho_bota='42',
        cargo='Encarregado de Obras',
        empresa='Construtora Horizonte Ltda.',
        status='ativo',
        data_admissao=date(2022, 1, 12),
        etapa_admissao=5,
    )
    c1.obras.set([obras['Obra Paulista'], obras['Obra Morumbi']])
    add_docs(c1, [
        ('RG', 'received', None),
        ('CPF', 'received', None),
        ('Título de Eleitor', 'received', None),
        ('Certidão de Nascimento/Casamento', 'received', None),
        ('Comprovante Bancário', 'received', None),
        ('Comprovante de Endereço', 'received', None),
        ('Certificado de Escolaridade', 'received', None),
        ('PIS', 'received', None),
        ('CTPS (Carteira de Trabalho)', 'received', None),
        ('Documentos dos Filhos', 'received', None),
        ('ASO – Atestado de Saúde Ocupacional', 'pending', date(2026, 6, 25)),
        ('NR-35 – Trabalho em Altura', 'missing', date(2026, 7, 30)),
    ])

    c2 = Colaborador.objects.create(
        nome='Fernanda Lima Souza',
        cpf='987.654.321-00',
        rg='41.234.567-8',
        data_nascimento=date(1994, 7, 22),
        endereco='Av. Paulista, 1000, Conj. 52 – São Paulo/SP',
        dados_bancarios='Bradesco – Ag. 1234 / CC 56789-0',
        pis='234.56789.01-2',
        escolaridade='Superior em Administração',
        tamanho_camisa='M',
        tamanho_bota='37',
        cargo='Auxiliar Administrativa',
        empresa='Construtora Horizonte Ltda.',
        status='em_admissao',
        data_admissao=date(2026, 6, 5),
        etapa_admissao=2,
    )
    c2.obras.set([obras['Obra Lapa']])
    add_docs(c2, [
        ('RG', 'received', None),
        ('CPF', 'received', None),
        ('Título de Eleitor', 'missing', None),
        ('Certidão de Nascimento/Casamento', 'received', None),
        ('Comprovante Bancário', 'pending', None),
        ('Comprovante de Endereço', 'received', None),
        ('Certificado de Escolaridade', 'received', None),
        ('PIS', 'missing', None),
        ('CTPS (Carteira de Trabalho)', 'missing', None),
        ('Documentos dos Filhos', 'missing', None),
        ('ASO – Atestado de Saúde Ocupacional', 'missing', None),
        ('NR-35 – Trabalho em Altura', 'missing', None),
    ])
    for ev in [
        (1, 'Requisição criada', datetime(2026, 6, 5, 9, 14), 'RH — Carla Moreira', True),
        (1, 'Candidato aprovado na entrevista', datetime(2026, 6, 6, 14, 30), 'Ger. — Paulo Saraiva', True),
        (2, 'Link de coleta enviado ao candidato', datetime(2026, 6, 7, 8, 0), 'Sistema automático', True),
        (2, 'RG, CPF, certidão e endereço recebidos', datetime(2026, 6, 7, 15, 22), 'Fernanda Lima Souza', True),
        (2, 'Aguardando: Título de Eleitor, PIS, CTPS, ASO, NR-35', datetime(2026, 6, 10, 0, 0), 'Pendente', False),
    ]:
        AdmissaoHistorico.objects.create(
            colaborador=c2,
            etapa=ev[0],
            descricao=ev[1],
            data_hora=aware(ev[2]),
            autor=ev[3],
            concluido=ev[4],
        )

    c3 = Colaborador.objects.create(
        nome='José Roberto Alves',
        cpf='111.222.333-44',
        rg='55.667.788-9',
        data_nascimento=date(1980, 11, 8),
        endereco='Rua Voluntários da Pátria, 78 – São Paulo/SP',
        dados_bancarios='Itaú – Ag. 5678 / CC 90123-4',
        pis='345.67890.12-3',
        escolaridade='Ensino Fundamental',
        tamanho_camisa='GG',
        tamanho_bota='43',
        cargo='Pedreiro',
        empresa='Construtora Horizonte Ltda.',
        status='ativo',
        data_admissao=date(2019, 5, 3),
        etapa_admissao=5,
    )
    c3.obras.set([obras['Obra ABC']])
    add_docs(c3, [
        ('RG', 'received', None),
        ('CPF', 'received', None),
        ('Título de Eleitor', 'received', None),
        ('Certidão de Nascimento/Casamento', 'received', None),
        ('Comprovante Bancário', 'received', None),
        ('Comprovante de Endereço', 'received', None),
        ('Certificado de Escolaridade', 'received', None),
        ('PIS', 'received', None),
        ('CTPS (Carteira de Trabalho)', 'received', None),
        ('Documentos dos Filhos', 'received', None),
        ('ASO – Atestado de Saúde Ocupacional', 'received', date(2026, 9, 10)),
        ('NR-35 – Trabalho em Altura', 'received', date(2026, 12, 15)),
    ])

    c4 = Colaborador.objects.create(
        nome='Marcos Antônio Ferreira',
        cpf='555.666.777-88',
        rg='12.345.678-9',
        data_nascimento=date(1975, 4, 30),
        endereco='Rua Guaicurus, 450 – São Paulo/SP',
        dados_bancarios='Banco do Brasil – Ag. 9012 / CC 34567-8',
        pis='456.78901.23-4',
        escolaridade='Técnico em Edificações',
        tamanho_camisa='GG',
        tamanho_bota='44',
        cargo='Mestre de Obras',
        empresa='Construtora Horizonte Ltda.',
        status='ativo',
        data_admissao=date(2015, 8, 17),
        etapa_admissao=5,
    )
    c4.obras.set([obras['Obra Tatuapé'], obras['Obra ABC']])
    add_docs(c4, [
        ('RG', 'received', None),
        ('CPF', 'received', None),
        ('Título de Eleitor', 'received', None),
        ('Certidão de Nascimento/Casamento', 'received', None),
        ('Comprovante Bancário', 'received', None),
        ('Comprovante de Endereço', 'received', None),
        ('Certificado de Escolaridade', 'received', None),
        ('PIS', 'received', None),
        ('CTPS (Carteira de Trabalho)', 'received', None),
        ('Documentos dos Filhos', 'missing', None),
        ('ASO – Atestado de Saúde Ocupacional', 'pending', date(2026, 7, 3)),
        ('NR-35 – Trabalho em Altura', 'missing', date(2026, 6, 20)),
    ])

    c5 = Colaborador.objects.create(
        nome='Ana Paula Rodrigues',
        cpf='999.888.777-66',
        rg='98.765.432-1',
        data_nascimento=date(1991, 12, 14),
        endereco='Av. Interlagos, 333 – São Paulo/SP',
        dados_bancarios='Nubank – Ag. 0001 / CC 11111-1',
        pis='567.89012.34-5',
        escolaridade='Superior em Engenharia Civil',
        tamanho_camisa='P',
        tamanho_bota='36',
        cargo='Engenheira de Obras',
        empresa='Construtora Horizonte Ltda.',
        status='desligado',
        data_admissao=date(2021, 3, 2),
        etapa_admissao=5,
    )
    c5.obras.set([obras['Obra Paulista']])
    add_docs(c5, [
        ('RG', 'received', None),
        ('CPF', 'received', None),
        ('Título de Eleitor', 'received', None),
        ('Certidão de Nascimento/Casamento', 'received', None),
        ('Comprovante Bancário', 'received', None),
        ('Comprovante de Endereço', 'received', None),
        ('Certificado de Escolaridade', 'received', None),
        ('PIS', 'received', None),
        ('CTPS (Carteira de Trabalho)', 'received', None),
        ('Documentos dos Filhos', 'received', None),
        ('ASO – Atestado de Saúde Ocupacional', 'received', date(2025, 11, 30)),
        ('NR-35 – Trabalho em Altura', 'received', date(2026, 5, 15)),
    ])

    c6 = Colaborador.objects.create(
        nome='Ricardo Souza Neto',
        cpf='444.333.222-11',
        rg='22.333.444-5',
        cargo='Servente',
        empresa='Construtora Horizonte Ltda.',
        status='em_admissao',
        data_admissao=date(2026, 6, 2),
        etapa_admissao=3,
    )
    c6.obras.set([obras['Obra Tatuapé']])
    add_docs(c6, [
        ('RG', 'received', None),
        ('CPF', 'received', None),
        ('Título de Eleitor', 'received', None),
        ('Certidão de Nascimento/Casamento', 'received', None),
        ('Comprovante Bancário', 'received', None),
        ('Comprovante de Endereço', 'received', None),
        ('Certificado de Escolaridade', 'received', None),
        ('PIS', 'received', None),
        ('CTPS (Carteira de Trabalho)', 'received', None),
        ('ASO – Atestado de Saúde Ocupacional', 'received', date(2026, 12, 1)),
        ('NR-35 – Trabalho em Altura', 'received', date(2027, 6, 1)),
    ])
    for ev in [
        (1, 'Requisição criada', datetime(2026, 6, 2, 10, 0), 'RH — Carla Moreira', True),
        (1, 'Candidato aprovado', datetime(2026, 6, 3, 16, 0), 'Ger. — Paulo Saraiva', True),
        (2, 'Todos os documentos coletados (11/11)', datetime(2026, 6, 6, 11, 45), 'Ricardo Souza Neto', True),
        (3, 'Em análise pelo RH', datetime(2026, 6, 9, 9, 0), 'RH — Carla Moreira', False),
    ]:
        AdmissaoHistorico.objects.create(
            colaborador=c6,
            etapa=ev[0],
            descricao=ev[1],
            data_hora=aware(ev[2]),
            autor=ev[3],
            concluido=ev[4],
        )


def unseed_rh_demo(apps, schema_editor):
    Colaborador = apps.get_model('recursos_humanos', 'Colaborador')
    Colaborador.objects.all().delete()
