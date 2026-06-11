import csv
import io
import json
import zipfile
from datetime import datetime

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from accounts.decorators import login_required
from accounts.groups import GRUPOS
from core.frontend_views import _get_projects_for_user, _user_can_access_project, _with_no_cache_html, get_selected_project
from core.models import Project

from .decorators import mapa_project_required

from .models import GeoFeature, GeoObraConfig
from .services import (
    available_timeline_dates,
    create_geo_feature,
    delete_geo_feature,
    export_csv_geometrias_rows,
    export_csv_pontos_rows,
    features_geojson_at_date,
    geojson_to_kml,
    get_map_summary,
    import_geojson_features,
    kml_to_geojson_features,
    list_project_activities,
    sync_snapshots_from_diario,
    update_geo_feature,
)


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def _user_can_edit_geo(request) -> bool:
    user = request.user
    if user.is_staff or user.is_superuser:
        return True
    groups = set(user.groups.values_list('name', flat=True))
    return GRUPOS.GERENTES in groups


def _json_body(request) -> dict:
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError as exc:
        raise ValueError('JSON inválido.') from exc


@login_required
def selecionar_obra_view(request):
    """Seleção de obra no contexto do Mapa Geográfico (não redireciona ao Diário)."""
    projects = _get_projects_for_user(request)

    if request.method == 'POST':
        project_id = request.POST.get('project_id')
        if project_id:
            try:
                project = Project.objects.get(pk=project_id)
            except (Project.DoesNotExist, ValueError, TypeError):
                response = render(
                    request,
                    'mapa_geo/selecionar_obra.html',
                    {
                        'projects': projects,
                        'selected_project_id': request.session.get('selected_project_id'),
                        'error': 'Obra não encontrada.',
                    },
                )
                return _with_no_cache_html(response)

            if not _user_can_access_project(request.user, project):
                response = render(
                    request,
                    'mapa_geo/selecionar_obra.html',
                    {
                        'projects': projects,
                        'selected_project_id': request.session.get('selected_project_id'),
                        'error': 'Você não está vinculado a esta obra.',
                    },
                )
                return _with_no_cache_html(response)

            request.session['selected_project_id'] = project.id
            request.session['selected_project_name'] = project.name
            request.session['selected_project_code'] = project.code
            request.session.modified = True
            return redirect('mapa_geo:mapa')

    response = render(
        request,
        'mapa_geo/selecionar_obra.html',
        {
            'projects': projects,
            'selected_project_id': request.session.get('selected_project_id'),
        },
    )
    return _with_no_cache_html(response)


@login_required
@mapa_project_required
def mapa_view(request):
    project = get_selected_project(request)
    config = GeoObraConfig.objects.filter(project=project).first()
    feature_count = GeoFeature.objects.filter(project=project, is_active=True).count()
    dates = available_timeline_dates(project)
    can_edit = _user_can_edit_geo(request)

    focus_diary = request.GET.get('diary')
    focus_feature = request.GET.get('feature')

    context = {
        'project': project,
        'geo_config': config,
        'feature_count': feature_count,
        'timeline_dates': dates,
        'can_edit_geo': can_edit,
        'has_features': feature_count > 0,
        'map_summary': get_map_summary(project),
        'focus_diary': focus_diary or '',
        'focus_feature': focus_feature or '',
    }
    return render(request, 'mapa_geo/mapa.html', context)


@login_required
@mapa_project_required
@require_http_methods(['GET', 'POST'])
def api_features_view(request):
    project = get_selected_project(request)

    if request.method == 'GET':
        target = _parse_date(request.GET.get('date'))
        payload = features_geojson_at_date(project, target)
        return JsonResponse(payload)

    if not _user_can_edit_geo(request):
        return JsonResponse({'error': 'Sem permissão para editar o mapa.'}, status=403)

    try:
        from .services import _feature_to_geojson_dict

        data = _json_body(request)
        feat = create_geo_feature(project, data)
        return JsonResponse({'ok': True, 'feature': _feature_to_geojson_dict(feat)}, status=201)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@login_required
@mapa_project_required
@require_http_methods(['GET', 'PUT', 'PATCH', 'DELETE'])
def api_feature_detail_view(request, pk: int):
    project = get_selected_project(request)
    feat = get_object_or_404(GeoFeature, pk=pk, project=project, is_active=True)

    if request.method == 'GET':
        from .services import _feature_to_geojson_dict
        return JsonResponse(_feature_to_geojson_dict(feat))

    if not _user_can_edit_geo(request):
        return JsonResponse({'error': 'Sem permissão para editar o mapa.'}, status=403)

    if request.method == 'DELETE':
        delete_geo_feature(feat)
        return JsonResponse({'ok': True})

    try:
        data = _json_body(request)
        feat = update_geo_feature(feat, data)
        from .services import _feature_to_geojson_dict
        return JsonResponse({'ok': True, 'feature': _feature_to_geojson_dict(feat)})
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)


