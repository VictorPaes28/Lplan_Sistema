from datetime import date, timedelta
from dataclasses import dataclass
from io import BytesIO

from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from recursos_humanos.models import Colaborador, ContratoAdmissao, PrazoContrato

MARCO_EXPERIENCIA_1 = 45
MARCO_EXPERIENCIA_2 = 90
ATENCAO_DIAS_ANTES_MARCO = 4
URGENTE_DIA_INICIO = 85
ANTECEDENCIA_PREVIEW_D45 = 15  # aviso a partir de D30 (15 dias antes do marco D45)

NOME_EXPERIENCIA_CLT = 'Período de experiência'
NOME_EXPERIENCIA_CLT_TIPO = 'Período de experiência (90 dias)'


@dataclass(frozen=True)
class SituacaoExperiencia:
    data_admissao: date
    dias_decorridos: int
    periodo: int
    periodo_label: str
    proximo_marco: int
    proximo_marco_data: date
    dias_restantes_marco: int
    prioridade: str
    decisao_status: str
    prazo_id: int | None


def colaborador_recebe_prazo_teste_clt(colaborador: Colaborador) -> bool:
    """Todo CLT contratado pela LPLAN tem prazo teste de 90 dias (marcos D45/D90)."""
    return (colaborador.tipo_contrato or 'CLT').upper() == 'CLT'


def obter_data_admissao_oficial(colaborador: Colaborador):
    """
    Data definitiva para marcos D45/D90 e prazos CLT.
    Única fonte: etapa 4 do fluxo (ContratoAdmissao.data_admissao_oficial).
    """
    try:
        contrato = colaborador.contrato_admissao
    except ContratoAdmissao.DoesNotExist:
        return None
    return contrato.data_admissao_oficial if contrato else None


def data_admissao_oficial_bloqueada(colaborador: Colaborador) -> bool:
    """CLT com data registrada na etapa 4 não pode alterar admissão pelo cadastro."""
    if not colaborador_recebe_prazo_teste_clt(colaborador):
        return False
    return obter_data_admissao_oficial(colaborador) is not None


def _decisao_status_experiencia(prazo: PrazoContrato | None) -> str:
    if not prazo:
        return 'pendente'
    if prazo.status == PrazoContrato.Status.CONVERTIDO:
        return 'efetivado'
    if prazo.status == PrazoContrato.Status.ENCERRADO:
        return 'desligado'
    if prazo.renovacao_numero >= 1:
        return 'prorrogado'
    return 'pendente'


def calcular_situacao_experiencia(
    colaborador: Colaborador,
    prazo: PrazoContrato | None = None,
) -> SituacaoExperiencia | None:
    """Calcula marcos D45/D90 a partir da data oficial de admissão (etapa 4)."""
    if colaborador.status == Colaborador.Status.DESLIGADO:
        return None
    if not colaborador_recebe_prazo_teste_clt(colaborador):
        return None

    if prazo is not None and (
        prazo.tipo != PrazoContrato.Tipo.EXPERIENCIA
        or prazo.status != PrazoContrato.Status.ATIVO
    ):
        return None

    if prazo is None:
        prazo = (
            colaborador.prazos_contrato.filter(
                status=PrazoContrato.Status.ATIVO,
                tipo=PrazoContrato.Tipo.EXPERIENCIA,
            )
            .order_by('-data_inicio', '-pk')
            .first()
        )

    if prazo is None:
        ultimo = (
            colaborador.prazos_contrato.filter(tipo=PrazoContrato.Tipo.EXPERIENCIA)
            .order_by('-pk')
            .first()
        )
        if ultimo and ultimo.status in (
            PrazoContrato.Status.CONVERTIDO,
            PrazoContrato.Status.ENCERRADO,
        ):
            return None
        data = obter_data_admissao_oficial(colaborador)
        if not data:
            return None
        renovacao = 0
        prazo_id = None
    else:
        data = obter_data_admissao_oficial(colaborador)
        if not data:
            return None
        renovacao = prazo.renovacao_numero
        prazo_id = prazo.pk

    hoje = timezone.localdate()
    dias_decorridos = (hoje - data).days

    if renovacao >= 1 or dias_decorridos >= MARCO_EXPERIENCIA_1:
        periodo = 2
        periodo_label = '2º período (D46–D90)'
    else:
        periodo = 1
        periodo_label = '1º período (D1–D45)'

    proximo_marco = MARCO_EXPERIENCIA_1 if periodo == 1 else MARCO_EXPERIENCIA_2
    proximo_marco_data = data + timedelta(days=proximo_marco)
    dias_restantes_marco = (proximo_marco_data - hoje).days

    if dias_decorridos > MARCO_EXPERIENCIA_2:
        prioridade = 'critico'
    elif periodo == 2 and dias_decorridos >= URGENTE_DIA_INICIO:
        prioridade = 'urgente'
    elif dias_restantes_marco < 0:
        prioridade = 'critico'
    elif 0 <= dias_restantes_marco <= ATENCAO_DIAS_ANTES_MARCO:
        prioridade = 'atencao'
    else:
        prioridade = 'normal'

    return SituacaoExperiencia(
        data_admissao=data,
        dias_decorridos=dias_decorridos,
        periodo=periodo,
        periodo_label=periodo_label,
        proximo_marco=proximo_marco,
        proximo_marco_data=proximo_marco_data,
        dias_restantes_marco=dias_restantes_marco,
        prioridade=prioridade,
        decisao_status=_decisao_status_experiencia(prazo),
        prazo_id=prazo_id,
    )


