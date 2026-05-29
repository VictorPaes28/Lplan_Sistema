from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('workflow_aprovacao', '0008_seed_gestcontroll_process_categories'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='approvalstepparticipant',
            name='is_variable',
            field=models.BooleanField(
                default=False,
                help_text='Se marcado, o participante é preenchido por processo na criação manual.',
            ),
        ),
        migrations.AddField(
            model_name='approvalstepparticipant',
            name='required_on_create',
            field=models.BooleanField(
                default=False,
                help_text='Exige preenchimento na criação manual do processo.',
            ),
        ),
        migrations.AddField(
            model_name='approvalstepparticipant',
            name='variable_key',
            field=models.SlugField(
                blank=True,
                help_text='Chave estável do campo variável (ex.: terceirizado_responsavel).',
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name='approvalstepparticipant',
            name='variable_label',
            field=models.CharField(
                blank=True,
                help_text='Rótulo de exibição para o campo variável.',
                max_length=160,
            ),
        ),
        migrations.AddField(
            model_name='approvalstepparticipant',
            name='variable_subject_kind',
            field=models.CharField(
                blank=True,
                choices=[('user', 'Usuário'), ('django_group', 'Grupo Django')],
                help_text='Tipo de sujeito permitido quando a linha for variável.',
                max_length=20,
            ),
        ),
        migrations.RemoveConstraint(
            model_name='approvalstepparticipant',
            name='workflow_participant_user_xor_group',
        ),
        migrations.AddConstraint(
            model_name='approvalstepparticipant',
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(('django_group__isnull', True), ('is_variable', True), ('user__isnull', True)),
                    models.Q(('django_group__isnull', True), ('subject_kind', 'user'), ('user__isnull', False)),
                    models.Q(('django_group__isnull', False), ('subject_kind', 'django_group'), ('user__isnull', True)),
                    _connector='OR',
                ),
                name='workflow_participant_user_xor_group',
            ),
        ),
        migrations.CreateModel(
            name='ApprovalProcessParticipant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('owner', 'Responsável pela etapa'), ('approver', 'Aprovador'), ('viewer', 'Somente visualização')], default='approver', max_length=20)),
                ('subject_kind', models.CharField(choices=[('user', 'Usuário'), ('django_group', 'Grupo Django')], max_length=20)),
                ('is_runtime_variable', models.BooleanField(default=False)),
                ('label_override', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('django_group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='workflow_process_participations', to='auth.group')),
                ('process', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='process_participants', to='workflow_aprovacao.approvalprocess')),
                ('source_step_participant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_process_participants', to='workflow_aprovacao.approvalstepparticipant')),
                ('step', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='process_participants', to='workflow_aprovacao.approvalstep')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='workflow_process_participations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Participante efetivo do processo',
                'verbose_name_plural': 'Participantes efetivos dos processos',
                'ordering': ['step__sequence', 'pk'],
            },
        ),
        migrations.AddConstraint(
            model_name='approvalprocessparticipant',
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(('django_group__isnull', True), ('subject_kind', 'user'), ('user__isnull', False)),
                    models.Q(('django_group__isnull', False), ('subject_kind', 'django_group'), ('user__isnull', True)),
                    _connector='OR',
                ),
                name='workflow_process_participant_user_xor_group',
            ),
        ),
        migrations.CreateModel(
            name='ExternalParticipantSignupRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('variable_key', models.SlugField(blank=True, max_length=64)),
                ('full_name', models.CharField(max_length=255)),
                ('company_name', models.CharField(blank=True, max_length=180)),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('phone_whatsapp', models.CharField(blank=True, db_index=True, max_length=40)),
                ('cnpj', models.CharField(blank=True, db_index=True, max_length=32)),
                ('note', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('pendente', 'Pendente'), ('aprovado', 'Aprovado'), ('rejeitado', 'Rejeitado'), ('cancelado', 'Cancelado'), ('inativo', 'Inativo')], db_index=True, default='pendente', max_length=20)),
                ('review_reason', models.TextField(blank=True)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('rejected_at', models.DateTimeField(blank=True, null=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('linked_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='workflow_external_requests_linked', to=settings.AUTH_USER_MODEL)),
                ('process', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='external_signup_requests', to='workflow_aprovacao.approvalprocess')),
                ('requester', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='workflow_external_requests_created', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='workflow_external_requests_reviewed', to=settings.AUTH_USER_MODEL)),
                ('step', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='external_signup_requests', to='workflow_aprovacao.approvalstep')),
            ],
            options={
                'verbose_name': 'Solicitação de cadastro externo (workflow)',
                'verbose_name_plural': 'Solicitações de cadastro externo (workflow)',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='externalparticipantsignuprequest',
            index=models.Index(fields=['status', '-created_at'], name='workflow_ap_status_28bab8_idx'),
        ),
        migrations.AddIndex(
            model_name='externalparticipantsignuprequest',
            index=models.Index(fields=['email', 'status'], name='workflow_ap_email_068e62_idx'),
        ),
        migrations.AddIndex(
            model_name='externalparticipantsignuprequest',
            index=models.Index(fields=['phone_whatsapp', 'status'], name='workflow_ap_phone_w_070ca5_idx'),
        ),
    ]
