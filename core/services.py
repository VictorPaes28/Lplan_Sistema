"""
Services Layer para Diário de Obra V2.0 - LPLAN

Este módulo contém a lógica de negócio crítica:
- Transições de workflow de aprovação de diários
- Cálculo de rollup de progresso na hierarquia EAP
- Validações e regras de negócio
"""
from decimal import Decimal
from typing import Optional, List, Tuple
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from accounts.groups import GRUPOS
from .models import (
    Activity,
    ConstructionDiary,
    DailyWorkLog,
    DiaryStatus,
    ActivityStatus,
    Notification,
)


class WorkflowService:
    """
    Workflow simplificado: não há mais revisar/aprovar.
    Salvar diário (não rascunho) no formulário define status APROVADO e envia ao dono da obra.
    """


class ProgressService:
    """
    Service para cálculo de progresso na hierarquia EAP.
    
    Implementa rollup ponderado de progresso, propagando valores
    dos filhos para os pais baseado nos pesos (weight) das atividades.
    """
    
    @staticmethod
    def get_activity_progress(activity: Activity) -> Decimal:
        """
        Calcula o progresso atual de uma atividade específica.
        
        Para atividades folha (sem filhos):
        - Retorna o progresso acumulado do último DailyWorkLog
        
        Para atividades com filhos:
        - Calcula média ponderada dos filhos baseado no campo 'weight'
        
        Args:
            activity: Instância da Activity
            
        Returns:
            Decimal representando o progresso (0-100)
        """
        if activity.is_leaf():
            # Atividade folha: busca o último registro de progresso
            last_work_log = (
                DailyWorkLog.objects
                .filter(activity=activity)
                .order_by('-created_at')
                .first()
            )
            
            if last_work_log:
                return last_work_log.accumulated_progress_snapshot
            return Decimal('0.00')
        
        # Atividade com filhos: calcula média ponderada
        children = activity.get_children()
        if not children.exists():
            return Decimal('0.00')
        
        total_weight = Decimal('0.00')
        weighted_sum = Decimal('0.00')
        
        for child in children:
            child_weight = child.weight
            child_progress = ProgressService.get_activity_progress(child)
            
            total_weight += child_weight
            weighted_sum += child_weight * child_progress
        
        if total_weight == Decimal('0.00'):
            # Se nenhum filho tem peso, calcula média simples
            child_progresses = [
                ProgressService.get_activity_progress(child)
                for child in children
            ]
            if child_progresses:
                return sum(child_progresses) / len(child_progresses)
            return Decimal('0.00')
        
        # Progresso ponderado
        return weighted_sum / total_weight
    
    @staticmethod
    @transaction.atomic
    def calculate_rollup_progress(activity_id: int) -> Decimal:
        """
        Calcula e atualiza o progresso de uma atividade e propaga para os ancestrais.
        
        Este método:
        1. Calcula o progresso da atividade (folha ou com filhos)
        2. Atualiza o status da atividade baseado no progresso
        3. Propaga o recálculo para todos os ancestrais
        
        Usa transações atômicas para garantir integridade durante o rollup.
        
        Args:
            activity_id: ID da Activity a ser recalculada
            
        Returns:
            Decimal representando o novo progresso calculado
            
        Raises:
            Activity.DoesNotExist: Se a atividade não existir
        """
        try:
            activity = Activity.objects.get(pk=activity_id)
        except Activity.DoesNotExist:
            raise ValidationError(f"Atividade com ID {activity_id} não encontrada.")
        
        # Calcula progresso atual
        new_progress = ProgressService.get_activity_progress(activity)
        
        # Atualiza status baseado no progresso
        if new_progress == Decimal('0.00'):
            activity.status = ActivityStatus.NOT_STARTED
        elif new_progress == Decimal('100.00'):
            activity.status = ActivityStatus.COMPLETED
        else:
            activity.status = ActivityStatus.IN_PROGRESS
        
        activity.save(update_fields=['status', 'updated_at'])
        
        # Propaga para os ancestrais
        ancestors = activity.get_ancestors()
        for ancestor in ancestors:
            ancestor_progress = ProgressService.get_activity_progress(ancestor)
            
            # Atualiza status do ancestral
            if ancestor_progress == Decimal('0.00'):
                ancestor.status = ActivityStatus.NOT_STARTED
            elif ancestor_progress == Decimal('100.00'):
                ancestor.status = ActivityStatus.COMPLETED
            else:
                ancestor.status = ActivityStatus.IN_PROGRESS
            
            ancestor.save(update_fields=['status', 'updated_at'])
        
        return new_progress
    
    @staticmethod
    @transaction.atomic
    def update_activity_progress_from_worklog(work_log: DailyWorkLog) -> Decimal:
        """
        Atualiza o progresso de uma atividade a partir de um DailyWorkLog.
        
        Este método é chamado quando um novo registro de trabalho é criado
        ou atualizado. Ele:
        1. Atualiza o snapshot de progresso acumulado
        2. Dispara o rollup para a hierarquia
        
        Args:
            work_log: Instância do DailyWorkLog
            
        Returns:
            Decimal representando o novo progresso calculado
        """
        # O progresso acumulado já está no work_log.accumulated_progress_snapshot
        # Dispara o rollup para atualizar a hierarquia
        return ProgressService.calculate_rollup_progress(work_log.activity_id)
    
    @staticmethod
    def get_project_overall_progress(project_id: int) -> Decimal:
        """
        Calcula o progresso geral do projeto baseado na raiz da EAP.
        
        Args:
            project_id: ID do Project
            
        Returns:
            Decimal representando o progresso geral (0-100)
        """
        from .models import Project
        
        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            raise ValidationError(f"Projeto com ID {project_id} não encontrado.")
        
        # Busca a atividade raiz (sem pai)
        root_activities = Activity.objects.filter(
            project=project,
            depth=1  # Primeiro nível da hierarquia
        )
        
        if not root_activities.exists():
            return Decimal('0.00')
        
        # Se houver múltiplas raízes, calcula média ponderada
        total_weight = Decimal('0.00')
        weighted_sum = Decimal('0.00')
        
        for root in root_activities:
            root_weight = root.weight
            root_progress = ProgressService.get_activity_progress(root)
            
            total_weight += root_weight
            weighted_sum += root_weight * root_progress
        
        if total_weight == Decimal('0.00'):
            # Média simples se não houver pesos
            progresses = [
                ProgressService.get_activity_progress(root)
                for root in root_activities
            ]
            if progresses:
                return sum(progresses) / len(progresses)
            return Decimal('0.00')
        
        return weighted_sum / total_weight

