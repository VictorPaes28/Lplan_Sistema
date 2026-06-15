from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0019_documentocolaborador_reenvio_solicitado'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name='configuracaoalertasrh',
            old_name='dias_documento_vencendo',
            new_name='dias_antecedencia_documentos',
        ),
        migrations.RenameField(
            model_name='configuracaoalertasrh',
            old_name='dias_renotificar_vencido',
            new_name='dias_renotificar_vencidos',
        ),
        migrations.RenameField(
            model_name='configuracaoalertasrh',
            old_name='canal_email_rh',
            new_name='notificar_email',
        ),
        migrations.RenameField(
            model_name='configuracaoalertasrh',
            old_name='canal_notificacao_sistema',
            new_name='notificar_sistema',
        ),
        migrations.AlterField(
            model_name='configuracaoalertasrh',
            name='dias_antecedencia_documentos',
            field=models.PositiveSmallIntegerField(
                default=30,
                verbose_name='Antecedência documentos e prazos de contrato (dias)',
            ),
        ),
        migrations.AlterField(
            model_name='configuracaoalertasrh',
            name='dias_renotificar_vencidos',
            field=models.PositiveSmallIntegerField(
                default=7,
                verbose_name='Documentos vencidos — renotificar (dias)',
            ),
        ),
        migrations.AlterField(
            model_name='configuracaoalertasrh',
            name='notificar_email',
            field=models.BooleanField(default=True, verbose_name='E-mail para responsáveis'),
        ),
        migrations.AlterField(
            model_name='configuracaoalertasrh',
            name='notificar_sistema',
            field=models.BooleanField(default=True, verbose_name='Notificação no sistema'),
        ),
        migrations.RemoveField(
            model_name='configuracaoalertasrh',
            name='dias_treinamento_vencer',
        ),
        migrations.RemoveField(
            model_name='configuracaoalertasrh',
            name='dias_renovacao_aso',
        ),
        migrations.RemoveField(
            model_name='configuracaoalertasrh',
            name='canal_whatsapp_gestor',
        ),
        migrations.RemoveField(
            model_name='configuracaoalertasrh',
            name='canal_relatorio_pdf_semanal',
        ),
    ]
