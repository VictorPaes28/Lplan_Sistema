"""
Dados genéricos para testar a Central de Aprovações (workflow_aprovacao) sem Sienge.

Cria um projeto core.Project, fluxos por categoria (contrato, BM, medição) e processos
via ApprovalEngine.start com sync_status sem integração externa.

Uso:
  python manage.py seed_workflow_demo
  python manage.py seed_workflow_demo --username admin
  python manage.py seed_workflow_demo --reset   # remove o projeto demo e recria
"""
from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.groups import GRUPOS
from core.models import Project
from workflow_aprovacao.models import (
    ApprovalFlowDefinition,
    ApprovalPolicy,
    ApprovalProcess,
    ApprovalStep,
    ApprovalStepParticipant,
    ParticipantRole,
    ProcessCategory,
    SubjectKind,
    SyncStatus,
)
from workflow_aprovacao.services.engine import ApprovalEngine

DEMO_PROJECT_CODE = 'LPLAN-DEMO-WF'


class Command(BaseCommand):
    help = 'Gera projeto, fluxos e processos demo para a Central de Aprovações (sem Sienge).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default=None,
            help='Utilizador que será aprovador nas alçadas (default: primeiro superuser).',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help=f'Apaga o projeto {DEMO_PROJECT_CODE!r} e tudo em cascata antes de recriar.',
        )
        parser.add_argument(
            '--grant-group',
            action='store_true',
            help=f'Adiciona o grupo {GRUPOS.CENTRAL_APROVACOES_APROVADOR!r} ao utilizador escolhido.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']

        if options['reset']:
            n, _ = Project.objects.filter(code=DEMO_PROJECT_CODE).delete()
            if n:
                self.stdout.write(self.style.WARNING(f'Removido projeto demo (e dependentes).'))

        user = None
        if username:
            user = User.objects.filter(username=username).first()
            if not user:
                self.stderr.write(self.style.ERROR(f'Utilizador {username!r} não encontrado.'))
                return
        else:
            user = User.objects.filter(is_superuser=True).order_by('id').first()
            if not user:
                user = User.objects.filter(is_staff=True).order_by('id').first()
        if not user:
            self.stderr.write(
                self.style.ERROR(
                    'Nenhum superuser/staff encontrado. Crie um utilizador ou use --username.'
                )
            )
            return

        if options['grant_group']:
            from django.contrib.auth.models import Group

            g = Group.objects.filter(name=GRUPOS.CENTRAL_APROVACOES_APROVADOR).first()
            if g:
                user.groups.add(g)
                self.stdout.write(self.style.SUCCESS(f'Grupo {GRUPOS.CENTRAL_APROVACOES_APROVADOR} atribuído a {user.username}.'))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'Grupo {GRUPOS.CENTRAL_APROVACOES_APROVADOR!r} não existe. Rode: python manage.py setup_groups'
                    )
                )

        today = date.today()
        project, p_created = Project.objects.get_or_create(
            code=DEMO_PROJECT_CODE,
            defaults={
                'name': '[DEMO] Obra — Central de Aprovações',
                'description': 'Projeto fictício só para testes locais da Central (sem Sienge).',
                'address': 'Endereço fictício, 100 — Bairro Demo',
                'responsible': 'Responsável Demo',
                'contract_number': 'CT-2026-DEMO-001',
                'client_name': 'Cliente Genérico S.A.',
                'start_date': today,
                'end_date': today + timedelta(days=540),
                'is_active': True,
            },
        )
        if not p_created:
            self.stdout.write(self.style.WARNING(f'Projeto {DEMO_PROJECT_CODE} já existia; atualizando metadados opcionais.'))
            project.name = '[DEMO] Obra — Central de Aprovações'
            project.contract_number = project.contract_number or 'CT-2026-DEMO-001'
            project.client_name = project.client_name or 'Cliente Genérico S.A.'
            project.save()

        # Idempotente: remove fluxos/processos demo deste projeto para recriar sem conflito (FK PROTECT nas alçadas).
        np, _ = ApprovalProcess.objects.filter(project=project).delete()
        nf, _ = ApprovalFlowDefinition.objects.filter(project=project).delete()
        if np or nf:
            self.stdout.write(f'  (Limpeza) {np} processo(s), {nf} definição(ões) de fluxo removidos do demo.')

        specs = [
            ('contrato', 'Contrato — suprimentos estrutura (demo)', True),
            ('bm', 'BM — adequação hidráulica bloco A (demo)', False),
            ('medicao', 'Medição — competência ref. 03/2026 (demo)', False),
        ]

        for cat_code, title, two_steps in specs:
            cat = ProcessCategory.objects.filter(code=cat_code, is_active=True).first()
            if not cat:
                self.stderr.write(self.style.ERROR(f'Categoria {cat_code!r} inexistente. Rode migrações workflow_aprovacao.'))
                continue

            flow = ApprovalFlowDefinition.objects.create(
                project=project,
                category=cat,
                is_active=True,
            )

            if two_steps:
                s1 = ApprovalStep.objects.create(
                    flow=flow,
                    sequence=1,
                    name='Alçada — Revisão técnica',
                    approval_policy=ApprovalPolicy.SINGLE_ANY,
                )
                s2 = ApprovalStep.objects.create(
                    flow=flow,
                    sequence=2,
                    name='Alçada — Assinatura contratual',
                    approval_policy=ApprovalPolicy.SINGLE_ANY,
                )
                for st in (s1, s2):
                    ApprovalStepParticipant.objects.create(
                        step=st,
                        role=ParticipantRole.APPROVER,
                        subject_kind=SubjectKind.USER,
                        user=user,
                    )
            else:
                s1 = ApprovalStep.objects.create(
                    flow=flow,
                    sequence=1,
                    name='Alçada única',
                    approval_policy=ApprovalPolicy.SINGLE_ANY,
                )
                ApprovalStepParticipant.objects.create(
                    step=s1,
                    role=ParticipantRole.APPROVER,
                    subject_kind=SubjectKind.USER,
                    user=user,
                )

            proc = ApprovalEngine.start(
                project=project,
                category=cat,
                initiated_by=user,
                title=title,
                summary='Processo gerado por `manage.py seed_workflow_demo`. Integração externa desligada.',
                external_id='',
                external_entity_type='demo_local',
                sync_status=SyncStatus.NOT_APPLICABLE,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'  [{cat_code}] fluxo + processo #{proc.pk} — {title}'
                )
            )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Concluído.'))
        self.stdout.write(f'  Projeto: {project.code} — {project.name}')
        self.stdout.write(f'  Aprovador nas alçadas: {user.username}')
        self.stdout.write('  Abra: /aprovacoes/fila/ (com utilizador no grupo Central ou superuser).')
