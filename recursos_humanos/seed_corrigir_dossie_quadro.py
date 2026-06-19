"""Corrige dossiê de colaboradores já ativados — admissão exige docs antes da etapa 5."""
from __future__ import annotations

from datetime import date, timedelta


def _vencimentos_demo(cpf: str, hoje: date) -> dict[str, date]:
    """Datas de validade para manter variedade de alertas sem docs faltando."""
    return {
        '423.891.047-55': {  # Carlos
            'ASO – Atestado de Saúde Ocupacional': hoje + timedelta(days=8),
            'NR-35 – Trabalho em Altura': hoje + timedelta(days=42),
            'Comprovante de Endereço': hoje + timedelta(days=60),
        },
        '555.666.777-88': {  # Marcos
            'ASO – Atestado de Saúde Ocupacional': hoje + timedelta(days=10),
            'NR-35 – Trabalho em Altura': hoje + timedelta(days=3),
            'Comprovante de Endereço': hoje + timedelta(days=45),
        },
        '333.222.111-00': {  # Paulo
            'ASO – Atestado de Saúde Ocupacional': hoje + timedelta(days=60),
            'NR-35 – Trabalho em Altura': hoje + timedelta(days=90),
        },
        '222.111.000-99': {  # Roberto
            'ASO – Atestado de Saúde Ocupacional': hoje + timedelta(days=22),
            'NR-35 – Trabalho em Altura': hoje + timedelta(days=120),
        },
        '999.888.777-55': {  # Camila
            'ASO – Atestado de Saúde Ocupacional': hoje + timedelta(days=40),
        },
        '888.777.666-44': {  # Luís
            'ASO – Atestado de Saúde Ocupacional': hoje + timedelta(days=75),
            'NR-35 – Trabalho em Altura': hoje + timedelta(days=95),
        },
        '111.222.333-44': {  # José
            'ASO – Atestado de Saúde Ocupacional': hoje + timedelta(days=85),
            'NR-35 – Trabalho em Altura': hoje + timedelta(days=180),
        },
        '999.888.777-66': {  # Ana Paula
            'ASO – Atestado de Saúde Ocupacional': hoje + timedelta(days=100),
            'NR-35 – Trabalho em Altura': hoje + timedelta(days=140),
        },
    }.get(cpf, {})


def corrigir_dossie_quadro(apps, schema_editor):
    Colaborador = apps.get_model('recursos_humanos', 'Colaborador')
    DocumentoColaborador = apps.get_model('recursos_humanos', 'DocumentoColaborador')

    hoje = date(2026, 6, 17)
    status_quadro = ('ativo', 'desligado')

    for colab in Colaborador.objects.filter(status__in=status_quadro, etapa_admissao__gte=5):
        vencimentos = _vencimentos_demo(colab.cpf, hoje)
        padrao_validade = hoje + timedelta(days=120)
        for doc in DocumentoColaborador.objects.filter(colaborador=colab).select_related('tipo'):
            alterado = False
            if doc.status in ('missing', 'pending'):
                doc.status = 'received'
                alterado = True
            if doc.tipo.tem_validade:
                novo_venc = vencimentos.get(doc.tipo.nome, padrao_validade)
                if doc.vencimento != novo_venc:
                    doc.vencimento = novo_venc
                    alterado = True
            elif doc.vencimento is not None:
                doc.vencimento = None
                alterado = True
            if alterado:
                doc.save(update_fields=['status', 'vencimento'])


def noop_reverse(apps, schema_editor):
    pass
