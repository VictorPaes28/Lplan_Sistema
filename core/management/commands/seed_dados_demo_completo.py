"""
Gera dados de teste completos para ambiente LOCAL (desenvolvimento/screencasts).

Executa SOMENTE quando DEBUG=True. Não roda em produção.

Popula:
- Obras LPLAN (Entreáguas, Okena, Marghot, Sunrise) + locais (blocos, pavimentos)
- Insumos variados
- SCs / Recebimentos e Itens no Mapa de Suprimentos (com e sem SC, com alocações, etc.)
- Mapa de serviço (ItemMapaServico + referências de status) para Mapa de Controle e BI da Obra
- Diário de Obras: vários diários (por padrão ~últimos 32 dias), fotos (placeholder), descrições, clima, progresso, ocorrências

Uso:
    python manage.py seed_dados_demo_completo
    python manage.py seed_dados_demo_completo --dias-diarios 32
    python manage.py seed_dados_demo_completo --dry-run

Requisitos: DEBUG=True no settings (ou .env). Migrations aplicadas.
"""
import base64
import random
from datetime import date, timedelta, datetime
from decimal import Decimal, ROUND_FLOOR
from io import BytesIO

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.models import User, Group
from django.core.files.base import ContentFile
from django.utils import timezone

from accounts.groups import GRUPOS
from core.models import (
    Project, ProjectMember, ProjectOwner, ProjectDiaryRecipient,
    Activity, ActivityStatus, ConstructionDiary, DiaryStatus,
    DailyWorkLog, DailyWorkLogEquipment, DiaryLaborEntry, DiaryOccurrence, OccurrenceTag,
    LaborCategory, LaborCargo, DiaryImage, DiaryAttachment,
    EquipmentCategory, StandardEquipment, Equipment,
)
from mapa_obras.models import Obra as ObraMapa, LocalObra
from suprimentos.models import (
    Insumo,
    ItemMapa,
    ItemMapaServico,
    ItemMapaServicoStatusRef,
    RecebimentoObra,
    AlocacaoRecebimento,
    NotaFiscalEntrada,
    HistoricoAlteracao,
)


# 1x1 pixel PNG transparente (base64) - para fotos placeholder no diário
PNG_1X1_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKMIQQAAAABJRU5ErkJggg=="
)


# Obras LPLAN: (codigo_sienge, nome, contratante, responsavel)
OBRAS_LPLAN = [
    ("224", "Entreáguas", "Incorporadora Adamo", "Eng. Antônio Azevedo"),
    ("242", "Okena", "JP Empreendimentos", "Eng. Stanisley Costa"),
    ("259", "Marghot", "Antonina Hotéis", "Eng. Maria Santos"),
    ("260", "Sunrise", "Rpontes", "Eng. Ricardo Oliveira"),
    # Obra extra para demonstrar listagem/filtros
    ("301", "Residencial Vista Verde", "Construtora Beta", "Eng. Carla Mendes"),
]


def _check_local_only():
    """Só permite execução em ambiente local (DEBUG=True)."""
    if not getattr(settings, "DEBUG", False):
        raise CommandError(
            "Este comando só pode ser executado em ambiente LOCAL (DEBUG=True). "
            "Em produção, defina DEBUG=False e não execute seed de dados de teste."
        )


def ensure_groups():
    """Garante que os grupos existam."""
    for name in GRUPOS.TODOS:
        Group.objects.get_or_create(name=name)


def get_or_create_demo_user():
    """Retorna o primeiro superuser ou staff para ser dono dos dados; cria 'demo' se não houver."""
    user = User.objects.filter(is_superuser=True).first() or User.objects.filter(is_staff=True).first()
    if not user:
        user, _ = User.objects.get_or_create(
            username="demo",
            defaults={
                "email": "demo@lplan.com.br",
                "first_name": "Usuário",
                "last_name": "Demo",
                "is_staff": True,
                "is_active": True,
            },
        )
        user.set_password("demo1234")
        user.save()
        grp = Group.objects.filter(name=GRUPOS.ENGENHARIA).first()
        if grp:
            user.groups.add(grp)
    return user


def create_obras_and_projects():
    """Cria ou reutiliza Obra (mapa) e Project (core) para cada obra LPLAN."""
    hoje = date.today()
    fim_placeholder = date(hoje.year + 2, 12, 31)
    obras_mapa = []
    projects = []
    for codigo, nome, contratante, responsavel in OBRAS_LPLAN:
        display = f"{nome} ({contratante})" if contratante else nome
        proj, created = Project.objects.get_or_create(
            code=codigo,
            defaults={
                "name": display,
                "is_active": True,
                "client_name": contratante or "",
                "start_date": hoje,
                "end_date": fim_placeholder,
                "responsible": responsavel or "Engenheiro Responsável",
            },
        )
        if not created and (proj.responsible != (responsavel or "")):
            proj.responsible = responsavel or proj.responsible
            proj.save(update_fields=["responsible"])
        projects.append(proj)

        om, _ = ObraMapa.objects.get_or_create(
            codigo_sienge=codigo,
            defaults={"nome": display, "ativa": True, "project_id": proj.pk},
        )
        if not om.ativa:
            om.ativa = True
            om.save(update_fields=["ativa"])
        if om.project_id != proj.pk:
            om.project_id = proj.pk
            om.save(update_fields=["project"])
        obras_mapa.append(om)
    return obras_mapa, projects


