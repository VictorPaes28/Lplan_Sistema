from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('recursos_humanos', '0035_contratoadmissao_data_admissao_oficial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DecisaoPrazoContrato',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('acao', models.CharField(
                    choices=[
                        ('efetivar', 'Efetivar'),
                        ('prorrogar', 'Prorrogar'),
                        ('converter', 'Converter'),
                        ('renovar', 'Renovar'),
                        ('desligar', 'Desligar'),
                        ('encerrar', 'Encerrar'),
                    ],
                    max_length=20,
                )),
                ('motivo', models.TextField(blank=True)),
                ('observacoes', models.TextField(blank=True)),
                ('registrado_em', models.DateTimeField(auto_now_add=True)),
                ('colaborador', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='decisoes_prazo',
                    to='recursos_humanos.colaborador',
                )),
                ('prazo_contrato', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='decisoes',
                    to='recursos_humanos.prazocontrato',
                )),
                ('usuario', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='decisoes_prazo_rh',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Decisão de prazo contratual',
                'verbose_name_plural': 'Decisões de prazo contratual',
                'ordering': ['-registrado_em'],
            },
        ),
    ]
