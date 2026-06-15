from datetime import timedelta
from io import BytesIO

from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from recursos_humanos.models import Colaborador, PrazoContrato


LABELS_ACAO = {
    'efetivar': 'Efetivar (CLT indeterminado)',
    'prorrogar': 'Prorrogar período de experiência',
    'converter': 'Converter para indeterminado',
    'renovar': 'Renovar contrato',
    'desligar': 'Desligar colaborador',
    'encerrar': 'Encerrar contrato',
}


def criar_prazo_contrato(
    colaborador,
    tipo,
    data_inicio,
    data_fim,
    observacoes='',
) -> PrazoContrato:
    return PrazoContrato.objects.create(
        colaborador=colaborador,
        tipo=tipo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        observacoes=observacoes,
    )


def prazos_vencendo(dias_antecedencia=30):
    """Retorna prazos ativos que vencem dentro de X dias ou já vencidos."""
    hoje = timezone.localdate()
    limite = hoje + timedelta(days=dias_antecedencia)

    return PrazoContrato.objects.filter(
        status=PrazoContrato.Status.ATIVO,
        data_fim__isnull=False,
        data_fim__lte=limite,
        colaborador__status__in=(
            Colaborador.Status.ATIVO,
            Colaborador.Status.EM_ADMISSAO,
        ),
    ).select_related('colaborador').order_by('data_fim')


