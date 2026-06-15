from django.db import migrations, models


def limpar_data_fim_convertidos(apps, schema_editor):
    PrazoContrato = apps.get_model('recursos_humanos', 'PrazoContrato')
    PrazoContrato.objects.filter(status='convertido').update(data_fim=None)


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0020_simplify_configuracaoalertasrh'),
    ]

    operations = [
        migrations.AlterField(
            model_name='prazocontrato',
            name='data_fim',
            field=models.DateField(blank=True, null=True, verbose_name='Data de fim'),
        ),
        migrations.RunPython(limpar_data_fim_convertidos, migrations.RunPython.noop),
    ]
