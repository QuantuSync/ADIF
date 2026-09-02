from decimal import Decimal

from app.extraccion.baja import BajaDeclarada, elegir_baja_preferida, extraer_baja_declarada
from app.extraccion.texto import extraer_texto
from app.models import TipoDocumento
from tests import fixtures as fx


def test_baja_en_propuesta_lc27_individual():
    r = extraer_baja_declarada(extraer_texto(fx.PROPUESTA_LC27_PRECIOS_UNITARIOS))
    assert r.baja == Decimal("0.5400")
    assert r.pagina == 1


def test_baja_en_propuesta_lc27_ute():
    r = extraer_baja_declarada(extraer_texto(fx.PROPUESTA_LC27_UTE))
    assert r.baja == Decimal("0.0050")


def test_baja_en_resolucion_adjudicacion():
    r = extraer_baja_declarada(extraer_texto(fx.RESOLUCION_ADJUDICACION))
    assert r.baja == Decimal("0.0450")


def test_baja_en_contrato():
    r = extraer_baja_declarada(extraer_texto(fx.CONTRATO_PRECIOS_UNITARIOS))
    assert r.baja == Decimal("0.5400")


def test_propuesta_y_contrato_del_mismo_expediente_declaran_la_misma_baja():
    # CLAUDE.md sección 17: propuesta y (aquí) contrato son el mismo hecho.
    baja_propuesta = extraer_baja_declarada(extraer_texto(fx.PROPUESTA_LC27_PRECIOS_UNITARIOS))
    baja_contrato = extraer_baja_declarada(extraer_texto(fx.CONTRATO_PRECIOS_UNITARIOS))
    assert baja_propuesta.baja == baja_contrato.baja


def test_anuncio_pcsp_no_declara_baja():
    # El Anuncio PCSP no trae la frase de baja; no debe inventarse un match.
    r = extraer_baja_declarada(extraer_texto(fx.ANUNCIO_PCSP_CON_MATRIZ))
    assert r is None


def test_elegir_baja_preferida_prioriza_resolucion_sobre_propuesta():
    de_propuesta = BajaDeclarada(Decimal("0.54"), 1, "frag", TipoDocumento.propuesta_lc27)
    de_resolucion = BajaDeclarada(Decimal("0.54"), 1, "frag", TipoDocumento.resolucion_adjudicacion)
    elegida = elegir_baja_preferida([de_propuesta, de_resolucion])
    assert elegida.tipo_documento == TipoDocumento.resolucion_adjudicacion


def test_elegir_baja_preferida_sin_candidatas():
    assert elegir_baja_preferida([]) is None
