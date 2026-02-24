"""
Testes unitários para Diário de Obra V2.0 - LPLAN

Cobre:
- Transições de workflow de aprovação
- Cálculo de rollup de progresso na EAP
- Validações de permissão
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User, Group, Permission
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from datetime import date, timedelta
from accounts.groups import GRUPOS
from .models import (
    Project,
    Activity,
    ConstructionDiary,
    DailyWorkLog,
    DiaryStatus,
    ActivityStatus,
    Labor,
    Equipment,
)
from .services import ProgressService


class ProgressServiceTestCase(TestCase):
    """Testes para cálculo de progresso e rollup na EAP."""
    
    def setUp(self):
        """Configuração inicial para os testes."""
        # Cria projeto
        self.project = Project.objects.create(
            code='PROJ-2024-002',
            name='Projeto Progresso Teste',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365)
        )
        
        # Cria hierarquia de atividades (EAP)
        # Projeto
        #   └── 1.0 Fundação (peso: 30%)
        #       ├── 1.1 Escavação (peso: 50%, folha)
        #       └── 1.2 Concreto (peso: 50%, folha)
        #   └── 2.0 Estrutura (peso: 70%)
        #       └── 2.1 Pilares (peso: 100%, folha)
        
        self.fundacao = Activity.add_root(
            project=self.project,
            name='Fundação',
            code='1.0',
            weight=Decimal('30.00')
        )
        
        self.escavacao = self.fundacao.add_child(
            project=self.project,
            name='Escavação',
            code='1.1',
            weight=Decimal('50.00')
        )
        
        self.concreto = self.fundacao.add_child(
            project=self.project,
            name='Concreto',
            code='1.2',
            weight=Decimal('50.00')
        )
        
        self.estrutura = Activity.add_root(
            project=self.project,
            name='Estrutura',
            code='2.0',
            weight=Decimal('70.00')
        )
        
        self.pilares = self.estrutura.add_child(
            project=self.project,
            name='Pilares',
            code='2.1',
            weight=Decimal('100.00')
        )
        
        # Cria diário
        self.diary = ConstructionDiary.objects.create(
            project=self.project,
            date=date.today(),
            status=DiaryStatus.PREENCHENDO,
            created_by=User.objects.create_user(username='testuser')
        )
    
    def test_leaf_activity_progress_without_worklog(self):
        """Testa progresso de atividade folha sem registros."""
        progress = ProgressService.get_activity_progress(self.escavacao)
        self.assertEqual(progress, Decimal('0.00'))
    
    def test_leaf_activity_progress_with_worklog(self):
        """Testa progresso de atividade folha com registro."""
        DailyWorkLog.objects.create(
            activity=self.escavacao,
            diary=self.diary,
            percentage_executed_today=Decimal('10.00'),
            accumulated_progress_snapshot=Decimal('50.00')
        )
        
        progress = ProgressService.get_activity_progress(self.escavacao)
        self.assertEqual(progress, Decimal('50.00'))
    
    def test_parent_activity_progress_weighted_average(self):
        """Testa cálculo de progresso ponderado de atividade pai."""
        # Escavação: 50% de progresso
        DailyWorkLog.objects.create(
            activity=self.escavacao,
            diary=self.diary,
            percentage_executed_today=Decimal('10.00'),
            accumulated_progress_snapshot=Decimal('50.00')
        )
        
        # Concreto: 100% de progresso
        DailyWorkLog.objects.create(
            activity=self.concreto,
            diary=self.diary,
            percentage_executed_today=Decimal('20.00'),
            accumulated_progress_snapshot=Decimal('100.00')
        )
        
        # Fundação deve ter: (50% * 50% + 100% * 50%) / 100% = 75%
        progress = ProgressService.get_activity_progress(self.fundacao)
        expected = (Decimal('50.00') * Decimal('50.00') + Decimal('100.00') * Decimal('50.00')) / Decimal('100.00')
        self.assertEqual(progress, expected)
    
    def test_parent_activity_progress_simple_average_no_weights(self):
        """Testa cálculo de média simples quando pesos são zero."""
        # Remove pesos
        self.escavacao.weight = Decimal('0.00')
        self.escavacao.save()
        self.concreto.weight = Decimal('0.00')
        self.concreto.save()
        
        DailyWorkLog.objects.create(
            activity=self.escavacao,
            diary=self.diary,
            accumulated_progress_snapshot=Decimal('30.00')
        )
        
        DailyWorkLog.objects.create(
            activity=self.concreto,
            diary=self.diary,
            accumulated_progress_snapshot=Decimal('70.00')
        )
        
        # Média simples: (30% + 70%) / 2 = 50%
        progress = ProgressService.get_activity_progress(self.fundacao)
        self.assertEqual(progress, Decimal('50.00'))
    
    def test_calculate_rollup_progress_updates_status(self):
        """Testa que rollup atualiza status da atividade."""
        # Marca escavação como 100% concluída
        DailyWorkLog.objects.create(
            activity=self.escavacao,
            diary=self.diary,
            accumulated_progress_snapshot=Decimal('100.00')
        )
        
        # Marca concreto como 100% concluída
        DailyWorkLog.objects.create(
            activity=self.concreto,
            diary=self.diary,
            accumulated_progress_snapshot=Decimal('100.00')
        )
        
        # Dispara rollup na fundação
        ProgressService.calculate_rollup_progress(self.fundacao.id)
        
        self.fundacao.refresh_from_db()
        self.assertEqual(self.fundacao.status, ActivityStatus.COMPLETED)
    
    def test_calculate_rollup_propagates_to_ancestors(self):
        """Testa que rollup propaga para ancestrais."""
        # Marca ambas as folhas como concluídas
        DailyWorkLog.objects.create(
            activity=self.escavacao,
            diary=self.diary,
            accumulated_progress_snapshot=Decimal('100.00')
        )
        
        DailyWorkLog.objects.create(
            activity=self.concreto,
            diary=self.diary,
            accumulated_progress_snapshot=Decimal('100.00')
        )
        
        # Dispara rollup em uma folha (deve propagar para pai e avô)
        ProgressService.calculate_rollup_progress(self.escavacao.id)
        
        self.fundacao.refresh_from_db()
        self.assertEqual(self.fundacao.status, ActivityStatus.COMPLETED)
    
    def test_update_activity_progress_from_worklog(self):
        """Testa atualização de progresso a partir de worklog."""
        work_log = DailyWorkLog.objects.create(
            activity=self.escavacao,
            diary=self.diary,
            percentage_executed_today=Decimal('25.00'),
            accumulated_progress_snapshot=Decimal('75.00')
        )
        
        # Dispara atualização
        new_progress = ProgressService.update_activity_progress_from_worklog(work_log)
        
        self.escavacao.refresh_from_db()
        self.assertEqual(self.escavacao.status, ActivityStatus.IN_PROGRESS)
        self.assertEqual(new_progress, Decimal('75.00'))
    
    def test_get_project_overall_progress(self):
        """Testa cálculo de progresso geral do projeto."""
        # Fundação: 75% (calculado anteriormente)
        DailyWorkLog.objects.create(
            activity=self.escavacao,
            diary=self.diary,
            accumulated_progress_snapshot=Decimal('50.00')
        )
        
        DailyWorkLog.objects.create(
            activity=self.concreto,
            diary=self.diary,
            accumulated_progress_snapshot=Decimal('100.00')
        )
        
        # Estrutura: 60%
        DailyWorkLog.objects.create(
            activity=self.pilares,
            diary=self.diary,
            accumulated_progress_snapshot=Decimal('60.00')
        )
        
        # Progresso geral ponderado:
        # Fundação (30% peso): 75%
        # Estrutura (70% peso): 60%
        # Total: (75% * 30% + 60% * 70%) / 100% = 64.5%
        
        overall = ProgressService.get_project_overall_progress(self.project.id)
        expected = (
            Decimal('75.00') * Decimal('30.00') +
            Decimal('60.00') * Decimal('70.00')
        ) / Decimal('100.00')
        
        self.assertEqual(overall, expected)


class ActivityModelTestCase(TestCase):
    """Testes para métodos do modelo Activity."""
    
    def setUp(self):
        """Configuração inicial."""
        self.project = Project.objects.create(
            code='PROJ-2024-003',
            name='Projeto Árvore Teste',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365)
        )
        
        self.root = Activity.add_root(
            project=self.project,
            name='Raiz',
            code='1.0'
        )
        
        self.child = self.root.add_child(
            project=self.project,
            name='Filho',
            code='1.1'
        )
    
    def test_is_leaf(self):
        """Testa método is_leaf()."""
        self.assertFalse(self.root.is_leaf())
        self.assertTrue(self.child.is_leaf())
    
    def test_get_children(self):
        """Testa método get_children()."""
        children = list(self.root.get_children())
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0], self.child)
    
    def test_get_descendants(self):
        """Testa método get_descendants()."""
        # Adiciona neto
        grandchild = self.child.add_child(
            project=self.project,
            name='Neto',
            code='1.1.1'
        )
        
        descendants = list(self.root.get_descendants())
        self.assertEqual(len(descendants), 2)
        self.assertIn(self.child, descendants)
        self.assertIn(grandchild, descendants)
    
    def test_get_ancestors(self):
        """Testa método get_ancestors()."""
        ancestors = list(self.child.get_ancestors())
        self.assertEqual(len(ancestors), 1)
        self.assertEqual(ancestors[0], self.root)