def create_locais_for_obra(obra):
    """Cria locais variados: blocos, pavimentos, setores, área comum, cobertura, subsolo."""
    pais = {}
    for nome, tipo in [
        ("Bloco A", "BLOCO"),
        ("Bloco B", "BLOCO"),
        ("Área comum", "SETOR"),
        ("Cobertura", "OUTRO"),
        ("Subsolo", "OUTRO"),
    ]:
        obj, _ = LocalObra.objects.get_or_create(
            obra=obra, nome=nome, parent=None, defaults={"tipo": tipo}
        )
        pais[nome] = obj
    filhos = [
        ("Pavimento Térreo", "PAVIMENTO", "Bloco A"),
        ("Pavimento 1", "PAVIMENTO", "Bloco A"),
        ("Pavimento 2", "PAVIMENTO", "Bloco A"),
        ("Pavimento 3", "PAVIMENTO", "Bloco A"),
        ("Pavimento Térreo", "PAVIMENTO", "Bloco B"),
        ("Pavimento 1", "PAVIMENTO", "Bloco B"),
        ("Lobby", "SETOR", "Bloco A"),
        ("Setor 1", "SETOR", "Bloco A"),
        ("Setor 2", "SETOR", "Bloco A"),
        ("Hall de entrada", "SETOR", "Bloco A"),
        ("Área técnica", "SETOR", "Bloco B"),
    ]
    for nome, tipo, parent_nome in filhos:
        parent = pais.get(parent_nome)
        if parent:
            LocalObra.objects.get_or_create(
                obra=obra, nome=nome, parent=parent, defaults={"tipo": tipo}
            )
    return list(LocalObra.objects.filter(obra=obra))


def link_user_to_projects(projects, user):
    """Vincula usuário a todos os projetos (para ver obras no Mapa e Diário)."""
    for proj in projects:
        ProjectMember.objects.get_or_create(user=user, project=proj)
    if projects:
        ProjectOwner.objects.get_or_create(project=projects[0], user=user)
        ProjectDiaryRecipient.objects.get_or_create(
            project=projects[0], email=user.email or "demo@lplan.com.br", defaults={"nome": "Demo"}
        )


def create_insumos():
    """Cria catálogo variado de insumos (macroelementos e itens menores)."""
    data = [
        ("5926", "Cimento CP II-32", "kg", True),
        ("7352", "Régua (filtro de linha) com 5 tomadas 2p+t", "UND", False),
        ("15666", "Tubo PVC 100mm esgoto", "m", True),
        ("8801", "Ferragem CA-50 10mm", "kg", True),
        ("12000", "Concreto usinado C25", "m³", True),
        ("4500", "Bloco cerâmico 9x19x19", "UND", True),
        ("3200", "Telha cerâmica", "UND", True),
        ("1001", "Areia média", "m³", True),
        ("1002", "Brita 1", "m³", True),
        ("5500", "Cabo flexível 2,5mm²", "m", True),
        ("7700", "Luminária LED embutida", "UND", False),
        ("2100", "Rejunte flexível", "kg", False),
        ("3300", "Massa corrida", "kg", False),
        ("4100", "Tinta látex branca", "L", False),
        ("5001", "Vergalhão CA-50 12mm", "kg", True),
        ("6100", "Porta de madeira 0,70x2,10", "UND", True),
        ("6200", "Janela de alumínio 1,00x1,20", "UND", True),
        ("7001", "Piso porcelanato 60x60", "m²", True),
        ("7100", "Argamassa colante AC-II", "kg", False),
        ("8100", "Caixa d'água 1000L", "UND", True),
        ("8200", "Bombas centrífugas", "UND", True),
        ("9100", "Quadro de distribuição 24 circuitos", "UND", True),
        ("9200", "Disjuntor bipolar 32A", "UND", False),
    ]
    insumos = []
    for cod, desc, un, macro in data:
        inv, _ = Insumo.objects.get_or_create(
            codigo_sienge=cod,
            defaults={
                "descricao": desc,
                "unidade": un or "UND",
                "eh_macroelemento": macro,
                "ativo": True,
            },
        )
        insumos.append(inv)
    return insumos


