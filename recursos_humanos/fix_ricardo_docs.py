"""Corrige documentos do Ricardo (etapa 3) em bases já seedadas."""
from datetime import date


def _docs_ricardo_specs():
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
        ('ASO – Atestado de Saúde Ocupacional', 'received', date(2026, 12, 1)),
        ('NR-35 – Trabalho em Altura', 'received', date(2027, 6, 1)),
    ]


def fix_ricardo_docs(apps, schema_editor):
    Colaborador = apps.get_model('recursos_humanos', 'Colaborador')
    TipoDocumento = apps.get_model('recursos_humanos', 'TipoDocumento')
    DocumentoColaborador = apps.get_model('recursos_humanos', 'DocumentoColaborador')

    ricardo = Colaborador.objects.filter(cpf='444.333.222-11').first()
    if not ricardo or ricardo.documentos.exists():
        return

    tipos = {t.nome: t for t in TipoDocumento.objects.all()}
    for nome, status, venc in _docs_ricardo_specs():
        tipo = tipos.get(nome)
        if not tipo:
            continue
        DocumentoColaborador.objects.create(
            colaborador=ricardo,
            tipo=tipo,
            status=status,
            vencimento=venc,
        )


def unfix_ricardo_docs(apps, schema_editor):
    Colaborador = apps.get_model('recursos_humanos', 'Colaborador')
    DocumentoColaborador = apps.get_model('recursos_humanos', 'DocumentoColaborador')

    ricardo = Colaborador.objects.filter(cpf='444.333.222-11').first()
    if ricardo:
        DocumentoColaborador.objects.filter(colaborador=ricardo).delete()
