"""Bloque 1, sesión 2026-09-19 (tercera parte) -- las cantidades que faltan.

`completar_cantidad_por_contenido`: una tabla sin cabecera propia cuyo mapeo
no reclama ninguna columna de cantidad, en un documento que SÍ la declara en
otra de sus tablas. Casos reales medidos: `6.20/28510.0042`/`0046`/`0047`
(doc `ANEJO_abd69efbdd39b552`, cabecera en la p.3, 60 páginas de continuación
sin ella) y `6.22/28510.0125`/`0126` (doc `ANEJO_57694f5d5dacb236`, cabecera
en la p.15). Los contraejemplos son igual de importantes: `6.21/28510.0108`-
`0111`, cuyo anejo de criterios nunca declara cantidad y trae dos columnas de
enteros que no lo son (el radio de la tipología y el peso en toneladas).
"""
from app.extraccion.mapeo_cabecera import completar_cantidad_por_contenido

# Mapeo real medido en el documento del trío: el modelo, con la cabecera
# vacía de una página de continuación, no reclama columna de cantidad.
MAPEO_SIN_CANTIDAD = {
    "codigo_precio": None,
    "matricula": 0,
    "descripcion": 1,
    "unidad_medida": None,
    "cantidad": None,
    "precio_unitario": 4,
}

# Filas reales de `6.20/28510.0042` p.18 y p.23 (la columna de cantidad es la
# última y solo la rellenan unos pocos renglones).
FILAS_TRIO = [
    ["610840006", "COJINETE DE 50", "213-5", "03.300.103.3", "200,54 €", "", "", "2"],
    ["617540130", "ARANDELA MUELLE", "", "DIN 127-B", "0,18 €", "", "", ""],
    ["611450126", "CZI-AG-B1/C-54", "P16.2149.00", "03.361.140.1", "8.041,04 €", "", "", "3"],
]


def test_completa_la_cantidad_cuando_el_documento_la_declara():
    mapeo = completar_cantidad_por_contenido(MAPEO_SIN_CANTIDAD, FILAS_TRIO, True)
    assert mapeo["cantidad"] == 7
    # Ningún otro campo se mueve.
    assert {c: i for c, i in mapeo.items() if c != "cantidad"} == {
        c: i for c, i in MAPEO_SIN_CANTIDAD.items() if c != "cantidad"
    }


def test_no_completa_nada_si_el_documento_nunca_declara_cantidad():
    """La certeza la da el documento, no el contenido de la columna: sin una
    cabecera propia que declare cantidad en alguna de sus tablas, no se
    adivina. Es lo que protege al anejo de criterios de `6.21/28510.0108`."""
    assert completar_cantidad_por_contenido(MAPEO_SIN_CANTIDAD, FILAS_TRIO, False) is MAPEO_SIN_CANTIDAD


def test_no_toca_un_mapeo_que_ya_tiene_columna_de_cantidad():
    mapeo = {**MAPEO_SIN_CANTIDAD, "cantidad": 6}
    assert completar_cantidad_por_contenido(mapeo, FILAS_TRIO, True) is mapeo


def test_no_reclama_una_columna_que_ya_es_de_otro_campo():
    """La columna 4 es el precio: aunque sus valores fueran enteros pequeños,
    nunca se le quita a `precio_unitario`."""
    filas = [["610840006", "COJINETE", "", "", "2", "", "", ""]]
    mapeo = completar_cantidad_por_contenido(MAPEO_SIN_CANTIDAD, filas, True)
    assert mapeo["cantidad"] is None


def test_dos_columnas_candidatas_no_se_adivinan():
    filas = [
        ["610840006", "COJINETE DE 50", "", "", "200,54 €", "", "5", "2"],
        ["617540130", "ARANDELA MUELLE", "", "", "0,18 €", "", "7", "3"],
    ]
    assert completar_cantidad_por_contenido(MAPEO_SIN_CANTIDAD, filas, True)["cantidad"] is None


