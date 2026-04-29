"""
Gestão de comunicados (Painel do sistema — grupo Administrador).
"""
from __future__ import annotations

import csv
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from django.core.files.base import ContentFile

from accounts.decorators import require_group
from accounts.groups import GRUPOS

from .forms import (
    ComunicadoForm,
    comunicado_imagem_formset_factory,
    reordenar_imagens_comunicado,
)
from .metrics import get_eligible_user_ids
from .models import Comunicado, ComunicadoImagem, ComunicadoResposta, ComunicadoVisualizacao, TipoConteudo

User = get_user_model()


def _limpar_exclusoes_comunicado(comunicado: Comunicado) -> None:
    """O painel só gere público por inclusão; exclusões ficam para o admin Django."""
    comunicado.grupos_excluidos.clear()
    comunicado.usuarios_excluidos.clear()
    comunicado.obras_excluidas.clear()


def _status_comunicado(comunicado, agora):
    if comunicado.data_fim and comunicado.data_fim < agora:
        return 'encerrado', 'Encerrado'
    if comunicado.ativo:
        return 'ativo', 'Ativo'
    return 'inativo', 'Inativo'


LISTA_PER_PAGE = 25


def _querystring_voltar_lista(request) -> str:
    """Reconstrói filtros da lista a partir de GET (incl. querystring em POST)."""
    q = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or '').strip()
    page = (request.GET.get('page') or '').strip()
    params: dict[str, str] = {}
    if q:
        params['q'] = q
    if status:
        params['status'] = status
    if page.isdigit():
        p = int(page)
        if p > 1:
            params['page'] = str(p)
    return urlencode(params)


def _redirect_painel_lista(request):
    qs = _querystring_voltar_lista(request)
    base = reverse('comunicados_painel_lista')
    if qs:
        return redirect(f'{base}?{qs}')
    return redirect(base)


