"""
Configuração Celery para Sistema LPLAN Central.

Configura o broker e backend do Celery para processamento assíncrono
de tarefas como geração de PDFs.
"""
import os
from celery import Celery

# Define o módulo de configuração do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lplan_central.settings')

app = Celery('lplan_central')

# Carrega configurações do Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descobre tarefas em apps instalados
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Tarefa de debug para testar configuração do Celery."""
    print(f'Request: {self.request!r}')
