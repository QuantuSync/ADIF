"""Bloque 1, sesión 2026-09-19 (sexta parte): las decisiones que el cliente
dejó cerradas sobre los residuales de la quinta parte.

1. `3.18/28510.0082` — el IMPORTE que no es precio unitario.
2. `6.17/28510.0116` — las matrículas con letra final.
4. La fila `12.01` de `3.16/28510.0044` y la cuarta fila del lote 1 de
   `3.21/28510.0096`.
5. Los tres cuadros cuya única columna de texto es la referencia de la
   herramienta.

(La 3 —la numeración de lotes desplazada de `3.22/28510.0009` y
`3.21/28510.0096`— no toca código por decisión del cliente: va al documento de
preguntas, `docs/preguntas-pendientes-cliente.md`.)
"""
from decimal import Decimal

from app.catalogo import (
    CAMPO_IMPORTE,
    MARCA_PRECIO_DESDE_IMPORTE,
    MOTIVO_IMPORTE_SIN_PRECIO_NI_CONFIRMACION,
    MOTIVO_PRECIO_DESDE_IMPORTE,
    construir_linea_catalogo,
    corregir_precio_con_importe_del_documento,
    resolver_cuadros_sin_precio_propio,
)
from app.exportacion import _sale_en_materiales
from app.extraccion.invalidado import INVALIDADO
from app.extraccion.mapeo_cabecera import (
    corregir_columna_importe_tomada_por_precio,
    liberar_unidad_que_son_solo_cifras,
)
from app.extraccion.referencia_como_descripcion import (
    MARCA_FRAGMENTO,
    MOTIVO_DESCRIPCION_DESDE_REFERENCIA,
    marcar_descripcion_desde_referencia,
)
from app.extraccion.tabla import _cuadro_demostrado_por_aritmetica, _fila_cuadra_desplazada

# --------------------------------------------------------------------------
# Decisión 1 — el IMPORTE que no es precio unitario (`3.18/28510.0082`)
# --------------------------------------------------------------------------

# Cabecera real de `3.18/28510.0082_ANEJO_1.pdf` p.238 (12 columnas, con sus
# fantasmas). La p.7 repite el mismo cuadro con "IMPORTE **".
_CABECERA_0082 = [None, "MATRICULA", None, None, "DESIGNACIÓN", None, None, "U", None, None, "IMPORTE", None]
_MAPEO_0082 = {
    "codigo_precio": None,
    "matricula": 1,
    "descripcion": 4,
    "unidad_medida": 7,
    "cantidad": 6,
    "precio_unitario": 10,
}
# Las ocho filas reales, tal y como las devuelve pdfplumber: las seis con
# matrícula van un sitio a la izquierda de lo que etiqueta la cabecera; las dos
# últimas tienen la descripción una a la izquierda y la cantidad en su sitio.
_FILAS_0082 = [
    ["650000030", None, None, "", "Aire Acondicionado 1x1.", "", "16", None, None, "49.604,00€", None, None],
    ["650000031", None, None, "", "Aire Acondicionado 1x1.", "", "11", None, None, "36.770,25€", None, None],
    ["650000032", None, None, "", "Aire Acondicionado 1x1.", "", "15", None, None, "57.472,50€", None, None],
    ["650000033", None, None, "", "Aire Acondicionado 1x1.", "", "7", None, None, "29.900,50€", None, None],
    ["650000034", None, None, "", "Aire Acondicionado 1x1.", "", "15", None, None, "93.153,75€", None, None],
    ["650000035", None, None, "", "Aire Acondicionado 1x1.", "", "11", None, None, "84.262,75€", None, None],
    ["", "", "", "Instalación y puesta en marcha", None, None, "", "75", "", "", "27.918,75€", ""],
    ["", "", "", "Materiales necesarios para la instalación", None, None, "", "1", "", "", "16.732,50€", ""],
]
# El presupuesto de licitación publicado del lote 1 de ese expediente.
_PRESUPUESTO_0082 = Decimal("395815.00")


