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
    DocumentoColaborador,
    ObraLocal,
    TipoDocumento,
)


def _autor(user) -> str:
    if isinstance(user, str):
        return user
    if not user or not getattr(user, 'is_authenticated', False):
        return 'Sistema'
    return user.get_full_name() or user.username


def registrar_historico(colaborador, etapa: int, descricao: str, autor: str, *, concluido: bool = True):
    return AdmissaoHistorico.objects.create(
        colaborador=colaborador,
        etapa=etapa,
        descricao=descricao,
        autor=autor,
        concluido=concluido,
    )


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


def _tentar_notificar_gestor_whatsapp(gestor_user, colaborador, user) -> None:
    from recursos_humanos.services.notificacoes import notificar_gestor_nova_requisicao

    autor = _autor(user)
    try:
        ok = notificar_gestor_nova_requisicao(gestor_user, colaborador)
        if not ok:
            logger.warning(
                'RH: falha ao notificar gestor %s via WhatsApp (sem telefone ou API indisponível)',
                gestor_user.username,
            )
            registrar_historico(
                colaborador,
                1,
                'Falha ao notificar gestor (WhatsApp não configurado ou sem telefone)',
                autor,
                concluido=False,
            )
    except Exception as exc:
        logger.warning('RH: falha ao notificar gestor via WhatsApp: %s', exc)
        registrar_historico(
            colaborador,
            1,
            'Falha ao notificar gestor (WhatsApp não configurado)',
            autor,
            concluido=False,
        )


def tipo_aplica_colaborador(tipo: TipoDocumento, colaborador: Colaborador) -> bool:
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
                    'vencimento': _calcular_vencimento(tipo),
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


def dados_portal_completos(colaborador: Colaborador) -> bool:
    return all(getattr(colaborador, campo) for campo in CAMPOS_DADOS_PORTAL_OBRIGATORIOS)


