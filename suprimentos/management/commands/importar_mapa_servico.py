from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import unicodedata

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from mapa_obras.models import Obra
from suprimentos.models import ImportacaoMapaServico, ItemMapaServico, ItemMapaServicoStatusRef


def _normalize_col(name: object) -> str:
    if name is None:
        return ""
    return str(name).strip().upper()


def _clean_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "nat", "<na>"}:
        return ""
    return text


def _to_decimal(value: object) -> Decimal | None:
    text = _clean_text(value)
    if not text:
        return None
    normalized = (
        text.replace("R$", "")
        .replace("%", "")
        .replace(" ", "")
        .replace("\u00a0", "")
    )
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")
    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None


def _to_date(value: object):
    text = _clean_text(value)
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date()


def _norm_key(value: object) -> str:
    text = _clean_text(value).upper()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("ASCII")
    return " ".join(text.split())


def _parse_status_sheet(file_path: Path, status_sheet_name: str) -> tuple[dict[str, dict], int]:
    xls = pd.ExcelFile(file_path)
    if status_sheet_name not in xls.sheet_names:
        return {}, 0

    raw_df = pd.read_excel(file_path, sheet_name=status_sheet_name, header=None, dtype=object)
    if raw_df.empty:
        return {}, 0

    header_idx = None
    for idx in range(min(len(raw_df.index), 80)):
        row_vals = [_norm_key(v) for v in raw_df.iloc[idx].tolist()]
        if "SERVICO" in row_vals or "SERVICO" in "".join(row_vals):
            header_idx = idx
            break
    if header_idx is None:
        return {}, 0

    header_vals = [_norm_key(v) for v in raw_df.iloc[header_idx].tolist()]
    data_df = raw_df.iloc[header_idx + 1 :].copy()
    data_df.columns = header_vals
    data_df = data_df.dropna(how="all")

    def _pick_col(*candidates: str):
        for col in data_df.columns:
            if col in candidates:
                return col
        return None

    col_servico = _pick_col("SERVICO")
    col_status = _pick_col("STATUS")
    col_situacao = _pick_col("SITUACAO")
    col_prazo = _pick_col("PRAZO EXECUCAO", "PRAZO")
    col_resp = _pick_col("RESPONSABILIDADE")
    if not col_servico:
        return {}, 0

    parsed: dict[str, dict] = {}
    for _, row in data_df.iterrows():
        atividade = _clean_text(row.get(col_servico))
        if not atividade:
            continue
        atividade_key = _norm_key(atividade)
        if not atividade_key:
            continue
        parsed[atividade_key] = {
            "atividade": atividade[:200],
            "status_macro": _clean_text(row.get(col_status))[:80] if col_status else "",
            "situacao": _clean_text(row.get(col_situacao)) if col_situacao else "",
            "prazo_execucao": _clean_text(row.get(col_prazo))[:50] if col_prazo else "",
            "responsabilidade": _clean_text(row.get(col_resp))[:120] if col_resp else "",
        }
    return parsed, len(data_df.index)


