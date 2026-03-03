import os
import unicodedata
import re
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Empresa(models.Model):
    """
    Model para Empresa.
    Representa uma empresa que possui várias obras.
    """
    
    codigo = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Código',
        help_text='Código único da empresa (ex: EMP-001)'
    )
    
    nome = models.CharField(
        max_length=200,
        verbose_name='Nome',
        help_text='Nome da empresa'
    )
    
    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name='E-mail',
        help_text='E-mail principal da empresa'
    )
    
    telefone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Telefone',
        help_text='Telefone de contato'
    )
    
    responsavel = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='empresas_responsavel',
        verbose_name='Responsável pela Empresa',
        help_text='Usuário responsável por gerenciar esta empresa',
        limit_choices_to={'groups__name': 'Responsavel Empresa'},
        null=True,
        blank=True
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name='Ativo',
        help_text='Indica se a empresa está ativa'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Atualização'
    )
    
    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering = ['codigo']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class Obra(models.Model):
    """
    Model para Obra.
    Representa uma obra física onde serão feitos os pedidos.
    Cada obra pertence a uma empresa.
    Quando project está preenchido, esta obra é a mesma do Diário de Obra (core.Project):
    um único cadastro de obra para todo o sistema.
    """
    # Vínculo com o projeto do Diário de Obra (lista única de obras no sistema)
    project = models.ForeignKey(
        'core.Project',
        on_delete=models.SET_NULL,
        related_name='obras_gestao',
        verbose_name='Projeto (Diário de Obra)',
        help_text='Projeto correspondente no Diário de Obra; se preenchido, acesso ao usuário é unificado.',
        null=True,
        blank=True,
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name='obras',
        verbose_name='Empresa',
        help_text='Empresa à qual esta obra pertence',
        null=True,  # Temporariamente nullable até migrar dados
        blank=True  # Temporariamente blank até migrar dados
    )
    
    codigo = models.CharField(
        max_length=50,
        verbose_name='Código',
        help_text='Código da obra (ex: OBRA-001)'
    )
    
    nome = models.CharField(
        max_length=200,
        verbose_name='Nome',
        help_text='Nome ou identificador da obra'
    )
    
    descricao = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descrição',
        help_text='Descrição adicional da obra'
    )
    
    email_obra = models.EmailField(
        blank=True,
        null=True,
        verbose_name='E-mail da Obra',
        help_text='E-mail para notificações relacionadas à obra (opcional)'
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name='Ativo',
        help_text='Indica se a obra está ativa'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Atualização'
    )
    
    class Meta:
        verbose_name = 'Obra'
        verbose_name_plural = 'Obras'
        ordering = ['empresa', 'codigo']
        # unique_together removido temporariamente porque empresa pode ser NULL
        # Será adicionado em migração futura após todas as obras terem empresa
    
    def __str__(self):
        if self.empresa_id:
            return f"{self.empresa.codigo}-{self.codigo} - {self.nome}"
        return f"{self.codigo} - {self.nome}"