def test_la_columna_llamada_importe_deja_de_ser_el_precio_unitario():
    mapeo, corregido = corregir_columna_importe_tomada_por_precio(_CABECERA_0082, dict(_MAPEO_0082))
    assert corregido is True
    assert mapeo["precio_unitario"] is None
    assert mapeo[CAMPO_IMPORTE] == 10


def test_la_llamada_a_nota_al_pie_de_la_cabecera_no_cambia_el_nombre():
    """La p.7 del mismo anejo imprime "IMPORTE **": el asterisco es la llamada
    a una nota al pie, no parte del nombre de la columna."""
    cabecera = list(_CABECERA_0082)
    cabecera[10] = "IMPORTE **"
    _mapeo, corregido = corregir_columna_importe_tomada_por_precio(cabecera, dict(_MAPEO_0082))
    assert corregido is True


def test_una_columna_de_precio_de_verdad_no_se_toca():
    """El vocabulario es cerrado y exacto: "IMPORTE UNITARIO" sí es un precio,
    y una columna "PRECIO" no se mueve de sitio."""
    for nombre in ("IMPORTE UNITARIO", "PRECIO UNITARIO", "P. Ejecución Material"):
        cabecera = list(_CABECERA_0082)
        cabecera[10] = nombre
        _mapeo, corregido = corregir_columna_importe_tomada_por_precio(cabecera, dict(_MAPEO_0082))
        assert corregido is False, nombre


def test_no_se_toca_nada_si_la_tabla_ya_tiene_su_columna_de_importes():
    """Un cuadro con precio Y importe es el caso de siempre (bloque 2 de la
    sesión 2026-09-19): ahí el precio impreso sí es un precio."""
    mapeo = {**_MAPEO_0082, CAMPO_IMPORTE: 11}
    _resultado, corregido = corregir_columna_importe_tomada_por_precio(_CABECERA_0082, mapeo)
    assert corregido is False


def test_la_columna_de_unidades_que_son_solo_cifras_se_libera():
    mapeo = liberar_unidad_que_son_solo_cifras(dict(_MAPEO_0082), _FILAS_0082)
    assert mapeo["unidad_medida"] is None
    # `cantidad` ya tenía columna: esta solo se libera, para que la
    # recuperación de columna fantasma pueda leerla.
    assert mapeo["cantidad"] == 6


def test_sin_columna_de_cantidad_la_de_unidades_pasa_a_serlo():
    """La copia de la p.7 resolvió su cabecera con `cantidad` sin columna."""
    mapeo = liberar_unidad_que_son_solo_cifras({**_MAPEO_0082, "cantidad": None}, _FILAS_0082)
    assert mapeo["unidad_medida"] is None
    assert mapeo["cantidad"] == 7


def test_una_columna_de_unidades_de_verdad_no_se_libera():
    filas = [["", "650000030", None, None, "Aire", None, None, "ud", None, None, "49.604,00€", None]]
    mapeo = liberar_unidad_que_son_solo_cifras(dict(_MAPEO_0082), filas)
    assert mapeo["unidad_medida"] == 7


def _lineas_0082(mapeo, tabla_origen=(1, 1)):
    lineas = []
    for orden, fila in enumerate(_FILAS_0082):
        linea = construir_linea_catalogo(fila, mapeo, 238, 1, 1, None, orden)
        assert linea is not None, fila
        from app.catalogo import _importe_de_fila

        linea["importe_documento"] = _importe_de_fila(fila, mapeo)
        linea["identificador_lote"] = "1"
        linea["tabla_origen"] = tabla_origen
        linea["precio_solo_en_la_columna_de_importe"] = True
        lineas.append(linea)
    return lineas


def _mapeo_0082_corregido():
    mapeo, _ = corregir_columna_importe_tomada_por_precio(_CABECERA_0082, dict(_MAPEO_0082))
    return liberar_unidad_que_son_solo_cifras(mapeo, _FILAS_0082)


