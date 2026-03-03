from django import template
from decimal import Decimal, ROUND_HALF_UP

register = template.Library()

@register.filter
def format_quantidade(value):
    """
    Formata quantidade preservando PRECISÃO TOTAL e zeros significativos.
    Formato brasileiro: ponto para milhar, vírgula para decimal.
    
    IMPORTANTE: Para empresa de engenharia - NÃO PERDE PRECISÃO.
    Sempre mostra 2 casas decimais para consistência visual, mas preserva
    a precisão completa do Decimal no banco de dados.
    
    Exemplos:
    - 20 -> "20,00"
    - 20000 -> "20.000,00"
    - 20000.5 -> "20.000,50"
    - 20000.123 -> "20.000,12" (arredondamento apenas visual, não no banco)
    - 0 -> "0,00"
    """
    if value is None:
        return "0,00"
    
    try:
        # Converter para Decimal preservando precisão máxima
        if isinstance(value, (int, float)):
            # Converter float para string primeiro para evitar perda de precisão
            value = Decimal(str(value))
        elif not isinstance(value, Decimal):
            value = Decimal(str(value))
        
        # Quantificar para 2 casas decimais (apenas para formatação visual)
        # IMPORTANTE PARA ENGENHARIA: 
        # - Isso NÃO altera o valor no banco de dados (que usa DecimalField com 2 casas)
        # - Apenas formata a exibição para consistência visual
        # - O valor original no banco mantém precisão total (max_digits=14, decimal_places=2)
        # - Arredondamento ROUND_HALF_UP segue padrão contábil/engenharia
        value_quantized = value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Converter para string preservando todos os dígitos
        value_str = str(value_quantized)
        
        # Separar parte inteira e decimal
        if '.' in value_str:
            integer_part, decimal_part = value_str.split('.')
        else:
            integer_part = value_str
            decimal_part = '00'
        
        # Garantir 2 dígitos decimais sempre
        if len(decimal_part) < 2:
            decimal_part = decimal_part.ljust(2, '0')
        elif len(decimal_part) > 2:
            # Se tiver mais de 2 dígitos, truncar (não deveria acontecer após quantize)
            decimal_part = decimal_part[:2]
        
        # Adicionar separador de milhar (ponto) na parte inteira
        # Formato brasileiro: 20000 -> 20.000
        integer_formatted = ''
        for i, digit in enumerate(reversed(integer_part)):
            if i > 0 and i % 3 == 0:
                integer_formatted = '.' + integer_formatted
            integer_formatted = digit + integer_formatted
        
        # Retornar formato brasileiro: "20.000,00"
        return f"{integer_formatted},{decimal_part}"
        
    except (ValueError, TypeError, AttributeError) as e:
        # Em caso de erro, retornar valor seguro mas logar para debug
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Erro ao formatar quantidade {value}: {e}")
        return "0,00"

@register.filter(name='format_unidade')
def format_unidade(value):
    """
    Formata a unidade de medida para exibição.
    Converte M3 -> m³ e M2 -> m²
    Retorna '-' se vazio
    """
    if not value or not str(value).strip():
        return '-'
    
    unidade = str(value).strip().upper()
    
    if unidade == 'M3':
        return 'm³'
    elif unidade == 'M2':
        return 'm²'
    
    return value