class WorkOrder(models.Model):
    """
    Model para Pedido de Obra.
    Representa um pedido de obra criado por um engenheiro e que precisa ser aprovado por gestores.
    """
    
    # Status possíveis do pedido
    STATUS_CHOICES = [
        ('rascunho', 'Rascunho'),
        ('pendente', 'Pendente Aprovação'),
        ('aprovado', 'Aprovado'),
        ('reprovado', 'Reprovado'),
        ('reaprovacao', 'Reaprovação'),
        ('cancelado', 'Cancelado'),
    ]
    
    # Tipo de solicitação
    TIPO_SOLICITACAO_CHOICES = [
        ('contrato', 'Contrato'),
        ('medicao', 'Medição'),
        ('ordem_servico', 'Ordem de Serviço (OS)'),
        ('mapa_cotacao', 'Mapa de Cotação'),
    ]
    
    # Relacionamento com Obra (OBRIGATÓRIO)
    obra = models.ForeignKey(
        Obra,
        on_delete=models.PROTECT,
        related_name='work_orders',
        verbose_name='Obra',
        help_text='Obra à qual este pedido pertence'
    )
    
    # Campos principais
    codigo = models.CharField(
        max_length=50,
        verbose_name='Código',
        help_text='Código único do pedido (ex: OB-2024-001)'
        # Único por obra (definido em Meta.unique_together)
    )
    
    # Campos conforme checklist
    nome_credor = models.CharField(
        max_length=200,
        verbose_name='Nome do Credor',
        help_text='Nome do fornecedor/credor relacionado ao pedido'
    )
    
    tipo_solicitacao = models.CharField(
        max_length=20,
        choices=TIPO_SOLICITACAO_CHOICES,
        verbose_name='Tipo de Solicitação',
        help_text='Tipo de solicitação: Contrato ou Medição'
    )
    
    observacoes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observações',
        help_text='Observações ou detalhes adicionais sobre o pedido'
    )
    
    # Campos opcionais (mantidos para compatibilidade, mas podem ser removidos depois)
    valor_estimado = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='Valor Estimado',
        help_text='Valor estimado (opcional)'
    )
    prazo_estimado = models.IntegerField(
        blank=True,
        null=True,
        verbose_name='Prazo Estimado (dias)',
        help_text='Prazo estimado em dias (opcional)'
    )
    local = models.CharField(
        max_length=300,
        blank=True,
        null=True,
        verbose_name='Local',
        help_text='Localização adicional (opcional)'
    )
    
    # Status e controle
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='rascunho',
    )
    
    # Controle de exclusão
    solicitado_exclusao = models.BooleanField(
        default=False,
        verbose_name='Solicitado para Exclusão',
        help_text='Indica se o pedido foi solicitado para exclusão pelo solicitante'
    )
    
    solicitado_exclusao_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos_solicitados_exclusao',
        verbose_name='Solicitado Exclusão Por',
        help_text='Usuário que solicitou a exclusão do pedido'
    )
    
    solicitado_exclusao_em = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Solicitado Exclusão Em',
        help_text='Data e hora em que a exclusão foi solicitada'
    )
    
    motivo_exclusao = models.TextField(
        blank=True,
        null=True,
        verbose_name='Motivo da Exclusão',
        help_text='Motivo informado pelo solicitante para exclusão do pedido'
    )
    
    # Controle de exclusão pelo admin (apenas para pedidos aprovados)
    marcado_para_deletar = models.BooleanField(
        default=False,
        verbose_name='Marcado para Deletar',
        help_text='Indica se o pedido foi marcado pelo admin para ser deletado do sistema'
    )
    
    marcado_para_deletar_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos_marcados_deletar',
        verbose_name='Marcado para Deletar Por',
        help_text='Admin que marcou o pedido para exclusão'
    )
    
    marcado_para_deletar_em = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Marcado para Deletar Em',
        help_text='Data e hora em que o pedido foi marcado para exclusão'
    )
    
    # Relacionamentos
    criado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='work_orders_criados',
        verbose_name='Criado por (Solicitante)',
        help_text='Usuário que criou o pedido (engenheiro solicitante)'
    )
    
    # Datas
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Atualização'
    )
    data_envio = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Data de Envio',
        help_text='Data/hora em que o pedido foi enviado para aprovação (preenchido automaticamente)'
    )
    data_aprovacao = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Data de Aprovação/Reprovação',
        help_text='Data em que o pedido foi aprovado ou reprovado'
    )
    
    class Meta:
        verbose_name = 'Pedido de Obra'
        verbose_name_plural = 'Pedidos de Obra'
        ordering = ['-created_at']  # Mais recentes primeiro
        unique_together = [['obra', 'codigo']]  # Código único por obra
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['obra', '-created_at']),
            models.Index(fields=['criado_por', '-created_at']),
            models.Index(fields=['nome_credor']),
            models.Index(fields=['data_envio', '-created_at']),  # Para filtros por data
            models.Index(fields=['status', 'data_envio']),  # Para filtros combinados
            models.Index(fields=['marcado_para_deletar', 'status']),  # Para filtro de analisados
        ]
    
    def __str__(self):
        return f"{self.codigo} - {self.nome_credor}"
    
    # Transições válidas de status (state machine)
    TRANSICOES_VALIDAS = {
        'rascunho': ['pendente', 'cancelado'],
        'pendente': ['aprovado', 'reprovado', 'cancelado'],
        'aprovado': [],  # Estado final - imutável
        'reprovado': ['reaprovacao', 'cancelado'],
        'reaprovacao': ['aprovado', 'reprovado', 'cancelado'],
        'cancelado': [],  # Estado final
    }

    def pode_transitar_para(self, novo_status):
        """
        Verifica se a transição de status é válida conforme o state machine.
        
        Transições válidas:
          rascunho    -> pendente, cancelado
          pendente    -> aprovado, reprovado, cancelado
          aprovado    -> (nenhuma - estado final)
          reprovado   -> reaprovacao, cancelado
          reaprovacao -> aprovado, reprovado, cancelado
          cancelado   -> (nenhuma - estado final)
        """
        return novo_status in self.TRANSICOES_VALIDAS.get(self.status, [])

    def transitar_status(self, novo_status, user=None):
        """
        Realiza a transição de status com validação.
        Levanta ValidationError se a transição for inválida.
        """
        if not self.pode_transitar_para(novo_status):
            from django.core.exceptions import ValidationError
            raise ValidationError(
                f'Transição de status inválida: "{self.get_status_display()}" → '
                f'"{dict(self.STATUS_CHOICES).get(novo_status, novo_status)}". '
                f'Transições permitidas: {", ".join(self.TRANSICOES_VALIDAS.get(self.status, [])) or "nenhuma (estado final)"}.'
            )
        self.status = novo_status

    def pode_editar(self, user):
        """
        Verifica se o usuário pode editar este pedido.
        Regra: só pode editar se estiver pendente para aprovação, em reaprovação, reprovado (para reenviar), ou rascunho, e for o criador.
        """
        if self.status in ['pendente', 'reaprovacao', 'rascunho']:
            return self.criado_por == user
        # Se estiver reprovado, o criador pode editar para reenviar
        if self.status == 'reprovado':
            return self.criado_por == user
        return False
    
    def pode_aprovar(self, user):
        """
        Verifica se o usuário pode aprovar/reprovar este pedido.
        Regra: precisa estar pendente ou em reaprovação e o usuário deve ser gestor/admin.
        (A validação de permissão será feita na view)
        """
        return self.status in ['pendente', 'reaprovacao']