def test_0082_las_ocho_filas_entran_con_su_precio_porque_el_lote_suma_su_presupuesto():
    """La regla completa, de punta a punta: sin precio unitario en el cuadro,
    el precio es `importe / cantidad` y la prueba es que la suma del cuadro dé
    exactamente el presupuesto de licitación publicado del lote.
    395.815,00 € al céntimo."""
    mapeo = _mapeo_0082_corregido()
    lineas = _lineas_0082(mapeo)
    assert [l["cantidad"] for l in lineas] == [
        Decimal(n) for n in (16, 11, 15, 7, 15, 11, 75, 1)
    ]
    corregidas = resolver_cuadros_sin_precio_propio(lineas, {"1": [_PRESUPUESTO_0082]})
    assert corregidas == 8
    assert [l["precio_unitario"] for l in lineas] == [
        Decimal(p) for p in ("3100.25", "3342.75", "3831.50", "4271.50", "6210.25", "7660.25", "372.25", "16732.50")
    ]
    assert sum(l["cantidad"] * l["precio_unitario"] for l in lineas) == _PRESUPUESTO_0082
    assert all(l["precio_corregido_desde_importe"] is True for l in lineas)
    assert all(MOTIVO_PRECIO_DESDE_IMPORTE in l["motivo_revision"] for l in lineas)
    assert all(l["fragmento"].startswith(MARCA_PRECIO_DESDE_IMPORTE) for l in lineas)


def test_el_mismo_cuadro_impreso_dos_veces_no_descuadra_la_suma():
    """La comprobación es por cuadro, no por lote entero: el anejo de
    `3.18/28510.0082` imprime el mismo cuadro en la p.7 y en la p.238. Sumar
    las dos copias daría 791.630,00 € y tiraría un cuadro que cuadra."""
    mapeo = _mapeo_0082_corregido()
    lineas = _lineas_0082(mapeo, tabla_origen=(1, 1)) + _lineas_0082(mapeo, tabla_origen=(1, 2))
    corregidas = resolver_cuadros_sin_precio_propio(lineas, {"1": [_PRESUPUESTO_0082]})
    assert corregidas == 16
    assert all(l["precio_unitario"] is not INVALIDADO for l in lineas)


def test_si_el_lote_no_confirma_la_division_las_filas_se_quedan_fuera():
    """Lo que pidió el cliente con todas las letras: "si no se confirma, esas
    filas se quedan fuera con su motivo"."""
    mapeo = _mapeo_0082_corregido()
    lineas = _lineas_0082(mapeo)
    corregidas = resolver_cuadros_sin_precio_propio(lineas, {"1": [Decimal("400000.00")]})
    assert corregidas == 0
    assert all(l["precio_unitario"] is INVALIDADO for l in lineas)
    assert all(MOTIVO_IMPORTE_SIN_PRECIO_NI_CONFIRMACION in l["motivo_revision"] for l in lineas)
    # Y ese motivo es de exclusión del entregable, no un aviso más.
    assert _sale_en_materiales(lineas[0]["motivo_revision"], True, False) is False


def test_sin_ningun_total_publicado_del_lote_tampoco_entran():
    mapeo = _mapeo_0082_corregido()
    lineas = _lineas_0082(mapeo)
    corregidas = resolver_cuadros_sin_precio_propio(lineas, {})
    assert corregidas == 0
    assert all(l["precio_unitario"] is INVALIDADO for l in lineas)


def test_una_fila_sin_cantidad_tira_la_demostracion_del_cuadro_entero():
    """Todo o nada: sin la cantidad de una fila, la suma ya no es la del
    cuadro y no hay nada que comparar contra el presupuesto."""
    mapeo = _mapeo_0082_corregido()
    lineas = _lineas_0082(mapeo)
    lineas[0]["cantidad"] = None
    corregidas = resolver_cuadros_sin_precio_propio(lineas, {"1": [_PRESUPUESTO_0082]})
    assert corregidas == 0
    assert all(l["precio_unitario"] is INVALIDADO for l in lineas)


# --------------------------------------------------------------------------
# Decisión 2 — las matrículas con letra final (`6.17/28510.0116`)
# --------------------------------------------------------------------------

_MAPEO_SIMPLE = {
    "codigo_precio": None,
    "matricula": 0,
    "descripcion": 1,
    "unidad_medida": None,
    "cantidad": 2,
    "precio_unitario": 3,
}