def create_mapa_and_recebimentos(obras_mapa, insumos, user, dry_run=False):
    """Cria ItemMapa e RecebimentoObra com situações variadas (com/sem SC, com alocação, etc.)."""
    if dry_run:
        return
    categorias = [
        "FUNDAÇÃO", "ESTRUTURA", "PINTURA", "INSTALAÇÕES ELÉTRICA",
        "ALVENARIA/FECHAMENTO", "INSTALAÇÕES HIDRÁULICA", "REVESTIMENTO DE PAREDE",
    ]
    for obra in obras_mapa:
        locais = list(LocalObra.objects.filter(obra=obra))
        if not locais:
            create_locais_for_obra(obra)
            locais = list(LocalObra.objects.filter(obra=obra))

        # ItemMapa: alguns com SC, alguns sem; alguns com quantidade planejada 0 (sem planejamento)
        for i, insumo in enumerate(insumos):
            local = random.choice(locais) if locais else None
            cat = random.choice(categorias)
            qtd_planejada = Decimal("0") if i % 7 == 0 else Decimal(str(round(random.uniform(10, 500), 2)))
            numero_sc = ""
            numero_pc = ""
            data_sc = None
            data_pc = None
            empresa_fornecedora = ""
            prazo_recebimento = None
            qtd_recebida = Decimal("0")
            if i % 3 != 0:  # 2/3 com SC
                numero_sc = f"SC{80 + (obra.id % 20) + (i % 10)}"
                data_sc = date.today() - timedelta(days=random.randint(10, 90))
                if i % 2 == 0:
                    numero_pc = f"PC-{obra.codigo_sienge}-{100 + i}"
                    data_pc = data_sc + timedelta(days=random.randint(5, 30))
                    empresa_fornecedora = random.choice([
                        "Materiais Construção Ltda", "Ferragens Norte", "Concreto ABC",
                        "Elétrica São Paulo", "Hidráulica Centro",
                    ])
                    prazo_recebimento = date.today() + timedelta(days=random.randint(-10, 30))
                qtd_recebida = Decimal(str(round(random.uniform(0, 150), 2))) if numero_pc else Decimal("0")

            item, created = ItemMapa.objects.get_or_create(
                obra=obra,
                insumo=insumo,
                local_aplicacao=local,
                defaults={
                    "categoria": cat,
                    "prioridade": random.choice(["URGENTE", "ALTA", "MEDIA", "BAIXA"]),
                    "quantidade_planejada": qtd_planejada,
                    "numero_sc": numero_sc,
                    "numero_pc": numero_pc,
                    "data_sc": data_sc,
                    "data_pc": data_pc,
                    "empresa_fornecedora": empresa_fornecedora,
                    "prazo_recebimento": prazo_recebimento,
                    "responsavel": "Eng. Campo" if random.random() > 0.5 else "",
                    "observacao_eng": "Item de demonstração para screencast." if random.random() > 0.7 else "",
                    "nao_aplica": False,
                    "criado_por": user,
                },
            )
            if not created:
                item.categoria = cat
                item.prioridade = random.choice(["URGENTE", "ALTA", "MEDIA", "BAIXA"])
                item.quantidade_planejada = qtd_planejada
                item.numero_sc = numero_sc
                item.numero_pc = numero_pc
                item.data_sc = data_sc
                item.data_pc = data_pc
                item.empresa_fornecedora = empresa_fornecedora
                item.prazo_recebimento = prazo_recebimento
                item.save(update_fields=[
                    "categoria", "prioridade", "quantidade_planejada", "numero_sc", "numero_pc",
                    "data_sc", "data_pc", "empresa_fornecedora", "prazo_recebimento",
                ])
            # RecebimentoObra para itens que têm SC (permite alocação)
            if numero_sc and numero_pc and qtd_recebida and qtd_recebida > 0:
                rec, _ = RecebimentoObra.objects.get_or_create(
                    obra=obra,
                    insumo=insumo,
                    numero_sc=numero_sc,
                    item_sc="",
                    defaults={
                        "quantidade_solicitada": qtd_planejada or Decimal("100"),
                        "quantidade_recebida": qtd_recebida,
                        "saldo_a_entregar": Decimal("0"),
                        "numero_pc": numero_pc,
                        "data_sc": data_sc,
                        "data_pc": data_pc,
                        "empresa_fornecedora": empresa_fornecedora,
                        "prazo_recebimento": prazo_recebimento,
                    },
                )
                # Alocação só se houver saldo disponível no recebimento (evita erro em re-runs)
                if item.local_aplicacao and rec.quantidade_recebida > 0 and random.random() > 0.4:
                    disponivel = rec.quantidade_disponivel
                    if disponivel >= Decimal("0.01"):
                        qtd_aloc = min(
                            disponivel / 2,
                            item.quantidade_planejada or disponivel,
                            disponivel,
                        )
                        qtd_aloc = qtd_aloc.quantize(Decimal("0.01"), rounding=ROUND_FLOOR)
                        if qtd_aloc > disponivel:
                            qtd_aloc = disponivel
                        qtd_aloc = max(qtd_aloc, Decimal("0.01"))
                        AlocacaoRecebimento.objects.get_or_create(
                            obra=obra,
                            recebimento=rec,
                            item_mapa=item,
                            defaults={
                                "insumo": insumo,
                                "local_aplicacao": item.local_aplicacao,
                                "quantidade_alocada": qtd_aloc,
                                "criado_por": user,
                            },
                        )
                # Nota fiscal de entrada (demonstração de drill-down)
                if random.random() > 0.6:
                    nf_num = f"NF-{rec.id}-{random.randint(1000, 9999)}"
                    data_ent = data_pc or date.today()
                    NotaFiscalEntrada.objects.get_or_create(
                        obra=obra,
                        insumo=insumo,
                        numero_nf=nf_num,
                        data_entrada=data_ent,
                        numero_pc=numero_pc or "",
                        defaults={
                            "recebimento": rec,
                            "quantidade": qtd_recebida,
                        },
                    )
    # Histórico de alterações (auditoria no Mapa)
    itens_com_historico = list(
        ItemMapa.objects.filter(obra__in=obras_mapa).select_related("insumo", "local_aplicacao")[:30]
    )
    for item in random.sample(itens_com_historico, min(15, len(itens_com_historico))):
        HistoricoAlteracao.registrar(
            obra=item.obra,
            usuario=user,
            tipo="EDICAO",
            descricao=f"Quantidade planejada alterada para {item.quantidade_planejada} (demo).",
            item_mapa=item,
            campo_alterado="quantidade_planejada",
            valor_anterior="0",
            valor_novo=str(item.quantidade_planejada),
        )

    # Cenários variados no Mapa: itens atrasados (prazo no passado), descrição override, não aplica
    todos_itens = list(ItemMapa.objects.filter(obra__in=obras_mapa))
    for item in random.sample(todos_itens, min(12, len(todos_itens))):
        item.prazo_necessidade = date.today() - timedelta(days=random.randint(5, 30))
        item.save(update_fields=["prazo_necessidade"])
    for item in random.sample(todos_itens, min(8, len(todos_itens))):
        item.descricao_override = f"{item.insumo.descricao} - Especificação conforme memorial."
        item.save(update_fields=["descricao_override"])
    for item in random.sample(todos_itens, min(2, len(todos_itens))):
        if not item.descricao_override:
            item.descricao_override = item.insumo.descricao
        item.nao_aplica = True
        item.save(update_fields=["nao_aplica", "descricao_override"])


