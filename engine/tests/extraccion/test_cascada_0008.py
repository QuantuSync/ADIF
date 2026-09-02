"""Caso de aceptación de la sesión: expediente 6.24/28510.0008. 138.000 € en
licitación, 138.000 € en adjudicación, baja declarada del 54,00 % — el
sistema debe devolver 54,00 %, no 0 %. Encadena las cuatro etapas de esta
sesión (clasificar -> campos de etiqueta fija -> baja declarada -> detección
de precios unitarios) tal como las usaría el pipeline real, con los importes
sacados del PDF, no escritos a mano en el test.
"""
from decimal import Decimal

from app.extraccion.baja import extraer_baja_declarada
from app.extraccion.campos_lc27 import (
    extraer_importe_adjudicacion_lc27,
    extraer_importe_licitacion_lc27,
    extraer_numero_expediente_lc27,
)
from app.extraccion.clasificador import clasificar
from app.extraccion.normalizacion import parsear_importe_es
from app.extraccion.precios_unitarios import calcular_baja_efectiva
from app.extraccion.texto import extraer_texto
from app.models import TipoDocumento
from tests import fixtures as fx


def test_expediente_6_24_28510_0008_devuelve_54_por_ciento_no_cero():
    paginas = extraer_texto(fx.PROPUESTA_LC27_PRECIOS_UNITARIOS)

    clasificacion = clasificar(paginas)
    assert clasificacion.tipo == TipoDocumento.propuesta_lc27

    numero_expediente = extraer_numero_expediente_lc27(paginas)
    assert numero_expediente.valor == "6.24/28510.0008"

    importe_licitacion = parsear_importe_es(extraer_importe_licitacion_lc27(paginas).valor)
    importe_adjudicacion = parsear_importe_es(extraer_importe_adjudicacion_lc27(paginas).valor)
    assert importe_licitacion == Decimal("138000.00")
    assert importe_adjudicacion == Decimal("138000.00")

    baja = extraer_baja_declarada(paginas, tipo_documento=clasificacion.tipo)
    assert baja.baja == Decimal("0.5400")

    resultado = calcular_baja_efectiva(importe_licitacion, importe_adjudicacion, baja.baja)

    assert resultado.caso_precios_unitarios is True
    assert resultado.requiere_revision is False
    assert resultado.baja == Decimal("0.5400")
    assert resultado.baja != Decimal("0")  # la fórmula ingenua daría esto; no es lo que se pide
