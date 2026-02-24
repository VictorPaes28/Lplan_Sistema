"""
Zera dados de teste e recria um conjunto único: 3 empresas (Entreaguas, Okena, Sunrise)
e as mesmas obras em todos os sistemas (Diário de Obra, GestControll, Mapa de Suprimentos).

Uso:
    python manage.py reset_e_criar_dados

Não apaga usuários nem grupos; apenas dados de negócio (obras, projetos, empresas, pedidos, etc.).
"""
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction

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
)
from mapa_obras.models import Obra as ObraMapa, LocalObra


# Dados únicos para os 3 sistemas
EMPRESAS = [
    {'codigo': 'ENT', 'nome': 'Entreaguas'},
    {'codigo': 'OKN', 'nome': 'Okena'},
    {'codigo': 'SUN', 'nome': 'Sunrise'},
]

# Uma obra por empresa, mesmo código/nome em todo o sistema
OBRAS = [
    {'codigo': 'ENT-01', 'nome': 'Obra Entreaguas', 'empresa_idx': 0},
    {'codigo': 'OKN-01', 'nome': 'Obra Okena', 'empresa_idx': 1},
    {'codigo': 'SUN-01', 'nome': 'Obra Sunrise', 'empresa_idx': 2},
]


class Command(BaseCommand):
    help = 'Zera dados e recria 3 empresas (Entreaguas, Okena, Sunrise) com obras unificadas em todos os sistemas'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Zerando dados de todos os sistemas...'))

        with transaction.atomic():
            self._limpar_gestao()
            self._limpar_core()
            self._limpar_suprimentos()  # antes do mapa: AlocacaoRecebimento referencia LocalObra
            self._limpar_mapa()

            self.stdout.write(self.style.SUCCESS('Dados zerados.'))

            self.stdout.write('Criando empresas e obras unificadas...')
            empresas = self._criar_empresas()
            projects = self._criar_projetos()
            self._criar_obras_gestao(empresas, projects)
            self._criar_obras_mapa(projects)

            self.stdout.write(self.style.SUCCESS('\nConcluído.'))
            self.stdout.write('  Empresas: Entreaguas (ENT), Okena (OKN), Sunrise (SUN)')
            self.stdout.write('  Obras: ENT-01, OKN-01, SUN-01 (mesmo nome no Diário, GestControll e Mapa)')
            self.stdout.write('  Vincule usuários às obras em GestControll → Usuários → Editar → Obras.')

    def _limpar_gestao(self):
        self.stdout.write('  Limpando GestControll...')
        EmailLog.objects.all().delete()
        Notificacao.objects.all().delete()
        Comment.objects.all().delete()
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

    def _criar_empresas(self):
        empresas = []
        for e in EMPRESAS:
            emp = Empresa.objects.create(
                codigo=e['codigo'],
                nome=e['nome'],
                ativo=True,
            )
            empresas.append(emp)
            self.stdout.write(f'    Empresa: {emp.codigo} - {emp.nome}')
        return empresas

    def _criar_projetos(self):
        hoje = date.today()
        projects = []
        for o in OBRAS:
            proj = Project.objects.create(
                code=o['codigo'],
                name=o['nome'],
                is_active=True,
                start_date=hoje,
                end_date=hoje + timedelta(days=365),
            )
            projects.append(proj)
            self.stdout.write(f'    Projeto (Diário): {proj.code} - {proj.name}')
        return projects

    def _criar_obras_gestao(self, empresas, projects):
        for i, o in enumerate(OBRAS):
            emp = empresas[o['empresa_idx']]
            proj = projects[i]
            Obra.objects.create(
                empresa=emp,
                project=proj,
                codigo=o['codigo'],
                nome=o['nome'],
                ativo=True,
            )
            self.stdout.write(f'    Obra (GestControll): {o["codigo"]} - {o["nome"]} → {emp.codigo}')

    def _criar_obras_mapa(self, projects):
        for proj in projects:
            ObraMapa.objects.create(
                codigo_sienge=proj.code,
                nome=proj.name,
                ativa=True,
            )
            self.stdout.write(f'    Obra (Mapa): {proj.code} - {proj.name}')
