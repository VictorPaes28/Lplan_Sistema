"""
Models para Diário de Obra V2.0 - LPLAN

Este módulo contém os modelos principais para:
- Estrutura Analítica de Projetos (EAP) hierárquica usando django-treebeard
- Workflow de aprovação de imagens com máquina de estados
- Registros transacionais de progresso diário
"""
import os
from datetime import timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from treebeard.mp_tree import MP_Node, MP_NodeManager


class ActivityStatus(models.TextChoices):
    """Status possíveis para uma Atividade na EAP."""
    NOT_STARTED = 'NS', 'Não Iniciada'
    IN_PROGRESS = 'IP', 'Em Andamento'
    COMPLETED = 'CO', 'Concluída'
    BLOCKED = 'BL', 'Bloqueada'
    CANCELLED = 'CA', 'Cancelada'


class DiaryStatus(models.TextChoices):
    """
    Status do diário. Fluxo simplificado:
    - SALVAMENTO_PARCIAL: rascunho (Salvar rascunho); editável.
    - PREENCHENDO: em preenchimento (legado ou estado intermediário); editável.
    - REVISAR: legado (não usado no fluxo atual).
    - APROVADO: diário finalizado (Salvar diário); enviado ao dono da obra; somente leitura.
    """
    PREENCHENDO = 'PR', 'Preenchendo'
    SALVAMENTO_PARCIAL = 'SP', 'Salvamento Parcial'
    AGUARDANDO_APROVACAO_GESTOR = 'AG', 'Aguardando aprovação do gestor'
    REPROVADO_GESTOR = 'RG', 'Reprovado pelo gestor'
    REVISAR = 'RV', 'Revisar'  # Legado
    APROVADO = 'AP', 'Aprovado'


