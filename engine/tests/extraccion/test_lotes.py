from decimal import Decimal

from app.extraccion.lotes import _importe_o_none, extraer_identidad_contrato, extraer_lotes_declarados
from app.extraccion.texto import PaginaTexto, extraer_texto
from tests import fixtures as fx

# Cabecera literal (pdfplumber) de la página 1 de los dos Contratos reales de
# tornillería -- sus recortes pesan 220-280 KB, ver tests/fixtures.
_CABECERA_CONTRATO_TORNILLERIA_LOTE1 = (
    "OBJETO DEL CONTRATO\n"
    "Contrato nº: 6.21/28510.0015\n"
    "SUMINISTRO DE TORNILLERÍA, MATERIAL AUXILIAR Y ANCLAJES DE SEGURIDAD (2 LOTES). EXPTE. Nº: 6.20/28510.0115\n"
    "LOTE 1: TORNILLERÍA Y MATERIAL AUXILIAR\n"
    "PRECIO DE ADJUDICACIÓN Y ANUALIDADES\n"
    "TOTAL 35.000,00 € 7.350,00 € 42.350,00 €\n"
    "La baja ofertada de 0,00% será aplicable al conjunto de precios unitarios de los artículos que componen "
    "el objeto del contrato.\n"
    "1. La solicitud de inicio del expediente 6.20/28510.0115, correspondiente a 2 lotes fue aprobada con un "
    "presupuesto de\nlicitación, de:\nBase Imponible 50.000,00 €\n"
    "Ascendiendo el importe de licitación del lote 1 a 35.000,00 € (IVA excluido)\n"
)
_CABECERA_CONTRATO_TORNILLERIA_LOTE2 = (
    "OBJETO DEL CONTRATO\n"
    "Contrato nº: 6.21/28510.0016\n"
    "SUMINISTRO DE TORNILLERÍA, MATERIAL AUXILIAR Y ANCLAJES DE SEGURIDAD (2 LOTES). EXPTE. Nº: 6.20/28510.0115\n"
    "LOTE 2 - ANCLAJES DE SEGURIDAD\n"
    "PRECIO DE ADJUDICACIÓN Y ANUALIDADES\n"
    "TOTAL 15.000,00 € 3.150,00 € 18.150,00 €\n"
    "La baja ofertada de 0,00% será aplicable al conjunto de precios unitarios de los artículos que componen "
    "el objeto del contrato.\n"
    # Errata real del propio Contrato del LOTE 2, en el cuerpo: no debe
    # confundir la identidad, que sale de la cabecera.
    "Ascendiendo el importe de licitación del lote 1 a 15.000,00 € (IVA excluido)\n"
)


def _por_identificador(resultado):
    return {l.identificador: l for l in resultado.lotes}


def test_importe_o_none_devuelve_none_en_vez_de_reventar():
    # Bloque 3, sesión 2026-09-10: mismo hallazgo que
    # `app.extraccion.campos_pcsp.importe_como_decimal` (expediente real
    # 6.20/28510.0062) -- un importe que el regex encontró pero
    # `parsear_numero_es` rechaza no debe propagar la excepción.
    assert _importe_o_none("1.10") is None
    assert _importe_o_none("7.915,61") == Decimal("7915.61")


def test_documento_sin_ninguna_mencion_de_lote_no_declara_nada():
    # CONTEXTO.md sección 19: el llamador cae al lote implícito único cuando
    # esto devuelve una lista vacía.
    resultado = extraer_lotes_declarados(extraer_texto(fx.PROPUESTA_LC27_PRECIOS_UNITARIOS))
    assert resultado.lotes == []
    assert resultado.lotes_totales_declarados is None