class Approval(models.Model):
    """
    Model para registro de aprovações/reprovações de pedidos de obra.
    Mantém histórico completo de todas as decisões tomadas.
    """
    
    DECISAO_CHOICES = [
        ('aprovado', 'Aprovado'),
        ('reprovado', 'Reprovado'),
    ]
    
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name='approvals',
        verbose_name='Pedido de Obra',
        help_text='Pedido de obra relacionado'
    )
    
    aprovado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='approvals_feitas',
        verbose_name='Aprovado/Reprovado por',
        help_text='Usuário que tomou a decisão'
    )
    
    decisao = models.CharField(
        max_length=20,
        choices=DECISAO_CHOICES,
        verbose_name='Decisão',
        help_text='Aprovação ou reprovação'
    )
    
    comentario = models.TextField(
        blank=True,
        null=True,
        verbose_name='Comentário',
        help_text='Justificativa ou observações sobre a decisão'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data/Hora da Decisão'
    )
    
    # Tags de erro (apenas para reprovações)
    tags_erro = models.ManyToManyField(
        'TagErro',
        related_name='approvals',
        blank=True,
        verbose_name='Tags de Erro',
        help_text='Tags/motivos de erro selecionados para esta reprovação'
    )
    
    class Meta:
        verbose_name = 'Aprovação'
        verbose_name_plural = 'Aprovações'
        ordering = ['-created_at']  # Mais recentes primeiro
        indexes = [
            models.Index(fields=['work_order', '-created_at']),
            models.Index(fields=['aprovado_por', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.work_order.codigo} - {self.get_decisao_display()} por {self.aprovado_por.username} em {self.created_at.strftime('%d/%m/%Y %H:%M')}"


def sanitize_filename(filename):
    """
    Sanitiza o nome de um arquivo removendo caracteres especiais e acentos.
    Converte caracteres especiais para ASCII equivalente.
    """
    # Separar nome e extensão
    name, ext = os.path.splitext(filename)
    
    # Normalizar unicode (NFD = decomposição)
    name = unicodedata.normalize('NFD', name)
    
    # Remover acentos e caracteres diacríticos
    name = ''.join(char for char in name if unicodedata.category(char) != 'Mn')
    
    # Substituir espaços por underscores
    name = name.replace(' ', '_')
    
    # Remover caracteres especiais, mantendo apenas letras, números, underscore e hífen
    name = re.sub(r'[^a-zA-Z0-9_-]', '', name)
    
    # Limitar tamanho (evitar nomes muito longos)
    if len(name) > 200:
        name = name[:200]
    
    # Retornar nome sanitizado com extensão
    return name + ext.lower()


def attachment_upload_path(instance, filename):
    """
    Função para gerar o caminho de upload de anexos com nome sanitizado.
    """
    # Sanitizar o nome do arquivo
    filename = sanitize_filename(filename)
    
    # Retornar caminho com data (anexos/YYYY/MM/DD/nome_sanitizado.ext)
    return os.path.join('anexos', timezone.now().strftime('%Y/%m/%d'), filename)


class Attachment(models.Model):
    """
    Model para anexos de documentos relacionados a pedidos de obra.
    Permite upload de arquivos (PDFs, imagens, documentos, etc.).
    """
    
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='Pedido de Obra',
        help_text='Pedido de obra relacionado'
    )
    
    arquivo = models.FileField(
        upload_to=attachment_upload_path,
        verbose_name='Arquivo',
        help_text='Arquivo anexado (PDF, imagem, documento, etc.)'
    )
    
    nome = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Nome do Arquivo',
        help_text='Nome descritivo do arquivo (opcional, será preenchido automaticamente se vazio)'
    )
    
    descricao = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descrição',
        help_text='Descrição ou observações sobre o anexo'
    )
    
    enviado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='attachments_enviados',
        verbose_name='Enviado por',
        help_text='Usuário que fez o upload do arquivo'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data/Hora do Upload'
    )
    
    # Campo para identificar anexos adicionados durante reaprovação
    versao_reaprovacao = models.IntegerField(
        default=0,
        verbose_name='Versão de Reaprovação',
        help_text='Número da versão de reaprovação quando o anexo foi adicionado (0 = versão original)'
    )
    
    class Meta:
        verbose_name = 'Anexo'
        verbose_name_plural = 'Anexos'
        ordering = ['-created_at']  # Mais recentes primeiro
        indexes = [
            models.Index(fields=['work_order', '-created_at']),
            models.Index(fields=['enviado_por', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.work_order.codigo} - {self.get_nome_display()}"
    
    def get_nome_display(self):
        """Retorna o nome do arquivo ou o nome do arquivo original."""
        if self.nome:
            return self.nome
        return self.arquivo.name.split('/')[-1] if self.arquivo else 'Sem nome'
    
    def get_tamanho_display(self):
        """Retorna o tamanho do arquivo formatado."""
        if not self.arquivo:
            return '0 B'
        
        try:
            tamanho = self.arquivo.size
            for unidade in ['B', 'KB', 'MB', 'GB']:
                if tamanho < 1024.0:
                    return f"{tamanho:.2f} {unidade}"
                tamanho /= 1024.0
            return f"{tamanho:.2f} TB"
        except Exception:
            return 'N/A'
    
    def get_extensao(self):
        """Retorna a extensão do arquivo."""
        if not self.arquivo:
            return ''
        nome = self.arquivo.name
        if '.' in nome:
            return nome.split('.')[-1].upper()
        return ''


class StatusHistory(models.Model):
    """
    Model para histórico completo de mudanças de status dos pedidos.
    Registra todas as transições de status (não apenas aprovações).
    """
    
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name='Pedido de Obra',
        help_text='Pedido de obra relacionado'
    )
    
    status_anterior = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Status Anterior',
        help_text='Status antes da mudança'
    )
    
    status_novo = models.CharField(
        max_length=20,
        verbose_name='Status Novo',
        help_text='Novo status'
    )
    
    alterado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='status_changes',
        verbose_name='Alterado por',
        help_text='Usuário que fez a alteração'
    )
    
    observacao = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observação',
        help_text='Observação sobre a mudança de status'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data/Hora da Alteração'
    )
    
    class Meta:
        verbose_name = 'Histórico de Status'
        verbose_name_plural = 'Históricos de Status'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['work_order', '-created_at']),
        ]
    
    def __str__(self):
        status_ant = self.status_anterior or 'N/A'
        return f"{self.work_order.codigo}: {status_ant} → {self.status_novo} ({self.created_at.strftime('%d/%m/%Y %H:%M')})"