@login_required
@mapa_project_required
@require_GET
def api_activities_view(request):
    project = get_selected_project(request)
    query = (request.GET.get('q') or '').strip()
    leaves_only = request.GET.get('leaves', '1') != '0'
    activities = list_project_activities(project, query=query, leaves_only=leaves_only)
    return JsonResponse({'activities': activities})


@login_required
@mapa_project_required
@require_GET
def api_summary_view(request):
    project = get_selected_project(request)
    return JsonResponse(get_map_summary(project))


@login_required
@mapa_project_required
@require_http_methods(['POST'])
def api_sync_view(request):
    if not _user_can_edit_geo(request):
        return JsonResponse({'error': 'Sem permissão para sincronizar o mapa.'}, status=403)
    project = get_selected_project(request)
    stats = sync_snapshots_from_diario(project)
    return JsonResponse({'ok': True, **stats, 'summary': get_map_summary(project)})


@login_required
@mapa_project_required
@require_GET
def api_timeline_view(request):
    project = get_selected_project(request)
    dates = available_timeline_dates(project)
    return JsonResponse({'dates': dates})


@login_required
@mapa_project_required
@require_GET
def exportar_view(request):
    project = get_selected_project(request)
    fmt = (request.GET.get('format') or 'geojson').lower()
    collection = features_geojson_at_date(project, None)
    safe_code = project.code.replace(' ', '_')

    if fmt == 'geojson':
        response = HttpResponse(
            json.dumps(collection, ensure_ascii=False, indent=2),
            content_type='application/geo+json; charset=utf-8',
        )
        response['Content-Disposition'] = f'attachment; filename="{safe_code}_mapa.geojson"'
        return response

    if fmt == 'kml':
        kml = geojson_to_kml(collection, doc_name=f'{project.code} — {project.name}')
        response = HttpResponse(kml, content_type='application/vnd.google-earth.kml+xml; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{safe_code}_mapa.kml"'
        return response

    if fmt == 'kmz':
        kml = geojson_to_kml(collection, doc_name=f'{project.code} — {project.name}')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('doc.kml', kml.encode('utf-8'))
        response = HttpResponse(buf.getvalue(), content_type='application/vnd.google-earth.kmz')
        response['Content-Disposition'] = f'attachment; filename="{safe_code}_mapa.kmz"'
        return response

    if fmt == 'csv-pontos':
        rows = export_csv_pontos_rows(project)
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=['name', 'folder', 'latitude', 'longitude', 'altitude', 'description', 'status', 'progress_pct', 'kind'],
        )
        writer.writeheader()
        writer.writerows(rows)
        response = HttpResponse(buf.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{safe_code}_pontos.csv"'
        return response

    if fmt == 'csv-geometrias':
        rows = export_csv_geometrias_rows(project)
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=['name', 'folder', 'geometry_type', 'coordinate_count', 'description', 'status', 'progress_pct', 'kind'],
        )
        writer.writeheader()
        writer.writerows(rows)
        response = HttpResponse(buf.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{safe_code}_geometrias.csv"'
        return response

    return JsonResponse({'error': 'Formato inválido. Use geojson, kml, kmz, csv-pontos ou csv-geometrias.'}, status=400)


@login_required
@mapa_project_required
@require_http_methods(['GET', 'POST'])
def importar_view(request):
    if not _user_can_edit_geo(request):
        messages.error(request, 'Sem permissão para importar dados geográficos.')
        return redirect('mapa_geo:mapa')

    project = get_selected_project(request)

    if request.method == 'GET':
        return render(
            request,
            'mapa_geo/importar.html',
            {
                'project': project,
                'feature_count': GeoFeature.objects.filter(project=project, is_active=True).count(),
            },
        )

    upload = request.FILES.get('arquivo')
    if not upload:
        messages.error(request, 'Selecione um arquivo GeoJSON, KML ou KMZ.')
        return redirect('mapa_geo:importar')

    replace = request.POST.get('replace') == 'on'
    source_label = (request.POST.get('source_label') or upload.name or '').strip()[:200]
    name_lower = (upload.name or '').lower()

    try:
        content = upload.read()
        if name_lower.endswith('.kmz'):
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                kml_name = 'doc.kml' if 'doc.kml' in zf.namelist() else next(
                    (n for n in zf.namelist() if n.lower().endswith('.kml')),
                    None,
                )
                if not kml_name:
                    raise ValueError('KMZ sem arquivo KML interno.')
                raw = zf.read(kml_name).decode('utf-8', errors='replace')
        else:
            raw = content.decode('utf-8', errors='replace')

        if name_lower.endswith('.kml') or raw.lstrip().startswith('<'):
            payload = kml_to_geojson_features(raw)
        else:
            payload = json.loads(raw)

        stats = import_geojson_features(
            project,
            payload,
            source_label=source_label,
            replace=replace,
        )
        sync_stats = sync_snapshots_from_diario(project)
        messages.success(
            request,
            f'Importação concluída: {stats["created"]} criados, {stats["updated"]} atualizados. '
            f'Snapshots: {sync_stats["snapshots"]} em {sync_stats["dates"]} datas.',
        )
    except Exception as exc:
        messages.error(request, f'Falha na importação: {exc}')

    return redirect('mapa_geo:mapa')
