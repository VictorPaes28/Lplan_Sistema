"""
Views da camada transversal de comunicação (perfil do usuário + painel admin).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.painel_sistema_access import user_is_painel_sistema_admin
from core.comunicacao_constants import (
    MODO_LABELS,
    MODO_OPCOES_GRUPO,
    MODO_OPCOES_PERFIL,
    MODULO_LABELS,
    RESUMO_DIARIO_DISPONIVEL,
    TIPOS_COM_ROUTER_ATIVO,
    TIPOS_NUNCA_DESLIGAR,
    TIPO_GESTCONTROLL_COPIA_ADMIN,
    texto_ui_tipo_comunicacao,
)
from core.comunicacao_models import (
    LogDecisaoComunicacao,
    PreferenciaComunicacao,
    TipoComunicacao,
)
from core.comunicacao_router import ComunicacaoPreferenciasService


def _staff_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_authenticated and user_is_painel_sistema_admin(request.user)):
            raise PermissionDenied('Acesso restrito ao painel do sistema.')
        return view_func(request, *args, **kwargs)
    return wrapper


def _agrupar_tipos_por_modulo(tipos):
    grupos = defaultdict(list)
    for t in tipos:
        grupos[t.modulo].append(t)
    return [
        {
            'modulo': mod,
            'modulo_label': MODULO_LABELS.get(mod, mod),
            'tipos': items,
        }
        for mod, items in sorted(grupos.items(), key=lambda x: MODULO_LABELS.get(x[0], x[0]))
    ]


_STATUS_LABEL_POR_MODO = {
    'padrao': 'Seguindo regra da empresa',
    'email': 'Você pediu para receber por e-mail',
    'sem_email': 'Você pediu para não receber este e-mail',
    'interno': 'Você pediu para não receber este e-mail',
}


def _status_label_modo(modo: str) -> str:
    return _STATUS_LABEL_POR_MODO.get(modo, 'Seguindo regra da empresa')


_MOTIVO_LABELS = {
    'tipo_obrigatorio': 'Tipo obrigatório',
    'padrao_envio': 'Sem preferência personalizada',
    'preferencia_usuario_ativa': 'Preferência individual: recebe',
    'preferencia_usuario_desativada': 'Preferência individual: não recebe',
    'preferencia_email_livre_desativada': 'E-mail externo bloqueado',
    'bloqueado_por_admin': 'Bloqueado por administrador',
    'padrao_grupo_desativado': 'Perfil/grupo bloqueou envio',
    'padrao_grupo_ativo': 'Perfil/grupo permite envio',
    'preferencia_usuario_ativa_sobre_grupo': 'Preferência individual sobrescreveu perfil',
    'preferencia_usuario_desativada_sobre_grupo': 'Preferência individual sobrescreveu perfil',
    'preferencia_resumo': 'Resumo diário (indisponível)',
    'tipo_desconhecido_fallback': 'Tipo não mapeado (fallback)',
    'fallback_erro_servico': 'Falha no serviço (fallback)',
    'router_nao_aplicavel': 'Tipo sem controle central',
}


def _resumo_preferencia(pref: PreferenciaComunicacao) -> dict:
    """Rótulos para listagem admin (somente exibição)."""
    if pref.herdar_padrao:
        modo = 'padrao'
        label = 'Padrão do sistema'
    elif pref.email_ativo is False:
        modo = 'sem_email'
        label = MODO_LABELS.get('sem_email', 'Desativar e-mail imediato')
    elif pref.email_ativo is True:
        modo = 'email'
        label = MODO_LABELS.get('email', 'E-mail imediato')
    else:
        modo = 'outro'
        label = 'Personalizado'
    if pref.email and not pref.usuario_id:
        origem = 'E-mail livre'
    elif pref.usuario_id:
        origem = 'Individual'
    else:
        origem = '—'
    return {'modo': modo, 'label': label, 'origem': origem}


def _montar_linhas_email_pessoa(svc, usuario, *, apenas_controlaveis=False):
    """Monta linhas para UI: controláveis (toggle) e fixas (sempre envia)."""
    tipos = TipoComunicacao.objects.filter(ativo=True).order_by('modulo', 'ordem', 'nome')
    controlaveis = []
    fixos = []
    for tipo in tipos:
        ui = texto_ui_tipo_comunicacao(tipo)
        router_ativo = tipo.codigo in TIPOS_COM_ROUTER_ATIVO
        bloqueado = tipo.codigo in TIPOS_NUNCA_DESLIGAR
        base = {
            'tipo': tipo,
            'titulo': ui['titulo'],
            'quando': ui['quando'],
            'modulo_label': MODULO_LABELS.get(tipo.modulo, tipo.modulo),
        }
        if bloqueado:
            fixos.append({**base, 'motivo': 'Obrigatório (senha, credenciais ou diário ao cliente)'})
            continue
        if router_ativo and (
            tipo.permite_usuario_desativar_email or tipo.permite_admin_desativar_email
        ):
            decisao = svc.pode_enviar_email(
                usuario.email or '',
                tipo.codigo,
                usuario=usuario,
                registrar=False,
            )
            controlaveis.append({**base, 'recebe': decisao.enviar, 'router_ativo': True})
        else:
            if apenas_controlaveis:
                continue
            fixos.append({
                **base,
                'motivo': 'Controle deste envio ainda não está ativo — segue como hoje',
            })
    return controlaveis, fixos


def _agrupar_linhas_por_modulo(controlaveis, fixos):
    """Agrupa linhas por módulo/app para a UI."""
    ordem_mod = list(MODULO_LABELS.keys())
    buckets = {m: {'modulo': m, 'label': MODULO_LABELS.get(m, m), 'controlaveis': [], 'fixos': []} for m in ordem_mod}
    for linha in controlaveis:
        m = linha['tipo'].modulo
        if m not in buckets:
            buckets[m] = {'modulo': m, 'label': MODULO_LABELS.get(m, m), 'controlaveis': [], 'fixos': []}
        buckets[m]['controlaveis'].append(linha)
    for linha in fixos:
        m = linha['tipo'].modulo
        if m not in buckets:
            buckets[m] = {'modulo': m, 'label': MODULO_LABELS.get(m, m), 'controlaveis': [], 'fixos': []}
        buckets[m]['fixos'].append(linha)

    resultado = []
    for m in ordem_mod:
        if m in buckets and (buckets[m]['controlaveis'] or buckets[m]['fixos']):
            resultado.append(buckets[m])
    for m, data in buckets.items():
        if m not in ordem_mod and (data['controlaveis'] or data['fixos']):
            resultado.append(data)
    return resultado


def _modo_atual_usuario(usuario, tipo, svc: ComunicacaoPreferenciasService):
    pref = PreferenciaComunicacao.objects.filter(usuario=usuario, tipo=tipo).first()
    if not pref or pref.herdar_padrao:
        modo = 'padrao'
        return modo, _status_label_modo(modo), svc.explicar_recebimento(
            usuario.email or '', tipo.codigo, usuario=usuario
        )
    if pref.resumo_ativo and RESUMO_DIARIO_DISPONIVEL:
        return 'resumo', 'Resumo diário (indisponível)', 'Opção ainda não disponível.'
    if pref.email_ativo is False:
        modo = 'sem_email'
        return modo, _status_label_modo(modo), (
            'Com sua escolha, este aviso não é enviado por e-mail. '
            'Isso não gera alerta no sino.'
        )
    if pref.email_ativo is True:
        modo = 'email'
        return modo, _status_label_modo(modo), (
            'Com sua escolha, este aviso continua chegando por e-mail, '
            'mesmo que o perfil da empresa diga o contrário.'
        )
    modo = 'padrao'
    return modo, _status_label_modo(modo), svc.explicar_recebimento(
        usuario.email or '', tipo.codigo, usuario=usuario
    )


@login_required
def perfil_comunicacao_view(request):
    """Minhas preferências de e-mail / notificações (perfil do usuário)."""
    svc = ComunicacaoPreferenciasService()

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        if action == 'restaurar_tudo':
            PreferenciaComunicacao.objects.filter(usuario=request.user).delete()
            messages.success(request, 'Preferências restauradas ao padrão do sistema.')
            return redirect('perfil_comunicacao')

        tipo_id = request.POST.get('tipo_id')
        receber = request.POST.get('receber') == '1'
        tipo = get_object_or_404(
            TipoComunicacao,
            pk=tipo_id,
            ativo=True,
            permite_usuario_desativar_email=True,
            obrigatorio=False,
        )
        if tipo.criticidade == 'critico' or tipo.categoria == 'critico':
            messages.error(request, 'Este aviso é obrigatório e não pode ser alterado.')
            return redirect('perfil_comunicacao')
        try:
            modo = 'email' if receber else 'sem_email'
            svc.salvar_preferencia_usuario(
                usuario=request.user,
                tipo=tipo,
                modo=modo,
                atualizado_por=request.user,
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect('perfil_comunicacao')

    controlaveis, fixos = _montar_linhas_email_pessoa(svc, request.user)

    context = {
        'modulos_email': _agrupar_linhas_por_modulo(controlaveis, fixos),
        'tem_algum_editavel': bool(controlaveis),
    }
    return render(request, 'core/comunicacao/perfil_preferencias.html', context)


@login_required
@_staff_required
def admin_comunicacao_hub_view(request):
    """Hub administrativo — E-mails e Notificações."""
    desde = timezone.now() - timedelta(days=30)
    logs = LogDecisaoComunicacao.objects.filter(created_at__gte=desde)
    decisoes_bloqueio = logs.filter(decisao='bloquear').count()
    decisoes_envio = logs.filter(decisao='enviar').count()

    try:
        from gestao_aprovacao.models import EmailLog
        email_logs = EmailLog.objects.filter(criado_em__gte=desde, status='enviado')
        total_emails_enviados = email_logs.count()
        top_modulos_email = []
        for row in email_logs.values('tipo_email').annotate(c=Count('id')).order_by('-c')[:5]:
            top_modulos_email.append({'tipo': row['tipo_email'], 'total': row['c']})
    except Exception:
        total_emails_enviados = 0
        top_modulos_email = []

    top_destinatarios = (
        logs.filter(decisao='enviar', email__gt='')
        .values('email')
        .annotate(c=Count('id'))
        .order_by('-c')[:8]
    )
    top_tipos_decisao = []
    for row in logs.values('tipo_codigo').annotate(c=Count('id')).order_by('-c')[:8]:
        tipo_codigo = row.get('tipo_codigo') or ''
        tipo = TipoComunicacao.objects.filter(codigo=tipo_codigo).only('nome').first()
        top_tipos_decisao.append({
            'tipo_codigo': tipo_codigo,
            'tipo_nome': (tipo.nome if tipo else tipo_codigo) or 'Sem tipo',
            'c': row['c'],
        })

    context = {
        'total_tipos': TipoComunicacao.objects.filter(ativo=True).count(),
        'tipos_controle_ativo': len(TIPOS_COM_ROUTER_ATIVO),
        'total_preferencias': PreferenciaComunicacao.objects.count(),
        'preferencias_personalizadas': PreferenciaComunicacao.objects.filter(herdar_padrao=False).count(),
        'decisoes_bloqueio': decisoes_bloqueio,
        'decisoes_envio': decisoes_envio,
        'decisoes_recentes': logs.count(),
        'total_emails_enviados': total_emails_enviados,
        'top_destinatarios': top_destinatarios,
        'top_tipos_decisao': top_tipos_decisao,
        'top_modulos_email': top_modulos_email,
        'router_ativo_codigo': TIPO_GESTCONTROLL_COPIA_ADMIN,
    }
    return render(request, 'core/comunicacao/admin_hub.html', context)


@login_required
@_staff_required
def admin_comunicacao_tipos_view(request):
    tipos = TipoComunicacao.objects.all().order_by('modulo', 'ordem', 'nome')
    f_modulo = (request.GET.get('modulo') or '').strip()
    f_router = (request.GET.get('router') or '').strip()
    if f_modulo:
        tipos = tipos.filter(modulo=f_modulo)
    tipos_rows = []
    for t in tipos:
        router_ativo = t.codigo in TIPOS_COM_ROUTER_ATIVO
        if f_router == 'sim' and not router_ativo:
            continue
        if f_router == 'nao' and router_ativo:
            continue
        tipos_rows.append({
            'tipo': t,
            'router_ativo': router_ativo,
            'nunca_desligar': t.codigo in TIPOS_NUNCA_DESLIGAR,
            'modulo_label': MODULO_LABELS.get(t.modulo, t.modulo),
        })
    modulos_qs = TipoComunicacao.objects.values_list('modulo', flat=True).distinct().order_by('modulo')
    return render(request, 'core/comunicacao/admin_tipos.html', {
        'tipos_rows': tipos_rows,
        'modulos_choices': [(m, MODULO_LABELS.get(m, m)) for m in modulos_qs],
        'f_modulo': f_modulo,
        'f_router': f_router,
    })


@login_required
@_staff_required
def admin_comunicacao_preferencias_view(request):
    svc = ComunicacaoPreferenciasService()

    alvo = None
    user_id = request.GET.get('usuario') or request.POST.get('user_id')
    if user_id:
        alvo = get_object_or_404(User, pk=user_id, is_active=True)

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        try:
            if action == 'toggle_usuario':
                alvo = get_object_or_404(User, pk=request.POST.get('user_id'), is_active=True)
                tipo = get_object_or_404(TipoComunicacao, pk=request.POST.get('tipo_id'), ativo=True)
                if tipo.codigo not in TIPOS_COM_ROUTER_ATIVO:
                    raise ValueError('Este aviso ainda não pode ser ajustado.')
                if tipo.codigo in TIPOS_NUNCA_DESLIGAR:
                    raise ValueError('Este e-mail é obrigatório do sistema.')
                receber = request.POST.get('receber') == '1'
                modo = 'email' if receber else 'sem_email'
                svc.salvar_preferencia_usuario(
                    usuario=alvo,
                    tipo=tipo,
                    modo=modo,
                    atualizado_por=request.user,
                    contexto_validacao='admin',
                )
                return redirect(f'{reverse("admin_comunicacao_preferencias")}?usuario={alvo.pk}')
            elif action == 'email_livre':
                email = (request.POST.get('email') or '').strip()
                tipo_id = request.POST.get('tipo_id')
                ativo = request.POST.get('email_ativo') == 'on'
                tipo = get_object_or_404(TipoComunicacao, pk=tipo_id)
                bloqueado = request.POST.get('bloqueado_por_admin') == 'on'
                obs = (request.POST.get('observacao') or '').strip()
                svc.salvar_preferencia_email_livre(
                    email=email,
                    tipo=tipo,
                    email_ativo=ativo,
                    atualizado_por=request.user,
                    bloqueado_por_admin=bloqueado,
                    observacao=obs,
                )
                messages.success(request, f'Preferência para {email} salva.')
            else:
                messages.error(request, 'Ação inválida.')
        except (ValueError, ValidationError) as exc:
            messages.error(request, str(exc))
        if alvo:
            return redirect(f'{reverse("admin_comunicacao_preferencias")}?usuario={alvo.pk}')
        return redirect('admin_comunicacao_preferencias')

    q = (request.GET.get('q') or '').strip()
    usuarios = User.objects.filter(is_active=True).order_by('username')
    if q:
        usuarios = usuarios.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )[:30]
    else:
        usuarios = usuarios[:20]

    linhas_controlaveis = []
    linhas_fixos = []
    if alvo:
        linhas_controlaveis, linhas_fixos = _montar_linhas_email_pessoa(svc, alvo)

    vista = (request.GET.get('vista') or 'pessoa').strip()
    if alvo:
        vista = 'pessoa'

    f_modulo = (request.GET.get('modulo') or '').strip()
    f_tipo = (request.GET.get('tipo') or '').strip()
    f_modo = (request.GET.get('modo') or '').strip()
    f_lista_q = (request.GET.get('lista_q') or '').strip()

    lista_prefs = []
    if vista == 'registros':
        prefs_qs = (
            PreferenciaComunicacao.objects.filter(herdar_padrao=False)
            .select_related('tipo', 'usuario', 'atualizado_por')
            .order_by('-updated_at')
        )
        if f_modulo:
            prefs_qs = prefs_qs.filter(tipo__modulo=f_modulo)
        if f_tipo:
            prefs_qs = prefs_qs.filter(tipo_id=f_tipo)
        if f_lista_q:
            prefs_qs = prefs_qs.filter(
                Q(usuario__username__icontains=f_lista_q)
                | Q(usuario__email__icontains=f_lista_q)
                | Q(email__icontains=f_lista_q)
            )
        for pref in prefs_qs[:100]:
            resumo = _resumo_preferencia(pref)
            if f_modo and resumo['modo'] != f_modo:
                continue
            lista_prefs.append({
                'pref': pref,
                'resumo': resumo,
                'modulo_label': MODULO_LABELS.get(pref.tipo.modulo, pref.tipo.modulo),
            })

    return render(request, 'core/comunicacao/admin_preferencias.html', {
        'usuarios': usuarios,
        'q': q,
        'alvo': alvo,
        'vista': vista,
        'modulos_email': _agrupar_linhas_por_modulo(linhas_controlaveis, linhas_fixos),
        'tem_algum_editavel': bool(linhas_controlaveis),
        'lista_prefs': lista_prefs,
        'tipos_email_livre': list(
            TipoComunicacao.objects.filter(
                ativo=True,
                codigo__in=TIPOS_COM_ROUTER_ATIVO,
            )
        ),
        'tipos_filtro': TipoComunicacao.objects.filter(ativo=True).order_by('modulo', 'nome'),
        'modulos_choices': [
            (m, MODULO_LABELS.get(m, m))
            for m in TipoComunicacao.objects.values_list('modulo', flat=True).distinct().order_by('modulo')
        ],
        'f_modulo': f_modulo,
        'f_tipo': f_tipo,
        'f_modo': f_modo,
        'f_lista_q': f_lista_q,
    })


@login_required
@_staff_required
def admin_comunicacao_decisoes_view(request):
    qs = LogDecisaoComunicacao.objects.select_related('tipo', 'usuario').all()

    decisao = (request.GET.get('decisao') or '').strip()
    modulo = (request.GET.get('modulo') or '').strip()
    email_f = (request.GET.get('email') or '').strip()
    tipo_codigo = (request.GET.get('tipo') or '').strip()

    if decisao:
        qs = qs.filter(decisao=decisao)
    if modulo:
        qs = qs.filter(modulo=modulo)
    if email_f:
        qs = qs.filter(email__icontains=email_f)
    if tipo_codigo:
        qs = qs.filter(tipo_codigo=tipo_codigo)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'core/comunicacao/admin_decisoes.html', {
        'page_obj': page_obj,
        'decisao': decisao,
        'modulo': modulo,
        'email_f': email_f,
        'tipo_codigo': tipo_codigo,
        'modulos_choices': [
            (m, MODULO_LABELS.get(m, m))
            for m in TipoComunicacao.objects.values_list('modulo', flat=True).distinct().order_by('modulo')
        ],
        'tipos': TipoComunicacao.objects.filter(ativo=True).order_by('modulo', 'ordem'),
        'filtros_ativos': any([decisao, modulo, email_f, tipo_codigo]),
        'motivos_humanos': _MOTIVO_LABELS,
    })


@login_required
@_staff_required
def admin_comunicacao_padroes_grupo_view(request):
    """Padrões de comunicação por grupo Django (perfil)."""
    svc = ComunicacaoPreferenciasService()
    grupos = Group.objects.all().order_by('name')
    tipos = list(svc.tipos_configuraveis_padrao_grupo())
    tipos_router = TIPOS_COM_ROUTER_ATIVO

    grupo_id = request.GET.get('grupo') or request.POST.get('grupo_id')
    grupo = None
    if grupo_id:
        grupo = get_object_or_404(Group, pk=grupo_id)
    elif grupos.exists():
        grupo = grupos.first()

    if request.method == 'POST' and grupo:
        action = (request.POST.get('action') or '').strip()
        try:
            if action == 'restaurar_grupo':
                n = svc.restaurar_padroes_grupo(grupo)
                messages.success(
                    request,
                    f'Padrões do grupo "{grupo.name}" restaurados ({n} registro(s) removido(s)).',
                )
            elif action == 'salvar':
                tipo_id = request.POST.get('tipo_id')
                modo = (request.POST.get('modo') or 'padrao').strip()
                tipo = get_object_or_404(
                    TipoComunicacao,
                    pk=tipo_id,
                    ativo=True,
                    permite_admin_desativar_email=True,
                )
                if tipo.codigo in TIPOS_NUNCA_DESLIGAR:
                    raise ValueError('Este e-mail não pode ser alterado.')
                svc.salvar_padrao_grupo(grupo, tipo, modo)
                messages.success(request, f'Padrão de "{tipo.nome}" atualizado para {grupo.name}.')
            elif action == 'salvar_todos':
                for tipo in tipos:
                    if tipo.codigo in TIPOS_NUNCA_DESLIGAR:
                        continue
                    modo = (request.POST.get(f'modo_{tipo.pk}') or 'padrao').strip()
                    svc.salvar_padrao_grupo(grupo, tipo, modo)
                messages.success(request, f'Padrões do grupo "{grupo.name}" salvos.')
            else:
                messages.error(request, 'Ação inválida.')
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect(f'{reverse("admin_comunicacao_padroes_grupo")}?grupo={grupo.pk}')

    linhas = []
    if grupo:
        for tipo in tipos:
            bloqueado = tipo.codigo in TIPOS_NUNCA_DESLIGAR
            ui = texto_ui_tipo_comunicacao(tipo)
            modo_grupo = svc.modo_padrao_grupo(grupo, tipo)
            linhas.append({
                'tipo': tipo,
                'titulo': ui['titulo'],
                'modo': modo_grupo,
                'modo_label': MODO_LABELS.get(modo_grupo, 'Padrão do sistema'),
                'bloqueado': bloqueado,
                'router_ativo': tipo.codigo in tipos_router,
                'modulo_label': MODULO_LABELS.get(tipo.modulo, tipo.modulo),
            })

    return render(request, 'core/comunicacao/admin_padroes_grupo.html', {
        'grupos': grupos,
        'grupo': grupo,
        'linhas': linhas,
        'modo_labels': MODO_LABELS,
        'tipos_router': tipos_router,
    })
