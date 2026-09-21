"""Sesión 2026-09-21 (tercera parte): la partición de una tabla aceptada por
los rótulos de lote de sus filas (bloque 2) y las líneas que faltan (bloque 3).
Cada recuperación solo se queda si con ella el lote cuadra con su presupuesto
publicado."""
from decimal import Decimal
from types import SimpleNamespace

from app.catalogo import _firma_material
from app.extraccion.filas_repetidas import (
    MOTIVO_FILA_REPETIDA_EN_EL_CUADRO,
    conservar_filas_repetidas_que_cierran_el_lote,
)
from app.extraccion.partida_alzada_del_lote import (
    MOTIVO_PARTIDA_ALZADA_RECUPERADA,
    descartar_recuperadas_que_no_cuadran,
    recuperar_partidas_alzadas_que_cierran_el_lote,
    suma_del_lote_como_el_catalogo,
)
from app.extraccion.tabla import (
    TablaExtraida,
    _cuadro_demostrado_por_aritmetica,
    _fila_con_el_codigo_en_la_cabecera,
    _partir_tabla_aceptada_por_rotulos,
)
from app.extraccion.texto import PaginaTexto


# --- Bloque 2: rótulos de lote dentro de una tabla ya aceptada ---


def _partir(filas, primera_de_datos):
    unica = TablaExtraida(cabecera=["h"], filas=filas[primera_de_datos:], pagina=25, bbox=(0, 0, 1, 1))
    return _partir_tabla_aceptada_por_rotulos(SimpleNamespace(bbox=(0, 0, 1, 1), rows=[]), filas, unica)


def test_una_tabla_con_el_rotulo_de_cada_lote_en_sus_filas_se_parte_sin_perder_ninguna():
    # `3.23/28510.0135` ANEJO p.25: los lotes 2 a 5 en la misma caja.
    filas = [
        ["", "", "", "", ""],
        ["LOTE 2 – FORMACIÓN - APORTE Y RECTIFICACIÓN", "", "", "", ""],
        ["P-6", "Inversor", "1.650,00 €", "1", "1.650,00 €"],
        ["P-7", "Grupo electrógeno", "3.872,00 €", "1", "3.872,00 €"],
        ["", "", "", "", ""],
        ["LOTE 3 – FORMACIÓN - AUXILIARES", "", "", "", ""],
        ["P-9", "Aspirador", "12.117,60 €", "3", "36.352,80 €"],
    ]
    partes = _partir(filas, 2)
    assert [(p.rotulo_de_lote.split()[1], [f[0] for f in p.filas if f[0]]) for p in partes] == [
        ("2", ["P-6", "P-7"]), ("3", ["P-9"]),
    ]
    assert all(p.titulo_propio == "" for p in partes)  # no activan la guarda de bloques recuperados


def test_el_rotulo_de_la_primera_fila_decide_el_lote_de_la_tabla():
    # `3.22/28510.0048` p.6: cada lote en su tabla, con su rótulo encima de la cabecera.
    filas = [
        ["LOTE 2 - Equipos para recepción de materiales", "", "", ""],
        ["Concepto", "Unidades", "Precio unitario (€)", "Importe (€)"],
        ["Regla de comprobación", "3", "10.400,00", "31.200,00"],
    ]
    partes = _partir(filas, 2)
    assert len(partes) == 1 and partes[0].rotulo_de_lote.startswith("LOTE 2")


def test_una_tabla_sin_rotulos_propios_no_se_toca():
    filas = [["Concepto", "Unidades"], ["Regla", "3"]]
    assert _partir(filas, 1) is None


# --- Bloque 3: la fila cuyo código quedó pegado a la cabecera ---

_LOTE_2_0141 = [
    ["CODIFICACIÓN DEL PRECIO P-1", "DESCRIPCIÓN", "UNIDADES", "CANTIDADES ESTIMADAS DE REFERENCIA",
     "PRECIO UNITARIO DE REFERENCIA", ""],
    ["", "", "", "", "", "TOTALES"],
    ["", "Balasto sobre camión en cantera", "t", "61.000", "10,8500 €", "661.850,00 €"],
    ["P-2", "T de balasto transportado", "t", "54.900", "12,6280 €", "693.277,20 €"],
]


