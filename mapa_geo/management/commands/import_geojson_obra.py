import json
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.models import Project

from mapa_geo.services import (
    import_geojson_features,
    kml_to_geojson_features,
    sync_snapshots_from_diario,
)


class Command(BaseCommand):
    help = 'Importa GeoJSON, KML ou KMZ para o mapa geográfico de uma obra (core.Project).'

    def add_arguments(self, parser):
        parser.add_argument('--project-code', required=True, help='Código do projeto (core.Project.code)')
        parser.add_argument('--file', required=True, help='Caminho do arquivo .geojson, .json, .kml ou .kmz')
        parser.add_argument('--replace', action='store_true', help='Remove elementos existentes antes de importar')
        parser.add_argument('--label', default='', help='Rótulo da fonte (opcional)')
        parser.add_argument('--sync-diario', action='store_true', help='Gera snapshots evolutivos a partir dos diários')

    def handle(self, *args, **options):
        code = options['project_code']
        path = Path(options['file'])
        if not path.exists():
            raise CommandError(f'Arquivo não encontrado: {path}')

        try:
            project = Project.objects.get(code=code)
        except Project.DoesNotExist as exc:
            raise CommandError(f'Projeto não encontrado: {code}') from exc

        suffix = path.suffix.lower()
        if suffix == '.kmz':
            with zipfile.ZipFile(path) as zf:
                kml_name = 'doc.kml' if 'doc.kml' in zf.namelist() else next(
                    (n for n in zf.namelist() if n.lower().endswith('.kml')),
                    None,
                )
                if not kml_name:
                    raise CommandError('KMZ sem KML interno.')
                raw = zf.read(kml_name).decode('utf-8', errors='replace')
            payload = kml_to_geojson_features(raw)
        else:
            raw = path.read_text(encoding='utf-8', errors='replace')
            if suffix == '.kml' or raw.lstrip().startswith('<'):
                payload = kml_to_geojson_features(raw)
            else:
                payload = json.loads(raw)

        stats = import_geojson_features(
            project,
            payload,
            source_label=options['label'] or path.name,
            replace=options['replace'],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Importado em {project.code}: {stats["created"]} criados, {stats["updated"]} atualizados.'
            )
        )

        if options['sync_diario']:
            sync_stats = sync_snapshots_from_diario(project)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Snapshots: {sync_stats["snapshots"]} registros em {sync_stats["dates"]} datas.'
                )
            )
