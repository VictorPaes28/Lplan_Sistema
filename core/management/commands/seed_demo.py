"""
Seed completo para simular 1 mês de uso do Sistema LPLAN em todos os apps.

Regras aplicadas:
- Grupos e permissões conforme accounts.groups e setup_groups
- Obras com nomes realistas; código único (OBRA-2024-XXX)
- Mapa de Suprimentos: apenas insumos grossos (eh_macroelemento=True)
- Diário: EAP, diários aprovados/parciais, work logs, ocorrências
- Gestão: pedidos em vários status, aprovações/reprovações
- Mapa: locais hierárquicos, ItemMapa, RecebimentoObra, alocações

Uso:
    python manage.py seed_demo

Recomendado rodar após migrate e setup_groups.
"""
import random
from datetime import date, timedelta, datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User, Group
from django.utils import timezone

from accounts.groups import GRUPOS
from core.models import (
    Project, ProjectMember, ProjectOwner, ProjectDiaryRecipient,
    Activity, ActivityStatus, ConstructionDiary, DiaryStatus,
    DailyWorkLog, DiaryLaborEntry, DiaryOccurrence, OccurrenceTag,
    LaborCategory, LaborCargo, EquipmentCategory, StandardEquipment, Equipment,
)
from gestao_aprovacao.models import Empresa, Obra as ObraGestao, WorkOrder, WorkOrderPermission, Approval, UserEmpresa
from mapa_obras.models import Obra as ObraMapa, LocalObra
from suprimentos.models import Insumo, ItemMapa, RecebimentoObra, AlocacaoRecebimento


def ensure_groups():
    """Cria grupos se não existirem (espelho do setup_groups)."""
    for name in GRUPOS.TODOS:
        Group.objects.get_or_create(name=name)


def create_users():
    """Cria usuários de demonstração com grupos. Senha padrão: demo1234"""
    senha = 'demo1234'
    users_config = [
        ('admin', 'Administrador', 'admin@lplan.com.br', True, True, []),  # superuser
        ('gerente', 'Gerente Diário', 'gerente@lplan.com.br', True, False, [GRUPOS.GERENTES]),
        ('carlos.silva', 'Carlos Silva (Aprovador)', 'carlos.silva@lplan.com.br', False, False, [GRUPOS.APROVADOR]),
        ('ana.oliveira', 'Ana Oliveira (Solicitante)', 'ana.oliveira@lplan.com.br', False, False, [GRUPOS.SOLICITANTE]),
        ('ricardo.empresa', 'Ricardo Costa (Resp. Empresa)', 'ricardo@lplan.com.br', False, False, [GRUPOS.RESPONSAVEL_EMPRESA]),
        ('eng.maria', 'Maria Santos (Engenharia)', 'maria.santos@lplan.com.br', False, False, [GRUPOS.ENGENHARIA]),
        ('dono.obra', 'Cliente Dono da Obra', 'cliente@empresa.com.br', False, False, []),  # sem grupo; ProjectOwner
    ]
    created = []
    for username, full_name, email, is_staff, is_superuser, group_names in users_config:
        user, created_flag = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'first_name': full_name.split(' ', 1)[0] if ' ' in full_name else full_name,
                'last_name': full_name.split(' ', 1)[1] if ' ' in full_name else '',
                'is_staff': is_staff,
                'is_superuser': is_superuser,
                'is_active': True,
            }
        )
        if created_flag:
            user.set_password(senha)
            user.save()
            created.append(username)
        for gname in group_names:
            g = Group.objects.filter(name=gname).first()
            if g:
                user.groups.add(g)
        user.save()
    return created


