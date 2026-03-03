"""
Sinais Django para Diário de Obra V2.0.

Dispara ações automáticas quando modelos são criados/atualizados:
- Rollup de progresso quando DailyWorkLog é salvo
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging
from .models import DailyWorkLog
from .services import ProgressService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=DailyWorkLog)
def update_progress_on_worklog_save(sender, instance, created, **kwargs):
    """
    Dispara rollup de progresso quando um DailyWorkLog é criado ou atualizado.
    
    Args:
        sender: Modelo que disparou o sinal (DailyWorkLog)
        instance: Instância do DailyWorkLog salva
        created: True se foi criado, False se foi atualizado
        **kwargs: Argumentos adicionais
    """
    try:
        ProgressService.update_activity_progress_from_worklog(instance)
    except Exception as e:
        # Log do erro mas não interrompe o save
        logger.error(f"Erro ao atualizar progresso após salvar worklog {instance.id}: {e}", exc_info=True)


@receiver(post_delete, sender=DailyWorkLog)
def update_progress_on_worklog_delete(sender, instance, **kwargs):
    """
    Dispara rollup de progresso quando um DailyWorkLog é deletado.
    
    Args:
        sender: Modelo que disparou o sinal (DailyWorkLog)
        instance: Instância do DailyWorkLog deletado
        **kwargs: Argumentos adicionais
    """
    try:
        # Recalcula progresso da atividade após deleção
        ProgressService.calculate_rollup_progress(instance.activity_id)
    except Exception as e:
        # Log do erro mas não interrompe o delete
        logger.error(f"Erro ao atualizar progresso após deleção de worklog {instance.id}: {e}", exc_info=True)

