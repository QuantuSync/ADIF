from app.extraccion.campos_lc27 import extraer_adjudicatario_lc27, extraer_objeto_contrato_lc27
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
    # Plantilla distinta (L9_AF.01-FE, CONTEXTO.md sección 17) pero misma
    # estructura de bloque de firma que la Propuesta LC.27.
    paginas = extraer_texto(fx.RESOLUCION_ADJUDICACION)
    campo = extraer_objeto_contrato_lc27(paginas)

    assert campo.valor == (
        "SUMINISTRO DE BALASTO PARA LAS NECESIDADES DE OBRAS Y "
        "MANTENIMIENTO EN LA RED FERROVIARIA DE INTERÉS GENERAL (ZONA NOROESTE). 2 LOTES."
    )


def test_adjudicatario_propuesta_lc27_camino_lote_unico():
    # Bloque 1, sesión de descubrimiento inverso (docs/descubrimiento-
    # inverso-matriz-pedidos.md sección 7): dos de las tres matrices de
    # carril declaran su adjudicatario solo en Propuesta LC.27, camino de
    # lote único (sin ningún "LOTE N" en el texto). Documento real.
    paginas = extraer_texto(fx.PROPUESTA_LC27_PRECIOS_UNITARIOS)
    campo = extraer_adjudicatario_lc27(paginas)

    assert campo.valor == "PASTOR EPPS S.L."


def test_adjudicatario_propuesta_lc27_sin_la_palabra_con_delante_del_nif():
    # Documento real de una de las tres matrices de carril
    # (6.23/28510.0102): "...S.A.– NIF:" con guion, no "con NIF:" como el
    # resto del corpus -- verificado que la regex generalizada la cubre sin
    # dejar de casar la forma estricta.
    paginas = extraer_texto(fx.PROPUESTA_LC27_ADJUDICATARIO_SIN_CON)
    campo = extraer_adjudicatario_lc27(paginas)

    assert campo.valor == "ARCELORMITTAL ESPAÑA, S.A."
