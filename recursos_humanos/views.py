from django.contrib import messages
from django.db.models import Prefetch, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.decorators import login_required

from .decorators import require_rh
from .forms import (
    ColaboradorBasicoForm,
    DevolverAdmissaoForm,
    DocumentoStatusForm,
    DocumentoUploadForm,
    NovaRequisicaoForm,
    TipoDocumentoForm,
)
from .models import Colaborador, DocumentoColaborador, ObraLocal, TipoDocumento
from .services.admissao import montar_contexto_admissao
from .services.admissao_actions import (
    aprovar_documentacao,
    atualizar_status_documento,
    avancar_etapa_admissao,
    concluir_admissao,
    criar_requisicao,
    devolver_admissao,
    enviar_contrato,
    sincronizar_obras_gestao,
    upload_documento_arquivo,
)
from .services.alerts import contar_alertas, gerar_alertas, resumo_alertas


def _rh_nav_context(request, alertas_count=None):
    if alertas_count is None:
        alertas_count = contar_alertas()
    return {'rh_alertas_count': alertas_count}


def _enriquecer_colaborador(c):
    docs = list(c.documentos.all())
    c.docs_recebidos = sum(1 for d in docs if d.status == DocumentoColaborador.Status.RECEBIDO)
    c.docs_total = len(docs)
    c.proximo_prazo_fmt = c.proximo_prazo().strftime('%d/%m/%Y') if c.proximo_prazo() else None
    c.dias_proximo_prazo = c.dias_proximo_prazo()


def _redirect_admissao(pk):
    return redirect(f"{reverse('recursos_humanos:admissao')}?id={pk}")


@login_required
@require_rh
def colaboradores_list_view(request):
    qs = Colaborador.objects.prefetch_related('obras', 'documentos').all()
    busca = (request.GET.get('q') or '').strip()
    status_filtro = request.GET.get('status') or 'todos'
    obra_filtro = request.GET.get('obra') or ''

    if busca:
        qs = qs.filter(
            Q(nome__icontains=busca)
            | Q(cpf__icontains=busca)
            | Q(cargo__icontains=busca)
        )
    if status_filtro == 'em_admissao':
        qs = qs.filter(status=Colaborador.Status.EM_ADMISSAO)
    elif status_filtro == 'ativo':
        qs = qs.filter(status=Colaborador.Status.ATIVO)
    elif status_filtro == 'desligado':
        qs = qs.filter(status=Colaborador.Status.DESLIGADO)

    if obra_filtro:
        qs = qs.filter(obras__pk=obra_filtro).distinct()

    colaboradores = list(qs)
    for c in colaboradores:
        _enriquecer_colaborador(c)

    ctx = {
        'colaboradores': colaboradores,
        'obras': ObraLocal.objects.all(),
        'busca': busca,
        'status_filtro': status_filtro,
        'obra_filtro': obra_filtro,
        'contagens': {
            'ativo': Colaborador.objects.filter(status=Colaborador.Status.ATIVO).count(),
            'em_admissao': Colaborador.objects.filter(status=Colaborador.Status.EM_ADMISSAO).count(),
            'desligado': Colaborador.objects.filter(status=Colaborador.Status.DESLIGADO).count(),
        },
        **_rh_nav_context(request),
    }
    return render(request, 'recursos_humanos/colaboradores_list.html', ctx)


@login_required
@require_rh
def colaborador_detalhe_view(request, pk):
    colaborador = get_object_or_404(
        Colaborador.objects.prefetch_related(
            Prefetch('documentos', queryset=DocumentoColaborador.objects.select_related('tipo')),
            'obras',
        ),
        pk=pk,
    )

    if request.method == 'POST':
        acao = request.POST.get('acao')
        if acao == 'salvar_dados':
            form = ColaboradorBasicoForm(request.POST, instance=colaborador)
            if form.is_valid():
                form.save()
                messages.success(request, 'Dados atualizados.')
            else:
                messages.error(request, 'Verifique os campos do formulário.')
        elif acao == 'status_colaborador':
            novo = request.POST.get('status')
            if novo in dict(Colaborador.Status.choices):
                colaborador.status = novo
                colaborador.save(update_fields=['status', 'atualizado_em'])
                messages.success(request, f'Status alterado para {colaborador.get_status_display()}.')
        return redirect('recursos_humanos:colaborador_detalhe', pk=pk)

    ctx = {
        'colaborador': colaborador,
        'documentos': colaborador.documentos.all(),
        'form_colaborador': ColaboradorBasicoForm(instance=colaborador),
        **_rh_nav_context(request),
    }
    return render(request, 'recursos_humanos/colaborador_detalhe.html', ctx)


def _admissao_queryset():
    doc_qs = DocumentoColaborador.objects.select_related('tipo').order_by('tipo__ordem', 'tipo__nome')
    return (
        Colaborador.objects.filter(status=Colaborador.Status.EM_ADMISSAO)
        .prefetch_related(
            'historico_admissao',
            'obras',
            Prefetch('documentos', queryset=doc_qs),
        )
        .order_by('-data_admissao', 'nome')
    )


@login_required
@require_rh
def admissao_view(request):
    sincronizar_obras_gestao()
    admissoes = _admissao_queryset()
    selecionado_id = request.GET.get('id')
    selecionado = admissoes.filter(pk=selecionado_id).first() if selecionado_id else None
    if selecionado is None:
        selecionado = admissoes.first()

    historico = selecionado.historico_admissao.all() if selecionado else []
    admissao_ctx = montar_contexto_admissao(selecionado, historico) if selecionado else None
    devolver_form = DevolverAdmissaoForm()

    ctx = {
        'admissoes': admissoes,
        'selecionado': selecionado,
        'historico': historico,
        'admissao_ctx': admissao_ctx,
        'devolver_form': devolver_form,
        'etapas': [
            (1, 'Requisição'),
            (2, 'Coleta de Docs'),
            (3, 'Aprovação RH'),
            (4, 'Ass. Contrato'),
            (5, 'Ativo'),
        ],
        **_rh_nav_context(request),
    }
    return render(request, 'recursos_humanos/admissao.html', ctx)


