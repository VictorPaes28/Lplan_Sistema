from datetime import timedelta
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def rh_upload_path(instance, filename):
    return f'rh/documentos/{instance.colaborador_id}/{instance.tipo_id}/{filename}'


class ObraLocal(models.Model):
    """Obra de alocação do colaborador; pode espelhar gestao_aprovacao.Obra."""

    nome = models.CharField('Nome', max_length=120, unique=True)
    gestao_obra = models.ForeignKey(
        'gestao_aprovacao.Obra',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='obras_rh',
        verbose_name='Obra GestControll',
    )

    class Meta:
        verbose_name = 'Obra (RH)'
        verbose_name_plural = 'Obras (RH)'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class CargoRH(models.Model):
    nome = models.CharField('Nome', max_length=120, unique=True)

    class Meta:
        verbose_name = 'Cargo (RH)'
        verbose_name_plural = 'Cargos (RH)'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class CargoCatalogo(models.Model):
    """Catálogo de cargos operacionais para sugestão em novas requisições."""

    nome = models.CharField('Nome', max_length=120, unique=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cargo (catálogo)'
        verbose_name_plural = 'Cargos (catálogo)'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class TipoDocumento(models.Model):
    class AplicaA(models.TextChoices):
        TODOS = 'todos', 'Todos os colaboradores'
        POR_CARGO = 'por_cargo', 'Por Cargo específico'
        POR_OBRA = 'por_obra', 'Por Obra específica'

    nome = models.CharField('Nome', max_length=200)
    aplica_a = models.CharField(
        'Aplica-se a',
        max_length=20,
        choices=AplicaA.choices,
        default=AplicaA.TODOS,
    )
    tem_validade = models.BooleanField('Tem validade', default=False)
    dias_validade = models.PositiveIntegerField('Dias de validade', null=True, blank=True)
    obrigatorio = models.BooleanField('Obrigatório', default=True)
    ordem = models.PositiveSmallIntegerField('Ordem', default=0)
    cargos_aplicaveis = models.ManyToManyField(
        CargoRH,
        blank=True,
        related_name='tipos_documento',
        verbose_name='Cargos aplicáveis',
        help_text='Preencher apenas se aplica_a=por_cargo',
    )
    obras_aplicaveis = models.ManyToManyField(
        ObraLocal,
        blank=True,
        related_name='tipos_documento',
        verbose_name='Obras aplicáveis',
        help_text='Preencher apenas se aplica_a=por_obra',
    )

    class Meta:
        verbose_name = 'Tipo de documento'
        verbose_name_plural = 'Tipos de documento'
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome


class Colaborador(models.Model):
    class Status(models.TextChoices):
        EM_ADMISSAO = 'em_admissao', 'Em Admissão'
        ATIVO = 'ativo', 'Ativo'
        DESLIGADO = 'desligado', 'Desligado'

    nome = models.CharField('Nome completo', max_length=200)
    cpf = models.CharField('CPF', max_length=14, unique=True)
    email = models.EmailField('E-mail', max_length=254, blank=True)
    telefone = models.CharField('Telefone', max_length=20, blank=True)
    rg = models.CharField('RG', max_length=20, blank=True)
    data_nascimento = models.DateField('Data de nascimento', null=True, blank=True)
    endereco = models.CharField('Endereço', max_length=300, blank=True)
    dados_bancarios = models.CharField('Conta bancária', max_length=200, blank=True)
    pis = models.CharField('PIS', max_length=20, blank=True)
    escolaridade = models.CharField('Escolaridade', max_length=120, blank=True)
    tamanho_camisa = models.CharField('Tamanho camisa', max_length=10, blank=True)
    tamanho_bota = models.CharField('Tamanho bota', max_length=10, blank=True)
    cargo = models.CharField('Cargo', max_length=120)
    cargo_rh = models.ForeignKey(
        CargoRH,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='colaboradores',
        verbose_name='Cargo (RH)',
    )
    empresa = models.CharField('Empresa', max_length=200, blank=True)
    status = models.CharField(
        'Status',
        max_length=20,
        choices=Status.choices,
        default=Status.EM_ADMISSAO,
    )
    data_admissao = models.DateField('Data de admissão', null=True, blank=True)
    etapa_admissao = models.PositiveSmallIntegerField(
        'Etapa admissão',
        default=1,
        help_text='1=Requisição … 5=Ativo',
    )
    tipo_contrato = models.CharField('Tipo de contrato', max_length=40, blank=True, default='CLT')
    salario = models.CharField('Salário', max_length=40, blank=True)
    gestor_aprovador = models.CharField('Gestor aprovador', max_length=120, blank=True)
    gestor_aprovador_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requisicoes_admissao_gestor',
        verbose_name='Gestor aprovador (usuário)',
    )
    requisicao_aprovada_gestor = models.BooleanField(
        'Requisição aprovada pelo gestor',
        default=False,
    )
    requisicao_reprovada = models.BooleanField(
        'Requisição reprovada pelo gestor',
        default=False,
    )
    requisicao_motivo_reprovacao = models.TextField(
        'Motivo da reprovação da requisição',
        blank=True,
    )
    requisicao_criada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requisicoes_admissao_criadas',
        verbose_name='Requisição criada por',
    )
    motivo_admissao = models.CharField('Motivo admissão', max_length=120, blank=True)
    observacoes_requisicao = models.TextField('Observações da requisição', blank=True)
    obras = models.ManyToManyField(ObraLocal, blank=True, related_name='colaboradores')
    token_portal = models.CharField(
        'Token do portal',
        max_length=64,
        blank=True,
        unique=True,
        null=True,
        help_text='Token para acesso ao portal do candidato',
    )
    token_portal_expira = models.DateTimeField(
        'Expiração do token',
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Colaborador'
        verbose_name_plural = 'Colaboradores'
        ordering = ['nome']

    def __str__(self):
        return self.nome

    @property
    def iniciais(self):
        parts = self.nome.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.nome[:2].upper() if self.nome else '?'

    def documentos_recebidos(self):
        return self.documentos.filter(status=DocumentoColaborador.Status.RECEBIDO).count()

    def documentos_total(self):
        return self.documentos.count()

    def documentos_obrigatorios_pendentes(self):
        return self.documentos.filter(
            tipo__obrigatorio=True,
        ).exclude(status=DocumentoColaborador.Status.RECEBIDO).count()

    def proximo_prazo(self):
        doc = (
            self.documentos.filter(vencimento__isnull=False)
            .order_by('vencimento')
            .first()
        )
        return doc.vencimento if doc else None

    def dias_proximo_prazo(self):
        prazo = self.proximo_prazo()
        if prazo is None:
            return None
        return (prazo - timezone.localdate()).days

    def gerar_token_portal(self, dias=30):
        self.token_portal = secrets.token_urlsafe(32)
        self.token_portal_expira = timezone.now() + timedelta(days=dias)
        self.save(update_fields=['token_portal', 'token_portal_expira'])
        return self.token_portal

    def token_portal_valido(self):
        if not self.token_portal:
            return False
        if self.token_portal_expira:
            return timezone.now() < self.token_portal_expira
        return True


class DocumentoColaborador(models.Model):
    class Status(models.TextChoices):
        RECEBIDO = 'received', 'Recebido'
        PENDENTE = 'pending', 'Pendente'
        FALTANDO = 'missing', 'Faltando'

    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.CASCADE,
        related_name='documentos',
    )
    tipo = models.ForeignKey(
        TipoDocumento,
        on_delete=models.PROTECT,
        related_name='documentos_colaborador',
    )
    status = models.CharField(
        'Status',
        max_length=20,
        choices=Status.choices,
        default=Status.FALTANDO,
    )
    vencimento = models.DateField('Vencimento', null=True, blank=True)
    observacao = models.CharField('Observação', max_length=300, blank=True)
    arquivo = models.FileField('Arquivo', upload_to=rh_upload_path, blank=True, null=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Documento do colaborador'
        verbose_name_plural = 'Documentos dos colaboradores'
        unique_together = [('colaborador', 'tipo')]
        ordering = ['tipo__ordem', 'tipo__nome']

    def __str__(self):
        return f'{self.colaborador.nome} — {self.tipo.nome}'


class AdmissaoHistorico(models.Model):
    colaborador = models.ForeignKey(
        Colaborador,
        on_delete=models.CASCADE,
        related_name='historico_admissao',
    )
    etapa = models.PositiveSmallIntegerField('Etapa')
    descricao = models.CharField('Descrição', max_length=300)
    data_hora = models.DateTimeField('Data/hora', default=timezone.now)
    autor = models.CharField('Autor', max_length=120, blank=True)
    concluido = models.BooleanField('Concluído', default=True)

    class Meta:
        verbose_name = 'Histórico de admissão'
        verbose_name_plural = 'Históricos de admissão'
        ordering = ['data_hora']

    def __str__(self):
        return f'{self.colaborador.nome} — {self.descricao}'


class ConfiguracaoAlertasRH(models.Model):
    """Configuração global (singleton) de prazos e canais de alerta do RH."""

    dias_documento_vencendo = models.PositiveSmallIntegerField(
        'Documentos com vencimento próximo (dias)',
        default=30,
    )
    dias_treinamento_vencer = models.PositiveSmallIntegerField(
        'Treinamentos a vencer (dias)',
        default=60,
    )
    dias_renovacao_aso = models.PositiveSmallIntegerField(
        'Renovação de ASO (dias)',
        default=45,
    )
    dias_renotificar_vencido = models.PositiveSmallIntegerField(
        'Documentos vencidos — renotificar (dias)',
        default=7,
    )
    canal_email_rh = models.BooleanField('E-mail para o RH', default=True)
    canal_notificacao_sistema = models.BooleanField('Notificação no sistema', default=True)
    canal_whatsapp_gestor = models.BooleanField('WhatsApp para o gestor', default=False)
    canal_relatorio_pdf_semanal = models.BooleanField('Relatório semanal PDF', default=True)
    responsaveis = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='config_alertas_rh',
        verbose_name='Responsáveis por receber alertas',
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração de alertas RH'
        verbose_name_plural = 'Configuração de alertas RH'

    def __str__(self):
        return 'Configuração de alertas RH'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ContratoAdmissao(models.Model):
    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente assinatura (ZapSign)'
        CONCLUIDO = 'concluido', 'Contrato assinado arquivado'

    colaborador = models.OneToOneField(
        Colaborador,
        on_delete=models.CASCADE,
        related_name='contrato_admissao',
    )
    pdf_contrato = models.FileField(
        'PDF do contrato',
        upload_to='rh/contratos/%Y/%m/',
        blank=True,
        null=True,
        help_text='Rascunho gerado pelo sistema ou PDF assinado vindo do ZapSign',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    concluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Contrato de admissão'

    def __str__(self):
        return f'Contrato — {self.colaborador.nome}'
