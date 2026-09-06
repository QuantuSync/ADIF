from decimal import Decimal

from app.extraccion.baja import BajaDeclarada, elegir_baja_preferida, extraer_baja_declarada
from app.extraccion.texto import PaginaTexto, extraer_texto
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
    # CONTEXTO.md sección 17: propuesta y (aquí) contrato son el mismo hecho.
    baja_propuesta = extraer_baja_declarada(extraer_texto(fx.PROPUESTA_LC27_PRECIOS_UNITARIOS))
    baja_contrato = extraer_baja_declarada(extraer_texto(fx.CONTRATO_PRECIOS_UNITARIOS))
    assert baja_propuesta.baja == baja_contrato.baja


def test_baja_en_propuesta_dt_con_falso_positivo_de_pliego():
    # docs/analisis-corpus.md hallazgo 4: la baja ("con una baja del 20% a
    # todos los precios unitarios") la captura `_BAJA_RE` sin cambios, una
    # vez que el documento llega a `extraer_baja_declarada` en absoluto —
    # antes del arreglo de clasificación, ni siquiera llegaba a intentarlo.
    r = extraer_baja_declarada(
        extraer_texto(fx.PROPUESTA_DT_CON_FALSO_POSITIVO_PLIEGO), tipo_documento=TipoDocumento.propuesta_dt
    )
    assert r.baja == Decimal("0.2000")


def test_baja_en_propuesta_dt_sin_falso_positivo():
    r = extraer_baja_declarada(
        extraer_texto(fx.PROPUESTA_DT_SIN_FALSO_POSITIVO), tipo_documento=TipoDocumento.propuesta_dt
    )
    assert r.baja == Decimal("0.0013")


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


# Sesión de expedientes sin publicar (CONTEXTO.md sección 22): variantes de
# etiqueta de campo, no de frase en prosa — no vienen del corpus de PDFs de
# este proyecto, sino de otra fuente real. `_BAJA_RE` no las alcanza (no
# tienen "del" ni "precios unitarios"), así que solo las resuelve el patrón
# de respaldo `_BAJA_ETIQUETA_RE`. Fixture sintético (texto, no PDF): no hace
# falta un documento real para probar una expresión regular sobre texto ya
# extraído.
def test_baja_con_simbolo_de_porcentaje_pegado_a_la_etiqueta():
    r = extraer_baja_declarada([PaginaTexto(numero=1, texto="% de baja:    12,5")])
    assert r.baja == Decimal("0.1250")
    assert r.pagina == 1


def test_baja_variante_total_de_baja():
    r = extraer_baja_declarada([PaginaTexto(numero=1, texto="% total de baja: 6,02")])
    assert r.baja == Decimal("0.0602")


def test_baja_variante_baja_adjudicado():
    r = extraer_baja_declarada([PaginaTexto(numero=1, texto="% baja adjudicado: 20")])
    assert r.baja == Decimal("0.2000")


def test_baja_variante_baja_ofertada():
    r = extraer_baja_declarada([PaginaTexto(numero=1, texto="Baja ofertada: 12,50%")])
    assert r.baja == Decimal("0.1250")


def test_baja_variante_porcentaje_de_baja():
    r = extraer_baja_declarada([PaginaTexto(numero=1, texto="Porcentaje de baja: 3,00%")])
    assert r.baja == Decimal("0.0300")


def test_baja_etiqueta_no_confunde_baja_laboral_con_baja_de_expediente():
    # "de baja" sin el símbolo de porcentaje pegado a la etiqueta es
    # boilerplate laboral habitual en pliegos ("el trabajador que se
    # encuentre de baja médica..."), no la baja del expediente -- sin el "%"
    # como ancla, el patrón de respaldo no debe dispararse.
    r = extraer_baja_declarada(
        [PaginaTexto(numero=1, texto="El trabajador que se encuentre de baja médica percibirá el 100% de su salario.")]
    )
    assert r is None


# Sesión de identidad de lote (CONTEXTO.md sección 27), verificado contra
# 6.23/28510.0051_ADJUDICACION_1.pdf: "con un 25,31 % de baja a todos los
# precios unitarios" -- el número precede a "% de baja" en vez de seguirlo,
# la redacción exactamente opuesta a `_BAJA_RE`. Fixture sintético: el
# regex no necesita el PDF completo, `test_lotes.py` ya prueba el documento
# real.
def test_baja_invertida_numero_antes_de_baja():
    r = extraer_baja_declarada(
        [PaginaTexto(numero=1, texto="con un 25,31 % de baja a todos los precios unitarios")]
    )
    assert r.baja == Decimal("0.2531")


def test_baja_del_con_puntuacion_suelta():
    # 6.24/28510.0203_ADJUDICACION_1.pdf, LOTE 4: "con una baja del. 10,75%,
    # aplicable al conjunto de precios unitarios" -- un punto suelto entre
    # "del" y el número que `_BAJA_RE` no toleraba antes de esta sesión.
    r = extraer_baja_declarada(
        [PaginaTexto(numero=1, texto="con una baja del. 10,75%, aplicable al conjunto de precios unitarios")]
    )
    assert r.baja == Decimal("0.1075")


def test_baja_etiqueta_solo_se_intenta_si_baja_re_no_encuentra_nada():
    # Si ya hay una baja declarada en la forma estricta en cualquier página,
    # esa gana siempre -- el patrón de respaldo ni se llega a probar.
    paginas = [
        PaginaTexto(numero=1, texto="% de baja: 99,00"),
        PaginaTexto(numero=2, texto="con una baja del 54,00 % a precios unitarios licitados"),
    ]
    r = extraer_baja_declarada(paginas)
    assert r.baja == Decimal("0.5400")
    assert r.pagina == 2