def create_empresa_and_obras():
    """Cria 1 empresa e 3 projetos/obras (core + gestão + mapa) com códigos alinhados."""
    hoje = date.today()
    inicio = hoje - timedelta(days=180)
    fim = hoje + timedelta(days=365)

    # Responsável para a empresa (evita erro se a coluna responsavel_id for NOT NULL no MySQL)
    responsavel = User.objects.filter(username='ricardo.empresa').first() or User.objects.filter(is_superuser=True).first()

    # Empresa
    empresa, _ = Empresa.objects.get_or_create(
        codigo='LPLAN',
        defaults={
            'nome': 'LPLAN Construções',
            'email': 'contato@lplan.com.br',
            'ativo': True,
            **({'responsavel': responsavel} if responsavel else {}),
        }
    )
    if responsavel and not empresa.responsavel_id:
        empresa.responsavel = responsavel
        empresa.save(update_fields=['responsavel'])

    obras_data = [
        ('OBRA-2024-001', 'Edificação Residencial Alto Padrão - Bloco A', 'Rua das Flores, 100 - Centro', 'Construtora Alpha Ltda'),
        ('OBRA-2024-002', 'Obra de Infraestrutura - Drenagem e Pavimentação', 'Av. Industrial, km 5', 'Prefeitura Municipal'),
        ('OBRA-2024-003', 'Reforma e Ampliação - Centro Comercial Sul', 'Praça do Comércio, 50', 'Shopping Sul S.A.'),
    ]
    projects = []
    obras_gestao = []
    obras_mapa = []

    for code, name, address, client in obras_data:
        # Core: Project
        proj, _ = Project.objects.get_or_create(
            code=code,
            defaults={
                'name': name,
                'address': address,
                'client_name': client,
                'start_date': inicio,
                'end_date': fim,
                'responsible': 'Engenheiro Responsável',
                'is_active': True,
            }
        )
        projects.append(proj)

        # Gestão: Obra (vinculada ao Project)
        og, _ = ObraGestao.objects.get_or_create(
            codigo=code,
            defaults={
                'nome': name,
                'project': proj,
                'empresa': empresa,
                'ativo': True,
            }
        )
        if not og.project_id:
            og.project = proj
            og.save()
        obras_gestao.append(og)

        # Mapa: Obra (codigo_sienge = code para usuário ver pelo Project)
        om, _ = ObraMapa.objects.get_or_create(
            codigo_sienge=code,
            defaults={'nome': name, 'ativa': True}
        )
        obras_mapa.append(om)

    return empresa, projects, obras_gestao, obras_mapa


def link_users_to_projects(projects, users_dict):
    """ProjectMember para gerente, carlos, ana, eng.maria, ricardo em todos. ProjectOwner: dono na primeira obra."""
    for proj in projects:
        for uname in ('gerente', 'carlos.silva', 'ana.oliveira', 'eng.maria', 'ricardo.empresa'):
            u = users_dict.get(uname)
            if u:
                ProjectMember.objects.get_or_create(user=u, project=proj)
    dono = users_dict.get('dono.obra')
    if dono and projects:
        ProjectOwner.objects.get_or_create(project=projects[0], user=dono)
    # E-mail destinatário diário (opcional)
    gerente = users_dict.get('gerente')
    if gerente and projects:
        for proj in projects[:2]:
            ProjectDiaryRecipient.objects.get_or_create(
                project=proj, email=gerente.email,
                defaults={'nome': 'Gerente'}
            )


def link_gestao_permissions(obras_gestao, users_dict):
    """WorkOrderPermission: Ana solicitante em todas, Carlos aprovador em todas. UserEmpresa."""
    ana = users_dict.get('ana.oliveira')
    carlos = users_dict.get('carlos.silva')
    ricardo = users_dict.get('ricardo.empresa')
    empresa = Empresa.objects.filter(codigo='LPLAN').first()
    if not empresa:
        return
    for obra in obras_gestao:
        if ana:
            WorkOrderPermission.objects.get_or_create(
                obra=obra, usuario=ana, tipo_permissao='solicitante', defaults={'ativo': True}
            )
        if carlos:
            WorkOrderPermission.objects.get_or_create(
                obra=obra, usuario=carlos, tipo_permissao='aprovador', defaults={'ativo': True}
            )
    for u in (ana, carlos, ricardo):
        if u and empresa:
            UserEmpresa.objects.get_or_create(usuario=u, empresa=empresa, defaults={'ativo': True})
    if ricardo and empresa:
        empresa.responsavel = ricardo
        empresa.save()


def create_eap(project):
    """Cria EAP com 2 raízes e filhos (folhas para work log)."""
    if Activity.objects.filter(project=project).exists():
        return list(Activity.objects.filter(project=project))
    raiz1 = Activity.add_root(
        project=project,
        name='Serviços Preliminares',
        code='1.0',
        weight=Decimal('15.00'),
        status=ActivityStatus.IN_PROGRESS,
    )
    raiz1.add_child(project=project, name='Mobilização e instalação do canteiro', code='1.1', weight=Decimal('50.00'), status=ActivityStatus.COMPLETED)
    raiz1.add_child(project=project, name='Limpeza e cercamento', code='1.2', weight=Decimal('50.00'), status=ActivityStatus.IN_PROGRESS)
    raiz2 = Activity.add_root(
        project=project,
        name='Fundação',
        code='2.0',
        weight=Decimal('25.00'),
        status=ActivityStatus.IN_PROGRESS,
    )
    r2_1 = raiz2.add_child(project=project, name='Escavação', code='2.1', weight=Decimal('40.00'), status=ActivityStatus.IN_PROGRESS)
    r2_2 = raiz2.add_child(project=project, name='Concreto de fundação', code='2.2', weight=Decimal('60.00'), status=ActivityStatus.NOT_STARTED)
    raiz3 = Activity.add_root(
        project=project,
        name='Registro Geral de Mão de Obra e Equipamentos',
        code='GEN-MAO-OBRA-EQUIP',
        weight=Decimal('0.00'),
        status=ActivityStatus.NOT_STARTED,
    )
    return [raiz1, raiz2, raiz3, r2_1, r2_2]


