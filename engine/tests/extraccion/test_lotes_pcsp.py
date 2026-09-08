"""Tercera variante multi-lote (sesión de medición del alcance, 2026-09-08):
"Nº Lote: NNN" del Anuncio PCSP, con el desglose por lote dentro del mismo
documento -- ver docstring de `app.extraccion.lotes_pcsp` para el hallazgo
real completo. El fixture `ANUNCIO_PCSP_DOS_LOTES_SIN_DESGLOSE` es el PDF
real de `6.23/28510.0139`, dos lotes reales (La Gineta / Almussafes)."""
from decimal import Decimal

from app.extraccion.campos_pcsp import importe_como_decimal
from app.extraccion.invalidado import INVALIDADO
from app.extraccion.lotes_pcsp import (
    emparejar_ventana_por_nombre_proyecto,
    extraer_campos_pcsp_para_expediente,
    extraer_ventanas_multi_lote_pcsp,
)
from app.extraccion.texto import PaginaTexto, extraer_texto
from tests import fixtures as fx

_OBJETO_LOTE_1 = (
    "Suministro de balasto para las necesidades de obras y mantenimiento en la red ferroviaria de interés "
    "general (línea este). 2 lotes. Lote 1: Base de mantenimiento de La Gineta"
)
_OBJETO_LOTE_2 = (
    "Suministro de balasto para las necesidades de obras y mantenimiento en la red ferroviaria de interés "
    "general (línea este). 2 lotes. Lote 2: Base de mantenimiento de Almussafes"
)


def test_extrae_una_ventana_por_cada_nº_lote_del_documento_real():
    paginas = extraer_texto(fx.ANUNCIO_PCSP_DOS_LOTES_SIN_DESGLOSE)

    ventanas = extraer_ventanas_multi_lote_pcsp(paginas)

    assert {v.numero_lote for v in ventanas} == {"001", "002"}


def test_cada_ventana_trae_su_propio_importe_y_adjudicatario_no_el_del_otro_lote():
    # El hallazgo real: importe_licitacion=importe_adjudicacion dentro de
    # CADA lote (caso de precios unitarios, CONTEXTO.md sección 4), pero
    # los dos lotes tienen valores DISTINTOS entre sí -- si la extracción
    # mezclara los bloques, alguno de estos dos pares saldría igual al del
    # otro lote.
    paginas = extraer_texto(fx.ANUNCIO_PCSP_DOS_LOTES_SIN_DESGLOSE)
    ventanas = {v.numero_lote: v for v in extraer_ventanas_multi_lote_pcsp(paginas)}

    lote1, lote2 = ventanas["001"], ventanas["002"]
    assert importe_como_decimal(lote1.importe_licitacion) == Decimal("590256")
    assert importe_como_decimal(lote1.importe_adjudicacion) == Decimal("590256")
    assert lote1.adjudicatario.valor == "UTE SUMINISTRO LA GINETA"

    assert importe_como_decimal(lote2.importe_licitacion) == Decimal("1291698")
    assert importe_como_decimal(lote2.importe_adjudicacion) == Decimal("1291698")
    assert lote2.adjudicatario.valor == "PORFIDOS DEL MEDITERRANEO S A"


def test_objeto_de_cada_ventana_no_arrastra_la_descripcion_repetida():
    # `6.23/28510.0139` repite el objeto bajo la etiqueta "Descripción" y
    # añade "Valor estimado del contrato" antes de "Presupuesto base de
    # licitación" -- sin las tres etiquetas de corte, el objeto capturado se
    # comía ese bloque entero.
    paginas = extraer_texto(fx.ANUNCIO_PCSP_DOS_LOTES_SIN_DESGLOSE)
    ventanas = {v.numero_lote: v for v in extraer_ventanas_multi_lote_pcsp(paginas)}

    assert ventanas["001"].objeto == _OBJETO_LOTE_1
    assert "Descripción" not in ventanas["001"].objeto
    assert "Valor estimado" not in ventanas["001"].objeto


def test_un_solo_nlote_en_el_documento_no_activa_esta_via():
    pagina = PaginaTexto(numero=1, texto="Nº Lote: 001\nObjeto del Contrato: Un único lote.\nPresupuesto...")

    assert extraer_ventanas_multi_lote_pcsp([pagina]) == []


