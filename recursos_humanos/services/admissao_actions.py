"""Ações de escrita no fluxo de admissão e documentos."""
from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

logger = logging.getLogger(__name__)

from recursos_humanos.models import (
    AdmissaoHistorico,
    Colaborador,
    ContratoAdmissao,
    DocumentoColaborador,
    ObraLocal,
    PrazoContrato,
    TipoDocumento,
)


def _autor(user) -> str:
    if isinstance(user, str):
        return user
    if not user or not getattr(user, 'is_authenticated', False):
        return 'Sistema'
    return user.get_full_name() or user.username


def _responsavel_registro_requisicao(user):
    """Usuário logado que cria ou corrige a requisição (responsável pela admissão)."""
    if not user or not getattr(user, 'is_authenticated', False):
        raise ValueError('Usuário logado inválido para registrar a requisição.')
    nome = user.get_full_name() or user.username
    return user, nome


def registrar_historico(colaborador, etapa: int, descricao: str, autor: str, *, concluido: bool = True):
    return AdmissaoHistorico.objects.create(
        colaborador=colaborador,
        etapa=etapa,
        descricao=descricao,
        autor=autor,
        concluido=concluido,
    )


def desligar_colaborador(
    colaborador: Colaborador,
    motivo: str,
    data_desligamento,
    user,
    *,
    registrar_historico_entry: bool = True,
) -> tuple[bool, str]:
    """Desliga colaborador ativo (mesma regra do formulário Desligar)."""
    motivo = (motivo or '').strip()
    erros = []

    if colaborador.status != Colaborador.Status.ATIVO:
        erros.append('Apenas colaboradores ativos podem ser desligados.')
    if not data_desligamento:
        erros.append('Informe a data de desligamento.')
    elif data_desligamento > timezone.localdate():
        erros.append('A data de desligamento não pode ser futura.')
    if len(motivo) < 10:
        erros.append('O motivo deve ter pelo menos 10 caracteres.')

    if erros:
        return False, erros[0]

    autor = _autor(user)
    colaborador.status = Colaborador.Status.DESLIGADO
    colaborador.save(update_fields=['status', 'atualizado_em'])

    if registrar_historico_entry:
        data_fmt = (
            data_desligamento.strftime('%d/%m/%Y')
            if hasattr(data_desligamento, 'strftime')
            else str(data_desligamento)
        )
        registrar_historico(
            colaborador,
            etapa=0,
            descricao=f'Colaborador desligado. Data: {data_fmt}. Motivo: {motivo}',
            autor=autor,
        )
    return True, 'Colaborador desligado com sucesso.'


def listar_historico_colaborador(
    colaborador,
    *,
    limite: int = 100,
    recente_primeiro: bool = True,
):
    """Histórico via query direta — evita inconsistência com prefetch_related."""
    colaborador_id = colaborador.pk if isinstance(colaborador, Colaborador) else colaborador
    qs = AdmissaoHistorico.objects.filter(colaborador_id=colaborador_id)
    if recente_primeiro:
        qs = qs.order_by('-data_hora', '-pk')
    else:
        qs = qs.order_by('data_hora', 'pk')
    return list(qs[:limite])


def serializar_historico_json(eventos) -> list[dict]:
    return [
        {
            'descricao': ev.descricao,
            'data_hora': ev.data_hora.strftime('%d/%m/%Y %H:%M'),
            'autor': ev.autor or '—',
            'concluido': ev.concluido,
            'etapa': ev.etapa,
        }
        for ev in eventos
    ]


def tipo_aplica_colaborador(tipo: TipoDocumento, colaborador: Colaborador) -> bool:
    if not tipo.ativo:
        return False
    if tipo.aplica_a == TipoDocumento.AplicaA.TODOS:
        return True
    if tipo.aplica_a == TipoDocumento.AplicaA.POR_CARGO:
        return bool(
            colaborador.cargo_rh_id
            and tipo.cargos_aplicaveis.filter(pk=colaborador.cargo_rh_id).exists()
        )
    if tipo.aplica_a == TipoDocumento.AplicaA.POR_OBRA:
        obras_col = colaborador.obras.values_list('pk', flat=True)
        return tipo.obras_aplicaveis.filter(pk__in=obras_col).exists()
    return False


def instanciar_documentos(colaborador: Colaborador) -> int:
    """Cria documentos faltantes conforme tipos configurados e regras de aplica-se."""
    tipos = TipoDocumento.objects.prefetch_related('cargos_aplicaveis', 'obras_aplicaveis')
    criados = 0
    for tipo in tipos:
        if tipo_aplica_colaborador(tipo, colaborador):
            _, created = DocumentoColaborador.objects.get_or_create(
                colaborador=colaborador,
                tipo=tipo,
                defaults={
                    'status': DocumentoColaborador.Status.FALTANDO,
                    'vencimento': None,
                },
            )
            if created:
                criados += 1
    return criados


CAMPOS_DADOS_PORTAL = (
    'rg',
    'data_nascimento',
    'pis',
    'endereco',
    'dados_bancarios',
    'escolaridade',
    'tamanho_camisa',
    'tamanho_bota',
)

CAMPOS_DADOS_PORTAL_OBRIGATORIOS = (
    'rg',
    'data_nascimento',
    'endereco',
    'dados_bancarios',
    'escolaridade',
    'tamanho_camisa',
    'tamanho_bota',
)

LABELS_CAMPOS_PORTAL = {
    'rg': 'RG',
    'data_nascimento': 'Data de nascimento',
    'pis': 'PIS/PASEP',
    'endereco': 'Endereço completo',
    'dados_bancarios': 'Conta bancária',
    'escolaridade': 'Escolaridade',
    'tamanho_camisa': 'Tamanho de camisa',
    'tamanho_bota': 'Tamanho de bota',
}


def contexto_dados_portal_rh(colaborador: Colaborador) -> dict:
    """Dados pessoais preenchidos pelo candidato no portal — visão do RH."""
    campos = []
    for campo in CAMPOS_DADOS_PORTAL:
        valor = getattr(colaborador, campo, None)
        if campo == 'data_nascimento' and valor:
            valor_fmt = valor.strftime('%d/%m/%Y')
        else:
            valor_fmt = (valor or '').strip()
        campos.append({
            'campo': campo,
            'label': LABELS_CAMPOS_PORTAL.get(campo, campo),
            'valor': valor_fmt or '—',
            'preenchido': bool(valor),
        })
    tem_algum = any(c['preenchido'] for c in campos)
    return {
        'campos': campos,
        'completo': dados_portal_completos(colaborador),
        'coleta_solicitada': colaborador.dados_coleta_solicitada,
        'tem_algum_preenchido': tem_algum,
    }