def create_mapa_servico_controle(obras_mapa, dry_run=False):
    """
    Gera linhas de mapa de serviço (controle físico) com blocos × pavimentos × aptos e
    percentuais variados — alimenta heatmap e KPIs do BI da Obra.
    """
    if dry_run:
        return 0
    rng = random.Random(42)
    blocos = ["A", "B", "C"]
    pavs = ["TÉRREO", "1", "2"]
    aptos = ["101", "102", "201"]
    atividades = [
        "Alvenaria de vedação",
        "Instalações elétricas",
        "Instalações hidráulicas",
        "Revestimento cerâmico",
        "Pintura interna",
        "Forro de gesso",
    ]
    situacoes = [
        ("Concluído", Decimal("1.000")),
        ("Em execução", Decimal("0.550")),
        ("Em execução", Decimal("0.220")),
        ("Não iniciado", Decimal("0")),
        ("Parcial", Decimal("0.400")),
        ("Aguardando material", Decimal("0.080")),
        ("", Decimal("0.350")),
    ]
    created = 0
    for obra in obras_mapa:
        n = 0
        for b in blocos:
            for p in pavs:
                for apto in aptos:
                    for act in atividades:
                        stxt, spct = situacoes[n % len(situacoes)]
                        n += 1
                        uid = f"DEMO|MOCK|{obra.pk}|{b}|{p}|{apto}|{act}"[:255]
                        ItemMapaServico.objects.update_or_create(
                            obra=obra,
                            chave_uid=uid,
                            defaults={
                                "setor": "EDIFÍCIO",
                                "bloco": b,
                                "pavimento": p,
                                "apto": apto,
                                "atividade": act[:200],
                                "grupo_servicos": "OBRA" if n % 2 else "ACABAMENTO",
                                "status_texto": stxt,
                                "status_percentual": spct,
                            },
                        )
                        created += 1
        for act in atividades:
            key = act.upper()[:220]
            ItemMapaServicoStatusRef.objects.update_or_create(
                obra=obra,
                atividade_chave=key,
                defaults={
                    "atividade": act,
                    "status_macro": rng.choice(
                        ["Planejado", "Em curso", "Concluído", "Atraso", "Crítico"]
                    ),
                    "situacao": (
                        "Referência gerada para demonstração do mapa de controle e do BI da Obra."
                    ),
                    "prazo_execucao": "Conforme cronograma",
                    "responsabilidade": rng.choice(
                        ["Construtora", "Empreiteira", "Instaladora", "Pintura"]
                    ),
                },
            )
    return created


def create_eap(project, dry_run=False):
    """Cria EAP (atividades) no projeto."""
    if dry_run:
        return []
    if Activity.objects.filter(project=project).exists():
        return list(Activity.objects.filter(project=project))
    raiz1 = Activity.add_root(
        project=project,
        name="Serviços Preliminares",
        code="1.0",
        weight=Decimal("15.00"),
        status=ActivityStatus.IN_PROGRESS,
    )
    raiz1.add_child(
        project=project,
        name="Mobilização e instalação do canteiro",
        code="1.1",
        weight=Decimal("50.00"),
        status=ActivityStatus.COMPLETED,
    )
    raiz1.add_child(
        project=project,
        name="Limpeza e cercamento",
        code="1.2",
        weight=Decimal("50.00"),
        status=ActivityStatus.IN_PROGRESS,
    )
    raiz2 = Activity.add_root(
        project=project,
        name="Fundação",
        code="2.0",
        weight=Decimal("25.00"),
        status=ActivityStatus.IN_PROGRESS,
    )
    raiz2.add_child(
        project=project,
        name="Escavação",
        code="2.1",
        weight=Decimal("40.00"),
        status=ActivityStatus.IN_PROGRESS,
    )
    raiz2.add_child(
        project=project,
        name="Concreto de fundação",
        code="2.2",
        weight=Decimal("60.00"),
        status=ActivityStatus.NOT_STARTED,
    )
    raiz3 = Activity.add_root(
        project=project,
        name="Estrutura",
        code="3.0",
        weight=Decimal("30.00"),
        status=ActivityStatus.IN_PROGRESS,
    )
    raiz3.add_child(
        project=project,
        name="Alvenaria",
        code="3.1",
        weight=Decimal("50.00"),
        status=ActivityStatus.NOT_STARTED,
    )
    raiz3.add_child(
        project=project,
        name="Instalações",
        code="3.2",
        weight=Decimal("50.00"),
        status=ActivityStatus.NOT_STARTED,
    )
    return [raiz1, raiz2, raiz3]