def salvar_dados_portal_candidato(colaborador: Colaborador, cleaned_data: dict) -> Colaborador:
    for campo in CAMPOS_DADOS_PORTAL:
        valor = cleaned_data.get(campo)
        if campo == 'data_nascimento':
            setattr(colaborador, campo, valor)
        else:
            setattr(colaborador, campo, valor or '')
    colaborador.save(update_fields=[*CAMPOS_DADOS_PORTAL, 'atualizado_em'])
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
    Gestores sem perfil RH veem só requisições pendentes da sua aprovação.
    """
    qs = Colaborador.objects.filter(
        Q(status=Colaborador.Status.EM_ADMISSAO)
        | Q(status=Colaborador.Status.ATIVO, etapa_admissao__gte=5),
    )
    if user is not None and not _usuario_eh_rh(user):
        qs = qs.filter(
            gestor_aprovador_user=user,
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
    return (
        colaborador.etapa_admissao >= 5
        and colaborador.status == Colaborador.Status.ATIVO
    )


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
    if colaborador.gestor_aprovador_user_id and user.pk == colaborador.gestor_aprovador_user_id:
        return True
    return _usuario_eh_rh(user)


def _usuario_pode_corrigir_requisicao(colaborador: Colaborador, user) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    if _usuario_e_criador_requisicao(colaborador, user):
        return True
    return _usuario_eh_rh(user)


@transaction.atomic
def criar_requisicao(cleaned_data, user) -> Colaborador:
    obras = list(cleaned_data.get('obra') or [])
    if not obras:
        raise ValueError('Selecione ao menos uma obra.')
    from django.contrib.auth.models import User

    gestor_user = User.objects.get(pk=cleaned_data['gestor_id'], is_active=True)
    gestor_nome = gestor_user.get_full_name() or gestor_user.username
    colab = Colaborador.objects.create(
        nome=cleaned_data['nome'].strip(),
        cpf=cleaned_data['cpf'].strip(),
        email=cleaned_data['email'].strip(),
        telefone=cleaned_data['telefone'],
        cargo=cleaned_data['cargo'].strip(),
        cargo_rh=cleaned_data.get('cargo_rh'),
        status=Colaborador.Status.EM_ADMISSAO,
        etapa_admissao=1,
        data_admissao=cleaned_data['data_inicio'],
        tipo_contrato=cleaned_data['tipo_contrato'],
        salario=cleaned_data['salario'],
        gestor_aprovador=gestor_nome,
        gestor_aprovador_user=gestor_user,
        requisicao_aprovada_gestor=False,
        requisicao_reprovada=False,
        requisicao_motivo_reprovacao='',
        requisicao_criada_por=user if getattr(user, 'is_authenticated', False) else None,
        motivo_admissao=cleaned_data['motivo'],
        observacoes_requisicao=cleaned_data.get('observacoes', ''),
    )
    colab.obras.set(obras)

    autor = _autor(user)
    registrar_historico(colab, 1, 'Requisição criada', f'RH — {autor}')
    registrar_historico(
        colab,
        1,
        f'Aguardando aprovação do gestor {gestor_nome}',
        gestor_nome,
        concluido=False,
    )

    _tentar_notificar_gestor_whatsapp(gestor_user, colab, user)

    from recursos_humanos.services.notificacoes_sistema import notificar_gestor_requisicao_pendente

    notificar_gestor_requisicao_pendente(colab)

    return colab


@transaction.atomic
def reprovar_requisicao_gestor(colaborador: Colaborador, motivo: str, user) -> tuple[bool, str]:
    if colaborador.etapa_admissao != 1:
        return False, 'Reprovação só na etapa Requisição.'
    if colaborador.requisicao_aprovada_gestor:
        return False, 'Requisição já aprovada pelo gestor.'
    if colaborador.requisicao_reprovada:
        return False, 'Requisição já está reprovada. Aguarde correção do RH.'
    if not _usuario_pode_aprovar_requisicao(colaborador, user):
        return False, 'Apenas o gestor responsável ou o RH pode reprovar esta requisição.'
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
        f'Requisição reprovada pelo gestor {colaborador.gestor_aprovador}: {motivo}',
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
    from django.contrib.auth.models import User

    gestor_user = User.objects.get(pk=cleaned_data['gestor_id'], is_active=True)
    gestor_nome = gestor_user.get_full_name() or gestor_user.username
    obras = list(cleaned_data.get('obra') or [])
    if not obras:
        raise ValueError('Selecione ao menos uma obra.')
    colaborador.nome = cleaned_data['nome'].strip()
    colaborador.cpf = cleaned_data['cpf'].strip()
    colaborador.email = cleaned_data['email'].strip()
    colaborador.telefone = cleaned_data['telefone']
    colaborador.cargo = cleaned_data['cargo'].strip()
    colaborador.cargo_rh = cleaned_data.get('cargo_rh')
    colaborador.data_admissao = cleaned_data['data_inicio']
    colaborador.tipo_contrato = cleaned_data['tipo_contrato']
    colaborador.salario = cleaned_data['salario']
    colaborador.gestor_aprovador = gestor_nome
    colaborador.gestor_aprovador_user = gestor_user
    colaborador.motivo_admissao = cleaned_data['motivo']
    colaborador.observacoes_requisicao = cleaned_data.get('observacoes', '')
    colaborador.requisicao_reprovada = False
    colaborador.requisicao_motivo_reprovacao = ''
    colaborador.requisicao_aprovada_gestor = False
    colaborador.save()
    colaborador.obras.set(obras)
    autor = _autor(user)
    registrar_historico(
        colaborador,
        1,
        f'Requisição corrigida e reenviada ao gestor {gestor_nome}',
        f'RH — {autor}',
    )
    registrar_historico(
        colaborador,
        1,
        f'Aguardando aprovação do gestor {gestor_nome}',
        gestor_nome,
        concluido=False,
    )
    _tentar_notificar_gestor_whatsapp(gestor_user, colaborador, user)

    from recursos_humanos.services.notificacoes_sistema import notificar_gestor_requisicao_pendente

    notificar_gestor_requisicao_pendente(colaborador)

    return colaborador


@transaction.atomic
def aprovar_requisicao_gestor(colaborador: Colaborador, user) -> tuple[bool, str]:
    colaborador = Colaborador.objects.select_for_update().get(pk=colaborador.pk)
    if colaborador.requisicao_aprovada_gestor:
        return False, 'Requisição já foi aprovada anteriormente.'
    if colaborador.etapa_admissao >= 2:
        return False, 'Colaborador já está na etapa 2 ou superior.'
    if colaborador.requisicao_reprovada:
        return False, 'Requisição reprovada. Aguarde o RH corrigir e reenviar.'
    if not _usuario_pode_aprovar_requisicao(colaborador, user):
        return False, 'Apenas o gestor responsável ou o RH pode aprovar esta requisição.'

    colaborador.requisicao_aprovada_gestor = True
    colaborador.etapa_admissao = 2
    colaborador.save(update_fields=['requisicao_aprovada_gestor', 'etapa_admissao', 'atualizado_em'])
    instanciar_documentos(colaborador)
    colaborador.gerar_token_portal(dias=30)

    from django.conf import settings

    from recursos_humanos.services.notificacoes import (
        enviar_link_portal_candidato,
        notificar_nova_admissao,
    )

    telefone_rh = getattr(settings, 'RH_WHATSAPP_NOTIFICACAO', None)
    if telefone_rh:
        try:
            ok = notificar_nova_admissao(telefone_rh, colaborador.nome, colaborador.cargo)
            if not ok:
                logger.warning('RH: falha ao notificar RH via WhatsApp (nova admissão)')
        except Exception as exc:
            logger.warning('RH: falha ao notificar RH via WhatsApp: %s', exc)

    envio_link = {'email': False, 'whatsapp': False}
    try:
        envio_link = enviar_link_portal_candidato(colaborador)
    except Exception as exc:
        logger.exception('RH: falha ao enviar link do portal ao candidato: %s', exc)

    autor = _autor(user)
    registrar_historico(
        colaborador,
        1,
        f'Requisição aprovada pelo gestor {colaborador.gestor_aprovador}',
        autor,
    )

    email_ok = envio_link.get('email', False)
    whatsapp_ok = envio_link.get('whatsapp', False)

    if email_ok:
        registrar_historico(
            colaborador,
            2,
            f'Link do portal enviado por e-mail para {colaborador.email}',
            autor,
        )
    else:
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

    from recursos_humanos.services.notificacoes_sistema import notificar_rh_coleta_iniciada

    notificar_rh_coleta_iniciada(colaborador)

    if not email_ok:
        return True, 'Requisição aprovada, mas não foi possível enviar o link por e-mail ao candidato.'
    return True, 'Requisição aprovada. Link enviado por e-mail ao candidato.'


def _calcular_vencimento(tipo: TipoDocumento):
    if tipo.tem_validade and tipo.dias_validade:
        return timezone.localdate() + timedelta(days=tipo.dias_validade)
    return None


@transaction.atomic
def atualizar_status_documento(doc: DocumentoColaborador, status: str, observacao: str, user):
    doc.status = status
    doc.observacao = (observacao or '').strip()
    if status == DocumentoColaborador.Status.RECEBIDO:
        doc.vencimento = _calcular_vencimento(doc.tipo)
    elif status == DocumentoColaborador.Status.FALTANDO:
        doc.vencimento = None
    doc.save(update_fields=['status', 'observacao', 'vencimento', 'atualizado_em'])
    registrar_historico(
        doc.colaborador,
        doc.colaborador.etapa_admissao,
        f'Documento «{doc.tipo.nome}» marcado como {doc.get_status_display()}',
        _autor(user),
    )


@transaction.atomic
def aprovar_documento_arquivo(doc: DocumentoColaborador, user) -> tuple[bool, str]:
    if not doc.arquivo:
        return False, 'Nenhum arquivo para aprovar.'
    if doc.status == DocumentoColaborador.Status.RECEBIDO:
        return True, 'Documento já aprovado.'
    doc.status = DocumentoColaborador.Status.RECEBIDO
    doc.observacao = ''
    doc.vencimento = _calcular_vencimento(doc.tipo)
    doc.save(update_fields=['status', 'observacao', 'vencimento', 'atualizado_em'])
    registrar_historico(
        doc.colaborador,
        doc.colaborador.etapa_admissao,
        f'Documento aprovado: {doc.tipo.nome}',
        _autor(user),
    )
    return True, f'"{doc.tipo.nome}" aprovado.'


@transaction.atomic
def rejeitar_documento_arquivo(doc: DocumentoColaborador, observacao: str, user) -> tuple[bool, str]:
    obs = (observacao or '').strip()
    if not obs:
        return False, 'Informe uma observação para o candidato.'
    nome_tipo = doc.tipo.nome
    if doc.arquivo:
        doc.arquivo.delete(save=False)
        doc.arquivo = None
    doc.status = DocumentoColaborador.Status.FALTANDO
    doc.observacao = obs
    doc.vencimento = None
    doc.save(update_fields=['arquivo', 'status', 'observacao', 'vencimento', 'atualizado_em'])
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
    doc.vencimento = None
    doc.save(update_fields=['arquivo', 'status', 'vencimento', 'atualizado_em'])
    registrar_historico(
        doc.colaborador,
        doc.colaborador.etapa_admissao,
        f'Arquivo removido: {nome_tipo}',
        _autor(user),
    )


@transaction.atomic
def upload_documento_arquivo(doc: DocumentoColaborador, arquivo, user):
    if doc.arquivo:
        doc.arquivo.delete(save=False)
    doc.arquivo = arquivo
    via_portal = isinstance(user, str) and 'portal' in user.lower()
    if via_portal:
        doc.status = DocumentoColaborador.Status.PENDENTE
        doc.observacao = ''
        doc.vencimento = None
        update_fields = ['arquivo', 'status', 'observacao', 'vencimento', 'atualizado_em']
    else:
        doc.status = DocumentoColaborador.Status.RECEBIDO
        doc.observacao = ''
        doc.vencimento = _calcular_vencimento(doc.tipo)
        update_fields = ['arquivo', 'status', 'observacao', 'vencimento', 'atualizado_em']
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
    return colaborador.documentos_obrigatorios_pendentes() == 0


@transaction.atomic
def avancar_etapa_admissao(colaborador: Colaborador, user) -> tuple[bool, str]:
    etapa = colaborador.etapa_admissao
    autor = _autor(user)

    if etapa == 1:
        if not colaborador.requisicao_aprovada_gestor:
            return False, 'Aguardando aprovação do gestor responsável.'
        colaborador.etapa_admissao = 2
        colaborador.save(update_fields=['etapa_admissao', 'atualizado_em'])
        registrar_historico(colaborador, 2, 'Coleta de documentos iniciada', autor)
        return True, 'Etapa avançada para Coleta de Docs.'

    if etapa == 2:
        if not _docs_obrigatorios_ok(colaborador):
            return False, 'Ainda há documentos obrigatórios pendentes.'
        colaborador.etapa_admissao = 3
        colaborador.save(update_fields=['etapa_admissao', 'atualizado_em'])
        registrar_historico(colaborador, 3, 'Documentação encaminhada para aprovação do RH', autor)
        from recursos_humanos.services.notificacoes_sistema import notificar_rh_aprovacao_pendente

        notificar_rh_aprovacao_pendente(colaborador)
        return True, 'Encaminhado para Aprovação RH.'

    if etapa == 3:
        return False, 'Use «Aprovar documentação» nesta etapa.'

    if etapa == 4:
        colaborador.etapa_admissao = 5
        colaborador.status = Colaborador.Status.ATIVO
        colaborador.save(update_fields=['etapa_admissao', 'status', 'atualizado_em'])
        registrar_historico(colaborador, 5, 'Admissão concluída — colaborador ativo', autor)
        return True, 'Colaborador ativado com sucesso.'

    return False, 'Não há próxima etapa.'


@transaction.atomic
def aprovar_documentacao(colaborador: Colaborador, user) -> tuple[bool, str]:
    if colaborador.etapa_admissao != 3:
        return False, 'Aprovação só na etapa 3.'
    if not _docs_obrigatorios_ok(colaborador):
        return False, 'Documentação incompleta.'
    colaborador.etapa_admissao = 4
    colaborador.save(update_fields=['etapa_admissao', 'atualizado_em'])
    registrar_historico(colaborador, 4, 'Documentação aprovada pelo RH', _autor(user))
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
    if colaborador.etapa_admissao != 3:
        return False, 'Devolução só na etapa 3.'
    colaborador.etapa_admissao = 2
    colaborador.save(update_fields=['etapa_admissao', 'atualizado_em'])
    registrar_historico(
        colaborador,
        2,
        f'Documentação devolvida: {motivo}',
        _autor(user),
        concluido=False,
    )
    return True, 'Admissão devolvida para coleta de documentos.'


@transaction.atomic
def enviar_contrato(colaborador: Colaborador, user) -> tuple[bool, str]:
    if colaborador.etapa_admissao != 4:
        return False, 'Ação disponível na etapa Ass. Contrato.'
    registrar_historico(colaborador, 4, 'Contrato enviado para assinatura', _autor(user))
    return True, 'Contrato marcado como enviado.'


@transaction.atomic
def concluir_admissao(colaborador: Colaborador, user) -> tuple[bool, str]:
    if colaborador.etapa_admissao != 4:
        return False, 'Conclusão só na etapa 4.'
    return avancar_etapa_admissao(colaborador, user)


def obras_reais_queryset():
    """Obras RH espelhadas do GestControll, ativas no sistema."""
    sincronizar_obras_gestao()
    return ObraLocal.objects.filter(
        gestao_obra__isnull=False,
        gestao_obra__ativo=True,
    ).select_related('gestao_obra').order_by('nome')


def usuarios_gestor_list():
    from django.contrib.auth.models import User

    return [
        {
            'id': u.pk,
            'nome': u.get_full_name() or u.username,
            'username': u.username,
        }
        for u in User.objects.filter(is_active=True).order_by(
            'first_name', 'last_name', 'username',
        )
    ]


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
