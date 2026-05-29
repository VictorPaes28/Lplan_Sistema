"""
Modelos da Central de Aprovações.

Obra canónica: core.Project (alinhado a core.sync_obras).
"""
import json

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class ProcessCategory(models.Model):
    """Categoria de processo (contrato, medição, …). Extensível por cadastro."""

    code = models.SlugField(
        max_length=64,
        unique=True,
        help_text='Identificador estável (ex.: contrato, medicao).',
    )
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Categoria de processo'
        verbose_name_plural = 'Categorias de processo'

    def __str__(self):
        return self.name


class ApprovalFlowDefinition(models.Model):
    """
    Definição de fluxo para o par (obra + categoria).
    Uma definição ativa por projeto e categoria.
    """

    project = models.ForeignKey(
        'core.Project',
        on_delete=models.CASCADE,
        related_name='approval_flow_definitions',
    )
    category = models.ForeignKey(
        ProcessCategory,
        on_delete=models.PROTECT,
        related_name='approval_flow_definitions',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'category'],
                name='workflow_unique_flow_per_project_category',
            ),
        ]
        verbose_name = 'Definição de fluxo'
        verbose_name_plural = 'Definições de fluxo'

    def __str__(self):
        return f'{self.project.code} · {self.category.code}'


class ApprovalPolicy(models.TextChoices):
    """Política de decisão na alçada (extensível)."""

    SINGLE_ANY = 'single_any', 'Um aprovador basta (qualquer participante aprovador)'


class ApprovalStep(models.Model):
    """Alçada ordenada dentro de um fluxo."""

    flow = models.ForeignKey(
        ApprovalFlowDefinition,
        on_delete=models.CASCADE,
        related_name='steps',
    )
    sequence = models.PositiveIntegerField(
        help_text='Ordem crescente (1, 2, 3, …).',
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    approval_policy = models.CharField(
        max_length=32,
        choices=ApprovalPolicy.choices,
        default=ApprovalPolicy.SINGLE_ANY,
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['flow', 'sequence']
        constraints = [
            models.UniqueConstraint(
                fields=['flow', 'sequence'],
                name='workflow_unique_step_sequence_per_flow',
            ),
        ]
        verbose_name = 'Alçada'
        verbose_name_plural = 'Alçadas'

    def __str__(self):
        return f'{self.flow} — {self.sequence}. {self.name}'


class ParticipantRole(models.TextChoices):
    OWNER = 'owner', 'Responsável pela etapa'
    APPROVER = 'approver', 'Aprovador'
    VIEWER = 'viewer', 'Somente visualização'


class SubjectKind(models.TextChoices):
    USER = 'user', 'Usuário'
    DJANGO_GROUP = 'django_group', 'Grupo Django'


class ExternalSignupStatus(models.TextChoices):
    PENDING = 'pendente', 'Pendente'
    APPROVED = 'aprovado', 'Aprovado'
    REJECTED = 'rejeitado', 'Rejeitado'
    CANCELLED = 'cancelado', 'Cancelado'
    INACTIVE = 'inativo', 'Inativo'


class ApprovalStepParticipant(models.Model):
    """Quem participa da alçada (usuário ou grupo), com papel."""

    step = models.ForeignKey(
        ApprovalStep,
        on_delete=models.CASCADE,
        related_name='participants',
    )
    role = models.CharField(
        max_length=20,
        choices=ParticipantRole.choices,
        default=ParticipantRole.APPROVER,
    )
    subject_kind = models.CharField(
        max_length=20,
        choices=SubjectKind.choices,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='workflow_step_participations',
    )
    django_group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='workflow_step_participations',
    )
    is_variable = models.BooleanField(
        default=False,
        help_text='Se marcado, o participante é preenchido por processo na criação manual.',
    )
    variable_key = models.SlugField(
        max_length=64,
        blank=True,
        help_text='Chave estável do campo variável (ex.: terceirizado_responsavel).',
    )
    variable_label = models.CharField(
        max_length=160,
        blank=True,
        help_text='Rótulo de exibição para o campo variável.',
    )
    required_on_create = models.BooleanField(
        default=False,
        help_text='Exige preenchimento na criação manual do processo.',
    )
    variable_subject_kind = models.CharField(
        max_length=20,
        choices=SubjectKind.choices,
        blank=True,
        help_text='Tipo de sujeito permitido quando a linha for variável.',
    )

    class Meta:
        verbose_name = 'Participante da alçada'
        verbose_name_plural = 'Participantes da alçada'
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(is_variable=True, user__isnull=True, django_group__isnull=True)
                    | Q(subject_kind=SubjectKind.USER, user__isnull=False, django_group__isnull=True)
                    | Q(
                        subject_kind=SubjectKind.DJANGO_GROUP,
                        user__isnull=True,
                        django_group__isnull=False,
                    )
                ),
                name='workflow_participant_user_xor_group',
            ),
        ]

    def __str__(self):
        subj = self.user_id or self.django_group_id
        return f'{self.step} — {self.get_role_display()} — {subj}'

    def clean(self):
        super().clean()
        if self.is_variable:
            if self.subject_kind not in (SubjectKind.USER, SubjectKind.DJANGO_GROUP):
                raise ValidationError({'subject_kind': 'Tipo de sujeito inválido para participante variável.'})
            if not self.variable_key:
                raise ValidationError({'variable_key': 'Informe a chave do participante variável.'})
            if self.subject_kind == SubjectKind.USER and self.user_id:
                raise ValidationError({'user': 'Participante variável não deve fixar utilizador no fluxo.'})
            if self.subject_kind == SubjectKind.DJANGO_GROUP and self.django_group_id:
                raise ValidationError({'django_group': 'Participante variável não deve fixar grupo no fluxo.'})
            if self.variable_subject_kind and self.variable_subject_kind != self.subject_kind:
                raise ValidationError(
                    {'variable_subject_kind': 'O tipo variável deve corresponder ao tipo da linha variável.'}
                )
            return
        if self.subject_kind == SubjectKind.USER and not self.user_id:
            raise ValidationError({'user': 'Obrigatório para sujeito do tipo usuário.'})
        if self.subject_kind == SubjectKind.DJANGO_GROUP and not self.django_group_id:
            raise ValidationError({'django_group': 'Obrigatório para sujeito do tipo grupo.'})