def test_resolucion_multi_lote_en_el_lote_n():
    # Redacción original, la única que reconocía el código anterior a esta
    # sesión ("En el LOTE N. ..."): sigue funcionando con el generalizador.
    resultado = extraer_lotes_declarados(extraer_texto(fx.RESOLUCION_MULTI_LOTE))
    lotes = _por_identificador(resultado)
    assert set(lotes) == {"1", "3"}
    assert lotes["1"].baja == Decimal("0.0713")
    assert lotes["1"].importe_adjudicacion == Decimal("593375.00")
    assert lotes["1"].importe_licitacion == Decimal("593375.00")
    assert lotes["1"].codigo_expediente_lote == "6.25/28510.0099"
    assert lotes["1"].adjudicatario is not None and "VILLACASTÍN" in lotes["1"].adjudicatario
    assert lotes["3"].codigo_expediente_lote == "6.25/28510.0101"
    assert resultado.lotes_totales_declarados == 6
    assert resultado.codigo_principal_declarado.valor == "6.25/28510.0027"


def test_propuesta_lc27_un_solo_lote_de_una_licitacion_de_dos():
    # 6.24/28510.0088 (CONTEXTO.md sección 26): el cuerpo nunca repite "LOTE
    # N", solo la cabecera la nombra una vez -- antes de esta sesión caía
    # al lote implícito único; ahora debe quedar etiquetado con el número
    # de lote real (1), no con el sentinela.
    resultado = extraer_lotes_declarados(extraer_texto(fx.PROPUESTA_LC27_UTE))
    lotes = _por_identificador(resultado)
    assert set(lotes) == {"1"}
    assert lotes["1"].baja == Decimal("0.0050")
    assert lotes["1"].importe_adjudicacion == Decimal("1000000.00")
    assert lotes["1"].codigo_expediente_lote == "6.24/28510.0113"
    assert resultado.lotes_totales_declarados == 2


def test_resolucion_un_solo_lote_de_una_licitacion_de_dos():
    # 6.24/28510.0124: mismo patrón que el anterior pero con la plantilla de
    # Resolución en vez de LC.27, y el único lote presente es el LOTE 2, no
    # el 1 -- no debe fabricarse ningún LOTE 1.
    resultado = extraer_lotes_declarados(extraer_texto(fx.RESOLUCION_ADJUDICACION))
    lotes = _por_identificador(resultado)
    assert set(lotes) == {"2"}
    assert lotes["2"].baja == Decimal("0.0450")
    assert lotes["2"].importe_adjudicacion == Decimal("800000.00")
    assert lotes["2"].codigo_expediente_lote == "6.24/28510.0179"
    assert lotes["2"].adjudicatario is not None and "CANTERAS DE CUARCITA" in lotes["2"].adjudicatario
    assert resultado.lotes_totales_declarados == 2


def test_propuesta_lc27_un_lote_de_cuatro():
    # 6.23/28510.0066: mismo patrón (un solo lote por documento) verificado
    # con una redacción de baja distinta ("baja económica del 3,00% a todos
    # a todos los precios unitarios licitados").
    resultado = extraer_lotes_declarados(extraer_texto(fx.PROPUESTA_LC27_UN_LOTE_DE_VARIOS))
    lotes = _por_identificador(resultado)
    assert set(lotes) == {"1"}
    assert lotes["1"].baja == Decimal("0.0300")
    assert lotes["1"].importe_adjudicacion == Decimal("960480.00")
    assert lotes["1"].codigo_expediente_lote == "6.23/28510.0073"
    assert resultado.lotes_totales_declarados == 4


def test_tres_lotes_con_bloque_partido_entre_paginas():
    # 6.24/28510.0117: los tres lotes traen su propio bloque de
    # adjudicación en el mismo documento, redacción "- LOTE N: <desc>.
    # EXPEDIENTE Nº X: <empresa>, con NIF: Y, con una baja económica del
    # Z%..." -- distinta de "En el LOTE N." de 6.25/28510.0027. El bloque
    # del LOTE 2 parte su importe (página 0) y su baja (página 1): sin
    # concatenar las páginas antes de ventanear, la baja de LOTE 2 se
    # perdería.
    resultado = extraer_lotes_declarados(extraer_texto(fx.PROPUESTA_LC27_TRES_LOTES_BAJA_ENTRE_PAGINAS))
    lotes = _por_identificador(resultado)
    assert set(lotes) == {"1", "2", "3"}
    assert lotes["1"].baja == Decimal("0.2499")
    assert lotes["1"].codigo_expediente_lote == "6.24/28510.0168"
    assert lotes["2"].baja == Decimal("0.2100")
    assert lotes["2"].importe_adjudicacion == Decimal("1250000.00")
    assert lotes["2"].codigo_expediente_lote == "6.24/28510.0169"
    assert lotes["3"].baja == Decimal("0.4550")
    assert lotes["3"].codigo_expediente_lote == "6.24/28510.0170"
    assert resultado.lotes_totales_declarados == 3


