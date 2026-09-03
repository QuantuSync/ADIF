import pdfplumber

from app.extraccion.tabla import extraer_tablas_pagina
from app.extraccion.texto import normalizar
from tests import fixtures as fx


def test_cabecera_de_una_sola_fila_se_extrae_tal_cual():
    with pdfplumber.open(fx.ANEJO_PRECIOS_GUANTES) as pdf:
        tablas = extraer_tablas_pagina(pdf.pages[10])  # página 11

    assert len(tablas) == 1
    tabla = tablas[0]
    assert tabla.pagina == 11
    assert normalizar(tabla.cabecera[0]) == "codigo precio"
    assert len(tabla.filas) == 13
    assert tabla.filas[0][0] == "P-001"


def test_cabecera_partida_en_varias_filas_fisicas_se_reconstruye():
    # CLAUDE.md sección 3 / hallazgo de esta sesión: en esta página
    # find_tables() devuelve la cabecera repartida en 8 filas físicas antes
    # de la primera fila de datos (P-001). Debe reconstruirse en una sola
    # fila lógica, igual que la cabecera limpia de la página 19 del mismo
    # documento.
    with pdfplumber.open(fx.ANEJO_PRECIOS_TRAVIESAS) as pdf:
        tablas_18 = extraer_tablas_pagina(pdf.pages[17])  # página 18
        tablas_19 = extraer_tablas_pagina(pdf.pages[18])  # página 19

    assert len(tablas_18) == 2  # la tabla ancha se detecta partida en dos regiones
    assert len(tablas_19) == 1

    cabeceras_normalizadas = {tuple(normalizar(c) for c in t.cabecera) for t in tablas_18 + tablas_19}
    # Las tres regiones son la misma tabla lógica: una única cabecera reconstruida.
    assert len(cabeceras_normalizadas) == 1
    cabecera = next(iter(cabeceras_normalizadas))
    assert cabecera == (
        "codigo de precio",
        "descripcion",
        "unidad de medida",
        "cantidades estimadas de referencia",
        "precio de referencia del elemento",
    )


def test_tabla_espuria_sin_codigo_de_precio_se_descarta():
    # Página 17: una tabla de identificación/firmas del documento, sin
    # ninguna fila con código de precio ("P-NNN"). No debe aparecer como
    # cuadro de precios.
    with pdfplumber.open(fx.ANEJO_PRECIOS_TRAVIESAS) as pdf:
        tablas = extraer_tablas_pagina(pdf.pages[16])  # página 17

    assert tablas == []


def test_celdas_con_codigo_partido_por_salto_de_linea():
    # Página 23 del mismo fixture: la columna estrecha envuelve "P-001" en
    # dos líneas dentro de la misma celda ("P-\n001"). No es cabecera
    # partida (eso ya lo cubre el test anterior): es una celda de datos con
    # salto de línea interno, y debe seguir contando como fila de datos.
    with pdfplumber.open(fx.ANEJO_PRECIOS_TRAVIESAS) as pdf:
        tablas = extraer_tablas_pagina(pdf.pages[22])  # página 23

    assert len(tablas) == 1
    assert tablas[0].filas[0][0] == "P-\n001"
    assert len(tablas[0].filas) == 13


def test_codigo_con_guion_unicode_se_reconoce_como_fila_de_datos():
    # docs/analisis-corpus.md hallazgo 2: expediente real 6.23/28510.0018,
    # página 12, cuadro de precios de carriles con código "P‐01".."P‐13"
    # (guion U+2010, no ASCII). Antes del arreglo esta tabla se descartaba
    # entera como espuria porque ninguna fila pasaba `_es_fila_de_datos`.
    with pdfplumber.open(fx.ANEJO_PRECIOS_CARRILES_GUION_UNICODE) as pdf:
        tablas = extraer_tablas_pagina(pdf.pages[11])  # página 12

    assert len(tablas) == 1  # la segunda tabla de la página es la leyenda espuria, sin código
    tabla = tablas[0]
    assert normalizar(tabla.cabecera[1]) == "codigo"
    assert len(tabla.filas) == 13
    assert tabla.filas[0][1] == "P‐01"  # el guion Unicode se conserva en la celda cruda
    assert tabla.filas[-1][1] == "P‐13"