def executar_acao_prazo(
    prazo: PrazoContrato,
    acao: str,
    user,
    nova_data_fim=None,
    motivo='',
) -> tuple[bool, str]:
    """Executa a ação escolhida sobre o prazo de contrato. Retorna (sucesso, mensagem)."""
    from .admissao_actions import _autor, registrar_historico

    colaborador = prazo.colaborador
    autor = _autor(user)

    if acao not in prazo.acoes_disponiveis():
        return False, f'Ação "{acao}" não disponível para este tipo de contrato.'

    if acao == 'efetivar':
        prazo.status = PrazoContrato.Status.CONVERTIDO
        prazo.data_fim = None
        prazo.finalizado_em = timezone.now()
        prazo.save(update_fields=['status', 'data_fim', 'finalizado_em'])
        colaborador.tipo_contrato = 'CLT'
        colaborador.save(update_fields=['tipo_contrato', 'atualizado_em'])
        registrar_historico(
            colaborador,
            colaborador.etapa_admissao,
            'Período de experiência concluído. Colaborador efetivado em CLT indeterminado.',
            autor,
        )
        return True, 'Colaborador efetivado com sucesso.'

    if acao == 'prorrogar':
        if not nova_data_fim:
            return False, 'Informe a nova data de fim.'
        dias_totais = (nova_data_fim - prazo.data_inicio).days
        if prazo.limite_legal_dias and dias_totais > prazo.limite_legal_dias:
            return False, (
                f'Prorrogação excede o limite legal de '
                f'{prazo.limite_legal_dias} dias para '
                f'{prazo.get_tipo_display()}.'
            )
        prazo.status = PrazoContrato.Status.RENOVADO
        prazo.finalizado_em = timezone.now()
        prazo.save()

        novo_prazo = criar_prazo_contrato(
            colaborador,
            prazo.tipo,
            prazo.data_fim,
            nova_data_fim,
        )
        novo_prazo.renovacao_numero = prazo.renovacao_numero + 1
        novo_prazo.prazo_anterior = prazo
        novo_prazo.save(update_fields=['renovacao_numero', 'prazo_anterior'])

        registrar_historico(
            colaborador,
            colaborador.etapa_admissao,
            f'Período de experiência prorrogado até {nova_data_fim.strftime("%d/%m/%Y")}.',
            autor,
        )
        return True, 'Prazo prorrogado com sucesso.'

    if acao == 'converter':
        prazo.status = PrazoContrato.Status.CONVERTIDO
        prazo.data_fim = None
        prazo.finalizado_em = timezone.now()
        prazo.save(update_fields=['status', 'data_fim', 'finalizado_em'])
        colaborador.tipo_contrato = 'CLT'
        colaborador.save(update_fields=['tipo_contrato', 'atualizado_em'])
        registrar_historico(
            colaborador,
            colaborador.etapa_admissao,
            'Contrato convertido de prazo determinado para indeterminado.',
            autor,
        )
        return True, 'Contrato convertido para indeterminado.'

    if acao == 'renovar':
        if not nova_data_fim:
            return False, 'Informe a nova data de fim.'

        if prazo.limite_legal_dias:
            anterior = prazo
            while anterior.prazo_anterior_id:
                anterior = anterior.prazo_anterior
            dias_totais = (nova_data_fim - anterior.data_inicio).days
            if dias_totais > prazo.limite_legal_dias:
                return False, (
                    f'Renovação excede o limite legal de '
                    f'{prazo.limite_legal_dias} dias para '
                    f'{prazo.get_tipo_display()}. '
                    f'Considere converter para indeterminado.'
                )

        prazo.status = PrazoContrato.Status.RENOVADO
        prazo.finalizado_em = timezone.now()
        prazo.save(update_fields=['status', 'finalizado_em'])

        data_inicio_novo = prazo.data_fim or timezone.localdate()
        novo_prazo = criar_prazo_contrato(
            colaborador,
            prazo.tipo,
            data_inicio_novo,
            nova_data_fim,
        )
        novo_prazo.renovacao_numero = prazo.renovacao_numero + 1
        novo_prazo.prazo_anterior = prazo
        novo_prazo.save(update_fields=['renovacao_numero', 'prazo_anterior'])

        registrar_historico(
            colaborador,
            colaborador.etapa_admissao,
            f'Contrato renovado até {nova_data_fim.strftime("%d/%m/%Y")} '
            f'(renovação nº {novo_prazo.renovacao_numero}).',
            autor,
        )
        return True, 'Contrato renovado com sucesso.'

    if acao == 'desligar':
        motivo = (motivo or '').strip()
        if not motivo:
            return False, 'Informe o motivo do desligamento.'

        from .admissao_actions import desligar_colaborador

        data_hoje = timezone.localdate()
        with transaction.atomic():
            ok, msg = desligar_colaborador(
                colaborador,
                motivo,
                data_hoje,
                user,
                registrar_historico_entry=False,
            )
            if not ok:
                return False, msg

            prazo.status = PrazoContrato.Status.ENCERRADO
            prazo.finalizado_em = timezone.now()
            prazo.observacoes = motivo
            prazo.save(update_fields=['status', 'finalizado_em', 'observacoes'])

            registrar_historico(
                colaborador,
                colaborador.etapa_admissao,
                (
                    f'Contrato encerrado e colaborador desligado. '
                    f'Data: {data_hoje.strftime("%d/%m/%Y")}. Motivo: {motivo}'
                ),
                autor,
            )
        return True, 'Contrato encerrado e colaborador desligado.'

    if acao == 'encerrar':
        motivo = (motivo or '').strip()
        if not motivo:
            return False, 'Informe o motivo do encerramento.'

        from .admissao_actions import desligar_colaborador

        data_hoje = timezone.localdate()
        with transaction.atomic():
            ok, msg = desligar_colaborador(
                colaborador,
                motivo,
                data_hoje,
                user,
                registrar_historico_entry=False,
            )
            if not ok:
                return False, msg

            prazo.status = PrazoContrato.Status.ENCERRADO
            prazo.finalizado_em = timezone.now()
            prazo.observacoes = motivo
            prazo.save(update_fields=['status', 'finalizado_em', 'observacoes'])

            registrar_historico(
                colaborador,
                colaborador.etapa_admissao,
                (
                    f'Contrato encerrado e colaborador desligado. '
                    f'Data: {data_hoje.strftime("%d/%m/%Y")}. Motivo: {motivo}'
                ),
                autor,
            )
        return True, 'Contrato encerrado e colaborador desligado.'

    return False, 'Ação não reconhecida.'


