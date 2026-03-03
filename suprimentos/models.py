from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from mapa_obras.models import Obra, LocalObra
from django.contrib.auth.models import User
from django.db.models import Sum


class Insumo(models.Model):
    """
    Catálogo de insumos - Importado do Sienge.
    
    Contém apenas dados básicos que vêm do CSV do Sienge:
    - Código do insumo
    - Descrição
    - Unidade
    
    A CATEGORIA é definida no ItemMapa (onde o insumo será aplicado),
    não aqui, porque o mesmo insumo pode ser usado em diferentes categorias
    (ex: Cimento pode ser usado em FUNDAÇÃO, ESTRUTURA, ALVENARIA).
    """
    codigo_sienge = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Código único do insumo no Sienge (ex: 5926)"
    )
    descricao = models.CharField(
        max_length=500,
        help_text="Descrição do insumo (vem do Sienge)"
    )
    unidade = models.CharField(
        max_length=20, 
        blank=True,
        default='',
        help_text="Unidade de medida (KG, M², UND, etc) - preencher manualmente"
    )
    
    # Controle
    ativo = models.BooleanField(default=True)
    eh_macroelemento = models.BooleanField(
        default=True,
        help_text="Marcar se é um macroelemento (grande volume/valor). Insumos pequenos e cimentos geralmente NÃO são macroelementos."
    )
    observacoes = models.TextField(blank=True, help_text="Observações internas")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def identificar_eh_macroelemento(self):
        """
        Identifica automaticamente se o insumo é um macroelemento baseado na descrição.
        Retorna True se for macroelemento, False se for insumo pequeno/cimento.
        
        Baseado em práticas de mapas de suprimentos em engenharia:
        - Macroelementos: estruturas grandes, sistemas completos, componentes principais
        - Não-macroelementos: insumos pequenos (parafusos, pregos, acessórios), cimentos, materiais básicos
        """
        desc_lower = (self.descricao or '').lower()
        
        # Palavras-chave que indicam insumos pequenos
        palavras_pequenas = [
            'parafuso', 'preg', 'arruela', 'porca', 'rebite', 'grampo',
            'clipe', 'bucha', 'tirante', 'abracadeira', 'cinta',
            'fita adesiva', 'fita isolante', 'fita dupla face', 'cola',
            'aditivo', 'impermeabilizante', 'selante', 'massa',
            'tinta', 'verniz', 'esmalte', 'primer',
            'cimento', 'argamassa', 'rejunte', 'cal',
            'areia', 'brita', 'pedra', 'seixo',
            'lixa', 'broca', 'disco', 'serra',
            'pincel', 'rolo', 'lona', 'papel',
        ]
        
        # Palavras-chave que indicam macroelementos (sobrescrevem as pequenas)
        palavras_macros = [
            'viga', 'pilar', 'laje', 'estrutura', 'concreto estrutural',
            'porta', 'janela', 'esquadria', 'ferragem estrutural',
            'telha', 'tijolo', 'bloco', 'alvenaria estrutural',
            'tubo', 'cano', 'conexão principal', 'conexão de grande diâmetro',
            'ar condicionado', 'split', 'equipamento', 'máquina',
            'elevador', 'gerador', 'transformador', 'painel elétrico',
            'piscina', 'sauna', 'spa', 'jacuzzi',
        ]
        
        # Verificar se é macroelemento explícito
        for palavra in palavras_macros:
            if palavra in desc_lower:
                return True
        
        # Verificar se é insumo pequeno
        for palavra in palavras_pequenas:
            if palavra in desc_lower:
                return False
        
        # Por padrão, se não identificar, assume que é macroelemento
        return True

    class Meta:
        ordering = ['descricao']
        verbose_name = 'Insumo'
        verbose_name_plural = 'Insumos'
        indexes = [
            models.Index(fields=['ativo']),
        ]

    def __str__(self):
        return f"{self.codigo_sienge} - {self.descricao}"