def dados_portal_completos(colaborador: Colaborador) -> bool:
    return all(getattr(colaborador, campo) for campo in CAMPOS_DADOS_PORTAL_OBRIGATORIOS)


def salvar_dados_portal_candidato(colaborador: Colaborador, cleaned_data: dict) -> Colaborador:
    for campo in CAMPOS_DADOS_PORTAL:
        valor = cleaned_data.get(campo)
        if campo == 'data_nascimento':
            setattr(colaborador, campo, valor)
        else:
            setattr(colaborador, campo, valor or '')
    if dados_portal_completos(colaborador):
        colaborador.dados_coleta_solicitada = False
        update_fields = [*CAMPOS_DADOS_PORTAL, 'dados_coleta_solicitada', 'atualizado_em']
    else:
        update_fields = [*CAMPOS_DADOS_PORTAL, 'atualizado_em']
    colaborador.save(update_fields=update_fields)
    registrar_historico(
        colaborador,
        2,
        'Dados pessoais atualizados pelo candidato no portal',
        'Candidato (portal)',
    )
    return colaborador


def sincronizar_documentos_em_andamento() -> int:
    """Propaga tipos de documento novos/alterados para admissões já em coleta ou posteriores."""
    total_criados = 0
    for colaborador in Colaborador.objects.filter(
        etapa_admissao__gte=2,
    ).exclude(
        status=Colaborador.Status.DESLIGADO,
    ).prefetch_related('obras'):
        total_criados += instanciar_documentos(colaborador)
    return total_criados


def _usuario_eh_rh(user) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    from accounts.groups import GRUPOS

    return user.groups.filter(name=GRUPOS.RECURSOS_HUMANOS).exists()


def queryset_fluxo_admissao(user=None):
    """
    Colaboradores visíveis no fluxo de admissão:
    - em andamento (EM_ADMISSAO), ou
    - concluídos (ATIVO na etapa 5+), para consulta histórica.
    Usuários sem perfil RH veem só requisições legadas pendentes que criaram.
    """
    qs = Colaborador.objects.filter(
        Q(status=Colaborador.Status.EM_ADMISSAO)
        | Q(status=Colaborador.Status.ATIVO, etapa_admissao__gte=5),
    )
    if user is not None and not _usuario_eh_rh(user):
        qs = qs.filter(
            requisicao_criada_por=user,
            etapa_admissao=1,
            requisicao_aprovada_gestor=False,
            requisicao_reprovada=False,
        )
    doc_qs = DocumentoColaborador.objects.select_related('tipo').order_by('tipo__ordem', 'tipo__nome')
    return qs.prefetch_related(
        'historico_admissao',
        'obras',
        Prefetch('documentos', queryset=doc_qs),
    ).order_by('-data_admissao', 'nome')


def colaborador_admissao_concluida(colaborador: Colaborador) -> bool:
    if colaborador.etapa_admissao < 5:
        return False
    if colaborador.status != Colaborador.Status.ATIVO:
        return False
    from recursos_humanos.services.documentos import colaborador_tem_pendencia_documentos

    return not colaborador_tem_pendencia_documentos(colaborador)


def _usuario_e_criador_requisicao(colaborador: Colaborador, user) -> bool:
    if colaborador.requisicao_criada_por_id:
        return user.pk == colaborador.requisicao_criada_por_id
    nome = (user.get_full_name() or '').strip().lower()
    login = user.username.lower()
    eventos = colaborador.historico_admissao.filter(
        descricao__icontains='requisição criada',
    ).order_by('data_hora')[:3]
    for ev in eventos:
        autor = (ev.autor or '').lower()
        if login in autor:
            return True
        if nome and nome in autor:
            return True
    return False


def garantir_requisicao_criada_por(colaborador: Colaborador) -> Colaborador:
    """Preenche requisicao_criada_por em registros antigos a partir do histórico."""
    if colaborador.requisicao_criada_por_id:
        return colaborador
    from django.contrib.auth.models import User

    ev = colaborador.historico_admissao.filter(
        descricao__icontains='requisição criada',
    ).order_by('data_hora').first()
    if not ev or not ev.autor:
        return colaborador
    autor_txt = ev.autor.replace('RH —', '').replace('RH -', '').strip()
    candidatos = User.objects.filter(is_active=True)
    user = candidatos.filter(username__iexact=autor_txt).first()
    if not user and autor_txt:
        user = candidatos.filter(
            username__iexact=autor_txt.split()[-1],
        ).first()
    if not user:
        for u in candidatos:
            if _usuario_e_criador_requisicao(colaborador, u):
                user = u
                break
    if user:
        colaborador.requisicao_criada_por = user
        colaborador.save(update_fields=['requisicao_criada_por', 'atualizado_em'])
    return colaborador


def _usuario_pode_aprovar_requisicao(colaborador: Colaborador, user) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    if colaborador.aprovadores_requisicao.filter(pk=user.pk, is_active=True).exists():
        return True
    if colaborador.gestor_aprovador_user_id and user.pk == colaborador.gestor_aprovador_user_id:
        return True
    return False


def _sync_gestor_aprovador_campos(colaborador: Colaborador, users) -> None:
    users = list(users)
    if users:
        nomes = [u.get_full_name() or u.username for u in users]
        colaborador.gestor_aprovador = ', '.join(nomes)[:120]
        colaborador.gestor_aprovador_user = users[0]
    else:
        colaborador.gestor_aprovador = ''
        colaborador.gestor_aprovador_user = None


def _aplicar_aprovadores_requisicao(colaborador: Colaborador, users) -> None:
    users = list(users)
    colaborador.aprovadores_requisicao.set(users)
    _sync_gestor_aprovador_campos(colaborador, users)
    colaborador.save(update_fields=['gestor_aprovador', 'gestor_aprovador_user', 'atualizado_em'])


def nomes_aprovadores_requisicao(colaborador: Colaborador) -> list[str]:
    users = list(
        colaborador.aprovadores_requisicao.filter(is_active=True).order_by(
            'first_name', 'last_name', 'username',
        )
    )
    if users:
        return [u.get_full_name() or u.username for u in users]
    if colaborador.gestor_aprovador:
        return [colaborador.gestor_aprovador]
    return []