def test_documento_sin_ningun_nlote_no_activa_esta_via():
    pagina = PaginaTexto(numero=1, texto="Presupuesto base de licitación\nImporte (sin impuestos) 100.000 EUR")

    assert extraer_ventanas_multi_lote_pcsp([pagina]) == []


def test_emparejar_por_nombre_proyecto_exacto():
    paginas = extraer_texto(fx.ANUNCIO_PCSP_DOS_LOTES_SIN_DESGLOSE)
    ventanas = extraer_ventanas_multi_lote_pcsp(paginas)

    encontrada = emparejar_ventana_por_nombre_proyecto(ventanas, _OBJETO_LOTE_2)

    assert encontrada.numero_lote == "002"


def test_emparejar_por_nombre_proyecto_ignora_acentos_y_espacios():
    paginas = extraer_texto(fx.ANUNCIO_PCSP_DOS_LOTES_SIN_DESGLOSE)
    ventanas = extraer_ventanas_multi_lote_pcsp(paginas)

    sin_acentos_ni_espacios_limpios = "  suministro de balasto   para las necesidades de obras Y mantenimiento " \
        "en la red ferroviaria de interes  general (linea este). 2 lotes. lote 1: base de mantenimiento de la gineta  "

    encontrada = emparejar_ventana_por_nombre_proyecto(ventanas, sin_acentos_ni_espacios_limpios)

    assert encontrada.numero_lote == "001"


def test_emparejar_sin_nombre_proyecto_no_adivina():
    paginas = extraer_texto(fx.ANUNCIO_PCSP_DOS_LOTES_SIN_DESGLOSE)
    ventanas = extraer_ventanas_multi_lote_pcsp(paginas)

    assert emparejar_ventana_por_nombre_proyecto(ventanas, None) is None
    assert emparejar_ventana_por_nombre_proyecto(ventanas, "") is None
    assert emparejar_ventana_por_nombre_proyecto(ventanas, "un objeto que no coincide con ningún lote") is None


def test_extraer_campos_pcsp_para_expediente_usa_el_bloque_propio():
    paginas = extraer_texto(fx.ANUNCIO_PCSP_DOS_LOTES_SIN_DESGLOSE)

    campos, motivo = extraer_campos_pcsp_para_expediente(paginas, _OBJETO_LOTE_2)

    assert motivo is None
    assert importe_como_decimal(campos.importe_licitacion) == Decimal("1291698")
    assert importe_como_decimal(campos.importe_adjudicacion) == Decimal("1291698")
    assert campos.adjudicatario.valor == "PORFIDOS DEL MEDITERRANEO S A"
    # Campos del documento entero (no por lote): sin cambios respecto a la
    # extracción de siempre.
    assert campos.numero_expediente is not None


def test_extraer_campos_pcsp_para_expediente_sin_nombre_proyecto_no_usa_ningun_bloque():
    # `INVALIDADO` (app.extraccion.invalidado), no `None`: el documento SÍ
    # trae los tres campos, solo que no se puede atribuir con confianza --
    # a diferencia de "no encontrado", esto sí debe poder borrar un valor
    # guardado en una pasada anterior (ver docstring de `INVALIDADO`).
    paginas = extraer_texto(fx.ANUNCIO_PCSP_DOS_LOTES_SIN_DESGLOSE)

    campos, motivo = extraer_campos_pcsp_para_expediente(paginas, None)

    assert motivo is not None
    assert "Nº Lote: 001/002" in motivo
    assert campos.importe_licitacion is INVALIDADO
    assert campos.importe_adjudicacion is INVALIDADO
    assert campos.adjudicatario is INVALIDADO
    # También el objeto: un expediente recién descubierto, sin
    # nombre_proyecto propio todavía, no debe sembrarlo con el del primer
    # lote del documento -- envenenaría el propio ancla de emparejamiento.
    assert campos.objeto_contrato is INVALIDADO


def test_extraer_campos_pcsp_para_expediente_documento_de_un_solo_lote_no_cambia():
    # Camino de siempre para el 99% del corpus: un Anuncio PCSP sin "Nº
    # Lote: NNN" repetido sigue devolviendo exactamente lo que ya devolvía
    # `extraer_campos_anuncio_pcsp`, sin motivo de revisión.
    paginas = extraer_texto(fx.ANUNCIO_PCSP_CON_MATRIZ)

    campos, motivo = extraer_campos_pcsp_para_expediente(paginas, None)

    assert motivo is None
    assert importe_como_decimal(campos.importe_licitacion) == Decimal("145100")