def prioridade_experiencia_para_urgencia(prioridade: str) -> str:
    return {
        'normal': 'green',
        'atencao': 'yellow',
        'urgente': 'red',
        'critico': 'red',
    }.get(prioridade, 'green')


def experiencia_deve_gerar_alerta(situacao: SituacaoExperiencia) -> bool:
    """Limiar de alerta: preview D30, atenção D41+, urgente D85+, marco vencido."""
    if situacao.prioridade in ('atencao', 'urgente', 'critico'):
        return True
    if situacao.dias_restantes_marco <= 7:
        return True
    if situacao.periodo == 1:
        dias_ate_d45 = MARCO_EXPERIENCIA_1 - situacao.dias_decorridos
        if 0 < dias_ate_d45 <= ANTECEDENCIA_PREVIEW_D45:
            return True
    return False


def experiencia_decisao_pendente(situacao: SituacaoExperiencia) -> bool:
    """Colaborador ainda aguarda decisão humana no período de experiência."""
    return situacao.decisao_status in ('pendente', 'prorrogado')


def prazo_teste_clt_deve_exibir(situacao: SituacaoExperiencia) -> bool:
    """
    Regra de tela: alertas, pendências na lista e export.
    Após D90, permanece visível enquanto a decisão estiver pendente (nunca some sozinho).
    """
    if situacao.dias_decorridos > MARCO_EXPERIENCIA_2 and experiencia_decisao_pendente(situacao):
        return True
    return experiencia_deve_gerar_alerta(situacao)


def texto_guia_decisao_experiencia(situacao: SituacaoExperiencia | None) -> str:
    if not situacao:
        return ''
    if situacao.periodo == 1:
        return (
            '1º período (até D45): prorrogar para o 2º período (até D90), '
            'efetivar antecipadamente em CLT indeterminado ou desligar.'
        )
    if situacao.dias_decorridos > MARCO_EXPERIENCIA_2:
        return (
            'Marco D90 ultrapassado sem decisão registrada. '
            'Efetive em CLT indeterminado ou desligue — este item permanece até a decisão.'
        )
    return (
        '2º período (até D90): efetive em CLT indeterminado ou desligue ao término.'
    )