class Project(models.Model):
    """
    Entidade raiz que representa um Projeto de Construção.
    
    Cada projeto contém uma hierarquia de atividades (EAP) e múltiplos
    diários de obra associados.
    """
    name = models.CharField(
        max_length=255,
        verbose_name='Nome do Projeto',
        help_text='Nome oficial do projeto de construção'
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Código do Projeto',
        help_text='Código único identificador do projeto (ex: PROJ-2024-001)'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Descrição',
        help_text='Descrição detalhada do projeto'
    )
    address = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Endereço',
        help_text='Endereço completo da obra'
    )
    responsible = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Responsável',
        help_text='Nome do responsável pela obra'
    )
    contract_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Número do Contrato',
        help_text='Número do contrato da obra'
    )
    client_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Contratante',
        help_text='Nome do cliente/contratante'
    )
    start_date = models.DateField(
        verbose_name='Data de Início',
        help_text='Data planejada de início do projeto'
    )
    end_date = models.DateField(
        verbose_name='Data de Término',
        help_text='Data planejada de término do projeto'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Data de Atualização'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Ativo',
        help_text='Indica se o projeto está ativo'
    )
    sienge_codigos_alternativos = models.TextField(
        blank=True,
        verbose_name='Códigos Sienge alternativos (Mapa de suprimentos)',
        help_text=(
            'Outros códigos de obra no Sienge que devem apontar para este projeto na importação MAPA '
            '(ex.: MAPA envia 42 e o código principal da obra é 260). Separar por vírgula, ponto e vírgula ou linha.'
        ),
    )

    class Meta:
        verbose_name = 'Projeto'
        verbose_name_plural = 'Projetos'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active', '-created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class ProjectMember(models.Model):
    """
    Vínculo usuário–obra no Diário de Obra.
    Só aparecem na seleção de obra os projetos aos quais o usuário está vinculado.
    Staff/superuser veem todas as obras.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='diario_project_memberships',
        verbose_name='Usuário',
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name='Obra / Projeto',
    )

    class Meta:
        verbose_name = 'Vínculo usuário–obra (Diário)'
        verbose_name_plural = 'Vínculos usuário–obra (Diário)'
        unique_together = [['user', 'project']]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['project']),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.project.code}"


class ProjectDiaryRecipient(models.Model):
    """
    E-mail que recebe todo dia um aviso quando houver diário da obra.
    Cadastrado por obra; o envio é feito por tarefa agendada (comando ou Celery).
    """
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='diary_recipients',
        verbose_name='Obra',
    )
    email = models.EmailField(verbose_name='E-mail')
    nome = models.CharField(
        max_length=120,
        blank=True,
        verbose_name='Nome (opcional)',
        help_text='Ex.: Gerente, Fiscal da obra',
    )

    class Meta:
        verbose_name = 'E-mail para envio do diário'
        verbose_name_plural = 'E-mails para envio do diário'
        unique_together = [['project', 'email']]
        ordering = ['email']

    def __str__(self):
        return f"{self.email} ({self.project.code})"


class ProjectOwner(models.Model):
    """
    Dono da obra (cliente): usuário real com acesso restrito.
    Só visualiza diários das obras das quais é dono e pode comentar na janela de 24h.
    """
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='owners',
        verbose_name='Obra',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_projects',
        verbose_name='Dono (usuário)',
    )

    class Meta:
        verbose_name = 'Dono da Obra'
        verbose_name_plural = 'Donos da Obra'
        unique_together = [['project', 'user']]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['project']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} → {self.project.code}"


class ProjectDiaryApprover(models.Model):
    """
    Usuários que podem aprovar o RDO de uma obra antes do envio ao cliente.
    """
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='rdo_approvers',
        verbose_name='Obra',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='rdo_project_approvals',
        verbose_name='Aprovador',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Ativo',
        help_text='Permite desativar temporariamente sem remover o vínculo.',
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Ordem',
        help_text='Apenas para ordenação visual no painel.',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Data de Atualização')

    class Meta:
        verbose_name = 'Aprovador de RDO por obra'
        verbose_name_plural = 'Aprovadores de RDO por obra'
        unique_together = [['project', 'user']]
        ordering = ['project', 'order', 'user__first_name', 'user__username']
        indexes = [
            models.Index(fields=['project', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.project.code} → {self.user.get_full_name() or self.user.username}"


class ActivityManager(MP_NodeManager):
    """Manager customizado para queries otimizadas de Activity."""
    pass


class Activity(MP_Node):
    """
    Modelo de Atividade na Estrutura Analítica de Projetos (EAP).
    
    Herda de MP_Node (Materialized Path) do django-treebeard para suportar
    hierarquias profundas com leituras eficientes sem recursão excessiva.
    
    Suporta milhares de atividades com desempenho otimizado através do
    caminho materializado armazenado no campo 'path'.
    """
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='activities',
        verbose_name='Projeto',
        help_text='Projeto ao qual esta atividade pertence'
    )
    name = models.CharField(
        max_length=255,
        verbose_name='Nome da Atividade',
        help_text='Nome descritivo da atividade'
    )
    code = models.CharField(
        max_length=100,
        verbose_name='Código da Atividade',
        help_text='Código hierárquico da atividade (ex: "1.2.1")'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Descrição',
        help_text='Descrição detalhada da atividade'
    )
    planned_start = models.DateField(
        null=True,
        blank=True,
        verbose_name='Início Planejado',
        help_text='Data planejada de início da atividade'
    )
    planned_end = models.DateField(
        null=True,
        blank=True,
        verbose_name='Término Planejado',
        help_text='Data planejada de término da atividade'
    )
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        verbose_name='Peso',
        help_text='Peso da atividade para cálculo de progresso ponderado (0-100)'
    )
    status = models.CharField(
        max_length=2,
        choices=ActivityStatus.choices,
        default=ActivityStatus.NOT_STARTED,
        verbose_name='Status',
        help_text='Status atual da atividade'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Data de Atualização'
    )

    objects = ActivityManager()

    class Meta:
        verbose_name = 'Atividade'
        verbose_name_plural = 'Atividades'
        ordering = ['code']
        indexes = [
            models.Index(fields=['project', 'code']),
            models.Index(fields=['project', 'status']),
            # Índice GIST recomendado para PostgreSQL no campo 'path' do treebeard
            # será criado via migration customizada
        ]

    def __str__(self) -> str:
        return self.display_code_name

    @property
    def display_code(self) -> str:
        """Código não é exibido na aplicação (apenas persistido no BD)."""
        from core.utils.activity_display import activity_code_for_display

        return activity_code_for_display(self.code)

    @property
    def display_name(self) -> str:
        """Nome sem prefixo legado GEN- no texto, quando existir."""
        from core.utils.activity_display import activity_name_for_display

        return activity_name_for_display(self.name)

    @property
    def display_code_name(self) -> str:
        """Rótulo único para PDF/telas: somente o nome (código fica só no BD)."""
        return self.display_name

    def is_leaf(self) -> bool:
        """
        Verifica se a atividade é uma folha (não tem filhos).
        
        Nota: Os métodos get_children(), get_descendants() e get_ancestors()
        são herdados de MP_Node e estão disponíveis diretamente.
        O atributo numchild é fornecido pelo treebeard e indica o número de filhos.
        """
        return self.numchild == 0


class Labor(models.Model):
    """
    Modelo para representar recursos de mão de obra.
    
    Usado em ManyToMany com DailyWorkLog para registrar quais trabalhadores
    estiveram envolvidos em uma atividade específica.
    """
    name = models.CharField(
        max_length=255,
        verbose_name='Nome',
        help_text='Nome do trabalhador ou função'
    )
    role = models.CharField(
        max_length=3,
        choices=[
            ('AJ', 'Ajudante'),
            ('EL', 'Eletricista'),
            ('EN', 'Engenheiro'),
            ('ES', 'Estagiário'),
            ('GE', 'Gesseiro'),
            ('ME', 'Mestre de Obra'),
            ('PE', 'Pedreiro'),
            ('SE', 'Servente'),
            ('TE', 'Técnico em Edificações'),
            ('CA', 'Carpinteiro'),
            ('HI', 'Hidráulico'),
            ('AR', 'Armador'),
            ('OU', 'Outro'),
        ],
        default='OU',
        verbose_name='Função/Categoria',
        help_text='Categoria ou função do trabalhador'
    )
    role_custom = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Função Personalizada',
        help_text='Função personalizada (usado quando categoria é "Outro")'
    )
    labor_type = models.CharField(
        max_length=1,
        choices=[
            ('I', 'Indireto (LPLAN)'),
            ('D', 'Direto'),
            ('T', 'Terceiros'),
        ],
        default='D',
        verbose_name='Tipo de Efetivo',
        help_text='Tipo de efetivo: Indireto (LPLAN), Direto ou Terceiros'
    )
    company = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Empresa (Terceiros)',
        help_text='Nome da empresa terceirizada (se aplicável)'
    )
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Taxa Horária',
        help_text='Taxa horária de remuneração (opcional)'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Ativo'
    )

    class Meta:
        verbose_name = 'Mão de Obra'
        verbose_name_plural = 'Mão de Obra'
        ordering = ['name']

    def __str__(self) -> str:
        role_display = self.get_role_display()
        if self.role == 'OU' and self.role_custom:
            role_display = self.role_custom
        return f"{self.name} ({role_display})"


class LaborCategory(models.Model):
    """
    Categoria de mão de obra para o diário (Indireta, Direta, Terceirizada).
    Usado para organizar a seleção por blocos na tela de preenchimento.
    """
    slug = models.SlugField(max_length=32, unique=True, verbose_name='Identificador')
    name = models.CharField(max_length=100, verbose_name='Nome')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Ordem de exibição')

    class Meta:
        verbose_name = 'Categoria de Mão de Obra'
        verbose_name_plural = 'Categorias de Mão de Obra'
        ordering = ['order', 'pk']

    def __str__(self):
        return self.name


class LaborCargo(models.Model):
    """
    Cargo/função padrão dentro de uma categoria (ex: Pedreiro, Engenheiro Civil).
    Terceirizada pode ter cargos como Topógrafo, Encarregado, Operador de Máquina.
    """
    category = models.ForeignKey(
        LaborCategory,
        on_delete=models.CASCADE,
        related_name='cargos',
        verbose_name='Categoria'
    )
    name = models.CharField(max_length=120, verbose_name='Nome do cargo')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Ordem de exibição')

    class Meta:
        verbose_name = 'Cargo (Mão de Obra)'
        verbose_name_plural = 'Cargos (Mão de Obra)'
        ordering = ['category', 'order', 'name']
        unique_together = [['category', 'name']]

    def __str__(self):
        return self.name


class DiaryLaborEntry(models.Model):
    """
    Registro de presença por cargo no dia (quantidade de profissionais).
    Para terceirizada, company identifica a empresa.
    """
    diary = models.ForeignKey(
        'ConstructionDiary',
        on_delete=models.CASCADE,
        related_name='labor_entries',
        verbose_name='Diário'
    )
    cargo = models.ForeignKey(
        LaborCargo,
        on_delete=models.CASCADE,
        related_name='diary_entries',
        verbose_name='Cargo'
    )
    quantity = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name='Quantidade'
    )
    company = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Empresa (Terceirizada)',
        help_text='Nome da empresa terceirizada; preencher apenas para mão de obra terceirizada'
    )

    class Meta:
        verbose_name = 'Registro de Mão de Obra no Diário'
        verbose_name_plural = 'Registros de Mão de Obra no Diário'
        ordering = ['diary', 'company', 'cargo']

    def __str__(self):
        if self.company:
            return f"{self.diary} | {self.company} – {self.cargo.name}: {self.quantity}"
        return f"{self.diary} | {self.cargo.name}: {self.quantity}"


class EquipmentCategory(models.Model):
    """Categoria de equipamentos para seleção no diário (ex.: Máquinas, Canteiro)."""
    slug = models.SlugField(max_length=32, unique=True, verbose_name='Identificador')
    name = models.CharField(max_length=100, verbose_name='Nome')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Ordem de exibição')

    class Meta:
        verbose_name = 'Categoria de Equipamento'
        verbose_name_plural = 'Categorias de Equipamento'
        ordering = ['order', 'pk']

    def __str__(self):
        return self.name


class StandardEquipment(models.Model):
    """Equipamento padrão por categoria (lista pré-definida para o diário)."""
    category = models.ForeignKey(
        EquipmentCategory,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Categoria'
    )
    name = models.CharField(max_length=120, verbose_name='Nome')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Ordem de exibição')

    class Meta:
        verbose_name = 'Equipamento Padrão'
        verbose_name_plural = 'Equipamentos Padrão'
        ordering = ['category', 'order', 'name']
        unique_together = [['category', 'name']]

    def __str__(self):
        return self.name


class Equipment(models.Model):
    """
    Modelo para representar recursos de equipamentos.
    
    Usado em ManyToMany com DailyWorkLog para registrar quais equipamentos
    foram utilizados em uma atividade específica.
    """
    name = models.CharField(
        max_length=255,
        verbose_name='Nome',
        help_text='Nome ou identificação do equipamento'
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Código',
        help_text='Código único do equipamento'
    )
    equipment_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Tipo',
        help_text='Tipo de equipamento (ex: Escavadeira, Betoneira)'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Ativo'
    )

    class Meta:
        verbose_name = 'Equipamento'
        verbose_name_plural = 'Equipamentos'
        ordering = ['code']
        indexes = [
            models.Index(fields=['code']),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class ConstructionDiary(models.Model):
    """
    Modelo principal do Diário de Obra.
    
    Representa um registro diário de atividades e progresso em um projeto.
    Status: SALVAMENTO_PARCIAL (rascunho) ou APROVADO (Salvar diário). Uma vez APROVADO, o registro torna-se imutável.
    """
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='diaries',
        verbose_name='Projeto',
        help_text='Projeto ao qual este diário pertence'
    )
    date = models.DateField(
        verbose_name='Data',
        help_text='Data do registro do diário'
    )
    report_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Número do Relatório',
        help_text='Número sequencial do relatório dentro do projeto'
    )
    status = models.CharField(
        max_length=2,
        choices=DiaryStatus.choices,
        default=DiaryStatus.PREENCHENDO,
        verbose_name='Status',
        help_text='Status do relatório (Preenchendo por padrão)'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_diaries',
        verbose_name='Criado por',
        help_text='Engenheiro de campo que criou o diário'
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='reviewed_diaries',
        null=True,
        blank=True,
        verbose_name='Revisado por',
        help_text='Gerente que revisou o diário'
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data de Aprovação',
        help_text='Data e hora em que o diário foi aprovado'
    )
    sent_to_owner_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Enviado ao dono em',
        help_text='Data/hora em que o diário foi enviado ao dono da obra (início da janela de 24h para comentários)'
    )
    inspection_responsible = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Responsável pela Inspeção Diária',
        help_text='Nome do responsável pela inspeção diária'
    )
    production_responsible = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Responsável pela Produção',
        help_text='Nome do responsável pela produção'
    )
    weather_conditions = models.TextField(
        blank=True,
        verbose_name='Condições Climáticas',
        help_text='Descrição das condições climáticas do dia'
    )
    # Clima Manhã - Melhorado
    weather_morning_condition = models.CharField(
        max_length=1,
        choices=[
            ('', 'Não informado'),
            ('B', 'Bom'),
            ('R', 'Ruim'),
        ],
        blank=True,
        default='',
        verbose_name='Clima Manhã - Condição',
        help_text='Condição climática da manhã (Bom/Ruim)'
    )
    weather_morning_workable = models.CharField(
        max_length=1,
        choices=[
            ('', 'Não informado'),
            ('T', 'Trabalhável'),
            ('N', 'Não Trabalhável'),
        ],
        blank=True,
        default='',
        verbose_name='Clima Manhã - Trabalhável',
        help_text='Se as condições da manhã permitem trabalho'
    )
    # Clima Tarde - Melhorado
    weather_afternoon_condition = models.CharField(
        max_length=1,
        choices=[
            ('', 'Não informado'),
            ('B', 'Bom'),
            ('R', 'Ruim'),
        ],
        blank=True,
        default='',
        verbose_name='Clima Tarde - Condição',
        help_text='Condição climática da tarde (Bom/Ruim)'
    )
    weather_afternoon_workable = models.CharField(
        max_length=1,
        choices=[
            ('', 'Não informado'),
            ('T', 'Trabalhável'),
            ('N', 'Não Trabalhável'),
        ],
        blank=True,
        default='',
        verbose_name='Clima Tarde - Trabalhável',
        help_text='Se as condições da tarde permitem trabalho'
    )
    # Clima Noite - Novo
    weather_night_enabled = models.BooleanField(
        default=False,
        verbose_name='Registrar Clima Noite',
        help_text='Marque se deseja registrar condições climáticas da noite'
    )
    weather_night_type = models.CharField(
        max_length=2,
        choices=[
            ('', 'Não informado'),
            ('C', 'Claro'),
            ('N', 'Nublado'),
            ('CH', 'Chuvoso'),
        ],
        blank=True,
        default='',
        verbose_name='Clima Noite - Tipo',
        help_text='Tipo de clima na noite'
    )
    weather_night_workable = models.CharField(
        max_length=1,
        choices=[
            ('', 'Não informado'),
            ('P', 'Praticável'),
            ('I', 'Impraticável'),
        ],
        blank=True,
        default='',
        verbose_name='Clima Noite - Praticável',
        help_text='Se as condições da noite permitem trabalho'
    )
    # Índice Pluviométrico
    pluviometric_index = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Índice Pluviométrico (mm)',
        help_text='Índice pluviométrico do dia em milímetros (ex: 5.30)'
    )
    rain_occurrence = models.CharField(
        max_length=1,
        choices=[
            ('', 'Nenhuma'),
            ('F', 'Fraca'),
            ('M', 'Média'),
            ('S', 'Forte'),
        ],
        blank=True,
        default='',
        verbose_name='Ocorrência de Chuvas',
        help_text='Intensidade de chuva no dia'
    )
    rain_observations = models.TextField(
        blank=True,
        verbose_name='Observações sobre Chuvas',
        help_text='Observações sobre ocorrência de chuvas'
    )
    deliberations = models.TextField(
        blank=True,
        verbose_name='Deliberações',
        help_text='Deliberações e decisões tomadas no dia'
    )
    work_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Horas Trabalhadas',
        help_text='Horas efetivas de trabalho (ex: 8.00, 7.50)'
    )
    # Ocorrências - Separadas
    accidents = models.TextField(
        blank=True,
        verbose_name='Acidentes',
        help_text='Registro de acidentes ocorridos no dia'
    )
    stoppages = models.TextField(
        blank=True,
        verbose_name='Paralisações',
        help_text='Registro de paralisações, interrupções ou paradas no trabalho'
    )
    imminent_risks = models.TextField(
        blank=True,
        verbose_name='Riscos Eminentes',
        help_text='Registro de riscos eminentes identificados no dia'
    )
    incidents = models.TextField(
        blank=True,
        verbose_name='Outros Incidentes',
        help_text='Registro de outros incidentes ou eventos relevantes do dia'
    )
    # Atividades executadas (Fiscalizações, DDS)
    inspections = models.TextField(
        blank=True,
        verbose_name='Fiscalizações',
        help_text='Registro de fiscalizações realizadas no dia'
    )
    dds = models.TextField(
        blank=True,
        verbose_name='DDS (Discurso Diário de Segurança)',
        help_text='Registro do Discurso Diário de Segurança realizado'
    )
    # Mantido para compatibilidade (deprecated)
    interruptions = models.TextField(
        blank=True,
        verbose_name='Interrupções/Paradas (Deprecated)',
        help_text='DEPRECATED: Use o campo Paralisações. Mantido para compatibilidade.'
    )
    general_notes = models.TextField(
        blank=True,
        verbose_name='Observações Gerais',
        help_text='Observações gerais sobre o dia de trabalho'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Data de Atualização'
    )
    # Pedido de correção em relatório já aprovado (fluxo: solicitar → staff libera → editar até guardar)
    edit_requested_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Pedido de correção em',
    )
    edit_requested_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='diary_edit_requests_made',
        verbose_name='Pedido de correção por',
    )
    edit_request_note = models.TextField(
        blank=True,
        verbose_name='Motivo / observação do pedido',
    )
    provisional_edit_granted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Edição provisória liberada em',
    )
    provisional_edit_granted_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='diary_provisional_edits_granted',
        verbose_name='Liberação feita por',
    )

    class Meta:
        verbose_name = 'Diário de Obra'
        verbose_name_plural = 'Diários de Obra'
        ordering = ['-date', '-created_at']
        unique_together = [['project', 'date']]
        indexes = [
            models.Index(fields=['project', 'date']),
            models.Index(fields=['project', 'status']),
            models.Index(fields=['status', '-date']),
        ]

    def __str__(self) -> str:
        return f"Diário {self.project.code} - {self.date}"

    def is_approved(self) -> bool:
        """Verifica se o diário está aprovado (imutável)."""
        return self.status == DiaryStatus.APROVADO

    def is_waiting_manager_approval(self) -> bool:
        """True quando o diário aguarda decisão de aprovador do RDO."""
        return self.status == DiaryStatus.AGUARDANDO_APROVACAO_GESTOR

    def requires_manager_approval(self) -> bool:
        """True quando a obra tem ao menos um aprovador ativo de RDO."""
        return self.project.rdo_approvers.filter(is_active=True).exists()

    def save(self, *args, **kwargs):
        """
        Sobrescreve save() para gerar automaticamente o número do relatório.
        
        O número é sequencial dentro do projeto, baseado no último relatório criado.
        Usa select_for_update dentro de uma transação atômica para evitar race conditions
        quando múltiplos usuários criam relatórios simultaneamente.
        
        O select_for_update() bloqueia as linhas selecionadas até o fim da transação,
        garantindo que apenas um processo por vez possa ler e incrementar o número.
        Se já estiver dentro de uma transação, transaction.atomic() cria um savepoint.
        """
        from django.db import transaction
        
        if not self.pk and not self.report_number:
            # Usa transação atômica com select_for_update para evitar race conditions
            # O select_for_update bloqueia as linhas até o fim da transação
            with transaction.atomic():
                # Lock nas linhas do projeto para garantir exclusividade
                # nowait=False faz com que espere se outra transação já tiver o lock
                last_diary = ConstructionDiary.objects.filter(
                    project=self.project
                ).select_for_update(nowait=False).order_by('-report_number').first()
                
                if last_diary and last_diary.report_number:
                    self.report_number = last_diary.report_number + 1
                else:
                    self.report_number = 1
        
        super().save(*args, **kwargs)
    
    def can_be_edited_by(self, user: User) -> bool:
        """
        Verifica se o diário pode ser editado por um usuário.
        Quem pode editar é definido pela view (acesso à obra); aqui só checamos status.
        - Ninguém edita quando status = APROVADO, exceto se houver liberação provisória
          (provisional_edit_granted_at) após pedido aprovado pelo staff.
        - Enquanto não estiver APROVADO (inclusive AGUARDANDO_APROVACAO_GESTOR):
          editável conforme permissão na obra.
        """
        if getattr(self, 'provisional_edit_granted_at', None):
            return True
        if self.is_approved():
            return False
        if self.status in (
            DiaryStatus.PREENCHENDO,
            DiaryStatus.SALVAMENTO_PARCIAL,
            DiaryStatus.AGUARDANDO_APROVACAO_GESTOR,
            DiaryStatus.REPROVADO_GESTOR,
        ):
            return True
        return False


class DiaryApprovalHistory(models.Model):
    """
    Histórico de decisões de aprovação do RDO (aprovar/reprovar por gestor).
    """
    DECISAO_APROVAR = 'AP'
    DECISAO_REPROVAR = 'RP'
    DECISAO_CHOICES = [
        (DECISAO_APROVAR, 'Aprovado'),
        (DECISAO_REPROVAR, 'Reprovado'),
    ]

    diary = models.ForeignKey(
        'ConstructionDiary',
        on_delete=models.CASCADE,
        related_name='approval_history',
        verbose_name='Diário',
    )
    decided_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='diary_approval_decisions',
        verbose_name='Decidido por',
    )
    decision = models.CharField(
        max_length=2,
        choices=DECISAO_CHOICES,
        verbose_name='Decisão',
    )
    comment = models.TextField(
        blank=True,
        verbose_name='Comentário',
        help_text='Justificativa opcional para aprovar e obrigatória para reprovar.',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Data da decisão')

    class Meta:
        verbose_name = 'Histórico de aprovação do RDO'
        verbose_name_plural = 'Histórico de aprovação do RDO'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['diary', '-created_at']),
            models.Index(fields=['decision', '-created_at']),
        ]

    def __str__(self):
        decisao = self.get_decision_display()
        return f"RDO {self.diary_id} - {decisao} ({self.created_at})"


class DiaryCorrectionRequestLog(models.Model):
    """
    Histórico de pedidos de correção em relatório já aprovado (solicitar → liberar → guardar).
    Mantém registo após liberação e após o utilizador guardar (closed_at).
    """
    diary = models.ForeignKey(
        'ConstructionDiary',
        on_delete=models.CASCADE,
        related_name='correction_request_logs',
        verbose_name='Diário',
    )
    requested_at = models.DateTimeField(verbose_name='Pedido em')
    requested_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name='Pedido por',
    )
    note = models.TextField(blank=True, verbose_name='Justificativa')
    granted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Liberação em',
    )
    granted_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name='Liberação por',
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Encerrado em',
        help_text='Quando o utilizador guardou após a edição provisória.',
    )

    class Meta:
        verbose_name = 'Pedido de correção (histórico)'
        verbose_name_plural = 'Pedidos de correção (histórico)'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['-requested_at']),
            models.Index(fields=['diary', '-requested_at']),
        ]

    def __str__(self) -> str:
        return f'Correção diário {self.diary_id} @ {self.requested_at}'


class DiaryComment(models.Model):
    """
    Comentário do dono da obra (ou da LPLAN) no diário.
    Vinculado ao User que criou e ao ConstructionDiary.
    Janela de 24h após sent_to_owner_at para novos comentários.
    """
    diary = models.ForeignKey(
        ConstructionDiary,
        on_delete=models.CASCADE,
        related_name='owner_comments',
        verbose_name='Diário',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diary_comments',
        verbose_name='Autor',
    )
    text = models.TextField(verbose_name='Comentário')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Data')

    class Meta:
        verbose_name = 'Comentário no diário (cliente/LPLAN)'
        verbose_name_plural = 'Comentários no diário'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['diary']),
        ]

    def __str__(self):
        autor = getattr(self.author, 'username', None) or 'Usuário removido'
        return f"{self.diary} — {autor} ({self.created_at})"


class DiaryEditLog(models.Model):
    """
    Modelo para registrar histórico de edições do Diário de Obra.
    """
    diary = models.ForeignKey(
        ConstructionDiary,
        on_delete=models.CASCADE,
        related_name='edit_logs',
        verbose_name='Diário'
    )
    edited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diary_edits',
        verbose_name='Editado por'
    )
    edited_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data da Edição'
    )
    field_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Campo Alterado',
        help_text='Nome do campo que foi alterado (opcional)'
    )
    old_value = models.TextField(
        blank=True,
        verbose_name='Valor Anterior',
        help_text='Valor anterior do campo (opcional)'
    )
    new_value = models.TextField(
        blank=True,
        verbose_name='Novo Valor',
        help_text='Novo valor do campo (opcional)'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Observações',
        help_text='Observações sobre a edição'
    )

    class Meta:
        verbose_name = 'Log de Edição'
        verbose_name_plural = 'Logs de Edição'
        ordering = ['-edited_at']
        indexes = [
            models.Index(fields=['diary', '-edited_at']),
        ]

    def __str__(self) -> str:
        editado = self.edited_by.username if self.edited_by else 'Usuário removido'
        return f"Edição de {self.diary} por {editado} em {self.edited_at}"


class DiaryView(models.Model):
    """
    Modelo para registrar visualizações do Diário de Obra.
    """
    diary = models.ForeignKey(
        ConstructionDiary,
        on_delete=models.CASCADE,
        related_name='views',
        verbose_name='Diário'
    )
    viewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diary_views',
        verbose_name='Visualizado por'
    )
    viewed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data da Visualização'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='Endereço IP'
    )

    class Meta:
        verbose_name = 'Visualização'
        verbose_name_plural = 'Visualizações'
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['diary', '-viewed_at']),
        ]
        unique_together = [['diary', 'viewed_by', 'viewed_at']]

    def __str__(self) -> str:
        visualizado = self.viewed_by.username if self.viewed_by else 'Usuário removido'
        return f"Visualização de {self.diary} por {visualizado} em {self.viewed_at}"


class DiarySignature(models.Model):
    """
    Modelo para armazenar assinaturas manuais do Diário de Obra.
    """
    diary = models.ForeignKey(
        ConstructionDiary,
        on_delete=models.CASCADE,
        related_name='signatures',
        verbose_name='Diário'
    )
    signer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diary_signatures',
        verbose_name='Assinante'
    )
    signature_type = models.CharField(
        max_length=50,
        choices=[
            ('inspection', 'Responsável pela Inspeção'),
            ('production', 'Responsável pela Produção'),
            ('reviewer', 'Revisor'),
            ('approver', 'Aprovador'),
        ],
        verbose_name='Tipo de Assinatura'
    )
    signature_data = models.TextField(
        verbose_name='Dados da Assinatura',
        help_text='Dados da assinatura em formato base64 (canvas)'
    )
    signed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data da Assinatura'
    )

    class Meta:
        verbose_name = 'Assinatura'
        verbose_name_plural = 'Assinaturas'
        ordering = ['-signed_at']
        indexes = [
            models.Index(fields=['diary', 'signature_type']),
        ]

    def __str__(self) -> str:
        assinante = self.signer.username if self.signer else 'Usuário removido'
        return f"Assinatura de {assinante} em {self.diary} ({self.get_signature_type_display()})"


class DiaryImage(models.Model):
    """
    Modelo para imagens associadas ao Diário de Obra.
    
    Implementa "ocultação suave" (soft hiding) através do campo
    is_approved_for_report. Isso permite que o revisor "oculte" imagens
    do PDF sem excluí-las do banco, preservando evidência legal.
    
    As imagens são otimizadas automaticamente no método save() para
    geração eficiente de PDF (redimensionamento, conversão JPEG, remoção EXIF).
    """
    diary = models.ForeignKey(
        ConstructionDiary,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Diário',
        help_text='Diário de obra ao qual esta imagem pertence'
    )
    image = models.ImageField(
        upload_to='diary_images/%Y/%m/%d/',
        verbose_name='Imagem',
        help_text='Arquivo de imagem original (alta resolução)'
    )
    pdf_optimized = models.ImageField(
        upload_to='diary_images/pdf_optimized/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name='Imagem Otimizada para PDF',
        help_text='Versão otimizada da imagem para geração de PDF (max 800px, JPEG, sem EXIF)'
    )
    caption = models.CharField(
        max_length=500,
        verbose_name='Legenda',
        help_text='Legenda descritiva da foto (obrigatório, ex: "Bloco C, serviço tal")'
    )
    is_approved_for_report = models.BooleanField(
        default=True,
        verbose_name='Aprovada para Relatório',
        help_text='Se False, a imagem não será incluída no PDF mas permanece no banco (preservação de evidência)'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Upload'
    )

    class Meta:
        verbose_name = 'Imagem do Diário'
        verbose_name_plural = 'Imagens do Diário'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['diary', 'is_approved_for_report']),
        ]

    def __str__(self) -> str:
        return f"Imagem {self.diary} - {self.caption[:50] if self.caption else 'Sem legenda'}"

    def save(self, *args, **kwargs):
        """
        Sobrescreve save() para gerar versão otimizada da imagem.
        
        A otimização é feita automaticamente usando Pillow para:
        - Redimensionar para max-width 800px
        - Converter para JPEG (Qualidade 80%, RGB)
        - Remover dados EXIF
        
        A versão otimizada é salva no campo pdf_optimized.
        """
        # Sanitiza o nome preservando diretórios relativos (ex.: diary_images/2026/03/...)
        # para evitar quebrar referências existentes ao remover acidentalmente o upload_to.
        if self.image and getattr(self.image, 'name', None):
            from core.utils.file_validators import sanitize_filename
            normalized_name = str(self.image.name).replace('\\', '/')
            if '/' in normalized_name:
                folder, filename = normalized_name.rsplit('/', 1)
                sanitized_filename = sanitize_filename(filename)
                self.image.name = f"{folder}/{sanitized_filename}" if folder else sanitized_filename
            else:
                self.image.name = sanitize_filename(normalized_name)
        # Salva primeiro para garantir que o arquivo existe
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Otimiza imagem se foi criada/atualizada e existe arquivo
        if self.image and self.image.name:
            try:
                # Importação lazy do ImageOptimizer (Pillow pode não estar disponível)
                from core.utils.pdf_generator import ImageOptimizer
                
                # Verifica se já existe versão otimizada e se a imagem original mudou
                if is_new or not self.pdf_optimized or not os.path.exists(self.pdf_optimized.path):
                    # Obtém caminho da imagem original
                    original_path = self.image.path
                    
                    if os.path.exists(original_path):
                        # Otimiza e salva no campo pdf_optimized
                        optimized_path = ImageOptimizer.optimize_image_for_pdf(original_path)
                        
                        if optimized_path and os.path.exists(optimized_path):
                            with open(optimized_path, 'rb') as f:
                                from django.core.files.base import ContentFile
                                self.pdf_optimized.save(
                                    os.path.basename(optimized_path),
                                    ContentFile(f.read()),
                                    save=True
                                )
            except (ImportError, OSError) as e:
                # Log do erro mas não interrompe o save
                # Em produção, usar logging adequado
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Erro ao otimizar imagem {self.image.name}: {e}. A otimização será pulada.")
            except Exception as e:
                # Log do erro mas não interrompe o save
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Erro ao otimizar imagem {self.image.name}: {e}")


class DailyWorkLog(models.Model):
    """
    Registro transacional de progresso diário de uma atividade específica.
    
    Vincula uma Activity a um ConstructionDiary, registrando:
    - Porcentagem executada no dia
    - Snapshot do progresso acumulado
    - Notas específicas
    - Recursos utilizados (Labor e Equipment via ManyToMany)
    
    Este modelo é usado para calcular o rollup de progresso na hierarquia EAP
    através do serviço calculate_rollup_progress().
    """
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name='work_logs',
        verbose_name='Atividade',
        help_text='Atividade da EAP relacionada a este registro'
    )
    diary = models.ForeignKey(
        ConstructionDiary,
        on_delete=models.CASCADE,
        related_name='work_logs',
        verbose_name='Diário',
        help_text='Diário de obra ao qual este registro pertence'
    )
    percentage_executed_today = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        verbose_name='Porcentagem Executada Hoje',
        help_text='Porcentagem da atividade executada neste dia específico (0-100)'
    )
    accumulated_progress_snapshot = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        verbose_name='Progresso Acumulado (Snapshot)',
        help_text='Progresso acumulado total da atividade no momento deste registro'
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Local',
        help_text='Local onde a atividade foi realizada (ex: Bloco A, Andar 2, Sala 101)'
    )
    work_stage = models.CharField(
        max_length=2,
        choices=[
            ('IN', 'Iniciada'),
            ('AN', 'Em andamento'),
            ('TE', 'Finalizada'),
        ],
        default='AN',
        blank=True,
        verbose_name='Status',
        help_text='Estágio da atividade no dia'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Notas/Descrição',
        help_text='Descrição detalhada do que foi feito nesta atividade'
    )
    resources_labor = models.ManyToManyField(
        Labor,
        blank=True,
        related_name='work_logs',
        verbose_name='Mão de Obra',
        help_text='Trabalhadores envolvidos nesta atividade'
    )
    resources_equipment = models.ManyToManyField(
        Equipment,
        blank=True,
        related_name='work_logs',
        through='DailyWorkLogEquipment',
        through_fields=('work_log', 'equipment'),
        verbose_name='Equipamentos',
        help_text='Equipamentos utilizados nesta atividade'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Data de Atualização'
    )

    class Meta:
        verbose_name = 'Registro de Trabalho Diário'
        verbose_name_plural = 'Registros de Trabalho Diário'
        ordering = ['-created_at']
        unique_together = [['activity', 'diary']]
        indexes = [
            models.Index(fields=['activity', 'diary']),
            models.Index(fields=['diary', '-created_at']),
        ]

    def clean(self):
        """Valida que a atividade pertence ao projeto do diário."""
        super().clean()
        if self.activity_id and self.diary_id:
            # Garantir que a atividade pertence ao mesmo projeto do diário
            if self.activity.project_id != self.diary.project_id:
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'activity': 'A atividade selecionada não pertence ao projeto deste diário.'
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.activity.display_code_name} · {self.diary.date} ({self.percentage_executed_today}%)"


class DailyWorkLogEquipment(models.Model):
    """
    Tabela through para DailyWorkLog <-> Equipment com quantidade.
    Permite registrar quantas unidades de cada equipamento foram usadas no work log.
    """
    work_log = models.ForeignKey(
        DailyWorkLog,
        on_delete=models.CASCADE,
        related_name='equipment_through',
        verbose_name='Registro de trabalho',
    )
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name='work_log_through',
        verbose_name='Equipamento',
    )
    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name='Quantidade',
        help_text='Número de unidades utilizadas',
    )

    class Meta:
        verbose_name = 'Equipamento do registro de trabalho'
        verbose_name_plural = 'Equipamentos do registro de trabalho'
        unique_together = [['work_log', 'equipment']]

    def __str__(self):
        return f"{self.work_log_id} - {self.equipment.name} x{self.quantity}"


class DiaryVideo(models.Model):
    """
    Modelo para vídeos associados ao Diário de Obra.
    """
    diary = models.ForeignKey(
        ConstructionDiary,
        on_delete=models.CASCADE,
        related_name='videos',
        verbose_name='Diário',
        help_text='Diário de obra ao qual este vídeo pertence'
    )
    video = models.FileField(
        upload_to='diary_videos/%Y/%m/%d/',
        verbose_name='Vídeo',
        help_text='Arquivo de vídeo (MP4, AVI, MOV, etc.)'
    )
    thumbnail = models.ImageField(
        upload_to='diary_videos/thumbnails/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name='Miniatura',
        help_text='Miniatura do vídeo (gerada automaticamente)'
    )
    caption = models.CharField(
        max_length=500,
        verbose_name='Legenda',
        help_text='Legenda descritiva do vídeo (obrigatório)'
    )
    duration = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Duração (segundos)',
        help_text='Duração do vídeo em segundos'
    )
    is_approved_for_report = models.BooleanField(
        default=True,
        verbose_name='Aprovado para Relatório',
        help_text='Se False, o vídeo não será incluído no relatório mas permanece no banco'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Upload'
    )

    class Meta:
        verbose_name = 'Vídeo do Diário'
        verbose_name_plural = 'Vídeos do Diário'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['diary', 'is_approved_for_report']),
        ]

    def __str__(self) -> str:
        return f"Vídeo {self.diary} - {self.caption[:50] if self.caption else 'Sem legenda'}"

    # Nome do arquivo é sanitizado no upload (validate_video_file) antes de criar o registro.
    # Não alterar .name no save() para não quebrar vídeos já gravados no disco com outro nome (404).


class DiaryAttachment(models.Model):
    """
    Modelo para anexos/documentos associados ao Diário de Obra.
    
    Permite anexar documentos diversos (PDF, DOC, XLS, etc.) além de imagens.
    """
    diary = models.ForeignKey(
        ConstructionDiary,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='Diário',
        help_text='Diário de obra ao qual este anexo pertence'
    )
    file = models.FileField(
        upload_to='diary_attachments/%Y/%m/%d/',
        verbose_name='Arquivo',
        help_text='Arquivo anexo (PDF, DOC, XLS, etc.)'
    )
    name = models.CharField(
        max_length=255,
        verbose_name='Nome do Arquivo',
        help_text='Nome descritivo do arquivo'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Descrição',
        help_text='Descrição do conteúdo do anexo'
    )
    file_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Tipo de Arquivo',
        help_text='Tipo MIME do arquivo (ex: application/pdf)'
    )
    file_size = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Tamanho (bytes)',
        help_text='Tamanho do arquivo em bytes'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Upload'
    )

    class Meta:
        verbose_name = 'Anexo do Diário'
        verbose_name_plural = 'Anexos do Diário'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['diary', '-uploaded_at']),
        ]

    def __str__(self) -> str:
        return f"Anexo {self.diary} - {self.name}"

    def save(self, *args, **kwargs):
        """Atualiza file_type e file_size automaticamente."""
        if self.file and self.file.name:
            # Sanitiza nome do arquivo para evitar 404/500 com espaços ou caracteres especiais
            from core.utils.file_validators import sanitize_filename
            self.file.name = sanitize_filename(self.file.name)
            # Detecta tipo MIME
            import mimetypes
            mime_type, _ = mimetypes.guess_type(self.file.name)
            if mime_type:
                self.file_type = mime_type
            
            # Obtém tamanho do arquivo
            try:
                if hasattr(self.file, 'size'):
                    self.file_size = self.file.size
                elif hasattr(self.file, 'file') and hasattr(self.file.file, 'size'):
                    self.file_size = self.file.file.size
            except (AttributeError, OSError):
                pass
        
        super().save(*args, **kwargs)


class Notification(models.Model):
    """
    Modelo para notificações do sistema.
    
    Usado para alertar usuários sobre eventos importantes como:
    - Relatórios pendentes de aprovação
    - Diários que precisam ser revisados
    - Atividades atrasadas
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Usuário',
        help_text='Usuário que receberá a notificação'
    )
    notification_type = models.CharField(
        max_length=50,
        choices=[
            ('diary_pending', 'Relatório Pendente de Aprovação'),
            ('diary_review', 'Relatório Requer Revisão'),
            ('activity_delayed', 'Atividade Atrasada'),
            ('system', 'Notificação do Sistema'),
        ],
        verbose_name='Tipo de Notificação'
    )
    title = models.CharField(
        max_length=255,
        verbose_name='Título',
        help_text='Título da notificação'
    )
    message = models.TextField(
        verbose_name='Mensagem',
        help_text='Mensagem detalhada da notificação'
    )
    related_diary = models.ForeignKey(
        ConstructionDiary,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name='Diário Relacionado',
        help_text='Diário relacionado à notificação (se aplicável)'
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name='Lida',
        help_text='Indica se a notificação foi lida pelo usuário'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )

    class Meta:
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'
        ordering = ['-created_at', '-is_read']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.title} - {self.user.username}"