class ProcessStatus(models.TextChoices):
    AWAITING_STEP = 'awaiting_step', 'Aguardando aprovação na alçada atual'
    APPROVED = 'approved', 'Fluxo concluído — aprovado'
    REJECTED = 'rejected', 'Reprovado'
    CANCELLED = 'cancelled', 'Cancelado'


class SyncStatus(models.TextChoices):
    NOT_APPLICABLE = 'not_applicable', 'Sem integração externa'
    PENDING = 'pending', 'Aguardando envio ao Sienge'
    IN_PROGRESS = 'in_progress', 'Sincronização em andamento'
    SYNCED = 'synced', 'Sincronizado com Sienge'
    FAILED = 'failed', 'Falha na sincronização'


class ApprovalConfigBacklogStatus(models.TextChoices):
    """Estado na fila administrativa de configuração de fluxo."""

    PENDING = 'pending', 'Aguardando definição de fluxo/alçadas'
    DISMISSED = 'dismissed', 'Dispensado (não criar por agora)'
    RESOLVED = 'resolved', 'Resolvido — processo criado ou reprocessado'


class ApprovalConfigBlockReason(models.TextChoices):
    """Por que o motor não iniciou o processo."""

    NO_FLOW = 'no_flow', 'Sem fluxo ativo ou sem alçada inicial'
    UNSUPPORTED_POLICY = 'unsupported_policy', 'Política de alçada não suportada'