def create_diaries_and_worklogs(projects, users_dict, num_days=30):
    """Cria diários dos últimos num_days (2-4 por semana por projeto) e work logs em alguns."""
    gerente = users_dict.get('gerente')
    if not gerente:
        return
    hoje = date.today()
    diaries_created = 0
    for proj in projects:
        activities = list(Activity.objects.filter(project=proj).filter(numchild=0))  # folhas
        if not activities:
            create_eap(proj)
            activities = list(Activity.objects.filter(project=proj).filter(numchild=0))
        for d in range(num_days):
            di = hoje - timedelta(days=d)
            if di.weekday() >= 5:  # fim de semana menos diários
                if random.random() > 0.3:
                    continue
            if random.random() > 0.6:  # ~3 por semana
                continue
            status = DiaryStatus.APROVADO if random.random() > 0.2 else DiaryStatus.SALVAMENTO_PARCIAL
            diary, created = ConstructionDiary.objects.get_or_create(
                project=proj,
                date=di,
                defaults={
                    'status': status,
                    'created_by': gerente,
                    'reviewed_by': gerente if status == DiaryStatus.APROVADO else None,
                    'approved_at': timezone.now() if status == DiaryStatus.APROVADO else None,
                    'weather_conditions': 'Céu claro pela manhã; tarde com nuvens.',
                    'weather_morning_condition': 'B',
                    'weather_morning_workable': 'T',
                    'weather_afternoon_condition': 'B',
                    'weather_afternoon_workable': 'T',
                    'work_hours': Decimal('8.00'),
                    'general_notes': f'Trabalhos conforme planejado no dia {di.strftime("%d/%m/%Y")}.',
                    'inspection_responsible': 'Eng. Campo',
                    'production_responsible': 'Mestre de Obras',
                }
            )
            if created:
                diaries_created += 1
            if created and status == DiaryStatus.APROVADO and activities and random.random() > 0.5:
                act = random.choice(activities)
                DailyWorkLog.objects.get_or_create(
                    activity=act,
                    diary=diary,
                    defaults={
                        'percentage_executed_today': Decimal(str(round(random.uniform(5, 25), 2))),
                        'notes': 'Execução conforme cronograma.',
                    }
                )
                # DiaryLaborEntry: precisa de LaborCargo
                cat = LaborCategory.objects.first()
                if cat:
                    cargo = LaborCargo.objects.filter(category=cat).first()
                    if cargo:
                        DiaryLaborEntry.objects.get_or_create(
                            diary=diary, cargo=cargo,
                            defaults={'quantity': random.randint(2, 8), 'company': ''}
                        )
    return diaries_created


def create_occurrences(projects, users_dict, num_tags=5, num_occurrences=20):
    """Tags de ocorrência e ocorrências em diários existentes."""
    tags_data = [
        ('Atraso', '#EF4444'),
        ('Material', '#F59E0B'),
        ('Segurança', '#10B981'),
        ('Qualidade', '#3B82F6'),
        ('Clima', '#8B5CF6'),
    ]
    for name, color in tags_data[:num_tags]:
        OccurrenceTag.objects.get_or_create(name=name, defaults={'color': color, 'is_active': True})
    gerente = users_dict.get('gerente')
    if not gerente:
        return
    diaries = list(ConstructionDiary.objects.filter(project__in=projects, status=DiaryStatus.APROVADO).order_by('-date')[:40])
    tags = list(OccurrenceTag.objects.filter(is_active=True))
    for _ in range(min(num_occurrences, len(diaries))):
        diary = random.choice(diaries)
        tag = random.choice(tags) if tags else None
        desc = f"Ocorrência registrada em {diary.date}: verificação de campo realizada."
        occ, created = DiaryOccurrence.objects.get_or_create(
            diary=diary,
            description=desc[:500],
            defaults={'created_by': gerente}
        )
        if created and tag:
            occ.tags.add(tag)