def _linea_con_matricula(matricula, descripcion="CELDA DE LÍNEA, corte y aislamiento íntegro en SF6"):
    return construir_linea_catalogo(
        [matricula, descripcion, "1", "5.400,00 €"], _MAPEO_SIMPLE, 9, 1, 1, None, 0
    )


def test_la_matricula_con_letra_final_se_descarta_y_su_literal_va_a_la_descripcion():
    linea = _linea_con_matricula("69520000N")
    assert linea["matricula"] is None
    assert "valor de matrícula no reconocible, descartado: '69520000N'" in linea["motivo_revision"]
    assert linea["descripcion"].endswith("[matrícula impresa en el documento, no válida: 69520000N]")
    # El precio de la línea no se toca: es el que imprime el documento.
    assert linea["precio_unitario"] == Decimal("5400.00")


def test_la_matricula_antigua_de_ocho_cifras_con_letra_tambien():
    linea = _linea_con_matricula("64551025O")
    assert linea["matricula"] is None
    assert linea["descripcion"].endswith("[matrícula impresa en el documento, no válida: 64551025O]")


def test_un_literal_sin_forma_de_matricula_no_ensucia_la_descripcion():
    """Solo la forma exacta (8 o 9 cifras y una sola letra). Un valor de otra
    columna leído por error en la celda de matrícula es ruido, y el motivo de
    revisión ya lo recoge."""
    for ruido in ("18.309", "ET03.364.203.4", "NODISPONE", "66ireV"):
        linea = _linea_con_matricula(ruido)
        assert linea is not None, ruido
        assert "[matrícula impresa" not in (linea["descripcion"] or ""), ruido


def test_la_matricula_valida_sigue_entrando_intacta():
    linea = _linea_con_matricula("650000030")
    assert linea["matricula"] == "650000030"
    assert "[matrícula impresa" not in linea["descripcion"]


# --------------------------------------------------------------------------
# Decisión 4 — la cuarta fila del lote 1 de `3.21/28510.0096`
# --------------------------------------------------------------------------

# La tabla real de `3.21/28510.0096_ANEJO_1.pdf` p.6 (14 columnas).
_FILAS_0096 = [
    [None, "LOTE 1. REPUESTOS PARA REPARACIÓN DE REGLAS DE MEDIDA DE ANCHO DE VÍA Y PERALTE",
     None, None, None, None, None, None, None, None, None, None, None, ""],
    ["Concepto", None, "TIPOLOGÍA", None, None, "Unidades", None, None, "Precio unitario (€)",
     None, None, "TOTAL", None, None],
    ["PCB tarjeta electrónica para regla de ancho de vía (ancho 1668 mm)", None, "Ancho 1668",
     None, None, "25", None, None, "460,00", None, None, "11.500,00", None, None],
    ["PCB tarjeta electrónica para regla de ancho de vía (ancho 1000 mm)", None, "Ancho 1000",
     None, None, "10", None, None, "460,00", None, None, "4.600,00", None, None],
    ["PCB tarjeta electrónica para regla de ancho de vía (ancho 1435 mm)", None, "Ancho 1435",
     None, None, "10", None, None, "460,00", None, None, "4.600,00", None, None],
    # La cuarta fila: sus tres celdas numéricas van una columna a la derecha.
    ["Potenciómetro rotatorio, componente 20299800", None, "", "", "", "", "10", "", "",
     "150,00", "", "", "1.500,00", ""],
]


def test_la_cuarta_fila_desplazada_entra_porque_su_aritmetica_cuadra():
    demostrado = _cuadro_demostrado_por_aritmetica(_FILAS_0096)
    assert demostrado is not None
    _inicio, datos, _columna = demostrado
    assert len(datos) == 4
    assert datos[3][0].startswith("Potenciómetro rotatorio")
    # Con ella, el cuadro suma el presupuesto publicado del lote 1:
    # 11.500 + 4.600 + 4.600 + 1.500 = 22.200,00 €.


