from django.core.management.base import BaseCommand

from recursos_humanos.forms import EMISSAO_ANO_MINIMO
from recursos_humanos.models import DocumentoColaborador


class Command(BaseCommand):
    help = (
        'Detecta documentos com data de emissão implausível (ano anterior a '
        f'{EMISSAO_ANO_MINIMO}) — normalmente causados por um ano digitado '
        'parcialmente no seletor de data (ex.: «2» vira 0002, gerando '
        'vencimento 0003). Use --fix para limpar a data de emissão e o '
        'vencimento desses registros, exigindo novo preenchimento pelo RH.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Limpa data de emissão e vencimento dos registros inválidos.',
        )

    def handle(self, *args, **options):
        invalidos = [
            doc
            for doc in DocumentoColaborador.objects.select_related('colaborador', 'tipo')
            if doc.data_emissao and doc.data_emissao.year < EMISSAO_ANO_MINIMO
        ]

        if not invalidos:
            self.stdout.write(self.style.SUCCESS('Nenhum documento com data de emissão inválida.'))
            return

        self.stdout.write(f'{len(invalidos)} documento(s) com data de emissão inválida:')
        for doc in invalidos:
            venc = doc.vencimento.isoformat() if doc.vencimento else '—'
            self.stdout.write(
                f'  #{doc.pk} {doc.colaborador.nome} · {doc.tipo.nome} · '
                f'emissão={doc.data_emissao.isoformat()} · vencimento={venc}'
            )

        if not options['fix']:
            self.stdout.write(self.style.WARNING('\nExecute com --fix para limpar esses registros.'))
            return

        for doc in invalidos:
            doc.data_emissao = None
            doc.vencimento = None
            doc.save(update_fields=['data_emissao', 'vencimento', 'atualizado_em'])

        self.stdout.write(self.style.SUCCESS(f'\n{len(invalidos)} registro(s) corrigido(s).'))