class RecebimentoObra(models.Model):
    """
    RECEBIMENTO NA OBRA (vem do Sienge) - SEM LOCAL ESPECÍFICO.
    
    Representa o que chegou na obra como um todo.
    A distribuição por local é feita via AlocacaoRecebimento.
    """
    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name='recebimentos')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name='recebimentos')
    
    # Dados do Sienge
    item_sc = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        help_text="Nº do ITEM na SC (linha do mapa exportado). Ajuda a diferenciar múltiplas linhas na mesma SC."
    )
    numero_sc = models.CharField(max_length=100, db_index=True, help_text="Nº SOLICITAÇÃO (chave de ligação)")
    data_sc = models.DateField(null=True, blank=True)
    numero_pc = models.CharField(max_length=100, blank=True, db_index=True, help_text="Nº PEDIDO DE COMPRA")
    data_pc = models.DateField(null=True, blank=True)
    empresa_fornecedora = models.CharField(max_length=200, blank=True, help_text="Fornecedor")
    prazo_recebimento = models.DateField(null=True, blank=True, help_text="Prazo previsto de entrega")

    descricao_item = models.CharField(
        max_length=500,
        blank=True,
        help_text="Descrição da linha no mapa do Sienge (pode diferir do cadastro do insumo)."
    )
    
    # Quantidades (do Sienge)
    quantidade_solicitada = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Quantidade solicitada no pedido"
    )
    quantidade_recebida = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Quantidade que CHEGOU NA OBRA (sem especificar local)"
    )
    saldo_a_entregar = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Saldo pendente de entrega"
    )
    
    # NF de entrada (última ou principal)
    numero_nf = models.CharField(max_length=100, blank=True, help_text="Nº da última NF")
    data_nf = models.DateField(null=True, blank=True)
    
    # Auditoria
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Permite múltiplos insumos na mesma SC (ex: sapato 32, 36, 38 no mesmo pedido)
        # Também permite múltiplas LINHAS do mesmo insumo na mesma SC quando o Sienge vier quebrado por ITEM.
        unique_together = [['obra', 'numero_sc', 'insumo', 'item_sc']]
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['obra', 'numero_sc', 'insumo']),  # Otimiza recebimento_vinculado lookup
        ]
        constraints = [
            # Quantidades não podem ser negativas
            models.CheckConstraint(
                check=models.Q(quantidade_solicitada__gte=0),
                name='recebimento_qtd_solicitada_nao_negativa'
            ),
            models.CheckConstraint(
                check=models.Q(quantidade_recebida__gte=0),
                name='recebimento_qtd_recebida_nao_negativa'
            ),
        ]
        verbose_name = 'Recebimento na Obra'
        verbose_name_plural = 'Recebimentos na Obra'
        indexes = [
            models.Index(fields=['obra', 'insumo']),
            models.Index(fields=['numero_sc']),
            models.Index(fields=['numero_pc']),
            models.Index(fields=['obra', 'numero_sc']),  # Para buscar todos insumos de uma SC
        ]

    def __str__(self):
        return f"{self.obra.nome} - SC {self.numero_sc} - {self.insumo.descricao}"

    @property
    def quantidade_alocada(self):
        """Soma de todas as alocações feitas a partir deste recebimento."""
        return AlocacaoRecebimento.objects.filter(
            recebimento=self
        ).aggregate(total=Sum('quantidade_alocada'))['total'] or Decimal('0.00')
    
    @property
    def quantidade_disponivel(self):
        """Quantidade recebida que ainda não foi alocada para nenhum local."""
        try:
            recebido = self.quantidade_recebida or Decimal('0.00')
            alocado = self.quantidade_alocada or Decimal('0.00')
            resultado = recebido - alocado
            # Garantir que nunca retorna negativo
            return max(resultado, Decimal('0.00'))
        except Exception:
            return Decimal('0.00')

    @property
    def quantidade_alocada_total_sc_insumo(self):
        """
        Quantidade TOTAL alocada para esta SC+insumo na obra.
        Soma todas as alocações de todos os ItemMapa com a mesma SC e insumo.
        """
        try:
            # Buscar todos os ItemMapa com a mesma SC e insumo
            itens_mesma_sc = ItemMapa.objects.filter(
                obra=self.obra,
                insumo=self.insumo,
                numero_sc=self.numero_sc
            )
            # Soma total de alocações de itens com a mesma SC
            total_alocado = AlocacaoRecebimento.objects.filter(
                obra=self.obra,
                insumo=self.insumo,
                item_mapa__in=itens_mesma_sc
            ).aggregate(total=Sum('quantidade_alocada'))['total'] or Decimal('0.00')
            return total_alocado
        except Exception:
            return Decimal('0.00')
    
    @property
    def saldo_a_entregar_calculado(self):
        """
        Saldo correto a entregar (Sienge):
        saldo = quantidade_solicitada - quantidade_alocada_total (clamp em 0).
        
        IMPORTANTE: Subtrai o que foi ALOCADO, não o que foi RECEBIDO.
        O recebido do Sienge é apenas informativo - o que importa é quanto foi alocado.
        """
        try:
            quantidade_alocada_total = self.quantidade_alocada_total_sc_insumo
            saldo = (self.quantidade_solicitada or Decimal('0.00')) - quantidade_alocada_total
        except Exception:
            saldo = Decimal('0.00')
        return max(saldo, Decimal('0.00'))
    
    @property
    def status_recebimento(self):
        """Status do recebimento."""
        if not self.numero_pc:
            return 'AGUARDANDO_PC'
        if self.quantidade_recebida == 0:
            return 'AGUARDANDO_ENTREGA'
        if self.quantidade_recebida < self.quantidade_solicitada:
            return 'PARCIAL'
        return 'COMPLETO'


