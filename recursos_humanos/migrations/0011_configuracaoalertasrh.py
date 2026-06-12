# Generated manually

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('recursos_humanos', '0010_colaborador_requisicao_reprovada_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracaoAlertasRH',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dias_documento_vencendo', models.PositiveSmallIntegerField(default=30, verbose_name='Documentos com vencimento próximo (dias)')),
                ('dias_treinamento_vencer', models.PositiveSmallIntegerField(default=60, verbose_name='Treinamentos a vencer (dias)')),
                ('dias_renovacao_aso', models.PositiveSmallIntegerField(default=45, verbose_name='Renovação de ASO (dias)')),
                ('dias_renotificar_vencido', models.PositiveSmallIntegerField(default=7, verbose_name='Documentos vencidos — renotificar (dias)')),
                ('canal_email_rh', models.BooleanField(default=True, verbose_name='E-mail para o RH')),
                ('canal_notificacao_sistema', models.BooleanField(default=True, verbose_name='Notificação no sistema')),
                ('canal_whatsapp_gestor', models.BooleanField(default=False, verbose_name='WhatsApp para o gestor')),
                ('canal_relatorio_pdf_semanal', models.BooleanField(default=True, verbose_name='Relatório semanal PDF')),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('responsaveis', models.ManyToManyField(blank=True, related_name='config_alertas_rh', to=settings.AUTH_USER_MODEL, verbose_name='Responsáveis por receber alertas')),
            ],
            options={
                'verbose_name': 'Configuração de alertas RH',
                'verbose_name_plural': 'Configuração de alertas RH',
            },
        ),
    ]