def create_diaries_with_photos(projects, user, num_days=60, dry_run=False):
    """Cria diários em várias datas, com clima, descrições e fotos placeholder."""
    if dry_run:
        return 0
    png_bytes = base64.b64decode(PNG_1X1_BASE64)
    legendas = [
        "Bloco A - Fundação em execução",
        "Vista geral do canteiro",
        "Detalhe da armadura",
        "Pavimento térreo - alvenaria",
        "Instalação elétrica - pré-instalação",
        "Registro de concretagem",
        "DDS da manhã",
        "Entrega de material",
    ]
    weather_opts = [
        ("Céu claro, tempo estável.", "B", "T", "B", "T"),
        ("Manhã com nuvens; tarde ensolarada.", "B", "T", "B", "T"),
        ("Chuva leve pela manhã; tarde sem chuva.", "R", "N", "B", "T"),
        ("Dia inteiro ensolarado.", "B", "T", "B", "T"),
        ("Neblina pela manhã; dissipou ao meio-dia.", "R", "T", "B", "T"),
    ]
    created_count = 0
    for project in projects:
        activities = list(Activity.objects.filter(project=project, numchild=0))
        if not activities:
            create_eap(project, dry_run=False)
            activities = list(Activity.objects.filter(project=project, numchild=0))

        for d in range(num_days):
            di = date.today() - timedelta(days=d)
            if di.weekday() >= 5 and random.random() > 0.4:
                continue
            if random.random() > 0.55:
                continue
            w_desc, w_m_c, w_m_t, w_a_c, w_a_t = random.choice(weather_opts)
            status = (
                DiaryStatus.APROVADO
                if random.random() > 0.25
                else DiaryStatus.SALVAMENTO_PARCIAL
            )
            diary, created = ConstructionDiary.objects.get_or_create(
                project=project,
                date=di,
                defaults={
                    "status": status,
                    "created_by": user,
                    "reviewed_by": user if status == DiaryStatus.APROVADO else None,
                    "approved_at": timezone.now() if status == DiaryStatus.APROVADO else None,
                    "weather_conditions": w_desc,
                    "weather_morning_condition": w_m_c,
                    "weather_morning_workable": w_m_t,
                    "weather_afternoon_condition": w_a_c,
                    "weather_afternoon_workable": w_a_t,
                    "pluviometric_index": Decimal(str(round(random.uniform(0, 15), 2))) if random.random() > 0.6 else None,
                    "rain_occurrence": random.choice(["", "F", "M"]) if random.random() > 0.7 else "",
                    "work_hours": Decimal("8.00"),
                    "general_notes": (
                        f"Atividades do dia {di.strftime('%d/%m/%Y')}: "
                        "acompanhamento de obra, fiscalização e registro fotográfico."
                    ),
                    "inspection_responsible": "Eng. Campo",
                    "production_responsible": "Mestre de Obras",
                    "deliberations": "Reunião de alinhamento às 7h." if random.random() > 0.6 else "",
                    "dds": "DDS sobre uso de EPI e acesso à obra." if random.random() > 0.5 else "",
                    "accidents": (
                        "Nenhum acidente registrado no dia."
                        if random.random() > 0.92
                        else "Queda de material em área restrita; sem vítimas. Área isolada e sinalizada."
                    ) if random.random() > 0.85 else "",
                    "stoppages": (
                        "Paralisação das 10h às 12h por falta de energia. Retomada à tarde."
                        if random.random() > 0.7
                        else ""
                    ) if random.random() > 0.88 else "",
                    "imminent_risks": (
                        "Risco de queda de altura no Bloco B - uso obrigatório de cinto. Sinalização reforçada."
                        if random.random() > 0.75
                        else ""
                    ) if random.random() > 0.9 else "",
                    "incidents": (
                        "Reclamação de vizinhança por barulho; horário de concretagem mantido dentro do permitido."
                        if random.random() > 0.7
                        else ""
                    ) if random.random() > 0.87 else "",
                },
            )
            if created:
                created_count += 1
            # Fotos placeholder (apenas em diários aprovados ou alguns parciais)
            if (created or not DiaryImage.objects.filter(diary=diary).exists()) and (
                status == DiaryStatus.APROVADO or random.random() > 0.6
            ):
                n_fotos = random.randint(1, 4)
                for j in range(n_fotos):
                    caption = random.choice(legendas) + f" ({di.strftime('%d/%m')})"
                    img = DiaryImage(
                        diary=diary,
                        caption=caption,
                        is_approved_for_report=True,
                    )
                    img.image.save(
                        f"demo_{diary.id}_{j}.png",
                        ContentFile(png_bytes),
                        save=True,
                    )
            # Work log em algumas atividades
            if created and status == DiaryStatus.APROVADO and activities and random.random() > 0.5:
                act = random.choice(activities)
                work_log, _ = DailyWorkLog.objects.get_or_create(
                    activity=act,
                    diary=diary,
                    defaults={
                        "percentage_executed_today": Decimal(str(round(random.uniform(5, 30), 2))),
                        "accumulated_progress_snapshot": Decimal(str(round(random.uniform(10, 60), 2))),
                        "location": "Bloco A" if "1.1" in act.code else "Obra",
                        "notes": "Execução conforme cronograma. Material conferido.",
                        "work_stage": random.choice(["IN", "AN", "TE"]),
                    },
                )
                # Vincular equipamentos em parte dos work logs (demonstração)
                if _ and Equipment.objects.filter(is_active=True).exists() and random.random() > 0.5:
                    equipamentos_ativos = list(Equipment.objects.filter(is_active=True))
                    for eq in random.sample(equipamentos_ativos, min(4, len(equipamentos_ativos))):
                        DailyWorkLogEquipment.objects.get_or_create(
                            work_log=work_log,
                            equipment=eq,
                            defaults={"quantity": random.randint(1, 3)},
                        )
            # Anexos (PDF/documento placeholder) em alguns diários
            if created and random.random() > 0.75:
                content = (
                    f"Registro de acompanhamento - {di.strftime('%d/%m/%Y')}\n"
                    "Obra em conformidade com cronograma. Relatório gerado automaticamente para demonstração."
                ).encode("utf-8")
                fname = f"relatorio_{diary.id}.txt"
                if not DiaryAttachment.objects.filter(diary=diary, name=fname).exists():
                    att = DiaryAttachment(
                        diary=diary,
                        name=fname,
                        file=ContentFile(content, name=fname),
                        description="Relatório de acompanhamento do dia (demo).",
                    )
                    att.file_size = len(content)
                    att.save()
            # DiaryLaborEntry (mão de obra do dia)
            if created:
                cat = LaborCategory.objects.first()
                if cat:
                    cargo = LaborCargo.objects.filter(category=cat).first()
                    if cargo:
                        DiaryLaborEntry.objects.get_or_create(
                            diary=diary,
                            cargo=cargo,
                            defaults={"quantity": random.randint(2, 10), "company": ""},
                        )
    return created_count


