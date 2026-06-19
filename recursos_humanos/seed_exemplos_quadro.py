"""Exemplos adicionais de colaboradores para demonstrar etapas e alertas de validade."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from django.utils import timezone


def _aware(dt):
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


def _tipos_por_nome(apps):
    TipoDocumento = apps.get_model('recursos_humanos', 'TipoDocumento')
    return {t.nome: t for t in TipoDocumento.objects.all()}


def _obra(apps, nome):
    ObraLocal = apps.get_model('recursos_humanos', 'ObraLocal')
    obra, _ = ObraLocal.objects.get_or_create(nome=nome)
    return obra


def _add_docs(DocumentoColaborador, colab, tipos, specs):
    for tipo_nome, status, venc in specs:
        DocumentoColaborador.objects.create(
            colaborador=colab,
            tipo=tipos[tipo_nome],
            status=status,
            vencimento=venc,
        )


def _docs_quadro_completo(*, aso_venc=None, nr35_venc=None):
    """Dossiê completo para quem já passou pela ativação (etapa 5)."""
    return [
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
        ('ASO – Atestado de Saúde Ocupacional', 'received', aso_venc),
        ('NR-35 – Trabalho em Altura', 'received', nr35_venc),
    ]


def seed_exemplos_quadro(apps, schema_editor):
    Colaborador = apps.get_model('recursos_humanos', 'Colaborador')
    DocumentoColaborador = apps.get_model('recursos_humanos', 'DocumentoColaborador')
    AdmissaoHistorico = apps.get_model('recursos_humanos', 'AdmissaoHistorico')
    PrazoContrato = apps.get_model('recursos_humanos', 'PrazoContrato')

    tipos = _tipos_por_nome(apps)
    if not tipos:
        return

    hoje = date(2026, 6, 17)
    obra_lapa = _obra(apps, 'Obra Lapa')
    obra_abc = _obra(apps, 'Obra ABC')
    obra_paulista = _obra(apps, 'Obra Paulista')
    obra_tatuape = _obra(apps, 'Obra Tatuapé')

    exemplos = [
        {
            'cpf': '333.222.111-00',
            'nome': 'Paulo Henrique Costa',
            'cargo': 'Eletricista',
            'status': 'ativo',
            'data_admissao': date(2023, 4, 10),
            'obras': [obra_abc],
            'docs': _docs_quadro_completo(
                aso_venc=hoje + timedelta(days=60),
                nr35_venc=hoje + timedelta(days=90),
            ),
        },
        {
            'cpf': '222.111.000-99',
            'nome': 'Roberto Silva',
            'cargo': 'Carpinteiro',
            'status': 'ativo',
            'data_admissao': date(2021, 9, 1),
            'obras': [obra_paulista],
            'docs': _docs_quadro_completo(
                aso_venc=hoje + timedelta(days=22),
                nr35_venc=hoje + timedelta(days=120),
            ),
        },
        {
            'cpf': '111.000.999-88',
            'nome': 'Patrícia Gomes',
            'cargo': 'Assistente de Compras',
            'status': 'em_admissao',
            'data_admissao': hoje - timedelta(days=2),
            'etapa_admissao': 2,
            'requisicao_aprovada_gestor': True,
            'obras': [obra_lapa],
            'historico': [
                (1, 'Requisição criada', datetime(2026, 6, 15, 10, 30), 'RH — Carla Moreira', True),
                (1, 'Coleta de documentos iniciada automaticamente', datetime(2026, 6, 15, 10, 30), 'RH — Carla Moreira', True),
            ],
        },
        {
            'cpf': '000.999.888-77',
            'nome': 'Diego Martins',
            'cargo': 'Ajudante de Produção',
            'status': 'em_admissao',
            'data_admissao': date(2026, 5, 28),
            'etapa_admissao': 4,
            'requisicao_aprovada_gestor': True,
            'obras': [obra_tatuape],
            'docs': _docs_quadro_completo(
                aso_venc=hoje + timedelta(days=180),
                nr35_venc=hoje + timedelta(days=200),
            ),
            'historico': [
                (1, 'Requisição aprovada', datetime(2026, 5, 29, 11, 0), 'Ger. — Paulo Saraiva', True),
                (2, 'Documentos conferidos (11/11)', datetime(2026, 6, 3, 16, 20), 'RH — Carla Moreira', True),
                (3, 'Validação final concluída', datetime(2026, 6, 8, 9, 45), 'RH — Carla Moreira', True),
                (4, 'Contrato enviado para assinatura', datetime(2026, 6, 12, 14, 0), 'Sistema ZapSign', False),
            ],
        },
        {
            'cpf': '999.888.777-55',
            'nome': 'Camila Rocha',
            'cargo': 'Estagiária de Engenharia',
            'status': 'ativo',
            'data_admissao': hoje - timedelta(days=75),
            'obras': [obra_paulista, obra_lapa],
            'docs': _docs_quadro_completo(
                aso_venc=hoje + timedelta(days=40),
                nr35_venc=hoje + timedelta(days=200),
            ),
            'prazo': {
                'tipo': 'estagio',
                'data_inicio': hoje - timedelta(days=75),
                'data_fim': hoje + timedelta(days=12),
            },
        },
        {
            'cpf': '888.777.666-44',
            'nome': 'Luís Oliveira',
            'cargo': 'Armador',
            'status': 'ativo',
            'data_admissao': date(2024, 2, 19),
            'obras': [obra_abc],
            'docs': _docs_quadro_completo(
                aso_venc=hoje + timedelta(days=75),
                nr35_venc=hoje + timedelta(days=95),
            ),
        },
        {
            'cpf': '777.666.555-33',
            'nome': 'Sandra Mendes',
            'cargo': 'Técnica de Segurança',
            'status': 'desligado',
            'data_admissao': date(2020, 6, 1),
            'obras': [obra_tatuape],
            'docs': _docs_quadro_completo(
                aso_venc=hoje + timedelta(days=90),
                nr35_venc=hoje + timedelta(days=150),
            ),
        },
    ]

    for spec in exemplos:
        if Colaborador.objects.filter(cpf=spec['cpf']).exists():
            continue

        colab = Colaborador.objects.create(
            nome=spec['nome'],
            cpf=spec['cpf'],
            cargo=spec['cargo'],
            empresa='Construtora Horizonte Ltda.',
            status=spec['status'],
            data_admissao=spec.get('data_admissao'),
            etapa_admissao=spec.get('etapa_admissao', 5 if spec['status'] == 'ativo' else 1),
            requisicao_aprovada_gestor=spec.get('requisicao_aprovada_gestor', True),
        )
        colab.obras.set(spec['obras'])
        _add_docs(DocumentoColaborador, colab, tipos, spec['docs'])

        for ev in spec.get('historico', []):
            AdmissaoHistorico.objects.create(
                colaborador=colab,
                etapa=ev[0],
                descricao=ev[1],
                data_hora=_aware(ev[2]),
                autor=ev[3],
                concluido=ev[4],
            )

        prazo_spec = spec.get('prazo')
        if prazo_spec:
            PrazoContrato.objects.create(
                colaborador=colab,
                tipo=prazo_spec['tipo'],
                data_inicio=prazo_spec['data_inicio'],
                data_fim=prazo_spec['data_fim'],
                status='ativo',
            )


def unseed_exemplos_quadro(apps, schema_editor):
    Colaborador = apps.get_model('recursos_humanos', 'Colaborador')
    cpfs = [
        '333.222.111-00',
        '222.111.000-99',
        '111.000.999-88',
        '000.999.888-77',
        '999.888.777-55',
        '888.777.666-44',
        '777.666.555-33',
    ]
    Colaborador.objects.filter(cpf__in=cpfs).delete()