def test_numeracion_de_lotes_con_hueco_no_se_rellena():
    # 6.25/28510.0028 (encargo explícito del cliente, sesión de identidad de
    # lote): licitación de "7 LOTES" cuyo LOTE 5 no aparece en ningún sitio
    # del documento -- desierto o anulado, sin verificar cuál. El hueco
    # nunca se rellena con un lote inventado.
    resultado = extraer_lotes_declarados(extraer_texto(fx.RESOLUCION_LOTES_CON_HUECO))
    lotes = _por_identificador(resultado)
    assert set(lotes) == {"1", "2", "3", "4", "6", "7"}
    assert "5" not in lotes
    assert lotes["1"].baja == Decimal("0.0602")
    assert lotes["6"].baja == Decimal("0.0000")
    assert resultado.lotes_totales_declarados == 7


# --- Sesión 2026-09-14 (continuación): identidad de lote en expedientes hermanos


def test_referencia_cruzada_a_otro_lote_no_se_lleva_el_codigo_del_lote():
    # 6.22/28510.0033: "LOTE 2: SUR Y, EN CASO DE URGENCIA QUE NO PUEDA SER
    # TENDIDA POR EL ADJUDICATARIO DEL LOTE1, NORTE | EXPEDIENTE Nº
    # 6.22/28510.0058". Antes, "LOTE1" abría su propia ventana y se quedaba
    # el código de LOTE 2 -- el catálogo tenía LOTE 1 ligado a 0058 y LOTE 2
    # a 0057, al revés que los dos Contratos.
    lotes = _por_identificador(extraer_lotes_declarados(extraer_texto(fx.RESOLUCION_REFERENCIA_CRUZADA_0058)))
    assert lotes["2"].codigo_expediente_lote == "6.22/28510.0058"
    assert lotes["1"].codigo_expediente_lote == "6.22/28510.0057"


def test_referencia_cruzada_nombra_el_lote_sin_datos():
    # 6.22/28510.0122: la Propuesta del LOTE 2 solo nombra el LOTE 1 dentro
    # de la referencia cruzada. El lote existe (queda nombrado), pero sin
    # ningún dato de la ventana del LOTE 2 -- antes se quedaba su código
    # (0156) y su baja (24,99 %).
    lotes = _por_identificador(extraer_lotes_declarados(extraer_texto(fx.PROPUESTA_REFERENCIA_CRUZADA_0156)))
    assert set(lotes) == {"1", "2"}
    assert lotes["2"].codigo_expediente_lote == "6.22/28510.0156"
    assert lotes["2"].baja == Decimal("0.2499")
    assert lotes["1"].codigo_expediente_lote is None
    assert lotes["1"].baja is None
    assert lotes["1"].importe_adjudicacion is None


def test_identidad_de_contrato_real():
    # "Contrato nº: X" + el "LOTE N" que le sigue en la cabecera, y la baja
    # que declara el propio Contrato.
    lote1 = extraer_identidad_contrato(extraer_texto(fx.CONTRATO_LOTE1_0057))
    assert (lote1.identificador, lote1.codigo_expediente_lote, lote1.baja) == (
        "1", "6.22/28510.0057", Decimal("0.1050"),
    )
    lote2 = extraer_identidad_contrato(extraer_texto(fx.CONTRATO_LOTE2_0058))
    assert (lote2.identificador, lote2.codigo_expediente_lote, lote2.baja) == (
        "2", "6.22/28510.0058", Decimal("0.0050"),
    )


