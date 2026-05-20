from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('trackhub', '0011_pendencia_recorrente_prazo_original'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TipoCustom',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, unique=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('criado_por', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='tipos_custom_criados',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Tipo customizado',
                'verbose_name_plural': 'Tipos customizados',
                'ordering': ['nome'],
            },
        ),
        migrations.AlterField(
            model_name='pendencia',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('financeiro', 'Financeiro'),
                    ('operacional', 'Operacional'),
                    ('documento', 'Documento'),
                    ('tarefa', 'Tarefa'),
                    ('outro', 'Outro'),
                ],
                default='outro',
                max_length=100,
            ),
        ),
    ]