@login_required
@require_rh
def admissao_nova_view(request):
    sincronizar_obras_gestao()
    if request.method == 'POST':
        form = NovaRequisicaoForm(request.POST)
        if form.is_valid():
            try:
                colab = criar_requisicao(form.cleaned_data, request.user)
                messages.success(request, f'Requisição criada para {colab.nome}.')
                return _redirect_admissao(colab.pk)
            except Exception as exc:
                messages.error(request, f'Não foi possível criar a requisição: {exc}')
    else:
        form = NovaRequisicaoForm(initial={'data_inicio': timezone.localdate()})
    return render(request, 'recursos_humanos/admissao_nova.html', {
        'form': form,
        **_rh_nav_context(request),
    })


@login_required
@require_rh
def admissao_acao_view(request, pk):
    if request.method != 'POST':
        return redirect('recursos_humanos:admissao')
    colaborador = get_object_or_404(Colaborador, pk=pk, status=Colaborador.Status.EM_ADMISSAO)
    acao = request.POST.get('acao')

    if acao == 'avancar':
        ok, msg = avancar_etapa_admissao(colaborador, request.user)
    elif acao == 'aprovar':
        ok, msg = aprovar_documentacao(colaborador, request.user)
    elif acao == 'devolver':
        form = DevolverAdmissaoForm(request.POST)
        if form.is_valid():
            ok, msg = devolver_admissao(colaborador, form.cleaned_data['motivo'], request.user)
        else:
            ok, msg = False, 'Informe o motivo da devolução.'
    elif acao == 'enviar_contrato':
        ok, msg = enviar_contrato(colaborador, request.user)
    elif acao == 'concluir':
        ok, msg = concluir_admissao(colaborador, request.user)
    else:
        ok, msg = False, 'Ação inválida.'

    (messages.success if ok else messages.error)(request, msg)
    if ok and acao == 'concluir':
        return redirect('recursos_humanos:colaborador_detalhe', pk=colaborador.pk)
    return _redirect_admissao(colaborador.pk)


@login_required
@require_rh
def documento_status_view(request, pk):
    if request.method != 'POST':
        return redirect('recursos_humanos:colaboradores')
    doc = get_object_or_404(DocumentoColaborador.objects.select_related('colaborador'), pk=pk)
    form = DocumentoStatusForm(request.POST)
    if form.is_valid():
        atualizar_status_documento(
            doc,
            form.cleaned_data['status'],
            form.cleaned_data.get('observacao', ''),
            request.user,
        )
        messages.success(request, f'Status de «{doc.tipo.nome}» atualizado.')
    else:
        messages.error(request, 'Status inválido.')
    next_url = request.POST.get('next') or reverse('recursos_humanos:colaborador_detalhe', args=[doc.colaborador_id])
    return HttpResponseRedirect(next_url)


@login_required
@require_rh
def documento_upload_view(request, pk):
    if request.method != 'POST':
        return redirect('recursos_humanos:colaboradores')
    doc = get_object_or_404(DocumentoColaborador.objects.select_related('colaborador'), pk=pk)
    form = DocumentoUploadForm(request.POST, request.FILES)
    if form.is_valid():
        upload_documento_arquivo(doc, form.cleaned_data['arquivo'], request.user)
        messages.success(request, f'Arquivo de «{doc.tipo.nome}» recebido.')
    else:
        messages.error(request, 'Selecione um arquivo válido (máx. 10 MB).')
    next_url = request.POST.get('next') or reverse('recursos_humanos:colaborador_detalhe', args=[doc.colaborador_id])
    return HttpResponseRedirect(next_url)


@login_required
@require_rh
def alertas_view(request):
    alertas = gerar_alertas()
    return render(request, 'recursos_humanos/alertas.html', {
        'alertas': alertas,
        'resumo': resumo_alertas(alertas),
        **_rh_nav_context(request, len(alertas)),
    })


@login_required
@require_rh
def documentos_config_view(request):
    if request.method == 'POST':
        acao = request.POST.get('acao')
        if acao == 'criar':
            form = TipoDocumentoForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Tipo de documento criado.')
            else:
                messages.error(request, 'Verifique os campos do novo tipo.')
        elif acao == 'editar':
            tipo = get_object_or_404(TipoDocumento, pk=request.POST.get('tipo_id'))
            form = TipoDocumentoForm(request.POST, instance=tipo)
            if form.is_valid():
                form.save()
                messages.success(request, 'Tipo de documento atualizado.')
            else:
                messages.error(request, 'Verifique os campos.')
        elif acao == 'excluir':
            tipo = get_object_or_404(TipoDocumento, pk=request.POST.get('tipo_id'))
            if tipo.documentos_colaborador.exists():
                messages.error(request, 'Não é possível excluir: documento em uso por colaboradores.')
            else:
                tipo.delete()
                messages.success(request, 'Tipo de documento excluído.')
        return redirect('recursos_humanos:documentos_config')

    tipos = TipoDocumento.objects.all()
    return render(request, 'recursos_humanos/documentos_config.html', {
        'tipos': tipos,
        'form_novo': TipoDocumentoForm(initial={'ordem': (tipos.count() + 1)}),
        **_rh_nav_context(request),
    })
