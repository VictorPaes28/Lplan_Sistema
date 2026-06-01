import workflow_aprovacao.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('workflow_aprovacao', '0009_manual_variable_participants_and_external_signup'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApprovalProcessAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to=workflow_aprovacao.models.approval_process_attachment_upload_path)),
                ('original_name', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'process',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='attachments',
                        to='workflow_aprovacao.approvalprocess',
                    ),
                ),
                (
                    'uploaded_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='workflow_process_attachments_uploaded',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Anexo de processo (Central)',
                'verbose_name_plural': 'Anexos de processo (Central)',
                'ordering': ['created_at', 'pk'],
            },
        ),
    ]