def sincronizar_prazo_experiencia(
    colaborador: Colaborador,
    data_admissao,
    user=None,
) -> PrazoContrato | None:
    """Atualiza data de admissão e recalcula o prazo teste CLT (90 dias) ativo."""
    from .admissao_actions import _autor, registrar_historico

    if not colaborador_recebe_prazo_teste_clt(colaborador):
        return None

    colaborador.data_admissao = data_admissao
    colaborador.save(update_fields=['data_admissao', 'atualizado_em'])

    prazo_ativo = (
        colaborador.prazos_contrato.filter(
            status=PrazoContrato.Status.ATIVO,
            tipo=PrazoContrato.Tipo.EXPERIENCIA,
        )
        .order_by('-data_inicio', '-pk')
        .first()
    )

    data_fim = data_admissao + timedelta(days=MARCO_EXPERIENCIA_1)
    if prazo_ativo and prazo_ativo.renovacao_numero >= 1:
        data_fim = data_admissao + timedelta(days=MARCO_EXPERIENCIA_2)

    if prazo_ativo:
        prazo_ativo.data_inicio = data_admissao
        prazo_ativo.data_fim = data_fim
        prazo_ativo.save(update_fields=['data_inicio', 'data_fim'])
        prazo = prazo_ativo
    else:
        prazo = criar_prazo_contrato(
            colaborador,
            PrazoContrato.Tipo.EXPERIENCIA,
            data_admissao,
            data_fim,
        )

    if user:
        autor = _autor(user)
        registrar_historico(
            colaborador,
            colaborador.etapa_admissao,
            (
                f'Data de admissão oficial: {data_admissao.strftime("%d/%m/%Y")}. '
                f'{NOME_EXPERIENCIA_CLT} atualizado até {data_fim.strftime("%d/%m/%Y")}.'
            ),
            autor,
        )
    return prazo


def garantir_prazo_teste_clt_colaborador(colaborador: Colaborador) -> PrazoContrato | None:
    """Garante registro ativo de prazo teste para um CLT com data de admissão."""
    if colaborador.status != Colaborador.Status.ATIVO:
        return None
    if not colaborador_recebe_prazo_teste_clt(colaborador):
        return None
    if colaborador.prazos_contrato.filter(
        status=PrazoContrato.Status.ATIVO,
        tipo=PrazoContrato.Tipo.EXPERIENCIA,
    ).exists():
        return None
    data = obter_data_admissao_oficial(colaborador)
    if not data:
        return None
    return sincronizar_prazo_experiencia(colaborador, data, user=None)


def sincronizar_datas_prazos_experiencia() -> int:
    """Alinha data_inicio/data_fim do prazo à admissão oficial (sem efetivar automaticamente)."""
    atualizados = 0
    prazos = PrazoContrato.objects.filter(
        status=PrazoContrato.Status.ATIVO,
        tipo=PrazoContrato.Tipo.EXPERIENCIA,
        colaborador__status=Colaborador.Status.ATIVO,
        colaborador__tipo_contrato__iexact='CLT',
    ).select_related('colaborador', 'colaborador__contrato_admissao')
    for prazo in prazos.iterator():
        data = obter_data_admissao_oficial(prazo.colaborador)
        if not data:
            continue
        data_fim = data + timedelta(days=MARCO_EXPERIENCIA_1)
        if prazo.renovacao_numero >= 1:
            data_fim = data + timedelta(days=MARCO_EXPERIENCIA_2)
        if prazo.data_inicio != data or prazo.data_fim != data_fim:
            prazo.data_inicio = data
            prazo.data_fim = data_fim
            prazo.save(update_fields=['data_inicio', 'data_fim'])
            atualizados += 1
    return atualizados


def encerrar_prazos_teste_clt_expirados() -> int:
    """Compatibilidade: apenas sincroniza datas oficiais; nunca efetiva sem decisão humana."""
    return sincronizar_datas_prazos_experiencia()


def garantir_prazos_teste_clt_ativos() -> int:
    """Cria prazo teste para CLTs ativos com data oficial ainda sem registro ativo."""
    criados = 0
    colaboradores = Colaborador.objects.filter(
        status=Colaborador.Status.ATIVO,
        tipo_contrato__iexact='CLT',
        contrato_admissao__data_admissao_oficial__isnull=False,
    )
    for colaborador in colaboradores.iterator():
        if garantir_prazo_teste_clt_colaborador(colaborador):
            criados += 1
    return criados