class WorkOrderPermission(models.Model):
    """
    Model para gerenciar permissões de usuários por obra.
    Define se um usuário pode atuar como solicitante ou aprovador em uma obra específica.
    """
    
    TIPO_PERMISSAO_CHOICES = [
        ('solicitante', 'Solicitante'),
        ('aprovador', 'Aprovador'),
    ]
    
    obra = models.ForeignKey(
        Obra,
        on_delete=models.CASCADE,
        related_name='permissoes',
        verbose_name='Obra',
        help_text='Obra à qual esta permissão se refere'
    )
    
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='permissoes_obra',
        verbose_name='Usuário',
        help_text='Usuário que terá a permissão'
    )
    
    tipo_permissao = models.CharField(
        max_length=20,
        choices=TIPO_PERMISSAO_CHOICES,
        verbose_name='Tipo de Permissão',
        help_text='Tipo de permissão: Solicitante ou Aprovador'
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name='Ativo',
        help_text='Indica se a permissão está ativa'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Atualização'
    )
    
    class Meta:
        verbose_name = 'Permissão de Obra'
        verbose_name_plural = 'Permissões de Obra'
        unique_together = ('obra', 'usuario', 'tipo_permissao')  # Um usuário não pode ter a mesma permissão duplicada
        ordering = ['obra', 'usuario']
        indexes = [
            models.Index(fields=['obra', 'tipo_permissao', 'ativo']),
            models.Index(fields=['usuario', 'tipo_permissao', 'ativo']),
        ]
    
    def __str__(self):
        return f"{self.obra} - {self.usuario.username} ({self.get_tipo_permissao_display()})"