def create_occurrences_and_tags(projects, user, dry_run=False):
    """Cria tags de ocorrência e ocorrências em diários."""
    if dry_run:
        return
    tags_data = [
        ("Atraso", "#EF4444"),
        ("Material", "#F59E0B"),
        ("Segurança", "#10B981"),
        ("Qualidade", "#3B82F6"),
        ("Clima", "#8B5CF6"),
        ("Fornecedor", "#EC4899"),
        ("Cronograma", "#06B6D4"),
        ("EPI", "#84CC16"),
        ("Infraestrutura", "#6366F1"),
        ("Mão de obra", "#F97316"),
        ("Documentação", "#64748B"),
        ("Vistoria", "#14B8A6"),
        ("Acesso/Obra", "#A855F7"),
        ("Reclamação", "#DC2626"),
        ("Conformidade", "#15803D"),
        ("Medição", "#0EA5E9"),
        ("Entrega", "#CA8A04"),
        ("Projeto", "#BE185D"),
    ]
    for name, color in tags_data:
        OccurrenceTag.objects.get_or_create(name=name, defaults={"color": color, "is_active": True})
    tags = list(OccurrenceTag.objects.filter(is_active=True))
    diaries = list(
        ConstructionDiary.objects.filter(
            project__in=projects,
            status=DiaryStatus.APROVADO,
        ).order_by("-date")[:120]
    )
    descricoes = [
        "Atraso na entrega de material - reagendado para amanhã.",
        "Vistoria de segurança realizada. EPIs em ordem.",
        "Chuva interrompeu trabalhos externos pela manhã.",
        "Reclamação do cliente sobre prazo - alinhamento com produção.",
        "Falta de ferragem no almoxarifado - pedido de urgência.",
        "Medição de serviço executado realizada. Documentação encaminhada.",
        "Acesso à obra interditado temporariamente para carga/descarga.",
        "Conformidade da etapa verificada. Laudo anexado.",
        "Entrega de insumos no prazo. Conferência OK.",
        "Ajuste de projeto aprovado em reunião. Alteração no cronograma.",
        "DDS sobre uso de EPI e trabalho em altura.",
        "Infraestrutura de canteiro ampliada (banheiros e refeitório).",
    ]
    for _ in range(min(140, len(diaries))):
        diary = random.choice(diaries)
        tag = random.choice(tags) if tags else None
        desc = random.choice(descricoes)
        occ, created = DiaryOccurrence.objects.get_or_create(
            diary=diary,
            description=desc[:500],
            defaults={"created_by": user},
        )
        if created and tag:
            occ.tags.add(tag)