def aplicar_data_admissao_oficial(
    colaborador: Colaborador,
    data_admissao,
    user,
) -> tuple[bool, str]:
    from .contrato import obter_ou_criar_contrato

    if not data_admissao:
        return False, 'Informe a data de admissão.'
    contrato = obter_ou_criar_contrato(colaborador)
    contrato.data_admissao_oficial = data_admissao
    contrato.save(update_fields=['data_admissao_oficial'])
    sincronizar_prazo_experiencia(colaborador, data_admissao, user)
    return True, 'Data de admissão registrada.'


def formatar_progresso_prazo_teste_clt(situacao: SituacaoExperiencia) -> str:
    """Progresso legível na tela: 41/45 no 1º período, 47/90 no 2º (D1 = dia da admissão)."""
    dia = situacao.dias_decorridos + 1
    if situacao.periodo == 1:
        return f'{min(dia, MARCO_EXPERIENCIA_1)}/{MARCO_EXPERIENCIA_1}'
    return f'{dia}/{MARCO_EXPERIENCIA_2}'


def formatar_progresso_prazo_ativo(prazo: PrazoContrato, *, hoje=None) -> str | None:
    """Progresso dia/total para contratos com data fim (D1 = dia da admissão/início)."""
    if not prazo.data_fim:
        return None
    ref = hoje or timezone.localdate()
    total = max((prazo.data_fim - prazo.data_inicio).days + 1, 1)
    dia = max(1, min((ref - prazo.data_inicio).days + 1, total))
    return f'{dia}/{total}'


def pct_progresso_texto(progresso: str) -> int:
    """Converte '42/45' em percentual para barra de progresso (0–100)."""
    if '/' not in progresso:
        return 0
    atual_str, total_str = progresso.split('/', 1)
    try:
        atual = int(atual_str)
        total = int(total_str)
    except ValueError:
        return 0
    if total <= 0:
        return 0
    return max(0, min(100, round(atual / total * 100)))


def serializar_experiencia_perfil(situacao: SituacaoExperiencia | None) -> dict | None:
    if not situacao:
        return None
    return {
        'data_admissao': situacao.data_admissao.strftime('%d/%m/%Y'),
        'dias_decorridos': situacao.dias_decorridos,
        'periodo': situacao.periodo,
        'periodo_label': situacao.periodo_label,
        'proximo_marco': situacao.proximo_marco,
        'proximo_marco_data': situacao.proximo_marco_data.strftime('%d/%m/%Y'),
        'dias_restantes_marco': situacao.dias_restantes_marco,
        'prioridade': situacao.prioridade,
        'decisao_status': situacao.decisao_status,
        'progresso': formatar_progresso_prazo_teste_clt(situacao),
    }



