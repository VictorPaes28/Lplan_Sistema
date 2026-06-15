"""Carrega e persiste a configuração de alertas do RH (singleton)."""
from __future__ import annotations

from django.contrib.auth.models import User

from recursos_humanos.models import ConfiguracaoAlertasRH


def usuarios_staff_alertas():
    return User.objects.filter(is_staff=True, is_active=True).order_by(
        'first_name', 'last_name', 'username',
    )


def rotulo_usuario_alertas(user: User) -> str:
    nome = (user.get_full_name() or user.username).strip()
    if user.is_superuser:
        papel = 'Administrador'
    elif user.is_staff:
        papel = 'Staff'
    else:
        papel = 'Usuário'
    return f'{nome} ({papel})'


def obter_configuracao_alertas() -> ConfiguracaoAlertasRH:
    config = ConfiguracaoAlertasRH.get_solo()
    if not config.responsaveis.exists():
        config.responsaveis.set(usuarios_staff_alertas())
    return config


def salvar_configuracao_alertas(cleaned_data: dict) -> ConfiguracaoAlertasRH:
    config = ConfiguracaoAlertasRH.get_solo()
    for campo in (
        'dias_antecedencia_documentos',
        'dias_renotificar_vencidos',
        'notificar_email',
        'notificar_sistema',
    ):
        setattr(config, campo, cleaned_data[campo])
    config.save()
    config.responsaveis.set(cleaned_data.get('responsaveis') or [])
    return config


def config_para_template(config: ConfiguracaoAlertasRH) -> dict:
    return {
        'dias_antecedencia_documentos': config.dias_antecedencia_documentos,
        'dias_renotificar_vencidos': config.dias_renotificar_vencidos,
        'notificar_email': config.notificar_email,
        'notificar_sistema': config.notificar_sistema,
        'responsaveis_ids': list(config.responsaveis.values_list('pk', flat=True)),
    }