def test_el_desplazamiento_tiene_que_ser_el_mismo_para_las_tres_celdas():
    """Nunca se recompone una fila celda a celda: o las tres van un sitio a la
    derecha, o no hay desplazamiento que demostrar."""
    tripleta = (5, 8, 11)
    a_medias = ["x", None, "", "", "", "", "10", "", "150,00", "", "", "", "1.500,00", ""]
    assert _fila_cuadra_desplazada(a_medias, tripleta) is False


def test_una_fila_desplazada_cuya_cuenta_no_cuadra_no_entra():
    tripleta = (5, 8, 11)
    no_cuadra = ["x", None, "", "", "", "", "10", "", "", "150,00", "", "", "1.499,00", ""]
    assert _fila_cuadra_desplazada(no_cuadra, tripleta) is False


def test_una_fila_con_sus_celdas_en_su_sitio_no_se_lee_desplazada():
    tripleta = (5, 8, 11)
    en_su_sitio = ["x", None, "", "", "", "10", "", "", "150,00", "", "", "1.500,00", "", ""]
    assert _fila_cuadra_desplazada(en_su_sitio, tripleta) is False


# --------------------------------------------------------------------------
# Decisión 5 — la referencia de la herramienta como Descripción del material
# --------------------------------------------------------------------------

# El cuadro real de `2.23/28510.0098_ANEJO_1.pdf` p.4 y p.9.
_FILAS_0098 = [
    ["TIPO", "CANTIDAD", "PRECIO UD.", "PRECIO TOTAL"],
    ["SFT01-2388L-PH-6920", "20", "24,00 €", "480,00 €"],
    ["SFT01-2389-PH-6920", "130", "18,00 €", "2.340,00 €"],
    ["SFT01-2390-PH-6920", "1.400", "8,00 €", "11.200,00 €"],
    ["WCMX-04 02 08-R53", "30", "12,00 €", "360,00 €"],
    ["Total", None, None, "35.760,00 €"],
]


def test_el_cuadro_de_referencias_entra_y_senala_su_columna_de_texto():
    demostrado = _cuadro_demostrado_por_aritmetica(_FILAS_0098)
    assert demostrado is not None
    inicio, datos, columna = demostrado
    assert inicio == 1
    assert len(datos) == 4
    assert columna.indice == 0 and columna.es_designacion is False


def test_un_cuadro_con_designacion_de_verdad_no_se_marca_como_referencia():
    filas = [
        ["Concepto", "Unidades", "Precio", "Importe"],
        ["Armario ETSI 2200*600*300 mm para alojamiento de equipo SDH", "20", "24,00 €", "480,00 €"],
        ["Instalación y puesta a punto de equipo SDH", "130", "18,00 €", "2.340,00 €"],
    ]
    demostrado = _cuadro_demostrado_por_aritmetica(filas)
    assert demostrado is not None
    _inicio, _datos, columna = demostrado
    assert columna.es_designacion is True


def test_la_linea_con_la_referencia_por_descripcion_queda_marcada():
    linea = {"descripcion": "SFT01-2388L-PH-6920", "motivo_revision": None, "fragmento": "SFT01-2388L-PH-6920 | 20"}
    marcar_descripcion_desde_referencia(linea)
    assert linea["descripcion_desde_referencia"] is True
    assert MOTIVO_DESCRIPCION_DESDE_REFERENCIA in linea["motivo_revision"]
    assert linea["fragmento"].startswith(MARCA_FRAGMENTO)
    # Idempotente: una segunda pasada no duplica ni el motivo ni la marca.
    motivo, fragmento = linea["motivo_revision"], linea["fragmento"]
    marcar_descripcion_desde_referencia(linea)
    assert (linea["motivo_revision"], linea["fragmento"]) == (motivo, fragmento)


def test_la_marca_no_saca_la_linea_del_entregable():
    """A diferencia de la decisión 1, esto no es un hueco: el documento no
    publica otra descripción, así que la línea sale, marcada."""
    linea = {"descripcion": "SFT01-2388L-PH-6920", "motivo_revision": None, "fragmento": "x"}
    marcar_descripcion_desde_referencia(linea)
    assert _sale_en_materiales(linea["motivo_revision"], True, False) is True