def _usuario_pode_corrigir_requisicao(colaborador: Colaborador, user) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    if _usuario_e_criador_requisicao(colaborador, user):
        return True
    return _usuario_eh_rh(user)


def _criar_prazo_requisicao_se_necessario(colaborador: Colaborador, form, user) -> None:
    if not form.tem_prazo():
        return
    from recursos_humanos.services.prazo_contrato import criar_prazo_contrato

    cleaned_data = form.cleaned_data
    tipo_prazo = form.get_tipo_prazo()
    data_inicio = cleaned_data.get('data_inicio') or timezone.localdate()
    duracao = cleaned_data['prazo_duracao_dias']
    data_fim = data_inicio + timedelta(days=duracao)
    criar_prazo_contrato(
        colaborador,
        tipo_prazo,
        data_inicio,
        data_fim,
    )
    autor = _autor(user)
    tipo_labels = dict(PrazoContrato.Tipo.choices)
    tipo_label = tipo_labels.get(tipo_prazo, tipo_prazo)
    registrar_historico(
        colaborador,
        1,
        f'Prazo de contrato registrado: {tipo_label} até {data_fim.strftime("%d/%m/%Y")}.',
        f'RH — {autor}',
    )


def _iniciar_coleta_apos_requisicao(
    colaborador: Colaborador,
    user,
    *,
    msg_historico_aprovacao: str | None = None,
) -> dict:
    """Avança para etapa 2, instancia documentos, gera token e notifica o candidato."""
    colaborador.requisicao_aprovada_gestor = True
    if colaborador.etapa_admissao < 2:
        colaborador.etapa_admissao = 2
    colaborador.save(update_fields=['requisicao_aprovada_gestor', 'etapa_admissao', 'atualizado_em'])
    instanciar_documentos(colaborador)
    from recursos_humanos.services.portal_token import renovar_token_portal_colaborador

    _token, portal_pin = renovar_token_portal_colaborador(colaborador)

    from django.conf import settings

    from recursos_humanos.services.notificacoes import (
        enviar_link_portal_candidato,
        envio_portal_candidato_ativo,
        notificar_nova_admissao,
    )

    telefone_rh = getattr(settings, 'RH_WHATSAPP_NOTIFICACAO', None)
    if telefone_rh and envio_portal_candidato_ativo():
        try:
            ok = notificar_nova_admissao(telefone_rh, colaborador.nome, colaborador.cargo)
            if not ok:
                logger.warning('RH: falha ao notificar RH via WhatsApp (nova admissão)')
        except Exception as exc:
            logger.warning('RH: falha ao notificar RH via WhatsApp: %s', exc)

    envio_link = {'email': False, 'whatsapp': False}
    if envio_portal_candidato_ativo():
        try:
            envio_link = enviar_link_portal_candidato(colaborador, portal_pin=portal_pin)
        except Exception as exc:
            logger.exception('RH: falha ao enviar link do portal ao candidato: %s', exc)

    autor = _autor(user)
    registrar_historico(
        colaborador,
        1,
        msg_historico_aprovacao or 'Requisição aprovada — coleta de documentos iniciada',
        autor,
    )

    if envio_portal_candidato_ativo():
        email_ok = envio_link.get('email', False)
        whatsapp_ok = envio_link.get('whatsapp', False)

        if email_ok:
            registrar_historico(
                colaborador,
                2,
                f'Link do portal enviado por e-mail para {colaborador.email}',
                autor,
            )
        elif (colaborador.email or '').strip():
            registrar_historico(
                colaborador,
                2,
                'Falha ao enviar e-mail com link do portal — verificar e-mail do colaborador',
                autor,
                concluido=False,
            )

        if whatsapp_ok:
            registrar_historico(
                colaborador,
                2,
                'Link do portal enviado por WhatsApp',
                autor,
            )
    else:
        registrar_historico(
            colaborador,
            2,
            'Coleta de documentos iniciada — preenchimento pelo gestor no sistema',
            autor,
        )

    from recursos_humanos.services.notificacoes_sistema import notificar_rh_coleta_iniciada

    notificar_rh_coleta_iniciada(colaborador)
    return envio_link


def _dados_candidato_opcionais_payload(cleaned_data: dict) -> dict:
    return {
        'rg': (cleaned_data.get('rg') or '').strip(),
        'data_nascimento': cleaned_data.get('data_nascimento'),
        'pis': (cleaned_data.get('pis') or '').strip(),
        'endereco': (cleaned_data.get('endereco') or '').strip(),
        'dados_bancarios': (cleaned_data.get('dados_bancarios') or '').strip(),
        'escolaridade': (cleaned_data.get('escolaridade') or '').strip(),
        'tamanho_camisa': (cleaned_data.get('tamanho_camisa') or '').strip(),
        'tamanho_bota': (cleaned_data.get('tamanho_bota') or '').strip(),
        'empresa': (cleaned_data.get('empresa') or '').strip(),
    }


def _aplicar_dados_candidato_opcionais(colaborador: Colaborador, cleaned_data: dict) -> None:
    dados = _dados_candidato_opcionais_payload(cleaned_data)
    colaborador.rg = dados['rg']
    colaborador.data_nascimento = dados['data_nascimento']
    colaborador.pis = dados['pis']
    colaborador.endereco = dados['endereco']
    colaborador.dados_bancarios = dados['dados_bancarios']
    colaborador.escolaridade = dados['escolaridade']
    colaborador.tamanho_camisa = dados['tamanho_camisa']
    colaborador.tamanho_bota = dados['tamanho_bota']
    colaborador.empresa = dados['empresa']


