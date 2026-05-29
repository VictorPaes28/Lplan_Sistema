"""
Serviço central de decisão de comunicação (e-mail / interno / resumo).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.db import models

from core.comunicacao_constants import (
    RESUMO_DIARIO_DISPONIVEL,
    TIPOS_COM_ROUTER_ATIVO,
    TIPOS_NUNCA_DESLIGAR,
)
from core.comunicacao_models import (
    LogDecisaoComunicacao,
    PadraoComunicacaoGrupo,
    PreferenciaComunicacao,
    TipoComunicacao,
)

logger = logging.getLogger(__name__)

User = get_user_model()


@dataclass
class DecisaoEmail:
    enviar: bool
    motivo: str
    origem: str = ''
    detalhe: str = ''


class ComunicacaoPreferenciasService:
    """
    Router de preferências de comunicação.
    Preserva comportamento atual quando não há preferência ou ocorre erro.
    """

    def pode_enviar_email(
        self,
        email: str,
        tipo_codigo: str,
        *,
        usuario=None,
        contexto: dict[str, Any] | None = None,
        registrar: bool = True,
    ) -> DecisaoEmail:
        """Decide se um destinatário deve receber e-mail imediato."""
        if tipo_codigo not in TIPOS_COM_ROUTER_ATIVO:
            return DecisaoEmail(True, 'router_nao_aplicavel', 'modulo')

        email_norm = self._normalizar_email(email)
        if not email_norm:
            return DecisaoEmail(False, 'email_vazio', 'validacao')

        try:
            decisao = self._resolver_decisao_email(email_norm, tipo_codigo, usuario=usuario)
            if registrar:
                ctx = dict(contexto or {})
                if decisao.detalhe:
                    ctx['detalhe'] = decisao.detalhe
                self.registrar_decisao(
                    email=email_norm,
                    tipo_codigo=tipo_codigo,
                    decisao='enviar' if decisao.enviar else 'bloquear',
                    motivo=decisao.detalhe or decisao.motivo,
                    origem_destinatario=decisao.origem,
                    usuario=usuario,
                    contexto=ctx,
                )
            return decisao
        except Exception as exc:
            logger.warning(
                'ComunicacaoPreferenciasService falhou para %s / %s: %s — fallback enviar',
                email_norm,
                tipo_codigo,
                exc,
            )
            if registrar:
                try:
                    self.registrar_decisao(
                        email=email_norm,
                        tipo_codigo=tipo_codigo,
                        decisao='enviar',
                        motivo='fallback_erro_servico',
                        origem_destinatario='fallback',
                        usuario=usuario,
                        contexto=contexto,
                    )
                except Exception:
                    pass
            return DecisaoEmail(True, 'fallback_erro_servico', 'fallback')

    def filtrar_destinatarios_email(
        self,
        destinatarios,
        tipo_codigo: str,
        *,
        contexto: dict[str, Any] | None = None,
    ) -> list[str]:
        """Filtra lista de e-mails mantendo apenas os autorizados pelo router."""
        if tipo_codigo not in TIPOS_COM_ROUTER_ATIVO:
            return list(destinatarios or [])

        permitidos = []
        vistos = set()
        for raw in destinatarios or []:
            email = self._normalizar_email(raw)
            if not email or email in vistos:
                continue
            vistos.add(email)
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            decisao = self.pode_enviar_email(
                email,
                tipo_codigo,
                usuario=user,
                contexto=contexto,
                registrar=True,
            )
            if decisao.enviar:
                permitidos.append(email)
        return permitidos

    def registrar_decisao(
        self,
        *,
        email: str = '',
        tipo_codigo: str = '',
        decisao: str,
        motivo: str,
        origem_destinatario: str = '',
        usuario=None,
        canal: str = 'email',
        contexto: dict[str, Any] | None = None,
    ) -> LogDecisaoComunicacao | None:
        try:
            tipo = TipoComunicacao.objects.filter(codigo=tipo_codigo).first()
            ctx = contexto or {}
            return LogDecisaoComunicacao.objects.create(
                usuario=usuario if getattr(usuario, 'pk', None) else None,
                email=self._normalizar_email(email),
                tipo=tipo,
                tipo_codigo=tipo_codigo or '',
                modulo=(tipo.modulo if tipo else (ctx.get('modulo') or '')),
                canal=canal,
                decisao=decisao,
                motivo=motivo[:120],
                origem_destinatario=(origem_destinatario or '')[:120],
                objeto_tipo=(ctx.get('objeto_tipo') or '')[:80],
                objeto_id=str(ctx.get('objeto_id') or '')[:64],
                contexto_json=ctx if isinstance(ctx, dict) else {},
            )
        except Exception as exc:
            logger.warning('Falha ao registrar LogDecisaoComunicacao: %s', exc)
            return None

    def explicar_recebimento(
        self,
        email: str,
        tipo_codigo: str,
        *,
        usuario=None,
    ) -> str:
        """Texto legível sobre por que o e-mail seria ou não enviado."""
        decisao = self.pode_enviar_email(
            email, tipo_codigo, usuario=usuario, registrar=False
        )
        mapa = {
            'tipo_obrigatorio': 'Este tipo de mensagem é obrigatório e não pode ser desligado.',
            'padrao_envio': 'Nenhuma preferência personalizada — envio padrão (como hoje).',
            'preferencia_usuario_ativa': 'Sua preferência mantém o recebimento por e-mail.',
            'preferencia_usuario_desativada': (
                'Você desativou o e-mail imediato deste aviso. '
                'Isso não cria notificação no sino — apenas deixa de enviar por e-mail.'
            ),
            'preferencia_email_livre_desativada': (
                'Este endereço foi configurado para não receber e-mail imediato deste aviso.'
            ),
            'bloqueado_por_admin': 'Um administrador bloqueou este envio para você.',
            'padrao_grupo_desativado': 'O padrão do seu perfil (grupo) desativa este e-mail.',
            'padrao_grupo_ativo': 'O padrão do seu perfil (grupo) mantém este e-mail.',
            'preferencia_usuario_ativa_sobre_grupo': (
                'Sua preferência mantém o e-mail, sobrescrevendo o padrão do grupo.'
            ),
            'preferencia_usuario_desativada_sobre_grupo': (
                'Você desativou o e-mail mesmo com padrão de grupo favorável ao envio.'
            ),
            'preferencia_resumo': 'Configurado para resumo (ainda não implementado — e-mail imediato bloqueado).',
            'tipo_desconhecido_fallback': 'Tipo não cadastrado — mantém envio por segurança.',
            'fallback_erro_servico': 'Erro ao consultar preferências — mantém envio por segurança.',
            'router_nao_aplicavel': 'Este fluxo ainda não usa o controle central.',
        }
        return mapa.get(decisao.motivo, decisao.motivo)

    def tipos_visiveis_usuario(self, usuario):
        """Tipos que o usuário comum pode ver/editar no perfil."""
        return TipoComunicacao.objects.filter(
            ativo=True,
        ).filter(
            models.Q(permite_usuario_desativar_email=True)
            | models.Q(permite_usuario_alterar_interno=True)
        ).order_by('modulo', 'ordem', 'nome')

    def _resolver_decisao_email(self, email: str, tipo_codigo: str, *, usuario=None) -> DecisaoEmail:
        tipo = TipoComunicacao.objects.filter(codigo=tipo_codigo, ativo=True).first()
        if not tipo:
            return DecisaoEmail(True, 'tipo_desconhecido_fallback', 'catalogo')

        if tipo.codigo in TIPOS_NUNCA_DESLIGAR:
            return DecisaoEmail(True, 'tipo_obrigatorio', 'tipo')

        user = usuario
        if not user:
            user = User.objects.filter(email__iexact=email, is_active=True).first()

        pref = self._buscar_preferencia(email, user, tipo)

        if pref and pref.bloqueado_por_admin:
            if pref.email_ativo is False:
                return DecisaoEmail(False, 'bloqueado_por_admin', 'admin')
            if pref.resumo_ativo:
                return DecisaoEmail(False, 'preferencia_resumo', 'preferencia')

        if pref and not pref.herdar_padrao:
            if pref.resumo_ativo and RESUMO_DIARIO_DISPONIVEL:
                return DecisaoEmail(False, 'preferencia_resumo', 'preferencia')
            if pref.resumo_ativo and not RESUMO_DIARIO_DISPONIVEL:
                return DecisaoEmail(False, 'preferencia_usuario_desativada', 'preferencia')
            if pref.email_ativo is False:
                if pref.usuario_id:
                    grupo_dec = self._resolver_padrao_grupo(user, tipo)
                    if grupo_dec is not None and grupo_dec.enviar:
                        return DecisaoEmail(
                            False,
                            'preferencia_usuario_desativada_sobre_grupo',
                            'preferencia',
                            detalhe=(
                                'Bloqueado por preferência individual '
                                '(sobrescreve padrão do grupo favorável ao envio).'
                            ),
                        )
                    return DecisaoEmail(False, 'preferencia_usuario_desativada', 'preferencia')
                return DecisaoEmail(False, 'preferencia_email_livre_desativada', 'preferencia')
            if pref.email_ativo is True:
                grupo_dec = self._resolver_padrao_grupo(user, tipo)
                if grupo_dec is not None and not grupo_dec.enviar:
                    return DecisaoEmail(
                        True,
                        'preferencia_usuario_ativa_sobre_grupo',
                        'preferencia',
                        detalhe=(
                            'Enviado por preferência individual '
                            '(sobrescreve padrão do grupo).'
                        ),
                    )
                return DecisaoEmail(True, 'preferencia_usuario_ativa', 'preferencia')

        grupo_dec = self._resolver_padrao_grupo(user, tipo)
        if grupo_dec is not None:
            return grupo_dec

        if tipo.email_padrao:
            return DecisaoEmail(True, 'padrao_envio', 'tipo')
        return DecisaoEmail(False, 'padrao_tipo_desligado', 'tipo')

    def _buscar_preferencia(self, email: str, user, tipo: TipoComunicacao):
        if user:
            pref = PreferenciaComunicacao.objects.filter(usuario=user, tipo=tipo).first()
            if pref:
                return pref
        if email:
            return PreferenciaComunicacao.objects.filter(
                tipo=tipo, email__iexact=email, usuario__isnull=True
            ).first()
        return None

    @staticmethod
    def _tipo_e_informativo(tipo: TipoComunicacao) -> bool:
        return tipo.categoria == 'informativo' or tipo.criticidade == 'informativo'

    def _resolver_padrao_grupo(self, user, tipo: TipoComunicacao) -> DecisaoEmail | None:
        """
        Mescla padrões de todos os grupos do usuário:
        - informativo: qualquer grupo desativando e-mail → bloqueia;
        - operacional: bloqueia só se todos os padrões explícitos desativarem;
          qualquer grupo ativando → envia.
        """
        if not user or not getattr(user, 'pk', None):
            return None
        group_ids = list(user.groups.values_list('pk', flat=True))
        if not group_ids:
            return None

        padroes = list(
            PadraoComunicacaoGrupo.objects.filter(
                grupo_id__in=group_ids,
                tipo=tipo,
            )
            .select_related('grupo')
            .order_by('grupo__name')
        )
        if not padroes:
            return None

        effective = [p for p in padroes if not p.resumo_ativo]
        if not effective:
            return None

        desativados = [p for p in effective if p.email_ativo is False]
        ativados = [p for p in effective if p.email_ativo is True]
        nomes_des = [p.grupo.name for p in desativados]
        nomes_at = [p.grupo.name for p in ativados]

        if self._tipo_e_informativo(tipo):
            if desativados:
                detalhe = f'Bloqueado por padrão do grupo {", ".join(nomes_des)}.'
                return DecisaoEmail(
                    False, 'padrao_grupo_desativado', 'grupo', detalhe=detalhe
                )
            if ativados:
                detalhe = f'Enviado por padrão do grupo {", ".join(nomes_at)}.'
                return DecisaoEmail(True, 'padrao_grupo_ativo', 'grupo', detalhe=detalhe)
            return None

        if ativados:
            detalhe = f'Enviado por padrão do grupo {", ".join(nomes_at)}.'
            return DecisaoEmail(True, 'padrao_grupo_ativo', 'grupo', detalhe=detalhe)
        if desativados and len(desativados) == len(effective):
            detalhe = f'Bloqueado por padrão do grupo {", ".join(nomes_des)}.'
            return DecisaoEmail(False, 'padrao_grupo_desativado', 'grupo', detalhe=detalhe)
        return None

    def modo_padrao_grupo(self, grupo, tipo: TipoComunicacao) -> str:
        """Retorna padrao | email | sem_email para exibição na tela admin."""
        padrao = PadraoComunicacaoGrupo.objects.filter(grupo=grupo, tipo=tipo).first()
        if not padrao:
            return 'padrao'
        if padrao.email_ativo is False:
            return 'sem_email'
        if padrao.email_ativo is True:
            return 'email'
        return 'padrao'

    def salvar_padrao_grupo(self, grupo, tipo: TipoComunicacao, modo: str) -> None:
        """modo: padrao | email | sem_email | restaurar"""
        if tipo.codigo in TIPOS_NUNCA_DESLIGAR:
            raise ValueError('Este e-mail é obrigatório do sistema e não pode ser alterado.')
        if not tipo.permite_admin_desativar_email:
            raise ValueError('Este tipo não permite padrão por grupo.')

        modo = self.normalizar_modo_preferencia(modo)
        if modo in ('restaurar', 'padrao'):
            PadraoComunicacaoGrupo.objects.filter(grupo=grupo, tipo=tipo).delete()
            return
        if modo == 'resumo':
            raise ValueError('Resumo diário ainda não está disponível.')
        if modo not in ('email', 'sem_email'):
            raise ValueError('Opção inválida.')

        PadraoComunicacaoGrupo.objects.update_or_create(
            grupo=grupo,
            tipo=tipo,
            defaults={
                'email_ativo': modo == 'email',
                'interno_ativo': None,
                'resumo_ativo': False,
            },
        )

    def restaurar_padroes_grupo(self, grupo) -> int:
        deleted, _ = PadraoComunicacaoGrupo.objects.filter(grupo=grupo).delete()
        return deleted

    @staticmethod
    def _normalizar_email(email) -> str:
        return (email or '').strip().lower()

    def normalizar_modo_preferencia(self, modo: str) -> str:
        """Aceita alias legado 'interno' e rejeita modos inválidos."""
        m = (modo or 'padrao').strip().lower()
        if m == 'interno':
            m = 'sem_email'
        return m

    def validar_modo_usuario(self, tipo: TipoComunicacao, modo: str) -> str:
        """Valida modo para perfil do usuário; retorna modo normalizado."""
        m = self.normalizar_modo_preferencia(modo)
        if m == 'resumo':
            raise ValueError('Resumo diário ainda não está disponível.')
        if tipo.codigo in TIPOS_NUNCA_DESLIGAR:
            if m not in ('email', 'padrao', 'restaurar'):
                raise ValueError('Este aviso é obrigatório e não pode ser desativado.')
        if not tipo.permite_usuario_desativar_email:
            if m not in ('padrao', 'restaurar'):
                raise ValueError('Você não pode alterar este tipo de comunicação.')
        if m not in ('padrao', 'email', 'sem_email', 'restaurar'):
            raise ValueError('Opção inválida.')
        return m

    def validar_modo_admin_usuario(self, tipo: TipoComunicacao, modo: str) -> str:
        m = self.normalizar_modo_preferencia(modo)
        if m == 'resumo':
            raise ValueError('Resumo diário ainda não está disponível.')
        if tipo.codigo in TIPOS_NUNCA_DESLIGAR and m not in ('email', 'padrao', 'restaurar'):
            raise ValueError('Tipo obrigatório não pode ser desativado.')
        if not tipo.permite_admin_desativar_email and m not in ('padrao', 'restaurar', 'email'):
            raise ValueError('Este tipo não pode ser alterado pelo painel administrativo.')
        if m not in ('padrao', 'email', 'sem_email', 'restaurar'):
            raise ValueError('Opção inválida.')
        return m

    def salvar_preferencia_usuario(
        self,
        *,
        usuario,
        tipo: TipoComunicacao,
        modo: str,
        atualizado_por=None,
        herdar_padrao: bool = False,
        contexto_validacao: str = 'usuario',
    ) -> PreferenciaComunicacao:
        """
        modo: 'email' | 'sem_email' | 'padrao' | 'restaurar'
        contexto_validacao: 'usuario' (perfil) ou 'admin' (painel).
        """
        if contexto_validacao == 'admin':
            modo = self.validar_modo_admin_usuario(tipo, modo)
        else:
            modo = self.validar_modo_usuario(tipo, modo)
        if modo == 'restaurar':
            self.restaurar_padrao_usuario(usuario, tipo)
            return PreferenciaComunicacao.objects.filter(usuario=usuario, tipo=tipo).first()

        defaults = {
            'herdar_padrao': herdar_padrao or modo == 'padrao',
            'email_ativo': None,
            'interno_ativo': None,
            'resumo_ativo': False,
            'atualizado_por': atualizado_por,
            'email': '',
        }
        if modo == 'padrao':
            defaults['herdar_padrao'] = True
            defaults['email_ativo'] = None
            defaults['interno_ativo'] = None
            defaults['resumo_ativo'] = False
        elif modo == 'email':
            defaults['herdar_padrao'] = False
            defaults['email_ativo'] = True
            defaults['interno_ativo'] = None
            defaults['resumo_ativo'] = False
        elif modo == 'sem_email':
            defaults['herdar_padrao'] = False
            defaults['email_ativo'] = False
            defaults['interno_ativo'] = None
            defaults['resumo_ativo'] = False

        pref, _ = PreferenciaComunicacao.objects.update_or_create(
            usuario=usuario,
            tipo=tipo,
            defaults=defaults,
        )
        return pref

    def salvar_preferencia_email_livre(
        self,
        *,
        email: str,
        tipo: TipoComunicacao,
        email_ativo: bool,
        atualizado_por=None,
        bloqueado_por_admin: bool = False,
        observacao: str = '',
    ) -> PreferenciaComunicacao:
        email_norm = self._normalizar_email(email)
        if not email_norm:
            raise ValueError('E-mail inválido.')
        if tipo.codigo in TIPOS_NUNCA_DESLIGAR and not email_ativo:
            raise ValueError('Tipo obrigatório não pode ser desativado.')

        pref, _ = PreferenciaComunicacao.objects.update_or_create(
            tipo=tipo,
            email=email_norm,
            usuario=None,
            defaults={
                'herdar_padrao': False,
                'email_ativo': email_ativo,
                'interno_ativo': None,
                'resumo_ativo': False,
                'bloqueado_por_admin': bloqueado_por_admin,
                'observacao': (observacao or '')[:500],
                'atualizado_por': atualizado_por,
            },
        )
        return pref

    def restaurar_padrao_usuario(self, usuario, tipo: TipoComunicacao) -> None:
        PreferenciaComunicacao.objects.filter(usuario=usuario, tipo=tipo).delete()

    def tipos_configuraveis_padrao_grupo(self):
        """Tipos exibidos na tela de padrões por grupo (futuro + router ativo)."""
        return TipoComunicacao.objects.filter(
            ativo=True,
            permite_admin_desativar_email=True,
        ).order_by('modulo', 'ordem', 'nome')