def ensure_labor_equipment_categories(dry_run=False):
    """Garante categorias de mão de obra e equipamentos para o Diário (listagens e work logs)."""
    if dry_run:
        return
    # Mão de obra
    cat_indireta, _ = LaborCategory.objects.get_or_create(
        slug="indireta", defaults={"name": "Indireta (LPLAN)", "order": 0}
    )
    for name in ["Pedreiro", "Mestre de Obras", "Servente", "Engenheiro de Campo"]:
        LaborCargo.objects.get_or_create(category=cat_indireta, name=name, defaults={"order": 0})
    cat_direta, _ = LaborCategory.objects.get_or_create(
        slug="direta", defaults={"name": "Direta", "order": 1}
    )
    for name in ["Eletricista", "Encarregado", "Carpinteiro"]:
        LaborCargo.objects.get_or_create(category=cat_direta, name=name, defaults={"order": 0})
    cat_terc, _ = LaborCategory.objects.get_or_create(
        slug="terceirizada", defaults={"name": "Terceirizada", "order": 2}
    )
    for name in ["Eletricista terceirizado", "Pedreiro terceirizado", "Encanador terceirizado"]:
        LaborCargo.objects.get_or_create(category=cat_terc, name=name, defaults={"order": 0})
    # Equipamentos
    cat_maq, _ = EquipmentCategory.objects.get_or_create(
        slug="maquinas", defaults={"name": "Máquinas", "order": 0}
    )
    for name in [
        "Betoneira", "Escavadeira", "Caminhão basculante", "Retroescavadeira",
        "Guincho", "Pá carregadeira", "Rolo compactador", "Caminhão betoneira",
    ]:
        StandardEquipment.objects.get_or_create(category=cat_maq, name=name, defaults={"order": 0})
    cat_cant, _ = EquipmentCategory.objects.get_or_create(
        slug="canteiro", defaults={"name": "Canteiro", "order": 1}
    )
    for name in [
        "Andaime", "Bomba de concreto", "Grua", "Escoramento metálico",
        "Fôrma metálica", "Cimbramento", "Torre de iluminação",
    ]:
        StandardEquipment.objects.get_or_create(category=cat_cant, name=name, defaults={"order": 0})
    cat_ferr, _ = EquipmentCategory.objects.get_or_create(
        slug="ferramentas", defaults={"name": "Ferramentas e Pequenos Equipamentos", "order": 2}
    )
    for name in [
        "Compressor", "Betoneira portátil", "Cortadora de piso", "Vibrador de concreto",
        "Gerador", "Bomba d'água", "Cortadora de ferro",
    ]:
        StandardEquipment.objects.get_or_create(category=cat_ferr, name=name, defaults={"order": 0})
    # Equipment (instâncias usadas em DailyWorkLog)
    equipment_instances = [
        ("EQ-001", "Betoneira 400L", "Betoneira"),
        ("EQ-002", "Escavadeira hidráulica", "Escavadeira"),
        ("EQ-003", "Andaime metálico", "Andaime"),
        ("EQ-004", "Caminhão basculante 10m³", "Caminhão basculante"),
        ("EQ-005", "Bomba de concreto 28m", "Bomba de concreto"),
        ("EQ-006", "Retroescavadeira", "Retroescavadeira"),
        ("EQ-007", "Guincho 500kg", "Guincho"),
        ("EQ-008", "Rolo compactador liso", "Rolo compactador"),
        ("EQ-009", "Grua 8t", "Grua"),
        ("EQ-010", "Betoneira 300L", "Betoneira"),
        ("EQ-011", "Pá carregadeira", "Pá carregadeira"),
        ("EQ-012", "Escoramento metálico (jogo)", "Escoramento metálico"),
        ("EQ-013", "Gerador 50kVA", "Gerador"),
        ("EQ-014", "Compressor 500L", "Compressor"),
        ("EQ-015", "Vibrador de concreto", "Vibrador de concreto"),
        ("EQ-016", "Caminhão betoneira 6m³", "Caminhão betoneira"),
        ("EQ-017", "Torre de iluminação", "Torre de iluminação"),
        ("EQ-018", "Andaime fachadeiro", "Andaime"),
    ]
    for code, name, eq_type in equipment_instances:
        Equipment.objects.get_or_create(
            code=code, defaults={"name": name, "equipment_type": eq_type, "is_active": True}
        )


