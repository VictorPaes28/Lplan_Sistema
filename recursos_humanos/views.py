from django.contrib import messages
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Min, Prefetch, Q, Value, When
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.decorators import login_required

from .decorators import require_rh
from .forms import (
    CargoRHForm,
    ColaboradorBasicoForm,
    DevolverAdmissaoForm,
    DocumentoRejeitarForm,
    DocumentoStatusForm,
    DocumentoUploadForm,
    NovaRequisicaoForm,
    PortalCandidatoDadosForm,
    ReprovarRequisicaoForm,
    TipoDocumentoForm,
)
from .models import (
    CargoCatalogo,
    CargoRH,
    Colaborador,
    DocumentoColaborador,
    ObraLocal,
    PrazoContrato,
    TipoDocumento,
)
from .services.admissao import montar_contexto_admissao
from .services.alertas_config import obter_configuracao_alertas
from recursos_humanos.services.documentos import (
    admissao_etapa_concluida,
    colaborador_documentos_recebidos_validos,
    colaborador_tem_pendencia_documentos,
    documento_alerta_vencimento,
    documento_dias_restantes,
    documento_esta_vencido,
    documento_elegivel_reenvio,
    etapa_fluxo_efetiva,
    solicitar_reenvio_documento,
)
from .services.admissao_actions import (
    aprovar_documentacao,
    aprovar_requisicao_gestor,
    atualizar_requisicao,
    atualizar_status_documento,
    avancar_etapa_admissao,
    colaborador_admissao_concluida,
    concluir_admissao,
    criar_requisicao,
    devolver_admissao,
    enviar_lembrete_coleta_documentos,
    registrar_historico,
    reprovar_requisicao_gestor,
    garantir_requisicao_criada_por,
    dados_portal_completos,
    instanciar_documentos,
    obras_reais_queryset,
    salvar_dados_portal_candidato,
    sincronizar_documentos_em_andamento,
    sincronizar_obras_gestao,
    usuarios_gestor_list,
    aprovar_documento_arquivo,
    rejeitar_documento_arquivo,
    remover_documento_arquivo,
    upload_documento_arquivo,
    listar_historico_colaborador,
    queryset_fluxo_admissao,
    serializar_historico_json,
    _usuario_eh_rh,
    _usuario_pode_aprovar_requisicao,
)
from .services.alerts import contar_alertas, gerar_alertas, resumo_alertas
from .services.notificacoes_sistema import sincronizar_alertas_sino


def _sincronizar_notificacoes_rh():
    try:
        sincronizar_alertas_sino()
    except Exception:
        pass


def _salvar_rascunho_requisicao(request, form=None, exc_msg=None):
    draft = {
        'nome': request.POST.get('nome', ''),
        'cpf': request.POST.get('cpf', ''),
        'email': request.POST.get('email', ''),
        'telefone': request.POST.get('telefone', ''),
        'cargo': request.POST.get('cargo', ''),
        'cargo_rh': request.POST.get('cargo_rh', ''),
        'obra': request.POST.getlist('obra'),
        'tipo_contrato': request.POST.get('tipo_contrato', 'CLT'),
        'salario': request.POST.get('salario', ''),
        'data_inicio': request.POST.get('data_inicio', ''),
        'gestor_id': request.POST.get('gestor_id', ''),
        'motivo': request.POST.get('motivo', 'Nova contratação'),
        'observacoes': request.POST.get('observacoes', ''),
        'prazo_duracao_dias': request.POST.get('prazo_duracao_dias', ''),
        'clt_periodo_experiencia': bool(request.POST.get('clt_periodo_experiencia')),
    }
    if form is not None and not form.is_valid():
        draft['errors'] = {
            field: [str(err) for err in errs]
            for field, errs in form.errors.items()
        }
    if exc_msg:
        draft['exception'] = str(exc_msg)
    request.session['rh_requisicao_draft'] = draft


def _rh_nav_context(request, alertas_count=None):
    if alertas_count is None:
        alertas_count = contar_alertas()
    sincronizar_obras_gestao()
    form_requisicao = NovaRequisicaoForm(initial={'data_inicio': timezone.localdate()})
    cargos_catalogo = list(
        CargoCatalogo.objects.values_list('nome', flat=True).order_by('nome')
    )
    if not cargos_catalogo:
        cargos_catalogo = list(
            Colaborador.objects.exclude(cargo='')
            .values_list('cargo', flat=True)
            .distinct()
            .order_by('cargo')[:50]
        )
    solicitante = ''
    if getattr(request, 'user', None) and request.user.is_authenticated:
        solicitante = request.user.get_full_name() or request.user.username
    requisicao_draft = None
    if request.GET.get('nova') == '1':
        requisicao_draft = request.session.pop('rh_requisicao_draft', None)
    return {
        'rh_alertas_count': alertas_count,
        'rh_form_requisicao': form_requisicao,
        'rh_cargos_catalogo': cargos_catalogo,
        'rh_cargos_rh': CargoRH.objects.all(),
        'rh_solicitante_nome': solicitante,
        'rh_requisicao_draft': requisicao_draft,
        'rh_usuarios_gestor': usuarios_gestor_list(),
    }


def _enriquecer_colaborador(c):
    docs = list(c.documentos.all())
    c.docs_recebidos = sum(1 for d in docs if d.status == DocumentoColaborador.Status.RECEBIDO)
    c.docs_total = len(docs)
    c.proximo_prazo_fmt = c.proximo_prazo().strftime('%d/%m/%Y') if c.proximo_prazo() else None
    c.dias_proximo_prazo = c.dias_proximo_prazo()


def _redirect_admissao(pk):
    return redirect(f"{reverse('recursos_humanos:admissao')}?id={pk}")


def url_colaboradores_com_modal(pk, **extra_params):
    """URL da lista com query param para abrir o modal de perfil via JS."""
    from urllib.parse import urlencode

    params = {'abrir_colaborador': pk, **extra_params}
    return f'{reverse("recursos_humanos:colaboradores_list")}?{urlencode(params)}'


def redirect_para_colaborador(pk, **extra_params):
    """Redireciona para colaboradores_list com modal de perfil aberto."""
    return redirect(url_colaboradores_com_modal(pk, **extra_params))


_PORTAL_STATUS_OK = frozenset({
    Colaborador.Status.EM_ADMISSAO,
    Colaborador.Status.ATIVO,
})


def _portal_status_permitido(colaborador):
    return colaborador.status in _PORTAL_STATUS_OK


_STATUS_ORDER = Case(
    When(status=Colaborador.Status.EM_ADMISSAO, then=Value(0)),
    When(status=Colaborador.Status.ATIVO, then=Value(1)),
    When(status=Colaborador.Status.DESLIGADO, then=Value(2)),
    default=Value(3),
    output_field=IntegerField(),
)