@require_group(GRUPOS.ADMINISTRADOR)
def lista(request):
    agora = timezone.now()
    q_busca = (request.GET.get('q') or '').strip()
    status_filtro = (request.GET.get('status') or '').strip()

    qs = Comunicado.objects.annotate(
        _vis_sum=Sum('visualizacoes__total_visualizacoes'),
        _n_conf=Count('visualizacoes', filter=Q(visualizacoes__confirmou_leitura=True)),
        _n_resp=Count('visualizacoes', filter=Q(visualizacoes__respondeu=True)),
    ).select_related('criado_por').prefetch_related('grupos_permitidos', 'obras_permitidas')

    if q_busca:
        qs = qs.filter(titulo__icontains=q_busca)

    if status_filtro == 'encerrado':
        qs = qs.filter(data_fim__isnull=False, data_fim__lt=agora)
    elif status_filtro == 'ativo':
        qs = qs.filter(Q(data_fim__isnull=True) | Q(data_fim__gte=agora)).filter(ativo=True)
    elif status_filtro == 'inativo':
        qs = qs.filter(Q(data_fim__isnull=True) | Q(data_fim__gte=agora)).filter(ativo=False)

    qs = qs.order_by('-criado_em')
    paginator = Paginator(qs, LISTA_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    preserve_params = {k: v for k, v in {'q': q_busca, 'status': status_filtro}.items() if v}
    preserve_qs = urlencode(preserve_params)

    redirect_params = dict(preserve_params)
    if page_obj.number > 1:
        redirect_params['page'] = str(page_obj.number)
    redirect_lista_qs = urlencode(redirect_params)

    rows = []
    for c in page_obj.object_list:
        st_key, st_label = _status_comunicado(c, agora)
        rows.append(
            {
                'obj': c,
                'status_key': st_key,
                'status_label': st_label,
                'vis_total': c._vis_sum or 0,
                'n_conf': c._n_conf or 0,
                'n_resp': c._n_resp or 0,
            }
        )
    return render(
        request,
        'comunicados/lista.html',
        {
            'rows': rows,
            'agora': agora,
            'page_obj': page_obj,
            'q_busca': q_busca,
            'status_filtro': status_filtro,
            'preserve_qs': preserve_qs,
            'redirect_lista_qs': redirect_lista_qs,
            'lista_per_page': LISTA_PER_PAGE,
        },
    )


@require_group(GRUPOS.ADMINISTRADOR)
def criar(request):
    FS = comunicado_imagem_formset_factory()
    if request.method == 'POST':
        form = ComunicadoForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(
                request,
                'comunicados/form.html',
                {
                    'form': form,
                    'imagem_formset': FS(),
                    'titulo_pagina': 'Novo comunicado',
                    'modo': 'criar',
                },
            )
        saved_ok = False
        fs_invalid = None
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.criado_por = request.user
            obj.save()
            form.save_m2m()
            fs = FS(request.POST, request.FILES, instance=obj)
            if fs.is_valid():
                fs.save()
                reordenar_imagens_comunicado(obj)
                saved_ok = True
            else:
                fs_invalid = fs
                transaction.set_rollback(True)
        if saved_ok:
            _limpar_exclusoes_comunicado(obj)
            messages.success(request, 'Comunicado criado com sucesso.')
            if 'salvar_visualizar' in request.POST:
                return redirect('comunicados_painel_desempenho', pk=obj.pk)
            return redirect('comunicados_painel_criar')
        return render(
            request,
            'comunicados/form.html',
            {
                'form': ComunicadoForm(request.POST, request.FILES),
                'imagem_formset': fs_invalid,
                'titulo_pagina': 'Novo comunicado',
                'modo': 'criar',
            },
        )
    form = ComunicadoForm()
    imagem_formset = FS()
    return render(
        request,
        'comunicados/form.html',
        {
            'form': form,
            'imagem_formset': imagem_formset,
            'titulo_pagina': 'Novo comunicado',
            'modo': 'criar',
        },
    )


@require_group(GRUPOS.ADMINISTRADOR)
def editar(request, pk):
    comunicado = get_object_or_404(Comunicado, pk=pk)
    FS = comunicado_imagem_formset_factory()
    if request.method == 'POST':
        form = ComunicadoForm(request.POST, request.FILES, instance=comunicado)
        if not form.is_valid():
            return render(
                request,
                'comunicados/form.html',
                {
                    'form': form,
                    'imagem_formset': FS(request.POST, request.FILES, instance=comunicado),
                    'comunicado': comunicado,
                    'titulo_pagina': f'Editar: {comunicado.titulo}',
                    'modo': 'editar',
                },
            )
        saved_ok = False
        fs_invalid = None
        with transaction.atomic():
            form.save()
            form.save_m2m()
            fs = FS(request.POST, request.FILES, instance=comunicado)
            if fs.is_valid():
                fs.save()
                reordenar_imagens_comunicado(comunicado)
                saved_ok = True
            else:
                fs_invalid = fs
                transaction.set_rollback(True)
        if saved_ok:
            _limpar_exclusoes_comunicado(comunicado)
            messages.success(request, 'Alterações salvas.')
            if 'salvar_visualizar' in request.POST:
                return redirect('comunicados_painel_desempenho', pk=comunicado.pk)
            return redirect('comunicados_painel_editar', pk=comunicado.pk)
        comunicado.refresh_from_db()
        return render(
            request,
            'comunicados/form.html',
            {
                'form': ComunicadoForm(request.POST, request.FILES, instance=comunicado),
                'imagem_formset': fs_invalid,
                'comunicado': comunicado,
                'titulo_pagina': f'Editar: {comunicado.titulo}',
                'modo': 'editar',
            },
        )
    form = ComunicadoForm(instance=comunicado)
    imagem_formset = FS(instance=comunicado)
    return render(
        request,
        'comunicados/form.html',
        {
            'form': form,
            'imagem_formset': imagem_formset,
            'comunicado': comunicado,
            'titulo_pagina': f'Editar: {comunicado.titulo}',
            'modo': 'editar',
        },
    )


@require_group(GRUPOS.ADMINISTRADOR)
@require_POST
def duplicar(request, pk):
    orig = get_object_or_404(Comunicado, pk=pk)
    with transaction.atomic():
        novo = Comunicado(
            titulo=f'Cópia de {orig.titulo}',
            slug='',
            descricao_interna=orig.descricao_interna,
            ativo=False,
            tipo_conteudo=orig.tipo_conteudo,
            titulo_visivel=orig.titulo_visivel,
            subtitulo=orig.subtitulo,
            texto_principal=orig.texto_principal,
            link_destino=orig.link_destino,
            texto_botao=orig.texto_botao,
            destaque_visual=orig.destaque_visual,
            tipo_exibicao=orig.tipo_exibicao,
            max_exibicoes_por_usuario=orig.max_exibicoes_por_usuario,
            data_inicio=orig.data_inicio,
            data_fim=orig.data_fim,
            dias_ativo=orig.dias_ativo,
            prioridade=orig.prioridade,
            publico_todos=orig.publico_todos,
            publico_escopo_criterios=orig.publico_escopo_criterios,
            pode_fechar=orig.pode_fechar,
            exige_confirmacao=orig.exige_confirmacao,
            exige_resposta=orig.exige_resposta,
            abrir_automaticamente=orig.abrir_automaticamente,
            mostrar_apos_fechar=orig.mostrar_apos_fechar,
            permitir_nao_mostrar_novamente=orig.permitir_nao_mostrar_novamente,
            criado_por=request.user,
        )
        novo.save()
        for im in orig.imagens.all().order_by('ordem', 'pk'):
            nova = ComunicadoImagem(comunicado=novo, ordem=im.ordem)
            im.arquivo.open('rb')
            nome = im.arquivo.name.split('/')[-1]
            nova.arquivo.save(nome, ContentFile(im.arquivo.read()), save=False)
            nova.save()
            im.arquivo.close()
        novo.grupos_permitidos.set(orig.grupos_permitidos.all())
        novo.usuarios_permitidos.set(orig.usuarios_permitidos.all())
        novo.obras_permitidas.set(orig.obras_permitidas.all())
    messages.success(request, 'Comunicado duplicado. Revise e ative quando desejar.')
    return redirect('comunicados_painel_editar', pk=novo.pk)


@require_group(GRUPOS.ADMINISTRADOR)
@require_POST
def toggle(request, pk):
    c = get_object_or_404(Comunicado, pk=pk)
    c.ativo = not c.ativo
    c.save()
    messages.success(request, 'Status atualizado.')
    return _redirect_painel_lista(request)


@require_group(GRUPOS.ADMINISTRADOR)
@require_POST
def encerrar(request, pk):
    c = get_object_or_404(Comunicado, pk=pk)
    agora = timezone.now()
    if c.data_fim and c.data_fim < agora:
        messages.info(request, 'Este comunicado já está encerrado.')
        return _redirect_painel_lista(request)
    c.data_fim = agora
    c.save()
    messages.success(request, 'Comunicado encerrado (data de fim definida para agora).')
    return _redirect_painel_lista(request)


def _montar_contexto_desempenho(comunicado: Comunicado) -> dict:
    """Dados da página de desempenho e do export CSV (mesma fonte)."""
    agora = timezone.now()
    eligible_ids = get_eligible_user_ids(comunicado)
    n_deveriam = len(eligible_ids)

    visualizacoes = list(
        ComunicadoVisualizacao.objects.filter(comunicado=comunicado).select_related('usuario')
    )
    vis_by_uid = {v.usuario_id: v for v in visualizacoes}

    viewed_eligible = {
        uid
        for uid in eligible_ids
        if vis_by_uid.get(uid) and vis_by_uid[uid].total_visualizacoes > 0
    }
    n_visualizaram = len(viewed_eligible)

    n_confirm = sum(
        1
        for uid in eligible_ids
        if vis_by_uid.get(uid) and vis_by_uid[uid].confirmou_leitura
    )
    n_resp = sum(1 for uid in eligible_ids if vis_by_uid.get(uid) and vis_by_uid[uid].respondeu)

    pendentes = max(0, n_deveriam - n_visualizaram)

    def pct(num, den):
        if not den:
            return 0.0
        return round(100.0 * num / den, 1)

    taxa_leitura = pct(n_visualizaram, n_deveriam)
    taxa_conf = pct(n_confirm, n_deveriam)
    taxa_resp = pct(n_resp, n_deveriam)

    users_map = {u.pk: u for u in User.objects.filter(pk__in=eligible_ids)}

    def _sort_key(uid):
        u = users_map.get(uid)
        if not u:
            return ''
        return (u.get_full_name() or u.username or '').lower()

    detalhes = []
    for uid in sorted(eligible_ids, key=_sort_key):
        u = users_map[uid]
        v = vis_by_uid.get(uid)
        detalhes.append(
            {
                'usuario': u,
                'vis': v,
                'primeira': v.primeira_visualizacao if v else None,
                'ultima': v.ultima_visualizacao if v else None,
                'total_v': v.total_visualizacoes if v else 0,
                'confirmou': v.confirmou_leitura if v else False,
                'respondeu': v.respondeu if v else False,
            }
        )

    respostas = []
    if comunicado.tipo_conteudo == TipoConteudo.FORMULARIO:
        respostas = list(
            ComunicadoResposta.objects.filter(comunicado=comunicado)
            .select_related('usuario')
            .order_by('-data_resposta')
        )

    return {
        'comunicado': comunicado,
        'n_deveriam': n_deveriam,
        'n_visualizaram': n_visualizaram,
        'n_confirm': n_confirm,
        'n_resp': n_resp,
        'pendentes': pendentes,
        'taxa_leitura': taxa_leitura,
        'taxa_conf': taxa_conf,
        'taxa_resp': taxa_resp,
        'detalhes': detalhes,
        'respostas': respostas,
        'agora': agora,
    }


@require_group(GRUPOS.ADMINISTRADOR)
def desempenho(request, pk):
    comunicado = get_object_or_404(Comunicado, pk=pk)
    ctx = _montar_contexto_desempenho(comunicado)
    return render(request, 'comunicados/desempenho.html', ctx)


@require_group(GRUPOS.ADMINISTRADOR)
def desempenho_exportar_csv(request, pk):
    comunicado = get_object_or_404(Comunicado, pk=pk)
    ctx = _montar_contexto_desempenho(comunicado)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    fn = f'desempenho_comunicado_{comunicado.pk}.csv'
    response['Content-Disposition'] = f'attachment; filename="{fn}"'
    response.write('\ufeff')

    w = csv.writer(response, delimiter=';')
    c = ctx['comunicado']
    w.writerow(['Comunicado (interno)', c.titulo])
    w.writerow(['Slug', c.slug])
    w.writerow(['Exportado em', timezone.now().strftime('%d/%m/%Y %H:%M:%S')])
    w.writerow([])
    w.writerow(['Indicador', 'Valor'])
    w.writerow(['Deveriam ver', ctx['n_deveriam']])
    w.writerow(['Visualizaram', ctx['n_visualizaram']])
    w.writerow(['Confirmaram', ctx['n_confirm']])
    w.writerow(['Responderam', ctx['n_resp']])
    w.writerow(['Ainda não viram', ctx['pendentes']])
    w.writerow(['Taxa leitura %', ctx['taxa_leitura']])
    w.writerow(['Taxa confirmação %', ctx['taxa_conf']])
    w.writerow(['Taxa resposta %', ctx['taxa_resp']])
    w.writerow([])
    w.writerow(
        [
            'Usuário',
            'Username',
            '1ª visualização',
            'Última visualização',
            'Vezes',
            'Confirmou',
            'Respondeu',
            'Status final',
        ]
    )
    for row in ctx['detalhes']:
        u = row['usuario']
        nome = (u.get_full_name() or '').strip()
        vis = row['vis']
        st = vis.get_status_final_display() if vis else 'Pendente'
        w.writerow(
            [
                nome,
                u.username,
                row['primeira'].strftime('%d/%m/%Y %H:%M') if row['primeira'] else '',
                row['ultima'].strftime('%d/%m/%Y %H:%M') if row['ultima'] else '',
                row['total_v'],
                'Sim' if row['confirmou'] else 'Não',
                'Sim' if row['respondeu'] else 'Não',
                st,
            ]
        )

    if ctx['respostas']:
        w.writerow([])
        w.writerow(['Respostas ao formulário'])
        w.writerow(['Data', 'Usuário', 'Resposta'])
        for r in ctx['respostas']:
            w.writerow(
                [
                    r.data_resposta.strftime('%d/%m/%Y %H:%M'),
                    (r.usuario.get_full_name() or r.usuario.username),
                    (r.resposta or '').replace('\r\n', ' ').replace('\n', ' '),
                ]
            )

    return response