def test_la_fila_cuyo_codigo_quedo_en_la_cabecera_se_recupera_con_ese_codigo():
    assert _fila_con_el_codigo_en_la_cabecera(_LOTE_2_0141, 3) == (2, 0, "P-1")


def test_sin_el_codigo_anterior_en_la_cabecera_no_se_recupera_nada():
    filas = [list(f) for f in _LOTE_2_0141]
    filas[0][0] = "CODIFICACIÓN DEL PRECIO P-7"
    assert _fila_con_el_codigo_en_la_cabecera(filas, 3) is None


# --- Bloque 3: la referencia sin ninguna secuencia de tres letras ---


def test_una_referencia_corta_que_cuadra_entra_marcada_como_recuperada():
    filas = [
        ["TIPO", "CANTIDAD", "PRECIO UD.", "PRECIO TOTAL"],
        ["SFT01-2388L-PH-6920", "20", "24,00 €", "480,00 €"],
        ["RC-12-WK-H1X", "100", "8,00 €", "800,00 €"],
        ["APKT-1604-PDSR-X-28", "80", "7,00 €", "560,00 €"],
    ]
    _inicio, datos, columna, recuperadas = _cuadro_demostrado_por_aritmetica(filas)
    assert [f[0] for f in datos] == ["SFT01-2388L-PH-6920", "RC-12-WK-H1X", "APKT-1604-PDSR-X-28"]
    assert recuperadas == ("RC-12-WK-H1X",) and columna.es_designacion is False


# --- Bloque 3: la partida alzada que la tabla no llega a leer ---


def _linea(lote, descripcion, cantidad, precio, pagina=4, **extra):
    return {"identificador_lote": lote, "descripcion": descripcion, "cantidad": cantidad,
            "precio_unitario": precio, "pagina": pagina, "orden_aparicion": 0, "matricula": None,
            "codigo_precio": None, "motivo_revision": None, **extra}


def test_la_partida_alzada_que_cierra_el_lote_se_lee_del_texto():
    # `6.20/28510.0094` lote 2: 81.012,74 € en la tabla + 8.987,26 € en lo alto de la p.5.
    lineas = [_linea("2", "Material del lote", Decimal("1"), Decimal("81012.74"))]
    paginas = [PaginaTexto(numero=5, texto="PARTIDA ALZADA A JUSTIFICAR PARA IMPREVISTOS\n8.987,26 €\nLa partida")]
    motivos = recuperar_partidas_alzadas_que_cierran_el_lote(
        lineas, paginas, {"2": Decimal("90000")}, 1, 1, {"2": None}
    )
    assert len(motivos) == 1
    nueva = lineas[-1]
    assert nueva["precio_unitario"] == Decimal("8987.26") and nueva["cantidad"] is None
    assert nueva["descripcion"] == "PARTIDA ALZADA A JUSTIFICAR PARA IMPREVISTOS"
    assert MOTIVO_PARTIDA_ALZADA_RECUPERADA in nueva["motivo_revision"]
    assert suma_del_lote_como_el_catalogo(lineas) == Decimal("90000")


def test_una_partida_alzada_que_no_cierra_el_lote_no_entra():
    lineas = [_linea("2", "Material del lote", Decimal("1"), Decimal("81012.74"))]
    paginas = [PaginaTexto(numero=5, texto="PARTIDA ALZADA A JUSTIFICAR PARA IMPREVISTOS 8.993,98 €")]
    assert recuperar_partidas_alzadas_que_cierran_el_lote(
        lineas, paginas, {"2": Decimal("90000")}, 1, 1, {"2": None}
    ) == []
    assert len(lineas) == 1


# --- La guarda: una línea recuperada solo entra si el lote cuadra ---


