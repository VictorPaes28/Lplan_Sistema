"""
Reset do ambiente LOCAL: apaga dados operacionais e recria exatamente 4 obras LPLAN
100%% populadas (todos os módulos principais).

Só executa com DEBUG=True.

Uso:
    python manage.py reset_local_4_obras
    python manage.py reset_local_4_obras --confirmar
    python manage.py reset_local_4_obras --confirmar --dias-diarios 45
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

OBRAS_4 = [
    ("224", "Entreáguas", "Incorporadora Adamo", "Eng. Antônio Azevedo"),
    ("242", "Okena", "JP Empreendimentos", "Eng. Stanisley Costa"),
    ("259", "Marghot", "Antonina Hotéis", "Eng. Maria Santos"),
    ("260", "Sunrise", "Rpontes", "Eng. Ricardo Oliveira"),
]

def _require_local():
    if not getattr(settings, "DEBUG", False):
        raise CommandError("Este comando só pode rodar com DEBUG=True (ambiente local).")


def _wipe_operational_data(stdout, style):
    """Remove dados operacionais; mantém User, Group e catálogos globais de referência."""

    def log(msg):
        stdout.write(f"   OK {msg}")

    # --- TrackHub ---
    from trackhub.models import (
        AnexoComentario,
        AnexoEtapa,
        AnexoPendencia,
        AssinaturaEtapa,
        AtividadePendencia,
        ComentarioPendencia,
        EtapaPendencia,
        NotificacaoPendencia,
        NotificacaoPrazoTrackHub,
        Pendencia,
        PendenciaRecorrente,
        TipoCustom,
    )

    AnexoComentario.objects.all().delete()
    AnexoEtapa.objects.all().delete()
    AnexoPendencia.objects.all().delete()
    AssinaturaEtapa.objects.all().delete()
    ComentarioPendencia.objects.all().delete()
    NotificacaoPendencia.objects.all().delete()
    NotificacaoPrazoTrackHub.objects.all().delete()
    AtividadePendencia.objects.all().delete()
    EtapaPendencia.objects.all().delete()
    Pendencia.objects.all().delete()
    PendenciaRecorrente.objects.all().delete()
    TipoCustom.objects.all().delete()
    log("TrackHub")

    # --- Impedimentos ---
    from impedimentos.models import (
        ArquivoImpedimento,
        AtividadeImpedimento,
        ComentarioImpedimento,
        Impedimento,
        ImagemImpedimento,
        CategoriaImpedimento,
        StatusImpedimento,
    )

    ComentarioImpedimento.objects.all().delete()
    AtividadeImpedimento.objects.all().delete()
    ArquivoImpedimento.objects.all().delete()
    ImagemImpedimento.objects.all().delete()
    Impedimento.objects.all().delete()
    CategoriaImpedimento.objects.all().delete()
    StatusImpedimento.objects.all().delete()
    log("Impedimentos / Restrições")

    # --- Painel operacional ---
    from painel_operacional.models import (
        AmbienteCelula,
        AmbienteElemento,
        AmbienteHistorico,
        AmbientePermissao,
        AmbienteVersao,
        AmbienteOperacional,
    )

    AmbienteCelula.objects.all().delete()
    AmbienteElemento.objects.all().delete()
    AmbienteHistorico.objects.all().delete()
    AmbientePermissao.objects.all().delete()
    AmbienteVersao.objects.all().delete()
    AmbienteOperacional.objects.all().delete()
    log("Ferramenta de Ambientes")

    # --- Mapa geo ---
    from mapa_geo.models import GeoFeature, GeoObraConfig

    GeoFeature.objects.all().delete()
    GeoObraConfig.objects.all().delete()
    log("Mapa Geográfico")

    # --- Gestão: dispatch central antes de workflow e work orders ---
    from gestao_aprovacao.models import GestaoCentralDispatch

    GestaoCentralDispatch.objects.all().delete()
    log("Gestão Central dispatch")

    # --- Workflow central (antes de Projects) ---
    from workflow_aprovacao.models import (
        ApprovalProcessAttachment,
        ApprovalHistoryEntry,
        ApprovalProcessParticipant,
        ExternalParticipantSignupRequest,
        ApprovalIntegrationOutbox,
        SiengeCentralSyncState,
        ApprovalProcess,
        ApprovalConfigBacklog,
        ApprovalStepParticipant,
        ApprovalStep,
        ApprovalFlowDefinition,
    )

    ExternalParticipantSignupRequest.objects.all().delete()
    ApprovalProcessAttachment.objects.all().delete()
    ApprovalHistoryEntry.objects.all().delete()
    ApprovalProcessParticipant.objects.all().delete()
    ApprovalIntegrationOutbox.objects.all().delete()
    SiengeCentralSyncState.objects.all().delete()
    ApprovalProcess.objects.all().delete()
    ApprovalConfigBacklog.objects.all().delete()
    ApprovalStepParticipant.objects.all().delete()
    ApprovalStep.objects.all().delete()
    ApprovalFlowDefinition.objects.all().delete()
    log("Central de Aprovações (workflow)")

    # --- RH: obras locais (FK gestão) ---
    from recursos_humanos.models import ObraLocal

    ObraLocal.objects.all().delete()
    log("Obras RH (locais)")

    # --- Gestão ---
    from gestao_aprovacao.models import (
        Notificacao,
        Lembrete,
        Approval,
        Comment,
        Attachment,
        StatusHistory,
        EmailLog,
        WorkOrder,
        WorkOrderPermission,
        UserEmpresa,
        Obra as ObraGestao,
        Empresa,
    )

    Notificacao.objects.all().delete()
    Lembrete.objects.all().delete()
    Approval.objects.all().delete()
    Comment.objects.all().delete()
    Attachment.objects.all().delete()
    StatusHistory.objects.all().delete()
    EmailLog.objects.all().delete()
    WorkOrder.objects.all().delete()
    WorkOrderPermission.objects.all().delete()
    UserEmpresa.objects.all().delete()
    ObraGestao.objects.all().delete()
    Empresa.objects.all().delete()
    log("Gestão de Aprovações")

    # --- Core ---
    from core.models import (
        Notification,
        DiaryComment,
        DiaryEditLog,
        DiaryView,
        DiarySignature,
        DiaryImage,
        DiaryVideo,
        DiaryAttachment,
        DailyWorkLogEquipment,
        DailyWorkLog,
        DiaryLaborEntry,
        DiaryOccurrence,
        ConstructionDiary,
        Activity,
        ProjectDiaryRecipient,
        ProjectOwner,
        ProjectMember,
        ProjectFront,
        Project,
    )

    Notification.objects.all().delete()
    DiaryComment.objects.all().delete()
    DiaryEditLog.objects.all().delete()
    DiaryView.objects.all().delete()
    DiarySignature.objects.all().delete()
    DiaryImage.objects.all().delete()
    DiaryVideo.objects.all().delete()
    DiaryAttachment.objects.all().delete()
    DailyWorkLogEquipment.objects.all().delete()
    DailyWorkLog.objects.all().delete()
    DiaryLaborEntry.objects.all().delete()
    DiaryOccurrence.objects.all().delete()
    ConstructionDiary.objects.all().delete()
    for root in Activity.get_root_nodes():
        root.delete()
    ProjectDiaryRecipient.objects.all().delete()
    ProjectOwner.objects.all().delete()
    ProjectMember.objects.all().delete()
    ProjectFront.objects.all().delete()
    Project.objects.all().delete()
    log("Diário de Obra / Projetos")

    # --- Suprimentos + BI snapshots ---
    from suprimentos.models import (
        AlocacaoRecebimento,
        NotaFiscalEntrada,
        HistoricoAlteracao,
        ImportacaoSienge,
        ImportacaoMapaServico,
        ItemMapa,
        RecebimentoObra,
        ItemMapaServico,
        ItemMapaServicoStatusRef,
        BiObraKpiSnapshot,
        Insumo,
    )

    BiObraKpiSnapshot.objects.all().delete()
    AlocacaoRecebimento.objects.all().delete()
    NotaFiscalEntrada.objects.all().delete()
    HistoricoAlteracao.objects.all().delete()
    ImportacaoSienge.objects.all().delete()
    ImportacaoMapaServico.objects.all().delete()
    ItemMapaServico.objects.all().delete()
    ItemMapaServicoStatusRef.objects.all().delete()
    ItemMapa.objects.all().delete()
    RecebimentoObra.objects.all().delete()
    Insumo.objects.all().delete()
    log("Suprimentos / Mapa de Controle legado / BI snapshots")

    # --- Mapa obras ---
    from mapa_obras.models import LocalObra, Obra as ObraMapa

    LocalObra.objects.all().delete()
    ObraMapa.objects.all().delete()
    log("Obras (mapa_obras)")

    stdout.write(style.SUCCESS("\nLimpeza concluída. Usuários e grupos mantidos.\n"))


def _create_obras_and_projects():
    from core.models import Project
    from mapa_obras.models import Obra as ObraMapa

    hoje = date.today()
    fim = date(hoje.year + 2, 12, 31)
    obras_mapa = []
    projects = []
    for codigo, nome, contratante, responsavel in OBRAS_4:
        display = f"{nome} ({contratante})" if contratante else nome
        proj = Project.objects.create(
            code=codigo,
            name=display,
            is_active=True,
            client_name=contratante or "",
            start_date=hoje,
            end_date=fim,
            responsible=responsavel or "Engenheiro Responsável",
        )
        projects.append(proj)
        om = ObraMapa.objects.create(
            codigo_sienge=codigo,
            nome=display,
            ativa=True,
            project=proj,
        )
        obras_mapa.append(om)
    return obras_mapa, projects


def _create_ambientes_mapa_controle(obras_mapa, user):
    from core.demo_mapa_controle_data import build_mapa_controle_layout
    from painel_operacional.models import (
        AmbienteModoEditor,
        AmbienteOperacional,
        AmbienteTipo,
        AmbienteVersao,
        VersaoEstado,
    )

    created = 0
    for obra in obras_mapa:
        amb = AmbienteOperacional.objects.create(
            obra=obra,
            nome=f"Mapa de Controle — {obra.nome.split('(')[0].strip()}",
            tipo=AmbienteTipo.MAPA_CONTROLE,
            modo_editor=AmbienteModoEditor.MAPA_DEDICADO,
            criado_por=user,
            ativo=True,
        )
        AmbienteVersao.objects.create(
            ambiente=amb,
            numero=1,
            estado=VersaoEstado.DRAFT,
            layout=build_mapa_controle_layout(obra.id),
            metadados={"preset": "mapa_controle", "seed": "reset_local_4_obras"},
        )
        created += 1
    return created


def _create_impedimentos(obras_gestao, user):
    from impedimentos.models import CategoriaImpedimento, Impedimento, StatusImpedimento

    titulos = [
        "Atraso na entrega de steel frame",
        "Liberação de frente de serviço Bloco B",
        "Projeto executivo hidráulico pendente",
        "Interferência com rede elétrica externa",
        "Falta de mão de obra especializada",
    ]
    total = 0
    for og in obras_gestao:
        statuses = []
        for nome, cor, ordem, is_def in [
            ("Aberto", "#EF4444", 1, True),
            ("Em andamento", "#F59E0B", 2, False),
            ("Resolvido", "#10B981", 3, False),
        ]:
            st = StatusImpedimento.objects.create(
                obra=og, nome=nome, cor=cor, ordem=ordem, is_default=is_def
            )
            statuses.append(st)
        cats = []
        for nome, cor in [("Projeto", "#3B82F6"), ("Fornecedor", "#8B5CF6"), ("Clima", "#06B6D4")]:
            cats.append(
                CategoriaImpedimento.objects.create(
                    obra=og, nome=nome, cor=cor, criado_por=user
                )
            )
        for i, titulo in enumerate(titulos):
            imp = Impedimento.objects.create(
                obra=og,
                titulo=titulo,
                descricao="Restrição de demonstração gerada pelo reset local.",
                status=statuses[i % len(statuses)],
                criado_por=user,
                prioridade=random.choice(
                    [
                        Impedimento.PRIORIDADE_NORMAL,
                        Impedimento.PRIORIDADE_ALTA,
                        Impedimento.PRIORIDADE_CRITICA,
                    ]
                ),
                prazo=date.today() + timedelta(days=random.randint(3, 30)),
            )
            imp.categorias.add(cats[i % len(cats)])
            imp.responsaveis.add(user)
            total += 1
    return total


def _create_mapa_geo(projects):
    from mapa_geo.models import GeoFeature, GeoObraConfig

    coords = [
        (-23.5505, -46.6333),
        (-22.9068, -43.1729),
        (-25.4284, -49.2733),
        (-27.5954, -48.5480),
    ]
    total = 0
    for idx, proj in enumerate(projects):
        lat, lng = coords[idx % len(coords)]
        GeoObraConfig.objects.create(
            project=proj,
            center_latitude=Decimal(str(lat)),
            center_longitude=Decimal(str(lng)),
            default_zoom=14,
            import_label="Demo reset local",
        )
        for j in range(3):
            dlat = Decimal(str(lat + j * 0.001))
            dlng = Decimal(str(lng + j * 0.002))
            GeoFeature.objects.create(
                project=proj,
                name=f"Ponto demo {j + 1} — {proj.code}",
                geometry_type="Point",
                geometry=[float(dlng), float(dlat)],
                latitude=dlat,
                longitude=dlng,
                status=random.choice(["planned", "in_progress", "completed"]),
                kind=random.choice(["point", "segment", "vistoria"]),
                description="Feature de demonstração (reset local).",
            )
            total += 1
    return total


def _create_trackhub(obras_mapa, user):
    from trackhub.models import Pendencia

    total = 0
    for obra in obras_mapa:
        for i in range(1, 4):
            Pendencia.objects.create(
                obra=obra,
                titulo=f"Pendência demo {i} — {obra.codigo_sienge}",
                descricao="Gerada pelo reset local para demonstração do TrackHub.",
                tipo=random.choice(["operacional", "documento", "financeiro"]),
                status=random.choice(["aberta", "em_andamento", "concluida"]),
                prioridade=random.choice(["normal", "alta"]),
                criado_por=user,
                prazo=date.today() + timedelta(days=random.randint(5, 20)),
            )
            total += 1
    return total


def _link_all_staff(projects):
    from core.models import ProjectMember, ProjectOwner

    users = list(User.objects.filter(is_active=True, is_staff=True)[:20])
    if not users:
        users = list(User.objects.filter(is_active=True)[:5])
    for proj in projects:
        for u in users:
            ProjectMember.objects.get_or_create(user=u, project=proj)
        if users:
            ProjectOwner.objects.get_or_create(project=proj, user=users[0])


class Command(BaseCommand):
    help = (
        "Ambiente LOCAL: limpa o banco e recria 4 obras LPLAN totalmente populadas "
        "(Diário, Suprimentos, Mapa Controle, Ferramenta, Gestão, Restrições, Geo, TrackHub)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Executa a limpeza e o seed (sem isso, só mostra preview).",
        )
        parser.add_argument(
            "--dias-diarios",
            type=int,
            default=45,
            help="Dias de diário de obra para gerar (padrão: 45).",
        )

    def handle(self, *args, **options):
        _require_local()
        confirmar = options["confirmar"]
        dias_diarios = max(1, min(int(options["dias_diarios"]), 120))

        from mapa_obras.models import Obra as ObraMapa
        from core.models import Project

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "\n=== Reset local — 4 obras LPLAN totalmente populadas ===\n"
            )
        )
        self.stdout.write(f"Obras alvo: {[o[1] for o in OBRAS_4]}")
        self.stdout.write(
            f"Estado atual: {ObraMapa.objects.count()} obras mapa, "
            f"{Project.objects.count()} projetos.\n"
        )

        if not confirmar:
            self.stdout.write(
                self.style.WARNING(
                    "Modo preview. Para executar:\n"
                    "   python manage.py reset_local_4_obras --confirmar\n"
                )
            )
            return

        from core.management.commands.seed_dados_demo_completo import (
            create_diaries_with_photos,
            create_eap,
            create_gestao_aprovacao_data,
            create_insumos,
            create_locais_for_obra,
            create_mapa_and_recebimentos,
            create_mapa_servico_controle,
            create_occurrences_and_tags,
            ensure_groups,
            ensure_labor_equipment_categories,
            get_or_create_demo_user,
            link_user_to_projects,
        )

        with transaction.atomic():
            self.stdout.write(self.style.WARNING("Fase 1/3 — limpando dados operacionais...\n"))
            _wipe_operational_data(self.stdout, self.style)

            self.stdout.write(self.style.WARNING("Fase 2/3 — criando 4 obras e módulos base...\n"))
            ensure_groups()
            user = get_or_create_demo_user()
            self.stdout.write(self.style.SUCCESS(f"Usuário seed: {user.username}"))

            obras_mapa, projects = _create_obras_and_projects()
            link_user_to_projects(projects, user)
            _link_all_staff(projects)
            ensure_labor_equipment_categories(dry_run=False)

            for obra in obras_mapa:
                n = len(create_locais_for_obra(obra))
                self.stdout.write(f"  {obra.nome}: {n} locais")

            insumos = create_insumos()
            create_mapa_and_recebimentos(obras_mapa, insumos, user, dry_run=False)
            n_ms = create_mapa_servico_controle(obras_mapa, dry_run=False)
            self.stdout.write(f"  ItemMapaServico: {n_ms} linhas")

            for proj in projects:
                create_eap(proj, dry_run=False)

            n_diaries = create_diaries_with_photos(
                projects, user, num_days=dias_diarios, dry_run=False
            )
            create_occurrences_and_tags(projects, user, dry_run=False)
            n_gestao = create_gestao_aprovacao_data(projects, user, dry_run=False) or 0

            self.stdout.write(self.style.WARNING("Fase 3/3 — módulos complementares...\n"))
            n_amb = _create_ambientes_mapa_controle(obras_mapa, user)
            from core.demo_mapa_controle_data import ATIVIDADES_MAPA, count_unidades_demo

            n_linhas = count_unidades_demo()
            self.stdout.write(
                f"  Mapa controle: {n_amb} ambientes × {n_linhas} unidades × "
                f"{len(ATIVIDADES_MAPA)} atividades"
            )
            from gestao_aprovacao.models import Obra as ObraGestao

            obras_gestao = list(ObraGestao.objects.filter(codigo__in=[o[0] for o in OBRAS_4]))
            n_imp = _create_impedimentos(obras_gestao, user)
            n_geo = _create_mapa_geo(projects)
            n_th = _create_trackhub(obras_mapa, user)

        try:
            call_command("bi_obra_snapshot", verbosity=0)
            bi_ok = True
        except Exception as exc:
            bi_ok = False
            self.stdout.write(self.style.WARNING(f"bi_obra_snapshot: {exc}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Reset concluído."))
        self.stdout.write(f"  Obras mapa: {ObraMapa.objects.count()}")
        self.stdout.write(f"  Projetos: {Project.objects.count()}")
        self.stdout.write(f"  Diários novos: {n_diaries}")
        self.stdout.write(f"  Pedidos gestão: {n_gestao}")
        self.stdout.write(f"  Ambientes mapa controle: {n_amb}")
        self.stdout.write(f"  Restrições: {n_imp}")
        self.stdout.write(f"  Features geo: {n_geo}")
        self.stdout.write(f"  Pendências TrackHub: {n_th}")
        if bi_ok:
            self.stdout.write("  Snapshots BI: gerados")
        self.stdout.write(
            self.style.SUCCESS(
                "\nAcesse com seu usuário staff (ou demo/demo1234). "
                "Obras: Entreáguas, Okena, Marghot, Sunrise.\n"
            )
        )