@login_required
@require_rh
def colaboradores_list_view(request):
    _sincronizar_notificacoes_rh()
    qs = (
        Colaborador.objects.prefetch_related('obras', 'documentos')
        .annotate(
            status_order=_STATUS_ORDER,
            proximo_prazo_sort=Min('documentos__vencimento'),
        )
        .order_by('status_order', 'proximo_prazo_sort', 'nome')
    )
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

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    for c in page_obj:
        _enriquecer_colaborador(c)

    ctx = {
        'page_obj': page_obj,
        'colaboradores': page_obj,
        'obras': obras_reais_queryset(),
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
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if acao == 'salvar_dados':
            form = ColaboradorBasicoForm(request.POST, instance=colaborador)
            if is_ajax:
                if form.is_valid():
                    form.save()
                    colaborador.refresh_from_db()
                    return JsonResponse({
                        'ok': True,
                        'nome': colaborador.nome,
                        'cargo': colaborador.cargo,
                        'status': colaborador.status,
                        'status_display': colaborador.get_status_display(),
                    })
                return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
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
        elif acao == 'enviar_link_portal':
            telefone = request.POST.get('telefone', '').strip()
            if telefone and colaborador.status == Colaborador.Status.EM_ADMISSAO:
                if not colaborador.token_portal_valido():
                    colaborador.gerar_token_portal(dias=30)
                from .services.notificacoes import enviar_link_portal_whatsapp

                sucesso = enviar_link_portal_whatsapp(
                    telefone,
                    colaborador.nome,
                    colaborador.token_portal,
                )
                if sucesso:
                    messages.success(request, f'Link enviado para {telefone}.')
                else:
                    messages.error(request, 'Erro ao enviar o link.')
            elif not telefone:
                messages.error(request, 'Informe o telefone do candidato.')
        return redirect_para_colaborador(pk)

    historico = listar_historico_colaborador(colaborador, limite=50)

    prazo_ativo = colaborador.prazos_contrato.filter(
        status=PrazoContrato.Status.ATIVO,
    ).first()

    portal_url = None
    if colaborador.status == Colaborador.Status.EM_ADMISSAO and colaborador.token_portal:
        base = getattr(settings, 'SITE_URL', '').rstrip('/')
        portal_url = f'{base}/rh/portal/{colaborador.token_portal}/'

    ctx = {
        'colaborador': colaborador,
        'documentos': colaborador.documentos.all(),
        'form_colaborador': ColaboradorBasicoForm(instance=colaborador),
        'obras_catalogo': obras_reais_queryset(),
        'historico': historico,
        'portal_url': portal_url,
        'token_portal_valido': colaborador.token_portal_valido(),
        'prazo_ativo': prazo_ativo,
        'prazo_tipo_choices': PrazoContrato.Tipo.choices,
        **_rh_nav_context(request),
    }
    return render(request, 'recursos_humanos/colaborador_detalhe.html', ctx)


@login_required
@require_rh
def colaborador_json_view(request, pk):
    colaborador = get_object_or_404(
        Colaborador.objects.prefetch_related('obras'),
        pk=pk,
    )
    documentos = colaborador.documentos.select_related('tipo').order_by('tipo__ordem', 'tipo__nome')

    docs_data = []
    url_perfil = url_colaboradores_com_modal(colaborador.pk)
    for doc in documentos:
        dias_restantes = documento_dias_restantes(doc)
        alerta_venc = documento_alerta_vencimento(doc)
        vencido = documento_esta_vencido(doc)
        pode_reenvio, _ = documento_elegivel_reenvio(doc)
        pode_aprovar = (
            bool(doc.arquivo)
            and doc.status == DocumentoColaborador.Status.PENDENTE
        )
        docs_data.append({
            'id': doc.pk,
            'nome': doc.tipo.nome,
            'status': doc.status,
            'data_emissao': doc.data_emissao.strftime('%d/%m/%Y') if doc.data_emissao else None,
            'vencimento': doc.vencimento.strftime('%d/%m/%Y') if doc.vencimento else None,
            'dias_restantes': dias_restantes,
            'alerta_vencimento': alerta_venc,
            'vencido': vencido,
            'reenvio_solicitado': doc.reenvio_solicitado,
            'pode_solicitar_reenvio': pode_reenvio,
            'url_solicitar_reenvio': reverse(
                'recursos_humanos:documento_solicitar_reenvio',
                kwargs={'pk': colaborador.pk, 'doc_pk': doc.pk},
            ) if pode_reenvio else None,
            'pode_aprovar': pode_aprovar,
            'url_aprovar': reverse('recursos_humanos:documento_aprovar', args=[doc.pk]) if pode_aprovar else None,
            'url_redirect': url_perfil,
            'obrigatorio': doc.tipo.obrigatorio,
            'tem_arquivo': bool(doc.arquivo),
            'tem_validade': doc.tipo.tem_validade,
            'url_arquivo': doc.arquivo.url if doc.arquivo else None,
        })

    from .services.prazo_contrato import prazo_contrato_para_perfil, serializar_prazo_perfil

    prazo_exibir = prazo_contrato_para_perfil(colaborador)
    prazo_data = serializar_prazo_perfil(prazo_exibir) if prazo_exibir else None

    obras = list(colaborador.obras.values_list('nome', flat=True))

    historico = serializar_historico_json(listar_historico_colaborador(colaborador))

    return JsonResponse({
        'id': colaborador.pk,
        'nome': colaborador.nome,
        'iniciais': colaborador.iniciais,
        'cpf': colaborador.cpf,
        'email': colaborador.email,
        'telefone': colaborador.telefone,
        'rg': colaborador.rg,
        'data_nascimento': colaborador.data_nascimento.strftime('%Y-%m-%d') if colaborador.data_nascimento else '',
        'data_nascimento_fmt': colaborador.data_nascimento.strftime('%d/%m/%Y') if colaborador.data_nascimento else '',
        'endereco': colaborador.endereco,
        'dados_bancarios': colaborador.dados_bancarios,
        'pis': colaborador.pis,
        'escolaridade': colaborador.escolaridade,
        'tamanho_camisa': colaborador.tamanho_camisa,
        'tamanho_bota': colaborador.tamanho_bota,
        'cargo': colaborador.cargo,
        'cargo_rh': colaborador.cargo_rh_id or '',
        'cargo_rh_nome': colaborador.cargo_rh.nome if colaborador.cargo_rh_id else '',
        'empresa': colaborador.empresa,
        'status': colaborador.status,
        'status_display': colaborador.get_status_display(),
        'data_admissao': colaborador.data_admissao.strftime('%Y-%m-%d') if colaborador.data_admissao else '',
        'data_admissao_fmt': colaborador.data_admissao.strftime('%d/%m/%Y') if colaborador.data_admissao else '',
        'tipo_contrato': colaborador.tipo_contrato,
        'salario': colaborador.salario,
        'observacoes_requisicao': colaborador.observacoes_requisicao,
        'obras': obras,
        'obras_ids': list(colaborador.obras.values_list('pk', flat=True)),
        'docs_recebidos': colaborador_documentos_recebidos_validos(colaborador),
        'docs_total': colaborador.documentos_total(),
        'pendencia_documentos': colaborador_tem_pendencia_documentos(colaborador),
        'documentos': docs_data,
        'prazo_contrato': prazo_data,
        'historico': historico,
        'url_detalhe': reverse('recursos_humanos:colaborador_detalhe', args=[colaborador.pk]),
        'url_editar': reverse('recursos_humanos:colaborador_detalhe', args=[colaborador.pk]),
        'url_excluir': reverse('recursos_humanos:colaborador_excluir', args=[colaborador.pk]),
    })


@login_required
@require_rh
def documento_solicitar_reenvio_view(request, pk, doc_pk):
    if request.method != 'POST':
        return redirect_para_colaborador(pk)

    colaborador = get_object_or_404(Colaborador, pk=pk)
    doc = get_object_or_404(
        DocumentoColaborador,
        pk=doc_pk,
        colaborador=colaborador,
    )
    ok, msg = solicitar_reenvio_documento(doc, request.user)
    if ok:
        messages.success(request, msg)
    else:
        messages.error(request, msg)
    next_url = request.POST.get('next')
    if next_url:
        return HttpResponseRedirect(next_url)
    return redirect_para_colaborador(pk)


def _requisicao_edicao_payload(colaborador: Colaborador) -> dict:
    return {
        'colaborador_id': colaborador.pk,
        'nome': colaborador.nome,
        'cpf': colaborador.cpf,
        'email': colaborador.email,
        'telefone': colaborador.telefone,
        'cargo': colaborador.cargo,
        'cargo_rh': colaborador.cargo_rh_id or '',
        'obra': list(colaborador.obras.values_list('pk', flat=True)),
        'tipo_contrato': colaborador.tipo_contrato,
        'salario': colaborador.salario,
        'data_inicio': colaborador.data_admissao.isoformat() if colaborador.data_admissao else '',
        'gestor_id': colaborador.gestor_aprovador_user_id or '',
        'motivo': colaborador.motivo_admissao or 'Nova contratação',
        'observacoes': colaborador.observacoes_requisicao,
        'motivo_reprovacao': colaborador.requisicao_motivo_reprovacao,
    }


def _admissao_queryset(user=None):
    return queryset_fluxo_admissao(user)


@login_required
def gestor_aprovar_requisicao_view(request, pk):
    """Aprovação de requisição pelo gestor (sem exigir perfil RH)."""
    colaborador = get_object_or_404(
        Colaborador.objects.select_related('gestor_aprovador_user').prefetch_related('obras'),
        pk=pk,
        status=Colaborador.Status.EM_ADMISSAO,
        etapa_admissao=1,
        requisicao_aprovada_gestor=False,
        requisicao_reprovada=False,
    )
    if not _usuario_pode_aprovar_requisicao(colaborador, request.user):
        messages.error(request, 'Você não tem permissão para aprovar esta requisição.')
        return redirect('select-system')

    historico = listar_historico_colaborador(colaborador, limite=10)
    admissao_ctx = montar_contexto_admissao(colaborador, historico, user=request.user)
    ctx_etapa1 = admissao_ctx['etapa_1']

    if request.method == 'POST':
        acao = request.POST.get('acao')
        if acao == 'aprovar_requisicao':
            ok, msg = aprovar_requisicao_gestor(colaborador, request.user)
        elif acao == 'reprovar_requisicao':
            form = ReprovarRequisicaoForm(request.POST)
            if form.is_valid():
                ok, msg = reprovar_requisicao_gestor(colaborador, form.cleaned_data['motivo'], request.user)
            else:
                ok, msg = False, 'Informe o motivo da reprovação.'
        else:
            ok, msg = False, 'Ação inválida.'

        (messages.success if ok else messages.error)(request, msg)
        if ok and acao == 'aprovar_requisicao':
            if _usuario_eh_rh(request.user):
                return redirect(f"{reverse('recursos_humanos:admissao')}?id={colaborador.pk}")
            return render(
                request,
                'recursos_humanos/gestor_aprovar_requisicao.html',
                {
                    'colaborador': colaborador,
                    'ctx': ctx_etapa1,
                    'concluido': True,
                },
            )
        if ok and acao == 'reprovar_requisicao':
            return render(
                request,
                'recursos_humanos/gestor_aprovar_requisicao.html',
                {
                    'colaborador': colaborador,
                    'ctx': ctx_etapa1,
                    'reprovado': True,
                },
            )

    return render(
        request,
        'recursos_humanos/gestor_aprovar_requisicao.html',
        {
            'colaborador': colaborador,
            'ctx': ctx_etapa1,
            'reprovar_form': ReprovarRequisicaoForm(),
        },
    )


@login_required
@require_rh
def admissao_view(request):
    _sincronizar_notificacoes_rh()
    sincronizar_obras_gestao()
    admissoes_qs = _admissao_queryset(request.user)
    selecionado_id = request.GET.get('id')
    selecionado = admissoes_qs.filter(pk=selecionado_id).first() if selecionado_id else None
    if selecionado is None:
        selecionado = admissoes_qs.first()

    page_number = request.GET.get('page', 1)
    if selecionado and 'page' not in request.GET:
        ids = list(admissoes_qs.values_list('pk', flat=True))
        if selecionado.pk in ids:
            page_number = ids.index(selecionado.pk) // 10 + 1

    paginator = Paginator(admissoes_qs, 10)
    adm_page_obj = paginator.get_page(page_number)

    if selecionado and selecionado.etapa_admissao == 1:
        garantir_requisicao_criada_por(selecionado)
    elif selecionado and selecionado.etapa_admissao >= 2:
        instanciar_documentos(selecionado)
    historico = listar_historico_colaborador(selecionado) if selecionado else []
    admissao_ctx = (
        montar_contexto_admissao(selecionado, historico, user=request.user)
        if selecionado else None
    )
    devolver_form = DevolverAdmissaoForm()

    requisicao_edicao = None
    editar_id = request.GET.get('editar')
    if selecionado and selecionado.etapa_admissao == 1 and selecionado.requisicao_reprovada:
        if editar_id is None or str(selecionado.pk) == str(editar_id):
            requisicao_edicao = _requisicao_edicao_payload(selecionado)

    etapa_exibida = None
    somente_leitura = False
    pendencia_documentos = (
        colaborador_tem_pendencia_documentos(selecionado) if selecionado else False
    )
    etapa_fluxo = (
        etapa_fluxo_efetiva(selecionado) if selecionado else None
    )
    admissoes_status = {
        adm.pk: colaborador_admissao_concluida(adm)
        for adm in adm_page_obj
    }
    for adm in adm_page_obj:
        adm.admissao_concluida_flag = admissoes_status.get(adm.pk, False)
        adm.admissao_pendencia_flag = (
            adm.etapa_admissao >= 5
            and adm.status == Colaborador.Status.ATIVO
            and not adm.admissao_concluida_flag
            and colaborador_tem_pendencia_documentos(adm)
        )
    if selecionado and admissao_ctx:
        etapa_atual = selecionado.etapa_admissao
        ver_etapa_raw = request.GET.get('ver_etapa')
        if ver_etapa_raw:
            try:
                ver_etapa = int(ver_etapa_raw)
            except (TypeError, ValueError):
                ver_etapa = etapa_atual
            if 1 <= ver_etapa <= etapa_atual:
                etapa_exibida = ver_etapa
        if etapa_exibida is None:
            if pendencia_documentos:
                etapa_exibida = etapa_fluxo
            else:
                etapa_exibida = etapa_atual
        somente_leitura = etapa_exibida < etapa_atual
        if pendencia_documentos and etapa_exibida == etapa_fluxo:
            somente_leitura = False

    etapas_labels = [
        (1, 'Requisição'),
        (2, 'Coleta de Docs'),
        (3, 'Aprovação RH'),
        (4, 'Ass. Contrato'),
        (5, 'Ativo'),
    ]
    etapas_stepper = []
    if selecionado:
        for num, label in etapas_labels:
            concluida = admissao_etapa_concluida(selecionado, num)
            etapas_stepper.append({
                'num': num,
                'label': label,
                'concluida': concluida,
                'acessivel': num <= selecionado.etapa_admissao,
                'atual': num == etapa_fluxo and pendencia_documentos,
                'visualizando': etapa_exibida == num,
            })

    ctx = {
        'admissoes': adm_page_obj,
        'adm_page_obj': adm_page_obj,
        'selecionado': selecionado,
        'historico': historico,
        'admissao_ctx': admissao_ctx,
        'etapa_exibida': etapa_exibida,
        'somente_leitura': somente_leitura,
        'devolver_form': devolver_form,
        'rh_requisicao_edicao': requisicao_edicao,
        'etapas': etapas_labels,
        'etapas_stepper': etapas_stepper,
        'admissao_concluida': (
            colaborador_admissao_concluida(selecionado) if selecionado else False
        ),
        'pendencia_documentos': pendencia_documentos,
        'etapa_fluxo': etapa_fluxo,
        'admissoes_status': admissoes_status,
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
                colab = criar_requisicao(form, request.user)
                CargoCatalogo.objects.get_or_create(
                    nome=form.cleaned_data['cargo'].strip(),
                )
                request.session.pop('rh_requisicao_draft', None)
                messages.success(request, f'Requisição criada para {colab.nome}.')
                return _redirect_admissao(colab.pk)
            except Exception as exc:
                _salvar_rascunho_requisicao(request, exc_msg=exc)
                messages.error(request, f'Não foi possível criar a requisição: {exc}')
        else:
            _salvar_rascunho_requisicao(request, form=form)
            for field, errs in form.errors.items():
                for err in errs:
                    label = form.fields[field].label if field in form.fields else field
                    messages.error(request, f'{label}: {err}')
        next_url = request.POST.get('next') or reverse('recursos_humanos:admissao')
        sep = '&' if '?' in next_url else '?'
        return redirect(f'{next_url}{sep}nova=1')
    return redirect('recursos_humanos:admissao')


@login_required
@require_rh
def admissao_atualizar_requisicao_view(request, pk):
    sincronizar_obras_gestao()
    colaborador = get_object_or_404(Colaborador, pk=pk, status=Colaborador.Status.EM_ADMISSAO)
    if request.method != 'POST':
        return _redirect_admissao(colaborador.pk)
    form = NovaRequisicaoForm(request.POST, colaborador_pk=colaborador.pk)
    if form.is_valid():
        try:
            atualizar_requisicao(colaborador, form.cleaned_data, request.user)
            CargoCatalogo.objects.get_or_create(
                nome=form.cleaned_data['cargo'].strip(),
            )
            request.session.pop('rh_requisicao_draft', None)
            messages.success(request, f'Requisição de {colaborador.nome} corrigida e reenviada ao gestor.')
            return _redirect_admissao(colaborador.pk)
        except Exception as exc:
            _salvar_rascunho_requisicao(request, exc_msg=exc)
            messages.error(request, f'Não foi possível atualizar a requisição: {exc}')
    else:
        _salvar_rascunho_requisicao(request, form=form)
        for field, errs in form.errors.items():
            for err in errs:
                label = form.fields[field].label if field in form.fields else field
                messages.error(request, f'{label}: {err}')
    next_url = request.POST.get('next') or reverse('recursos_humanos:admissao')
    sep = '&' if '?' in next_url else '?'
    return redirect(f'{next_url}{sep}nova=1&editar={colaborador.pk}')


@login_required
@require_rh
def admissao_acao_view(request, pk):
    if request.method != 'POST':
        return redirect('recursos_humanos:admissao')
    colaborador = get_object_or_404(_admissao_queryset(request.user), pk=pk)
    if colaborador_admissao_concluida(colaborador):
        messages.error(request, 'Admissão já concluída — somente consulta.')
        return _redirect_admissao(colaborador.pk)
    if colaborador.status != Colaborador.Status.EM_ADMISSAO:
        messages.error(request, 'Colaborador não está em admissão.')
        return _redirect_admissao(colaborador.pk)
    acao = request.POST.get('acao')

    if acao == 'aprovar_requisicao':
        ok, msg = aprovar_requisicao_gestor(colaborador, request.user)
    elif acao == 'reprovar_requisicao':
        form = ReprovarRequisicaoForm(request.POST)
        if form.is_valid():
            ok, msg = reprovar_requisicao_gestor(colaborador, form.cleaned_data['motivo'], request.user)
        else:
            ok, msg = False, 'Informe o motivo da reprovação.'
    elif acao == 'avancar':
        ok, msg = avancar_etapa_admissao(colaborador, request.user)
    elif acao == 'aprovar':
        ok, msg = aprovar_documentacao(colaborador, request.user)
    elif acao == 'devolver':
        form = DevolverAdmissaoForm(request.POST)
        if form.is_valid():
            ok, msg = devolver_admissao(colaborador, form.cleaned_data['motivo'], request.user)
        else:
            ok, msg = False, 'Informe o motivo da devolução.'
    elif acao == 'concluir':
        ok, msg = concluir_admissao(colaborador, request.user)
    elif acao == 'enviar_lembrete':
        ok, msg = enviar_lembrete_coleta_documentos(colaborador, request.user)
    else:
        ok, msg = False, 'Ação inválida.'

    (messages.success if ok else messages.error)(request, msg)
    if ok and acao == 'concluir':
        return redirect_para_colaborador(colaborador.pk)
    return _redirect_admissao(colaborador.pk)


@login_required
@require_rh
def documento_status_view(request, pk):
    if request.method != 'POST':
        return redirect('recursos_humanos:colaboradores')
    doc = get_object_or_404(DocumentoColaborador.objects.select_related('colaborador'), pk=pk)
    form = DocumentoStatusForm(request.POST)
    if form.is_valid():
        status_label = dict(DocumentoColaborador.Status.choices).get(
            form.cleaned_data['status'],
            form.cleaned_data['status'],
        )
        atualizar_status_documento(
            doc,
            form.cleaned_data['status'],
            form.cleaned_data.get('observacao', ''),
            request.user,
        )
        messages.success(
            request,
            f'Status do documento atualizado para "{status_label}".',
        )
    else:
        messages.error(request, 'Status inválido.')
    next_url = request.POST.get('next') or url_colaboradores_com_modal(doc.colaborador_id)
    return HttpResponseRedirect(next_url)


@login_required
@require_rh
def documento_aprovar_view(request, pk):
    if request.method != 'POST':
        return redirect('recursos_humanos:colaboradores')
    doc = get_object_or_404(DocumentoColaborador.objects.select_related('colaborador', 'tipo'), pk=pk)
    next_url = request.POST.get('next') or (
        f'{reverse("recursos_humanos:admissao")}?id={doc.colaborador_id}&ver_etapa=2'
    )

    data_emissao = None
    raw_emissao = (request.POST.get('data_emissao') or '').strip()
    if raw_emissao:
        from django.forms import DateField
        data_emissao = DateField().to_python(raw_emissao)
        if data_emissao is None:
            messages.error(request, 'Data de emissão inválida.')
            return HttpResponseRedirect(next_url)

    if doc.tipo.tem_validade and not data_emissao:
        messages.error(
            request,
            f'Informe a data de emissão do documento "{doc.tipo.nome}" '
            f'— necessária para calcular o vencimento.',
        )
        return HttpResponseRedirect(next_url)

    ok, msg = aprovar_documento_arquivo(doc, request.user, data_emissao)
    if ok:
        messages.success(request, msg)
    else:
        messages.error(request, msg)
    return HttpResponseRedirect(next_url)


@login_required
@require_rh
def documento_rejeitar_view(request, pk):
    if request.method != 'POST':
        return redirect('recursos_humanos:colaboradores')
    doc = get_object_or_404(DocumentoColaborador.objects.select_related('colaborador', 'tipo'), pk=pk)
    form = DocumentoRejeitarForm(request.POST)
    if form.is_valid():
        ok, msg = rejeitar_documento_arquivo(doc, form.cleaned_data['observacao'], request.user)
        if ok:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
    else:
        messages.error(request, 'Informe uma observação para o candidato.')
    next_url = request.POST.get('next') or f'{reverse("recursos_humanos:admissao")}?id={doc.colaborador_id}'
    return HttpResponseRedirect(next_url)


@login_required
@require_rh
def documento_upload_view(request, pk):
    if request.method != 'POST':
        return redirect('recursos_humanos:colaboradores')
    doc = get_object_or_404(
        DocumentoColaborador.objects.select_related('colaborador', 'tipo'),
        pk=pk,
    )
    next_url = request.POST.get('next') or url_colaboradores_com_modal(doc.colaborador_id)
    form = DocumentoUploadForm(request.POST, request.FILES)
    if form.is_valid():
        arquivo = form.cleaned_data['arquivo']
        data_emissao = form.cleaned_data.get('data_emissao')

        if doc.tipo.tem_validade and not data_emissao:
            messages.error(
                request,
                f'Informe a data de emissão do documento "{doc.tipo.nome}" '
                f'— necessária para calcular o vencimento.',
            )
            return HttpResponseRedirect(next_url)

        upload_documento_arquivo(doc, arquivo, request.user, data_emissao)

        msg = f'Arquivo "{arquivo.name}" enviado com sucesso.'
        if data_emissao and doc.vencimento:
            msg += f' Vencimento calculado: {doc.vencimento.strftime("%d/%m/%Y")}.'
        messages.success(request, msg)
    else:
        messages.error(request, 'Selecione um arquivo válido (máx. 10 MB).')
    return HttpResponseRedirect(next_url)


@login_required
@require_rh
def alertas_view(request):
    _sincronizar_notificacoes_rh()
    from .services.alertas_config import (
        config_para_template,
        obter_configuracao_alertas,
        rotulo_usuario_alertas,
        usuarios_staff_alertas,
    )
    from .services.alertas_email import enviar_emails_alertas_diarios

    alertas = gerar_alertas()
    enviar_emails_alertas_diarios(alertas)
    config = obter_configuracao_alertas()
    usuarios_alertas = [
        {'id': u.pk, 'rotulo': rotulo_usuario_alertas(u)}
        for u in usuarios_staff_alertas()
    ]
    return render(request, 'recursos_humanos/alertas.html', {
        'alertas': alertas,
        'resumo': resumo_alertas(alertas, config),
        'config_alertas': config_para_template(config),
        'usuarios_alertas': usuarios_alertas,
        **_rh_nav_context(request),
    })


@login_required
@require_rh
def alertas_configurar_view(request):
    from .forms import ConfigurarAlertasForm
    from .services.alertas_config import salvar_configuracao_alertas

    if request.method != 'POST':
        return redirect('recursos_humanos:alertas')

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    form = ConfigurarAlertasForm(request.POST)
    if form.is_valid():
        salvar_configuracao_alertas(form.cleaned_data)
        if is_ajax:
            return JsonResponse({'ok': True})
        messages.success(request, 'Configurações de alertas salvas.')
        return redirect('recursos_humanos:alertas')

    if is_ajax:
        return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
    messages.error(request, 'Verifique os valores informados.')
    return redirect('recursos_humanos:alertas')


@login_required
@require_rh
def enviar_alertas_whatsapp_view(request):
    """POST: envia resumo de alertas para um número informado."""
    if request.method != 'POST':
        return redirect('recursos_humanos:alertas')

    telefone = request.POST.get('telefone', '').strip()
    if not telefone:
        messages.error(request, 'Informe o telefone.')
        return redirect('recursos_humanos:alertas')

    from .services.notificacoes import enviar_resumo_alertas_whatsapp

    resultado = enviar_resumo_alertas_whatsapp(telefone)

    if resultado['enviado']:
        messages.success(
            request,
            f'Resumo enviado para {telefone}. '
            f'{resultado["alertas"]} alerta(s) crítico(s).',
        )
    else:
        messages.error(
            request,
            'Erro ao enviar. Verifique o número e tente novamente.',
        )
    return redirect('recursos_humanos:alertas')


@login_required
@require_rh
def documentos_config_view(request):
    if request.method == 'POST':
        acao = request.POST.get('acao')
        if acao == 'criar':
            form = TipoDocumentoForm(request.POST)
            if form.is_valid():
                form.save()
                novos = sincronizar_documentos_em_andamento()
                msg = 'Tipo de documento criado.'
                if novos:
                    msg += f' {novos} documento(s) adicionado(s) em admissões em andamento.'
                messages.success(request, msg)
            else:
                messages.error(request, 'Verifique os campos do novo tipo.')
        elif acao == 'editar':
            tipo = get_object_or_404(TipoDocumento, pk=request.POST.get('tipo_id'))
            form = TipoDocumentoForm(request.POST, instance=tipo)
            if form.is_valid():
                form.save()
                novos = sincronizar_documentos_em_andamento()
                msg = 'Tipo de documento atualizado.'
                if novos:
                    msg += f' {novos} documento(s) adicionado(s) em admissões em andamento.'
                messages.success(request, msg)
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

    tipos = TipoDocumento.objects.prefetch_related('cargos_aplicaveis', 'obras_aplicaveis').all()
    tipos_forms = [(t, TipoDocumentoForm(instance=t)) for t in tipos]
    return render(request, 'recursos_humanos/documentos_config.html', {
        'tipos_forms': tipos_forms,
        'form_novo': TipoDocumentoForm(),
        **_rh_nav_context(request),
    })


@login_required
@require_rh
def colaborador_excluir_view(request, pk):
    colaborador = get_object_or_404(Colaborador, pk=pk)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if colaborador.status == Colaborador.Status.ATIVO:
        msg = (
            'Não é possível excluir colaborador ativo. '
            'Faça o desligamento primeiro.'
        )
        if is_ajax:
            return JsonResponse({'ok': False, 'error': msg}, status=400)
        messages.error(request, msg)
        return redirect_para_colaborador(pk)
    if request.method == 'POST':
        colab_id = colaborador.pk
        nome = colaborador.nome
        colaborador.delete()
        if is_ajax:
            return JsonResponse({'ok': True, 'id': colab_id, 'nome': nome})
        messages.success(request, f'Colaborador {nome} excluído.')
        return redirect('recursos_humanos:colaboradores_list')
    return render(
        request,
        'recursos_humanos/colaborador_confirmar_exclusao.html',
        {'colaborador': colaborador, **_rh_nav_context(request)},
    )


@login_required
@require_rh
def colaborador_desligar_view(request, pk):
    colaborador = get_object_or_404(Colaborador, pk=pk, status=Colaborador.Status.ATIVO)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method == 'POST':
        motivo = request.POST.get('motivo', '').strip()
        data_desligamento_raw = request.POST.get('data_desligamento', '').strip()
        from .services.admissao_actions import desligar_colaborador

        if not data_desligamento_raw:
            msg = 'Informe a data de desligamento.'
            ok = False
            data_parsed = None
        else:
            data_parsed = parse_date(data_desligamento_raw)
            if data_parsed is None:
                msg = 'Data de desligamento inválida.'
                ok = False
            else:
                ok, msg = desligar_colaborador(
                    colaborador,
                    motivo,
                    data_parsed,
                    request.user,
                )

        if not ok:
            if is_ajax:
                return JsonResponse({'ok': False, 'errors': [msg]}, status=400)
            messages.error(request, msg)
            return render(
                request,
                'recursos_humanos/colaborador_desligar.html',
                {
                    'colaborador': colaborador,
                    'motivo': motivo,
                    'data_desligamento': data_desligamento_raw,
                    **_rh_nav_context(request),
                },
            )

        if is_ajax:
            return JsonResponse({
                'ok': True,
                'status': colaborador.status,
                'status_display': colaborador.get_status_display(),
            })
        messages.success(request, f'{colaborador.nome} desligado com sucesso.')
        return redirect_para_colaborador(pk)
    return render(
        request,
        'recursos_humanos/colaborador_desligar.html',
        {'colaborador': colaborador, **_rh_nav_context(request)},
    )


@login_required
@require_rh
def cargo_catalogo_create_view(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    nome = (request.POST.get('nome') or '').strip()
    if len(nome) < 2:
        return JsonResponse({'ok': False, 'error': 'Informe o nome do cargo.'}, status=400)
    obj, created = CargoCatalogo.objects.get_or_create(nome=nome)
    return JsonResponse({'ok': True, 'id': obj.pk, 'nome': obj.nome, 'created': created})


@login_required
@require_rh
def cargo_rh_quick_create_view(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    nome = (request.POST.get('nome') or '').strip()
    if len(nome) < 2:
        return JsonResponse({'ok': False, 'error': 'Informe o nome do cargo (RH).'}, status=400)
    form = CargoRHForm({'nome': nome})
    if form.is_valid():
        cargo = form.save()
        return JsonResponse({'ok': True, 'id': cargo.pk, 'nome': cargo.nome, 'created': True})
    msgs = []
    for errs in form.errors.values():
        msgs.extend(errs)
    return JsonResponse({'ok': False, 'errors': msgs}, status=400)


@login_required
@require_rh
def cargos_view(request):
    if request.method == 'POST':
        form = CargoRHForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cargo cadastrado.')
        else:
            messages.error(request, 'Verifique o nome do cargo.')
        return redirect('recursos_humanos:cargos')

    return render(request, 'recursos_humanos/cargos.html', {
        'cargos': CargoRH.objects.all(),
        'form_cargo': CargoRHForm(),
        **_rh_nav_context(request),
    })


@login_required
@require_rh
def cargo_excluir_view(request, pk):
    if request.method != 'POST':
        return redirect('recursos_humanos:cargos')
    cargo = get_object_or_404(CargoRH, pk=pk)
    if cargo.colaboradores.exists() or cargo.tipos_documento.exists():
        messages.error(request, 'Não é possível excluir: cargo em uso por colaboradores ou tipos de documento.')
    else:
        nome = cargo.nome
        cargo.delete()
        messages.success(request, f'Cargo «{nome}» excluído.')
    return redirect('recursos_humanos:cargos')


def _meta_arquivo_portal(doc, token):
    if not doc.arquivo:
        return None
    nome = doc.arquivo.name.rsplit('/', 1)[-1]
    partes = nome.rsplit('.', 1)
    ext = partes[-1].lower() if len(partes) > 1 else ''
    icones = {
        'pdf': 'fa-file-pdf',
        'doc': 'fa-file-word',
        'docx': 'fa-file-word',
        'xls': 'fa-file-excel',
        'xlsx': 'fa-file-excel',
    }
    return {
        'nome': nome,
        'url': reverse('recursos_humanos:portal_arquivo', args=[token, doc.pk]),
        'is_image': ext in ('jpg', 'jpeg', 'png', 'webp', 'gif'),
        'is_pdf': ext == 'pdf',
        'icon': icones.get(ext, 'fa-file'),
    }


def portal_candidato_view(request, token):
    """Portal público — candidato vê e envia documentos. Não requer login."""
    colaborador = get_object_or_404(Colaborador, token_portal=token)

    if not colaborador.token_portal_valido():
        return render(
            request,
            'recursos_humanos/portal_expirado.html',
            {'colaborador': colaborador},
        )

    if not _portal_status_permitido(colaborador):
        return render(
            request,
            'recursos_humanos/portal_encerrado.html',
            {'colaborador': colaborador},
        )

    portal_modo_reenvio = colaborador.status == Colaborador.Status.ATIVO

    instanciar_documentos(colaborador)

    dados_form = PortalCandidatoDadosForm(instance=colaborador)
    if request.method == 'POST' and request.POST.get('acao') == 'salvar_dados':
        dados_form = PortalCandidatoDadosForm(request.POST, instance=colaborador)
        if dados_form.is_valid():
            salvar_dados_portal_candidato(colaborador, dados_form.cleaned_data)
            messages.success(request, 'Seus dados foram salvos com sucesso!')
            return redirect('recursos_humanos:portal', token=token)
        messages.error(request, 'Verifique os campos destacados e tente novamente.')

    documentos = list(
        colaborador.documentos.select_related('tipo').order_by('tipo__ordem', 'tipo__nome')
    )
    for doc in documentos:
        doc.portal_arquivo = _meta_arquivo_portal(doc, token)
    total = len(documentos)
    recebidos = sum(1 for d in documentos if d.status == DocumentoColaborador.Status.RECEBIDO)
    progresso = int(recebidos / total * 100) if total else 0

    return render(
        request,
        'recursos_humanos/portal_candidato.html',
        {
            'colaborador': colaborador,
            'documentos': documentos,
            'dados_form': dados_form,
            'dados_completos': dados_portal_completos(colaborador),
            'token': token,
            'total_docs': total,
            'recebidos_docs': recebidos,
            'progresso_pct': progresso,
            'portal_modo_reenvio': portal_modo_reenvio,
        },
    )


def portal_upload_view(request, token, doc_pk):
    """Upload de documento pelo candidato."""
    colaborador = get_object_or_404(Colaborador, token_portal=token)

    if not colaborador.token_portal_valido():
        return redirect('recursos_humanos:portal', token=token)
    if not _portal_status_permitido(colaborador):
        return redirect('recursos_humanos:portal', token=token)

    doc = get_object_or_404(
        DocumentoColaborador,
        pk=doc_pk,
        colaborador=colaborador,
    )

    if request.method == 'POST':
        form = DocumentoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload_documento_arquivo(doc, form.cleaned_data['arquivo'], 'Candidato (portal)')
            messages.success(request, f'"{doc.tipo.nome}" enviado! Aguarde a aprovação do gestor.')
        else:
            messages.error(request, 'Arquivo inválido. Máx. 10 MB.')

    return redirect('recursos_humanos:portal', token=token)


def portal_arquivo_view(request, token, doc_pk):
    """Visualização do arquivo enviado pelo candidato (portal público com token)."""
    from django.http import FileResponse, Http404

    colaborador = get_object_or_404(Colaborador, token_portal=token)
    if not colaborador.token_portal_valido():
        return redirect('recursos_humanos:portal', token=token)
    if not _portal_status_permitido(colaborador):
        raise Http404

    doc = get_object_or_404(
        DocumentoColaborador,
        pk=doc_pk,
        colaborador=colaborador,
    )
    if not doc.arquivo:
        raise Http404

    nome = doc.arquivo.name.rsplit('/', 1)[-1]
    return FileResponse(doc.arquivo.open('rb'), as_attachment=False, filename=nome)


def portal_remover_view(request, token, doc_pk):
    """Remove arquivo enviado pelo candidato (portal público com token)."""
    colaborador = get_object_or_404(Colaborador, token_portal=token)

    if not colaborador.token_portal_valido():
        return redirect('recursos_humanos:portal', token=token)
    if not _portal_status_permitido(colaborador):
        return redirect('recursos_humanos:portal', token=token)

    doc = get_object_or_404(
        DocumentoColaborador,
        pk=doc_pk,
        colaborador=colaborador,
    )

    if request.method == 'POST' and doc.arquivo:
        remover_documento_arquivo(doc, 'Candidato (portal)')
        messages.success(request, f'"{doc.tipo.nome}" removido. Você pode enviar outro arquivo.')

    return redirect('recursos_humanos:portal', token=token)


@login_required
@require_rh
def contrato_gerar_view(request, pk):
    """Gera PDF do contrato para download e envio manual ao ZapSign."""
    from io import BytesIO

    from django.http import FileResponse

    from .services.contrato import obter_ou_criar_contrato, salvar_rascunho_contrato

    colaborador = get_object_or_404(Colaborador, pk=pk, etapa_admissao=4)
    contrato = obter_ou_criar_contrato(colaborador)
    pdf_bytes = salvar_rascunho_contrato(contrato, colaborador)

    registrar_historico(
        colaborador,
        4,
        'PDF do contrato gerado para assinatura no ZapSign.',
        request.user.get_full_name() or request.user.username,
    )

    cpf_limpo = (colaborador.cpf or '').replace('.', '').replace('-', '')
    nome = f'contrato_rascunho_{cpf_limpo}.pdf'
    return FileResponse(
        BytesIO(pdf_bytes),
        as_attachment=True,
        filename=nome,
        content_type='application/pdf',
    )


@login_required
@require_rh
def contrato_upload_view(request, pk):
    """Upload do PDF assinado vindo do ZapSign."""
    if request.method != 'POST':
        return redirect('recursos_humanos:admissao')

    colaborador = get_object_or_404(Colaborador, pk=pk, etapa_admissao=4)
    arquivo = request.FILES.get('pdf_assinado')
    if not arquivo:
        messages.error(request, 'Selecione o PDF assinado.')
        return _redirect_admissao(pk)
    if not arquivo.name.lower().endswith('.pdf'):
        messages.error(request, 'Envie um arquivo PDF.')
        return _redirect_admissao(pk)

    from .services.contrato import obter_ou_criar_contrato, salvar_contrato_assinado

    contrato = obter_ou_criar_contrato(colaborador)
    if salvar_contrato_assinado(contrato, arquivo, request.user):
        messages.success(request, 'Contrato assinado arquivado. Colaborador ativado.')
        return redirect_para_colaborador(colaborador.pk)

    messages.error(request, 'Não foi possível salvar o contrato.')
    return _redirect_admissao(pk)


@login_required
@require_rh
def contrato_download_view(request, pk):
    """Download do PDF do contrato gerado."""
    from django.http import FileResponse, Http404

    colaborador = get_object_or_404(Colaborador, pk=pk)
    try:
        contrato = colaborador.contrato_admissao
    except Exception:
        raise Http404('Contrato não encontrado.')
    if not contrato or not contrato.pdf_contrato:
        raise Http404('PDF do contrato indisponível.')
    nome = contrato.pdf_contrato.name.rsplit('/', 1)[-1]
    return FileResponse(contrato.pdf_contrato.open('rb'), as_attachment=True, filename=nome)


def _prazo_contrato_decisao_queryset(pk):
    return get_object_or_404(
        PrazoContrato.objects.select_related('colaborador'),
        pk=pk,
        status__in=(
            PrazoContrato.Status.ATIVO,
            PrazoContrato.Status.CONVERTIDO,
        ),
    )


def _serializar_prazo_decisao_response(prazo):
    from .services.prazo_contrato import serializar_prazo_decisao

    return serializar_prazo_decisao(
        prazo,
        post_url=reverse('recursos_humanos:prazo_contrato_decisao', kwargs={'pk': prazo.pk}),
        perfil_url=url_colaboradores_com_modal(prazo.colaborador.pk),
    )


@login_required
@require_rh
def prazo_contrato_decisao_json_view(request, pk):
    """Dados do prazo para o modal de decisão."""
    prazo = _prazo_contrato_decisao_queryset(pk)
    return JsonResponse(_serializar_prazo_decisao_response(prazo))


@login_required
@require_rh
def prazo_contrato_decisao_view(request, pk):
    """POST: executa a ação escolhida. GET redireciona para abrir o modal."""
    from datetime import datetime

    from .services.prazo_contrato import executar_acao_prazo

    prazo = _prazo_contrato_decisao_queryset(pk)
    ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        acao = request.POST.get('acao')
        nova_data_str = request.POST.get('nova_data_fim', '')
        motivo = request.POST.get('motivo', '')

        nova_data_fim = None
        if nova_data_str:
            try:
                nova_data_fim = datetime.strptime(nova_data_str, '%Y-%m-%d').date()
            except ValueError:
                if ajax:
                    return JsonResponse({'ok': False, 'message': 'Data de fim inválida.'}, status=400)
                messages.error(request, 'Data de fim inválida.')
                return _redirect_abrir_prazo_decisao(request, pk)

        sucesso, msg = executar_acao_prazo(
            prazo,
            acao,
            request.user,
            nova_data_fim,
            motivo,
        )

        if ajax:
            if sucesso:
                return JsonResponse({
                    'ok': True,
                    'message': msg,
                    'colaborador_id': prazo.colaborador.pk,
                })
            return JsonResponse({'ok': False, 'message': msg}, status=400)

        if sucesso:
            messages.success(request, msg)
        else:
            messages.error(request, msg)

        return redirect_para_colaborador(prazo.colaborador.pk)

    return _redirect_abrir_prazo_decisao(request, pk)


def _redirect_abrir_prazo_decisao(request, pk):
    """Redireciona para a página de origem (ou alertas) com query para abrir o modal."""
    from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

    referer = request.META.get('HTTP_REFERER', '')
    parsed = urlparse(referer)
    if not referer or '/prazo-contrato/' in referer or not parsed.path.startswith('/'):
        target = reverse('recursos_humanos:alertas')
        sep = '?'
        return redirect(f'{target}{sep}{urlencode({"abrir_prazo_decisao": pk})}')

    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs['abrir_prazo_decisao'] = [str(pk)]
    new_query = urlencode(qs, doseq=True)
    return redirect(urlunparse(parsed._replace(query=new_query)))


@login_required
@require_rh
def prazo_contrato_reativar_view(request, pk):
    """Reativa contrato encerrado e colaborador desligado pelo encerramento."""
    from .services.prazo_contrato import reativar_prazo_contrato

    prazo = get_object_or_404(
        PrazoContrato.objects.select_related('colaborador'),
        pk=pk,
        status=PrazoContrato.Status.ENCERRADO,
    )
    ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method != 'POST':
        if ajax:
            return JsonResponse({'ok': False, 'message': 'Método não permitido.'}, status=405)
        return redirect_para_colaborador(prazo.colaborador.pk)

    sucesso, msg = reativar_prazo_contrato(prazo, request.user)
    if ajax:
        if sucesso:
            return JsonResponse({
                'ok': True,
                'message': msg,
                'colaborador_id': prazo.colaborador.pk,
            })
        return JsonResponse({'ok': False, 'message': msg}, status=400)

    if sucesso:
        messages.success(request, msg)
    else:
        messages.error(request, msg)
    return redirect_para_colaborador(prazo.colaborador.pk)


@login_required
@require_rh
def prazo_contrato_criar_view(request, pk):
    """Cria um novo PrazoContrato para um colaborador."""
    from datetime import datetime

    from .services.prazo_contrato import criar_prazo_contrato

    colaborador = get_object_or_404(Colaborador, pk=pk)

    if request.method != 'POST':
        return redirect_para_colaborador(pk)

    if colaborador.prazos_contrato.filter(status=PrazoContrato.Status.ATIVO).exists():
        messages.error(request, 'Já existe um prazo de contrato ativo para este colaborador.')
        return redirect_para_colaborador(pk)

    tipo = request.POST.get('tipo')
    data_inicio_str = request.POST.get('data_inicio')
    data_fim_str = request.POST.get('data_fim')

    tipos_validos = {c[0] for c in PrazoContrato.Tipo.choices}
    if tipo not in tipos_validos:
        messages.error(request, 'Tipo de prazo inválido.')
        return redirect_para_colaborador(pk)

    try:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        messages.error(request, 'Datas inválidas.')
        return redirect_para_colaborador(pk)

    if data_fim <= data_inicio:
        messages.error(request, 'A data de fim deve ser posterior à data de início.')
        return redirect_para_colaborador(pk)

    criar_prazo_contrato(colaborador, tipo, data_inicio, data_fim)
    messages.success(request, 'Prazo de contrato registrado.')
    return redirect_para_colaborador(pk)
