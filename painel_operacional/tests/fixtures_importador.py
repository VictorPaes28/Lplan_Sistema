from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook


def _xlsx_from_sheets(sheets: dict[str, list[list[object]]]) -> bytes:
    wb = Workbook()
    default = wb.active
    wb.remove(default)
    for name, rows in sheets.items():
        ws = wb.create_sheet(title=name[:31] or "Sheet")
        for row in rows:
            ws.append(list(row))
    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out.getvalue()


def workbook_edificio_residencial() -> bytes:
    capa = [["MAPA DE CONTROLE"], [""], ["Gerado por fornecedor externo"]]
    dados = [
        ["SETOR", "BLOCO", "PAVIMENTO", "APTO", "ATIVIDADE", "STATUS"],
        ["HAB", "A1", "TERREO", "101", "ARMACAO PILAR", "100%"],
        ["HAB", "A1", "TERREO", "101", "ALVENARIA", "35%"],
        ["HAB", "A1", "TERREO", "102", "ARMACAO PILAR", "100%"],
        ["HAB", "A1", "TERREO", "102", "ALVENARIA", "10%"],
        ["HAB", "A2", "1 PAV", "201", "ARMACAO PILAR", "90%"],
        ["HAB", "A2", "1 PAV", "201", "ALVENARIA", "0%"],
    ]
    return _xlsx_from_sheets({"CAPA": capa, "DADOS": dados})


def workbook_resort_multieixo() -> bytes:
    guia = [["RESORT - CONTROLE"], ["Aba operacional: EXECUCAO"]]
    execucao = [
        ["TORRE", "ALA", "TIPO DE UNIDADE", "ATIVIDADE", "AVANCO"],
        ["SOL", "NORTE", "BANGALO", "FUNDACAO", "100"],
        ["SOL", "NORTE", "BANGALO", "ESTRUTURA", "80"],
        ["SOL", "SUL", "SUITE", "FUNDACAO", "100"],
        ["SOL", "SUL", "SUITE", "ESTRUTURA", "45"],
        ["MAR", "LESTE", "LOBBY", "FUNDACAO", "100"],
        ["MAR", "LESTE", "LOBBY", "ESTRUTURA", "20"],
    ]
    return _xlsx_from_sheets({"GUIA": guia, "EXECUCAO": execucao})


def workbook_atividade_em_colunas() -> bytes:
    matriz = [
        ["ATIVIDADE", "UH 101", "UH 102", "UH 103", "OBS"],
        ["FUNDACAO", "100%", "100%", "95%", ""],
        ["ESTRUTURA", "80%", "72%", "68%", ""],
        ["ALVENARIA", "25%", "18%", "5%", ""],
    ]
    return _xlsx_from_sheets({"MATRIZ": matriz})


def workbook_baixa_confianca() -> bytes:
    rows = [
        ["RELATORIO", "SEM MODELO"],  # sem campos-chave esperados
        ["CHAVE", "VALOR"],
        ["A", "B"],
        ["C", "D"],
    ]
    return _xlsx_from_sheets({"DUMP": rows})


def workbook_multiabas_operacional_nome_nao_padrao() -> bytes:
    painel = [
        ["PAINEL EXECUTIVO"],
        ["INDICADOR", "VALOR"],
        ["PRAZO", "78%"],
        ["CUSTO", "R$ 1.200.000"],
    ]
    operacional = [
        ["REGIAO", "TORRE", "NIVEL", "UNIDADE", "ATIVIDADE", "GRUPO DE SERVIÇOS", "STATUS", "OBSERVAÇÃO"],
        ["NORTE", "T1", "1P", "101", "ARMAÇÃO PILAR", "ESTRUTURA", "100%", ""],
        ["NORTE", "T1", "1P", "101", "ARMAÇÃO VIGA", "ESTRUTURA", "70%", "frente"],
        ["NORTE", "T1", "1P", "102", "ALVENARIA", "VEDAÇÕES", "20%", ""],
    ]
    apoio = [
        ["ATIVIDADE", "RESPONSÁVEL"],
        ["ARMAÇÃO PILAR", "ENG"],
        ["ALVENARIA", "ENG"],
    ]
    return _xlsx_from_sheets({"PAINEL": painel, "BASE_UNIDADES": operacional, "APOIO": apoio})


def workbook_tabular_sem_grupo_com_auxiliares() -> bytes:
    rows = [
        ["SETOR", "BLOCO", "PAVIMENTO", "APTO", "ATIVIDADE", "STATUS", "CUSTO", "DATA DE TERMINO"],
        ["HAB", "B2", "2P", "201", "CHAPISCO INTERNO", "45%", "1000", "2026-08-10"],
        ["HAB", "B2", "2P", "201", "EMBOÇO INTERNO", "10%", "1000", "2026-08-11"],
        ["HAB", "B2", "2P", "202", "CHAPISCO INTERNO", "60%", "1000", "2026-08-12"],
    ]
    return _xlsx_from_sheets({"Operação": rows})


def workbook_tabular_colunas_reordenadas() -> bytes:
    rows = [
        ["DATA DE TERMINO", "OBSERVAÇÃO", "STATUS", "GRUPO DE SERVIÇOS", "ATIVIDADE", "SETOR", "BLOCO", "PAVIMENTO", "APTO"],
        ["2026-09-01", "", "1", "ESTRUTURA", "CONCRETO PILAR", "HAB", "C1", "3P", "301"],
        ["2026-09-02", "ok", "0.5", "ESTRUTURA", "FÔRMA PILAR", "HAB", "C1", "3P", "301"],
        ["2026-09-03", "", "0", "VEDAÇÕES", "ELEVAÇÃO DE ALVENARIA", "HAB", "C1", "3P", "302"],
    ]
    return _xlsx_from_sheets({"QualquerNome": rows})


def workbook_grande_com_atividades_apos_linha_2500() -> bytes:
    rows = [["SETOR", "BLOCO", "PAVIMENTO", "APTO", "ATIVIDADE", "STATUS"]]
    base_atividades = [f"ATV_BASE_{i}" for i in range(1, 11)]
    extras = [f"ATV_EXTRA_{i}" for i in range(1, 6)]
    # Primeiras 2500 linhas: só atividades base.
    for i in range(1, 2501):
        rows.append(["HAB", "A1", "T", str(100 + (i % 50)), base_atividades[i % len(base_atividades)], "50%"])
    # Linhas seguintes: adiciona atividades extras que antes ficavam fora do limite antigo.
    for i in range(2501, 2801):
        rows.append(["HAB", "A1", "1P", str(200 + (i % 50)), extras[i % len(extras)], "75%"])
    return _xlsx_from_sheets({"OPERACIONAL": rows})