def reativar_prazo_contrato(prazo: PrazoContrato, user) -> tuple[bool, str]:
    """Reativa prazo encerrado e colaborador desligado pelo encerramento."""
    from .admissao_actions import _autor, registrar_historico

    if prazo.status != PrazoContrato.Status.ENCERRADO:
        return False, 'Apenas contratos encerrados podem ser reativados.'

    colaborador = prazo.colaborador
    if colaborador.status != Colaborador.Status.DESLIGADO:
        return False, 'O colaborador não está desligado.'

    autor = _autor(user)
    with transaction.atomic():
        prazo.status = PrazoContrato.Status.ATIVO
        prazo.finalizado_em = None
        prazo.save(update_fields=['status', 'finalizado_em'])

        colaborador.status = Colaborador.Status.ATIVO
        colaborador.save(update_fields=['status', 'atualizado_em'])

        registrar_historico(
            colaborador,
            colaborador.etapa_admissao,
            (
                f'Contrato reativado ({prazo.get_tipo_display()}, '
                f'vigência {prazo.data_inicio.strftime("%d/%m/%Y")} a '
                f'{prazo.data_fim.strftime("%d/%m/%Y")}). Colaborador reativado.'
            ),
            autor,
        )
    return True, 'Contrato e colaborador reativados com sucesso.'


def prazo_contrato_para_perfil(colaborador):
    """Prazo para exibir no perfil: ativo > convertido/encerrado mais recente."""
    ativo = colaborador.prazos_contrato.filter(
        status=PrazoContrato.Status.ATIVO,
    ).order_by('-data_inicio', '-pk').first()
    if ativo:
        return ativo
    return colaborador.prazos_contrato.filter(
        status__in=(
            PrazoContrato.Status.CONVERTIDO,
            PrazoContrato.Status.ENCERRADO,
        ),
    ).order_by('-finalizado_em', '-data_inicio', '-pk').first()


def serializar_prazo_perfil(prazo: PrazoContrato) -> dict:
    encerrado = prazo.status == PrazoContrato.Status.ENCERRADO
    convertido = prazo.status == PrazoContrato.Status.CONVERTIDO
    ativo = prazo.status == PrazoContrato.Status.ATIVO
    pode_decidir = ativo or convertido

    if encerrado:
        situacao = 'Encerrado'
    elif convertido:
        situacao = 'Convertido para indeterminado'
    else:
        situacao = formatar_situacao_prazo(prazo)

    dias = prazo.dias_restantes() if ativo else None
    renovacao = 'Original' if not prazo.renovacao_numero else f'Nº {prazo.renovacao_numero}'

    data = {
        'id': prazo.pk,
        'tipo': prazo.get_tipo_display(),
        'data_inicio': prazo.data_inicio.strftime('%d/%m/%Y'),
        'data_fim': formatar_data_fim_prazo(prazo),
        'data_fim_indeterminado': prazo.data_fim is None,
        'renovacao': renovacao,
        'dias_restantes': dias,
        'situacao': situacao,
        'status': prazo.status,
        'status_display': prazo.get_status_display(),
        'encerrado': encerrado,
        'convertido': convertido,
        'motivo_encerramento': prazo.observacoes if encerrado else '',
        'pode_decidir': pode_decidir,
        'pode_reativar': encerrado,
        'exibir_decidir': pode_decidir,
        'exibir_reativar': encerrado,
    }
    if encerrado:
        data['url_reativar'] = reverse(
            'recursos_humanos:prazo_contrato_reativar',
            kwargs={'pk': prazo.pk},
        )
    else:
        data['url_reativar'] = None
    return data