class SupportTicket(models.Model):
    """Chamado de suporte interno do sistema."""

    class Status(models.TextChoices):
        OPEN = 'OP', 'Novo'
        TRIAGE = 'TR', 'Triagem'
        IN_PROGRESS = 'IP', 'Em atendimento'
        WAITING_USER = 'WU', 'Aguardando usuário'
        WAITING_DEPLOY = 'WD', 'Aguardando deploy'
        RESOLVED = 'RS', 'Resolvido'
        CLOSED = 'CL', 'Fechado'
        REOPENED = 'RO', 'Reaberto'

    class Severity(models.TextChoices):
        BLOCKER = 'BL', 'Bloqueante'
        IMPORTANT = 'IM', 'Importante'
        MEDIUM = 'MD', 'Médio'
        LOW = 'LW', 'Baixo/Dúvida'

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='support_tickets_created',
        verbose_name='Criado por',
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_tickets_assigned',
        verbose_name='Responsável',
    )
    category = models.CharField(max_length=80, verbose_name='Categoria')
    severity = models.CharField(max_length=2, choices=Severity.choices, default=Severity.MEDIUM, verbose_name='Severidade')
    title = models.CharField(max_length=120, verbose_name='Título')
    description = models.TextField(verbose_name='Descrição')
    status = models.CharField(max_length=2, choices=Status.choices, default=Status.OPEN, verbose_name='Status')
    related_project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_tickets',
        verbose_name='Obra relacionada',
    )
    screen_path = models.CharField(max_length=255, blank=True, verbose_name='Tela de origem')
    browser_info = models.CharField(max_length=255, blank=True, verbose_name='Navegador/cliente')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Data de Atualização')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='Data de Resolução')
    first_response_due_at = models.DateTimeField(null=True, blank=True, verbose_name='Prazo 1ª resposta')
    resolution_due_at = models.DateTimeField(null=True, blank=True, verbose_name='Prazo de resolução')
    first_response_at = models.DateTimeField(null=True, blank=True, verbose_name='Data da 1ª resposta')

    class Meta:
        verbose_name = 'Chamado de suporte'
        verbose_name_plural = 'Chamados de suporte'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['created_by', '-created_at']),
            models.Index(fields=['assigned_to', '-created_at']),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} - {self.title}"

    def is_first_response_overdue(self):
        return bool(self.first_response_due_at and not self.first_response_at and timezone.now() > self.first_response_due_at)

    def is_resolution_overdue(self):
        return bool(
            self.resolution_due_at
            and self.status not in {self.Status.RESOLVED, self.Status.CLOSED}
            and timezone.now() > self.resolution_due_at
        )

    def can_be_reopened_by_user(self, user):
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        if self.created_by_id != user.id:
            return False
        if self.status not in {self.Status.RESOLVED, self.Status.CLOSED}:
            return False
        if not self.resolved_at:
            return False
        return timezone.now() <= (self.resolved_at + timedelta(days=7))