@transaction.atomic
def criar_requisicao(form, user) -> Colaborador:
    cleaned_data = form.cleaned_data
    obras = list(cleaned_data.get('obra') or [])
    if not obras:
        raise ValueError('Selecione ao menos uma obra.')
    cargo_rh = cleaned_data.get('cargo_rh')
    if not cargo_rh:
        raise ValueError('Selecione o cargo (RH).')
    cargo = (cleaned_data.get('cargo') or '').strip() or cargo_rh.nome
    dados_opc = _dados_candidato_opcionais_payload(cleaned_data)
    colab = Colaborador.objects.create(
        nome=cleaned_data['nome'].strip(),
        cpf=cleaned_data['cpf'].strip(),
        email=(cleaned_data.get('email') or '').strip(),
        telefone=cleaned_data['telefone'],
        rg=dados_opc['rg'],
        data_nascimento=dados_opc['data_nascimento'],
        pis=dados_opc['pis'],
        endereco=dados_opc['endereco'],
        dados_bancarios=dados_opc['dados_bancarios'],
        escolaridade=dados_opc['escolaridade'],
        tamanho_camisa=dados_opc['tamanho_camisa'],
        tamanho_bota=dados_opc['tamanho_bota'],
        empresa=dados_opc['empresa'],
        cargo=cargo,
        cargo_rh=cargo_rh,
        status=Colaborador.Status.EM_ADMISSAO,
        etapa_admissao=1,
        data_admissao=cleaned_data['data_inicio'],
        tipo_contrato=cleaned_data['tipo_contrato'],
        salario=cleaned_data['salario'],
        deslocamento_origem=(cleaned_data.get('deslocamento_origem') or '').strip(),
        deslocamento_destino=(cleaned_data.get('deslocamento_destino') or '').strip(),
        reembolsos=cleaned_data.get('reembolsos') or [],
        requisicao_aprovada_gestor=False,
        requisicao_reprovada=False,
        requisicao_motivo_reprovacao='',
        requisicao_criada_por=user if getattr(user, 'is_authenticated', False) else None,
        motivo_admissao=cleaned_data['motivo'],
        observacoes_requisicao=cleaned_data.get('observacoes', ''),
    )
    colab.obras.set(obras)
    _aplicar_aprovadores_requisicao(colab, cleaned_data['aprovadores'])

    _criar_prazo_requisicao_se_necessario(colab, form, user)

    autor = _autor(user)
    registrar_historico(colab, 1, 'Requisição criada', f'RH — {autor}')

    from recursos_humanos.services.notificacoes_sistema import notificar_aprovadores_requisicao_pendente

    notificar_aprovadores_requisicao_pendente(colab)

    return colab


@transaction.atomic
def reprovar_requisicao_gestor(colaborador: Colaborador, motivo: str, user) -> tuple[bool, str]:
    if colaborador.etapa_admissao != 1:
        return False, 'Reprovação só na etapa Requisição.'
    if colaborador.requisicao_aprovada_gestor:
        return False, 'Requisição já foi aprovada anteriormente.'
    if colaborador.requisicao_reprovada:
        return False, 'Requisição já está reprovada. Aguarde correção do responsável.'
    if not _usuario_pode_aprovar_requisicao(colaborador, user):
        return False, 'Apenas os aprovadores designados podem reprovar esta requisição.'
    motivo = (motivo or '').strip()
    if not motivo:
        return False, 'Informe o motivo da reprovação.'
    colaborador.requisicao_reprovada = True
    colaborador.requisicao_motivo_reprovacao = motivo
    colaborador.save(update_fields=[
        'requisicao_reprovada',
        'requisicao_motivo_reprovacao',
        'atualizado_em',
    ])
    autor = _autor(user)
    registrar_historico(
        colaborador,
        1,
        f'Requisição reprovada por {autor}: {motivo}',
        autor,
        concluido=False,
    )
    from recursos_humanos.services.notificacoes import notificar_rh_requisicao_reprovada

    try:
        ok = notificar_rh_requisicao_reprovada(colaborador)
        if not ok:
            logger.warning(
                'RH: e-mail de reprovação não enviado para colaborador pk=%s',
                colaborador.pk,
            )
    except Exception as exc:
        logger.warning('RH: falha ao notificar RH sobre reprovação: %s', exc)

    from recursos_humanos.services.notificacoes_sistema import notificar_rh_requisicao_reprovada

    notificar_rh_requisicao_reprovada(colaborador)

    return True, 'Requisição reprovada. O responsável pela admissão foi notificado para corrigir.'


@transaction.atomic
def atualizar_requisicao(colaborador: Colaborador, cleaned_data, user) -> Colaborador:
    if colaborador.etapa_admissao != 1:
        raise ValueError('Correção só na etapa Requisição.')
    if not colaborador.requisicao_reprovada:
        raise ValueError('Esta requisição não está aguardando correção.')
    if not _usuario_pode_corrigir_requisicao(colaborador, user):
        raise ValueError('Você não tem permissão para corrigir esta requisição.')
    obras = list(cleaned_data.get('obra') or [])
    if not obras:
        raise ValueError('Selecione ao menos uma obra.')
    colaborador.nome = cleaned_data['nome'].strip()
    colaborador.cpf = cleaned_data['cpf'].strip()
    colaborador.email = (cleaned_data.get('email') or '').strip()
    colaborador.telefone = cleaned_data['telefone']
    cargo_rh = cleaned_data.get('cargo_rh')
    if not cargo_rh:
        raise ValueError('Selecione o cargo (RH).')
    colaborador.cargo = (cleaned_data.get('cargo') or '').strip() or cargo_rh.nome
    colaborador.cargo_rh = cargo_rh
    colaborador.data_admissao = cleaned_data['data_inicio']
    colaborador.tipo_contrato = cleaned_data['tipo_contrato']
    colaborador.salario = cleaned_data['salario']
    colaborador.deslocamento_origem = (cleaned_data.get('deslocamento_origem') or '').strip()
    colaborador.deslocamento_destino = (cleaned_data.get('deslocamento_destino') or '').strip()
    colaborador.reembolsos = cleaned_data.get('reembolsos') or []
    colaborador.motivo_admissao = cleaned_data['motivo']
    colaborador.observacoes_requisicao = cleaned_data.get('observacoes', '')
    _aplicar_dados_candidato_opcionais(colaborador, cleaned_data)
    colaborador.requisicao_reprovada = False
    colaborador.requisicao_motivo_reprovacao = ''
    colaborador.requisicao_aprovada_gestor = False
    _limpar_aprovacao_requisicao(colaborador)
    colaborador.etapa_admissao = 1
    colaborador.save()
    colaborador.obras.set(obras)
    _aplicar_aprovadores_requisicao(colaborador, cleaned_data['aprovadores'])
    autor = _autor(user)
    registrar_historico(
        colaborador,
        1,
        f'Requisição corrigida por {autor} — reenviada para aprovação',
        f'RH — {autor}',
    )
    from recursos_humanos.services.notificacoes_sistema import notificar_aprovadores_requisicao_pendente

    notificar_aprovadores_requisicao_pendente(colaborador)

    return colaborador


