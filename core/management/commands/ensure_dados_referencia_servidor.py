"""
Garante dados de referência para o Diário de Obra no SERVIDOR (produção ou staging).

Cria apenas:
- Tags de ocorrência (OccurrenceTag)
- Categorias e cargos de mão de obra (LaborCategory, LaborCargo)
- Categorias e equipamentos padrão (EquipmentCategory, StandardEquipment, Equipment)

Seguro para rodar em produção: usa get_or_create, não exige DEBUG.
Rode após migrate, junto com bootstrap (obras/projetos) se necessário.

Uso:
    python manage.py ensure_dados_referencia_servidor
    python manage.py ensure_dados_referencia_servidor --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    OccurrenceTag,
    LaborCategory,
    LaborCargo,
    EquipmentCategory,
    StandardEquipment,
    Equipment,
)


TAGS_OCORRENCIA = [
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


def ensure_tags(dry_run=False):
    """Cria tags de ocorrência. Idempotente."""
    created = 0
    for name, color in TAGS_OCORRENCIA:
        if dry_run:
            if not OccurrenceTag.objects.filter(name=name).exists():
                created += 1
            continue
        _, was_created = OccurrenceTag.objects.get_or_create(
            name=name, defaults={"color": color, "is_active": True}
        )
        if was_created:
            created += 1
    return created


def ensure_labor_equipment(dry_run=False):
    """Cria categorias de mão de obra, cargos e equipamentos. Idempotente."""
    if dry_run:
        return 0, 0
    labor_created = 0
    equipment_created = 0

    cat_indireta, c = LaborCategory.objects.get_or_create(
        slug="indireta", defaults={"name": "Indireta (LPLAN)", "order": 0}
    )
    labor_created += 1 if c else 0
    for name in ["Pedreiro", "Mestre de Obras", "Servente", "Engenheiro de Campo"]:
        _, c = LaborCargo.objects.get_or_create(
            category=cat_indireta, name=name, defaults={"order": 0}
        )
        labor_created += 1 if c else 0

    cat_direta, c = LaborCategory.objects.get_or_create(
        slug="direta", defaults={"name": "Direta", "order": 1}
    )
    labor_created += 1 if c else 0
    for name in ["Eletricista", "Encarregado", "Carpinteiro"]:
        _, c = LaborCargo.objects.get_or_create(
            category=cat_direta, name=name, defaults={"order": 0}
        )
        labor_created += 1 if c else 0

    cat_terc, c = LaborCategory.objects.get_or_create(
        slug="terceirizada", defaults={"name": "Terceirizada", "order": 2}
    )
    labor_created += 1 if c else 0
    for name in ["Eletricista terceirizado", "Pedreiro terceirizado", "Encanador terceirizado"]:
        _, c = LaborCargo.objects.get_or_create(
            category=cat_terc, name=name, defaults={"order": 0}
        )
        labor_created += 1 if c else 0

    # Equipamentos
    cat_maq, c = EquipmentCategory.objects.get_or_create(
        slug="maquinas", defaults={"name": "Máquinas", "order": 0}
    )
    equipment_created += 1 if c else 0
    for name in [
        "Betoneira", "Escavadeira", "Caminhão basculante", "Retroescavadeira",
        "Guincho", "Pá carregadeira", "Rolo compactador", "Caminhão betoneira",
    ]:
        _, c = StandardEquipment.objects.get_or_create(
            category=cat_maq, name=name, defaults={"order": 0}
        )
        equipment_created += 1 if c else 0

    cat_cant, c = EquipmentCategory.objects.get_or_create(
        slug="canteiro", defaults={"name": "Canteiro", "order": 1}
    )
    equipment_created += 1 if c else 0
    for name in [
        "Andaime", "Bomba de concreto", "Grua", "Escoramento metálico",
        "Fôrma metálica", "Cimbramento", "Torre de iluminação",
    ]:
        _, c = StandardEquipment.objects.get_or_create(
            category=cat_cant, name=name, defaults={"order": 0}
        )
        equipment_created += 1 if c else 0

    cat_ferr, c = EquipmentCategory.objects.get_or_create(
        slug="ferramentas", defaults={"name": "Ferramentas e Pequenos Equipamentos", "order": 2}
    )
    equipment_created += 1 if c else 0
    for name in [
        "Compressor", "Betoneira portátil", "Cortadora de piso", "Vibrador de concreto",
        "Gerador", "Bomba d'água", "Cortadora de ferro",
    ]:
        _, c = StandardEquipment.objects.get_or_create(
            category=cat_ferr, name=name, defaults={"order": 0}
        )
        equipment_created += 1 if c else 0

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
        _, c = Equipment.objects.get_or_create(
            code=code, defaults={"name": name, "equipment_type": eq_type, "is_active": True}
        )
        equipment_created += 1 if c else 0

    return labor_created, equipment_created


class Command(BaseCommand):
    help = (
        "Garante dados de referência do Diário no servidor: "
        "tags de ocorrência, categorias/cargos de mão de obra e equipamentos. Idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas mostra o que seria criado, sem gravar.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: nenhuma alteração no banco."))

        with transaction.atomic():
            n_tags = ensure_tags(dry_run=dry_run)
            labor_n, equipment_n = ensure_labor_equipment(dry_run=dry_run)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Dados de referência (Diário)"))
        self.stdout.write(f"  Tags de ocorrência: {n_tags} criada(s).")
        if not dry_run:
            self.stdout.write(f"  Mão de obra / equipamentos: {labor_n} + {equipment_n} itens criados ou já existentes.")
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: nenhuma alteração persistida."))
        else:
            self.stdout.write(self.style.SUCCESS("Concluído. Tags, mão de obra e equipamentos garantidos."))