class ApprovalConfigBacklog(models.Model):
    """
    Fila para administradores: chegou integração (ex.: Sienge) com obra+categoria
    identificadas, mas não existia fluxo ativo para iniciar o processo.
    """

    status = models.CharField(
        max_length=20,
        choices=ApprovalConfigBacklogStatus.choices,
        default=ApprovalConfigBacklogStatus.PENDING,
        db_index=True,
    )
    block_reason = models.CharField(
        max_length=40,
        choices=ApprovalConfigBlockReason.choices,
        default=ApprovalConfigBlockReason.NO_FLOW,
    )

    project = models.ForeignKey(
        'core.Project',
        on_delete=models.CASCADE,
        related_name='approval_config_backlog',
    )
    category = models.ForeignKey(
        ProcessCategory,
        on_delete=models.PROTECT,
        related_name='approval_config_backlog',
    )
    external_system = models.CharField(max_length=32, default='sienge', db_index=True)
    external_id = models.CharField(max_length=120, db_index=True)
    external_entity_type = models.CharField(max_length=80, blank=True)
    title = models.CharField(max_length=300, blank=True)
    summary = models.TextField(blank=True)
    source_payload = models.JSONField(default=dict, blank=True)
    last_error_message = models.TextField(blank=True)

    hit_count = models.PositiveIntegerField(default=1)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_approval_backlog',
    )
    linked_process = models.ForeignKey(
        'ApprovalProcess',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='origin_backlog_entry',
    )
    dismiss_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Pendência de configuração de fluxo'
        verbose_name_plural = 'Pendências de configuração de fluxo'
        constraints = [
            models.UniqueConstraint(
                fields=['external_system', 'external_id'],
                name='workflow_unique_backlog_external',
            ),
        ]

    def __str__(self):
        return f'{self.project.code} · {self.category.code} · {self.external_id}'

    def formatted_source_payload(self, max_len: int = 12000) -> str:
        try:
            s = json.dumps(self.source_payload or {}, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            return ''
        if len(s) > max_len:
            return s[: max_len - 20] + '\n… (truncado)'
        return s


class ApprovalProcess(models.Model):
    """
    Instância de processo em aprovação.
    Opcionalmente vinculada a um objeto de negócio (GenericFK).
    """

    flow_definition = models.ForeignKey(
        ApprovalFlowDefinition,
        on_delete=models.PROTECT,
        related_name='processes',
    )
    project = models.ForeignKey(
        'core.Project',
        on_delete=models.CASCADE,
        related_name='approval_processes',
    )
    category = models.ForeignKey(
        ProcessCategory,
        on_delete=models.PROTECT,
        related_name='approval_processes',
    )
    status = models.CharField(
        max_length=32,
        choices=ProcessStatus.choices,
        default=ProcessStatus.AWAITING_STEP,
        db_index=True,
    )
    current_step = models.ForeignKey(
        ApprovalStep,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+',
    )
    title = models.CharField(max_length=300, blank=True)
    summary = models.TextField(blank=True)

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflows_initiated',
    )

    external_system = models.CharField(
        max_length=32,
        default='sienge',
        blank=True,
        help_text='Sistema externo alvo (ex.: sienge).',
    )
    external_entity_type = models.CharField(max_length=80, blank=True)
    external_id = models.CharField(max_length=120, blank=True, db_index=True)
    external_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text='Snapshot não sensível do registo externo (ex.: Sienge) para exibição e auditoria.',
    )
    sync_status = models.CharField(
        max_length=24,
        choices=SyncStatus.choices,
        default=SyncStatus.NOT_APPLICABLE,
        db_index=True,
    )
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Processo de aprovação'
        verbose_name_plural = 'Processos de aprovação'
        permissions = [
            ('configure_approval_flows', 'Pode configurar fluxos da central de aprovações'),
            ('act_on_approval_process', 'Pode aprovar ou reprovar processos em que atua'),
        ]

    def __str__(self):
        return f'{self.project.code} · {self.category.code} — {self.get_status_display()}'


class ApprovalProcessParticipant(models.Model):
    """
    Participantes efetivos por processo/alçada.

    Em processos antigos ou integrações legadas, quando vazio, o sistema usa os
    participantes do fluxo (ApprovalStepParticipant) como fallback.
    """

    process = models.ForeignKey(
        ApprovalProcess,
        on_delete=models.CASCADE,
        related_name='process_participants',
    )
    step = models.ForeignKey(
        ApprovalStep,
        on_delete=models.CASCADE,
        related_name='process_participants',
    )
    role = models.CharField(
        max_length=20,
        choices=ParticipantRole.choices,
        default=ParticipantRole.APPROVER,
    )
    subject_kind = models.CharField(
        max_length=20,
        choices=SubjectKind.choices,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='workflow_process_participations',
    )
    django_group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='workflow_process_participations',
    )
    source_step_participant = models.ForeignKey(
        ApprovalStepParticipant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_process_participants',
    )
    is_runtime_variable = models.BooleanField(default=False)
    label_override = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['step__sequence', 'pk']
        verbose_name = 'Participante efetivo do processo'
        verbose_name_plural = 'Participantes efetivos dos processos'
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(subject_kind=SubjectKind.USER, user__isnull=False, django_group__isnull=True)
                    | Q(
                        subject_kind=SubjectKind.DJANGO_GROUP,
                        user__isnull=True,
                        django_group__isnull=False,
                    )
                ),
                name='workflow_process_participant_user_xor_group',
            ),
        ]

    def __str__(self):
        subj = self.user_id or self.django_group_id
        return f'P{self.process_id} · S{self.step_id} · {self.role} · {subj}'