def create_work_orders(obras_gestao, users_dict):
    """Pedidos de obra em vários status (rascunho, pendente, aprovado, reprovado, reaprovacao)."""
    ana = users_dict.get('ana.oliveira')
    carlos = users_dict.get('carlos.silva')
    if not ana or not carlos:
        return 0
    tipos = ['contrato', 'medicao', 'ordem_servico', 'mapa_cotacao']
    credores = ['Materiais Construção Ltda', 'Ferragens Norte', 'Concreto ABC', 'Elétrica São Paulo', 'Hidráulica Centro']
    created = 0
    for obra in obras_gestao:
        for i in range(1, 6):
            cod = f'PO-2024-{obra.codigo[-1]}{i:02d}'
            if WorkOrder.objects.filter(obra=obra, codigo=cod).exists():
                continue
            status = random.choice(['rascunho', 'pendente', 'aprovado', 'reprovado', 'reaprovacao', 'cancelado'])
            wo = WorkOrder.objects.create(
                obra=obra,
                codigo=cod,
                nome_credor=random.choice(credores),
                tipo_solicitacao=random.choice(tipos),
                observacoes='Pedido de demonstração.',
                status=status,
                criado_por=ana,
                valor_estimado=Decimal(str(round(random.uniform(5000, 50000), 2))) if random.random() > 0.3 else None,
            )
            created += 1
            if status in ('pendente', 'reaprovacao'):
                wo.data_envio = timezone.now() - timedelta(days=random.randint(1, 10))
                wo.save()
            if status in ('aprovado', 'reprovado'):
                wo.data_envio = timezone.now() - timedelta(days=random.randint(5, 20))
                wo.data_aprovacao = timezone.now() - timedelta(days=random.randint(1, 15))
                wo.save()
                Approval.objects.create(
                    work_order=wo,
                    aprovado_por=carlos,
                    decisao='aprovado' if status == 'aprovado' else 'reprovado',
                    comentario='Aprovado conforme documentação.' if status == 'aprovado' else 'Ajustar valor e reenviar.',
                )
    return created


def create_suprimentos_grossos(obras_mapa):
    """Insumos grossos (eh_macroelemento=True), locais, ItemMapa, RecebimentoObra e alocações."""
    # Insumos apenas grossos (mapa de suprimentos)
    insumos_data = [
        ('CONC-001', 'Concreto usinado C25', 'm³', True),
        ('CONC-002', 'Concreto usinado C30', 'm³', True),
        ('FERR-001', 'Ferragem CA-50', 'kg', True),
        ('TUB-001', 'Tubo PVC 100mm esgoto', 'm', True),
        ('TUB-002', 'Tubo PVC 75mm água', 'm', True),
        ('TEL-001', 'Telha cerâmica', 'und', True),
        ('BLOC-001', 'Bloco cerâmico 9x19x19', 'und', True),
        ('AREIA', 'Areia média', 'm³', True),
        ('BRITA', 'Brita 1', 'm³', True),
    ]
    insumos = []
    for cod, desc, un, macro in insumos_data:
        inv, _ = Insumo.objects.get_or_create(
            codigo_sienge=cod,
            defaults={'descricao': desc, 'unidade': un, 'eh_macroelemento': macro, 'ativo': True}
        )
        insumos.append(inv)

    for om in obras_mapa:
        # Locais hierárquicos
        bloco_a, _ = LocalObra.objects.get_or_create(obra=om, nome='Bloco A', parent=None, defaults={'tipo': 'BLOCO'})
        pav1, _ = LocalObra.objects.get_or_create(obra=om, nome='Pavimento 1', parent=bloco_a, defaults={'tipo': 'PAVIMENTO'})
        LocalObra.objects.get_or_create(obra=om, nome='Setor 1', parent=pav1, defaults={'tipo': 'SETOR'})
        LocalObra.objects.get_or_create(obra=om, nome='Lobby', parent=pav1, defaults={'tipo': 'SETOR'})
        bloco_b, _ = LocalObra.objects.get_or_create(obra=om, nome='Bloco B', parent=None, defaults={'tipo': 'BLOCO'})
        LocalObra.objects.get_or_create(obra=om, nome='Pavimento Térreo', parent=bloco_b, defaults={'tipo': 'PAVIMENTO'})

        # ItemMapa (necessidades por local) - apenas insumos grossos
        categorias = ['FUNDAÇÃO', 'ESTRUTURA', 'ALVENARIA/FECHAMENTO', 'INSTALAÇÕES HIDRÁULICA', 'INSTALAÇÕES ELÉTRICA']
        locais = list(LocalObra.objects.filter(obra=om))
        for ins in insumos[:5]:
            local = random.choice(locais) if locais else None
            cat = random.choice(categorias)
            ItemMapa.objects.get_or_create(
                obra=om, insumo=ins, local_aplicacao=local, categoria=cat,
                defaults={
                    'quantidade_planejada': Decimal(str(round(random.uniform(10, 200), 2))),
                    'numero_sc': f'SC-{om.codigo_sienge[-1]}-{random.randint(100, 999)}',
                    'prioridade': 'MEDIA',
                }
            )

        # RecebimentoObra (entrada na obra - Sienge)
        for ins in insumos[:4]:
            num_sc = f'SC-{om.id}-{ins.id}-{random.randint(100, 999)}'
            rec, created = RecebimentoObra.objects.get_or_create(
                obra=om, insumo=ins, numero_sc=num_sc, item_sc='',
                defaults={
                    'quantidade_solicitada': Decimal(str(round(random.uniform(20, 100), 2))),
                    'quantidade_recebida': Decimal(str(round(random.uniform(15, 80), 2))),
                    'saldo_a_entregar': Decimal('0.00'),
                    'data_sc': date.today() - timedelta(days=random.randint(5, 60)),
                }
            )
            if created and rec.quantidade_recebida and rec.quantidade_recebida > 0:
                itens = ItemMapa.objects.filter(obra=om, insumo=ins).select_related('local_aplicacao')[:2]
                for item in itens:
                    if item.local_aplicacao and rec.quantidade_recebida > 0:
                        qtd = min(rec.quantidade_recebida / 2, item.quantidade_planejada) if item.quantidade_planejada else rec.quantidade_recebida / 2
                        qtd = max(round(Decimal(str(qtd)), 2), Decimal('0.01'))
                        AlocacaoRecebimento.objects.get_or_create(
                            obra=om, recebimento=rec, item_mapa=item,
                            defaults={
                                'insumo': ins,
                                'local_aplicacao': item.local_aplicacao,
                                'quantidade_alocada': qtd,
                            }
                        )


