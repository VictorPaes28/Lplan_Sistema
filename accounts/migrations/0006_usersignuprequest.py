from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_userloginlog_accounts_us_created_b5cd99_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserSignupRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=255, verbose_name='Nome completo')),
                ('email', models.EmailField(db_index=True, max_length=254, verbose_name='E-mail')),
                ('username_suggestion', models.CharField(blank=True, max_length=150, verbose_name='Sugestão de usuário')),
                ('requested_groups', models.JSONField(blank=True, default=list, verbose_name='Grupos solicitados')),
                ('requested_project_ids', models.JSONField(blank=True, default=list, verbose_name='Projetos solicitados')),
                ('notes', models.TextField(blank=True, verbose_name='Observações')),
                ('status', models.CharField(choices=[('pendente', 'Pendente'), ('aprovado', 'Aprovado'), ('rejeitado', 'Rejeitado')], db_index=True, default='pendente', max_length=20, verbose_name='Status')),
                ('origem', models.CharField(choices=[('auto', 'Auto cadastro'), ('interno', 'Cadastro interno')], db_index=True, default='auto', max_length=20, verbose_name='Origem da solicitação')),
                ('approved_at', models.DateTimeField(blank=True, null=True, verbose_name='Aprovado em')),
                ('rejected_at', models.DateTimeField(blank=True, null=True, verbose_name='Rejeitado em')),
                ('rejection_reason', models.TextField(blank=True, verbose_name='Motivo da rejeição')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='signup_requests_approved', to=settings.AUTH_USER_MODEL, verbose_name='Aprovado por')),
                ('approved_user', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='signup_request_origin', to=settings.AUTH_USER_MODEL, verbose_name='Usuário criado')),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='signup_requests_created', to=settings.AUTH_USER_MODEL, verbose_name='Solicitado por')),
            ],
            options={
                'verbose_name': 'Solicitação de cadastro',
                'verbose_name_plural': 'Solicitações de cadastro',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['status', '-created_at'], name='accounts_us_status_f6f013_idx'), models.Index(fields=['email', 'status'], name='accounts_us_email_8b040c_idx')],
            },
        ),
    ]
