"""
Gera dados para o Mapa de Suprimentos: ~60 insumos GROSSOS por obra.

O Mapa de Suprimentos é focado em insumos de grande volume/valor (grossos):
- Agregados: areia, brita, pedra, cascalho
- Cimento e cal
- Concreto usinado
- Aço (vergalhões, telas)
- Blocos, tijolos, argamassas
- Formas e escoramento
- Revestimentos (porcelanato, cerâmica, fachada)
- Telhas, esquadrias, louças, tubos e reservatórios

NÃO inclui: parafusos, rejunte fino, tintas em pequeno volume, acessórios.

Uso:
    python manage.py seed_insumos_grossos
    python manage.py seed_insumos_grossos --limpar   # Remove itens/insumos criados por este comando e recria
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from datetime import date, timedelta
import random

from mapa_obras.models import Obra, LocalObra
from suprimentos.models import Insumo, ItemMapa


# 60 insumos grossos: (codigo_sienge, descricao, unidade, categoria)
INSUMOS_GROSSOS = [
    # --- FUNDAÇÃO ---
    ('GROS-001', 'Cimento Portland CP II-32', 'KG', 'FUNDAÇÃO'),
    ('GROS-002', 'Cimento Portland CP II-E', 'KG', 'FUNDAÇÃO'),
    ('GROS-003', 'Areia média lavada', 'M³', 'FUNDAÇÃO'),
    ('GROS-004', 'Areia grossa', 'M³', 'FUNDAÇÃO'),
    ('GROS-005', 'Brita 1', 'M³', 'FUNDAÇÃO'),
    ('GROS-006', 'Brita 2', 'M³', 'FUNDAÇÃO'),
    ('GROS-007', 'Pedra britada (bica corrida)', 'M³', 'FUNDAÇÃO'),
    ('GROS-008', 'Rachão', 'M³', 'FUNDAÇÃO'),
    ('GROS-009', 'Estaca pré-moldada 30x30', 'M', 'FUNDAÇÃO'),
    ('GROS-010', 'Concreto usinado FCK 15 MPa (fundação)', 'M³', 'FUNDAÇÃO'),
    # --- SUPERESTRUTURA ---
    ('GROS-011', 'Concreto usinado FCK 20 MPa', 'M³', 'SUPERESTRUTURA'),
    ('GROS-012', 'Concreto usinado FCK 25 MPa', 'M³', 'SUPERESTRUTURA'),
    ('GROS-013', 'Concreto usinado FCK 30 MPa', 'M³', 'SUPERESTRUTURA'),
    ('GROS-014', 'Concreto usinado FCK 35 MPa', 'M³', 'SUPERESTRUTURA'),
    ('GROS-015', 'Concreto usinado FCK 40 MPa', 'M³', 'SUPERESTRUTURA'),
    ('GROS-016', 'Aço CA-50 vergalhões 6,3 mm', 'KG', 'SUPERESTRUTURA'),
    ('GROS-017', 'Aço CA-50 vergalhões 8 mm', 'KG', 'SUPERESTRUTURA'),
    ('GROS-018', 'Aço CA-50 vergalhões 10 mm', 'KG', 'SUPERESTRUTURA'),
    ('GROS-019', 'Aço CA-50 vergalhões 12,5 mm', 'KG', 'SUPERESTRUTURA'),
    ('GROS-020', 'Aço CA-60 (telas e treliças)', 'KG', 'SUPERESTRUTURA'),
    ('GROS-021', 'Tela soldada Q-75', 'M²', 'SUPERESTRUTURA'),
    ('GROS-022', 'Tela soldada Q-90', 'M²', 'SUPERESTRUTURA'),
    ('GROS-023', 'Forma de madeira compensada 18 mm', 'M²', 'SUPERESTRUTURA'),
    ('GROS-024', 'Escoramento metálico', 'M²', 'SUPERESTRUTURA'),
    ('GROS-025', 'Laje treliçada H12', 'M²', 'SUPERESTRUTURA'),
    # --- ALVENARIA/FECHAMENTO ---
    ('GROS-026', 'Argamassa de assentamento', 'KG', 'ALVENARIA/FECHAMENTO'),
    ('GROS-027', 'Bloco cerâmico 14x19x29', 'UND', 'ALVENARIA/FECHAMENTO'),
    ('GROS-028', 'Bloco cerâmico 9x19x29', 'UND', 'ALVENARIA/FECHAMENTO'),
    ('GROS-029', 'Bloco de concreto estrutural 19x19x39', 'UND', 'ALVENARIA/FECHAMENTO'),
    ('GROS-030', 'Tijolo baiano 6 furos', 'UND', 'ALVENARIA/FECHAMENTO'),
    ('GROS-031', 'Verga e contraverga pré-moldada', 'UND', 'ALVENARIA/FECHAMENTO'),
    ('GROS-032', 'Areia fina (assentamento)', 'M³', 'ALVENARIA/FECHAMENTO'),
    # --- REGULARIZAÇÃO E IMPERMEABILIZAÇÃO ---
    ('GROS-033', 'Argamassa de revestimento (emboço)', 'KG', 'REGULARIZAÇÃO E IMPERMEABILIZAÇÃO'),
    ('GROS-034', 'Manta impermeabilizante', 'M²', 'REGULARIZAÇÃO E IMPERMEABILIZAÇÃO'),
    ('GROS-035', 'Cal hidratada', 'KG', 'REGULARIZAÇÃO E IMPERMEABILIZAÇÃO'),
    # --- REVESTIMENTOS ---
    ('GROS-036', 'Porcelanato piso 60x60', 'M²', 'REVESTIMENTO DE PISO'),
    ('GROS-037', 'Porcelanato piso 80x80', 'M²', 'REVESTIMENTO DE PISO'),
    ('GROS-038', 'Piso cerâmico 45x45', 'M²', 'REVESTIMENTO DE PISO'),
    ('GROS-039', 'Azulejo / pastilha parede', 'M²', 'REVESTIMENTO DE PAREDE'),
    ('GROS-040', 'Revestimento cerâmico fachada', 'M²', 'REVESTIMENTO DE FACHADA'),
    ('GROS-041', 'Argamassa colante', 'KG', 'REVESTIMENTO DE PISO'),
    # --- PINTURA (volume grosso) ---
    ('GROS-042', 'Tinta látex PVA 18 L', 'L', 'PINTURA'),
    ('GROS-043', 'Tinta acrílica premium 18 L', 'L', 'PINTURA'),
    ('GROS-044', 'Massas corrida/acrílica', 'KG', 'PINTURA'),
    # --- ESQUADRIAS E LOUÇAS ---
    ('GROS-045', 'Porta de madeira 80x210', 'UND', 'ESQUADRIA MADEIRA'),
    ('GROS-046', 'Porta de madeira 90x210', 'UND', 'ESQUADRIA MADEIRA'),
    ('GROS-047', 'Janela de alumínio 120x120', 'UND', 'ESQUADRIA ALUMÍNIO/VIDRO'),
    ('GROS-048', 'Janela de alumínio 150x150', 'UND', 'ESQUADRIA ALUMÍNIO/VIDRO'),
    ('GROS-049', 'Vaso sanitário com caixa acoplada', 'UND', 'LOUÇAS E METAIS'),
    ('GROS-050', 'Lavatório', 'UND', 'LOUÇAS E METAIS'),
    ('GROS-051', 'Torneira de parede', 'UND', 'LOUÇAS E METAIS'),
    # --- INSTALAÇÕES (tubos e reservatórios grossos) ---
    ('GROS-052', 'Tubo PVC 100 mm esgoto', 'M', 'INSTALAÇÕES ESGOTO'),
    ('GROS-053', 'Tubo PVC 75 mm esgoto', 'M', 'INSTALAÇÕES ESGOTO'),
    ('GROS-054', 'Tubo PVC 50 mm água fria', 'M', 'INSTALAÇÕES HIDRÁULICA'),
    ('GROS-055', 'Caixa d\'água polietileno 1000 L', 'UND', 'INSTALAÇÕES HIDRÁULICA'),
    ('GROS-056', 'Caixa d\'água polietileno 5000 L', 'UND', 'INSTALAÇÕES HIDRÁULICA'),
    ('GROS-057', 'Fio/cabo elétrico 4 mm²', 'M', 'INSTALAÇÕES ELÉTRICA'),
    ('GROS-058', 'Fio/cabo elétrico 6 mm²', 'M', 'INSTALAÇÕES ELÉTRICA'),
    ('GROS-059', 'Quadro de distribuição 24 disjuntores', 'UND', 'INSTALAÇÕES ELÉTRICA'),
    # --- COBERTA / COMPLEMENTARES ---
    ('GROS-060', 'Telha cerâmica', 'UND', 'COBERTA'),
    ('GROS-061', 'Telha metálica', 'M²', 'COBERTA'),
    ('GROS-062', 'Aditivo plastificante concreto', 'L', 'A CLASSIFICAR'),
    ('GROS-063', 'Rejunte flexível (embalagem grande)', 'KG', 'A CLASSIFICAR'),
]


def quantidade_realista(unidade):
    """Retorna uma quantidade planejada realista conforme unidade (insumos grossos)."""
    if unidade == 'KG':
        return Decimal(str(random.randint(500, 6000)))
    if unidade == 'M³':
        return Decimal(str(round(random.uniform(5, 80), 2)))
    if unidade == 'M²':
        return Decimal(str(random.randint(20, 400)))
    if unidade == 'M':
        return Decimal(str(random.randint(50, 500)))
    if unidade == 'L':
        return Decimal(str(random.randint(20, 200)))
    if unidade == 'UND':
        return Decimal(str(random.randint(10, 300)))
    return Decimal(str(random.randint(50, 500)))


class Command(BaseCommand):
    help = 'Gera ~60 insumos grossos e itens do mapa para cada obra (quantidades realistas)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpar',
            action='store_true',
            help='Remove insumos GROS-* e itens do mapa antes de recriar',
        )

    def handle(self, *args, **options):
        limpar = options.get('limpar', False)

        if limpar:
            with transaction.atomic():
                codigos = [c[0] for c in INSUMOS_GROSSOS]
                itens_rem = ItemMapa.objects.filter(insumo__codigo_sienge__in=codigos).count()
                ItemMapa.objects.filter(insumo__codigo_sienge__in=codigos).delete()
                Insumo.objects.filter(codigo_sienge__in=codigos).delete()
                self.stdout.write(self.style.WARNING(
                    f'   Removidos {itens_rem} itens do mapa e {len(codigos)} insumos GROS-*'
                ))

        obras = list(Obra.objects.filter(ativa=True).order_by('nome'))
        if not obras:
            self.stdout.write(self.style.ERROR('Nenhuma obra ativa encontrada. Crie obras antes.'))
            return

        with transaction.atomic():
            insumos_com_categoria = []
            for codigo, descricao, unidade, categoria in INSUMOS_GROSSOS:
                ins, created = Insumo.objects.get_or_create(
                    codigo_sienge=codigo,
                    defaults={
                        'descricao': descricao,
                        'unidade': unidade,
                        'ativo': True,
                        'eh_macroelemento': True,
                    },
                )
                if not created:
                    ins.descricao = descricao
                    ins.unidade = unidade
                    ins.eh_macroelemento = True
                    ins.save(update_fields=['descricao', 'unidade', 'eh_macroelemento'])
                insumos_com_categoria.append((ins, categoria, unidade))

            self.stdout.write(self.style.SUCCESS(f'   {len(insumos_com_categoria)} insumos grossos no catálogo.'))

            total_itens = 0
            hoje = date.today()
            for obra in obras:
                locais = list(obra.locais.all())
                for insumo, categoria, unidade in insumos_com_categoria:
                    local = random.choice(locais) if locais else None
                    qtd = quantidade_realista(unidade)
                    prazo = hoje + timedelta(days=random.randint(15, 120))
                    prioridades = ['URGENTE', 'ALTA', 'MEDIA', 'MEDIA', 'BAIXA']
                    prioridade = random.choice(prioridades)
                    item, created = ItemMapa.objects.get_or_create(
                        obra=obra,
                        insumo=insumo,
                        defaults={
                            'categoria': categoria,
                            'prioridade': prioridade,
                            'quantidade_planejada': qtd,
                            'prazo_necessidade': prazo,
                            'local_aplicacao': local,
                        },
                    )
                    if not created:
                        item.categoria = categoria
                        item.quantidade_planejada = qtd
                        item.prazo_necessidade = prazo
                        item.local_aplicacao = local
                        item.save(update_fields=['categoria', 'quantidade_planejada', 'prazo_necessidade', 'local_aplicacao'])
                    total_itens += 1
                self.stdout.write(f'   Obra "{obra.nome}": {len(insumos_com_categoria)} itens do mapa.')

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Concluído. Total de itens do mapa: {total_itens} '
            f'({len(obras)} obra(s) × {len(INSUMOS_GROSSOS)} insumos grossos).\n'
        ))