class Command(BaseCommand):
    help = 'Popula o sistema com dados de demonstração (1 mês de uso em todos os apps).'

    def add_arguments(self, parser):
        parser.add_argument('--no-groups', action='store_true', help='Não criar/atualizar grupos (já rodou setup_groups)')
        parser.add_argument('--no-suprimentos', action='store_true', help='Não criar dados de suprimentos/mapa')

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Seed Demo - Sistema LPLAN ===\n'))
        with transaction.atomic():
            if not options['no_groups']:
                ensure_groups()
                self.stdout.write(self.style.SUCCESS('Grupos verificados.'))
            created_users = create_users()
            if created_users:
                self.stdout.write(self.style.SUCCESS(f'Usuários criados (senha: demo1234): {", ".join(created_users)}'))
            empresa, projects, obras_gestao, obras_mapa = create_empresa_and_obras()
            self.stdout.write(self.style.SUCCESS(f'Empresa: {empresa.nome}. Projetos: {[p.code for p in projects]}.'))

            users_dict = {u.username: u for u in User.objects.filter(username__in=[
                'admin', 'gerente', 'carlos.silva', 'ana.oliveira', 'ricardo.empresa', 'eng.maria', 'dono.obra'
            ])}
            link_users_to_projects(projects, users_dict)
            link_gestao_permissions(obras_gestao, users_dict)
            self.stdout.write('Vínculos usuário–obra e permissões Gestão configurados.')

            for proj in projects:
                create_eap(proj)
            self.stdout.write('EAP (atividades) criada nos projetos.')

            n_diaries = create_diaries_and_worklogs(projects, users_dict, num_days=35)
            self.stdout.write(self.style.SUCCESS(f'Diários criados/atualizados: {n_diaries}'))

            create_occurrences(projects, users_dict, num_occurrences=18)
            self.stdout.write('Ocorrências e tags criadas.')

            n_wo = create_work_orders(obras_gestao, users_dict)
            self.stdout.write(self.style.SUCCESS(f'Pedidos de obra (Gestão): {n_wo}'))

            if not options['no_suprimentos']:
                create_suprimentos_grossos(obras_mapa)
                self.stdout.write(self.style.SUCCESS('Mapa de Suprimentos: insumos grossos, locais, itens e recebimentos.'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Seed concluído. Acesse com admin/demo1234 ou gerente/demo1234.'))