def test_una_referencia_normativa_nunca_es_cantidad():
    """`03.361.140.1` y `17.000` traen separador de puntos o de miles: el
    predicado exige el 100 % de los valores con forma de cantidad pequeña, y
    esos dos son justo los que reventaron las heurísticas anteriores."""
    filas = [
        ["610840006", "COJINETE", "", "", "200,54 €", "", "", "03.361.140.1"],
        ["617540130", "ARANDELA", "", "", "0,18 €", "", "", "17.000"],
    ]
    assert completar_cantidad_por_contenido(MAPEO_SIN_CANTIDAD, filas, True)["cantidad"] is None


def test_un_peso_en_toneladas_nunca_es_cantidad_aunque_el_documento_declare_una():
    """El caso real que tumbó la primera versión de la regla:
    `6.21/28510.0108`-`0111` p.7 y p.8, encontrado en el reproceso completo.
    En ese documento alguna tabla con cabecera acaba con `cantidad` mapeada
    (se lo asigna el modelo por las filas de ejemplo, aunque ninguna cabecera
    diga literalmente "cantidad"), así que la guarda de "el documento la
    declara" no lo protegía -- y la única columna que ningún campo reclama en
    esas páginas es el PESO en toneladas ("4", "3,3", "2,9"). Cinco líneas por
    expediente se llenaron con el peso del aparato de vía como si fueran
    unidades. Lo que lo descarta es exigir **enteros**: una cantidad estimada
    de referencia es un recuento, un peso lleva decimales."""
    filas = [
        ["", "Semicambio para desvío", "", "", "35.910,00", "", "", "4"],
        ["", "Conjunto aguja-contraaguja", "", "", "39.637,50", "", "", "3,3"],
        ["", "Conjunto aguja-contraaguja", "", "", "62.186,25", "", "", "2,9"],
    ]
    assert completar_cantidad_por_contenido(MAPEO_SIN_CANTIDAD, filas, True)["cantidad"] is None
    # Y con la guarda del documento apagada, tampoco.
    assert completar_cantidad_por_contenido(MAPEO_SIN_CANTIDAD, filas, False)["cantidad"] is None


def test_una_matricula_de_nueve_cifras_nunca_es_cantidad():
    filas = [["", "COJINETE", "", "", "200,54 €", "", "", "610840006"]]
    assert completar_cantidad_por_contenido(MAPEO_SIN_CANTIDAD, filas, True)["cantidad"] is None


def test_un_precio_con_euro_nunca_es_cantidad():
    filas = [["610840006", "COJINETE", "", "", "", "", "", "200,54 €"]]
    assert completar_cantidad_por_contenido(MAPEO_SIN_CANTIDAD, filas, True)["cantidad"] is None


def test_columna_del_todo_vacia_no_es_candidata():
    filas = [["610840006", "COJINETE", "", "", "200,54 €", "", "", ""]]
    assert completar_cantidad_por_contenido(MAPEO_SIN_CANTIDAD, filas, True)["cantidad"] is None


def test_el_cero_que_imprime_el_documento_si_es_una_cantidad():
    """`6.22/28510.0125` p.16-20: su cabecera (p.15) declara "CANTIDADES
    ESTIMADAS DE REFERENCIA" y las páginas de continuación traen 0, 1 y 2 --
    el 0 es un valor real (un elemento del catálogo sin pedido estimado en
    este contrato), no un hueco. `app.catalogo._cantidad_parece_implausible`
    ya lo manda a revisión con ese texto exacto, así que nunca pasa como dato
    confirmado sin que nadie lo mire."""
    filas = [
        ["P-010", "", "", "DS-B1-54-500-0,09-CC-I", "", "UD.", "0", "", "157.355,39 €", ""],
        ["P-011", "611150112", "", "DS-B3-54-320/230-0,11-CR-D", "", "UD.", "2", "", "119.802,15 €", ""],
    ]
    mapeo = {
        "codigo_precio": 0, "matricula": 1, "descripcion": 3, "unidad_medida": 5,
        "cantidad": None, "precio_unitario": 8,
    }
    assert completar_cantidad_por_contenido(mapeo, filas, True)["cantidad"] == 6


def test_sin_filas_no_hace_nada():
    assert completar_cantidad_por_contenido(MAPEO_SIN_CANTIDAD, [], True) is MAPEO_SIN_CANTIDAD
