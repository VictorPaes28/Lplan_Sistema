"""
Apaga TODOS os dados de todos os sistemas: obras, projetos, pedidos, diários,
vínculos e, opcionalmente, usuários. Use para começar do zero.

Uso:
    python manage.py zerar_tudo              # Apaga tudo exceto superusers
    python manage.py zerar_tudo --usuarios   # Apaga também todos os usuários (depois rode createsuperuser)
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User

from core.models import (
    Project,
    ProjectMember,
    Activity,
    ConstructionDiary,
    DiaryEditLog,
    DiaryView,
    DiarySignature,
    DiaryImage,
    DailyWorkLog,
    DiaryVideo,
    DiaryAttachment,
    DiaryOccurrence,
)
from gestao_aprovacao.models import (
    Empresa,
    Obra,
    WorkOrder,
    Approval,
    Attachment,
    StatusHistory,
    WorkOrderPermission,
    UserEmpresa,
    Notificacao,
    Comment,
    EmailLog,
    Lembrete,
)
from mapa_obras.models import Obra as ObraMapa, LocalObra


class Command(BaseCommand):
    help = 'Apaga todos os dados (obras, projetos, pedidos, usuários, etc.) de todos os sistemas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--usuarios',
            action='store_true',
            help='Apagar também todos os usuários (depois execute python manage.py createsuperuser)',
        )

    def handle(self, *args, **options):
        apagar_usuarios = options['usuarios']
        self.stdout.write(self.style.WARNING('Zerando TODOS os dados...'))

        with transaction.atomic():
            self._limpar_gestao()
            self._limpar_core()
            self._limpar_suprimentos()
            self._limpar_mapa()
            if apagar_usuarios:
                self._limpar_usuarios()
            else:
                self.stdout.write('  Usuários mantidos (use --usuarios para apagar também).')

        self.stdout.write(self.style.SUCCESS('Concluído. Banco zerado.'))
        if apagar_usuarios:
            self.stdout.write(self.style.WARNING('Execute: python manage.py createsuperuser'))

    def _limpar_gestao(self):
        self.stdout.write('  Limpando GestControll...')
        EmailLog.objects.all().delete()
        Notificacao.objects.all().delete()
        Comment.objects.all().delete()
        Lembrete.objects.all().delete()
        Approval.objects.all().delete()
        Attachment.objects.all().delete()
        StatusHistory.objects.all().delete()
        WorkOrderPermission.objects.all().delete()
        WorkOrder.objects.all().delete()
        UserEmpresa.objects.all().delete()
        Obra.objects.all().delete()
        Empresa.objects.all().delete()

    def _limpar_core(self):
        self.stdout.write('  Limpando Diário de Obra (core)...')
        DiaryAttachment.objects.all().delete()
        DiaryVideo.objects.all().delete()
        DailyWorkLog.objects.all().delete()
        DiaryImage.objects.all().delete()
        DiarySignature.objects.all().delete()
        DiaryView.objects.all().delete()
        DiaryEditLog.objects.all().delete()
        DiaryOccurrence.objects.all().delete()
        ConstructionDiary.objects.all().delete()
        Activity.objects.all().delete()
        ProjectMember.objects.all().delete()
        Project.objects.all().delete()

    def _limpar_mapa(self):
        self.stdout.write('  Limpando Mapa de Obras...')
        LocalObra.objects.all().delete()
        ObraMapa.objects.all().delete()

    def _limpar_suprimentos(self):
        try:
            from suprimentos.models import AlocacaoRecebimento, RecebimentoObra, ItemMapa, Insumo
        except ImportError:
            return
        self.stdout.write('  Limpando Suprimentos...')
        AlocacaoRecebimento.objects.all().delete()
        RecebimentoObra.objects.all().delete()
        ItemMapa.objects.all().delete()
        Insumo.objects.all().delete()

    def _limpar_usuarios(self):
        self.stdout.write('  Limpando Usuários...')
        # Remove de grupos antes de apagar
        for u in User.objects.all():
            u.groups.clear()
        User.objects.all().delete()
