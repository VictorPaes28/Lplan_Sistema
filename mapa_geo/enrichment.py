"""Camadas extras do Mapa Geográfico: alertas, comparação, restrições e panorama."""

from __future__ import annotations



from datetime import date, timedelta

from decimal import Decimal

from typing import Any



from django.db.models import Count, Q

from django.urls import reverse

from django.utils import timezone



from core.models import ConstructionDiary, DailyWorkLog, DiaryImage, Project



from .models import GeoFeature, GeoObraConfig, GeoProgressSnapshot

from .services import (

    DIARY_STATUSES_FOR_GEO_PROGRESS,

    _feature_to_geojson_dict,

    _status_from_progress,

    available_timeline_dates,

    features_geojson_at_date,

    get_map_summary,

    resolve_feature_progress_and_status,

)



STALE_PROGRESS_DAYS = 30





def enrich_feature_properties(feat: GeoFeature, *, progress=None, status=None) -> dict[str, Any]:

    """Propriedades extras para popup rico e alertas no frontend."""

    progress = feat.progress_pct if progress is None else progress

    status = feat.status if status is None else status

    props = {

        'alert_blocked': status == 'blocked',

        'alert_no_eap': feat.geometry_type == 'LineString' and not feat.activity_id and not feat.diary_id,

        'alert_stale': False,

        'last_diary_date': None,

        'last_diary_report': None,

        'last_diary_path': None,

        'diary_photo_url': None,

        'activity_detail_path': None,

    }



    if feat.activity_id and feat.activity and feat.activity.project_id == feat.project_id:

        props['activity_detail_path'] = reverse(
            'activity-edit',
            kwargs={'project_id': feat.project_id, 'pk': feat.activity_id},
        )



    if feat.diary_id and feat.diary and feat.diary.project_id == feat.project_id:

        diary = feat.diary

        props['last_diary_date'] = diary.date.isoformat()

        props['last_diary_report'] = diary.report_number or diary.pk

        props['last_diary_path'] = reverse('diary-detail', kwargs={'pk': diary.pk})

        img = (

            DiaryImage.objects.filter(diary=diary)

            .exclude(image='')

            .order_by('uploaded_at', 'id')

            .first()

        )

        if img and img.image:

            props['diary_photo_url'] = img.image.url

    elif feat.activity_id and feat.activity and feat.activity.project_id == feat.project_id:

        wl = (

            DailyWorkLog.objects.filter(

                activity=feat.activity,

                diary__project_id=feat.project_id,

                diary__status__in=DIARY_STATUSES_FOR_GEO_PROGRESS,

            )

            .select_related('diary')

            .order_by('-diary__date', '-created_at')

            .first()

        )

        if wl and wl.diary:

            props['last_diary_date'] = wl.diary.date.isoformat()

            props['last_diary_report'] = wl.diary.report_number or wl.diary.pk

            props['last_diary_path'] = reverse('diary-detail', kwargs={'pk': wl.diary.pk})



    if float(progress or 0) < 100 and feat.geometry_type == 'LineString':

        last_snap = feat.snapshots.order_by('-snapshot_date').values_list('snapshot_date', flat=True).first()

        ref = last_snap or (feat.updated_at.date() if feat.updated_at else None)

        if ref and (timezone.localdate() - ref).days >= STALE_PROGRESS_DAYS:

            props['alert_stale'] = True



    return props





def list_feature_folders(project: Project) -> list[str]:

    folders = (

        GeoFeature.objects.filter(project=project, is_active=True)

        .exclude(folder='')

        .values_list('folder', flat=True)

        .distinct()

    )

    return sorted(set(folders), key=lambda s: s.lower())





def get_map_alerts(project: Project) -> dict[str, Any]:

    """Alertas operacionais: bloqueios, sem EAP, estagnação e restrições abertas."""

    items: list[dict[str, Any]] = []

    today = timezone.localdate()



    for feat in GeoFeature.objects.filter(project=project, is_active=True).select_related('activity'):

        extra = enrich_feature_properties(feat)

        if feat.status == 'blocked':

            items.append({

                'type': 'blocked',

                'severity': 'high',

                'feature_id': feat.id,

                'name': feat.name or 'Sem nome',

                'message': f'Trecho bloqueado: {feat.name or feat.id}',

            })

        if extra.get('alert_no_eap'):

            items.append({

                'type': 'no_eap',

                'severity': 'medium',

                'feature_id': feat.id,

                'name': feat.name or 'Sem nome',

                'message': f'Sem vínculo EAP: {feat.name or "elemento"}',

            })

        if extra.get('alert_stale'):

            items.append({

                'type': 'stale',

                'severity': 'low',

                'feature_id': feat.id,

                'name': feat.name or 'Sem nome',

                'message': f'Sem avanço há {STALE_PROGRESS_DAYS}+ dias: {feat.name or "trecho"}',

            })



    try:

        from gestao_aprovacao.models import Obra

        from impedimentos.models import Impedimento



        obra = Obra.objects.filter(project=project).first()

        if obra:

            impedimentos = (

                Impedimento.objects.filter(obra=obra, parent__isnull=True)

                .select_related('status', 'front')

                .exclude(status__nome__iexact='Finalizado')

                .order_by('-prioridade', '-criado_em')[:50]

            )

            for imp in impedimentos:

                items.append({

                    'type': 'impedimento',

                    'severity': 'high' if imp.prioridade in ('ALTA', 'CRITICA') else 'medium',

                    'impedimento_id': imp.id,

                    'obra_id': obra.id,

                    'name': imp.titulo,

                    'message': f'Restrição: {imp.titulo}',

                    'url': reverse('impedimentos:list_impedimentos', kwargs={'obra_id': obra.id}),

                })

    except Exception:

        pass



    return {

        'count': len(items),

        'items': items,

        'generated_at': today.isoformat(),

    }





