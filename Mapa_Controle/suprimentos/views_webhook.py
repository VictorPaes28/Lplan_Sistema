"""
Views para receber webhooks do Sienge quando há mudanças.

Quando o Sienge suportar webhooks, este endpoint receberá notificações
de novos insumos, atualizações de SC/PC/NF, etc.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.conf import settings
import json
import hmac
import hashlib
from obras.models import Obra
from suprimentos.models import Insumo, ItemMapa, NotaFiscalEntrada
from suprimentos.services.sienge_provider import APISiengeProvider
from decimal import Decimal


@csrf_exempt
@require_http_methods(["POST"])
def webhook_sienge(request):
    """
    Endpoint para receber webhooks do Sienge.
    
    URL: /api/webhook/sienge/
    
    O Sienge deve enviar um POST com:
    - Headers: X-Sienge-Signature (HMAC SHA256)
    - Body: JSON com evento e dados
    
    Eventos suportados:
    - insumo.criado
    - insumo.atualizado
    - sc.criada
    - sc.atualizada
    - pc.criado
    - pc.atualizado
    - nf.entrada
    """
    # Verificar assinatura (segurança)
    signature = request.headers.get('X-Sienge-Signature', '')
    webhook_secret = getattr(settings, 'SIENGE_WEBHOOK_SECRET', '')
    
    if webhook_secret:
        # Calcular HMAC
        expected_signature = hmac.new(
            webhook_secret.encode(),
            request.body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return JsonResponse({'error': 'Assinatura inválida'}, status=401)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    evento = data.get('evento')
    payload = data.get('dados', {})
    
    try:
        with transaction.atomic():
            if evento == 'insumo.criado' or evento == 'insumo.atualizado':
                # Criar/atualizar insumo
                insumo, created = Insumo.objects.update_or_create(
                    codigo_sienge=payload.get('codigo_insumo'),
                    defaults={
                        'descricao': payload.get('descricao', ''),
                        'unidade': payload.get('unidade', 'UND'),
                        'categoria': payload.get('categoria', ''),
                        'tipo_insumo': payload.get('tipo_insumo', ''),
                        'especificacao_tecnica': payload.get('especificacao_tecnica', ''),
                        'fornecedor_padrao': payload.get('fornecedor_padrao', ''),
                        'preco_unitario': Decimal(str(payload.get('preco_unitario', 0) or 0)),
                        'moeda': payload.get('moeda', 'BRL'),
                        'ativo': payload.get('ativo', True)
                    }
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Insumo {"criado" if created else "atualizado"}',
                    'insumo_id': insumo.id
                })
            
            elif evento == 'sc.criada' or evento == 'sc.atualizada':
                # Atualizar ItemMapa com dados da SC
                obra_codigo = payload.get('codigo_obra')
                numero_sc = payload.get('numero_sc')
                
                try:
                    obra = Obra.objects.get(codigo_sienge=obra_codigo)
                except Obra.DoesNotExist:
                    return JsonResponse({'error': f'Obra {obra_codigo} não encontrada'}, status=404)
                
                # Buscar todos os itens com esta SC
                itens = ItemMapa.objects.filter(obra=obra, numero_sc=numero_sc)
                
                for item in itens:
                    item.data_sc = payload.get('data_sc')
                    item.save()
                
                return JsonResponse({
                    'success': True,
                    'message': f'SC {numero_sc} processada',
                    'itens_atualizados': itens.count()
                })
            
            elif evento == 'pc.criado' or evento == 'pc.atualizado':
                # Atualizar ItemMapa com dados do PC
                obra_codigo = payload.get('codigo_obra')
                numero_pc = payload.get('numero_pc')
                numero_sc = payload.get('numero_sc')
                
                try:
                    obra = Obra.objects.get(codigo_sienge=obra_codigo)
                except Obra.DoesNotExist:
                    return JsonResponse({'error': f'Obra {obra_codigo} não encontrada'}, status=404)
                
                # Buscar itens por SC (se tiver) ou PC
                if numero_sc:
                    itens = ItemMapa.objects.filter(obra=obra, numero_sc=numero_sc)
                else:
                    itens = ItemMapa.objects.filter(obra=obra, numero_pc=numero_pc)
                
                for item in itens:
                    item.numero_pc = numero_pc
                    item.data_pc = payload.get('data_pc')
                    item.empresa_fornecedora = payload.get('empresa_fornecedora', '')
                    item.prazo_recebimento = payload.get('prazo_recebimento')
                    item.save()
                
                return JsonResponse({
                    'success': True,
                    'message': f'PC {numero_pc} processado',
                    'itens_atualizados': itens.count()
                })
            
            elif evento == 'nf.entrada':
                # Criar/atualizar Nota Fiscal
                obra_codigo = payload.get('codigo_obra')
                numero_nf = payload.get('numero_nf')
                codigo_insumo = payload.get('codigo_insumo')
                
                try:
                    obra = Obra.objects.get(codigo_sienge=obra_codigo)
                    insumo = Insumo.objects.get(codigo_sienge=codigo_insumo)
                except (Obra.DoesNotExist, Insumo.DoesNotExist) as e:
                    return JsonResponse({'error': str(e)}, status=404)
                
                nf, created = NotaFiscalEntrada.objects.update_or_create(
                    obra=obra,
                    insumo=insumo,
                    numero_nf=numero_nf,
                    defaults={
                        'numero_pc': payload.get('numero_pc', ''),
                        'quantidade': Decimal(str(payload.get('quantidade', 0) or 0)),
                        'data_entrada': payload.get('data_entrada')
                    }
                )
                
                # Recalcular quantidade_recebida nos ItemMapa
                from django.db.models import Sum
                total_recebido = NotaFiscalEntrada.objects.filter(
                    obra=obra,
                    insumo=insumo
                ).aggregate(total=Sum('quantidade'))['total'] or Decimal('0.00')
                
                ItemMapa.objects.filter(obra=obra, insumo=insumo).update(
                    quantidade_recebida=total_recebido
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'NF {numero_nf} {"criada" if created else "atualizada"}',
                    'nf_id': nf.id
                })
            
            else:
                return JsonResponse({'error': f'Evento desconhecido: {evento}'}, status=400)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

