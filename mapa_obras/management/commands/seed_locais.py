"""
Cria locais (Bloco, Pavimento, Setor) para obras no Mapa de Obras.

Uso:
  python manage.py seed_locais
  python manage.py seed_locais --obra 224
  python manage.py seed_locais --obra 224 --dry-run

Se --obra não for informado, cria locais para todas as obras ativas.
--obra pode ser o código Sienge (ex: 224) ou o ID da obra.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from mapa_obras.models import Obra, LocalObra


def _criar_locais_simples(obra, dry_run=False):
    """Versão simples: Bloco A, Bloco B, Pavimento 1, Pavimento Térreo, Lobby, Setor 1."""
    criados = 0
    existentes = 0
    pais = {}

    raizes = [
        ('Bloco A', 'BLOCO'),
        ('Bloco B', 'BLOCO'),
    ]
    for nome, tipo in raizes:
        if dry_run:
            if not LocalObra.objects.filter(obra=obra, nome=nome, parent__isnull=True).exists():
                criados += 1
            else:
                existentes += 1
        else:
            obj, c = LocalObra.objects.get_or_create(obra=obra, nome=nome, parent=None, defaults={'tipo': tipo})
            pais[nome] = obj
            criados += 1 if c else 0
            existentes += 0 if c else 1

    if dry_run:
        # Contar também filhos que seriam criados
        filhos = [
            ('Pavimento 1', 'PAVIMENTO', 'Bloco A'),
            ('Pavimento Térreo', 'PAVIMENTO', 'Bloco A'),
            ('Pavimento 1', 'PAVIMENTO', 'Bloco B'),
            ('Lobby', 'SETOR', 'Bloco A'),
            ('Setor 1', 'SETOR', 'Bloco A'),
        ]
        for nome, tipo, parent_nome in filhos:
            parent = LocalObra.objects.filter(obra=obra, nome=parent_nome, parent__isnull=True).first()
            if not parent:
                continue
            if not LocalObra.objects.filter(obra=obra, nome=nome, parent=parent).exists():
                criados += 1
            else:
                existentes += 1
        return criados, existentes

    # Pavimentos e setores (parent = Bloco A ou B)
    filhos = [
        ('Pavimento 1', 'PAVIMENTO', 'Bloco A'),
        ('Pavimento Térreo', 'PAVIMENTO', 'Bloco A'),
        ('Pavimento 1', 'PAVIMENTO', 'Bloco B'),
        ('Lobby', 'SETOR', 'Bloco A'),
        ('Setor 1', 'SETOR', 'Bloco A'),
    ]
    for nome, tipo, parent_nome in filhos:
        parent = pais.get(parent_nome)
        if not parent:
            continue
        obj, c = LocalObra.objects.get_or_create(
            obra=obra, nome=nome, parent=parent, defaults={'tipo': tipo}
        )
        criados += 1 if c else 0
        existentes += 0 if c else 1

    return criados, existentes


class Command(BaseCommand):
    help = 'Cria locais (Bloco, Pavimento, Setor) para obras. Use --obra para uma obra ou deixe vazio para todas ativas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--obra',
            type=str,
            default=None,
            help='Código Sienge (ex: 224) ou ID da obra. Se omitido, aplica em todas as obras ativas.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra o que seria criado, sem gravar.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        obra_arg = options.get('obra')

        if dry_run:
            self.stdout.write(self.style.WARNING('Modo dry-run: nenhuma alteração no banco.'))

        if obra_arg:
            try:
                if str(obra_arg).isdigit() and len(str(obra_arg)) <= 5:
                    obras = Obra.objects.filter(ativa=True).filter(
                        Q(id=int(obra_arg)) | Q(codigo_sienge=str(obra_arg))
                    )
                else:
                    obras = Obra.objects.filter(ativa=True, codigo_sienge=str(obra_arg))
            except ValueError:
                obras = Obra.objects.filter(ativa=True, codigo_sienge=str(obra_arg))
            if not obras.exists():
                self.stdout.write(self.style.ERROR(f'Obra não encontrada: {obra_arg}'))
                return
        else:
            obras = Obra.objects.filter(ativa=True).order_by('nome')

        if not obras.exists():
            self.stdout.write(self.style.WARNING('Nenhuma obra ativa encontrada. Crie obras antes (ex.: python manage.py seed_obras_lplan).'))
            return

        total_criados = 0
        total_existentes = 0

        with transaction.atomic():
            for obra in obras:
                self.stdout.write(f'\nObra: {obra} (id={obra.id})')
                c, e = _criar_locais_simples(obra, dry_run=dry_run)
                total_criados += c
                total_existentes += e
                if dry_run:
                    self.stdout.write(f'   [DRY-RUN] Criaria {c} local(is), {e} já existente(s).')
                else:
                    self.stdout.write(self.style.SUCCESS(f'   [OK] Criados: {c}, já existentes: {e}.'))

        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING(f'Total: criaria {total_criados} local(is), {total_existentes} já existente(s).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Total: {total_criados} local(is) criado(s), {total_existentes} já existente(s).'))