class UserEmpresa(models.Model):
    """
    Model para vincular usuários a empresas.
    Um usuário pode estar vinculado a múltiplas empresas.
    """
    
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='empresas_vinculadas',
        verbose_name='Usuário',
        help_text='Usuário vinculado à empresa'
    )
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='usuarios_vinculados',
        verbose_name='Empresa',
        help_text='Empresa à qual o usuário está vinculado'
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name='Ativo',
        help_text='Indica se o vínculo está ativo'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )
    
    class Meta:
        verbose_name = 'Vínculo Usuário-Empresa'
        verbose_name_plural = 'Vínculos Usuário-Empresa'
        unique_together = ('usuario', 'empresa')  # Um usuário não pode estar duplicado na mesma empresa
        ordering = ['empresa', 'usuario']
    
    def __str__(self):
        return f"{self.usuario.username} - {self.empresa.nome}"


class UserProfile(models.Model):
    """
    Model para Perfil de Usuário.
    Estende o modelo User do Django com informações adicionais, como foto de perfil.
    """
    
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil',
        verbose_name='Usuário',
        help_text='Usuário associado a este perfil'
    )
    
    foto_perfil = models.ImageField(
        upload_to='perfis/',
        blank=True,
        null=True,
        verbose_name='Foto de Perfil',
        help_text='Foto de perfil do usuário (opcional)'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Atualização'
    )
    
    class Meta:
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuário'
        ordering = ['usuario__username']
    
    def __str__(self):
        return f"Perfil de {self.usuario.username}"
    
    def get_foto_url(self):
        """Retorna a URL da foto de perfil ou uma imagem padrão."""
        if self.foto_perfil:
            return self.foto_perfil.url
        return '/static/images/default-avatar.png'  # Imagem padrão (vamos criar)


class Comment(models.Model):
    """
    Model para comentários em pedidos de obra.
    Permite comunicação entre solicitantes e aprovadores durante a análise.
    """
    
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Pedido de Obra',
        help_text='Pedido de obra relacionado'
    )
    
    autor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='comentarios_feitos',
        verbose_name='Autor',
        help_text='Usuário que fez o comentário'
    )
    
    texto = models.TextField(
        verbose_name='Comentário',
        help_text='Texto do comentário'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data/Hora do Comentário'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Data/Hora da Última Atualização'
    )
    
    class Meta:
        verbose_name = 'Comentário'
        verbose_name_plural = 'Comentários'
        ordering = ['created_at']  # Mais antigos primeiro (thread cronológico)
        indexes = [
            models.Index(fields=['work_order', 'created_at']),
            models.Index(fields=['autor', 'created_at']),
        ]
    
    def __str__(self):
        return f"Comentário de {self.autor.username} em {self.work_order.codigo}"


