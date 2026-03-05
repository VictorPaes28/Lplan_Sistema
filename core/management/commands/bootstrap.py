"""
Bootstrap inicial do sistema LPLAN – dados essenciais idempotentes.

Garante a existência de obras, projetos, empresa padrão, obras de gestão e locais
necessários para o Diário de Obra, Mapa de Obras e Gestão. Seguro para rodar
na subida do servidor ou ao preparar ambiente novo (não duplica registros).

Uso:
  python manage.py bootstrap
  python manage.py bootstrap --dry-run
"""
from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Project
from mapa_obras.models import Obra as ObraMapa, LocalObra

# (codigo_sienge, nome_exibicao, endereco, responsavel)
# codigo_sienge = código único (Sienge/centro de custo); usado em core.Project.code e mapa_obras.Obra
OBRAS_ESSENCIAIS = [
    ('242', 'ENTREGÁGUAS', 'Rodovia AL 101 Norte, Porto de Pedras – AL', 'Antônio Azevedo'),
    ('259', 'MARGHOT HOTEL SPA', 'Sítio Porto dos Pregos, Porto de Pedras – AL', 'Antônio Azevedo'),
    ('OKENA', 'POUSADA OKENA', 'Sítio Riacho da Pedra, Porto de Pedras – AL', 'Stanisley'),
]


def _criar_locais_padrao(obra_mapa, dry_run=False):
    """Cria locais padrão (Bloco A/B, Pavimentos, Setores) por obra. Idempotente."""
    criados = 0
    existentes = 0
    pais = {}

    raizes = [
        ('Bloco A', 'BLOCO'),
        ('Bloco B', 'BLOCO'),
    ]
    for nome, tipo in raizes:
        if dry_run:
            if not LocalObra.objects.filter(obra=obra_mapa, nome=nome, parent__isnull=True).exists():
                criados += 1
            else:
                existentes += 1
        else:
            obj, c = LocalObra.objects.get_or_create(
                obra=obra_mapa, nome=nome, parent=None, defaults={'tipo': tipo}
            )
            pais[nome] = obj
            criados += 1 if c else 0
            existentes += 0 if c else 1

    filhos = [
        ('Pavimento 1', 'PAVIMENTO', 'Bloco A'),
        ('Pavimento Térreo', 'PAVIMENTO', 'Bloco A'),
        ('Pavimento 1', 'PAVIMENTO', 'Bloco B'),
        ('Lobby', 'SETOR', 'Bloco A'),
        ('Setor 1', 'SETOR', 'Bloco A'),
    ]
    if dry_run:
        for nome, tipo, parent_nome in filhos:
            parent = LocalObra.objects.filter(
                obra=obra_mapa, nome=parent_nome, parent__isnull=True
            ).first()
            if not parent:
                continue
            if not LocalObra.objects.filter(obra=obra_mapa, nome=nome, parent=parent).exists():
                criados += 1
            else:
                existentes += 1
        return criados, existentes

    for nome, tipo, parent_nome in filhos:
        parent = pais.get(parent_nome)
        if not parent:
            continue
        obj, c = LocalObra.objects.get_or_create(
            obra=obra_mapa, nome=nome, parent=parent, defaults={'tipo': tipo}
        )
        criados += 1 if c else 0
        existentes += 0 if c else 1
    return criados, existentes