class SupportTicketMessage(models.Model):
    """Mensagens de conversa dentro do chamado de suporte."""

    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Chamado',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_ticket_messages',
        verbose_name='Autor',
    )
    message = models.TextField(verbose_name='Mensagem')
    is_internal_note = models.BooleanField(
        default=False,
        verbose_name='Nota interna',
        help_text='Visível apenas para admins/superusers.',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')

    class Meta:
        verbose_name = 'Mensagem de chamado'
        verbose_name_plural = 'Mensagens de chamado'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['ticket', 'created_at']),
        ]

    def __str__(self) -> str:
        return f"Mensagem #{self.pk} - Ticket #{self.ticket_id}"


class SupportTicketAttachment(models.Model):
    """Anexos enviados no chamado de suporte."""

    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='Chamado',
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_ticket_attachments',
        verbose_name='Enviado por',
    )
    file = models.FileField(upload_to='support_tickets/%Y/%m/%d/', verbose_name='Arquivo')
    original_name = models.CharField(max_length=255, blank=True, verbose_name='Nome original')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Data de Upload')

    class Meta:
        verbose_name = 'Anexo de chamado'
        verbose_name_plural = 'Anexos de chamado'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['ticket', '-uploaded_at']),
        ]

    def __str__(self) -> str:
        return f"Anexo #{self.pk} - Ticket #{self.ticket_id}"


