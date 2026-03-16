"""
Importa usuarios em lote (CSV/XLSX), vincula obras e envia credenciais por e-mail.

Uso basico:
  python manage.py importar_usuarios_obras --arquivo usuarios.xlsx
  python manage.py importar_usuarios_obras --arquivo usuarios.csv --separador ";"

Colunas aceitas (case-insensitive; sem acento):
  - nome_completo (ou nome)
  - email (obrigatorio)
  - username (opcional)
  - grupos (opcional, default: Solicitante)  ex: "Solicitante|Mapa de Suprimentos"
  - obras (obrigatorio)                      ex: "224,259" (codes de core.Project)

Tambem aceita:
  - first_name / last_name no lugar de nome_completo
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.groups import GRUPOS
from core.models import Project, ProjectMember
from gestao_aprovacao.email_utils import enviar_email_credenciais_novo_usuario
from gestao_aprovacao.models import Obra, UserEmpresa, UserProfile, WorkOrderPermission


class Command(BaseCommand):
    help = (
        "Importa usuarios em lote, define senha padrao, vincula obras no Diario/Gestao "
        "e envia e-mail de credenciais."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--arquivo",
            type=str,
            required=True,
            help="Caminho do arquivo .csv/.xlsx com os usuarios.",
        )
        parser.add_argument(
            "--sheet",
            type=str,
            default=None,
            help="Nome da aba (apenas para Excel).",
        )
        parser.add_argument(
            "--separador",
            type=str,
            default=";",
            help='Separador do CSV (padrao: ";").',
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula importacao sem gravar no banco.",
        )
        parser.add_argument(
            "--atualizar-existentes",
            action="store_true",
            help="Atualiza usuario existente (nome/email/grupos/vinculos).",
        )
        parser.add_argument(
            "--resetar-senha-existentes",
            action="store_true",
            help="Se usar --atualizar-existentes, tambem redefine senha dos existentes.",
        )
        parser.add_argument(
            "--sem-email",
            action="store_true",
            help="Nao envia e-mail de credenciais.",
        )
        parser.add_argument(
            "--senha-ano",
            type=str,
            default="2026",
            help="Sufixo de ano da senha (padrao: 2026).",
        )
        parser.add_argument(
            "--grupo-default",
            type=str,
            default=GRUPOS.SOLICITANTE,
            help='Grupo usado quando a coluna "grupos" vier vazia (padrao: Solicitante).',
        )

    @staticmethod
    def _normalizar_texto(valor: object) -> str:
        if valor is None:
            return ""
        s = str(valor).strip()
        if not s or s.lower() == "nan":
            return ""
        return s

    @staticmethod
    def _normalize_key(chave: str) -> str:
        base = unicodedata.normalize("NFKD", chave or "")
        sem_acento = "".join(c for c in base if not unicodedata.combining(c))
        limpo = re.sub(r"[^a-zA-Z0-9]+", "_", sem_acento.strip().lower())
        return limpo.strip("_")

    @staticmethod
    def _split_lista_bruta(valor: str) -> List[str]:
        if not valor:
            return []
        partes = re.split(r"[,\n;|]+", valor)
        return [p.strip() for p in partes if p and p.strip()]

    def _resolver_grupo(self, nome: str) -> Optional[str]:
        if not nome:
            return None
        chave = self._normalize_key(nome)
        mapa = {
            "administrador": GRUPOS.ADMINISTRADOR,
            "admin": GRUPOS.ADMINISTRADOR,
            "responsavel_empresa": GRUPOS.RESPONSAVEL_EMPRESA,
            "responsavel": GRUPOS.RESPONSAVEL_EMPRESA,
            "aprovador": GRUPOS.APROVADOR,
            "solicitante": GRUPOS.SOLICITANTE,
            "diario_de_obra": GRUPOS.GERENTES,
            "diario": GRUPOS.GERENTES,
            "mapa_de_suprimentos": GRUPOS.ENGENHARIA,
            "mapa_suprimentos": GRUPOS.ENGENHARIA,
            "mapa": GRUPOS.ENGENHARIA,
        }
        if chave in mapa:
            return mapa[chave]
        # Nome oficial vindo da planilha
        if nome in GRUPOS.TODOS:
            return nome
        return None

    def _gerar_senha(self, first_name: str, last_name: str, ano: str) -> str:
        f = (first_name or "").strip()
        l = (last_name or "").strip()
        ini_1 = f[0].upper() if f else "X"
        ini_2 = l[0].lower() if l else "x"
        return f"@#{ini_1}{ini_2}{ano}"

    def _quebrar_nome(self, nome_completo: str) -> Tuple[str, str]:
        nome_limpo = self._normalizar_texto(nome_completo)
        if not nome_limpo:
            return "", ""
        partes = [p for p in nome_limpo.split(" ") if p]
        if len(partes) == 1:
            return partes[0], ""
        return partes[0], " ".join(partes[1:])

    def _gerar_username(self, first_name: str, last_name: str, email: str) -> str:
        if email and "@" in email:
            base = email.split("@")[0]
        else:
            base = f"{first_name}.{(last_name or '').split(' ')[0]}".strip(".")
        base = self._normalize_key(base).replace("_", ".")
        base = re.sub(r"[^a-z0-9._-]", "", base.lower()) or "usuario"
        username = base
        idx = 1
        while User.objects.filter(username=username).exists():
            idx += 1
            username = f"{base}{idx}"
        return username

    def _resolver_projeto_token(self, token: str) -> Optional[Project]:
        if not token:
            return None
        t = token.strip()
        projeto = Project.objects.filter(code__iexact=t, is_active=True).first()
        if projeto:
            return projeto
        por_nome_exato = Project.objects.filter(name__iexact=t, is_active=True)
        if por_nome_exato.count() == 1:
            return por_nome_exato.first()
        return None

    def _vincular_usuario_obras(
        self,
        user: User,
        grupos_validos: Sequence[str],
        projetos: Sequence[Project],
        atualizar_existentes: bool,
    ) -> Dict[str, int]:
        stats = {
            "project_members_novos": 0,
            "permissoes_novas": 0,
            "user_empresa_novos": 0,
        }

        if atualizar_existentes:
            ProjectMember.objects.filter(user=user).delete()
            WorkOrderPermission.objects.filter(usuario=user).delete()

        # Diario de obra
        for proj in projetos:
            _, criado = ProjectMember.objects.get_or_create(user=user, project=proj)
            if criado:
                stats["project_members_novos"] += 1

        # Gestao (WorkOrderPermission) a partir das obras vinculadas ao project
        obras_gestao = Obra.objects.filter(project__in=projetos, ativo=True).select_related("empresa")
        for obra in obras_gestao:
            if GRUPOS.SOLICITANTE in grupos_validos:
                _, criado = WorkOrderPermission.objects.get_or_create(
                    usuario=user,
                    obra=obra,
                    tipo_permissao="solicitante",
                    defaults={"ativo": True},
                )
                if criado:
                    stats["permissoes_novas"] += 1
            if GRUPOS.APROVADOR in grupos_validos:
                _, criado = WorkOrderPermission.objects.get_or_create(
                    usuario=user,
                    obra=obra,
                    tipo_permissao="aprovador",
                    defaults={"ativo": True},
                )
                if criado:
                    stats["permissoes_novas"] += 1
            if obra.empresa_id:
                _, criado = UserEmpresa.objects.get_or_create(
                    usuario=user,
                    empresa=obra.empresa,
                    defaults={"ativo": True},
                )
                if criado:
                    stats["user_empresa_novos"] += 1

        return stats

    def _ler_arquivo(self, path: str, sheet: Optional[str], separador: str) -> pd.DataFrame:
        ext = os.path.splitext(path)[1].lower()
        if ext in (".xlsx", ".xls"):
            kwargs = {"dtype": str}
            if sheet:
                kwargs["sheet_name"] = sheet
            return pd.read_excel(path, **kwargs).fillna("")
        if ext == ".csv":
            return pd.read_csv(path, dtype=str, sep=separador).fillna("")
        raise CommandError("Formato nao suportado. Use .csv, .xlsx ou .xls.")

    def _mapear_colunas(self, df: pd.DataFrame) -> pd.DataFrame:
        mapping = {}
        for col in df.columns:
            mapping[col] = self._normalize_key(str(col))
        return df.rename(columns=mapping)

    def handle(self, *args, **options):
        arquivo = options["arquivo"]
        sheet = options["sheet"]
        separador = options["separador"]
        dry_run = options["dry_run"]
        atualizar_existentes = options["atualizar_existentes"]
        resetar_senha_existentes = options["resetar_senha_existentes"]
        sem_email = options["sem_email"]
        senha_ano = str(options["senha_ano"]).strip()
        grupo_default = options["grupo_default"].strip()

        if not os.path.exists(arquivo):
            raise CommandError(f"Arquivo nao encontrado: {arquivo}")
        if not senha_ano.isdigit() or len(senha_ano) != 4:
            raise CommandError("Parametro --senha-ano invalido. Exemplo: 2026")

        grupo_default_resolvido = self._resolver_grupo(grupo_default)
        if not grupo_default_resolvido:
            raise CommandError(f'Grupo default invalido: "{grupo_default}"')

        for nome in GRUPOS.TODOS:
            Group.objects.get_or_create(name=nome)

        df = self._ler_arquivo(arquivo, sheet, separador)
        df = self._mapear_colunas(df)
        total_linhas = len(df.index)
        if total_linhas == 0:
            self.stdout.write(self.style.WARNING("Arquivo vazio. Nada para importar."))
            return

        self.stdout.write(f"Arquivo carregado com {total_linhas} linha(s).")
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run ativo: nenhuma alteracao sera persistida."))

        stats = {
            "processadas": 0,
            "criadas": 0,
            "atualizadas": 0,
            "ignoradas": 0,
            "erros": 0,
            "emails_enviados": 0,
            "emails_falha": 0,
            "project_members_novos": 0,
            "permissoes_novas": 0,
            "user_empresa_novos": 0,
        }

        with transaction.atomic():
            for idx, row in df.iterrows():
                linha = idx + 2  # +2 por causa do header
                stats["processadas"] += 1

                nome_completo = self._normalizar_texto(row.get("nome_completo") or row.get("nome"))
                first_name = self._normalizar_texto(row.get("first_name"))
                last_name = self._normalizar_texto(row.get("last_name"))
                email = self._normalizar_texto(row.get("email")).lower()
                username = self._normalizar_texto(row.get("username"))

                if not first_name and not last_name and nome_completo:
                    first_name, last_name = self._quebrar_nome(nome_completo)

                if not email:
                    stats["erros"] += 1
                    self.stdout.write(self.style.ERROR(f"Linha {linha}: e-mail obrigatorio."))
                    continue
                if not username:
                    username = self._gerar_username(first_name, last_name, email)

                grupos_raw = self._normalizar_texto(row.get("grupos"))
                grupos_lista = self._split_lista_bruta(grupos_raw) or [grupo_default_resolvido]
                grupos_validos: List[str] = []
                grupos_invalidos: List[str] = []
                for g in grupos_lista:
                    resolvido = self._resolver_grupo(g)
                    if resolvido:
                        grupos_validos.append(resolvido)
                    else:
                        grupos_invalidos.append(g)
                grupos_validos = sorted(set(grupos_validos), key=lambda n: GRUPOS.TODOS.index(n))

                if not grupos_validos:
                    stats["erros"] += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"Linha {linha}: nenhum grupo valido. Valores recebidos: {grupos_lista}"
                        )
                    )
                    continue

                obras_raw = self._normalizar_texto(
                    row.get("obras") or row.get("obra") or row.get("projects") or row.get("projetos")
                )
                obra_tokens = self._split_lista_bruta(obras_raw)
                if not obra_tokens:
                    stats["erros"] += 1
                    self.stdout.write(self.style.ERROR(f"Linha {linha}: informe ao menos uma obra/projeto em 'obras'."))
                    continue

                projetos: List[Project] = []
                tokens_nao_resolvidos: List[str] = []
                for token in obra_tokens:
                    projeto = self._resolver_projeto_token(token)
                    if projeto:
                        projetos.append(projeto)
                    else:
                        tokens_nao_resolvidos.append(token)
                projetos = list({p.id: p for p in projetos}.values())

                if not projetos:
                    stats["erros"] += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"Linha {linha}: nenhuma obra/projeto encontrado para tokens {obra_tokens}."
                        )
                    )
                    continue

                user = User.objects.filter(username=username).first()
                criado = False
                senha_plana = self._gerar_senha(first_name, last_name, senha_ano)

                if user and not atualizar_existentes:
                    stats["ignoradas"] += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'Linha {linha}: usuario "{username}" ja existe (ignorado; use --atualizar-existentes).'
                        )
                    )
                    continue

                if not user:
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=senha_plana,
                        first_name=first_name,
                        last_name=last_name,
                    )
                    criado = True
                    stats["criadas"] += 1
                else:
                    user.email = email
                    user.first_name = first_name
                    user.last_name = last_name
                    if resetar_senha_existentes:
                        user.set_password(senha_plana)
                    user.save()
                    stats["atualizadas"] += 1

                user.groups.clear()
                for grupo_nome in grupos_validos:
                    grupo_obj = Group.objects.get(name=grupo_nome)
                    user.groups.add(grupo_obj)

                UserProfile.objects.get_or_create(usuario=user)

                vinc_stats = self._vincular_usuario_obras(
                    user=user,
                    grupos_validos=grupos_validos,
                    projetos=projetos,
                    atualizar_existentes=atualizar_existentes,
                )
                for key, val in vinc_stats.items():
                    stats[key] += val

                enviar_credenciais = (not sem_email) and (criado or resetar_senha_existentes)
                if enviar_credenciais and email:
                    nome_msg = f"{first_name} {last_name}".strip() or username
                    enviado = enviar_email_credenciais_novo_usuario(
                        email_destino=email,
                        username=username,
                        senha_plana=senha_plana,
                        nome_completo=nome_msg,
                    )
                    if enviado:
                        stats["emails_enviados"] += 1
                    else:
                        stats["emails_falha"] += 1

                aviso_grupos = ""
                if grupos_invalidos:
                    aviso_grupos = f" | grupos ignorados: {', '.join(grupos_invalidos)}"
                aviso_tokens = ""
                if tokens_nao_resolvidos:
                    aviso_tokens = f" | obras nao encontradas: {', '.join(tokens_nao_resolvidos)}"
                acao = "CRIADO" if criado else "ATUALIZADO"
                self.stdout.write(
                    f"[{acao}] {username} -> {email} | projetos: {len(projetos)} | grupos: {', '.join(grupos_validos)}"
                    f"{aviso_grupos}{aviso_tokens}"
                )

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Resumo importacao de usuarios"))
        self.stdout.write(f"  Processadas: {stats['processadas']}")
        self.stdout.write(f"  Criadas: {stats['criadas']}")
        self.stdout.write(f"  Atualizadas: {stats['atualizadas']}")
        self.stdout.write(f"  Ignoradas: {stats['ignoradas']}")
        self.stdout.write(f"  Erros: {stats['erros']}")
        self.stdout.write(f"  E-mails enviados: {stats['emails_enviados']}")
        self.stdout.write(f"  E-mails com falha: {stats['emails_falha']}")
        self.stdout.write(f"  Viculos Diario (ProjectMember): {stats['project_members_novos']}")
        self.stdout.write(f"  Permissoes Gestao (WorkOrderPermission): {stats['permissoes_novas']}")
        self.stdout.write(f"  Vinculos Empresa (UserEmpresa): {stats['user_empresa_novos']}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run finalizado. Nenhuma alteracao foi salva."))
        else:
            self.stdout.write(self.style.SUCCESS("Importacao concluida."))
