"""Validação de assinatura manual (PNG base64) — mesmo contrato do workflow."""

_SIGNATURE_PREFIX = 'data:image/png;base64,'
_SIGNATURE_MIN_LEN = 500


def validate_signature_data(raw: str) -> str:
    data = (raw or '').strip()
    if not data.startswith(_SIGNATURE_PREFIX):
        raise ValueError(
            'Desenhe sua assinatura no quadro ou use «Usar última assinatura».'
        )
    if len(data) < _SIGNATURE_MIN_LEN:
        raise ValueError('Assinatura vazia ou inválida. Desenhe novamente no quadro.')
    return data
