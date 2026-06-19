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
    ESCOLARIDADE_CHOICES,
    NovaRequisicaoForm,
    PortalCandidatoDadosForm,
    ReprovarRequisicaoForm,
    TipoDocumentoCatalogoForm,
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
from .services.papeis_fluxo import ETAPAS_FLUXO_LABELS
from .services.alertas_config import obter_configuracao_alertas
from recursos_humanos.services.documentos import (
    admissao_etapa_concluida,
    analisar_pendencias_coleta,
    colaborador_documentos_recebidos_validos,
    colaborador_tem_pendencia_documentos,
    coleta_documentos_iniciada,
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
    enviar_contrato,
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
    solicitar_pendencias_colaborador,
    solicitar_correcao_dados_portal,
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
        'rg': request.POST.get('rg', ''),
        'data_nascimento': request.POST.get('data_nascimento', ''),
        'pis': request.POST.get('pis', ''),
        'endereco': request.POST.get('endereco', ''),
        'dados_bancarios': request.POST.get('dados_bancarios', ''),
        'escolaridade': request.POST.get('escolaridade', ''),
        'tamanho_camisa': request.POST.get('tamanho_camisa', ''),
        'tamanho_bota': request.POST.get('tamanho_bota', ''),
        'empresa': request.POST.get('empresa', ''),
        'cargo': request.POST.get('cargo', ''),
        'cargo_rh': request.POST.get('cargo_rh', ''),
        'obra': request.POST.getlist('obra'),
        'aprovadores': request.POST.getlist('aprovadores'),
        'tipo_contrato': request.POST.get('tipo_contrato', 'CLT'),
        'salario': request.POST.get('salario', ''),
        'deslocamento_origem': request.POST.get('deslocamento_origem', ''),
        'deslocamento_destino': request.POST.get('deslocamento_destino', ''),
        'reembolsos_json': request.POST.get('reembolsos_json', '[]'),
        'data_inicio': request.POST.get('data_inicio', ''),
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
        'rh_escolaridade_choices': [c for c in ESCOLARIDADE_CHOICES if c[0]],
    }


def _enriquecer_colaborador(c):
    from .services.documentos import documento_conta_como_recebido
    from .services.lista_colaboradores import enriquecer_lista_colaborador
    from .services.status_colaborador import aplicar_status_exibicao

    docs = list(c.documentos.all())
    c.docs_recebidos = sum(1 for d in docs if documento_conta_como_recebido(d))
    c.docs_total = len(docs)
    aplicar_status_exibicao(c, docs_recebidos=c.docs_recebidos, docs_total=c.docs_total)
    enriquecer_lista_colaborador(
        c,
        docs=docs,
        recebidos=c.docs_recebidos,
        total=c.docs_total,
    )


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


def _portal_colaborador_from_token(request, token):
    from recursos_humanos.services.portal_token import colaborador_por_token_portal

    colaborador = colaborador_por_token_portal(token)
    if colaborador:
        return colaborador, None
    return None, render(request, 'recursos_humanos/portal_link_invalido.html')


def _portal_exigir_autenticacao(request, token, colaborador):
    from recursos_humanos.services.portal_auth import exigir_portal_autenticado

    return exigir_portal_autenticado(request, token, colaborador)


def _render_portal_acesso(request, colaborador, token, *, erro=''):
    from recursos_humanos.services.portal_auth import pin_bloqueado

    return render(
        request,
        'recursos_humanos/portal_acesso.html',
        {
            'colaborador': colaborador,
            'token': token,
            'erro_pin': erro,
            'pin_bloqueado': pin_bloqueado(request, token),
        },
    )