def test_la_recuperada_se_queda_si_el_lote_cuadra_y_sale_si_no():
    cuadra = [_linea("1", "A", Decimal("2"), Decimal("10")), _linea("1", "B", Decimal("1"), Decimal("5"),
                                                                    recuperada_que_falta=True)]
    quedan, _ = descartar_recuperadas_que_no_cuadran(cuadra, {"1": Decimal("25")})
    assert len(quedan) == 2 and all("recuperada_que_falta" not in l for l in quedan)
    no_cuadra = [_linea("1", "A", Decimal("2"), Decimal("10")), _linea("1", "B", Decimal("1"), Decimal("5"),
                                                                       recuperada_que_falta=True)]
    quedan, motivos = descartar_recuperadas_que_no_cuadran(no_cuadra, {"1": Decimal("26")})
    assert [l["descripcion"] for l in quedan] == ["A"] and motivos
    sin_presupuesto = [_linea("1", "B", Decimal("1"), Decimal("5"), recuperada_que_falta=True)]
    assert descartar_recuperadas_que_no_cuadran(sin_presupuesto, {})[0] == []


# --- Bloque 3: la fila que el propio cuadro repite ---


def test_la_fila_repetida_en_la_misma_tabla_se_conserva_si_con_ella_el_lote_cuadra():
    lineas = [
        _linea("1", "GUANTE JUBA", Decimal("100"), Decimal("1.50"), tabla_origen=(1, 1)),
        _linea("1", "GUANTE JUBA", Decimal("100"), Decimal("1.50"), tabla_origen=(1, 1)),
        _linea("1", "OTRA", Decimal("1"), Decimal("50"), tabla_origen=(1, 1)),
    ]
    motivos = conservar_filas_repetidas_que_cierran_el_lote(lineas, {"1": Decimal("350")})
    assert len(motivos) == 1
    assert _firma_material(lineas[0]) is not None
    assert MOTIVO_FILA_REPETIDA_EN_EL_CUADRO in lineas[1]["motivo_revision"]
    assert _firma_material(lineas[1]) is None  # ya no se funde con su gemela


def test_la_fila_repetida_no_se_conserva_si_el_lote_no_cuadra_con_ella():
    lineas = [
        _linea("1", "GUANTE JUBA", Decimal("100"), Decimal("1.50"), tabla_origen=(1, 1)),
        _linea("1", "GUANTE JUBA", Decimal("100"), Decimal("1.50"), tabla_origen=(1, 1)),
    ]
    assert conservar_filas_repetidas_que_cierran_el_lote(lineas, {"1": Decimal("150")}) == []
    assert conservar_filas_repetidas_que_cierran_el_lote(lineas, {"1": Decimal("999")}) == []
    assert all(l["motivo_revision"] is None for l in lineas)


def test_la_fila_con_codigo_de_sufijo_en_minuscula_antes_de_la_primera_se_recupera():
    # `6.24/28510.0185` p.22: "P-030b" (el anterior a "P-031") no cuenta como código de fila de datos.
    filas = [
        ["P-030b", "", "OPF-SW-185-4 SINUSOIDAL FILTER", "UN", "1", "", "530,00 €"],
        ["P-031", "", "RE-3009-2 Estabilizador", "UN", "1", "", "945,00 €"],
    ]
    assert _fila_con_el_codigo_en_la_cabecera(filas, 1) == (0, 0, "P-030b")


def test_un_decimal_con_punto_solo_se_lee_si_la_fila_cuadra():
    filas = [
        ["TIPO", "CANTIDAD", "PRECIO UD.", "PRECIO TOTAL"],
        ["SFT01-2388L-PH-6920", "20", "18", "360"],
        ["SFT01-2391-PH-6920", "140", "12.5", "1.750"],
        ["SFT01-2390-PH-6920", "1.350", "9", "12.150"],
        ["SFT01-2446-PH-6920", "60", "12.5", "751"],
    ]
    _inicio, datos, _columna, recuperadas = _cuadro_demostrado_por_aritmetica(filas)
    assert [f[2] for f in datos] == ["18", "12,5", "9"]
    assert recuperadas == ("SFT01-2391-PH-6920",)