class ItemMapa(models.Model):
    """
    PLANEJAMENTO - Linha do mapa de suprimentos.
    
    Representa a NECESSIDADE de um insumo em um LOCAL ESPECÍFICO.
    A quantidade alocada para este local vem das AlocacaoRecebimento.
    """
    PRIORIDADE_CHOICES = [
        ('URGENTE', 'Urgente'),
        ('ALTA', 'Alta'),
        ('MEDIA', 'Média'),
        ('BAIXA', 'Baixa'),
    ]

    # Categorias permitidas (LPLAN). Pode incluir novas no futuro.
    # Mantemos "A CLASSIFICAR" para triagem interna.
    CATEGORIA_CHOICES = [
        ('A CLASSIFICAR', 'A CLASSIFICAR'),
        ('SERVIÇOS PRELIMINARES', 'SERVIÇOS PRELIMINARES'),
        ('FUNDAÇÃO', 'FUNDAÇÃO'),
        ('ESTRUTURA', 'ESTRUTURA'),
        ('SUPERESTRUTURA', 'SUPERESTRUTURA'),
        ('ALVENARIA/FECHAMENTO', 'ALVENARIA/FECHAMENTO'),
        ('REGULARIZAÇÃO E IMPERMEABILIZAÇÃO', 'REGULARIZAÇÃO E IMPERMEABILIZAÇÃO'),
        ('IMPERMEABILIZAÇÃO', 'IMPERMEABILIZAÇÃO'),
        ('REVESTIMENTO DE PISO', 'REVESTIMENTO DE PISO'),
        ('REVESTIMENTO DE PAREDE', 'REVESTIMENTO DE PAREDE'),
        ('REVESTIMENTO DE TETO', 'REVESTIMENTO DE TETO'),
        ('REVESTIMENTO DE FACHADA', 'REVESTIMENTO DE FACHADA'),
        ('PINTURA', 'PINTURA'),
        ('ESQUADRIA MADEIRA', 'ESQUADRIA MADEIRA'),
        ('ESQUADRIA ALUMÍNIO/VIDRO', 'ESQUADRIA ALUMÍNIO/VIDRO'),
        ('GRANITO/MÁRMORE', 'GRANITO/MÁRMORE'),
        ('LOUÇAS E METAIS', 'LOUÇAS E METAIS'),
        ('PISCINAS INDIVIDUAIS', 'PISCINAS INDIVIDUAIS'),
        ('PAISAGISMO', 'PAISAGISMO'),
        ('COBERTA', 'COBERTA'),
        ('PAVIMENTAÇÃO', 'PAVIMENTAÇÃO'),
        ('OBRAS DE CONTENÇÃO', 'OBRAS DE CONTENÇÃO'),
        ('DRENAGEM', 'DRENAGEM'),
        ('SERVIÇOS COMPLEMENTARES', 'SERVIÇOS COMPLEMENTARES'),
        ('INSTALAÇÕES HIDRÁULICA', 'INSTALAÇÕES HIDRÁULICA'),
        ('INSTALAÇÕES ESGOTO', 'INSTALAÇÕES ESGOTO'),
        ('INSTALAÇÕES ELÉTRICA', 'INSTALAÇÕES ELÉTRICA'),
        ('INSTALAÇÕES GÁS', 'INSTALAÇÕES GÁS'),
        ('INSTALAÇÕES DADOS', 'INSTALAÇÕES DADOS'),
        ('INSTALAÇÕES CFTV', 'INSTALAÇÕES CFTV'),
        ('INSTALAÇÕES AR CONDICIONADO', 'INSTALAÇÕES AR CONDICIONADO'),
        ('INSTALAÇÕES PREVENÇÃO DE INCÊNDIO', 'INSTALAÇÕES PREVENÇÃO DE INCÊNDIO'),
        ('INSTALAÇÕES SPDA', 'INSTALAÇÕES SPDA'),
        ('INSTALAÇÕES ELEVADOR', 'INSTALAÇÕES ELEVADOR'),
        ('DIVERSOS', 'DIVERSOS'),
    ]

    # --- CLASSIFICAÇÃO / VISUAL ---
    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name='itens_mapa')
    categoria = models.CharField(
        max_length=100, 
        db_index=True, 
        default='A CLASSIFICAR',
        blank=True,
        help_text="Categoria de aplicação (ex: FUNDAÇÃO, ESTRUTURA). Itens do Sienge entram como 'A CLASSIFICAR'."
    )
    prioridade = models.CharField(max_length=20, choices=PRIORIDADE_CHOICES, default='MEDIA')
    nao_aplica = models.BooleanField(
        default=False,
        help_text="Marcar quando o item não se aplica"
    )

    # --- PLANEJAMENTO (ENGENHARIA - INPUT) ---
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name='itens_mapa')
    descricao_override = models.CharField(
        max_length=500,
        blank=True,
        help_text="Descrição alternativa sem quebrar vínculo com insumo"
    )
    local_aplicacao = models.ForeignKey(
        LocalObra,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_mapa',
        help_text="LOCAL onde será aplicado (Bloco A, Lobby, etc)"
    )
    responsavel = models.CharField(max_length=200, blank=True, help_text="Responsável técnico")
    prazo_necessidade = models.DateField(null=True, blank=True, help_text="Prazo que precisa do insumo")
    quantidade_planejada = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Quantidade NECESSÁRIA neste local"
    )
    observacao_eng = models.TextField(blank=True)

    # --- LIGAÇÃO COM SIENGE ---
    numero_sc = models.CharField(
        max_length=100, 
        blank=True, 
        db_index=True, 
        help_text="Nº SOLICITAÇÃO - Liga este item ao RecebimentoObra"
    )

    item_sc = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        help_text="Nº do ITEM na SC (quando houver). Ajuda a linkar a linha correta do Sienge."
    )
    
    # --- CAMPOS LEGADOS (mantidos para compatibilidade, mas preferir usar RecebimentoObra) ---
    # Estes campos podem ser removidos após migração completa
    data_sc = models.DateField(null=True, blank=True)
    numero_pc = models.CharField(max_length=100, blank=True, db_index=True)
    data_pc = models.DateField(null=True, blank=True)
    empresa_fornecedora = models.CharField(max_length=200, blank=True)
    prazo_recebimento = models.DateField(null=True, blank=True)
    quantidade_recebida = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="LEGADO: Total recebido na obra (usar RecebimentoObra)"
    )
    saldo_a_entregar = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    status_sienge_raw = models.CharField(max_length=200, blank=True)

    # --- AUDITORIA ---
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_mapa_criados'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['obra', 'categoria', 'insumo']
        indexes = [
            models.Index(fields=['obra', 'categoria']),
            models.Index(fields=['obra', 'insumo']),
            models.Index(fields=['numero_sc']),
            models.Index(fields=['numero_pc']),
            models.Index(fields=['obra', 'local_aplicacao']),  # Otimiza queries por obra+local
        ]
        constraints = [
            # Quantidade planejada não pode ser negativa
            models.CheckConstraint(
                check=models.Q(quantidade_planejada__gte=0),
                name='itemmapa_quantidade_planejada_nao_negativa'
            ),
            # Quantidade recebida (legado) não pode ser negativa
            models.CheckConstraint(
                check=models.Q(quantidade_recebida__gte=0),
                name='itemmapa_quantidade_recebida_nao_negativa'
            ),
        ]
        verbose_name = 'Item do Mapa'
        verbose_name_plural = 'Itens do Mapa'

    def __str__(self):
        return f"{self.obra.nome} - {self.insumo.descricao} - {self.local_aplicacao or 'Sem local'}"

    def clean(self):
        """Validações do modelo."""
        if self.numero_pc and not self.numero_sc:
            raise ValidationError({
                'numero_pc': 'Não é possível ter PC sem SC.'
            })
        if self.data_pc and not self.numero_pc:
            raise ValidationError({
                'data_pc': 'Data de PC requer número de PC.'
            })

    # =========================================================================
    # PROPRIEDADES CALCULADAS - NOVA ARQUITETURA
    # =========================================================================
    
    @property
    def recebimento_vinculado(self):
        """
        Busca o RecebimentoObra vinculado a este item pela SC + Insumo.
        SIMPLES: Prioriza o consolidado (item_sc='') que é criado na importação.
        """
        if not self.numero_sc:
            return None
        
        # Priorizar o consolidado (item_sc='') que é criado na importação
        recebimento = RecebimentoObra.objects.filter(
            obra=self.obra,
            numero_sc=self.numero_sc,
            insumo=self.insumo,
            item_sc=''  # Consolidado da importação
        ).first()
        
        if recebimento:
            return recebimento
        
        # Se não encontrou consolidado, buscar qualquer um (fallback)
        return RecebimentoObra.objects.filter(
            obra=self.obra,
            numero_sc=self.numero_sc,
            insumo=self.insumo
        ).first()

    @property
    def quantidade_alocada_local(self):
        """
        Quantidade que foi ALOCADA para este local específico.
        
        IMPORTANTE: A quantidade alocada é sempre a soma das AlocacaoRecebimento manuais.
        O saldo de 4.000 é global da obra, e as quantidades nos locais (Bloco A, Bloco B)
        são preenchidas manualmente, mas a soma delas não pode ultrapassar o valor máximo
        que veio do Sienge (validado no modelo AlocacaoRecebimento).
        
        OTIMIZAÇÃO: Se o queryset foi annotado com quantidade_alocada_annotated,
        usa esse valor para evitar N+1 queries.
        """
        # Se foi annotado (otimização de performance), usar esse valor
        if hasattr(self, 'quantidade_alocada_annotated'):
            return self.quantidade_alocada_annotated or Decimal('0.00')
        
        # Fallback: calcular normalmente (pode causar N+1 queries)
        return AlocacaoRecebimento.objects.filter(
            item_mapa=self
        ).aggregate(total=Sum('quantidade_alocada'))['total'] or Decimal('0.00')

    @property
    def quantidade_solicitada_sienge(self):
        """
        Quantidade SOLICITADA no Sienge (vem do RecebimentoObra).
        SIMPLES: Se tem SC, pega do RecebimentoObra vinculado.
        """
        if not self.numero_sc:
            return Decimal('0.00')
        
        recebimento = self.recebimento_vinculado
        if recebimento:
            return recebimento.quantidade_solicitada or Decimal('0.00')
        
        return Decimal('0.00')

    @property
    def quantidade_recebida_obra(self):
        """
        Quantidade que chegou NA OBRA (não necessariamente para este local).
        SIMPLES: Se tem SC, pega do RecebimentoObra vinculado.
        """
        if not self.numero_sc:
            # Fallback para campo legado
            return self.quantidade_recebida or Decimal('0.00')
        
        recebimento = self.recebimento_vinculado
        if recebimento:
            return recebimento.quantidade_recebida or Decimal('0.00')
        
        # Fallback para campo legado
        return self.quantidade_recebida or Decimal('0.00')

    @property
    def percentual_alocado(self):
        """Percentual alocado para este local (0 a 1)."""
        # Se tem SC, comparar com quantidade solicitada do Sienge
        qtd_solicitada_sienge = self.quantidade_solicitada_sienge
        if qtd_solicitada_sienge > 0:
            return min(self.quantidade_alocada_local / qtd_solicitada_sienge, Decimal('1.00'))
        
        # Se não tem SC ou quantidade_solicitada_sienge = 0, usar quantidade_planejada
        if self.quantidade_planejada <= 0:
            return Decimal('0.00')
        return min(self.quantidade_alocada_local / self.quantidade_planejada, Decimal('1.00'))
    
    @property
    def percentual_alocado_porcentagem(self):
        """Percentual alocado em porcentagem (0 a 100)."""
        return float(self.percentual_alocado) * 100

    @property
    def saldo_a_alocar_local(self):
        """Quanto ainda falta alocar para este local."""
        return max(self.quantidade_planejada - self.quantidade_alocada_local, Decimal('0.00'))
    
    @property
    def quantidade_disponivel_sienge(self):
        """
        Quantidade DISPONÍVEL no Sienge para alocar (recebida - já alocada manualmente).
        Este é o saldo pendente que pode ser alocado para esta linha específica.
        
        IMPORTANTE: 
        - O saldo de 4.000 é global da obra (RecebimentoObra)
        - As quantidades nos locais são preenchidas manualmente via AlocacaoRecebimento
        - A soma das alocações não pode ultrapassar o valor máximo recebido (validado no modelo)
        """
        if not self.numero_sc:
            return Decimal('0.00')
        
        # Buscar RecebimentoObra vinculado (com item_sc vazio para consolidar)
        recebimento = RecebimentoObra.objects.filter(
            obra=self.obra,
            numero_sc=self.numero_sc,
            insumo=self.insumo,
            item_sc=''
        ).first()
        
        if recebimento:
            # Quantidade recebida na obra (global)
            recebido = recebimento.quantidade_recebida or Decimal('0.00')
            
            # Quantidade já alocada manualmente (soma de todas as AlocacaoRecebimento deste recebimento)
            alocado_manual = recebimento.quantidade_alocada or Decimal('0.00')
            
            # Disponível = recebido - alocado manualmente
            disponivel = recebido - alocado_manual
            return max(Decimal('0.00'), disponivel)
        
        return Decimal('0.00')
    
    @property
    def saldo_pendente_alocacao(self):
        """
        Saldo DISPONÍVEL para alocar para ESTA linha específica.
        
        IMPORTANTE: 
        - Este é o saldo que JÁ FOI RECEBIDO na obra e ainda NÃO FOI ALOCADO.
        - Diferente do saldo_a_entregar, que indica quanto ainda falta chegar.
        - Quando há material recebido mas não alocado, este valor mostra quanto está disponível.
        """
        if not self.numero_sc:
            # Fallback para saldo local (sem SC, usa lógica de planejado - alocado)
            return self.saldo_a_alocar_local
        
        # Se tem SC, usar quantidade_disponivel_sienge (recebido - já alocado)
        # Este é o saldo que já chegou na obra e está disponível para alocação manual
        return self.quantidade_disponivel_sienge

    @property
    def saldo_local_diferenca(self):
        """
        Diferença do LOCAL (pode ser negativa):
        planejado - alocado
        """
        try:
            return (self.quantidade_planejada or Decimal('0.00')) - (self.quantidade_alocada_local or Decimal('0.00'))
        except Exception:
            return Decimal('0.00')

    @property
    def saldo_a_entregar_sienge(self):
        """
        Saldo a ser entregue (Sienge): solicitado - alocado_total.
        SEMPRE mostra o total (solicitado - alocado), não (solicitado - recebido).
        
        IMPORTANTE: O recebido do Sienge é apenas informativo.
        O saldo deve mostrar quanto ainda falta ser ALOCADO, não quanto falta ser recebido.
        """
        if not self.numero_sc:
            # Sem SC: usar campo legado ou saldo local
            return max(self.saldo_a_entregar or Decimal('0.00'), Decimal('0.00'))
        
        recebimento = self.recebimento_vinculado
        if recebimento:
            # Se tem recebimento vinculado, usar o saldo calculado (solicitado - alocado_total)
            # Isso sempre mostra o total correto: solicitado - alocado
            return recebimento.saldo_a_entregar_calculado
        
        # Se tem SC mas não tem recebimento vinculado, buscar TODOS os RecebimentoObra
        # com essa SC+insumo para calcular o saldo total
        recebimentos = RecebimentoObra.objects.filter(
            obra=self.obra,
            numero_sc=self.numero_sc,
            insumo=self.insumo
        )
        
        if recebimentos.exists():
            # Somar quantidade solicitada de todos os recebimentos
            total_solicitado = sum((r.quantidade_solicitada or Decimal('0.00')) for r in recebimentos)
            
            # Calcular quantidade total alocada para esta SC+insumo
            itens_mesma_sc = ItemMapa.objects.filter(
                obra=self.obra,
                insumo=self.insumo,
                numero_sc=self.numero_sc
            )
            total_alocado = AlocacaoRecebimento.objects.filter(
                obra=self.obra,
                insumo=self.insumo,
                item_mapa__in=itens_mesma_sc
            ).aggregate(total=Sum('quantidade_alocada'))['total'] or Decimal('0.00')
            
            saldo = max(total_solicitado - total_alocado, Decimal('0.00'))
            return saldo
        
        # Se não encontrou nenhum recebimento, usar campo legado
        # O campo legado saldo_a_entregar pode ter sido preenchido na importação ou manualmente
        saldo_legado = self.saldo_a_entregar or Decimal('0.00')
        return max(saldo_legado, Decimal('0.00'))

    @property
    def sienge_overdelivered(self):
        """Indica se o Sienge aponta entregue > solicitado (anomalia/ajuste)."""
        recebimento = self.recebimento_vinculado
        if not recebimento:
            return False
        try:
            return (recebimento.quantidade_solicitada or Decimal('0.00')) > 0 and (
                (recebimento.quantidade_recebida or Decimal('0.00')) > (recebimento.quantidade_solicitada or Decimal('0.00'))
            )
        except Exception:
            return False

    # =========================================================================
    # PROPRIEDADES DE STATUS - AJUSTADAS PARA NOVA ARQUITETURA
    # =========================================================================

    @property
    def percentual_entregue(self):
        """Percentual entregue PARA ESTE LOCAL (baseado em alocações)."""
        return self.percentual_alocado
    
    @property
    def percentual_entregue_porcentagem(self):
        """Percentual entregue em porcentagem."""
        return self.percentual_alocado_porcentagem

    @property
    def is_atrasado(self):
        """Verifica se está atrasado."""
        hoje = timezone.now().date()
        
        # Atraso por prazo de necessidade (se não tem SC ainda)
        if not self.numero_sc and self.prazo_necessidade and hoje > self.prazo_necessidade:
            return True
        
        # Atraso por prazo de recebimento (se tem SC/PC mas não recebeu tudo)
        recebimento = self.recebimento_vinculado
        prazo_recebimento = None
        
        if recebimento and recebimento.prazo_recebimento:
            prazo_recebimento = recebimento.prazo_recebimento
        elif self.prazo_recebimento:
            prazo_recebimento = self.prazo_recebimento
        
        if prazo_recebimento and hoje > prazo_recebimento:
            # Se tem SC, comparar com quantidade solicitada do Sienge
            qtd_solicitada_sienge = self.quantidade_solicitada_sienge
            if qtd_solicitada_sienge > 0:
                # Está atrasado se ainda não recebeu tudo que foi solicitado
                if self.quantidade_alocada_local < qtd_solicitada_sienge:
                    return True
            # Se não tem SC ou quantidade_solicitada_sienge = 0, usar quantidade_planejada
            elif self.quantidade_planejada > 0:
                if self.quantidade_alocada_local < self.quantidade_planejada:
                    return True
            # Fallback: se tem saldo a alocar local
            elif self.saldo_a_alocar_local > 0:
                return True
        
        return False

    @property
    def status_etapa(self):
        """Status textual da etapa."""
        if not self.numero_sc:
            return '1) LEVANTAMENTO'
        
        recebimento = self.recebimento_vinculado
        
        # Se não tem PC
        if recebimento and not recebimento.numero_pc:
            return '2) AGUARDANDO COMPRA'
        if not recebimento and not self.numero_pc:
            return '2) AGUARDANDO COMPRA'
        
        # Se tem PC mas não chegou na obra
        qtd_recebida_obra = recebimento.quantidade_recebida if recebimento else self.quantidade_recebida
        if qtd_recebida_obra == 0:
            return '3) AGUARDANDO ENTREGA'
        
        # Se chegou na obra mas não foi alocado para este local
        qtd_alocada = self.quantidade_alocada_local
        if qtd_alocada == 0:
            return '4) AGUARDANDO ALOCAÇÃO'
        
        # Se tem SC, comparar com quantidade solicitada do Sienge
        qtd_solicitada_sienge = self.quantidade_solicitada_sienge
        if qtd_solicitada_sienge > 0:
            # Se foi alocado parcialmente (recebeu menos do que foi solicitado)
            if qtd_alocada < qtd_solicitada_sienge:
                return '5) ALOCAÇÃO PARCIAL'
            # Entregue completamente
            if qtd_alocada >= qtd_solicitada_sienge:
                return 'ENTREGUE'
        
        # Se não tem quantidade_solicitada_sienge, usar quantidade_planejada
        if self.quantidade_planejada > 0:
            # Se foi alocado parcialmente
            if qtd_alocada < self.quantidade_planejada:
                return '5) ALOCAÇÃO PARCIAL'
            # Entregue
            if qtd_alocada >= self.quantidade_planejada:
                return 'ENTREGUE'
        
        return 'INDEFINIDO'

    @property
    def saldo_negativo(self):
        """Verifica se alocado > planejado."""
        return self.quantidade_alocada_local > self.quantidade_planejada and self.quantidade_planejada > 0

    @property
    def status_css(self):
        """
        Lógica de cores do status (sincronizada com status_etapa):
        
        1. 🟢 VERDE (Entregue): Totalmente alocado para este local
        2. 🟠 LARANJA (Parcial): Alocação parcial para este local
        3. 🟡 AMARELO (Aguardando Alocação): Chegou na obra, falta alocar
        4. 🔵 AZUL (Aguardando Entrega): Tem PC, aguardando fornecedor
        5. 🔴 VERMELHO (Solicitado): Tem SC, aguardando Compras gerar PC
        6. ⚪ BRANCO (Levantamento): Sem SC, pendente da Engenharia
        """
        qtd_recebida_obra = self.quantidade_recebida_obra
        has_pc = self.numero_pc or (self.recebimento_vinculado and self.recebimento_vinculado.numero_pc)
        qtd_solicitada_sienge = self.quantidade_solicitada_sienge
        
        # 1. VERDE (Entregue): Totalmente alocado para este local
        # Se tem SC, comparar com quantidade solicitada do Sienge
        if qtd_solicitada_sienge > 0:
            if self.quantidade_alocada_local >= qtd_solicitada_sienge:
                return 'status-verde'
        # Se não tem SC ou quantidade_solicitada_sienge = 0, usar quantidade_planejada
        elif self.quantidade_planejada > 0 and self.quantidade_alocada_local >= self.quantidade_planejada:
            return 'status-verde'
        
        # 2. LARANJA (Parcial): Alocação parcial para este local
        # Se tem SC, comparar com quantidade solicitada do Sienge
        if qtd_solicitada_sienge > 0:
            if self.quantidade_alocada_local > 0 and self.quantidade_alocada_local < qtd_solicitada_sienge:
                return 'status-laranja'
        # Se não tem SC ou quantidade_solicitada_sienge = 0, usar quantidade_planejada
        elif self.quantidade_planejada > 0 and self.quantidade_alocada_local > 0 and self.quantidade_alocada_local < self.quantidade_planejada:
            return 'status-laranja'
        
        # 3. AMARELO (Aguardando Alocação): Chegou na obra mas não foi alocado
        if has_pc and qtd_recebida_obra > 0 and self.quantidade_alocada_local == 0:
            return 'status-amarelo'
        
        # 4. AZUL (Aguardando Entrega): Tem PC mas ainda não chegou na obra
        if has_pc and qtd_recebida_obra == 0:
            return 'status-azul'
        
        # 5. VERMELHO (Solicitado): Tem SC, aguardando Compras gerar PC
        if self.numero_sc and self.numero_sc.strip() != '':
            if not has_pc:
                return 'status-vermelho'
        
        # 6. BRANCO (Levantamento): Sem SC, pendente da Engenharia
        if not self.numero_sc or self.numero_sc.strip() == '':
            return 'status-branco'
        
        return 'status-indefinido'

    @property
    def quem_cobrar(self):
        """Retorna quem deve ser cobrado baseado no status."""
        if not self.numero_sc:
            return 'ENGENHARIA'
        
        recebimento = self.recebimento_vinculado
        has_pc = self.numero_pc or (recebimento and recebimento.numero_pc)
        
        if not has_pc:
            return 'COMPRAS'
        
        qtd_recebida = recebimento.quantidade_recebida if recebimento else self.quantidade_recebida
        
        # Se chegou na obra mas não alocou, é responsabilidade interna (almoxarife/engenharia)
        if qtd_recebida > 0 and self.quantidade_alocada_local == 0:
            return 'ALMOXARIFADO'
        
        # Se não chegou tudo, cobrar fornecedor
        if qtd_recebida < self.quantidade_planejada:
            return 'FORNECEDOR'
        
        return None


