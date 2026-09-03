from app.extraccion.texto import PaginaTexto, es_documento_escaneado, extraer_texto
from tests import fixtures as fx


def test_documento_con_texto_normal_no_se_marca_escaneado():
    paginas = extraer_texto(fx.ANEJO_PRECIOS_GUANTES)
    assert es_documento_escaneado(paginas) is False


def test_documento_escaneado_real_se_detecta():
    # CLAUDE.md sección 3: el único documento escaneado confirmado del
    # corpus real (100 páginas, cada una una imagen a página completa, sin
    # ningún carácter de texto ni con pdfplumber ni con pypdf).
    paginas = extraer_texto(fx.DOCUMENTO_ESCANEADO_SIN_TEXTO)
    assert es_documento_escaneado(paginas) is True


def test_documento_sin_paginas_no_se_marca_escaneado():
    # Caso distinto: sin páginas en absoluto no es "escaneado", es vacío.
    assert es_documento_escaneado([]) is False


def test_umbral_deja_margen_a_un_artefacto_suelto():
    paginas = [PaginaTexto(numero=1, texto=""), PaginaTexto(numero=2, texto="   ")]
    assert es_documento_escaneado(paginas) is True

    paginas_con_texto_real = [PaginaTexto(numero=1, texto="PLIEGO DE PRESCRIPCIONES TÉCNICAS")]
    assert es_documento_escaneado(paginas_con_texto_real) is False
