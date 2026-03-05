"""
Comando para limpar todos os dados operacionais do servidor, mantendo apenas usuários e grupos.

Remove (nesta ordem, por dependências de FK):
- Gestão: Notificacao, Lembrete, Approval, Comment, Attachment, StatusHistory, EmailLog, WorkOrder,
  WorkOrderPermission, UserEmpresa, Obra (gestão), Empresa
- Core: Notification, DiaryComment, DiaryEditLog, DiaryView, DiarySignature, DiaryImage,
  DailyWorkLogEquipment, DailyWorkLog, DiaryLaborEntry, DiaryOccurrence, ConstructionDiary,
  Activity (EAP), ProjectDiaryRecipient, ProjectOwner, ProjectMember, Project
- Mapa Obras: LocalObra, Obra (mapa_obras)
- Suprimentos: AlocacaoRecebimento, NotaFiscalEntrada, HistoricoAlteracao, ItemMapa,
  RecebimentoObra, Insumo

Mantém: User, Group (e UserProfile se existir — opcional manter).

Uso:
    python manage.py limpar_dados_servidor
    python manage.py limpar_dados_servidor --confirmar
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Apaga todos os dados operacionais do servidor (projetos, diários, pedidos, mapa, etc.), mantendo usuários e grupos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma a exclusão (sem isso, apenas mostra o que será removido)',
        )

    def handle(self, *args, **options):
        confirmar = options.get('confirmar', False)

        if not confirmar:
            self.stdout.write(self.style.WARNING(
                '\nMODO SIMULAÇÃO - Nada será removido.\n'
                'Use --confirmar para realmente apagar.\n'
            ))

        # Contagens para preview
        from django.contrib.auth.models import User, Group
        from core.models import (
            Notification, DiaryComment, DiaryEditLog, DiaryView, DiarySignature,
            DiaryImage, DailyWorkLogEquipment, DailyWorkLog, DiaryLaborEntry, DiaryOccurrence,
            ConstructionDiary, Activity, ProjectDiaryRecipient, ProjectOwner, ProjectMember, Project,
        )
        from gestao_aprovacao.models import (
            Notificacao, Lembrete, Approval, Comment, Attachment, StatusHistory,
            EmailLog, WorkOrder, WorkOrderPermission, UserEmpresa, Obra as ObraGestao, Empresa,
        )
        from mapa_obras.models import LocalObra, Obra as ObraMapa
        from suprimentos.models import (
            AlocacaoRecebimento, NotaFiscalEntrada, HistoricoAlteracao,
            ItemMapa, RecebimentoObra, Insumo,
        )

        counts = {
            'Notificacao (gestão)': Notificacao.objects.count(),
            'Lembrete': Lembrete.objects.count(),
            'Approval': Approval.objects.count(),
            'Comment': Comment.objects.count(),
            'Attachment': Attachment.objects.count(),
            'StatusHistory': StatusHistory.objects.count(),
            'EmailLog': EmailLog.objects.count(),
            'WorkOrder': WorkOrder.objects.count(),
            'WorkOrderPermission': WorkOrderPermission.objects.count(),
            'UserEmpresa': UserEmpresa.objects.count(),
            'Obra (gestão)': ObraGestao.objects.count(),
            'Empresa': Empresa.objects.count(),
            'Notification (core)': Notification.objects.count(),
            'DiaryComment': DiaryComment.objects.count(),
            'DiaryEditLog': DiaryEditLog.objects.count(),
            'DiaryView': DiaryView.objects.count(),
            'DiarySignature': DiarySignature.objects.count(),
            'DiaryImage': DiaryImage.objects.count(),
            'DailyWorkLogEquipment': DailyWorkLogEquipment.objects.count(),
            'DailyWorkLog': DailyWorkLog.objects.count(),
            'DiaryLaborEntry': DiaryLaborEntry.objects.count(),
            'DiaryOccurrence': DiaryOccurrence.objects.count(),
            'ConstructionDiary': ConstructionDiary.objects.count(),
            'Activity': Activity.objects.count(),
            'ProjectDiaryRecipient': ProjectDiaryRecipient.objects.count(),
            'ProjectOwner': ProjectOwner.objects.count(),
            'ProjectMember': ProjectMember.objects.count(),
            'Project': Project.objects.count(),
            'LocalObra': LocalObra.objects.count(),
            'Obra (mapa)': ObraMapa.objects.count(),
            'AlocacaoRecebimento': AlocacaoRecebimento.objects.count(),
            'NotaFiscalEntrada': NotaFiscalEntrada.objects.count(),
            'HistoricoAlteracao': HistoricoAlteracao.objects.count(),
            'ItemMapa': ItemMapa.objects.count(),
            'RecebimentoObra': RecebimentoObra.objects.count(),
            'Insumo': Insumo.objects.count(),
        }

        self.stdout.write(self.style.SUCCESS('\nO QUE SERÁ REMOVIDO:\n'))
        for name, n in counts.items():
            self.stdout.write(f'   {name}: {n}')
        self.stdout.write(f'\n   (Mantidos: User={User.objects.count()}, Group={Group.objects.count()})\n')

        if not confirmar:
            self.stdout.write(self.style.WARNING(
                'Para executar a exclusão:\n'
                '   python manage.py limpar_dados_servidor --confirmar\n'
            ))
            return

        self.stdout.write(self.style.WARNING('\nApagando...\n'))

        with transaction.atomic():
            # --- Gestão (ordem por FK) ---
            Notificacao.objects.all().delete()
            self.stdout.write('   OK Notificacao (gestão)')
            Lembrete.objects.all().delete()
            self.stdout.write('   OK Lembrete')
            Approval.objects.all().delete()
            self.stdout.write('   OK Approval')
            Comment.objects.all().delete()
            self.stdout.write('   OK Comment')
            Attachment.objects.all().delete()
            self.stdout.write('   OK Attachment')
            StatusHistory.objects.all().delete()
            self.stdout.write('   OK StatusHistory')
            EmailLog.objects.all().delete()
            self.stdout.write('   OK EmailLog')
            WorkOrder.objects.all().delete()
            self.stdout.write('   OK WorkOrder')
            WorkOrderPermission.objects.all().delete()
            self.stdout.write('   OK WorkOrderPermission')
            UserEmpresa.objects.all().delete()
            self.stdout.write('   OK UserEmpresa')
            ObraGestao.objects.all().delete()
            self.stdout.write('   OK Obra (gestão)')
            Empresa.objects.all().delete()
            self.stdout.write('   OK Empresa')

            # --- Core ---
            Notification.objects.all().delete()
            self.stdout.write('   OK Notification (core)')
            DiaryComment.objects.all().delete()
            self.stdout.write('   OK DiaryComment')
            DiaryEditLog.objects.all().delete()
            self.stdout.write('   OK DiaryEditLog')
            DiaryView.objects.all().delete()
            self.stdout.write('   OK DiaryView')
            DiarySignature.objects.all().delete()
            self.stdout.write('   OK DiarySignature')
            DiaryImage.objects.all().delete()
            self.stdout.write('   OK DiaryImage')
            # DiaryVideo, DiaryAttachment (FK diary)
            from core.models import DiaryVideo, DiaryAttachment
            DiaryVideo.objects.all().delete()
            DiaryAttachment.objects.all().delete()
            self.stdout.write('   OK DiaryVideo, DiaryAttachment')
            DailyWorkLogEquipment.objects.all().delete()
            self.stdout.write('   OK DailyWorkLogEquipment')
            DailyWorkLog.objects.all().delete()
            self.stdout.write('   OK DailyWorkLog')
            DiaryLaborEntry.objects.all().delete()
            self.stdout.write('   OK DiaryLaborEntry')
            DiaryOccurrence.objects.all().delete()
            self.stdout.write('   OK DiaryOccurrence')
            ConstructionDiary.objects.all().delete()
            self.stdout.write('   OK ConstructionDiary')
            # Activity: árvore treebeard — deletar raízes remove os filhos
            for root in Activity.get_root_nodes():
                root.delete()
            self.stdout.write('   OK Activity (EAP)')
            ProjectDiaryRecipient.objects.all().delete()
            self.stdout.write('   OK ProjectDiaryRecipient')
            ProjectOwner.objects.all().delete()
            self.stdout.write('   OK ProjectOwner')
            ProjectMember.objects.all().delete()
            self.stdout.write('   OK ProjectMember')
            Project.objects.all().delete()
            self.stdout.write('   OK Project')

            # --- Mapa Obras ---
            LocalObra.objects.all().delete()
            self.stdout.write('   OK LocalObra')
            ObraMapa.objects.all().delete()
            self.stdout.write('   OK Obra (mapa)')

            # --- Suprimentos ---
            AlocacaoRecebimento.objects.all().delete()
            self.stdout.write('   OK AlocacaoRecebimento')
            NotaFiscalEntrada.objects.all().delete()
            self.stdout.write('   OK NotaFiscalEntrada')
            HistoricoAlteracao.objects.all().delete()
            self.stdout.write('   OK HistoricoAlteracao')
            ItemMapa.objects.all().delete()
            self.stdout.write('   OK ItemMapa')
            RecebimentoObra.objects.all().delete()
            self.stdout.write('   OK RecebimentoObra')
            Insumo.objects.all().delete()
            self.stdout.write('   OK Insumo')

        self.stdout.write(self.style.SUCCESS('\nDados do servidor apagados. Usuários e grupos mantidos.\n'))