def _limpar_aprovacao_requisicao(colaborador: Colaborador) -> None:
    colaborador.requisicao_aprovada_por = None
    colaborador.requisicao_aprovacao_assinatura = ''
    colaborador.requisicao_aprovada_em = None


def _validar_assinatura_aprovacao(signature_data: str) -> str:
    from gestao_aprovacao.signature_utils import validate_signature_data

    try:
        return validate_signature_data(signature_data)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


@transaction.atomic
def aprovar_requisicao_gestor(
    colaborador: Colaborador,
    user,
    *,
    signature_data: str = '',
) -> tuple[bool, str]:
    colaborador = Colaborador.objects.select_for_update().get(pk=colaborador.pk)
    if colaborador.requisicao_aprovada_gestor:
        return False, 'Requisição já foi aprovada anteriormente.'
    if colaborador.etapa_admissao >= 2:
        return False, 'Colaborador já está na etapa 2 ou superior.'
    if colaborador.requisicao_reprovada:
        return False, 'Requisição reprovada. Aguarde o RH corrigir e reenviar.'
    if not _usuario_pode_aprovar_requisicao(colaborador, user):
        return False, 'Apenas os aprovadores designados podem aprovar esta requisição.'
    try:
        assinatura = _validar_assinatura_aprovacao(signature_data)
    except ValueError as exc:
        return False, str(exc)

    colaborador.requisicao_aprovada_por = user
    colaborador.requisicao_aprovacao_assinatura = assinatura
    colaborador.requisicao_aprovada_em = timezone.now()
    colaborador.save(update_fields=[
        'requisicao_aprovada_por',
        'requisicao_aprovacao_assinatura',
        'requisicao_aprovada_em',
        'atualizado_em',
    ])

    envio_link = _iniciar_coleta_apos_requisicao(
        colaborador,
        user,
        msg_historico_aprovacao=f'Requisição aprovada por {_autor(user)} com assinatura digital.',
    )
    if envio_link.get('email'):
        return True, 'Requisição aprovada. Link enviado por e-mail ao candidato.'
    return True, 'Requisição aprovada. Coleta de documentos iniciada.'


def _calcular_vencimento(tipo: TipoDocumento, data_base=None):
    """
    Calcula vencimento a partir de uma data base (data de emissão do documento).
    Se data_base não informada, retorna None (vencimento fica pendente até informar emissão).
    """
    if tipo.tem_validade and tipo.dias_validade and data_base:
        return data_base + timedelta(days=tipo.dias_validade)
    return None


@transaction.atomic
def atualizar_status_documento(doc: DocumentoColaborador, status: str, observacao: str, user):
    ok_papel, msg_papel = _exigir_papel_conferencia_docs(user, doc.colaborador)
    if not ok_papel:
        raise PermissionError(msg_papel)
    doc.status = status
    doc.observacao = (observacao or '').strip()
    if status == DocumentoColaborador.Status.RECEBIDO:
        doc.vencimento = _calcular_vencimento(doc.tipo, doc.data_emissao)
    elif status == DocumentoColaborador.Status.FALTANDO:
        doc.data_emissao = None
        doc.vencimento = None
    doc.save(update_fields=['status', 'observacao', 'data_emissao', 'vencimento', 'atualizado_em'])
    registrar_historico(
        doc.colaborador,
        doc.colaborador.etapa_admissao,
        f'Documento «{doc.tipo.nome}» marcado como {doc.get_status_display()}',
        _autor(user),
    )


@transaction.atomic
def aprovar_documento_arquivo(
    doc: DocumentoColaborador,
    user,
    data_emissao=None,
) -> tuple[bool, str]:
    from recursos_humanos.models import PapelFluxoAdmissao

    ok_papel, msg_papel = _exigir_papel_conferencia_docs(user, doc.colaborador)
    if not ok_papel:
        return False, msg_papel
    if not doc.arquivo:
        return False, 'Nenhum arquivo para aprovar.'
    if doc.status == DocumentoColaborador.Status.RECEBIDO:
        return True, 'Documento já aprovado.'
    if doc.tipo.tem_validade and not data_emissao and not doc.data_emissao:
        return False, (
            f'"{doc.tipo.nome}" não tem data de emissão. '
            f'Solicite reenvio ao candidato para que informe a data no portal.'
        )
    doc.status = DocumentoColaborador.Status.RECEBIDO
    doc.observacao = ''
    doc.reenvio_solicitado = False
    if data_emissao:
        doc.data_emissao = data_emissao
        doc.vencimento = _calcular_vencimento(doc.tipo, data_emissao)
    elif doc.tipo.tem_validade:
        doc.vencimento = _calcular_vencimento(doc.tipo, doc.data_emissao)
    doc.save(update_fields=[
        'status', 'observacao', 'reenvio_solicitado', 'data_emissao', 'vencimento', 'atualizado_em',
    ])
    registrar_historico(
        doc.colaborador,
        doc.colaborador.etapa_admissao,
        f'Documento aprovado: {doc.tipo.nome}',
        _autor(user),
    )
    msg = f'"{doc.tipo.nome}" aprovado.'
    if doc.vencimento:
        msg += f' Vencimento: {doc.vencimento.strftime("%d/%m/%Y")}.'
    return True, msg


@transaction.atomic
def rejeitar_documento_arquivo(doc: DocumentoColaborador, observacao: str, user) -> tuple[bool, str]:
    ok_papel, msg_papel = _exigir_papel_conferencia_docs(user, doc.colaborador)
    if not ok_papel:
        return False, msg_papel
    obs = (observacao or '').strip()
    if not obs:
        return False, 'Informe uma observação para o candidato.'
    nome_tipo = doc.tipo.nome
    if doc.arquivo:
        doc.arquivo.delete(save=False)
        doc.arquivo = None
    doc.status = DocumentoColaborador.Status.FALTANDO
    doc.observacao = obs
    doc.reenvio_solicitado = False
    doc.coleta_solicitada = True
    doc.data_emissao = None
    doc.vencimento = None
    doc.save(update_fields=[
        'arquivo', 'status', 'observacao', 'reenvio_solicitado',
        'coleta_solicitada', 'data_emissao', 'vencimento', 'atualizado_em',
    ])
    registrar_historico(
        doc.colaborador,
        doc.colaborador.etapa_admissao,
        f'Documento rejeitado: {nome_tipo} — {obs}',
        _autor(user),
    )
    return True, f'"{nome_tipo}" rejeitado. O candidato verá sua observação no portal.'


