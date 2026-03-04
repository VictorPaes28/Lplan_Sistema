"""
Cadastra as obras LPlan (Marghot, Entreáguas, Okena, Sunrise) no Mapa de Obras
e os projetos correspondentes no core (Diário de Obra / seleção de obra).

NO SERVIDOR:
- Rode uma vez: python manage.py seed_obras_lplan
- Códigos abaixo são os que batem com o Sienge/CSV. Se descobrir outro número para
  alguma obra, altere a lista OBRAS_LPLAN e rode de novo (get_or_create não duplica).
- Responsáveis: preencher Project.responsible (nome) no admin e vincular usuários
  em ProjectMember / ProjectOwner por projeto.
- Locais (Bloco, Pavimento, etc.): cadastrar em Mapa de Obras > Locais quando
  tiver a lista definitiva.

Referência: core/frontend_views.py OBRA_CONTRATANTE_MAP (contratantes).
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from mapa_obras.models import Obra


# (codigo_sienge, nome_exibicao, contratante, responsavel_nome)
# codigo_sienge = código no Sienge e no CSV do MAPA_CONTROLE (único por obra)
# responsavel_nome = nome do responsável (opcional; preencher no servidor se já souber)
OBRAS_LPLAN = [
    ('224', 'Entreáguas', 'Incorporadora Adamo', ''),
    ('242', 'Okena', 'JP Empreendimentos', ''),
    ('259', 'Marghot', 'Antonina Hotéis', ''),
    ('260', 'Sunrise', 'Rpontes', ''),
]


class Command(BaseCommand):
    help = 'Cadastra as obras LPlan e projetos core (pronto para servidor: códigos, locais e responsáveis depois)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra o que seria feito, sem gravar',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('Modo dry-run: nenhuma alteração no banco.'))

        with transaction.atomic():
            for codigo, nome, contratante, responsavel_nome in OBRAS_LPLAN:
                display = f"{nome} ({contratante})" if contratante else nome
                try:
                    obra, created_obra = Obra.objects.get_or_create(
                        codigo_sienge=codigo,
                        defaults={
                            'nome': display,
                            'ativa': True,
                        },
                    )
                    if created_obra:
                        if dry_run:
                            self.stdout.write(f'   [DRY-RUN] Criaria Obra: {codigo} - {display}')
                        else:
                            self.stdout.write(self.style.SUCCESS(f'   [OK] Obra: {obra}'))
                    else:
                        self.stdout.write(f'   [EXISTE] Obra: {obra}')

                    # Projeto core (code = codigo_sienge para Diário de Obra e Mapa verem a mesma obra)
                    from datetime import date
                    from core.models import Project
                    # Datas placeholder (obrigatórias no modelo); ajustar no servidor se necessário
                    hoje = date.today()
                    fim_placeholder = date(hoje.year + 2, 12, 31)
                    project, created_proj = Project.objects.get_or_create(
                        code=codigo,
                        defaults={
                            'name': display,
                            'is_active': True,
                            'responsible': (responsavel_nome or '').strip(),
                            'client_name': (contratante or '').strip(),
                            'start_date': hoje,
                            'end_date': fim_placeholder,
                        },
                    )
                    if created_proj:
                        if dry_run:
                            self.stdout.write(f'   [DRY-RUN] Criaria Project: code={codigo}')
                        else:
                            self.stdout.write(self.style.SUCCESS(f'   [OK] Project: {project.code} - {project.name}'))
                    else:
                        if not dry_run and (responsavel_nome or '').strip() and not project.responsible:
                            project.responsible = (responsavel_nome or '').strip()
                            project.save(update_fields=['responsible'])
                        self.stdout.write(f'   [EXISTE] Project: {project.code}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'   [ERRO] {codigo} - {e}'))
                    raise

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                '\nObras e projetos criados. No servidor: vincule responsáveis (ProjectMember/ProjectOwner) '
                'e cadastre locais (Mapa de Obras > Locais) quando tiver a lista.'
            ))
