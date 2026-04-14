"""
Gestão de comunicados (Painel do sistema — grupo Administrador).
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from django.core.files.base import ContentFile

from accounts.decorators import require_group
from accounts.groups import GRUPOS

from .forms import ComunicadoForm
from .metrics import get_eligible_user_ids
from .models import Comunicado, ComunicadoResposta, ComunicadoVisualizacao, TipoConteudo

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


@require_group(GRUPOS.ADMINISTRADOR)
def lista(request):
    agora = timezone.now()
    qs = (
        Comunicado.objects.annotate(
            _vis_sum=Sum('visualizacoes__total_visualizacoes'),
            _n_conf=Count('visualizacoes', filter=Q(visualizacoes__confirmou_leitura=True)),
            _n_resp=Count('visualizacoes', filter=Q(visualizacoes__respondeu=True)),
        )
        .order_by('-criado_em')
        .select_related('criado_por')
        .prefetch_related('grupos_permitidos', 'obras_permitidas')
    )
    rows = []
    for c in qs:
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
        },
    )


@require_group(GRUPOS.ADMINISTRADOR)
def criar(request):
    if request.method == 'POST':
        form = ComunicadoForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.criado_por = request.user
            obj.save()
            form.save_m2m()
            _limpar_exclusoes_comunicado(obj)
            messages.success(request, 'Comunicado criado com sucesso.')
            if 'salvar_visualizar' in request.POST:
                return redirect('comunicados_painel_desempenho', pk=obj.pk)
            return redirect('comunicados_painel_editar', pk=obj.pk)
    else:
        form = ComunicadoForm()
    return render(request, 'comunicados/form.html', {'form': form, 'titulo_pagina': 'Novo comunicado', 'modo': 'criar'})


@require_group(GRUPOS.ADMINISTRADOR)
def editar(request, pk):
    comunicado = get_object_or_404(Comunicado, pk=pk)
    if request.method == 'POST':
        form = ComunicadoForm(request.POST, request.FILES, instance=comunicado)
        if form.is_valid():
            form.save()
            form.save_m2m()
            _limpar_exclusoes_comunicado(comunicado)
            messages.success(request, 'Alterações salvas.')
            if 'salvar_visualizar' in request.POST:
                return redirect('comunicados_painel_desempenho', pk=comunicado.pk)
            return redirect('comunicados_painel_editar', pk=comunicado.pk)
    else:
        form = ComunicadoForm(instance=comunicado)
    return render(
        request,
        'comunicados/form.html',
        {
            'form': form,
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
            publico_restrito_perfil=orig.publico_restrito_perfil,
            pode_fechar=orig.pode_fechar,
            exige_confirmacao=orig.exige_confirmacao,
            exige_resposta=orig.exige_resposta,
            bloquear_ate_acao=orig.bloquear_ate_acao,
            abrir_automaticamente=orig.abrir_automaticamente,
            mostrar_apos_fechar=orig.mostrar_apos_fechar,
            permitir_nao_mostrar_novamente=orig.permitir_nao_mostrar_novamente,
            criado_por=request.user,
        )
        novo.save()
        if orig.imagem:
            orig.imagem.open('rb')
            novo.imagem.save(orig.imagem.name, ContentFile(orig.imagem.read()), save=True)
            orig.imagem.close()
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
    return redirect('comunicados_painel_lista')


@require_group(GRUPOS.ADMINISTRADOR)
@require_POST
def encerrar(request, pk):
    c = get_object_or_404(Comunicado, pk=pk)
    agora = timezone.now()
    if c.data_fim and c.data_fim < agora:
        messages.info(request, 'Este comunicado já está encerrado.')
        return redirect('comunicados_painel_lista')
    c.data_fim = agora
    c.save()
    messages.success(request, 'Comunicado encerrado (data de fim definida para agora).')
    return redirect('comunicados_painel_lista')


@require_group(GRUPOS.ADMINISTRADOR)
def desempenho(request, pk):
    comunicado = get_object_or_404(Comunicado, pk=pk)
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
    n_resp = sum(
        1 for uid in eligible_ids if vis_by_uid.get(uid) and vis_by_uid[uid].respondeu
    )

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

    return render(
        request,
        'comunicados/desempenho.html',
        {
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
        },
    )