@transaction.atomic
def remover_documento_arquivo(doc: DocumentoColaborador, user):
    nome_tipo = doc.tipo.nome
    if doc.arquivo:
        doc.arquivo.delete(save=False)
        doc.arquivo = None
    doc.status = DocumentoColaborador.Status.FALTANDO
    doc.reenvio_solicitado = False
    doc.data_emissao = None
    doc.vencimento = None
    doc.save(update_fields=[
        'arquivo', 'status', 'reenvio_solicitado', 'data_emissao', 'vencimento', 'atualizado_em',
    ])
    registrar_historico(
        doc.colaborador,
        doc.colaborador.etapa_admissao,
        f'Arquivo removido: {nome_tipo}',
        _autor(user),
    )


@transaction.atomic
def upload_documento_arquivo(
    doc: DocumentoColaborador,
    arquivo,
    user,
    data_emissao=None,
):
    if doc.arquivo:
        doc.arquivo.delete(save=False)
    doc.arquivo = arquivo
    via_portal = isinstance(user, str) and 'portal' in user.lower()
    if via_portal:
        doc.status = DocumentoColaborador.Status.PENDENTE
        doc.observacao = ''
        doc.reenvio_solicitado = False
        doc.coleta_solicitada = False
        if data_emissao:
            doc.data_emissao = data_emissao
            doc.vencimento = _calcular_vencimento(doc.tipo, data_emissao)
        else:
            doc.data_emissao = None
            doc.vencimento = None
        update_fields = [
            'arquivo', 'status', 'observacao', 'reenvio_solicitado',
            'coleta_solicitada', 'data_emissao', 'vencimento', 'atualizado_em',
        ]
    else:
        doc.status = DocumentoColaborador.Status.RECEBIDO
        doc.observacao = ''
        if data_emissao:
            doc.data_emissao = data_emissao
            doc.vencimento = _calcular_vencimento(doc.tipo, data_emissao)
        elif doc.tipo.tem_validade:
            pass
        else:
            doc.vencimento = None
        update_fields = [
            'arquivo', 'status', 'observacao', 'data_emissao', 'vencimento', 'atualizado_em',
        ]
    doc.save(update_fields=update_fields)
    registrar_historico(
        doc.colaborador,
        doc.colaborador.etapa_admissao,
        f'Arquivo recebido: {doc.tipo.nome}',
        _autor(user),
    )
    if via_portal:
        from recursos_humanos.services.notificacoes_sistema import (
            notificar_rh_documentacao_pronta,
            notificar_rh_documento_recebido,
        )

        notificar_rh_documento_recebido(doc)
        if _docs_obrigatorios_ok(doc.colaborador):
            notificar_rh_documentacao_pronta(doc.colaborador)


def _docs_obrigatorios_ok(colaborador: Colaborador) -> bool:
    from recursos_humanos.services.documentos import documentacao_fluxo_completa

    return documentacao_fluxo_completa(colaborador)


def enviar_lembrete_coleta_documentos(colaborador: Colaborador, user) -> tuple[bool, str]:
    """Reenvia e-mail ao candidato lembrando pendências de coleta no portal."""
    from recursos_humanos.models import PapelFluxoAdmissao
    from recursos_humanos.services.documentos import conferencia_documentos_operacional

    if colaborador.etapa_admissao < 2:
        return False, 'A conferência de documentos ainda não foi iniciada.'
    if conferencia_documentos_operacional(colaborador):
        ok_papel, msg_papel = _exigir_papel_conferencia_docs(user, colaborador)
        if not ok_papel:
            return False, msg_papel
    if not colaborador.requisicao_aprovada_gestor:
        return False, 'Requisição ainda não aprovada (registro legado na etapa 1).'
    return solicitar_pendencias_colaborador(colaborador, user)


def solicitar_pendencias_colaborador(colaborador: Colaborador, user) -> tuple[bool, str]:
    """
    Analisa dados e documentos faltando na coleta e envia e-mail ao colaborador.
    Documentos vencidos devem usar «Solicitar reenvio» por item.
    """
    from recursos_humanos.services.documentos import (
        analisar_pendencias_coleta,
        portal_permite_solicitar_pendencias,
    )
    from recursos_humanos.services.notificacoes import (
        enviar_email_solicitacao_pendencias,
        enviar_whatsapp_portal_colaborador,
        envio_portal_candidato_ativo,
    )

    pendencias = analisar_pendencias_coleta(colaborador)
    if not pendencias:
        return (
            False,
            'Não há dados ou documentos faltando para solicitar. '
            'Para documentos vencidos, use «Solicitar reenvio» em cada item.',
        )

    ok_papel, msg_papel = _exigir_papel_conferencia_docs(user, colaborador)
    if not ok_papel:
        return False, msg_papel
    if envio_portal_candidato_ativo():
        if not (colaborador.email or '').strip() and not (colaborador.telefone or '').strip():
            return False, 'Colaborador sem e-mail ou telefone cadastrado.'
    if colaborador.status == Colaborador.Status.EM_ADMISSAO:
        if colaborador.etapa_admissao < 2:
            return False, 'A coleta de documentos ainda não foi iniciada.'
    if not portal_permite_solicitar_pendencias(colaborador):
        return False, 'O portal não está disponível para este colaborador no momento.'

    from recursos_humanos.services.portal_token import obter_ou_renovar_token_portal_colaborador

    _token, portal_pin = obter_ou_renovar_token_portal_colaborador(colaborador, reenviar_pin=True)

    from recursos_humanos.services.documentos import marcar_pendencias_solicitadas_portal

    marcar_pendencias_solicitadas_portal(colaborador, pendencias)
    autor = _autor(user)
    resumo = _resumo_pendencias_coleta(pendencias)

    if not envio_portal_candidato_ativo():
        registrar_historico(
            colaborador,
            colaborador.etapa_admissao or 2,
            f'Pendências registradas no sistema ({resumo})',
            autor,
        )
        return True, f'Pendências registradas no sistema ({resumo}).'

    email_ok = False
    if (colaborador.email or '').strip():
        email_ok = enviar_email_solicitacao_pendencias(colaborador, pendencias, portal_pin=portal_pin)
    whatsapp_ok = enviar_whatsapp_portal_colaborador(
        colaborador,
        modo='pendencias',
        pendencias_coleta=pendencias,
        portal_pin=portal_pin,
    )
    if email_ok or whatsapp_ok:
        canais = []
        if email_ok:
            canais.append('e-mail')
        if whatsapp_ok:
            canais.append('WhatsApp')
        registrar_historico(
            colaborador,
            colaborador.etapa_admissao or 2,
            f'Solicitação de pendências enviada por {" e ".join(canais)} ({resumo})',
            autor,
        )
        destino = colaborador.email or colaborador.telefone
        return True, f'Solicitação enviada por {" e ".join(canais)} ({destino}).'

    registrar_historico(
        colaborador,
        colaborador.etapa_admissao or 2,
        'Falha ao enviar solicitação de pendências ao colaborador',
        autor,
        concluido=False,
    )
    return False, 'Não foi possível notificar o colaborador (e-mail ou WhatsApp).'