class Lembrete(models.Model):
    """
    Model para rastrear lembretes enviados sobre pedidos pendentes.
    Evita envio de múltiplos lembretes do mesmo pedido no mesmo dia.
    """
    
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name='lembretes',
        verbose_name='Pedido de Obra',
        help_text='Pedido relacionado ao lembrete'
    )
    
    enviado_para = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='lembretes_recebidos',
        verbose_name='Enviado Para',
        help_text='Aprovador que recebeu o lembrete'
    )
    
    dias_pendente = models.IntegerField(
        verbose_name='Dias Pendente',
        help_text='Quantos dias o pedido estava pendente quando o lembrete foi enviado'
    )
    
    enviado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Enviado Em',
        help_text='Data/hora em que o lembrete foi enviado'
    )
    
    tipo = models.CharField(
        max_length=50,
        choices=[
            ('pendente_1_dia', 'Pendente há 1 dia'),
            ('pendente_2_dias', 'Pendente há 2 dias'),
            ('pendente_3_dias', 'Pendente há 3 dias'),
            ('pendente_5_dias', 'Pendente há 5 dias'),
            ('pendente_7_dias', 'Pendente há 7 dias'),
            ('pendente_10_dias', 'Pendente há 10 dias'),
            ('pendente_15_dias', 'Pendente há 15 dias'),
            ('pendente_20_dias', 'Pendente há 20 dias'),
            ('pendente_30_dias', 'Pendente há 30 dias'),
        ],
        verbose_name='Tipo de Lembrete',
        help_text='Tipo de lembrete enviado'
    )
    
    class Meta:
        verbose_name = 'Lembrete'
        verbose_name_plural = 'Lembretes'
        ordering = ['-enviado_em']
        indexes = [
            models.Index(fields=['work_order', 'enviado_para', 'enviado_em']),
            models.Index(fields=['enviado_para', 'enviado_em']),
        ]
        # Nota: A validação de evitar múltiplos lembretes do mesmo tipo no mesmo dia
        # é feita na lógica do management command, não via unique_together
    
    def __str__(self):
        return f"Lembrete {self.get_tipo_display()} - {self.work_order.codigo} para {self.enviado_para.username}"


class Notificacao(models.Model):
    """
    Model para Notificações do sistema.
    Notifica usuários sobre atualizações em pedidos, aprovações, etc.
    """
    
    TIPO_CHOICES = [
        ('pedido_criado', 'Novo Pedido Criado'),
        ('pedido_atualizado', 'Pedido Atualizado'),
        ('pedido_aprovado', 'Pedido Aprovado'),
        ('pedido_reprovado', 'Pedido Reprovado'),
        ('anexo_adicionado', 'Novo Anexo Adicionado'),
        ('anexo_removido', 'Anexo Removido'),
        ('comentario_adicionado', 'Novo Comentário'),
        ('exclusao_solicitada', 'Exclusão Solicitada'),
        ('exclusao_aprovada', 'Exclusão Aprovada'),
        ('exclusao_rejeitada', 'Exclusão Rejeitada'),
    ]
    
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notificacoes',
        verbose_name='Usuário',
        help_text='Usuário que receberá a notificação'
    )
    
    tipo = models.CharField(
        max_length=50,
        choices=TIPO_CHOICES,
        verbose_name='Tipo de Notificação',
        help_text='Tipo da notificação'
    )
    
    titulo = models.CharField(
        max_length=200,
        verbose_name='Título',
        help_text='Título da notificação'
    )
    
    mensagem = models.TextField(
        verbose_name='Mensagem',
        help_text='Mensagem da notificação'
    )
    
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name='notificacoes',
        null=True,
        blank=True,
        verbose_name='Pedido Relacionado',
        help_text='Pedido relacionado à notificação (se aplicável)'
    )
    
    lida = models.BooleanField(
        default=False,
        verbose_name='Lida',
        help_text='Indica se a notificação foi lida'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )
    
    class Meta:
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['usuario', 'lida', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.titulo} - {self.usuario.username}"
    
    def marcar_como_lida(self):
        """Marca a notificação como lida."""
        self.lida = True
        self.save(update_fields=['lida'])