def gerar_documento_renovacao(prazo: PrazoContrato) -> bytes:
    """Gera PDF de termo de renovação/aditivo contratual."""
    colaborador = prazo.colaborador
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=14,
        spaceAfter=6,
        alignment=1,
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=10,
        leading=16,
        spaceAfter=8,
    )

    story = []
    story.append(Paragraph('LPLAN ENGENHARIA', title_style))
    story.append(Paragraph('TERMO ADITIVO CONTRATUAL', title_style))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph(
        f'<b>Colaborador:</b> {colaborador.nome}<br/>'
        f'<b>CPF:</b> {colaborador.cpf}<br/>'
        f'<b>Cargo:</b> {colaborador.cargo}<br/>'
        f'<b>Tipo de contrato:</b> {prazo.get_tipo_display()}',
        body_style,
    ))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph(
        f'Por meio deste termo, as partes acordam a renovação do contrato '
        f'de trabalho, com vigência de '
        f'{prazo.data_inicio.strftime("%d/%m/%Y")} a '
        f'{prazo.data_fim.strftime("%d/%m/%Y")}.',
        body_style,
    ))

    if prazo.prazo_anterior_id:
        origem = prazo.prazo_anterior
        while origem.prazo_anterior_id:
            origem = origem.prazo_anterior
        story.append(Paragraph(
            f'Este termo é a renovação nº {prazo.renovacao_numero} '
            f'do contrato original iniciado em '
            f'{origem.data_inicio.strftime("%d/%m/%Y")}.',
            body_style,
        ))

    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(
        f'Recife, {timezone.localdate().strftime("%d/%m/%Y")}.',
        body_style,
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer


ACOES_META = {
    'efetivar': {'precisa_data': False, 'motivo_obrigatorio': False, 'danger': False},
    'prorrogar': {'precisa_data': True, 'motivo_obrigatorio': False, 'danger': False},
    'converter': {'precisa_data': False, 'motivo_obrigatorio': False, 'danger': False},
    'renovar': {'precisa_data': True, 'motivo_obrigatorio': False, 'danger': False},
    'desligar': {'precisa_data': False, 'motivo_obrigatorio': True, 'danger': True},
    'encerrar': {'precisa_data': False, 'motivo_obrigatorio': True, 'danger': True},
}


def formatar_data_fim_prazo(prazo: PrazoContrato) -> str:
    if prazo.data_fim is None:
        return 'Indeterminado'
    return prazo.data_fim.strftime('%d/%m/%Y')


def formatar_vigencia_prazo(prazo: PrazoContrato) -> str:
    inicio = prazo.data_inicio.strftime('%d/%m/%Y')
    if prazo.data_fim is None:
        return f'{inicio} — Indeterminado'
    return f'{inicio} a {prazo.data_fim.strftime("%d/%m/%Y")}'


def formatar_situacao_prazo(prazo: PrazoContrato) -> str:
    dias = prazo.dias_restantes()
    if dias is None:
        return 'Indeterminado'
    if dias < 0:
        return f'Vencido há {abs(dias)} dia(s)'
    if dias == 0:
        return 'Vence hoje'
    return f'{dias} dia(s) restantes'


def _situacao_prazo_decisao(prazo: PrazoContrato) -> str:
    if prazo.status == PrazoContrato.Status.CONVERTIDO:
        return 'Convertido para indeterminado'
    if prazo.status == PrazoContrato.Status.ENCERRADO:
        return 'Encerrado'
    return formatar_situacao_prazo(prazo)


def serializar_prazo_decisao(prazo: PrazoContrato, *, post_url: str, perfil_url: str) -> dict:
    acoes = []
    for codigo in prazo.acoes_disponiveis():
        meta = ACOES_META.get(codigo, {})
        acoes.append({
            'codigo': codigo,
            'label': LABELS_ACAO.get(codigo, codigo),
            'precisa_data': meta.get('precisa_data', False),
            'motivo_obrigatorio': meta.get('motivo_obrigatorio', False),
            'danger': meta.get('danger', False),
        })

    limite = prazo.limite_legal_dias
    limite_texto = None
    if limite:
        limite_texto = (
            f'Limite legal de referência para {prazo.get_tipo_display().lower()}: '
            f'{limite} dias (desde o início do período original).'
        )

    renovacao = 'Original' if not prazo.renovacao_numero else f'Nº {prazo.renovacao_numero}'

    return {
        'id': prazo.pk,
        'colaborador_id': prazo.colaborador_id,
        'colaborador_nome': prazo.colaborador.nome,
        'tipo': prazo.get_tipo_display(),
        'vigencia': formatar_vigencia_prazo(prazo),
        'renovacao': renovacao,
        'situacao': _situacao_prazo_decisao(prazo),
        'data_fim_min': (
            prazo.data_fim.strftime('%Y-%m-%d')
            if prazo.data_fim
            else timezone.localdate().strftime('%Y-%m-%d')
        ),
        'limite_legal_dias': limite,
        'limite_legal_texto': limite_texto,
        'url_post': post_url,
        'url_perfil': perfil_url,
        'acoes': acoes,
    }