class OccurrenceTag(models.Model):
    """
    Modelo para tags/categorias de ocorrências.
    
    Permite categorizar ocorrências (ex: "Atraso", "Material", "Segurança", etc.)
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Nome da Tag',
        help_text='Nome da tag/categoria (ex: "Atraso", "Material", "Segurança")'
    )
    color = models.CharField(
        max_length=7,
        default='#3B82F6',
        verbose_name='Cor',
        help_text='Cor da tag em hexadecimal (ex: #3B82F6)'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Ativa',
        help_text='Indica se a tag está ativa e pode ser usada'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )

    class Meta:
        verbose_name = 'Tag de Ocorrência'
        verbose_name_plural = 'Tags de Ocorrências'
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'name']),
        ]

    def __str__(self) -> str:
        return self.name


class DiaryOccurrence(models.Model):
    """
    Modelo para ocorrências do Diário de Obra.
    
    Representa eventos, problemas ou situações específicas que ocorreram no dia,
    com suporte a tags para categorização.
    """
    diary = models.ForeignKey(
        ConstructionDiary,
        on_delete=models.CASCADE,
        related_name='occurrences',
        verbose_name='Diário',
        help_text='Diário de obra ao qual esta ocorrência pertence'
    )
    description = models.TextField(
        verbose_name='Descrição',
        help_text='Descrição detalhada da ocorrência'
    )
    tags = models.ManyToManyField(
        OccurrenceTag,
        blank=True,
        related_name='occurrences',
        verbose_name='Tags',
        help_text='Tags/categorias associadas a esta ocorrência'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_occurrences',
        verbose_name='Criado por',
        help_text='Usuário que registrou a ocorrência'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Data de Criação'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Data de Atualização'
    )

    class Meta:
        verbose_name = 'Ocorrência'
        verbose_name_plural = 'Ocorrências'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['diary', '-created_at']),
        ]

    def __str__(self) -> str:
        return f"Ocorrência em {self.diary.date} - {self.description[:50]}"