class TagErro(models.Model):
    """
    Model para tags/motivos de erro por tipo de solicitação.
    Permite cadastrar tags específicas para cada tipo de solicitação.
    """
    
    # Tipos de solicitação (mesmos do WorkOrder)
    TIPO_SOLICITACAO_CHOICES = [
        ('contrato', 'Contrato'),
        ('medicao', 'Medição'),
        ('ordem_servico', 'Ordem de Serviço (OS)'),
        ('mapa_cotacao', 'Mapa de Cotação'),
    ]
    
    nome = models.CharField(
        max_length=200,
        verbose_name='Nome da Tag',
        help_text='Nome do motivo/tag de erro (ex: "Valor acima do orçamento", "Documentação incompleta")'
    )
    
    tipo_solicitacao = models.CharField(
        max_length=20,
        choices=TIPO_SOLICITACAO_CHOICES,
        verbose_name='Tipo de Solicitação',
        help_text='Tipo de solicitação ao qual esta tag se aplica'
    )
    
    descricao = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descrição',
        help_text='Descrição detalhada do motivo de erro (opcional)'
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name='Ativa',
        help_text='Indica se esta tag está ativa e disponível para seleção'
    )
    
    ordem = models.IntegerField(
        default=0,
        verbose_name='Ordem',
        help_text='Ordem de exibição (menor número aparece primeiro)'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Atualizado em'
    )
    
    class Meta:
        verbose_name = 'Tag de Erro'
        verbose_name_plural = 'Tags de Erro'
        ordering = ['tipo_solicitacao', 'ordem', 'nome']
        unique_together = [['nome', 'tipo_solicitacao']]  # Nome único por tipo
    
    def __str__(self):
        return f"{self.get_tipo_solicitacao_display()} - {self.nome}"


class EmailLog(models.Model):
    """
    Model para registrar todos os envios de email do sistema.
    Permite rastrear quais emails foram enviados com sucesso e quais falharam.
    """
    
    # Tipos de email
    TIPO_EMAIL_CHOICES = [
        ('novo_pedido', 'Novo Pedido'),
        ('aprovacao', 'Aprovação'),
        ('reprovacao', 'Reprovação'),
    ]
    
    # Status do envio
    STATUS_CHOICES = [
        ('enviado', 'Enviado com Sucesso'),
        ('falhou', 'Falhou'),
        ('pendente', 'Pendente'),
    ]
    
    tipo_email = models.CharField(
        max_length=20,
        choices=TIPO_EMAIL_CHOICES,
        verbose_name='Tipo de Email',
        db_index=True
    )
    
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name='email_logs',
        verbose_name='Pedido',
        null=True,
        blank=True
    )
    
    destinatarios = models.TextField(
        verbose_name='Destinatários',
        help_text='Lista de emails destinatários (separados por vírgula)'
    )
    
    assunto = models.CharField(
        max_length=500,
        verbose_name='Assunto'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pendente',
        verbose_name='Status',
        db_index=True
    )
    
    mensagem_erro = models.TextField(
        blank=True,
        null=True,
        verbose_name='Mensagem de Erro',
        help_text='Detalhes do erro caso o envio tenha falhado'
    )
    
    tentativas = models.IntegerField(
        default=1,
        verbose_name='Tentativas',
        help_text='Número de tentativas de envio'
    )
    
    enviado_em = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Enviado em',
        help_text='Data e hora em que o email foi enviado com sucesso'
    )
    
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em',
        db_index=True
    )
    
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name='Atualizado em'
    )
    
    class Meta:
        verbose_name = 'Log de Email'
        verbose_name_plural = 'Logs de Email'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['-criado_em', 'status']),
            models.Index(fields=['work_order', 'tipo_email']),
        ]
    
    def __str__(self):
        status_label = 'Enviado' if self.status == 'enviado' else 'Falhou' if self.status == 'falhou' else 'Pendente'
        return f"[{status_label}] {self.get_tipo_email_display()} - {self.assunto[:50]}"
    
    def marcar_como_enviado(self):
        """Marca o email como enviado com sucesso."""
        self.status = 'enviado'
        self.enviado_em = timezone.now()
        self.save(update_fields=['status', 'enviado_em', 'atualizado_em'])
    
    def marcar_como_falhou(self, erro):
        """Marca o email como falhou e registra o erro."""
        self.status = 'falhou'
        self.mensagem_erro = str(erro)[:1000]  # Limita tamanho
        self.tentativas += 1
        self.save(update_fields=['status', 'mensagem_erro', 'tentativas', 'atualizado_em'])