def solicitar_correcao_dados_portal(
    colaborador: Colaborador,
    user,
    *,
    motivo: str = '',
) -> tuple[bool, str]:
    """Libera edição dos dados pessoais no portal e notifica o candidato."""
    from recursos_humanos.services.documentos import (
        colaborador_tem_contato_portal,
        portal_permite_solicitar_pendencias,
    )
    from recursos_humanos.services.notificacoes import (
        enviar_email_solicitacao_pendencias,
        enviar_whatsapp_portal_colaborador,
        envio_portal_candidato_ativo,
    )
    from recursos_humanos.services.portal_token import obter_ou_renovar_token_portal_colaborador

    ok_papel, msg_papel = _exigir_papel_conferencia_docs(user, colaborador)
    if not ok_papel:
        return False, msg_papel
    if colaborador.status != Colaborador.Status.EM_ADMISSAO or colaborador.etapa_admissao < 2:
        return False, 'A coleta de documentos ainda não foi iniciada.'
    if not portal_permite_solicitar_pendencias(colaborador):
        return False, 'O portal não está disponível para este colaborador no momento.'
    if envio_portal_candidato_ativo() and not colaborador_tem_contato_portal(colaborador):
        return False, 'Colaborador sem e-mail ou telefone cadastrado.'
    if not contexto_dados_portal_rh(colaborador)['tem_algum_preenchido']:
        return False, 'O candidato ainda não enviou dados pessoais pelo portal.'

    detalhe = (motivo or '').strip() or 'Corrija as informações conforme orientação do RH.'
    pendencias = [{
        'tipo': 'dado',
        'label': 'Dados pessoais',
        'detalhe': detalhe,
    }]

    colaborador.dados_coleta_solicitada = True
    colaborador.save(update_fields=['dados_coleta_solicitada', 'atualizado_em'])

    _token, portal_pin = obter_ou_renovar_token_portal_colaborador(colaborador, reenviar_pin=True)

    autor = _autor(user)
    if not envio_portal_candidato_ativo():
        registrar_historico(
            colaborador,
            colaborador.etapa_admissao or 2,
            'Correção dos dados pessoais registrada no sistema',
            autor,
        )
        return True, 'Correção dos dados pessoais registrada. O gestor pode atualizar no sistema.'

    email_ok = False
    if (colaborador.email or '').strip():
        email_ok = enviar_email_solicitacao_pendencias(colaborador, pendencias, portal_pin=portal_pin)
    whatsapp_ok = enviar_whatsapp_portal_colaborador(
        colaborador,
        modo='pendencias',
        pendencias_coleta=pendencias,
        portal_pin=portal_pin,
    )
    autor = _autor(user)
    if email_ok or whatsapp_ok:
        canais = []
        if email_ok:
            canais.append('e-mail')
        if whatsapp_ok:
            canais.append('WhatsApp')
        registrar_historico(
            colaborador,
            colaborador.etapa_admissao or 2,
            f'Solicitação de correção dos dados pessoais enviada por {" e ".join(canais)}',
            autor,
        )
        destino = colaborador.email or colaborador.telefone
        return True, f'Solicitação enviada por {" e ".join(canais)} ({destino}).'

    registrar_historico(
        colaborador,
        colaborador.etapa_admissao or 2,
        'Falha ao solicitar correção dos dados pessoais ao colaborador',
        autor,
        concluido=False,
    )
    return False, 'Não foi possível notificar o colaborador (e-mail ou WhatsApp).'


def _resumo_pendencias_coleta(pendencias: list[dict]) -> str:
    labels = [p['label'] for p in pendencias[:5]]
    resumo = ', '.join(labels)
    if len(pendencias) > 5:
        resumo += f' e mais {len(pendencias) - 5}'
    return resumo


@transaction.atomic
def avancar_etapa_admissao(colaborador: Colaborador, user) -> tuple[bool, str]:
    etapa = colaborador.etapa_admissao
    autor = _autor(user)

    if etapa == 1:
        return False, (
            'A etapa Requisição avança automaticamente ao criar a admissão. '
            'Registros legados pendentes podem ser aprovados na etapa 1.'
        )

    if etapa == 2:
        from recursos_humanos.models import PapelFluxoAdmissao

        ok_papel, msg_papel = _exigir_papel_conferencia_docs(user, colaborador)
        if not ok_papel:
            return False, msg_papel
        if not _docs_obrigatorios_ok(colaborador):
            return False, 'Ainda há documentos pendentes, vencidos ou aguardando conferência.'
        colaborador.etapa_admissao = 3
        colaborador.save(update_fields=['etapa_admissao', 'atualizado_em'])
        registrar_historico(colaborador, 3, 'Documentação encaminhada para validação final', autor)
        from recursos_humanos.services.notificacoes_sistema import notificar_rh_aprovacao_pendente

        notificar_rh_aprovacao_pendente(colaborador)
        return True, 'Encaminhado para validação final.'

    if etapa == 3:
        return False, 'Use «Aprovar documentação» nesta etapa.'

    if etapa == 4:
        colaborador.etapa_admissao = 5
        colaborador.status = Colaborador.Status.ATIVO
        colaborador.save(update_fields=['etapa_admissao', 'status', 'atualizado_em'])
        registrar_historico(colaborador, 5, 'Admissão concluída — colaborador ativo', autor)
        return True, 'Colaborador ativado com sucesso.'

    return False, 'Não há próxima etapa.'


def _exigir_rh(user) -> tuple[bool, str]:
    if _usuario_eh_rh(user):
        return True, ''
    return False, 'Apenas usuários do RH podem executar esta ação.'


def _exigir_papel(user, codigo: str) -> tuple[bool, str]:
    return _exigir_rh(user)