class NotaFiscalEntrada(models.Model):
    """Detalhe das NFs de entrada, para drill-down e histórico."""
    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name='notas_fiscais')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name='notas_fiscais')
    recebimento = models.ForeignKey(
        RecebimentoObra,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notas_fiscais',
        help_text="Recebimento vinculado"
    )
    numero_pc = models.CharField(max_length=100, blank=True, db_index=True)
    numero_nf = models.CharField(max_length=100, db_index=True)
    data_entrada = models.DateField(null=True, blank=True)
    quantidade = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['obra', 'insumo', 'numero_nf', 'data_entrada', 'numero_pc']]
        ordering = ['-data_entrada', '-created_at']
        verbose_name = 'Nota Fiscal de Entrada'
        verbose_name_plural = 'Notas Fiscais de Entrada'

    def __str__(self):
        return f"NF {self.numero_nf} - {self.insumo.descricao} - {self.obra.nome}"


class AlocacaoRecebimento(models.Model):
    """
    RATEIO/ALOCAÇÃO - Distribui o recebimento para os locais da obra.
    
    Exemplo: Chegaram 1000 kg de cimento na obra.
    - 400 kg para Bloco A (ItemMapa do Bloco A)
    - 350 kg para Bloco B (ItemMapa do Bloco B)
    - 250 kg para Lobby (ItemMapa do Lobby)
    """
    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name='alocacoes')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name='alocacoes')
    local_aplicacao = models.ForeignKey(
        LocalObra, 
        on_delete=models.PROTECT, 
        related_name='alocacoes',
        help_text="Local para onde foi alocado"
    )
    
    # Vinculação
    recebimento = models.ForeignKey(
        RecebimentoObra,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='alocacoes',
        help_text="Recebimento de onde veio o material"
    )
    item_mapa = models.ForeignKey(
        ItemMapa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alocacoes',
        help_text="Item do mapa que recebeu a alocação"
    )
    referencia_nf = models.ForeignKey(
        NotaFiscalEntrada,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='alocacoes',
        help_text="NF específica (opcional)"
    )
    
    quantidade_alocada = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Quantidade alocada para este local"
    )
    observacao = models.TextField(blank=True, help_text="Observação da alocação")
    
    # Auditoria
    data_alocacao = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alocacoes_criadas'
    )

    class Meta:
        ordering = ['-data_alocacao']
        indexes = [
            models.Index(fields=['recebimento', 'item_mapa']),  # Otimiza queries de alocação
            models.Index(fields=['obra', 'insumo', 'local_aplicacao']),  # Otimiza totais por local
        ]
        constraints = [
            # Quantidade alocada deve ser positiva (> 0)
            models.CheckConstraint(
                check=models.Q(quantidade_alocada__gt=0),
                name='alocacao_quantidade_positiva'
            ),
        ]
        verbose_name = 'Alocação de Recebimento'
        verbose_name_plural = 'Alocações de Recebimento'

    def __str__(self):
        return f"{self.local_aplicacao.nome}: {self.quantidade_alocada} {self.insumo.unidade}"

    def clean(self):
        """Validação: não ultrapassar quantidade disponível."""
        if self.recebimento:
            # Validar contra o recebimento
            total_alocado = AlocacaoRecebimento.objects.filter(
                recebimento=self.recebimento
            ).exclude(pk=self.pk).aggregate(
                total=Sum('quantidade_alocada')
            )['total'] or Decimal('0.00')
            
            disponivel = self.recebimento.quantidade_recebida - total_alocado
            if self.quantidade_alocada > disponivel:
                raise ValidationError(
                    f'Quantidade alocada ({self.quantidade_alocada}) excede o disponível ({disponivel}).'
                )
        elif self.referencia_nf:
            # Validar contra NF específica
            total_alocado = AlocacaoRecebimento.objects.filter(
                referencia_nf=self.referencia_nf
            ).exclude(pk=self.pk).aggregate(
                total=Sum('quantidade_alocada')
            )['total'] or Decimal('0.00')
            
            disponivel = self.referencia_nf.quantidade - total_alocado
            if self.quantidade_alocada > disponivel:
                raise ValidationError(
                    f'Quantidade alocada ({self.quantidade_alocada}) excede o disponível da NF ({disponivel}).'
                )
    
    def save(self, *args, **kwargs):
        """
        Override save para garantir validação sempre executada.
        
        CORREÇÃO PRIORIDADE 2: Mover validação para save() garante que
        sempre seja executada, mesmo quando não chamar full_clean().
        Isso previne race conditions em casos onde o objeto é salvo diretamente.
        """
        # Sempre validar antes de salvar
        self.full_clean()
        
        # Chamar save do modelo base
        super().save(*args, **kwargs)


