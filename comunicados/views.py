"""
APIs JSON para comunicados administrativos (pendentes e registro de interações).
"""
import json

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import login_required

from .models import (
    Comunicado,
    ComunicadoResposta,
    ComunicadoVisualizacao,
    StatusFinalVisualizacao,
)
from .services import contar_pendentes, primeiro_pendente_e_total


def _comunicado_publico_json(comunicado: Comunicado, request) -> dict:
    imagem_url = ''
    if comunicado.imagem:
        imagem_url = request.build_absolute_uri(comunicado.imagem.url)
    link = comunicado.link_destino or ''
    return {
        'id': comunicado.pk,
        'tipo_conteudo': comunicado.tipo_conteudo,
        'titulo_visivel': comunicado.titulo_visivel or '',
        'subtitulo': comunicado.subtitulo or '',
        'texto_principal': comunicado.texto_principal or '',
        'imagem_url': imagem_url,
        'link_destino': link,
        'texto_botao': comunicado.texto_botao or '',
        'destaque_visual': comunicado.destaque_visual,
        'pode_fechar': comunicado.pode_fechar,
        'exige_confirmacao': comunicado.exige_confirmacao,
        'exige_resposta': comunicado.exige_resposta,
        'bloquear_ate_acao': comunicado.bloquear_ate_acao,
        'permitir_nao_mostrar_novamente': comunicado.permitir_nao_mostrar_novamente,
        'prioridade': comunicado.prioridade,
    }


@login_required
@require_GET
def api_pendentes(request):
    primeiro, total = primeiro_pendente_e_total(request.user)
    if total == 0:
        return JsonResponse(
            {
                'tem_pendente': False,
                'total_pendentes': 0,
                'comunicado': None,
            }
        )
    return JsonResponse(
        {
            'tem_pendente': True,
            'total_pendentes': total,
            'comunicado': _comunicado_publico_json(primeiro, request),
        }
    )


ACOES_REGISTRO = frozenset(
    {'visualizou', 'fechou', 'confirmou', 'respondeu', 'nao_mostrar_novamente'}
)


@login_required
@require_POST
def api_registrar(request):
    try:
        body = json.loads(request.body.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'sucesso': False, 'erro': 'JSON inválido.'}, status=400)

    try:
        comunicado_id = int(body.get('comunicado_id'))
    except (TypeError, ValueError):
        return JsonResponse({'sucesso': False, 'erro': 'comunicado_id inválido.'}, status=400)

    acao = body.get('acao')
    if acao not in ACOES_REGISTRO:
        return JsonResponse({'sucesso': False, 'erro': 'acao inválida.'}, status=400)

    resposta_texto = body.get('resposta') or ''
    if acao == 'respondeu' and not str(resposta_texto).strip():
        return JsonResponse(
            {'sucesso': False, 'erro': 'Campo resposta é obrigatório para ação respondeu.'},
            status=400,
        )

    try:
        comunicado = Comunicado.objects.get(pk=comunicado_id)
    except Comunicado.DoesNotExist:
        return JsonResponse({'sucesso': False, 'erro': 'Comunicado não encontrado.'}, status=404)

    user = request.user

    with transaction.atomic():
        vis, _created = ComunicadoVisualizacao.objects.get_or_create(
            comunicado=comunicado,
            usuario=user,
        )

        if acao == 'visualizou':
            vis.total_visualizacoes = vis.total_visualizacoes + 1
            vis.save()

        elif acao == 'fechou':
            vis.fechou = True
            if vis.status_final == StatusFinalVisualizacao.PENDENTE:
                vis.status_final = StatusFinalVisualizacao.VISUALIZADO
            vis.save()

        elif acao == 'confirmou':
            vis.confirmou_leitura = True
            vis.status_final = StatusFinalVisualizacao.CONFIRMADO
            vis.save()

        elif acao == 'respondeu':
            vis.respondeu = True
            agora = timezone.now()
            vis.data_resposta = agora
            vis.status_final = StatusFinalVisualizacao.RESPONDIDO
            vis.save()
            ComunicadoResposta.objects.create(
                comunicado=comunicado,
                usuario=user,
                resposta=str(resposta_texto).strip(),
            )

        elif acao == 'nao_mostrar_novamente':
            vis.fechou = True
            vis.status_final = StatusFinalVisualizacao.IGNORADO
            vis.save()

    proximo = contar_pendentes(user) > 0
    return JsonResponse({'sucesso': True, 'proximo_pendente': proximo})