def _exigir_papel_conferencia_docs(user, colaborador: Colaborador) -> tuple[bool, str]:
    from recursos_humanos.models import PapelFluxoAdmissao
    from recursos_humanos.services.papeis_fluxo import (
        obter_papel,
        usuario_pode_conferir_documentos,
    )

    if usuario_pode_conferir_documentos(user, colaborador):
        return True, ''
    papel = obter_papel(PapelFluxoAdmissao.Codigo.CONFERENCIA_DOCS)
    titulo = papel.titulo if papel else 'Conferência de documentos'
    return False, f'Você não tem permissão para executar «{titulo}».'


@transaction.atomic
def aprovar_documentacao(colaborador: Colaborador, user) -> tuple[bool, str]:
    from recursos_humanos.models import PapelFluxoAdmissao

    ok_papel, msg_papel = _exigir_papel(user, PapelFluxoAdmissao.Codigo.VALIDACAO_FINAL)
    if not ok_papel:
        return False, msg_papel
    if colaborador.etapa_admissao != 3:
        return False, 'Aprovação só na etapa 3.'
    if not _docs_obrigatorios_ok(colaborador):
        return False, 'Documentação incompleta ou com pendências (vencidos, reenvios ou faltantes).'
    colaborador.etapa_admissao = 4
    colaborador.save(update_fields=['etapa_admissao', 'atualizado_em'])
    registrar_historico(colaborador, 4, 'Documentação validada — contrato liberado', _autor(user))
    from core.notification_utils import marcar_lidas_por_event_key

    marcar_lidas_por_event_key(
        f'rh:colab:{colaborador.pk}:docs_ok',
        notification_types=('rh_documentacao_pronta', 'rh_admissao_pendente'),
    )
    marcar_lidas_por_event_key(
        f'rh:colab:{colaborador.pk}:aprovacao_rh',
        notification_types=('rh_admissao_pendente',),
    )
    return True, 'Documentação aprovada. Contrato liberado.'


@transaction.atomic
def devolver_admissao(colaborador: Colaborador, motivo: str, user) -> tuple[bool, str]:
    from recursos_humanos.models import PapelFluxoAdmissao

    ok_papel, msg_papel = _exigir_papel(user, PapelFluxoAdmissao.Codigo.VALIDACAO_FINAL)
    if not ok_papel:
        return False, msg_papel
    if colaborador.etapa_admissao != 3:
        return False, 'Devolução só na etapa 3.'
    colaborador.etapa_admissao = 2
    colaborador.save(update_fields=['etapa_admissao', 'atualizado_em'])
    registrar_historico(
        colaborador,
        2,
        f'Documentação devolvida para conferência: {motivo}',
        _autor(user),
        concluido=False,
    )
    from recursos_humanos.services.notificacoes_sistema import notificar_rh_devolucao_documentacao

    notificar_rh_devolucao_documentacao(colaborador, motivo)
    return True, 'Admissão devolvida para conferência de documentos.'


@transaction.atomic
def enviar_contrato(colaborador: Colaborador, user) -> tuple[bool, str]:
    from recursos_humanos.models import PapelFluxoAdmissao

    ok_papel, msg_papel = _exigir_papel(user, PapelFluxoAdmissao.Codigo.CONTRATO)
    if not ok_papel:
        return False, msg_papel
    if colaborador.etapa_admissao != 4:
        return False, 'Ação disponível na etapa Contrato (ZapSign).'
    try:
        contrato = colaborador.contrato_admissao
    except ContratoAdmissao.DoesNotExist:
        contrato = None
    if not contrato or not contrato.pdf_contrato:
        return False, 'Gere o PDF do contrato antes de marcar como enviado ao ZapSign.'
    if contrato.status == ContratoAdmissao.Status.CONCLUIDO:
        return False, 'Contrato já foi arquivado como assinado.'
    registrar_historico(
        colaborador,
        4,
        'Contrato enviado para assinatura no ZapSign',
        _autor(user),
    )
    return True, 'Contrato marcado como enviado para assinatura no ZapSign.'


def contrato_marcado_enviado_zapsign(colaborador: Colaborador) -> bool:
    return colaborador.historico_admissao.filter(
        etapa=4,
        descricao__icontains='Contrato enviado para assinatura',
    ).exists()


@transaction.atomic
def concluir_admissao(colaborador: Colaborador, user) -> tuple[bool, str]:
    from recursos_humanos.models import PapelFluxoAdmissao

    ok_papel, msg_papel = _exigir_papel(user, PapelFluxoAdmissao.Codigo.CONTRATO)
    if not ok_papel:
        return False, msg_papel
    if colaborador.etapa_admissao != 4:
        return False, 'Conclusão só na etapa 4.'
    try:
        contrato = colaborador.contrato_admissao
    except ContratoAdmissao.DoesNotExist:
        contrato = None
    if not contrato or contrato.status != ContratoAdmissao.Status.CONCLUIDO:
        return False, 'Arquive o contrato assinado antes de concluir a admissão.'
    if not contrato.data_admissao_oficial:
        return False, 'Informe a data de admissão oficial na etapa do contrato antes de concluir.'
    from recursos_humanos.services.prazo_contrato import aplicar_data_admissao_oficial

    ok_data, msg_data = aplicar_data_admissao_oficial(
        colaborador,
        contrato.data_admissao_oficial,
        user,
    )
    if not ok_data:
        return False, msg_data
    return avancar_etapa_admissao(colaborador, user)


def obras_reais_queryset():
    """Obras RH espelhadas do GestControll, ativas no sistema."""
    sincronizar_obras_gestao()
    return ObraLocal.objects.filter(
        gestao_obra__isnull=False,
        gestao_obra__ativo=True,
    ).select_related('gestao_obra').order_by('nome')


def sincronizar_obras_gestao():
    """Espelha obras ativas do GestControll em ObraLocal (sem apagar existentes)."""
    from gestao_aprovacao.models import Obra

    criadas = 0
    for obra in Obra.objects.filter(ativo=True).only('id', 'nome'):
        nome = (obra.nome or '').strip()
        if not nome:
            continue
        local, created = ObraLocal.objects.get_or_create(
            nome=nome,
            defaults={'gestao_obra_id': obra.pk},
        )
        if not created and local.gestao_obra_id is None:
            local.gestao_obra_id = obra.pk
            local.save(update_fields=['gestao_obra_id'])
        if created:
            criadas += 1
    return criadas
