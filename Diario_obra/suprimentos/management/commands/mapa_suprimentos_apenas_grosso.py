"""
Limpa todos os dados do Mapa de Suprimentos e deixa apenas insumos grossos.

Use para deixar o sistema como vai funcionar de fato: cadastro manual de itens
grossos (cimento, areia, brita, aço, blocos, concreto usinado, revestimentos)
e vínculo manual com o Sienge. Assim não confunde na hora de ensinar.

Remove:
- HistoricoAlteracao
- AlocacaoRecebimento
- NotaFiscalEntrada
- ItemMapa
- RecebimentoObra
- Insumo (catálogo inteiro)

Recria apenas o catálogo de INSUMOS GROSSOS e cria um item do mapa para
cada insumo em CADA OBRA (assim ao abrir qualquer obra já aparecem todos os itens).

Mantém: Obras, Locais, Usuários.

Uso:
    python manage.py mapa_suprimentos_apenas_grosso
    python manage.py mapa_suprimentos_apenas_grosso --confirmar
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from mapa_obras.models import Obra
from suprimentos.models import (
    HistoricoAlteracao,
    AlocacaoRecebimento,
    NotaFiscalEntrada,
    ItemMapa,
    RecebimentoObra,
    Insumo,
)


# Catálogo fixo: insumos grossos + categoria de aplicação (cod, descrição, unidade, categoria)
INSUMOS_GROSSOS = [
    # Fundação
    ('1001', 'Cimento Portland CP II-32', 'KG', 'FUNDAÇÃO'),
    ('1002', 'Cimento Portland CP II-E', 'KG', 'FUNDAÇÃO'),
    ('1003', 'Areia média lavada', 'M³', 'FUNDAÇÃO'),
    ('1005', 'Brita 1', 'M³', 'FUNDAÇÃO'),
    ('1007', 'Pedra britada (bica corrida)', 'M³', 'FUNDAÇÃO'),
    # Superestrutura
    ('1004', 'Areia fina', 'M³', 'SUPERESTRUTURA'),
    ('1006', 'Brita 2', 'M³', 'SUPERESTRUTURA'),
    ('1008', 'Concreto usinado FCK 20 MPa', 'M³', 'SUPERESTRUTURA'),
    ('1009', 'Concreto usinado FCK 30 MPa', 'M³', 'SUPERESTRUTURA'),
    ('1010', 'Concreto usinado FCK 35 MPa', 'M³', 'SUPERESTRUTURA'),
    ('1013', 'Aço CA-50 vergalhões', 'KG', 'SUPERESTRUTURA'),
    ('1014', 'Aço CA-60 (telas e treliças)', 'KG', 'SUPERESTRUTURA'),
    ('1015', 'Tela soldada', 'M²', 'SUPERESTRUTURA'),
    ('1020', 'Forma de madeira compensada', 'M²', 'SUPERESTRUTURA'),
    ('1021', 'Escoramento metálico', 'M²', 'SUPERESTRUTURA'),
    # Alvenaria / fechamento
    ('1011', 'Argamassa de assentamento', 'KG', 'ALVENARIA/FECHAMENTO'),
    ('1016', 'Bloco cerâmico 14x19x29', 'UND', 'ALVENARIA/FECHAMENTO'),
    ('1017', 'Bloco de concreto estrutural', 'UND', 'ALVENARIA/FECHAMENTO'),
    ('1018', 'Tijolo baiano', 'UND', 'ALVENARIA/FECHAMENTO'),
    ('1019', 'Verga e contraverga pré-moldada', 'UND', 'ALVENARIA/FECHAMENTO'),
    # Regularização e revestimento
    ('1012', 'Argamassa de revestimento', 'KG', 'REGULARIZAÇÃO E IMPERMEABILIZAÇÃO'),
    ('1022', 'Porcelanato piso', 'M²', 'REVESTIMENTO DE PISO'),
    ('1023', 'Azulejo / pastilha', 'M²', 'REVESTIMENTO DE PAREDE'),
    ('1024', 'Revestimento cerâmico fachada', 'M²', 'REVESTIMENTO DE FACHADA'),
    ('1025', 'Tinta látex PVA', 'L', 'PINTURA'),
    ('1026', 'Tinta acrílica premium', 'L', 'PINTURA'),
    # Esquadrias e louças
    ('1027', 'Porta de madeira', 'UND', 'ESQUADRIA MADEIRA'),
    ('1028', 'Janela de alumínio', 'UND', 'ESQUADRIA ALUMÍNIO/VIDRO'),
    ('1029', 'Louça sanitária (vaso, lavatório)', 'UND', 'LOUÇAS E METAIS'),
    ('1030', 'Metais (torneira, registro)', 'UND', 'LOUÇAS E METAIS'),
    # Alguns deixados para classificar depois (triagem)
    ('1031', 'Manta impermeabilizante', 'M²', 'A CLASSIFICAR'),
    ('1032', 'Aditivo plastificante', 'L', 'A CLASSIFICAR'),
    ('1033', 'Rejunte flexível', 'KG', 'A CLASSIFICAR'),
]


class Command(BaseCommand):
    help = 'Limpa dados do Mapa de Suprimentos e deixa só insumos grossos (para demonstração)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma a limpeza e recriação (sem isso, apenas mostra o que será feito)',
        )

    def handle(self, *args, **options):
        confirmar = options.get('confirmar', False)

        if not confirmar:
            self.stdout.write(self.style.WARNING(
                '\n⚠️  MODO SIMULAÇÃO - Nada será alterado.\n'
                'Use --confirmar para realmente limpar e recriar os insumos grossos.\n'
            ))

        # Contagens atuais
        n_hist = HistoricoAlteracao.objects.count()
        n_aloc = AlocacaoRecebimento.objects.count()
        n_nf = NotaFiscalEntrada.objects.count()
        n_itens = ItemMapa.objects.count()
        n_rec = RecebimentoObra.objects.count()
        n_ins = Insumo.objects.count()

        self.stdout.write(self.style.SUCCESS('\n📊 O QUE SERÁ REMOVIDO:\n'))
        self.stdout.write(f'   HistoricoAlteracao: {n_hist}')
        self.stdout.write(f'   AlocacaoRecebimento: {n_aloc}')
        self.stdout.write(f'   NotaFiscalEntrada: {n_nf}')
        self.stdout.write(f'   ItemMapa: {n_itens}')
        self.stdout.write(f'   RecebimentoObra: {n_rec}')
        self.stdout.write(f'   Insumo (catálogo): {n_ins}')

        obras = list(Obra.objects.all().order_by('id'))
        n_obras = len(obras)
        itens_a_criar = n_obras * len(INSUMOS_GROSSOS) if n_obras else 0

        self.stdout.write(self.style.SUCCESS('\n✅ O QUE SERÁ CRIADO:\n'))
        self.stdout.write(f'   Insumos grossos: {len(INSUMOS_GROSSOS)} (com categorias variadas)')
        for cod, desc, un, cat in INSUMOS_GROSSOS:
            self.stdout.write(f'      {cod} - {desc} ({un}) → {cat}')
        self.stdout.write(f'   Itens do mapa: {itens_a_criar} ({len(INSUMOS_GROSSOS)} itens × {n_obras} obra(s))')

        self.stdout.write(self.style.SUCCESS('\n✅ MANTIDO: Obras, Locais, Usuários\n'))

        if not confirmar:
            self.stdout.write(self.style.WARNING(
                '\n💡 Para aplicar, execute:\n'
                '   python manage.py mapa_suprimentos_apenas_grosso --confirmar\n'
            ))
            return

        self.stdout.write(self.style.WARNING('\n🗑️  Executando limpeza e recriação...\n'))

        with transaction.atomic():
            # Ordem respeitando FKs
            HistoricoAlteracao.objects.all().delete()
            self.stdout.write('   HistoricoAlteracao: removido')
            AlocacaoRecebimento.objects.all().delete()
            self.stdout.write('   AlocacaoRecebimento: removido')
            NotaFiscalEntrada.objects.all().delete()
            self.stdout.write('   NotaFiscalEntrada: removido')
            ItemMapa.objects.all().delete()
            self.stdout.write('   ItemMapa: removido')
            RecebimentoObra.objects.all().delete()
            self.stdout.write('   RecebimentoObra: removido')
            Insumo.objects.all().delete()
            self.stdout.write('   Insumo: removido')

            insumos_com_categoria = []
            for codigo, descricao, unidade, categoria in INSUMOS_GROSSOS:
                ins = Insumo.objects.create(
                    codigo_sienge=codigo,
                    descricao=descricao,
                    unidade=unidade,
                    ativo=True,
                    eh_macroelemento=True,
                )
                insumos_com_categoria.append((ins, categoria))
            self.stdout.write(self.style.SUCCESS(f'\n   {len(INSUMOS_GROSSOS)} insumos grossos criados.'))

            # Criar um item do mapa para cada insumo em cada obra (categoria já definida)
            obras = list(Obra.objects.all().order_by('id'))
            total_itens = 0
            for obra in obras:
                primeiro_local = obra.locais.first()  # pode ser None
                for insumo, categoria in insumos_com_categoria:
                    ItemMapa.objects.create(
                        obra=obra,
                        insumo=insumo,
                        categoria=categoria,
                        prioridade='MEDIA',
                        local_aplicacao=primeiro_local,
                        quantidade_planejada=0,
                    )
                    total_itens += 1
            self.stdout.write(self.style.SUCCESS(f'   {total_itens} itens do mapa criados ({len(obras)} obra(s)).'))

        self.stdout.write(self.style.SUCCESS(
            '\n✅ Concluído. Mapa de Suprimentos está só com insumos grossos.\n'
            '   Em cada obra aparecem todos os itens grossos; o engenheiro associa o código do Sienge depois.\n'
        ))