class HistoricoAlteracao(models.Model):
    """
    Registro de todas as alterações feitas no sistema.
    Permite auditoria: quem fez o quê, quando.
    """
    TIPO_CHOICES = [
        ('CRIACAO', 'Criação'),
        ('EDICAO', 'Edição'),
        ('ALOCACAO', 'Alocação'),
        ('STATUS', 'Mudança de Status'),
        ('IMPORTACAO', 'Importação Sienge'),
        ('EXCLUSAO', 'Exclusão'),
    ]
    
    obra = models.ForeignKey(
        Obra, 
        on_delete=models.CASCADE, 
        related_name='historico_alteracoes'
    )
    item_mapa = models.ForeignKey(
        ItemMapa, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='historico'
    )
    
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    campo_alterado = models.CharField(max_length=100, blank=True, help_text="Campo que foi alterado")
    valor_anterior = models.TextField(blank=True, help_text="Valor antes da alteração")
    valor_novo = models.TextField(blank=True, help_text="Valor após a alteração")
    descricao = models.TextField(help_text="Descrição legível da alteração")
    
    # Contexto
    insumo_nome = models.CharField(max_length=200, blank=True, help_text="Nome do insumo (para exibição)")
    local_nome = models.CharField(max_length=100, blank=True, help_text="Nome do local (para exibição)")
    
    # Auditoria
    usuario = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='alteracoes_realizadas'
    )
    data_hora = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-data_hora']
        verbose_name = 'Histórico de Alteração'
        verbose_name_plural = 'Histórico de Alterações'
        indexes = [
            models.Index(fields=['obra', '-data_hora']),
            models.Index(fields=['item_mapa', '-data_hora']),
            models.Index(fields=['usuario', '-data_hora']),
        ]
    
    def __str__(self):
        return f"{self.data_hora.strftime('%d/%m %H:%M')} - {self.usuario} - {self.descricao[:50]}"
    
    @classmethod
    def registrar(cls, obra, usuario, tipo, descricao, item_mapa=None, 
                  campo_alterado='', valor_anterior='', valor_novo='', ip_address=None):
        """Método auxiliar para registrar alterações facilmente."""
        return cls.objects.create(
            obra=obra,
            item_mapa=item_mapa,
            tipo=tipo,
            campo_alterado=campo_alterado,
            valor_anterior=str(valor_anterior) if valor_anterior else '',
            valor_novo=str(valor_novo) if valor_novo else '',
            descricao=descricao,
            insumo_nome=item_mapa.insumo.descricao[:200] if item_mapa and item_mapa.insumo else '',
            local_nome=item_mapa.local_aplicacao.nome if item_mapa and item_mapa.local_aplicacao else '',
            usuario=usuario,
            ip_address=ip_address
        )