LABELS_ACAO = {
    'efetivar': 'Efetivar (CLT indeterminado)',
    'prorrogar': 'Prorrogar para o 2º período (até D90)',
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
            f'{NOME_EXPERIENCIA_CLT} concluído. Colaborador efetivado em CLT indeterminado.',
            autor,
        )
        registrar_decisao_prazo(prazo, acao, user, motivo=motivo)
        return True, 'Colaborador efetivado com sucesso.'

    if acao == 'prorrogar':
        if not nova_data_fim:
            if prazo.tipo == PrazoContrato.Tipo.EXPERIENCIA:
                data_base = obter_data_admissao_oficial(colaborador) or prazo.data_inicio
                nova_data_fim = data_base + timedelta(days=MARCO_EXPERIENCIA_2)
            else:
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
            f'{NOME_EXPERIENCIA_CLT} prorrogado até {nova_data_fim.strftime("%d/%m/%Y")}.',
            autor,
        )
        registrar_decisao_prazo(prazo, acao, user, motivo=motivo, observacoes=f'Novo prazo até {nova_data_fim:%d/%m/%Y}')
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
        registrar_decisao_prazo(prazo, acao, user, motivo=motivo)
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
        registrar_decisao_prazo(
            prazo, acao, user, motivo=motivo,
            observacoes=f'Novo prazo até {nova_data_fim:%d/%m/%Y}',
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
            registrar_decisao_prazo(prazo, acao, user, motivo=motivo)
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
            registrar_decisao_prazo(prazo, acao, user, motivo=motivo)
        return True, 'Contrato encerrado e colaborador desligado.'

    return False, 'Ação não reconhecida.'


def registrar_decisao_prazo(
    prazo: PrazoContrato,
    acao: str,
    user,
    *,
    motivo: str = '',
    observacoes: str = '',
) -> None:
    from recursos_humanos.models import DecisaoPrazoContrato

    DecisaoPrazoContrato.objects.create(
        prazo_contrato=prazo,
        colaborador=prazo.colaborador,
        acao=acao,
        usuario=user if getattr(user, 'is_authenticated', False) else None,
        motivo=(motivo or '').strip(),
        observacoes=(observacoes or '').strip(),
    )


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
    """Prazo para exibir no perfil: teste CLT > ativo > convertido/encerrado."""
    if colaborador_recebe_prazo_teste_clt(colaborador):
        prazo_teste = colaborador.prazos_contrato.filter(
            tipo=PrazoContrato.Tipo.EXPERIENCIA,
        ).order_by('-data_inicio', '-pk').first()
        if prazo_teste:
            return prazo_teste
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
    pode_decidir = ativo

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
    if prazo.tipo == PrazoContrato.Tipo.EXPERIENCIA and ativo:
        sit = calcular_situacao_experiencia(prazo.colaborador, prazo)
        data['prazo_teste_clt'] = serializar_experiencia_perfil(sit)
        data['experiencia'] = data['prazo_teste_clt']
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
        meta = dict(ACOES_META.get(codigo, {}))
        if codigo == 'prorrogar' and prazo.tipo == PrazoContrato.Tipo.EXPERIENCIA:
            meta['precisa_data'] = False
        acoes.append({
            'codigo': codigo,
            'label': LABELS_ACAO.get(codigo, codigo),
            'precisa_data': meta.get('precisa_data', False),
            'motivo_obrigatorio': meta.get('motivo_obrigatorio', False),
            'danger': meta.get('danger', False),
        })

    limite = prazo.limite_legal_dias
    limite_texto = None
    data_fim_sugerida = None
    experiencia = None
    guia_texto = ''
    if prazo.tipo == PrazoContrato.Tipo.EXPERIENCIA and prazo.status == PrazoContrato.Status.ATIVO:
        sit = calcular_situacao_experiencia(prazo.colaborador, prazo)
        if sit:
            experiencia = serializar_experiencia_perfil(sit)
            guia_texto = texto_guia_decisao_experiencia(sit)
    if limite:
        limite_texto = (
            f'Limite legal de referência para {prazo.get_tipo_display().lower()}: '
            f'{limite} dias (desde o início do período original).'
        )
    if prazo.tipo == PrazoContrato.Tipo.EXPERIENCIA and 'prorrogar' in prazo.acoes_disponiveis():
        data_base = obter_data_admissao_oficial(prazo.colaborador) or prazo.data_inicio
        data_fim_sugerida = (data_base + timedelta(days=MARCO_EXPERIENCIA_2)).strftime('%Y-%m-%d')

    renovacao = 'Original' if not prazo.renovacao_numero else f'Nº {prazo.renovacao_numero}'
    ultima_decisao = None
    from recursos_humanos.models import DecisaoPrazoContrato
    dec = (
        DecisaoPrazoContrato.objects.filter(prazo_contrato=prazo)
        .select_related('usuario')
        .order_by('-registrado_em')
        .first()
    )
    if dec:
        ultima_decisao = {
            'acao': dec.get_acao_display(),
            'por': dec.usuario.get_full_name() if dec.usuario else '—',
            'em': timezone.localtime(dec.registrado_em).strftime('%d/%m/%Y %H:%M'),
            'motivo': dec.motivo,
        }

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
        'data_fim_sugerida': data_fim_sugerida,
        'url_post': post_url,
        'url_perfil': perfil_url,
        'acoes': acoes,
        'experiencia': experiencia,
        'guia_texto': guia_texto,
        'ultima_decisao': ultima_decisao,
    }
