from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.db import transaction
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.exceptions import ValidationError
from accounts.decorators import require_group
from accounts.groups import GRUPOS
from mapa_obras.models import Obra, LocalObra
from .models import ItemMapa, NotaFiscalEntrada, AlocacaoRecebimento, Insumo, RecebimentoObra, HistoricoAlteracao
from django.db.models import Q, Sum
from decimal import Decimal
from uuid import uuid4
import json


@login_required
@require_http_methods(["GET"])
def item_detalhe(request, item_id):
    """Retorna detalhes do item para modal."""
    item = get_object_or_404(ItemMapa, id=item_id)
    
    # Validar que o item pertence à obra da sessão
    obra_sessao_id = request.session.get('obra_id')
    if not request.user.is_superuser:
        if obra_sessao_id and int(obra_sessao_id) != item.obra_id:
            return JsonResponse({'success': False, 'error': 'Item não pertence à obra selecionada.'}, status=403)
    
    # Buscar RecebimentoObra vinculado
    recebimento = item.recebimento_vinculado
    
    # Buscar NFs relacionadas
    nfs = NotaFiscalEntrada.objects.filter(
        obra=item.obra,
        insumo=item.insumo
    ).order_by('-data_entrada')
    
    # Buscar alocações DESTE item
    alocacoes = AlocacaoRecebimento.objects.filter(
        item_mapa=item
    ).select_related('local_aplicacao', 'criado_por').order_by('-data_alocacao')
    
    # Calcular quantidades
    qtd_recebida_obra = item.quantidade_recebida_obra
    qtd_alocada_local = item.quantidade_alocada_local
    qtd_planejada = item.quantidade_planejada
    # Falta Alocar: baseado no que foi recebido na obra, não no planejado
    saldo_a_alocar = max(qtd_recebida_obra - qtd_alocada_local, Decimal('0.00'))
    
    from accounts.groups import GRUPOS
    pode_excluir = (
        request.user.is_superuser or
        request.user.groups.filter(name=GRUPOS.ENGENHARIA).exists()
    )

    # HTML do modal
    html = f"""
    <div class="row">
        <div class="col-md-6">
            <h6 class="border-bottom pb-2 mb-3"><i class="bi bi-info-circle"></i> Informações do Item</h6>
    <div class="detalhe-item">
        <div class="detalhe-label">Obra:</div>
        <div class="detalhe-valor">{item.obra.nome}</div>
    </div>
    <div class="detalhe-item">
        <div class="detalhe-label">Insumo:</div>
        <div class="detalhe-valor">{item.descricao_override or item.insumo.descricao}</div>
    </div>
    <div class="detalhe-item">
        <div class="detalhe-label">Categoria:</div>
        <div class="detalhe-valor">{item.categoria}</div>
    </div>
    <div class="detalhe-item">
                <div class="detalhe-label">Local Aplicação:</div>
                <div class="detalhe-valor"><strong>{item.local_aplicacao.nome if item.local_aplicacao else 'Não definido'}</strong></div>
    </div>
    <div class="detalhe-item">
        <div class="detalhe-label">Quantidade Planejada:</div>
                <div class="detalhe-valor"><strong>{qtd_planejada}</strong> {item.insumo.unidade}</div>
    </div>
    <div class="detalhe-item">
        <div class="detalhe-label">Prazo Necessidade:</div>
        <div class="detalhe-valor">{item.prazo_necessidade or '-'}</div>
    </div>
        </div>
        <div class="col-md-6">
            <h6 class="border-bottom pb-2 mb-3"><i class="bi bi-truck"></i> Status de Entrega</h6>
    <div class="detalhe-item">
        <div class="detalhe-label">Nº SC:</div>
                <div class="detalhe-valor">{item.numero_sc or '<span class="text-muted">Não lançada</span>'}</div>
    </div>
    <div class="detalhe-item">
        <div class="detalhe-label">Nº PC:</div>
                <div class="detalhe-valor">{item.numero_pc or (recebimento.numero_pc if recebimento else '-') or '<span class="text-muted">-</span>'}</div>
    </div>
    <div class="detalhe-item">
        <div class="detalhe-label">Fornecedor:</div>
                <div class="detalhe-valor">{item.empresa_fornecedora or (recebimento.empresa_fornecedora if recebimento else '-') or '-'}</div>
    </div>
    <div class="detalhe-item">
        <div class="detalhe-label">Prazo Recebimento:</div>
                <div class="detalhe-valor">{item.prazo_recebimento or (recebimento.prazo_recebimento if recebimento else '-') or '-'}</div>
            </div>
        </div>
    </div>
    
    <hr>
    
    <h6 class="border-bottom pb-2 mb-3"><i class="bi bi-box-seam"></i> Quantidades</h6>
    <div class="alert alert-info py-2">
        <div class="row text-center">
            <div class="col-4">
                <div class="small text-muted">Recebido na Obra</div>
                <div class="h5 mb-0">{qtd_recebida_obra} {item.insumo.unidade}</div>
                <small class="text-muted">(Sienge)</small>
            </div>
            <div class="col-4">
                <div class="small text-muted">Alocado p/ este Local</div>
                <div class="h5 mb-0 {'text-success' if qtd_alocada_local >= qtd_planejada else 'text-warning'}">{qtd_alocada_local} {item.insumo.unidade}</div>
                <small class="text-muted">(Manual)</small>
            </div>
            <div class="col-4">
                <div class="small text-muted">Falta Alocar</div>
                <div class="h5 mb-0 {'text-success' if saldo_a_alocar == 0 else 'text-danger'}">{saldo_a_alocar} {item.insumo.unidade}</div>
            </div>
    </div>
    </div>
    """

    if pode_excluir:
        html += f"""
        <div class="d-flex justify-content-end gap-2 mt-2">
            <button type="button"
                    class="btn btn-sm btn-outline-danger"
                    data-action="delete-item"
                    data-item-id="{item.id}"
                    data-delete-url="/api/internal/item/{item.id}/excluir/">
                <i class="bi bi-trash"></i> Excluir Item
            </button>
        </div>
        """
    
    # Histórico de alocações
    if alocacoes.exists():
        html += """
        <h6 class="border-bottom pb-2 mb-3"><i class="bi bi-list-check"></i> Alocações Realizadas</h6>
        <table class="table table-sm">
            <thead>
                <tr>
                    <th>Data</th>
                    <th>Quantidade</th>
                    <th>Por</th>
                    <th>Obs</th>
                </tr>
            </thead>
            <tbody>
        """
        for aloc in alocacoes:
            html += f"""
                <tr>
                    <td>{aloc.data_alocacao.strftime('%d/%m/%Y %H:%M')}</td>
                    <td><strong>{aloc.quantidade_alocada}</strong> {item.insumo.unidade}</td>
                    <td>{aloc.criado_por.username if aloc.criado_por else '-'}</td>
                    <td>{aloc.observacao or '-'}</td>
                </tr>
            """
        html += """
            </tbody>
        </table>
        """
    
    # Notas Fiscais
    if nfs.exists():
        html += """
        <h6 class="border-bottom pb-2 mb-3"><i class="bi bi-receipt"></i> Notas Fiscais</h6>
        <table class="table table-sm">
            <thead>
                <tr>
                    <th>NF</th>
                    <th>Data</th>
                    <th>Quantidade</th>
                </tr>
            </thead>
            <tbody>
        """
        for nf in nfs:
            html += f"""
                <tr>
                    <td>{nf.numero_nf}</td>
                    <td>{nf.data_entrada.strftime('%d/%m/%Y') if nf.data_entrada else '-'}</td>
                    <td>{nf.quantidade} {item.insumo.unidade}</td>
                </tr>
            """
        html += """
            </tbody>
        </table>
        """
    
    return JsonResponse({'html': html})