def compare_features_at_dates(project: Project, date_a: date, date_b: date) -> dict[str, Any]:

    """Compara progresso/status entre duas datas por elemento."""

    if date_a > date_b:

        date_a, date_b = date_b, date_a



    lines = list(

        GeoFeature.objects.filter(project=project, geometry_type='LineString', is_active=True).order_by(

            'sort_order', 'id'

        )

    )

    line_total = len(lines)

    overall_a = _project_progress_at(project, date_a)

    overall_b = _project_progress_at(project, date_b)



    features = []

    stats = {'same': 0, 'changed': 0, 'added': 0, 'removed': 0}



    from .services import _features_queryset_for_project

    qs = _features_queryset_for_project(project)

    for feat in qs:

        line_index = lines.index(feat) + 1 if feat in lines else None

        prog_a, status_a = resolve_feature_progress_and_status(

            feat, date_a, overall=overall_a, line_index=line_index, line_total=line_total

        )

        prog_b, status_b = resolve_feature_progress_and_status(

            feat, date_b, overall=overall_b, line_index=line_index, line_total=line_total

        )



        created = feat.created_at.date() if feat.created_at else None

        change_type = 'same'

        if created and created > date_a and created <= date_b:

            change_type = 'added'

            stats['added'] += 1

        elif float(prog_a) != float(prog_b) or status_a != status_b:

            change_type = 'changed'

            stats['changed'] += 1

        else:

            stats['same'] += 1



        item = _feature_to_geojson_dict(feat, progress=prog_b, status=status_b)

        item['properties'].update(enrich_feature_properties(feat, progress=prog_b, status=status_b))

        item['properties']['compare'] = {

            'change_type': change_type,

            'date_a': date_a.isoformat(),

            'date_b': date_b.isoformat(),

            'progress_a': float(prog_a),

            'progress_b': float(prog_b),

            'status_a': status_a,

            'status_b': status_b,

            'delta_progress': float(prog_b) - float(prog_a),

        }

        features.append(item)



    return {

        'type': 'FeatureCollection',

        'meta': {

            'date_a': date_a.isoformat(),

            'date_b': date_b.isoformat(),

            'stats': stats,

            'feature_count': len(features),

        },

        'features': features,

    }





def _project_progress_at(project: Project, target: date) -> Decimal:
    from .services import project_progress_at_date
    return project_progress_at_date(project, target)





def multi_obra_panorama(user) -> list[dict[str, Any]]:

    """Resumo de mapas das obras acessíveis ao usuário."""

    from core.frontend_views import _get_projects_for_user

    from django.test import RequestFactory



    factory = RequestFactory()

    req = factory.get('/')

    req.user = user

    projects = _get_projects_for_user(req)



    rows = []

    for project in projects[:80]:

        summary = get_map_summary(project)

        config = GeoObraConfig.objects.filter(project=project).first()

        rows.append({

            'project_id': project.id,

            'code': project.code,

            'name': project.name,

            'is_active': project.is_active,

            'total': summary['total'],

            'segments': summary['segments'],

            'overall_progress_pct': summary['overall_progress_pct'],

            'map_url': reverse('mapa_geo:mapa') + f'?project={project.id}',

            'center': [

                float(config.center_latitude),

                float(config.center_longitude),

            ] if config and config.center_latitude and config.center_longitude else None,

        })

    return rows





def build_relatorio_context(project: Project, target: date | None = None) -> dict[str, Any]:

    """Contexto para relatório imprimível / PDF via navegador."""

    collection = features_geojson_at_date(project, target)

    alerts = get_map_alerts(project)

    summary = get_map_summary(project)

    return {

        'project': project,

        'summary': summary,

        'alerts': alerts,

        'collection': collection,

        'display_date': target or timezone.localdate(),

        'timeline_dates': available_timeline_dates(project),

    }