def test_identidad_de_contrato_tornilleria_baja_ofertada_de():
    # "La baja ofertada de 0,00%" (sin "del"): ningún patrón de baja la
    # reconocía. La errata del cuerpo del Contrato del LOTE 2 ("del lote 1")
    # no cuenta: la identidad sale de la cabecera.
    lote1 = extraer_identidad_contrato([PaginaTexto(numero=1, texto=_CABECERA_CONTRATO_TORNILLERIA_LOTE1)])
    assert (lote1.identificador, lote1.codigo_expediente_lote, lote1.baja) == (
        "1", "6.21/28510.0015", Decimal("0.0000"),
    )
    lote2 = extraer_identidad_contrato([PaginaTexto(numero=1, texto=_CABECERA_CONTRATO_TORNILLERIA_LOTE2)])
    assert (lote2.identificador, lote2.codigo_expediente_lote) == ("2", "6.21/28510.0016")


def test_identidad_de_contrato_trae_el_importe_de_su_lote():
    # Sesión 2026-09-15: "Ascendiendo el importe de licitación del lote 2 a
    # 2.400.000,00 € (IVA excluido)" y "CUARTO. El importe del contrato es de:
    # - Base imponible ... 2.400.000,00 €", en la p.2.
    lote2 = extraer_identidad_contrato(extraer_texto(fx.CONTRATO_LOTE2_0058_CON_IMPORTE))
    assert lote2.importe_licitacion.valor == "2.400.000,00"
    assert lote2.importe_adjudicacion.valor == "2.400.000,00"
    assert lote2.importe_adjudicacion.pagina == 2
    assert "Base imponible" in lote2.importe_adjudicacion.fragmento


def test_importe_de_licitacion_de_otro_numero_de_lote_no_se_toma():
    # El Contrato del LOTE 2 de `6.21/28510.0016` dice "del lote 1" en sus
    # antecedentes (errata): no es el importe de licitación de su lote por
    # lo que dice el texto, así que no se usa.
    texto = _CABECERA_CONTRATO_TORNILLERIA_LOTE2 + (
        "\nAscendiendo el importe de licitación del lote 1 a 15.000,00 € (IVA excluido) y un valor estimado de "
        "15.000,00 €.\n"
    )
    lote2 = extraer_identidad_contrato([PaginaTexto(numero=1, texto=texto)])
    assert lote2.importe_licitacion is None


def test_documento_sin_contrato_no_declara_identidad():
    assert extraer_identidad_contrato(extraer_texto(fx.PROPUESTA_LC27_UTE)) is None


def test_errata_de_numero_de_lote_se_corrige_con_el_contrato():
    # Resolución del LOTE 2 de tornillería: "LOTE 1: ANCLAJES DE SEGURIDAD.
    # EXPEDIENTE Nº: 6.21/28510.0016" en el RESUELVE. Sin los Contratos, la
    # ventana se atribuye al número que dice el documento (errata incluida).
    paginas = extraer_texto(fx.RESOLUCION_LOTE2_ERRATA_LOTE1_0016)
    sin_contratos = _por_identificador(extraer_lotes_declarados(paginas))
    assert sin_contratos["1"].codigo_expediente_lote == "6.21/28510.0016"
    assert sin_contratos["1"].importe_adjudicacion == Decimal("15000.00")

    # Con ellos (0015 es el LOTE 1, 0016 el LOTE 2), el bloque va a su lote
    # de verdad y el LOTE 1 queda nombrado, sin datos, para que lo complete
    # su propio Contrato.
    con_contratos = _por_identificador(extraer_lotes_declarados(
        paginas, {"6.21/28510.0015": "1", "6.21/28510.0016": "2"},
    ))
    assert set(con_contratos) == {"1", "2"}
    assert con_contratos["2"].codigo_expediente_lote == "6.21/28510.0016"
    assert con_contratos["2"].importe_adjudicacion == Decimal("15000.00")
    assert con_contratos["2"].baja == Decimal("0.0000")
    assert con_contratos["1"].codigo_expediente_lote is None
    assert con_contratos["1"].importe_adjudicacion is None
    assert con_contratos["1"].baja is None