@login_required
@require_group(GRUPOS.ENGENHARIA)
@require_http_methods(["POST"])
@ensure_csrf_cookie
def item_excluir(request, item_id):
    """Exclui um item do mapa (engenharia)."""
    item = get_object_or_404(ItemMapa, id=item_id)

    # Segregação: só permitir excluir itens da obra atual da sessão (exceto superuser)
    obra_sessao_id = request.session.get('obra_id')
    if not request.user.is_superuser:
        if not obra_sessao_id or int(obra_sessao_id) != item.obra_id:
            return JsonResponse({'success': False, 'error': 'Obra inválida para exclusão.'}, status=403)

    # Capturar contexto antes de deletar
    desc = item.descricao_override or (item.insumo.descricao if item.insumo else 'Item')
    local = item.local_aplicacao.nome if item.local_aplicacao else '-'
    tinha_sc = bool((item.numero_sc or '').strip())
    tinha_alocacoes = AlocacaoRecebimento.objects.filter(item_mapa=item).exists()

    with transaction.atomic():
        # Registrar histórico (FK item_mapa ficará NULL após a exclusão por SET_NULL)
        HistoricoAlteracao.registrar(
            obra=item.obra,
            usuario=request.user,
            tipo='EXCLUSAO',
            descricao=f'Item excluído: "{desc}" (Categoria: {item.categoria}) - Local: {local}',
            item_mapa=item,
            campo_alterado='exclusao',
            valor_anterior='',
            valor_novo='EXCLUIDO',
            ip_address=request.META.get('REMOTE_ADDR')
        )

        item.delete()

    aviso = None
    if tinha_sc or tinha_alocacoes:
        aviso = 'Item excluído. Atenção: ele tinha vínculo com SC e/ou alocações (histórico preservado).'

    return JsonResponse({'success': True, 'message': aviso or 'Item excluído com sucesso.'})


@login_required
@require_group(GRUPOS.ENGENHARIA)
def item_alocacoes_json(request, item_id):
    """Retorna alocações do item em formato JSON."""
    item = get_object_or_404(ItemMapa, id=item_id)
    
    # Validar que o item pertence à obra da sessão
    obra_sessao_id = request.session.get('obra_id')
    if not request.user.is_superuser:
        if obra_sessao_id and int(obra_sessao_id) != item.obra_id:
            return JsonResponse({'success': False, 'error': 'Item não pertence à obra selecionada.'}, status=403)
    
    alocacoes = AlocacaoRecebimento.objects.filter(
        item_mapa=item
    ).select_related('local_aplicacao', 'criado_por').order_by('-data_alocacao')
    
    alocacoes_data = [{
        'id': a.id,
        'quantidade_alocada': str(a.quantidade_alocada),
        'data_alocacao': a.data_alocacao.isoformat(),
        'criado_por': a.criado_por.get_full_name() if a.criado_por else 'Sistema',
        'local_aplicacao': a.local_aplicacao.nome if a.local_aplicacao else 'Não definido'
    } for a in alocacoes]
    
    return JsonResponse({
        'alocacoes': alocacoes_data,
        'total': len(alocacoes_data)
    })


