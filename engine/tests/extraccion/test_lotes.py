from decimal import Decimal

from app.extraccion.lotes import extraer_lotes_declarados
from app.extraccion.texto import extraer_texto
from tests import fixtures as fx


def _por_identificador(resultado):
    return {l.identificador: l for l in resultado.lotes}


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