class HistoryAction(models.TextChoices):
    SUBMITTED = 'submitted', 'Iniciado'
    APPROVED_STEP = 'approved_step', 'Aprovado na alçada'
    REJECTED = 'rejected', 'Reprovado'
    COMMENT = 'comment', 'Comentário'
    CANCELLED = 'cancelled', 'Cancelado'
    SYNC_EVENT = 'sync_event', 'Evento de integração'


class ApprovalHistoryEntry(models.Model):
    """Histórico append-only do processo."""

    process = models.ForeignKey(
        ApprovalProcess,
        on_delete=models.CASCADE,
        related_name='history_entries',
    )
    step = models.ForeignKey(
        ApprovalStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    step_sequence_snapshot = models.PositiveIntegerField(null=True, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_history_actions',
    )
    action = models.CharField(max_length=32, choices=HistoryAction.choices)
    comment = models.TextField(blank=True)
    previous_status = models.CharField(max_length=32, blank=True)
    new_status = models.CharField(max_length=32, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Histórico de aprovação'
        verbose_name_plural = 'Históricos de aprovação'

    def __str__(self):
        return f'{self.process_id} {self.action} @ {self.created_at}'


class OutboxStatus(models.TextChoices):
    PENDING = 'pending', 'Pendente'
    SENT = 'sent', 'Enviado'
    FAILED = 'failed', 'Falhou'


class SiengeCentralSyncState(models.Model):
    """
    Registo único (pk=1) com o resultado da última ingestão Sienge agendada (Celery).

    Alimenta a Central de Aprovações (contratos/medições); processos aprovados aqui
    podem integrar-se depois com fluxos de assinatura (ex.: ClickSign), quando existirem.
    """

    id = models.IntegerField(primary_key=True, default=1, editable=False)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_ok = models.BooleanField(default=False)
    last_stats = models.JSONField(default=dict, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Sync Sienge para Central (estado)'
        verbose_name_plural = 'Sync Sienge para Central (estado)'

    def __str__(self):
        return f'Sienge sync @ {self.last_run_at} ok={self.last_ok}'

    @classmethod
    def get_singleton(cls) -> 'SiengeCentralSyncState':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ApprovalIntegrationOutbox(models.Model):
    """Fila de saída para integração (ex.: Sienge), desacoplada do HTTP."""

    process = models.ForeignKey(
        ApprovalProcess,
        on_delete=models.CASCADE,
        related_name='integration_outbox_entries',
    )
    event_type = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=16,
        choices=OutboxStatus.choices,
        default=OutboxStatus.PENDING,
        db_index=True,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Outbox de integração'
        verbose_name_plural = 'Outbox de integração'


class ExternalParticipantSignupRequest(models.Model):
    """
    Solicitação administrativa para criar/vincular participante externo variável.
    """

    process = models.ForeignKey(
        ApprovalProcess,
        on_delete=models.CASCADE,
        related_name='external_signup_requests',
    )
    step = models.ForeignKey(
        ApprovalStep,
        on_delete=models.CASCADE,
        related_name='external_signup_requests',
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_external_requests_created',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_external_requests_reviewed',
    )
    linked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_external_requests_linked',
    )
    variable_key = models.SlugField(max_length=64, blank=True)
    full_name = models.CharField(max_length=255)
    company_name = models.CharField(max_length=180, blank=True)
    email = models.EmailField(db_index=True)
    phone_whatsapp = models.CharField(max_length=40, blank=True, db_index=True)
    cnpj = models.CharField(max_length=32, blank=True, db_index=True)
    note = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=ExternalSignupStatus.choices,
        default=ExternalSignupStatus.PENDING,
        db_index=True,
    )
    review_reason = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Solicitação de cadastro externo (workflow)'
        verbose_name_plural = 'Solicitações de cadastro externo (workflow)'
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['email', 'status']),
            models.Index(fields=['phone_whatsapp', 'status']),
        ]

    def __str__(self):
        return f'{self.full_name} · {self.email} · {self.get_status_display()}'
