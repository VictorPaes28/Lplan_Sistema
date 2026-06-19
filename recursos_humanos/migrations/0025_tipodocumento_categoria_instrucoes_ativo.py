"""Campos de catálogo: categoria, instruções portal e ativo."""
from django.db import migrations, models


def _inferir_categoria(nome: str) -> str:
    n = nome.lower()
    if 'aso' in n or 'saúde' in n or 'saude' in n:
        return 'saude'
    if 'nr-' in n or n.startswith('nr '):
        return 'treinamentos'
    if any(k in n for k in ('comprovante', 'fgts', 'banc')):
        return 'comprovantes'
    if any(
        k in n
        for k in (
            'rg',
            'cpf',
            'título',
            'titulo',
            'certidão',
            'certidao',
            'pis',
            'ctps',
            'filhos',
            'escolaridade',
        )
    ):
        return 'pessoais'
    return 'outros'


def backfill_categoria(apps, schema_editor):
    TipoDocumento = apps.get_model('recursos_humanos', 'TipoDocumento')
    for tipo in TipoDocumento.objects.all():
        cat = _inferir_categoria(tipo.nome)
        if tipo.categoria != cat:
            tipo.categoria = cat
            tipo.save(update_fields=['categoria'])


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0024_corrigir_dossie_quadro'),
    ]

    operations = [
        migrations.AddField(
            model_name='tipodocumento',
            name='categoria',
            field=models.CharField(
                blank=True,
                choices=[
                    ('pessoais', 'Documentos pessoais'),
                    ('comprovantes', 'Comprovantes'),
                    ('saude', 'Saúde e segurança'),
                    ('treinamentos', 'Treinamentos e NRs'),
                    ('outros', 'Outros'),
                ],
                default='outros',
                max_length=20,
                verbose_name='Categoria',
            ),
        ),
        migrations.AddField(
            model_name='tipodocumento',
            name='instrucoes_portal',
            field=models.CharField(
                blank=True,
                help_text='Texto curto exibido no portal na hora do envio.',
                max_length=200,
                verbose_name='Instruções para o candidato',
            ),
        ),
        migrations.AddField(
            model_name='tipodocumento',
            name='ativo',
            field=models.BooleanField(
                default=True,
                help_text='Inativos não entram em novas admissões, mas permanecem no histórico.',
                verbose_name='Ativo',
            ),
        ),
        migrations.RunPython(backfill_categoria, migrations.RunPython.noop),
    ]