def create_gestao_aprovacao_data(projects, user, dry_run=False):
    """Cria Empresa, Obras de Gestão, Pedidos de Obra e Aprovações para demonstrar o módulo Gestão."""
    if dry_run:
        return 0
    try:
        from gestao_aprovacao.models import (
            Empresa, Obra as ObraGestao, WorkOrder, Approval,
            WorkOrderPermission, UserEmpresa,
        )
    except ImportError:
        return None
    # Empresa
    empresa, _ = Empresa.objects.get_or_create(
        codigo="LPLAN",
        defaults={
            "nome": "LPLAN Construções",
            "email": "contato@lplan.com.br",
            "ativo": True,
            "responsavel": user,
        },
    )
    if not empresa.responsavel_id:
        empresa.responsavel = user
        empresa.save(update_fields=["responsavel"])
    UserEmpresa.objects.get_or_create(usuario=user, empresa=empresa, defaults={"ativo": True})
    # Obras de Gestão (uma por Project com mesmo code)
    obras_gestao = []
    for proj in projects:
        og, _ = ObraGestao.objects.get_or_create(
            codigo=proj.code,
            defaults={
                "nome": proj.name,
                "project": proj,
                "empresa": empresa,
                "ativo": True,
            },
        )
        if not og.project_id:
            og.project = proj
            og.save(update_fields=["project"])
        obras_gestao.append(og)
        WorkOrderPermission.objects.get_or_create(
            obra=og, usuario=user, tipo_permissao="solicitante", defaults={"ativo": True}
        )
        WorkOrderPermission.objects.get_or_create(
            obra=og, usuario=user, tipo_permissao="aprovador", defaults={"ativo": True}
        )
    # Pedidos em vários status (para listagem e filtros)
    credores = ["Materiais Construção Ltda", "Ferragens Norte", "Concreto ABC", "Elétrica São Paulo"]
    tipos = ["contrato", "medicao", "ordem_servico", "mapa_cotacao"]
    status_list = ["rascunho", "pendente", "aprovado", "reprovado", "reaprovacao", "cancelado"]
    created = 0
    for obra in obras_gestao[:4]:  # primeiras 4 obras
        for i in range(1, 6):
            cod = f"PO-2024-{obra.codigo}-{i:02d}"
            if WorkOrder.objects.filter(obra=obra, codigo=cod).exists():
                continue
            status = random.choice(status_list)
            wo = WorkOrder.objects.create(
                obra=obra,
                codigo=cod,
                nome_credor=random.choice(credores),
                tipo_solicitacao=random.choice(tipos),
                observacoes="Pedido de demonstração para screencast.",
                status=status,
                criado_por=user,
                valor_estimado=Decimal(str(round(random.uniform(5000, 80000), 2))) if random.random() > 0.3 else None,
            )
            created += 1
            if status in ("pendente", "reaprovacao"):
                wo.data_envio = timezone.now() - timedelta(days=random.randint(1, 15))
                wo.save()
            if status in ("aprovado", "reprovado"):
                wo.data_envio = timezone.now() - timedelta(days=random.randint(5, 25))
                wo.data_aprovacao = timezone.now() - timedelta(days=random.randint(1, 10))
                wo.save()
                Approval.objects.create(
                    work_order=wo,
                    aprovado_por=user,
                    decisao="aprovado" if status == "aprovado" else "reprovado",
                    comentario="Aprovado conforme documentação." if status == "aprovado" else "Ajustar valor e reenviar.",
                )
    return created


class Command(BaseCommand):
    help = (
        "Gera dados de teste completos para ambiente LOCAL (screencasts). "
        "Só executa com DEBUG=True."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas mostra o que seria feito, sem gravar.",
        )
        parser.add_argument(
            "--dias-diarios",
            type=int,
            default=32,
            metavar="N",
            help="Quantidade de dias (para trás a partir de hoje) para tentar criar diários de obra. Padrão: 32 (~1 mês).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        dias_diarios = max(1, min(options["dias_diarios"], 120))
        _check_local_only()

        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: nenhuma alteração no banco."))

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Seed Dados Demo Completo (apenas LOCAL) ===\n"))

        with transaction.atomic():
            ensure_groups()
            user = get_or_create_demo_user()
            self.stdout.write(self.style.SUCCESS(f"Usuário: {user.username} (senha: demo1234 se acabou de criar)."))

            obras_mapa, projects = create_obras_and_projects()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Obras LPLAN: {[o.nome for o in obras_mapa]}. Projetos core: {[p.code for p in projects]}."
                )
            )

            if not dry_run:
                link_user_to_projects(projects, user)
                self.stdout.write("Usuário vinculado aos projetos (Mapa e Diário).")

            ensure_labor_equipment_categories(dry_run=dry_run)
            self.stdout.write("Categorias de mão de obra e equipamentos (Diário) garantidas.")

            for obra in obras_mapa:
                n_locais = len(create_locais_for_obra(obra)) if not dry_run else 0
                self.stdout.write(f"  Obra {obra.nome}: {n_locais} locais.")

            insumos = create_insumos()
            self.stdout.write(self.style.SUCCESS(f"Insumos: {len(insumos)} cadastrados."))

            create_mapa_and_recebimentos(obras_mapa, insumos, user, dry_run=dry_run)
            self.stdout.write(
                "Mapa de Suprimentos: itens, SCs, recebimentos e alocações (situações variadas)."
            )

            n_ms = create_mapa_servico_controle(obras_mapa, dry_run=dry_run)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Mapa de serviço (controle físico): {n_ms} linhas ItemMapaServico "
                    "(bloco × pavimento × apto × atividades) + refs de status por obra."
                )
            )

            for proj in projects:
                create_eap(proj, dry_run=dry_run)
            self.stdout.write("EAP (atividades) criada nos projetos.")

            n_diaries = create_diaries_with_photos(
                projects, user, num_days=dias_diarios, dry_run=dry_run
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Diários de obra: {n_diaries} novos em até {dias_diarios} dias corridos "
                    "(fotos placeholder, clima, ocorrências)."
                )
            )

            create_occurrences_and_tags(projects, user, dry_run=dry_run)
            self.stdout.write("Ocorrências e tags criadas.")

            n_gestao = create_gestao_aprovacao_data(projects, user, dry_run=dry_run)
            if n_gestao is not None and n_gestao > 0:
                self.stdout.write(self.style.SUCCESS(f"Pedidos de obra (Gestão): {n_gestao} criados."))
            elif n_gestao == 0 and not dry_run:
                self.stdout.write("Gestão de Aprovação: pedidos já existentes.")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Seed concluído. Use o usuário demo (ou seu superuser) para acessar Mapa, Dashboard e Diário."
            )
        )
        self.stdout.write(
            "Vídeos no diário: não são criados automaticamente; anexe manualmente se precisar."
        )