class Command(BaseCommand):
    help = "Importa mapa de serviço (Excel) para ItemMapaServico."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, required=True, help="Caminho do arquivo .xlsx")
        parser.add_argument(
            "--obra-id",
            type=int,
            required=True,
            help="ID da obra que receberá os registros do mapa de serviço.",
        )
        parser.add_argument(
            "--sheet",
            type=str,
            default="DADOS",
            help="Nome da aba principal (padrão: DADOS).",
        )
        parser.add_argument(
            "--limpar-antes",
            action="store_true",
            help="Apaga os itens atuais da obra antes de importar.",
        )
        parser.add_argument(
            "--strict-quality",
            action="store_true",
            help="Ignora linhas com campos críticos ausentes/inválidos para aumentar precisão.",
        )
        parser.add_argument(
            "--status-sheet",
            type=str,
            default="STATUS",
            help="Nome da aba complementar de status/situação (padrão: STATUS).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        file_path = Path(options["file"])
        if not file_path.exists():
            raise CommandError(f"Arquivo não encontrado: {file_path}")

        obra = Obra.objects.filter(pk=options["obra_id"], ativa=True).first()
        if not obra:
            raise CommandError(f"Obra ativa não encontrada para id={options['obra_id']}")

        sheet_name = options["sheet"]
        status_sheet_name = options["status_sheet"]
        self.stdout.write(f"Lendo arquivo: {file_path.name}")
        xls = pd.ExcelFile(file_path)
        if sheet_name not in xls.sheet_names:
            if "Plan1" in xls.sheet_names:
                self.stdout.write(
                    self.style.WARNING(
                        f"Aba '{sheet_name}' não encontrada. Usando fallback 'Plan1'."
                    )
                )
                sheet_name = "Plan1"
            else:
                raise CommandError(f"Aba '{sheet_name}' não encontrada no arquivo.")

        df = pd.read_excel(file_path, sheet_name=sheet_name, dtype=object)
        if df.empty:
            raise CommandError("A aba está vazia.")

        df.columns = [_normalize_col(c) for c in df.columns]
        col_map = {
            "setor": ["SETOR"],
            "bloco": ["BLOCO"],
            "pavimento": ["PAVIMENTO"],
            "apto": ["APTO", "UNIDADE"],
            "atividade": ["ATIVIDADE", "SERVIÇO", "SERVICO"],
            "grupo_servicos": ["GRUPO DE SERVIÇOS", "GRUPO DE SERVICOS", "GRUPO DE SERVIÇO", "GRUPO DE SERVICO"],
            "status": ["STATUS"],
            "observacao": ["OBSERVAÇÃO", "OBSERVACAO"],
            "custo": ["CUSTO"],
            "data_termino": ["DATA DE TERMINO", "DATA DE TÉRMINO", "DATA TERMINO"],
        }

        resolved = {}
        for field, candidates in col_map.items():
            for candidate in candidates:
                normalized = _normalize_col(candidate)
                if normalized in df.columns:
                    resolved[field] = normalized
                    break

        if "atividade" not in resolved:
            raise CommandError("Não encontrei coluna de atividade (ATIVIDADE/SERVIÇO).")

        if options["limpar_antes"]:
            deleted, _ = ItemMapaServico.objects.filter(obra=obra).delete()
            self.stdout.write(self.style.WARNING(f"Itens antigos removidos: {deleted}"))

        importacao = ImportacaoMapaServico.objects.create(
            obra=obra,
            usuario=None,
            nome_arquivo=file_path.name[:255],
            aba_origem=sheet_name[:120],
            total_linhas_lidas=len(df.index),
            total_linhas_importadas=0,
        )

        imported = 0
        updated = 0
        skipped = 0
        skipped_quality = 0
        duplicate_keys = 0
        invalid_status = 0
        invalid_date = 0
        invalid_cost = 0
        missing_bloco = 0
        missing_pavimento = 0
        missing_apto = 0
        missing_status = 0
        strict_quality = bool(options.get("strict_quality"))
        seen_keys = set()
        now = timezone.now()

        for _, row in df.iterrows():
            atividade = _clean_text(row.get(resolved.get("atividade", ""), ""))
            if not atividade:
                skipped += 1
                continue

            setor = _clean_text(row.get(resolved.get("setor", ""), ""))
            bloco = _clean_text(row.get(resolved.get("bloco", ""), ""))
            pavimento = _clean_text(row.get(resolved.get("pavimento", ""), ""))
            apto = _clean_text(row.get(resolved.get("apto", ""), ""))
            grupo = _clean_text(row.get(resolved.get("grupo_servicos", ""), ""))
            status_txt = _clean_text(row.get(resolved.get("status", ""), ""))
            observacao = _clean_text(row.get(resolved.get("observacao", ""), ""))
            custo = _to_decimal(row.get(resolved.get("custo", ""), None))
            data_termino = _to_date(row.get(resolved.get("data_termino", ""), None))
            custo_raw = _clean_text(row.get(resolved.get("custo", ""), ""))
            data_raw = _clean_text(row.get(resolved.get("data_termino", ""), ""))

            status_dec = _to_decimal(status_txt)
            if status_txt and status_dec is None:
                invalid_status += 1
            if custo_raw and custo is None:
                invalid_cost += 1
            if data_raw and data_termino is None:
                invalid_date += 1
            if not bloco:
                missing_bloco += 1
            if not pavimento:
                missing_pavimento += 1
            if not apto:
                missing_apto += 1
            if not status_txt and status_dec is None:
                missing_status += 1
            if status_dec is not None and status_dec > Decimal("1.000"):
                # Alguns layouts usam 0..100. Traz para 0..1.
                status_dec = (status_dec / Decimal("100")).quantize(Decimal("0.001"))

            chave_uid = "|".join(
                [
                    setor.strip().upper(),
                    bloco.strip().upper(),
                    pavimento.strip().upper(),
                    apto.strip().upper(),
                    atividade.strip().upper(),
                ]
            )[:255]

            if chave_uid in seen_keys:
                duplicate_keys += 1
                continue
            seen_keys.add(chave_uid)

            if strict_quality and (not bloco or not pavimento or not apto or ((not status_txt) and status_dec is None)):
                skipped_quality += 1
                continue

            defaults = {
                "importacao": importacao,
                "setor": setor,
                "bloco": bloco,
                "pavimento": pavimento,
                "apto": apto,
                "atividade": atividade[:200],
                "grupo_servicos": grupo[:120],
                "status_texto": status_txt[:100],
                "status_percentual": status_dec,
                "custo": custo,
                "observacao": observacao,
                "data_termino": data_termino,
                "updated_at": now,
            }

            item, created = ItemMapaServico.objects.update_or_create(
                obra=obra,
                chave_uid=chave_uid,
                defaults=defaults,
            )
            if created:
                imported += 1
            else:
                updated += 1

        importacao.total_linhas_importadas = imported + updated
        importacao.save(update_fields=["total_linhas_importadas"])

        # Fase 2: enriquecer atividade com dados da aba STATUS.
        status_parsed, status_rows_lidas = _parse_status_sheet(file_path, status_sheet_name)
        status_importados = 0
        if status_parsed:
            ItemMapaServicoStatusRef.objects.filter(obra=obra).delete()
            refs = []
            for atividade_key, data in status_parsed.items():
                refs.append(
                    ItemMapaServicoStatusRef(
                        obra=obra,
                        importacao=importacao,
                        atividade=data["atividade"],
                        atividade_chave=atividade_key[:220],
                        status_macro=data["status_macro"],
                        situacao=data["situacao"],
                        prazo_execucao=data["prazo_execucao"],
                        responsabilidade=data["responsabilidade"],
                    )
                )
            if refs:
                ItemMapaServicoStatusRef.objects.bulk_create(refs, batch_size=1000)
                status_importados = len(refs)

        processed = imported + updated
        if processed:
            # Score baseado na presença dos campos críticos no conjunto final.
            quality_penalty = (
                (missing_bloco / len(df.index)) * 20
                + (missing_pavimento / len(df.index)) * 20
                + (missing_apto / len(df.index)) * 20
                + (missing_status / len(df.index)) * 25
                + (invalid_status / len(df.index)) * 15
            )
            quality_score = max(0, round(100 - quality_penalty, 2))
        else:
            quality_score = 0

        self.stdout.write(self.style.SUCCESS("Importação concluída."))
        self.stdout.write(f"Obra: {obra.nome} (id={obra.id})")
        self.stdout.write(f"Aba: {sheet_name}")
        self.stdout.write(f"Linhas lidas: {len(df.index)}")
        self.stdout.write(f"Criados: {imported}")
        self.stdout.write(f"Atualizados: {updated}")
        self.stdout.write(f"Ignorados (sem atividade): {skipped}")
        self.stdout.write(f"Ignorados por qualidade (strict): {skipped_quality}")
        self.stdout.write(f"Duplicados no arquivo (mesma chave): {duplicate_keys}")
        self.stdout.write(f"Status inválido (mantido texto): {invalid_status}")
        self.stdout.write(f"Custo inválido (vazio): {invalid_cost}")
        self.stdout.write(f"Data inválida (vazia): {invalid_date}")
        self.stdout.write(f"Sem bloco: {missing_bloco}")
        self.stdout.write(f"Sem pavimento: {missing_pavimento}")
        self.stdout.write(f"Sem apto: {missing_apto}")
        self.stdout.write(f"Sem status (% e texto): {missing_status}")
        self.stdout.write(f"Score de qualidade da carga: {quality_score}%")
        if status_rows_lidas:
            self.stdout.write(f"Aba STATUS lida: {status_rows_lidas} linhas")
            self.stdout.write(f"Referências STATUS importadas: {status_importados}")
        else:
            self.stdout.write(f"Aba STATUS não encontrada/sem dados (aba esperada: {status_sheet_name})")