@login_required
@require_group(GRUPOS.ENGENHARIA)
@require_http_methods(["POST"])
@ensure_csrf_cookie
def item_atualizar_campo(request):
    """Atualiza um campo do item via AJAX."""
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        field = data.get('field')
        value = data.get('value')
        
        if not item_id or not field:
            return JsonResponse({'success': False, 'error': 'Dados incompletos'}, status=400)
        
        item = get_object_or_404(ItemMapa, id=item_id)
        
        # Validar que o item pertence à obra da sessão
        obra_sessao_id = request.session.get('obra_id')
        if not request.user.is_superuser:
            if not obra_sessao_id or int(obra_sessao_id) != item.obra_id:
                return JsonResponse({'success': False, 'error': 'Sem permissão para editar itens desta obra.'}, status=403)
        
        # Campos permitidos para edição
        campos_permitidos = [
            'insumo', 'insumo_codigo', 'insumo_unidade', 'local_aplicacao', 'responsavel', 'prazo_necessidade',
            'quantidade_planejada', 'prioridade', 'observacao_eng', 'numero_sc',
            'categoria', 'descricao_override', 'empresa_fornecedora'  # Categoria de aplicação e descrição alternativa
        ]
        
        if field not in campos_permitidos:
            return JsonResponse({'success': False, 'error': 'Campo não permitido'}, status=403)
        
        # Guardar valor anterior para histórico
        valor_anterior = getattr(item, field, '')
        if field == 'local_aplicacao' and item.local_aplicacao:
            valor_anterior = item.local_aplicacao.nome
        elif field == 'insumo' and item.insumo:
            valor_anterior = item.insumo.descricao
        elif field == 'insumo_unidade' and item.insumo:
            valor_anterior = item.insumo.unidade
        
        # Labels amigáveis para os campos
        campo_labels = {
            'insumo': 'Insumo',
            'insumo_codigo': 'Código Insumo',
            'insumo_unidade': 'Unidade',
            'local_aplicacao': 'Local',
            'responsavel': 'Responsável',
            'prazo_necessidade': 'Prazo',
            'quantidade_planejada': 'Quantidade',
            'prioridade': 'Prioridade',
            'observacao_eng': 'Observação',
            'numero_sc': 'Nº SC',
            'categoria': 'Categoria',
            'descricao_override': 'Descrição',
            'empresa_fornecedora': 'Empresa Responsável',
        }
        
        # Atualizar campo
        valor_novo = value
        
        # IMPORTANTE: Garantir que value seja tratado corretamente para campos ForeignKey
        # Se o campo for local_aplicacao, processar primeiro para evitar atribuição incorreta
        if field == 'local_aplicacao':
            # Processar local_aplicacao ANTES de qualquer outra coisa
            # IMPORTANTE: value pode vir como string '4' ou inteiro 4 do JavaScript
            # NUNCA atribuir value diretamente - sempre buscar a instância primeiro
            
            # Verificar se value existe e não é vazio
            if value is not None and value != '':
                try:
                    # Converter para string e depois para inteiro
                    value_str = str(value).strip()
                    if value_str and value_str != '' and value_str != '0':
                        local_id = int(value_str)
                        
                        if local_id > 0:
                            # Buscar LocalObra pelo ID - get_object_or_404 retorna a instância
                            try:
                                local = LocalObra.objects.get(id=local_id)
                                
                                # Validar se local pertence à obra do item
                                if local.obra_id != item.obra_id:
                                    return JsonResponse({
                                        'success': False,
                                        'error': 'Local não pertence à obra do item'
                                    }, status=400)
                                
                                # Atribuir a INSTÂNCIA do LocalObra (não o ID!)
                                item.local_aplicacao = local
                                valor_novo = local.nome
                            except LocalObra.DoesNotExist:
                                return JsonResponse({
                                    'success': False,
                                    'error': f'Local com ID {local_id} não encontrado'
                                }, status=404)
                        else:
                            # ID inválido (0 ou negativo) - limpar
                            item.local_aplicacao = None
                            valor_novo = '(vazio)'
                    else:
                        # String vazia - limpar local
                        item.local_aplicacao = None
                        valor_novo = '(vazio)'
                except (ValueError, TypeError) as e:
                    # Erro na conversão - retornar erro
                    return JsonResponse({
                        'success': False,
                        'error': f'ID do local inválido: {value}'
                    }, status=400)
            else:
                # Valor None ou vazio - limpar local
                item.local_aplicacao = None
                valor_novo = '(vazio)'
                # Valor None ou vazio - limpar local
                item.local_aplicacao = None
                valor_novo = '(vazio)'
        elif field == 'insumo_codigo':
            # Editar código do insumo - sempre editável
            # IMPORTANTE: A chave de ligação é SC + código do produto
            codigo_novo = (value or '').strip()
            
            # Verificar se já existe insumo com esse código
            insumo_existente = Insumo.objects.filter(codigo_sienge=codigo_novo).first()
            
            if insumo_existente:
                # Se existe no banco, vincular o ItemMapa a esse insumo
                item.insumo = insumo_existente
                valor_novo = codigo_novo
            else:
                # Se não existe, manter o código inserido (pode existir no futuro)
                # Atualizar o código do insumo atual
                insumo_atual = item.insumo
                outros_itens = ItemMapa.objects.filter(insumo=insumo_atual).exclude(id=item.id)
                
                if outros_itens.exists():
                    # Se outros itens usam esse insumo, criar um novo insumo com o código inserido
                    novo_insumo = Insumo.objects.create(
                        codigo_sienge=codigo_novo if codigo_novo else f'SM-LEV-{insumo_atual.id}',
                        descricao=insumo_atual.descricao,
                        unidade=insumo_atual.unidade,
                        ativo=True,
                        eh_macroelemento=insumo_atual.eh_macroelemento
                    )
                    item.insumo = novo_insumo
                    valor_novo = codigo_novo if codigo_novo else novo_insumo.codigo_sienge
                else:
                    # Se só este item usa, atualizar o código do insumo existente
                    # Se código vazio, manter provisório ou gerar novo
                    if not codigo_novo:
                        if not (insumo_atual.codigo_sienge or '').startswith('SM-LEV-'):
                            # Se tinha código e foi limpo, gerar provisório
                            codigo_novo = f'SM-LEV-{uuid4().hex[:10].upper()}'
                    
                    insumo_atual.codigo_sienge = codigo_novo
                    insumo_atual.save(update_fields=['codigo_sienge', 'updated_at'])
                    valor_novo = codigo_novo
        elif field == 'insumo_unidade':
            # Editar unidade do insumo
            if not item.insumo:
                return JsonResponse({'success': False, 'error': 'Item não possui insumo vinculado'}, status=400)
            
            unidade_nova = (value or '').strip().upper()[:20]  # Limitar a 20 caracteres e converter para maiúsculo
            # Deixar vazio se não informado - não preencher automaticamente
            
            insumo_atual = item.insumo
            valor_anterior = insumo_atual.unidade
            
            # Verificar se outros itens usam esse insumo
            outros_itens = ItemMapa.objects.filter(insumo=insumo_atual).exclude(id=item.id)
            
            if outros_itens.exists():
                # Se outros itens usam esse insumo, criar um novo insumo com a unidade editada
                novo_insumo = Insumo.objects.create(
                    codigo_sienge=insumo_atual.codigo_sienge,
                    descricao=insumo_atual.descricao,
                    unidade=unidade_nova,
                    ativo=True,
                    eh_macroelemento=insumo_atual.eh_macroelemento
                )
                item.insumo = novo_insumo
                valor_novo = unidade_nova
            else:
                # Se só este item usa, atualizar a unidade do insumo existente
                insumo_atual.unidade = unidade_nova
                insumo_atual.save(update_fields=['unidade', 'updated_at'])
                valor_novo = unidade_nova
        elif field == 'insumo':
            insumo = get_object_or_404(Insumo, id=value)
            item.insumo = insumo
            valor_novo = insumo.descricao
        elif field == 'prazo_necessidade':
            from datetime import datetime
            if value:
                try:
                    item.prazo_necessidade = datetime.strptime(value, '%Y-%m-%d').date()
                    valor_novo = item.prazo_necessidade.strftime('%d/%m/%Y')
                except ValueError:
                    return JsonResponse({'success': False, 'error': 'Data inválida'}, status=400)
            else:
                item.prazo_necessidade = None
                valor_novo = '(vazio)'
        elif field == 'quantidade_planejada':
            from decimal import Decimal as D
            try:
                qtd = D(str(value))
                if qtd < 0:
                    return JsonResponse({
                        'success': False,
                        'error': 'Quantidade não pode ser negativa'
                    }, status=400)
                item.quantidade_planejada = qtd
                valor_novo = str(qtd)
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'Valor inválido'}, status=400)
        elif field == 'categoria':
            # Lista fechada (LPLAN)
            categorias_validas = {v for v, _ in ItemMapa.CATEGORIA_CHOICES}
            valor = (value or '').strip()
            if not valor:
                valor = 'A CLASSIFICAR'
            # Normalizar múltiplos espaços
            valor = ' '.join(valor.split())
            if valor not in categorias_validas:
                return JsonResponse({'success': False, 'error': 'Categoria inválida'}, status=400)
            item.categoria = valor
            valor_novo = valor
        elif field == 'numero_sc':
            # Permitir edição do número SC pela engenharia
            item.numero_sc = value.strip() if value else ''
            valor_novo = item.numero_sc or '(vazio)'
            # Auto-vincular a linha correta do Sienge quando:
            # - o insumo ainda é provisório (SM-LEV-*) OU
            # - existe ambiguidade de múltiplas linhas na mesma SC
            numero_sc_atual = (item.numero_sc or '').strip()
            if numero_sc_atual:
                try:
                    alvo_desc = (item.descricao_override or item.insumo.descricao or '').strip()
                    # Buscar recebimentos dessa SC na obra
                    receb_qs = RecebimentoObra.objects.filter(
                        obra=item.obra,
                        numero_sc=numero_sc_atual
                    ).select_related('insumo')
                    if alvo_desc:
                        match = receb_qs.filter(descricao_item__iexact=alvo_desc).first()
                        if match:
                            # Ajustar insumo (se era provisório) e item_sc
                            if (item.insumo.codigo_sienge or '').startswith('SM-LEV-') or item.insumo_id != match.insumo_id:
                                item.insumo = match.insumo
                            item.item_sc = match.item_sc or ''
                            valor_novo = numero_sc_atual
                    # Se só existe 1 recebimento para a SC+insumo, podemos setar item_sc automaticamente
                    if not item.item_sc and item.insumo_id:
                        cand = RecebimentoObra.objects.filter(
                            obra=item.obra,
                            numero_sc=numero_sc_atual,
                            insumo=item.insumo
                        )
                        if cand.count() == 1:
                            item.item_sc = cand.first().item_sc or ''
                    
                    # IMPORTANTE: Atualizar campos consolidados do Sienge (PC, Prazo, Empresa, Quantidades)
                    # Buscar TODOS os RecebimentoObra desta SC+Insumo para consolidar dados
                    recebimentos_todos = RecebimentoObra.objects.filter(
                        obra=item.obra,
                        numero_sc=numero_sc_atual,
                        insumo=item.insumo
                    )
                    
                    if recebimentos_todos.exists():
                        # Consolidar dados: usar primeiro valor não vazio de cada campo
                        pc_consolidado = ''
                        prazo_consolidado = None
                        empresa_consolidada = ''
                        data_sc_consolidada = None
                        data_pc_consolidada = None
                        
                        for rec in recebimentos_todos:
                            if not pc_consolidado and rec.numero_pc:
                                pc_consolidado = rec.numero_pc
                            if not prazo_consolidado and rec.prazo_recebimento:
                                prazo_consolidado = rec.prazo_recebimento
                            if not empresa_consolidada and rec.empresa_fornecedora:
                                empresa_consolidada = rec.empresa_fornecedora
                            if not data_sc_consolidada and rec.data_sc:
                                data_sc_consolidada = rec.data_sc
                            if not data_pc_consolidada and rec.data_pc:
                                data_pc_consolidada = rec.data_pc
                        
                        # Atualizar campos do ItemMapa com dados consolidados
                        if pc_consolidado:
                            item.numero_pc = pc_consolidado
                        if data_pc_consolidada:
                            item.data_pc = data_pc_consolidada
                        if prazo_consolidado:
                            item.prazo_recebimento = prazo_consolidado
                        # Só atualizar empresa_fornecedora se estiver vazio (não sobrescrever valores digitados)
                        if (not item.empresa_fornecedora or item.empresa_fornecedora.strip() == '') and empresa_consolidada:
                            item.empresa_fornecedora = empresa_consolidada
                        if data_sc_consolidada:
                            item.data_sc = data_sc_consolidada
                        
                        # Calcular quantidades: somar todos os RecebimentoObra vinculados
                        total_recebido = sum(r.quantidade_recebida for r in recebimentos_todos)
                        total_solicitado = sum(r.quantidade_solicitada for r in recebimentos_todos)
                        
                        item.quantidade_recebida = total_recebido
                        saldo_calc = total_solicitado - total_recebido
                        item.saldo_a_entregar = max(saldo_calc, Decimal('0.00'))
                        
                        # Limpar item_sc para itens manuais (permitir múltiplos RecebimentoObra)
                        # Mas manter item_sc se foi setado acima (linha específica encontrada)
                        # Apenas limpar se não foi encontrada linha específica
                        if not item.item_sc or (alvo_desc and not receb_qs.filter(descricao_item__iexact=alvo_desc).exists()):
                            item.item_sc = ''  # Permitir vinculação com múltiplos RecebimentoObra
                            
                except Exception as e:
                    # Logar erro mas continuar (não bloquear a atualização do SC)
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Erro ao atualizar dados do Sienge ao vincular SC {numero_sc_atual}: {e}")

            # Se existir um "placeholder do Sienge" (A CLASSIFICAR, sem local) para a mesma SC+Insumo,
            # e agora já existe pelo menos 1 item "real" (ex: com local ou criado pela engenharia),
            # removemos o placeholder para evitar duplicidade visual.
            if numero_sc_atual:
                placeholders = ItemMapa.objects.filter(
                    obra=item.obra,
                    numero_sc=numero_sc_atual,
                    insumo=item.insumo,
                    local_aplicacao__isnull=True,
                    categoria='A CLASSIFICAR',
                    criado_por__isnull=True,
                ).exclude(pk=item.pk)
                # Se temos item_sc, remover somente o placeholder da mesma linha
                if item.item_sc:
                    placeholders = placeholders.filter(item_sc=item.item_sc)

                existe_item_real = ItemMapa.objects.filter(
                    obra=item.obra,
                    numero_sc=numero_sc_atual,
                    insumo=item.insumo,
                ).exclude(pk__in=placeholders.values_list('pk', flat=True)).exclude(pk=item.pk).exists()

                # O próprio item pode ser "real" (ex: tem local / foi criado por usuário)
                item_e_real = bool(item.local_aplicacao_id or item.criado_por_id or item.categoria != 'A CLASSIFICAR')

                if placeholders.exists() and (existe_item_real or item_e_real):
                    # Registrar no histórico antes de excluir
                    for ph in placeholders:
                        try:
                            HistoricoAlteracao.registrar(
                                obra=ph.obra,
                                usuario=request.user,
                                tipo='EXCLUSAO',
                                descricao=f'Placeholder do Sienge removido após vinculação de SC {numero_sc_atual} ({ph.insumo.descricao})',
                                item_mapa=ph,
                                campo_alterado='placeholder_sienge',
                                valor_anterior='PLACEHOLDER',
                                valor_novo='REMOVIDO',
                                ip_address=request.META.get('REMOTE_ADDR')
                            )
                        except Exception:
                            pass
                    placeholders.delete()
        
        # Tratar campos específicos que não são simples setattr
        # IMPORTANTE: local_aplicacao já foi processado acima, não processar novamente aqui
        if field == 'empresa_fornecedora':
            # Empresa responsável (pode ser editada manualmente, não é sobrescrita na importação)
            item.empresa_fornecedora = value.strip() if value else ''
            valor_novo = item.empresa_fornecedora or '(vazio)'
        elif field not in ['local_aplicacao', 'insumo_codigo']:
            # Para outros campos (exceto local_aplicacao e insumo_codigo que já foram processados), usar setattr genérico
            setattr(item, field, value)
            valor_novo = value or '(vazio)'
        # Se for local_aplicacao ou insumo_codigo, já foi processado acima, não fazer nada aqui
        
        item.save()
        
        # Registrar histórico
        campo_label = campo_labels.get(field, field)
        HistoricoAlteracao.registrar(
            obra=item.obra,
            usuario=request.user,
            tipo='EDICAO',
            descricao=f'{campo_label} alterado: "{valor_anterior}" → "{valor_novo}"',
            item_mapa=item,
            campo_alterado=field,
            valor_anterior=valor_anterior,
            valor_novo=valor_novo,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return JsonResponse({
            'success': True,
            'status_css': item.status_css
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


## item_toggle_nao_aplica removido (funcionalidade descontinuada)


@login_required
@require_group(GRUPOS.ENGENHARIA)
@require_http_methods(["POST"])
@ensure_csrf_cookie
def item_alocar(request, item_id):
    """Realiza alocação de recebimento para um item."""
    item = get_object_or_404(ItemMapa, id=item_id)
    
    # Validar que o item pertence à obra da sessão
    obra_sessao_id = request.session.get('obra_id')
    if not request.user.is_superuser:
        if not obra_sessao_id or int(obra_sessao_id) != item.obra_id:
            return JsonResponse({'success': False, 'error': 'Sem permissão para alocar itens desta obra.'}, status=403)
    
    try:
        data = json.loads(request.body)
        quantidade_str = data.get('quantidade_alocada', '0')
        observacao = data.get('observacao', '')
        
        quantidade = Decimal(str(quantidade_str))
        
        if quantidade <= 0:
            return JsonResponse({
                'success': False,
                'error': 'Quantidade deve ser maior que zero'
            }, status=400)
        
        # CORREÇÃO PRIORIDADE 1: Validar DENTRO da transação com SELECT FOR UPDATE
        # Isso evita race conditions quando múltiplos usuários alocam simultaneamente
        with transaction.atomic():
            # Buscar recebimento vinculado
            recebimento = item.recebimento_vinculado
            if not recebimento:
                return JsonResponse({
                    'success': False,
                    'error': f'Não há material recebido na obra para o insumo "{item.insumo.descricao}". Aguarde a importação do Sienge ou cadastre um recebimento manualmente.'
                }, status=400)
            
            # Lock no recebimento para evitar race condition
            # SELECT FOR UPDATE bloqueia a linha até o fim da transação
            recebimento = RecebimentoObra.objects.select_for_update().get(id=recebimento.id)
            
            # Verificar se há quantidade recebida
            if recebimento.quantidade_recebida <= 0:
                return JsonResponse({
                    'success': False,
                    'error': f'Não há material recebido na obra para o insumo "{item.insumo.descricao}".'
                }, status=400)
            
            # Calcular disponível DENTRO da transação (com lock)
            # Isso garante que o cálculo seja feito com dados consistentes
            total_alocado = AlocacaoRecebimento.objects.filter(
                recebimento=recebimento
            ).aggregate(total=Sum('quantidade_alocada'))['total'] or Decimal('0.00')
            
            disponivel = recebimento.quantidade_recebida - total_alocado
            
            if disponivel <= 0:
                return JsonResponse({
                    'success': False,
                    'error': 'Não há material disponível para alocar. Todo o material recebido já foi alocado.'
                }, status=400)
            
            if quantidade > disponivel:
                return JsonResponse({
                    'success': False,
                    'error': f'Quantidade ({quantidade}) excede o disponível ({disponivel} {item.insumo.unidade}). Informe um valor menor.'
                }, status=400)
            alocacao = AlocacaoRecebimento(
                obra=item.obra,
                insumo=item.insumo,
                local_aplicacao=item.local_aplicacao,
                recebimento=recebimento,
                item_mapa=item,
                quantidade_alocada=quantidade,
                observacao=observacao,
                criado_por=request.user
            )
            alocacao.save()
            
            # Registrar histórico de alocação
            local_nome = item.local_aplicacao.nome if item.local_aplicacao else 'local não definido'
            HistoricoAlteracao.registrar(
                obra=item.obra,
                usuario=request.user,
                tipo='ALOCACAO',
                descricao=f'Alocado {quantidade} {item.insumo.unidade} para {local_nome}',
                item_mapa=item,
                campo_alterado='alocacao',
                valor_anterior='',
                valor_novo=f'{quantidade} {item.insumo.unidade}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
        
        return JsonResponse({
            'success': True,
            'message': f'Alocado {quantidade} {item.insumo.unidade} para {item.local_aplicacao.nome if item.local_aplicacao else "este local"}',
            'nova_quantidade_alocada': str(item.quantidade_alocada_local),
            'saldo_restante': str(item.saldo_a_alocar_local),
            'status_css': item.status_css
        })
        
    except (ValueError, TypeError) as e:
        return JsonResponse({
            'success': False,
            'error': f'Valor inválido: {str(e)}'
        }, status=400)
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_group(GRUPOS.ENGENHARIA)
@require_http_methods(["POST"])
@ensure_csrf_cookie
def item_remover_alocacao(request, item_id):
    """Remove a última alocação de um item."""
    item = get_object_or_404(ItemMapa, id=item_id)
    
    try:
        data = json.loads(request.body)
        remover_todas = data.get('remover_todas', False)
        alocacao_id = data.get('alocacao_id')
        
        # Buscar alocações deste item
        alocacoes = AlocacaoRecebimento.objects.filter(
            item_mapa=item
        )
        
        if not alocacoes.exists():
            return JsonResponse({
                'success': False,
                'error': 'Não há alocações para remover.'
            }, status=400)
        
        with transaction.atomic():
            if remover_todas:
                # Remover todas as alocações
                total_removido = alocacoes.count()
                total_quantidade = sum(a.quantidade_alocada for a in alocacoes)
                alocacoes.delete()
                
                # Registrar histórico
                HistoricoAlteracao.registrar(
                    obra=item.obra,
                    usuario=request.user,
                    tipo='REMOÇÃO_ALOCACAO',
                    descricao=f'Removidas todas as alocações ({total_quantidade} {item.insumo.unidade}) de {item.local_aplicacao.nome if item.local_aplicacao else "este local"}',
                    item_mapa=item,
                    campo_alterado='alocacao',
                    valor_anterior=f'{total_quantidade} {item.insumo.unidade}',
                    valor_novo='0',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Removidas {total_removido} alocação(ões) ({total_quantidade} {item.insumo.unidade})',
                    'nova_quantidade_alocada': '0.00',
                    'saldo_restante': str(item.saldo_a_alocar_local),
                    'status_css': item.status_css
                })
            elif alocacao_id:
                # Remover alocação específica pelo ID
                try:
                    alocacao = AlocacaoRecebimento.objects.get(
                        id=alocacao_id,
                        item_mapa=item
                    )
                    quantidade_removida = alocacao.quantidade_alocada
                    alocacao.delete()
                    
                    # Registrar histórico
                    HistoricoAlteracao.registrar(
                        obra=item.obra,
                        usuario=request.user,
                        tipo='REMOÇÃO_ALOCACAO',
                        descricao=f'Removida alocação de {quantidade_removida} {item.insumo.unidade} de {item.local_aplicacao.nome if item.local_aplicacao else "este local"}',
                        item_mapa=item,
                        campo_alterado='alocacao',
                        valor_anterior=f'{quantidade_removida} {item.insumo.unidade}',
                        valor_novo='0',
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    
                    return JsonResponse({
                        'success': True,
                        'message': f'Removida alocação de {quantidade_removida} {item.insumo.unidade}',
                        'nova_quantidade_alocada': str(item.quantidade_alocada_local),
                        'saldo_restante': str(item.saldo_a_alocar_local),
                        'status_css': item.status_css
                    })
                except AlocacaoRecebimento.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Alocação não encontrada ou não pertence a este item.'
                    }, status=404)
            else:
                # Fallback: remover apenas a última alocação (comportamento antigo)
                ultima_alocacao = alocacoes.order_by('-data_alocacao').first()
                quantidade_removida = ultima_alocacao.quantidade_alocada
                ultima_alocacao.delete()
                
                # Registrar histórico
                HistoricoAlteracao.registrar(
                    obra=item.obra,
                    usuario=request.user,
                    tipo='REMOÇÃO_ALOCACAO',
                    descricao=f'Removida alocação de {quantidade_removida} {item.insumo.unidade} de {item.local_aplicacao.nome if item.local_aplicacao else "este local"}',
                    item_mapa=item,
                    campo_alterado='alocacao',
                    valor_anterior=f'{quantidade_removida} {item.insumo.unidade}',
                    valor_novo='0',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Removida alocação de {quantidade_removida} {item.insumo.unidade}',
                    'nova_quantidade_alocada': str(item.quantidade_alocada_local),
                    'saldo_restante': str(item.saldo_a_alocar_local),
                    'status_css': item.status_css
                })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_group(GRUPOS.ENGENHARIA)
@require_http_methods(["POST"])
@ensure_csrf_cookie
def dashboard2_alocar(request):
    """API para alocar material no Dashboard 2 - valida contra saldo máximo do Sienge."""
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        quantidade_str = data.get('quantidade_alocada', '0')
        observacao = data.get('observacao', '')
        
        if not item_id:
            return JsonResponse({
                'success': False,
                'error': 'Item ID é obrigatório'
            }, status=400)
        
        item = get_object_or_404(ItemMapa, id=item_id)
        quantidade = Decimal(str(quantidade_str))
        
        if quantidade <= 0:
            return JsonResponse({
                'success': False,
                'error': 'Quantidade deve ser maior que zero'
            }, status=400)
        
        # CORREÇÃO PRIORIDADE 1: Validar DENTRO da transação com SELECT FOR UPDATE
        # Isso evita race conditions quando múltiplos usuários alocam simultaneamente
        with transaction.atomic():
            # Buscar recebimentos com lock
            recebimentos = None
            saldo_maximo = Decimal('0.00')
            
            if item.numero_sc:
                # Lock nos recebimentos para evitar race condition
                recebimentos = RecebimentoObra.objects.select_for_update().filter(
                    obra=item.obra,
                    numero_sc=item.numero_sc,
                    insumo=item.insumo
                )
                if recebimentos.exists():
                    # Pegar o MÁXIMO, não somar
                    saldo_maximo = max(
                        (r.quantidade_recebida or Decimal('0.00')) for r in recebimentos
                    )
            
            if saldo_maximo <= 0:
                return JsonResponse({
                    'success': False,
                    'error': 'Não há material recebido do Sienge para este insumo'
                }, status=400)
            
            # Calcular total já alocado DENTRO da transação (com lock)
            # IMPORTANTE: Se tem SC, considerar apenas alocações de itens com a mesma SC
            # Se não tem SC, considerar todas as alocações do insumo na obra
            if item.numero_sc:
                # Buscar todos os ItemMapa com a mesma SC e insumo
                itens_mesma_sc = ItemMapa.objects.filter(
                    obra=item.obra,
                    insumo=item.insumo,
                    numero_sc=item.numero_sc
                )
                total_alocado = AlocacaoRecebimento.objects.filter(
                    obra=item.obra,
                    insumo=item.insumo,
                    item_mapa__in=itens_mesma_sc
                ).aggregate(
                    total=Sum('quantidade_alocada')
                )['total'] or Decimal('0.00')
            else:
                # Sem SC: considerar todas as alocações do insumo na obra
                total_alocado = AlocacaoRecebimento.objects.filter(
                    obra=item.obra,
                    insumo=item.insumo
                ).aggregate(
                    total=Sum('quantidade_alocada')
                )['total'] or Decimal('0.00')
            
            saldo_disponivel = saldo_maximo - total_alocado
            
            if quantidade > saldo_disponivel:
                return JsonResponse({
                    'success': False,
                    'error': f'Quantidade excede o saldo disponível. Disponível: {saldo_disponivel} {item.insumo.unidade}'
                }, status=400)
            
            # Buscar recebimento vinculado
            recebimento = item.recebimento_vinculado
            alocacao = AlocacaoRecebimento(
                obra=item.obra,
                insumo=item.insumo,
                local_aplicacao=item.local_aplicacao,
                recebimento=recebimento,
                item_mapa=item,
                quantidade_alocada=quantidade,
                observacao=observacao,
                criado_por=request.user
            )
            alocacao.save()
            
            # Registrar histórico
            local_nome = item.local_aplicacao.nome if item.local_aplicacao else 'local não definido'
            HistoricoAlteracao.registrar(
                obra=item.obra,
                usuario=request.user,
                tipo='ALOCACAO',
                descricao=f'[Dashboard 2] Alocado {quantidade} {item.insumo.unidade} para {local_nome}',
                item_mapa=item,
                campo_alterado='alocacao',
                valor_anterior='',
                valor_novo=f'{quantidade} {item.insumo.unidade}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
        
        # Recalcular totais
        if item.numero_sc:
            itens_mesma_sc = ItemMapa.objects.filter(
                obra=item.obra,
                insumo=item.insumo,
                numero_sc=item.numero_sc
            )
            novo_total_alocado = AlocacaoRecebimento.objects.filter(
                obra=item.obra,
                insumo=item.insumo,
                item_mapa__in=itens_mesma_sc
            ).aggregate(
                total=Sum('quantidade_alocada')
            )['total'] or Decimal('0.00')
        else:
            novo_total_alocado = AlocacaoRecebimento.objects.filter(
                obra=item.obra,
                insumo=item.insumo
            ).aggregate(
                total=Sum('quantidade_alocada')
            )['total'] or Decimal('0.00')
        
        novo_saldo_disponivel = saldo_maximo - novo_total_alocado
        
        return JsonResponse({
            'success': True,
            'message': f'Alocado {quantidade} {item.insumo.unidade} para {local_nome}',
            'saldo_maximo': str(saldo_maximo),
            'total_alocado': str(novo_total_alocado),
            'saldo_disponivel': str(novo_saldo_disponivel),
        })
        
    except (ValueError, TypeError) as e:
        return JsonResponse({
            'success': False,
            'error': f'Valor inválido: {str(e)}'
        }, status=400)
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def recebimentos_obra(request, obra_id):
    """Lista recebimentos de uma obra com saldo disponível para alocação."""
    obra = get_object_or_404(Obra, id=obra_id)
    
    recebimentos = RecebimentoObra.objects.filter(
        obra=obra,
        quantidade_recebida__gt=0
    ).select_related('insumo').order_by('-updated_at')
    
    result = []
    for rec in recebimentos:
        disponivel = rec.quantidade_disponivel
        if disponivel > 0:
            result.append({
                'id': rec.id,
                'numero_sc': rec.numero_sc,
                'insumo': rec.insumo.descricao,
                'insumo_id': rec.insumo_id,
                'quantidade_recebida': str(rec.quantidade_recebida),
                'quantidade_alocada': str(rec.quantidade_alocada),
                'quantidade_disponivel': str(disponivel),
                'unidade': rec.insumo.unidade,
                'status': rec.status_recebimento
            })
    
    return JsonResponse({'recebimentos': result})


@login_required
@require_http_methods(["GET"])
def listar_scs_disponiveis(request):
    """
    Lista SCs disponíveis (do RecebimentoObra) para vinculação no ItemMapa.
    Usado para o select de "Nº SOLICITAÇÃO" no formulário.
    """
    obra_id = request.GET.get('obra')
    if not obra_id:
        return JsonResponse({'scs': []})
    
    try:
        obra = get_object_or_404(Obra, id=obra_id)
        
        # Buscar todas as SCs da obra (RecebimentoObra)
        recebimentos = RecebimentoObra.objects.filter(
            obra=obra
        ).select_related('insumo').order_by('numero_sc')
        
        result = []
        for rec in recebimentos:
            # Verificar quantos ItemMapa já estão vinculados a esta SC
            itens_vinculados = ItemMapa.objects.filter(
                obra=obra,
                numero_sc=rec.numero_sc
            ).count()
            
            result.append({
                'numero_sc': rec.numero_sc,
                'insumo_id': rec.insumo_id,
                'insumo_codigo': rec.insumo.codigo_sienge,
                'insumo_descricao': rec.insumo.descricao,
                'insumo_unidade': rec.insumo.unidade,
                'numero_pc': rec.numero_pc or '',
                'quantidade_solicitada': str(rec.quantidade_solicitada),
                'quantidade_recebida': str(rec.quantidade_recebida),
                'status': rec.status_recebimento,
                'itens_vinculados': itens_vinculados,
                'display': f"SC {rec.numero_sc} - {rec.insumo.descricao[:40]}{'...' if len(rec.insumo.descricao) > 40 else ''}"
            })
        
        return JsonResponse({'scs': result})
    
    except Exception as e:
        return JsonResponse({'scs': [], 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def listar_insumos(request):
    """Lista insumos ativos para select."""
    insumos = Insumo.objects.filter(ativo=True).order_by('descricao')
    return JsonResponse({
        'insumos': [
            {
                'id': insumo.id,
                'codigo_sienge': insumo.codigo_sienge,
                'descricao': insumo.descricao,
                'unidade': insumo.unidade
            }
            for insumo in insumos
        ]
    })


@login_required
@require_http_methods(["GET"])
def listar_locais(request):
    """Lista locais de uma obra para select."""
    obra_id = request.GET.get('obra')
    if not obra_id:
        return JsonResponse({'locais': []})
    
    try:
        obra = get_object_or_404(Obra, id=obra_id)
        locais = LocalObra.objects.filter(obra=obra).order_by('tipo', 'nome')
        return JsonResponse({
            'locais': [
                {
                    'id': local.id,
                    'nome': local.nome,
                    'tipo': local.get_tipo_display()
                }
                for local in locais
            ]
        })
    except Exception:
        return JsonResponse({'locais': []})


@login_required
@require_http_methods(["GET"])
def busca_rapida_mobile(request):
    """
    Busca rápida para mobile - retorna cards de itens.
    Parâmetros: obra, q (query), filtro (atrasados, semana, meus, comprados, entregues, todos)
    """
    from datetime import datetime, timedelta
    
    obra_id = request.GET.get('obra')
    query = request.GET.get('q', '').strip()
    filtro = request.GET.get('filtro', '')
    
    if not obra_id:
        return JsonResponse({'items': [], 'error': 'Selecione uma obra'})
    
    try:
        obra = get_object_or_404(Obra, id=obra_id)
        itens = ItemMapa.objects.filter(
            obra=obra
        ).select_related('insumo', 'local_aplicacao')
        
        hoje = datetime.now().date()
        fim_semana = hoje + timedelta(days=7)
        
        # Converter para lista se precisar de propriedades calculadas
        itens_list = list(itens)
        
        # Aplicar filtros
        if filtro == 'atrasados':
            itens_list = [i for i in itens_list if i.is_atrasado]
        elif filtro == 'semana':
            itens_list = [
                i for i in itens_list 
                if i.prazo_recebimento and hoje <= i.prazo_recebimento <= fim_semana
                and i.status_css != 'status-verde'
            ]
        elif filtro == 'meus' and request.user.username:
            itens_list = [i for i in itens_list if request.user.username.lower() in (i.responsavel or '').lower()]
        elif filtro == 'comprados':
            itens_list = [i for i in itens_list if i.status_css in ('status-amarelo', 'status-laranja')]
        elif filtro == 'entregues':
            itens_list = [i for i in itens_list if i.status_css == 'status-verde']
        elif filtro == 'prazo':
            itens_list = [
                i for i in itens_list 
                if not i.is_atrasado and i.status_css != 'status-verde'
            ]
        elif filtro == 'todos':
            pass  # Todos os itens
        
        # Busca textual
        if query:
            query_lower = query.lower()
            itens_list = [
                i for i in itens_list
                if query_lower in (i.descricao_override or i.insumo.descricao or '').lower()
                or query_lower in (i.insumo.descricao or '').lower()
                or query_lower in (i.insumo.codigo_sienge or '').lower()
                or query_lower in (i.local_aplicacao.nome if i.local_aplicacao else '').lower()
                or query_lower in (i.numero_sc or '').lower()
                or query_lower in (i.numero_pc or '').lower()
                or query_lower in (i.empresa_fornecedora or '').lower()
                or query_lower in (i.categoria or '').lower()
            ]
        
        # Ordenar: atrasados primeiro, depois por prazo
        itens_list.sort(key=lambda x: (
            0 if x.is_atrasado else 1,
            x.prazo_recebimento or datetime.max.date()
        ))
        
        # Limitar resultados
        itens_list = itens_list[:50]
        
        # Serializar
        results = []
        for item in itens_list:
            recebimento = item.recebimento_vinculado
            prazo = item.prazo_recebimento or (recebimento.prazo_recebimento if recebimento else None)
            fornecedor = item.empresa_fornecedora or (recebimento.empresa_fornecedora if recebimento else None)
            
            dias_atraso = 0
            if prazo and prazo < hoje and item.status_css != 'status-verde':
                dias_atraso = (hoje - prazo).days
            
            results.append({
                'id': item.id,
                'insumo': item.descricao_override or item.insumo.descricao,
                'codigo': item.insumo.codigo_sienge,
                'unidade': item.insumo.unidade,
                'categoria': item.categoria or '-',
                'local': item.local_aplicacao.nome if item.local_aplicacao else '-',
                'qtd_plan': float(item.quantidade_planejada),
                'qtd_rec': float(item.quantidade_alocada_local),
                'status_css': item.status_css,
                'status_label': item.status_etapa,
                'prazo': prazo.strftime('%d/%m') if prazo else '-',
                'fornecedor': fornecedor[:25] if fornecedor else '-',
                'sc': item.numero_sc or '-',
                'pc': item.numero_pc or (recebimento.numero_pc if recebimento else '-') or '-',
                'is_atrasado': item.is_atrasado,
                'dias_atraso': dias_atraso,
                'prioridade': item.prioridade,
            })
        
        return JsonResponse({
            'items': results,
            'total': len(results),
            'obra': obra.nome
        })
    
    except Exception as e:
        return JsonResponse({'items': [], 'error': str(e)})