def _contexto_coleta_portal(colaborador, user):
    """Dados do portal e pendências de coleta para admissão / perfil."""
    from django.conf import settings

    from recursos_humanos.services.documentos import (
        analisar_pendencias_coleta,
        colaborador_tem_contato_portal,
        motivo_botao_pendencias_indisponivel,
        pode_solicitar_pendencias_coleta,
    )
    from recursos_humanos.services.portal_token import PORTAL_TOKEN_VALIDADE_DIAS

    from recursos_humanos.services.admissao_actions import contexto_dados_portal_rh
    from recursos_humanos.services.papeis_fluxo import usuario_pode_conferir_documentos

    pendencias = analisar_pendencias_coleta(colaborador)
    pode = pode_solicitar_pendencias_coleta(colaborador, user)
    dados_portal = contexto_dados_portal_rh(colaborador)
    pode_corrigir_dados = (
        dados_portal['tem_algum_preenchido']
        and colaborador_tem_contato_portal(colaborador)
        and usuario_pode_conferir_documentos(user, colaborador)
        and colaborador.status == Colaborador.Status.EM_ADMISSAO
        and colaborador.etapa_admissao >= 2
    )
    portal_url = None
    if colaborador.token_portal and colaborador.status == Colaborador.Status.EM_ADMISSAO:
        base = getattr(settings, 'SITE_URL', '').rstrip('/')
        portal_url = f'{base}/rh/portal/{colaborador.token_portal}/'
    return {
        'pendencias_coleta': pendencias,
        'pode_solicitar_pendencias': pode,
        'url_solicitar_pendencias': (
            reverse('recursos_humanos:colaborador_solicitar_pendencias', args=[colaborador.pk])
            if pode else None
        ),
        'portal_url': portal_url,
        'token_portal_valido': colaborador.token_portal_valido(),
        'portal_token_validade_dias': PORTAL_TOKEN_VALIDADE_DIAS,
        'tem_contato_portal': colaborador_tem_contato_portal(colaborador),
        'motivo_botao_pendencias_indisponivel': motivo_botao_pendencias_indisponivel(
            colaborador, user,
        ),
        'dados_portal': dados_portal,
        'pode_solicitar_correcao_dados': pode_corrigir_dados,
        'url_solicitar_correcao_dados': (
            reverse('recursos_humanos:colaborador_solicitar_correcao_dados', args=[colaborador.pk])
            if pode_corrigir_dados else None
        ),
    }


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
        Colaborador.objects.prefetch_related(
            'obras',
            'documentos__tipo',
            'prazos_contrato',
        )
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

    em_andamento = [c for c in page_obj if c.status == Colaborador.Status.EM_ADMISSAO]
    quadro = [c for c in page_obj if c.status != Colaborador.Status.EM_ADMISSAO]
    lista_dividida = status_filtro == 'todos' and bool(em_andamento) and bool(quadro)

    ctx = {
        'page_obj': page_obj,
        'colaboradores': page_obj,
        'colaboradores_em_andamento': em_andamento,
        'colaboradores_quadro': quadro,
        'lista_dividida': lista_dividida,
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
                from recursos_humanos.services.documentos import analisar_pendencias_coleta
                from recursos_humanos.services.portal_token import renovar_token_portal_colaborador
                from .services.notificacoes import enviar_whatsapp_portal_colaborador

                colaborador.telefone = telefone
                colaborador.save(update_fields=['telefone', 'atualizado_em'])
                renovar_token_portal_colaborador(colaborador, renovar_pin=False)
                sucesso = enviar_whatsapp_portal_colaborador(
                    colaborador,
                    modo='inicial',
                    pendencias_coleta=analisar_pendencias_coleta(colaborador),
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

    _enriquecer_colaborador(colaborador)

    portal_url = None
    if colaborador.status == Colaborador.Status.EM_ADMISSAO and colaborador.token_portal:
        base = getattr(settings, 'SITE_URL', '').rstrip('/')
        portal_url = f'{base}/rh/portal/{colaborador.token_portal}/'

    from recursos_humanos.services.reembolsos import reembolsos_para_contexto

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
        'reembolsos_ctx': reembolsos_para_contexto(colaborador),
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
        from recursos_humanos.services.papeis_fluxo import usuario_pode_conferir_documentos

        pode_aprovar = (
            bool(doc.arquivo)
            and doc.status == DocumentoColaborador.Status.PENDENTE
            and usuario_pode_conferir_documentos(request.user, colaborador)
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

    from .services.status_colaborador import serializar_status_colaborador
    from recursos_humanos.services.papeis_fluxo import usuario_pode_conferir_documentos

    status_info = serializar_status_colaborador(
        colaborador,
        docs_recebidos=colaborador_documentos_recebidos_validos(colaborador),
        docs_total=colaborador.documentos_total(),
    )

    pendencias_coleta = analisar_pendencias_coleta(colaborador)
    from recursos_humanos.services.documentos import pode_solicitar_pendencias_coleta

    pode_solicitar_pendencias = pode_solicitar_pendencias_coleta(colaborador, request.user)

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
        'status_display': status_info['status_display'],
        'status_hint': status_info['status_hint'],
        'status_tone': status_info['status_tone'],
        'data_admissao': colaborador.data_admissao.strftime('%Y-%m-%d') if colaborador.data_admissao else '',
        'data_admissao_fmt': colaborador.data_admissao.strftime('%d/%m/%Y') if colaborador.data_admissao else '',
        'tipo_contrato': colaborador.tipo_contrato,
        'salario': colaborador.salario,
        'deslocamento_origem': colaborador.deslocamento_origem,
        'deslocamento_destino': colaborador.deslocamento_destino,
        'observacoes_requisicao': colaborador.observacoes_requisicao,
        'obras': obras,
        'obras_ids': list(colaborador.obras.values_list('pk', flat=True)),
        'docs_recebidos': colaborador_documentos_recebidos_validos(colaborador),
        'docs_total': colaborador.documentos_total(),
        'pendencia_documentos': colaborador_tem_pendencia_documentos(colaborador),
        'pendencias_coleta': pendencias_coleta,
        'pode_solicitar_pendencias': pode_solicitar_pendencias,
        'url_solicitar_pendencias': reverse(
            'recursos_humanos:colaborador_solicitar_pendencias',
            args=[colaborador.pk],
        ) if pode_solicitar_pendencias else None,
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


@login_required
@require_rh
def colaborador_solicitar_pendencias_view(request, pk):
    if request.method != 'POST':
        return redirect_para_colaborador(pk)

    colaborador = get_object_or_404(Colaborador, pk=pk)
    ok, msg = solicitar_pendencias_colaborador(colaborador, request.user)
    if ok:
        messages.success(request, msg)
    else:
        messages.error(request, msg)
    next_url = request.POST.get('next')
    if next_url:
        return HttpResponseRedirect(next_url)
    return redirect_para_colaborador(pk)


@login_required
@require_rh
def colaborador_solicitar_correcao_dados_view(request, pk):
    if request.method != 'POST':
        return redirect_para_colaborador(pk)

    colaborador = get_object_or_404(Colaborador, pk=pk)
    motivo = (request.POST.get('motivo') or '').strip()
    ok, msg = solicitar_correcao_dados_portal(colaborador, request.user, motivo=motivo)
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
        'rg': colaborador.rg,
        'data_nascimento': colaborador.data_nascimento.isoformat() if colaborador.data_nascimento else '',
        'pis': colaborador.pis,
        'endereco': colaborador.endereco,
        'dados_bancarios': colaborador.dados_bancarios,
        'escolaridade': colaborador.escolaridade,
        'tamanho_camisa': colaborador.tamanho_camisa,
        'tamanho_bota': colaborador.tamanho_bota,
        'empresa': colaborador.empresa,
        'cargo': colaborador.cargo,
        'cargo_rh': colaborador.cargo_rh_id or '',
        'obra': list(colaborador.obras.values_list('pk', flat=True)),
        'aprovadores': list(colaborador.aprovadores_requisicao.values_list('pk', flat=True)),
        'tipo_contrato': colaborador.tipo_contrato,
        'salario': colaborador.salario,
        'deslocamento_origem': colaborador.deslocamento_origem,
        'deslocamento_destino': colaborador.deslocamento_destino,
        'reembolsos': colaborador.reembolsos or [],
        'data_inicio': colaborador.data_admissao.isoformat() if colaborador.data_admissao else '',
        'motivo': colaborador.motivo_admissao or 'Nova contratação',
        'observacoes': colaborador.observacoes_requisicao,
        'motivo_reprovacao': colaborador.requisicao_motivo_reprovacao,
    }


def _admissao_queryset(user=None):
    return queryset_fluxo_admissao(user)


@login_required
def gestor_aprovar_requisicao_view(request, pk):
    """Aprovação manual de requisição legada na etapa 1 (sem exigir perfil RH)."""
    colaborador = get_object_or_404(
        Colaborador.objects.select_related('gestor_aprovador_user').prefetch_related(
            'obras', 'aprovadores_requisicao',
        ),
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
            ok, msg = aprovar_requisicao_gestor(
                colaborador,
                request.user,
                signature_data=request.POST.get('signature_data', ''),
            )
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
        coleta_documentos_iniciada(selecionado)
        and colaborador_tem_pendencia_documentos(selecionado)
        if selecionado else False
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
            not adm.admissao_concluida_flag
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
            if pendencia_documentos and etapa_atual > 2:
                etapa_exibida = 2
            else:
                etapa_exibida = etapa_atual
        somente_leitura = etapa_exibida < etapa_atual
        if pendencia_documentos and etapa_exibida == 2 and etapa_atual > 2:
            somente_leitura = False

    etapas_labels = list(ETAPAS_FLUXO_LABELS)
    etapas_stepper = []
    if selecionado:
        for num, label in etapas_labels:
            concluida = admissao_etapa_concluida(selecionado, num)
            etapa_reg = selecionado.etapa_admissao
            etapas_stepper.append({
                'num': num,
                'label': label,
                'concluida': concluida,
                'acessivel': num <= etapa_reg,
                'etapa_registrada': num == etapa_reg,
                'visualizando': etapa_exibida == num,
                'reaberta_docs': num == 2 and pendencia_documentos and etapa_reg > 2,
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
    if selecionado and selecionado.etapa_admissao >= 2:
        ctx.update(_contexto_coleta_portal(selecionado, request.user))
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
                messages.success(
                    request,
                    f'Requisição criada para {colab.nome}. Coleta de documentos iniciada — link enviado ao candidato quando houver e-mail ou telefone.',
                )
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
            messages.success(request, f'Requisição de {colaborador.nome} corrigida. Coleta de documentos reiniciada.')
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
        ok, msg = aprovar_requisicao_gestor(
            colaborador,
            request.user,
            signature_data=request.POST.get('signature_data', ''),
        )
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
    elif acao == 'enviar_contrato':
        ok, msg = enviar_contrato(colaborador, request.user)
    elif acao == 'enviar_lembrete':
        ok, msg = enviar_lembrete_coleta_documentos(colaborador, request.user)
    else:
        ok, msg = False, 'Ação inválida.'

    (messages.success if ok else messages.error)(request, msg)
    if ok and acao in ('concluir',):
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
        try:
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
        except PermissionError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, 'Status inválido.')
    next_url = request.POST.get('next') or url_colaboradores_com_modal(doc.colaborador_id)
    return HttpResponseRedirect(next_url)


def _wants_json(request) -> bool:
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _responder_documento_acao(request, next_url, ok, msg, doc=None):
    if _wants_json(request):
        from recursos_humanos.services.documento_acao_api import resposta_json_documento

        status = 200 if ok else 400
        return JsonResponse(resposta_json_documento(ok, msg, doc, user=request.user), status=status)
    if ok:
        messages.success(request, msg)
    else:
        messages.error(request, msg)
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
            return _responder_documento_acao(
                request, next_url, False, 'Data de emissão inválida.',
            )

    if doc.tipo.tem_validade and not data_emissao:
        if doc.data_emissao:
            data_emissao = doc.data_emissao
        else:
            return _responder_documento_acao(
                request,
                next_url,
                False,
                f'"{doc.tipo.nome}" ainda não tem data de emissão. '
                f'Solicite reenvio ao candidato para que informe a data no portal.',
            )

    ok, msg = aprovar_documento_arquivo(doc, request.user, data_emissao)
    return _responder_documento_acao(request, next_url, ok, msg, doc if ok else None)


@login_required
@require_rh
def documento_rejeitar_view(request, pk):
    if request.method != 'POST':
        return redirect('recursos_humanos:colaboradores')
    doc = get_object_or_404(DocumentoColaborador.objects.select_related('colaborador', 'tipo'), pk=pk)
    next_url = request.POST.get('next') or f'{reverse("recursos_humanos:admissao")}?id={doc.colaborador_id}'
    form = DocumentoRejeitarForm(request.POST)
    if form.is_valid():
        ok, msg = rejeitar_documento_arquivo(doc, form.cleaned_data['observacao'], request.user)
        return _responder_documento_acao(request, next_url, ok, msg, doc if ok else None)
    return _responder_documento_acao(
        request, next_url, False, 'Informe uma observação para o candidato.',
    )


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
        from recursos_humanos.services.admissao_actions import _exigir_papel_conferencia_docs

        ok_papel, msg_papel = _exigir_papel_conferencia_docs(request.user, doc.colaborador)
        if not ok_papel:
            messages.error(request, msg_papel)
            return HttpResponseRedirect(next_url)

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
    from recursos_humanos.services.documentos_config import (
        garantir_cargos_rh_padrao,
        ids_docs_da_obra,
        ids_docs_do_cargo,
        montar_cards_tipos,
        montar_catalogo_documentos,
        montar_cargos_resumo,
        montar_obras_resumo,
        salvar_docs_da_obra,
        salvar_docs_do_cargo,
    )

    garantir_cargos_rh_padrao()

    if request.method == 'POST':
        acao = request.POST.get('acao')
        painel = request.POST.get('painel', 'todos')
        cargo_sel = request.POST.get('cargo_id', '')
        obra_sel = request.POST.get('obra_id', '')

        def _redirect_painel():
            url = reverse('recursos_humanos:documentos_config')
            params = [f'painel={painel}']
            if cargo_sel:
                params.append(f'cargo={cargo_sel}')
            if obra_sel:
                params.append(f'obra={obra_sel}')
            return redirect(f'{url}?{"&".join(params)}')

        if acao == 'criar':
            form = TipoDocumentoCatalogoForm(request.POST)
            if form.is_valid():
                tipo = form.save()
                if tipo.aplica_a == TipoDocumento.AplicaA.POR_CARGO:
                    cargo_ids = request.POST.getlist('cargos_aplicaveis')
                    cargo_ctx = request.POST.get('cargo_context')
                    if cargo_ctx and cargo_ctx not in cargo_ids:
                        cargo_ids.append(cargo_ctx)
                    if cargo_ids:
                        tipo.cargos_aplicaveis.set(
                            CargoRH.objects.filter(pk__in=cargo_ids),
                        )
                if tipo.aplica_a == TipoDocumento.AplicaA.POR_CARGO:
                    painel = 'cargo'
                    if tipo.cargos_aplicaveis.exists():
                        cargo_sel = str(tipo.cargos_aplicaveis.first().pk)
                novos = sincronizar_documentos_em_andamento()
                msg = 'Documento adicionado ao catálogo.'
                if novos:
                    msg += f' {novos} pendência(s) criada(s) em admissões em andamento.'
                messages.success(request, msg)
            else:
                messages.error(request, 'Verifique os campos do novo documento.')
        elif acao == 'editar':
            tipo = get_object_or_404(TipoDocumento, pk=request.POST.get('tipo_id'))
            form = TipoDocumentoCatalogoForm(request.POST, instance=tipo)
            if form.is_valid():
                form.save()
                novos = sincronizar_documentos_em_andamento()
                msg = 'Documento atualizado.'
                if novos:
                    msg += f' {novos} pendência(s) criada(s) em admissões em andamento.'
                messages.success(request, msg)
            else:
                messages.error(request, 'Verifique os campos.')
        elif acao == 'excluir':
            tipo = get_object_or_404(TipoDocumento, pk=request.POST.get('tipo_id'))
            if tipo.documentos_colaborador.exists():
                messages.error(request, 'Não é possível excluir: documento já usado em colaboradores.')
            else:
                tipo.delete()
                messages.success(request, 'Documento removido do catálogo.')
        elif acao == 'criar_cargo':
            form = CargoRHForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, f'Cargo «{form.cleaned_data["nome"]}» criado. Agora marque os documentos extras dele.')
                painel = 'cargo'
                cargo_sel = str(CargoRH.objects.order_by('-pk').values_list('pk', flat=True).first() or '')
            else:
                messages.error(request, 'Informe um nome válido para o cargo.')
                painel = 'cargo'
        elif acao == 'salvar_cargo':
            cargo_id = request.POST.get('cargo_id')
            if not cargo_id:
                messages.error(request, 'Selecione um cargo.')
            else:
                novos = salvar_docs_do_cargo(int(cargo_id), request.POST.getlist('tipo_cargo'))
                msg = 'Documentos do cargo salvos.'
                if novos:
                    msg += f' {novos} pendência(s) em admissões atualizadas.'
                messages.success(request, msg)
            painel = 'cargo'
            cargo_sel = cargo_id or cargo_sel
        elif acao == 'salvar_obra':
            obra_id = request.POST.get('obra_id')
            if not obra_id:
                messages.error(request, 'Selecione uma obra.')
            else:
                novos = salvar_docs_da_obra(int(obra_id), request.POST.getlist('tipo_obra'))
                msg = 'Documentos da obra salvos.'
                if novos:
                    msg += f' {novos} pendência(s) em admissões atualizadas.'
                messages.success(request, msg)
            painel = 'obra'
            obra_sel = obra_id or obra_sel
        return _redirect_painel()

    tipos = list(
        TipoDocumento.objects.prefetch_related('cargos_aplicaveis', 'obras_aplicaveis')
        .order_by('ordem', 'nome')
    )
    cards = montar_cards_tipos(tipos)
    cargos = montar_cargos_resumo(cards['por_cargo'])
    obras = montar_obras_resumo(cards['por_obra'])

    painel = request.GET.get('painel', 'todos')
    if painel == 'obra':
        painel = 'todos'
    if painel not in ('todos', 'cargo'):
        painel = 'todos'

    cargo_ativo = None
    cargo_id = request.GET.get('cargo')
    if cargo_id:
        cargo_ativo = CargoRH.objects.filter(pk=cargo_id).first()
    if not cargo_ativo and cargos:
        cargo_ativo = CargoRH.objects.filter(pk=cargos[0].pk).first()
        cargo_id = str(cargo_ativo.pk) if cargo_ativo else ''

    obra_ativa = None
    obra_id = request.GET.get('obra')
    if obra_id:
        obra_ativa = ObraLocal.objects.filter(pk=obra_id).first()
    if not obra_ativa and obras:
        obra_ativa = ObraLocal.objects.filter(pk=obras[0].pk).first()
        obra_id = str(obra_ativa.pk) if obra_ativa else ''

    docs_cargo_ativos = ids_docs_do_cargo(cargo_ativo, tipos) if cargo_ativo else set()
    docs_obra_ativos = ids_docs_da_obra(obra_ativa, tipos) if obra_ativa else set()

    tipos_forms_edit = {t.pk: TipoDocumentoCatalogoForm(instance=t) for t in tipos}

    return render(request, 'recursos_humanos/documentos_config.html', {
        'cards': cards,
        'catalogo_docs': montar_catalogo_documentos(cards),
        'cargos': cargos,
        'categorias': TipoDocumento.Categoria.choices,
        'obras': obras,
        'painel': painel,
        'cargo_ativo': cargo_ativo,
        'cargo_id': cargo_id,
        'obra_ativa': obra_ativa,
        'obra_id': obra_id,
        'docs_cargo_ativos': docs_cargo_ativos,
        'docs_obra_ativos': docs_obra_ativos,
        'form_novo': TipoDocumentoCatalogoForm(),
        'form_cargo': CargoRHForm(),
        'tipos_forms_edit': tipos_forms_edit,
        'stats': {
            'todos': len(cards['todos']),
            'cargo': len(cards['por_cargo']),
            'obra': len(cards['por_obra']),
            'cargos': len(cargos),
        },
        **_rh_nav_context(request),
    })


@login_required
@require_rh
def documentos_config_preview_view(request):
    from recursos_humanos.services.documentos_config import preview_kit_documentos

    cargo_id = request.GET.get('cargo')
    obra_id = request.GET.get('obra')
    data = preview_kit_documentos(
        cargo_id=int(cargo_id) if cargo_id else None,
        obra_id=int(obra_id) if obra_id else None,
    )
    return JsonResponse(data)


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
            colaborador.refresh_from_db()
            from .services.status_colaborador import serializar_status_colaborador

            return JsonResponse({
                'ok': True,
                **serializar_status_colaborador(colaborador),
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
    return redirect(reverse('recursos_humanos:documentos_config') + '?painel=cargo')


@login_required
@require_rh
def papeis_fluxo_view(request):
    from recursos_humanos.services.papeis_fluxo import (
        garantir_papeis_padrao,
        listar_papeis_configurados,
        meta_papel,
        papel_eh_automatico,
    )

    garantir_papeis_padrao()
    papeis = listar_papeis_configurados()

    if request.method == 'POST':
        from django.db import transaction

        from .forms import PapelFluxoAdmissaoForm

        forms_validos = []
        for papel in papeis:
            if papel_eh_automatico(papel.codigo):
                continue
            form = PapelFluxoAdmissaoForm(request.POST, instance=papel, prefix=papel.codigo)
            forms_validos.append(form)
        if all(f.is_valid() for f in forms_validos):
            with transaction.atomic():
                for form in forms_validos:
                    form.save()
            messages.success(request, 'Responsáveis do fluxo de admissão atualizados.')
        else:
            messages.error(request, 'Não foi possível salvar as configurações.')
        return redirect('recursos_humanos:papeis_fluxo')

    from .forms import PapelFluxoAdmissaoForm

    forms_papeis = []
    for papel in papeis:
        meta = meta_papel(papel.codigo)
        forms_papeis.append({
            'papel': papel,
            'form': None if meta.get('automatico') else PapelFluxoAdmissaoForm(
                instance=papel, prefix=papel.codigo,
            ),
            'meta': meta,
        })
    return render(request, 'recursos_humanos/papeis_fluxo.html', {
        **_rh_nav_context(request),
        'forms_papeis': forms_papeis,
    })


@login_required
@require_rh
def cargo_excluir_view(request, pk):
    if request.method != 'POST':
        return redirect(reverse('recursos_humanos:documentos_config') + '?painel=cargo')
    cargo = get_object_or_404(CargoRH, pk=pk)
    if cargo.colaboradores.exists() or cargo.tipos_documento.exists():
        messages.error(request, 'Não é possível excluir: cargo em uso por colaboradores ou documentos.')
    else:
        nome = cargo.nome
        cargo.delete()
        messages.success(request, f'Cargo «{nome}» excluído.')
    return redirect(reverse('recursos_humanos:documentos_config') + '?painel=cargo')


def _portal_sessao_upload_erros_key(token: str) -> str:
    return f'rh_portal_upload_erros_{token}'


def _portal_guardar_upload_erros_sessao(request, token: str, docs_erro_upload: set[int]) -> None:
    if docs_erro_upload:
        request.session[_portal_sessao_upload_erros_key(token)] = list(docs_erro_upload)


def _portal_pop_upload_erros_sessao(request, token: str) -> set[int]:
    key = _portal_sessao_upload_erros_key(token)
    raw = request.session.pop(key, None)
    if not raw:
        return set()
    return {int(pk) for pk in raw}


def _portal_documentos_enriquecidos(colaborador, token, *, docs_erro_upload=None):
    from recursos_humanos.services.documentos import (
        documento_permite_envio_portal,
        documentos_para_exibicao_portal,
    )

    erros = docs_erro_upload or set()
    documentos = documentos_para_exibicao_portal(colaborador)
    for doc in documentos:
        doc.portal_arquivo = _meta_arquivo_portal(doc, token)
        doc.portal_pode_enviar = documento_permite_envio_portal(doc, colaborador)
        doc.portal_upload_erro = doc.pk in erros
    return documentos


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
    from recursos_humanos.services.portal_token import colaborador_por_token_portal

    colaborador = colaborador_por_token_portal(token)
    if not colaborador:
        return render(request, 'recursos_humanos/portal_link_invalido.html')

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

    from recursos_humanos.services.portal_auth import (
        autenticar_portal,
        consumir_aviso_sessao_expirada,
        portal_esta_autenticado,
        portal_exige_pin,
    )

    if portal_exige_pin(colaborador) and not portal_esta_autenticado(request, token, colaborador):
        if request.method == 'POST' and request.POST.get('acao') == 'autenticar_portal':
            pin = request.POST.get('portal_pin', '')
            declaracao = request.POST.get('declaracao_identidade') == 'on'
            ok, msg = autenticar_portal(request, token, colaborador, pin, declaracao)
            if ok:
                return redirect('recursos_humanos:portal', token=token)
            return _render_portal_acesso(request, colaborador, token, erro=msg)
        erro_expirada = ''
        if consumir_aviso_sessao_expirada(request, token):
            erro_expirada = (
                'Por segurança, informe o código novamente '
                '(a sessão expira a cada 10 minutos).'
            )
        return _render_portal_acesso(request, colaborador, token, erro=erro_expirada)

    from recursos_humanos.services.documentos import (
        dados_visivel_no_portal,
        documento_permite_envio_portal,
        documentos_para_exibicao_portal,
        portal_em_modo_confirmacao,
        portal_modo_envio_restrito,
        portal_permite_editar_dados,
        portal_permite_envio_documentos,
    )

    portal_upload_habilitado = portal_permite_envio_documentos(colaborador)
    portal_modo_restrito = portal_modo_envio_restrito(colaborador)
    portal_modo_confirmacao = portal_em_modo_confirmacao(colaborador)
    portal_permite_dados = portal_permite_editar_dados(colaborador)
    exibir_dados = dados_visivel_no_portal(colaborador)

    instanciar_documentos(colaborador)

    docs_erro_upload = _portal_pop_upload_erros_sessao(request, token)
    documentos = _portal_documentos_enriquecidos(
        colaborador,
        token,
        docs_erro_upload=docs_erro_upload,
    )
    portal_tem_documentos_para_envio = portal_upload_habilitado and any(
        d.portal_pode_enviar for d in documentos
    )
    portal_pode_submeter = not portal_modo_confirmacao and (
        portal_permite_dados or portal_tem_documentos_para_envio
    )

    dados_form = PortalCandidatoDadosForm(instance=colaborador)
    if request.method == 'POST' and request.POST.get('acao') == 'submeter_portal':
        if not portal_pode_submeter:
            messages.error(request, 'O envio não está disponível nesta etapa do processo.')
            return redirect('recursos_humanos:portal', token=token)

        dados_ok = True
        dados_alterados = False
        if portal_permite_dados:
            dados_form = PortalCandidatoDadosForm(request.POST, instance=colaborador)
            if dados_form.is_valid():
                salvar_dados_portal_candidato(colaborador, dados_form.cleaned_data)
                dados_alterados = True
            else:
                dados_ok = False

        enviados: list[str] = []
        upload_erros: list[str] = []
        if portal_upload_habilitado:
            for doc in documentos:
                if not doc.portal_pode_enviar:
                    continue
                arquivo = request.FILES.get(f'doc_{doc.pk}')
                if not arquivo:
                    continue
                form_data = {}
                if doc.tipo.tem_validade:
                    form_data['data_emissao'] = request.POST.get(f'doc_emissao_{doc.pk}', '')
                upload_form = DocumentoUploadForm(
                    form_data,
                    {'arquivo': arquivo},
                    requer_emissao=doc.tipo.tem_validade,
                )
                if upload_form.is_valid():
                    upload_documento_arquivo(
                        doc,
                        upload_form.cleaned_data['arquivo'],
                        'Candidato (portal)',
                        upload_form.cleaned_data.get('data_emissao'),
                    )
                    enviados.append(doc.tipo.nome)
                else:
                    upload_erros.append(doc.tipo.nome)
                    docs_erro_upload.add(doc.pk)

        colaborador.refresh_from_db()
        documentos = _portal_documentos_enriquecidos(
            colaborador,
            token,
            docs_erro_upload=docs_erro_upload,
        )
        portal_tem_documentos_para_envio = portal_upload_habilitado and any(
            d.portal_pode_enviar for d in documentos
        )
        portal_pode_submeter = not portal_modo_confirmacao and (
            portal_permite_dados or portal_tem_documentos_para_envio
        )

        if dados_ok and not upload_erros:
            if enviados and dados_alterados:
                messages.success(
                    request,
                    f'Dados salvos e {len(enviados)} documento(s) enviado(s)! Aguarde a conferência do RH.',
                )
                return redirect('recursos_humanos:portal', token=token)
            if enviados:
                messages.success(
                    request,
                    f'{len(enviados)} documento(s) enviado(s)! Aguarde a conferência do RH.',
                )
                return redirect('recursos_humanos:portal', token=token)
            if dados_alterados:
                messages.success(request, 'Seus dados foram salvos com sucesso!')
                return redirect('recursos_humanos:portal', token=token)
            messages.warning(request, 'Preencha seus dados e/ou selecione arquivos antes de enviar.')
        else:
            if dados_ok:
                dados_form = PortalCandidatoDadosForm(instance=colaborador)
            if enviados:
                messages.success(
                    request,
                    f'{len(enviados)} documento(s) recebido(s): {", ".join(enviados)}.',
                )
            if dados_alterados:
                messages.info(request, 'Seus dados pessoais foram salvos.')
            if not dados_ok:
                dados_form = PortalCandidatoDadosForm(request.POST, instance=colaborador)
                messages.error(request, 'Verifique os campos destacados e tente novamente.')
            if upload_erros:
                messages.error(
                    request,
                    f'Corrija estes itens: {", ".join(upload_erros)}. '
                    f'Verifique arquivo (máx. 10 MB) e data de emissão quando solicitada. '
                    f'Os demais enviados nesta tentativa já foram recebidos.',
                )
            if enviados:
                _portal_guardar_upload_erros_sessao(request, token, docs_erro_upload)
                return redirect('recursos_humanos:portal', token=token)

    from recursos_humanos.forms import PORTAL_UPLOAD_MAX_BYTES

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
            'exibir_dados_pessoais': exibir_dados,
            'token': token,
            'total_docs': total,
            'recebidos_docs': recebidos,
            'progresso_pct': progresso,
            'portal_modo_restrito': portal_modo_restrito,
            'portal_modo_confirmacao': portal_modo_confirmacao,
            'portal_permite_editar_dados': portal_permite_dados,
            'portal_upload_habilitado': portal_upload_habilitado,
            'portal_pode_submeter': portal_pode_submeter,
            'portal_max_upload_bytes': PORTAL_UPLOAD_MAX_BYTES,
        },
    )


def portal_upload_view(request, token, doc_pk):
    """Upload de documento pelo candidato."""
    from recursos_humanos.services.documentos import (
        documento_permite_envio_portal,
        portal_permite_envio_documentos,
    )

    colaborador, invalid_resp = _portal_colaborador_from_token(request, token)
    if invalid_resp:
        return invalid_resp

    auth_redir = _portal_exigir_autenticacao(request, token, colaborador)
    if auth_redir:
        return auth_redir

    if not colaborador.token_portal_valido():
        return redirect('recursos_humanos:portal', token=token)
    if not _portal_status_permitido(colaborador):
        return redirect('recursos_humanos:portal', token=token)
    if not portal_permite_envio_documentos(colaborador):
        messages.error(request, 'O envio de documentos não está disponível nesta etapa do processo.')
        return redirect('recursos_humanos:portal', token=token)

    doc = get_object_or_404(
        DocumentoColaborador,
        pk=doc_pk,
        colaborador=colaborador,
    )
    if not documento_permite_envio_portal(doc, colaborador):
        messages.error(request, 'Este documento não está liberado para envio no momento.')
        return redirect('recursos_humanos:portal', token=token)

    if request.method == 'POST':
        form_data = {}
        if doc.tipo.tem_validade:
            form_data['data_emissao'] = request.POST.get('data_emissao', '')
        form = DocumentoUploadForm(
            form_data,
            request.FILES,
            requer_emissao=doc.tipo.tem_validade,
        )
        if form.is_valid():
            upload_documento_arquivo(
                doc,
                form.cleaned_data['arquivo'],
                'Candidato (portal)',
                form.cleaned_data.get('data_emissao'),
            )
            messages.success(request, f'"{doc.tipo.nome}" enviado! Aguarde a conferência do RH.')
        else:
            err = 'Arquivo inválido. Máx. 10 MB.'
            if doc.tipo.tem_validade and form.errors.get('data_emissao'):
                err = 'Informe a data de emissão e um arquivo válido (máx. 10 MB).'
            messages.error(request, err)

    return redirect('recursos_humanos:portal', token=token)


def portal_arquivo_view(request, token, doc_pk):
    """Visualização do arquivo enviado pelo candidato (portal público com token)."""
    from django.http import FileResponse, Http404

    colaborador, invalid_resp = _portal_colaborador_from_token(request, token)
    if invalid_resp:
        return invalid_resp

    auth_redir = _portal_exigir_autenticacao(request, token, colaborador)
    if auth_redir:
        return auth_redir

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
    from recursos_humanos.services.documentos import (
        documento_permite_envio_portal,
        portal_permite_envio_documentos,
    )

    colaborador, invalid_resp = _portal_colaborador_from_token(request, token)
    if invalid_resp:
        return invalid_resp

    auth_redir = _portal_exigir_autenticacao(request, token, colaborador)
    if auth_redir:
        return auth_redir

    if not colaborador.token_portal_valido():
        return redirect('recursos_humanos:portal', token=token)
    if not _portal_status_permitido(colaborador):
        return redirect('recursos_humanos:portal', token=token)
    if not portal_permite_envio_documentos(colaborador):
        messages.error(request, 'O envio de documentos não está disponível nesta etapa do processo.')
        return redirect('recursos_humanos:portal', token=token)

    doc = get_object_or_404(
        DocumentoColaborador,
        pk=doc_pk,
        colaborador=colaborador,
    )
    if not documento_permite_envio_portal(doc, colaborador):
        messages.error(request, 'Este documento não está liberado para alteração no momento.')
        return redirect('recursos_humanos:portal', token=token)

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
    from recursos_humanos.services.papeis_fluxo import _usuario_eh_rh

    if not _usuario_eh_rh(request.user):
        messages.error(request, 'Você não tem permissão para gerar contratos.')
        return _redirect_admissao(pk)
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
    from recursos_humanos.services.papeis_fluxo import _usuario_eh_rh

    if not _usuario_eh_rh(request.user):
        messages.error(request, 'Você não tem permissão para arquivar contratos.')
        return _redirect_admissao(pk)
    arquivo = request.FILES.get('pdf_assinado')
    if not arquivo:
        messages.error(request, 'Selecione o PDF assinado.')
        return _redirect_admissao(pk)
    if not arquivo.name.lower().endswith('.pdf'):
        messages.error(request, 'Envie um arquivo PDF.')
        return _redirect_admissao(pk)

    from .services.contrato import obter_ou_criar_contrato, salvar_contrato_assinado
    from .services.admissao_actions import contrato_marcado_enviado_zapsign

    if not contrato_marcado_enviado_zapsign(colaborador):
        messages.error(
            request,
            'Marque o contrato como enviado ao ZapSign antes de arquivar o PDF assinado.',
        )
        return _redirect_admissao(pk)

    contrato = obter_ou_criar_contrato(colaborador)
    if salvar_contrato_assinado(contrato, arquivo, request.user):
        ok, msg = concluir_admissao(colaborador, request.user)
        if ok:
            messages.success(request, 'Contrato assinado arquivado. Colaborador ativado.')
            return redirect_para_colaborador(colaborador.pk)
        messages.warning(
            request,
            f'Contrato arquivado, mas não foi possível ativar o colaborador: {msg}',
        )
        return _redirect_admissao(pk)

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
