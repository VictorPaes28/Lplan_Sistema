from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from core.models import Activity, ConstructionDiary, DailyWorkLog, DiaryStatus, Project
from core.services import ProgressService

DIARY_STATUSES_FOR_GEO_PROGRESS = (
    DiaryStatus.APROVADO,
    DiaryStatus.AGUARDANDO_APROVACAO_GESTOR,
    DiaryStatus.PREENCHENDO,
    DiaryStatus.SALVAMENTO_PARCIAL,
)

from .models import GeoFeature, GeoObraConfig, GeoProgressSnapshot

KML_NS = {'kml': 'http://www.opengis.net/kml/2.2'}


def _decimal(value: float | int | str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _infer_kind(name: str, folder: str, geometry_type: str) -> str:
    text = f'{name} {folder}'.lower()
    if geometry_type == 'LineString':
        return 'segment'
    if geometry_type == 'Polygon':
        return 'area'
    if any(k in text for k in ('vistoria', 'abordagem', 'images')):
        return 'vistoria'
    if any(k in text for k in ('caixa', 'cs0', 'poste')):
        return 'caixa'
    if any(
        k in text
        for k in (
            'pedra',
            'alagado',
            'ponte',
            'rocha',
            'travessia',
            'cerca',
            'lagoa',
            'vilarejo',
        )
    ):
        return 'obstacle'
    if geometry_type == 'Point':
        return 'point'
    return 'other'


def _status_from_progress(progress: Decimal) -> str:
    if progress >= Decimal('100'):
        return 'completed'
    if progress > Decimal('0'):
        return 'in_progress'
    return 'planned'


def _coords_centroid(geometry_type: str, geometry: dict) -> tuple[Decimal | None, Decimal | None]:
    coords = geometry.get('coordinates')
    if not coords:
        return None, None
    try:
        if geometry_type == 'Point':
            lon, lat = coords[0], coords[1]
            return _decimal(lat), _decimal(lon)
        if geometry_type == 'LineString':
            mid = coords[len(coords) // 2]
            return _decimal(mid[1]), _decimal(mid[0])
        if geometry_type == 'Polygon':
            ring = coords[0]
            if not ring:
                return None, None
            lats = [p[1] for p in ring]
            lons = [p[0] for p in ring]
            return _decimal(sum(lats) / len(lats)), _decimal(sum(lons) / len(lons))
    except (IndexError, TypeError, ValueError):
        pass
    return None, None


def _external_key(name: str, folder: str, geometry_type: str) -> str:
    raw = f'{geometry_type}|{folder}|{name}'.strip().lower()
    return hashlib.md5(raw.encode('utf-8')).hexdigest()[:32]


def import_geojson_features(
    project: Project,
    payload: dict[str, Any],
    *,
    source_label: str = '',
    replace: bool = False,
) -> dict[str, int]:
    """Importa FeatureCollection GeoJSON para o projeto."""
    if payload.get('type') != 'FeatureCollection':
        raise ValueError('O arquivo deve ser um GeoJSON FeatureCollection.')

    features = payload.get('features') or []
    if not features:
        raise ValueError('Nenhuma feature encontrada no GeoJSON.')

    if replace:
        GeoFeature.objects.filter(project=project).delete()

    created = 0
    updated = 0
    sort_line = 0

    with transaction.atomic():
        config, _ = GeoObraConfig.objects.get_or_create(project=project)
        if source_label:
            config.import_label = source_label[:200]
            config.save(update_fields=['import_label', 'updated_at'])

        for item in features:
            if not isinstance(item, dict) or item.get('type') != 'Feature':
                continue
            geom = item.get('geometry') or {}
            gtype = geom.get('type')
            if gtype not in ('Point', 'LineString', 'Polygon'):
                continue

            props = item.get('properties') or {}
            name = str(props.get('name') or '').strip()
            folder = str(props.get('folder') or '').strip()
            description = str(props.get('description') or '').strip()
            ext = _external_key(name, folder, gtype)
            kind = _infer_kind(name, folder, gtype)

            if gtype == 'LineString':
                sort_line += 1
                order = sort_line
            else:
                order = 0

            lat, lon = _coords_centroid(gtype, geom)
            defaults = {
                'name': name[:255],
                'folder': folder[:500],
                'description': description,
                'geometry_type': gtype,
                'geometry': geom,
                'latitude': lat,
                'longitude': lon,
                'kind': kind,
                'sort_order': order,
                'is_active': True,
            }

            obj, was_created = GeoFeature.objects.update_or_create(
                project=project,
                external_key=ext,
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1

        _update_project_center_from_features(project)

    return {'created': created, 'updated': updated, 'total': created + updated}


def _update_project_center_from_features(project: Project) -> None:
    qs = GeoFeature.objects.filter(project=project, latitude__isnull=False, longitude__isnull=False)
    if not qs.exists():
        return
    lats = [f.latitude for f in qs if f.latitude is not None]
    lons = [f.longitude for f in qs if f.longitude is not None]
    if not lats:
        return
    config, _ = GeoObraConfig.objects.get_or_create(project=project)
    config.center_latitude = sum(lats) / len(lats)
    config.center_longitude = sum(lons) / len(lons)
    config.save(update_fields=['center_latitude', 'center_longitude', 'updated_at'])


def kml_to_geojson_features(kml_text: str) -> dict[str, Any]:
    """Converte placemarks KML 2.2 em FeatureCollection GeoJSON."""
    root = ET.fromstring(kml_text.encode('utf-8'))

    def folder_path(folder_elem, path=''):
        name_el = folder_elem.find('kml:name', KML_NS)
        name = name_el.text.strip() if name_el is not None and name_el.text else ''
        return f'{path} / {name}'.strip(' /') if path else name

    def walk_folders(parent, path=''):
        for folder in parent.findall('kml:Folder', KML_NS):
            fpath = folder_path(folder, path)
            for pm in folder.findall('kml:Placemark', KML_NS):
                yield fpath, pm
            yield from walk_folders(folder, fpath)

    doc = root.find('kml:Document', KML_NS) or root
    root_name_el = doc.find('kml:name', KML_NS)
    root_name = root_name_el.text.strip() if root_name_el is not None and root_name_el.text else 'KML'

    features: list[dict] = []

    for pm in doc.findall('kml:Placemark', KML_NS):
        yield_folder = root_name
        name_el = pm.find('kml:name', KML_NS)
        desc_el = pm.find('kml:description', KML_NS)
        name = name_el.text.strip() if name_el is not None and name_el.text else ''
        description = desc_el.text if desc_el is not None and desc_el.text else ''
        geom, gtype = _parse_kml_geometry(pm)
        if geom:
            features.append(
                {
                    'type': 'Feature',
                    'properties': {'name': name, 'folder': yield_folder, 'description': description},
                    'geometry': geom,
                }
            )

    for fpath, pm in walk_folders(doc):
        name_el = pm.find('kml:name', KML_NS)
        desc_el = pm.find('kml:description', KML_NS)
        name = name_el.text.strip() if name_el is not None and name_el.text else ''
        description = desc_el.text if desc_el is not None and desc_el.text else ''
        geom, gtype = _parse_kml_geometry(pm)
        if geom:
            features.append(
                {
                    'type': 'Feature',
                    'properties': {'name': name, 'folder': fpath, 'description': description},
                    'geometry': geom,
                }
            )

    return {'type': 'FeatureCollection', 'name': root_name, 'features': features}


def _parse_kml_coordinates(text: str) -> list[list[float]]:
    coords = []
    for token in re.split(r'\s+', (text or '').strip()):
        if not token:
            continue
        parts = token.split(',')
        if len(parts) < 2:
            continue
        try:
            lon, lat = float(parts[0]), float(parts[1])
            alt = float(parts[2]) if len(parts) > 2 else 0.0
            coords.append([lon, lat, alt])
        except ValueError:
            continue
    return coords


def _parse_kml_geometry(placemark) -> tuple[dict | None, str | None]:
    point = placemark.find('.//kml:Point/kml:coordinates', KML_NS)
    if point is not None and point.text:
        c = _parse_kml_coordinates(point.text)
        if c:
            return {'type': 'Point', 'coordinates': c[0]}, 'Point'

    line = placemark.find('.//kml:LineString/kml:coordinates', KML_NS)
    if line is not None and line.text:
        c = _parse_kml_coordinates(line.text)
        if c:
            return {'type': 'LineString', 'coordinates': c}, 'LineString'

    poly = placemark.find('.//kml:Polygon/kml:outerBoundaryIs//kml:coordinates', KML_NS)
    if poly is not None and poly.text:
        c = _parse_kml_coordinates(poly.text)
        if c:
            return {'type': 'Polygon', 'coordinates': [c]}, 'Polygon'

    return None, None


def project_progress_at_date(project: Project, target: date) -> Decimal:
    """Progresso geral do projeto até uma data (último worklog aprovado)."""
    wl = (
        DailyWorkLog.objects.filter(
            diary__project=project,
            diary__date__lte=target,
            diary__status__in=DIARY_STATUSES_FOR_GEO_PROGRESS,
        )
        .order_by('-diary__date', '-created_at')
        .first()
    )
    if wl:
        return wl.accumulated_progress_snapshot
    try:
        return ProgressService.get_project_overall_progress(project.id)
    except Exception:
        return Decimal('0.00')


def sync_snapshots_from_diario(project: Project) -> dict[str, int]:
    """
    Gera snapshots evolutivos por data de diário:
    - trechos com atividade EAP vinculada usam progresso real da atividade;
    - demais linhas usam fallback proporcional ao progresso global;
    - pontos usam progresso manual ou da atividade vinculada.
    """
    features = list(GeoFeature.objects.filter(project=project, is_active=True))
    if not features:
        return {'dates': 0, 'snapshots': 0}

    diary_dates = list(
        ConstructionDiary.objects.filter(project=project, status__in=DIARY_STATUSES_FOR_GEO_PROGRESS)
        .order_by('date')
        .values_list('date', flat=True)
        .distinct()
    )
    if not diary_dates:
        diary_dates = [timezone.localdate()]

    lines = [f for f in features if f.geometry_type == 'LineString']
    line_total = len(lines)
    snapshots = 0

    with transaction.atomic():
        for d in diary_dates:
            overall = project_progress_at_date(project, d)
            for feat in features:
                line_index = None
                if feat.geometry_type == 'LineString' and feat in lines:
                    line_index = lines.index(feat) + 1
                prog, status = resolve_feature_progress_and_status(
                    feat,
                    d,
                    overall=overall,
                    line_index=line_index,
                    line_total=line_total,
                )
                source = 'eap' if feat.activity_id else 'diario'
                GeoProgressSnapshot.objects.update_or_create(
                    feature=feat,
                    snapshot_date=d,
                    defaults={
                        'progress_pct': prog.quantize(Decimal('0.01')),
                        'status': status,
                        'source': source,
                    },
                )
                snapshots += 1

    return {'dates': len(diary_dates), 'snapshots': snapshots}


def get_map_summary(project: Project) -> dict[str, Any]:
    """Indicadores do mapa integrados ao progresso e diários do Lplan."""
    from django.db.models import Count

    qs = GeoFeature.objects.filter(project=project, is_active=True)
    by_geom = {
        row['geometry_type']: row['c']
        for row in qs.values('geometry_type').annotate(c=Count('id'))
    }
    try:
        overall = float(ProgressService.get_project_overall_progress(project.id))
    except Exception:
        overall = 0.0

    diaries_with_gps = ConstructionDiary.objects.filter(
        project=project,
        geolocation_data__isnull=False,
    ).exclude(geolocation_data={}).count()
    last_diary = (
        ConstructionDiary.objects.filter(project=project, status__in=DIARY_STATUSES_FOR_GEO_PROGRESS)
        .order_by('-date')
        .values_list('date', flat=True)
        .first()
    )
    config = GeoObraConfig.objects.filter(project=project).first()
    timeline_count = len(available_timeline_dates(project))

    return {
        'total': qs.count(),
        'segments': by_geom.get('LineString', 0),
        'points': by_geom.get('Point', 0),
        'areas': by_geom.get('Polygon', 0),
        'gps_markers': qs.filter(diary__isnull=False).count(),
        'eap_linked': qs.filter(activity__isnull=False).count(),
        'overall_progress_pct': overall,
        'diaries_with_gps': diaries_with_gps,
        'last_diary_date': last_diary.isoformat() if last_diary else None,
        'timeline_dates': timeline_count,
        'import_label': (config.import_label if config else '') or '',
    }


def _features_queryset_for_project(project: Project):
    """Elementos da obra, excluindo vínculos EAP/RDO de outro projeto (dados inconsistentes)."""
    from django.db.models import Q

    return (
        GeoFeature.objects.filter(project=project, is_active=True)
        .select_related('activity', 'diary')
        .filter(Q(diary__isnull=True) | Q(diary__project=project))
        .filter(Q(activity__isnull=True) | Q(activity__project=project))
    )


def features_geojson_at_date(project: Project, target: date | None = None) -> dict[str, Any]:
    """Monta FeatureCollection com progresso vigente em uma data."""
    qs = _features_queryset_for_project(project)
    features = []
    display_date = target or timezone.localdate()
    overall = project_progress_at_date(project, display_date)
    lines = list(
        GeoFeature.objects.filter(project=project, geometry_type='LineString', is_active=True).order_by(
            'sort_order', 'id'
        )
    )
    line_total = len(lines)

    for feat in qs:
        line_index = lines.index(feat) + 1 if feat in lines else None
        progress, status = resolve_feature_progress_and_status(
            feat,
            target,
            overall=overall,
            line_index=line_index,
            line_total=line_total,
        )
        item = _feature_to_geojson_dict(feat, progress=progress, status=status)
        try:
            from .enrichment import enrich_feature_properties
            item['properties'].update(enrich_feature_properties(feat, progress=progress, status=status))
        except Exception:
            pass
        features.append(item)

    config = GeoObraConfig.objects.filter(project=project).first()
    meta = {
        'project_id': project.id,
        'project_code': project.code,
        'project_name': project.name,
        'date': target.isoformat() if target else None,
        'display_date': display_date.isoformat(),
        'overall_progress_pct': float(overall),
        'feature_count': len(features),
        'center': None,
    }
    if config and config.center_latitude and config.center_longitude:
        meta['center'] = [float(config.center_latitude), float(config.center_longitude)]

    return {
        'type': 'FeatureCollection',
        'meta': meta,
        'features': features,
    }


def _feature_to_geojson_dict(feat: GeoFeature, *, progress=None, status=None) -> dict:
    progress = feat.progress_pct if progress is None else progress
    status = feat.status if status is None else status
    props = {
        'id': feat.id,
        'name': feat.name,
        'folder': feat.folder,
        'description': feat.description,
        'geometry_type': feat.geometry_type,
        'kind': feat.kind,
        'status': status,
        'progress_pct': float(progress),
        'activity_id': feat.activity_id,
        'diary_id': feat.diary_id,
    }
    if feat.activity_id and feat.activity:
        props['activity_code'] = feat.activity.code
        props['activity_name'] = feat.activity.name
    if feat.diary_id and feat.diary and feat.diary.project_id == feat.project_id:
        props['is_diary_gps'] = True
        props['diary_date'] = feat.diary.date.isoformat()
        props['diary_report'] = feat.diary.report_number or feat.diary.pk
        from django.urls import reverse

        props['diary_detail_path'] = reverse('diary-detail', kwargs={'pk': feat.diary_id})
    return {
        'type': 'Feature',
        'id': feat.id,
        'properties': props,
        'geometry': feat.geometry,
    }


def activity_progress_at_date(activity: Activity, target: date | None) -> Decimal:
    """Progresso real da atividade EAP em uma data (último worklog até a data)."""
    if target is None:
        return ProgressService.get_activity_progress(activity)
    wl = (
        DailyWorkLog.objects.filter(
            activity=activity,
            diary__project_id=activity.project_id,
            diary__date__lte=target,
            diary__status__in=DIARY_STATUSES_FOR_GEO_PROGRESS,
        )
        .order_by('-diary__date', '-created_at')
        .first()
    )
    if wl:
        return wl.accumulated_progress_snapshot
    return Decimal('0.00')


def resolve_feature_progress_and_status(
    feat: GeoFeature,
    target: date | None,
    *,
    overall: Decimal | None = None,
    line_index: int | None = None,
    line_total: int = 0,
) -> tuple[Decimal, str]:
    """Prioridade: atividade EAP vinculada > snapshot histórico > progresso manual > proporcional."""
    if feat.activity_id:
        progress = activity_progress_at_date(feat.activity, target)
        return progress, _status_from_progress(progress)

    if target:
        snap = (
            feat.snapshots.filter(snapshot_date__lte=target)
            .order_by('-snapshot_date')
            .first()
        )
        if snap:
            return snap.progress_pct, snap.status

    if (
        feat.geometry_type == 'LineString'
        and overall is not None
        and line_index is not None
        and line_total > 0
        and not feat.activity_id
    ):
        threshold = (Decimal(line_index) / Decimal(line_total)) * Decimal('100')
        progress = overall if overall >= threshold else Decimal('0')
        return progress, _status_from_progress(progress)

    return feat.progress_pct, feat.status


def _assign_activity(feature: GeoFeature, activity_id) -> None:
    if activity_id in (None, '', 0, '0'):
        feature.activity = None
        return
    activity = Activity.objects.get(pk=int(activity_id), project=feature.project)
    feature.activity = activity
    feature.progress_pct = ProgressService.get_activity_progress(activity)
    feature.status = _status_from_progress(feature.progress_pct)


def create_geo_feature(project: Project, payload: dict[str, Any]) -> GeoFeature:
    geometry = payload.get('geometry') or {}
    gtype = geometry.get('type')
    if gtype not in ('Point', 'LineString', 'Polygon'):
        raise ValueError('Geometria inválida.')

    name = str(payload.get('name') or '').strip()
    folder = str(payload.get('folder') or '').strip()
    description = str(payload.get('description') or '').strip()
    kind = payload.get('kind') or _infer_kind(name, folder, gtype)
    if kind not in dict(GeoFeature.KIND_CHOICES):
        kind = _infer_kind(name, folder, gtype)

    status = payload.get('status') or 'planned'
    if status not in dict(GeoFeature.STATUS_CHOICES):
        status = 'planned'

    try:
        progress = Decimal(str(payload.get('progress_pct', 0))).quantize(Decimal('0.01'))
    except Exception:
        progress = Decimal('0.00')
    progress = max(Decimal('0'), min(Decimal('100'), progress))

    lat, lon = _coords_centroid(gtype, geometry)
    ext = _external_key(name or f'novo-{timezone.now().timestamp()}', folder, gtype)

    max_order = (
        GeoFeature.objects.filter(project=project, geometry_type='LineString')
        .aggregate(m=Max('sort_order'))
        .get('m')
        or 0
    )

    feat = GeoFeature.objects.create(
        project=project,
        external_key=ext,
        name=name[:255],
        folder=folder[:500],
        description=description,
        geometry_type=gtype,
        geometry=geometry,
        latitude=lat,
        longitude=lon,
        kind=kind,
        status=status,
        progress_pct=progress,
        sort_order=max_order + 1 if gtype == 'LineString' else 0,
        is_active=True,
    )
    if payload.get('activity_id'):
        try:
            _assign_activity(feat, payload.get('activity_id'))
            feat.save(update_fields=['activity', 'progress_pct', 'status', 'updated_at'])
        except Activity.DoesNotExist:
            pass
    _update_project_center_from_features(project)
    return feat


def update_geo_feature(feature: GeoFeature, payload: dict[str, Any]) -> GeoFeature:
    if 'geometry' in payload and payload['geometry']:
        geometry = payload['geometry']
        gtype = geometry.get('type')
        if gtype not in ('Point', 'LineString', 'Polygon'):
            raise ValueError('Geometria inválida.')
        feature.geometry = geometry
        feature.geometry_type = gtype
        lat, lon = _coords_centroid(gtype, geometry)
        feature.latitude = lat
        feature.longitude = lon

    if 'name' in payload:
        feature.name = str(payload.get('name') or '')[:255]
    if 'folder' in payload:
        feature.folder = str(payload.get('folder') or '')[:500]
    if 'description' in payload:
        feature.description = str(payload.get('description') or '')
    if 'kind' in payload and payload['kind'] in dict(GeoFeature.KIND_CHOICES):
        feature.kind = payload['kind']
    if 'status' in payload and payload['status'] in dict(GeoFeature.STATUS_CHOICES):
        feature.status = payload['status']
    if 'activity_id' in payload:
        try:
            _assign_activity(feature, payload.get('activity_id'))
        except Activity.DoesNotExist as exc:
            raise ValueError('Atividade EAP inválida para esta obra.') from exc
    elif 'progress_pct' in payload and not feature.activity_id:
        try:
            progress = Decimal(str(payload['progress_pct'])).quantize(Decimal('0.01'))
            feature.progress_pct = max(Decimal('0'), min(Decimal('100'), progress))
        except Exception:
            pass

    if feature.activity_id and 'progress_pct' not in payload:
        feature.progress_pct = ProgressService.get_activity_progress(feature.activity)
        feature.status = _status_from_progress(feature.progress_pct)

    feature.save()
    _update_project_center_from_features(feature.project)
    return feature


def delete_geo_feature(feature: GeoFeature) -> None:
    feature.is_active = False
    feature.save(update_fields=['is_active', 'updated_at'])


def _escape_kml(text: str) -> str:
    return (
        (text or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def geojson_to_kml(collection: dict[str, Any], *, doc_name: str = 'LPLAN Mapa') -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '<Document>',
        f'<name>{_escape_kml(doc_name)}</name>',
    ]
    for feat in collection.get('features') or []:
        props = feat.get('properties') or {}
        geom = feat.get('geometry') or {}
        gtype = geom.get('type')
        name = _escape_kml(str(props.get('name') or ''))
        desc = _escape_kml(str(props.get('description') or ''))
        folder = _escape_kml(str(props.get('folder') or ''))
        if folder:
            desc = f'Pasta: {folder}\\n{desc}' if desc else f'Pasta: {folder}'

        lines.append('<Placemark>')
        lines.append(f'<name>{name}</name>')
        if desc:
            lines.append(f'<description>{desc}</description>')

        coords = geom.get('coordinates') or []
        if gtype == 'Point' and coords:
            c = coords
            lines.append('<Point><coordinates>')
            lines.append(f'{c[0]},{c[1]},{c[2] if len(c) > 2 else 0}')
            lines.append('</coordinates></Point>')
        elif gtype == 'LineString' and coords:
            lines.append('<LineString><coordinates>')
            lines.append(' '.join(f'{p[0]},{p[1]},{p[2] if len(p) > 2 else 0}' for p in coords))
            lines.append('</coordinates></LineString>')
        elif gtype == 'Polygon' and coords:
            ring = coords[0] if coords else []
            lines.append('<Polygon><outerBoundaryIs><LinearRing><coordinates>')
            lines.append(' '.join(f'{p[0]},{p[1]},{p[2] if len(p) > 2 else 0}' for p in ring))
            lines.append('</coordinates></LinearRing></outerBoundaryIs></Polygon>')
        lines.append('</Placemark>')
    lines.extend(['</Document>', '</kml>'])
    return '\n'.join(lines)


def export_csv_pontos_rows(project: Project) -> list[dict[str, str]]:
    rows = []
    for feat in GeoFeature.objects.filter(project=project, is_active=True, geometry_type='Point'):
        rows.append(
            {
                'name': feat.name,
                'folder': feat.folder,
                'latitude': str(feat.latitude or ''),
                'longitude': str(feat.longitude or ''),
                'altitude': '0.0',
                'description': feat.description.replace('\n', ' '),
                'status': feat.status,
                'progress_pct': str(feat.progress_pct),
                'kind': feat.kind,
            }
        )
    return rows


def export_csv_geometrias_rows(project: Project) -> list[dict[str, str]]:
    rows = []
    for feat in GeoFeature.objects.filter(project=project, is_active=True):
        coord_count = 0
        coords = (feat.geometry or {}).get('coordinates') or []
        if feat.geometry_type == 'Point':
            coord_count = 1
        elif feat.geometry_type == 'LineString':
            coord_count = len(coords)
        elif feat.geometry_type == 'Polygon' and coords:
            coord_count = len(coords[0])
        rows.append(
            {
                'name': feat.name,
                'folder': feat.folder,
                'geometry_type': feat.geometry_type,
                'coordinate_count': str(coord_count),
                'description': feat.description.replace('\n', ' '),
                'status': feat.status,
                'progress_pct': str(feat.progress_pct),
                'kind': feat.kind,
            }
        )
    return rows


def sync_diary_geolocation_marker(diary: ConstructionDiary) -> GeoFeature | None:
    """Cria/atualiza ponto no mapa a partir do GPS capturado no RDO."""
    geo = diary.geolocation_data
    if not geo or not isinstance(geo, dict):
        return None
    try:
        lat = float(geo['latitude'])
        lng = float(geo['longitude'])
    except (KeyError, TypeError, ValueError):
        return None

    external_key = f'diary-{diary.pk}'
    folder = 'Diários de obra'
    if diary.front_id:
        folder = f'{folder} / {diary.front.name}'
    report = diary.report_number or diary.pk
    name = f'RDO #{report} — {diary.date:%d/%m/%Y}'
    desc_parts = []
    if geo.get('address'):
        desc_parts.append(str(geo['address']))
    if geo.get('accuracy_m'):
        desc_parts.append(f'Precisão: {geo["accuracy_m"]} m')
    if diary.created_by:
        desc_parts.append(f'Por: {diary.created_by.get_full_name() or diary.created_by.username}')

    geometry = {'type': 'Point', 'coordinates': [lng, lat, 0.0]}
    feat, _ = GeoFeature.objects.update_or_create(
        project=diary.project,
        external_key=external_key,
        defaults={
            'diary': diary,
            'name': name[:255],
            'folder': folder[:500],
            'description': '\n'.join(desc_parts),
            'geometry_type': 'Point',
            'geometry': geometry,
            'latitude': _decimal(lat),
            'longitude': _decimal(lng),
            'kind': 'vistoria',
            'status': 'vistoria',
            'progress_pct': project_progress_at_date(diary.project, diary.date),
            'is_active': True,
        },
    )
    GeoProgressSnapshot.objects.update_or_create(
        feature=feat,
        snapshot_date=diary.date,
        defaults={
            'progress_pct': feat.progress_pct,
            'status': 'vistoria',
            'source': 'diario_gps',
        },
    )
    _update_project_center_from_features(diary.project)
    return feat


def on_diary_saved(diary: ConstructionDiary) -> None:
    """Integração pós-salvamento do RDO com o mapa geográfico."""
    if not diary or not diary.project_id:
        return
    if diary.geolocation_data:
        sync_diary_geolocation_marker(diary)
    sync_snapshots_from_diario(diary.project)


def list_project_activities(
    project: Project,
    query: str = '',
    limit: int = 200,
    *,
    leaves_only: bool = True,
) -> list[dict]:
    from django.db.models import Q

    qs = Activity.objects.filter(project=project).order_by('code')
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(code__icontains=query))
    rows = []
    for act in qs[: limit * 3]:
        if leaves_only and not act.is_leaf():
            continue
        if len(rows) >= limit:
            break
        rows.append(
            {
                'id': act.id,
                'code': act.code,
                'name': act.name,
                'label': f'{act.code} — {act.name}',
                'progress_pct': float(ProgressService.get_activity_progress(act)),
                'is_leaf': act.is_leaf(),
            }
        )
    return rows


def available_timeline_dates(project: Project) -> list[str]:
    snap_dates = set(
        GeoProgressSnapshot.objects.filter(feature__project=project).values_list('snapshot_date', flat=True)
    )
    diary_dates = set(
        ConstructionDiary.objects.filter(project=project, status__in=DIARY_STATUSES_FOR_GEO_PROGRESS)
        .values_list('date', flat=True)
    )
    last_import = GeoFeature.objects.filter(project=project).aggregate(d=Max('created_at'))['d']
    import_dates = {last_import.date()} if last_import else set()
    all_dates = snap_dates | diary_dates | import_dates
    if not all_dates:
        all_dates = {timezone.localdate()}
    return sorted(d.isoformat() for d in all_dates)
