"""Carrega e persiste a configuração de alertas do RH (singleton)."""
from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import Q

from accounts.groups import GRUPOS
from recursos_humanos.models import ConfiguracaoAlertasRH


def usuarios_elegiveis_alertas():
    return User.objects.filter(is_active=True).filter(
        Q(groups__name=GRUPOS.RECURSOS_HUMANOS)
        | Q(is_superuser=True)
        | Q(is_staff=True),
    ).distinct().order_by('first_name', 'last_name', 'username')


def rotulo_usuario_alertas(user: User) -> str:
    nome = (user.get_full_name() or user.username).strip()
    if user.groups.filter(name=GRUPOS.RECURSOS_HUMANOS).exists():
        papel = 'RH'
    elif user.is_superuser:
        papel = 'Administrador'
    elif user.is_staff:
        papel = 'Staff'
    else:
        papel = 'Usuário'
    return f'{nome} ({papel})'


def obter_configuracao_alertas() -> ConfiguracaoAlertasRH:
    config = ConfiguracaoAlertasRH.get_solo()
    if not config.responsaveis.exists():
        config.responsaveis.set(usuarios_elegiveis_alertas())
    return config


def limite_dias_antecedencia_doc(nome_tipo: str, config: ConfiguracaoAlertasRH | None = None) -> int:
    """Retorna quantos dias antes do vencimento o documento entra em alerta."""
    cfg = config or obter_configuracao_alertas()
    nome = (nome_tipo or '').lower()
    if 'aso' in nome:
        return cfg.dias_renovacao_aso
    if 'nr' in nome or 'treinamento' in nome:
        return cfg.dias_treinamento_vencer
    return cfg.dias_documento_vencendo


def salvar_configuracao_alertas(cleaned_data: dict) -> ConfiguracaoAlertasRH:
    config = ConfiguracaoAlertasRH.get_solo()
    for campo in (
        'dias_documento_vencendo',
        'dias_treinamento_vencer',
        'dias_renovacao_aso',
        'dias_renotificar_vencido',
        'canal_email_rh',
        'canal_notificacao_sistema',
        'canal_whatsapp_gestor',
        'canal_relatorio_pdf_semanal',
    ):
        setattr(config, campo, cleaned_data[campo])
    config.save()
    config.responsaveis.set(cleaned_data.get('responsaveis') or [])
    return config


def config_para_template(config: ConfiguracaoAlertasRH) -> dict:
    return {
        'dias_documento_vencendo': config.dias_documento_vencendo,
        'dias_treinamento_vencer': config.dias_treinamento_vencer,
        'dias_renovacao_aso': config.dias_renovacao_aso,
        'dias_renotificar_vencido': config.dias_renotificar_vencido,
        'canal_email_rh': config.canal_email_rh,
        'canal_notificacao_sistema': config.canal_notificacao_sistema,
        'canal_whatsapp_gestor': config.canal_whatsapp_gestor,
        'canal_relatorio_pdf_semanal': config.canal_relatorio_pdf_semanal,
        'responsaveis_ids': list(config.responsaveis.values_list('pk', flat=True)),
    }
