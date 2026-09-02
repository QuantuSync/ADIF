from app.extraccion.campos_lc27 import extraer_objeto_contrato_lc27
from app.extraccion.texto import extraer_texto
from tests import fixtures as fx


def test_objeto_contrato_propuesta_lc27():
    paginas = extraer_texto(fx.PROPUESTA_LC27_PRECIOS_UNITARIOS)
    campo = extraer_objeto_contrato_lc27(paginas)

    assert campo.valor == "SUMINISTRO DE GUANTES CONTRA RIESGO ELECTRICO."
    assert campo.pagina == 2


def test_objeto_contrato_propuesta_lc27_multilinea_y_varios_lotes():
    paginas = extraer_texto(fx.PROPUESTA_LC27_UTE)
    campo = extraer_objeto_contrato_lc27(paginas)

    assert campo.valor == "SUMINISTRO DE TRAVIESAS DE MADERA Y ELEMENTOS AUXILIARES. 2 LOTES"


def test_objeto_contrato_resolucion_adjudicacion():
    # Plantilla distinta (L9_AF.01-FE, CLAUDE.md sección 17) pero misma
    # estructura de bloque de firma que la Propuesta LC.27.
    paginas = extraer_texto(fx.RESOLUCION_ADJUDICACION)
    campo = extraer_objeto_contrato_lc27(paginas)

    assert campo.valor == (
        "SUMINISTRO DE BALASTO PARA LAS NECESIDADES DE OBRAS Y "
        "MANTENIMIENTO EN LA RED FERROVIARIA DE INTERÉS GENERAL (ZONA NOROESTE). 2 LOTES."
    )