class Command(BaseCommand):
    help = (
        'Garante dados essenciais do sistema (obras, projetos, locais). '
        'Idempotente: cria só o que falta, atualiza o que já existe sem duplicar.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra o que seria criado/atualizado, sem gravar.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('Modo dry-run: nenhuma alteração no banco.'))

        stats = {'project_created': 0, 'project_updated': 0, 'obra_mapa_created': 0, 'obra_mapa_updated': 0,
                 'empresa_created': 0, 'obra_gestao_created': 0, 'obra_gestao_updated': 0,
                 'locais_created': 0, 'locais_existentes': 0}

        with transaction.atomic():
            hoje = date.today()
            fim_placeholder = date(hoje.year + 2, 12, 31)

            for codigo, nome, endereco, responsavel in OBRAS_ESSENCIAIS:
                # 1) core.Project (Diário de Obra / seleção de obra)
                proj, created_proj = Project.objects.get_or_create(
                    code=codigo,
                    defaults={
                        'name': nome,
                        'address': endereco,
                        'responsible': responsavel or '',
                        'client_name': '',
                        'start_date': hoje,
                        'end_date': fim_placeholder,
                        'is_active': True,
                    },
                )
                if created_proj:
                    stats['project_created'] += 1
                    if not dry_run:
                        self.stdout.write(self.style.SUCCESS(f'   [OK] Project: {proj.code} – {proj.name}'))
                else:
                    # Atualizar campos que podem ter mudado (idempotente = manter dados corretos)
                    updated = False
                    if proj.name != nome:
                        proj.name = nome
                        updated = True
                    if proj.address != endereco:
                        proj.address = endereco
                        updated = True
                    if (responsavel or '') and proj.responsible != responsavel:
                        proj.responsible = responsavel
                        updated = True
                    if updated and not dry_run:
                        proj.save(update_fields=['name', 'address', 'responsible'])
                        stats['project_updated'] += 1
                    self.stdout.write(f'   [EXISTE] Project: {proj.code}')

                # 2) mapa_obras.Obra (Mapa de Suprimentos)
                obra_mapa, created_mapa = ObraMapa.objects.get_or_create(
                    codigo_sienge=codigo,
                    defaults={'nome': nome, 'ativa': True},
                )
                if created_mapa:
                    stats['obra_mapa_created'] += 1
                    if not dry_run:
                        self.stdout.write(self.style.SUCCESS(f'   [OK] Obra (Mapa): {obra_mapa.codigo_sienge} – {obra_mapa.nome}'))
                else:
                    if obra_mapa.nome != nome and not dry_run:
                        obra_mapa.nome = nome
                        obra_mapa.save(update_fields=['nome'])
                        stats['obra_mapa_updated'] += 1
                    self.stdout.write(f'   [EXISTE] Obra (Mapa): {obra_mapa.codigo_sienge}')

                # 3) Locais padrão por obra (Bloco A/B, Pavimentos, Setores)
                c_loc, e_loc = _criar_locais_padrao(obra_mapa, dry_run=dry_run)
                stats['locais_created'] += c_loc
                stats['locais_existentes'] += e_loc
                if not dry_run:
                    self.stdout.write(f'   Locais: {c_loc} criado(s), {e_loc} já existente(s).')

            # 4) Empresa padrão e Obras de Gestão (gestao_aprovacao)
            try:
                from django.contrib.auth.models import User
                from gestao_aprovacao.models import Empresa, Obra as ObraGestao
            except ImportError:
                self.stdout.write(self.style.WARNING('   Gestão (gestao_aprovacao) não disponível; pulando Empresa/Obra Gestão.'))
            else:
                # Servidor pode ter responsavel_id NOT NULL; usar um usuário existente
                responsavel_empresa = (
                    User.objects.filter(is_superuser=True).first()
                    or User.objects.filter(is_staff=True).first()
                    or User.objects.filter(is_active=True).first()
                )
                if not responsavel_empresa:
                    self.stdout.write(
                        self.style.WARNING('   Nenhum usuário no sistema; pulando Empresa e Obras de Gestão (responsavel obrigatório no servidor).')
                    )
                else:
                    defaults_empresa = {
                        'nome': 'LPLAN',
                        'ativo': True,
                        'responsavel': responsavel_empresa,
                    }
                    empresa, created_emp = Empresa.objects.get_or_create(
                        codigo='LPLAN',
                        defaults=defaults_empresa,
                    )
                    if created_emp:
                        stats['empresa_created'] += 1
                        if not dry_run:
                            self.stdout.write(self.style.SUCCESS(f'   [OK] Empresa: {empresa.codigo} – {empresa.nome}'))

                    for codigo, nome, _end, _resp in OBRAS_ESSENCIAIS:
                        proj = Project.objects.filter(code=codigo).first()
                        if not proj:
                            continue
                        og, created_og = ObraGestao.objects.get_or_create(
                            codigo=codigo,
                            defaults={
                                'nome': nome,
                                'project': proj,
                                'empresa': empresa,
                                'ativo': True,
                            },
                        )
                        if created_og:
                            stats['obra_gestao_created'] += 1
                            if not dry_run:
                                self.stdout.write(self.style.SUCCESS(f'   [OK] Obra (Gestão): {og.codigo}'))
                        else:
                            if (og.project_id != proj.id or og.nome != nome) and not dry_run:
                                og.project = proj
                                og.nome = nome
                                og.save(update_fields=['project', 'nome'])
                                stats['obra_gestao_updated'] += 1

        # Resumo
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Resumo bootstrap'))
        self.stdout.write(
            f"  Projects: {stats['project_created']} criado(s), {stats['project_updated']} atualizado(s)."
        )
        self.stdout.write(
            f"  Obras (Mapa): {stats['obra_mapa_created']} criada(s), {stats['obra_mapa_updated']} atualizada(s)."
        )
        self.stdout.write(
            f"  Locais: {stats['locais_created']} criado(s), {stats['locais_existentes']} já existente(s)."
        )
        if stats.get('empresa_created', 0) + stats.get('obra_gestao_created', 0) + stats.get('obra_gestao_updated', 0) > 0:
            self.stdout.write(
                f"  Gestão: Empresa {stats.get('empresa_created', 0)} criada; "
                f"Obras {stats.get('obra_gestao_created', 0)} criada(s), {stats.get('obra_gestao_updated', 0)} atualizada(s)."
            )
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run: nenhuma alteração persistida.'))
        else:
            self.stdout.write(self.style.SUCCESS('Bootstrap concluído. Dados essenciais garantidos.'))
