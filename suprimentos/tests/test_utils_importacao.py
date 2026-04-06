from suprimentos.utils_importacao import sanitizar_texto_sienge


def test_sanitizar_remove_controle_e_normaliza_traco():
    texto = "\u0096 CIMENTO \u2013 CP II"
    assert sanitizar_texto_sienge(texto) == "CIMENTO - CP II"


def test_sanitizar_trata_tokens_na_como_vazio():
    assert sanitizar_texto_sienge("<NA>") == ""
    assert sanitizar_texto_sienge("nan") == ""
    assert sanitizar_texto_sienge("NaT") == ""


def test_sanitizar_respeita_max_length():
    assert len(sanitizar_texto_sienge("x" * 999, max_length=500)) == 500
