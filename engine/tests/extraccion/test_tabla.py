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
    # CONTEXTO.md sección 3 / hallazgo de esta sesión: en esta página
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


# Sesión de expedientes sin publicar (docs/analisis-corpus.md hallazgo 6):
# "otros formatos de código de precio" — antes del arreglo, ninguna de estas
# cinco tablas reales aportaba ninguna línea de catálogo porque
# `_es_fila_de_datos` solo reconocía "P-NNN" (con o sin guion Unicode).

def test_codigo_p_sin_guion_un_digito_se_reconoce_como_fila_de_datos():
    with pdfplumber.open(fx.ANEJO_PRECIOS_CODIGO_P_SIN_GUION) as pdf:
        tablas = extraer_tablas_pagina(pdf.pages[0])

    assert len(tablas) == 1
    assert [f[0] for f in tablas[0].filas] == ["P1", "P2"]


def test_codigo_p_sin_guion_dos_digitos_se_reconoce_como_fila_de_datos():
    with pdfplumber.open(fx.ANEJO_PRECIOS_CODIGO_P_DOS_DIGITOS) as pdf:
        tablas = extraer_tablas_pagina(pdf.pages[0])

    assert len(tablas) == 1
    assert [f[0] for f in tablas[0].filas] == ["P01", "P02"]


def test_codigo_con_prefijo_pn_se_reconoce_como_fila_de_datos():
    with pdfplumber.open(fx.ANEJO_PRECIOS_CODIGO_PN) as pdf:
        tablas = extraer_tablas_pagina(pdf.pages[0])

    assert len(tablas) == 1
    assert tablas[0].filas[0][0] == "PN001"
    assert tablas[0].filas[-1][0] == "PN018"
    assert len(tablas[0].filas) == 18


def test_codigo_lote_tipo_y_partida_alzada_se_reconocen_como_fila_de_datos():
    # 6.24/28510.0094: el mismo cuadro de traviesas trae "L0N-T0M" (lote+tipo,
    # no es semánticamente un código de precio per CONTEXTO.md sección 3, pero
    # identifica la fila igual) y "PA-NN" (partida alzada numerada) — dos
    # tablas en el recorte de 2 páginas, cada una con su propia cabecera.
    with pdfplumber.open(fx.ANEJO_PRECIOS_LOTE_TIPO_Y_PARTIDA_ALZADA) as pdf:
        tablas = [t for pagina in pdf.pages for t in extraer_tablas_pagina(pagina)]

    codigos = [fila[0] for tabla in tablas for fila in tabla.filas]
    assert "L01-T01" in codigos
    assert "L02-T01" in codigos
    assert "L03-T13" in codigos
    assert codigos.count("PA-01") == 2  # aparece una vez por página en este recorte
    assert codigos.count("PA-02") == 2


def test_codigo_con_prefijo_cod_se_reconoce_como_fila_de_datos():
    # Bloque 3, sesión de expedientes en revisión por trabajo pendiente real
    # (2026-09-07): 4.26/28510.0020, "Cod0001".."Cod0012" en esta página.
    # Antes del arreglo esta tabla se descartaba entera como espuria y el
    # expediente quedaba sin ninguna línea de catálogo.
    with pdfplumber.open(fx.ANEJO_PRECIOS_CODIGO_COD) as pdf:
        tablas = extraer_tablas_pagina(pdf.pages[0])

    assert len(tablas) == 1
    assert tablas[0].filas[0][0] == "Cod0001"
    assert tablas[0].filas[-1][0] == "Cod0012"
    assert len(tablas[0].filas) == 12


def test_matricula_de_9_digitos_se_reconoce_como_fila_de_datos_sin_codigo_precio():
    # 6.20/28510.0136: esta tabla no trae ninguna columna de código de
    # precio, solo matrícula (CONTEXTO.md sección 2: forma fija de 9 dígitos).
    # Antes del arreglo, `_es_fila_de_datos` solo miraba códigos de precio y
    # esta tabla entera se descartaba como espuria.
    with pdfplumber.open(fx.TABLA_PRECIOS_SOLO_MATRICULA) as pdf:
        tablas = extraer_tablas_pagina(pdf.pages[0])

    assert len(tablas) == 1
    matriculas = [fila[0] for fila in tablas[0].filas]
    assert "642910100" in matriculas
    assert "642910360" in matriculas


# --- Sesión 2026-09-14 ---


def test_codigo_con_sufijo_de_variante_en_mayuscula_es_fila_de_datos():
    # `6.21/28510.0109_ANEJO_7bfc92005f43e68e.pdf` p.15-22: páginas enteras
    # de filas "P-39B", "P-41 A" (aguja/contraaguja del mismo desvío), sin
    # ninguna fila "P-NN" pelada -- antes la tabla se descartaba como espuria.
    from app.extraccion.tabla import _es_fila_de_datos

    assert _es_fila_de_datos(["GAV 1500", "P-39B", "Contraaguja", "...", "1,4", "4.292,05"])
    assert _es_fila_de_datos(["PAV 1500", "P-41 A", "Aguja", "...", "1,7", "8.783,64"])
    # Minúscula pegada: el sello CSV invertido ("P-13\np", de "psj.adilav..."),
    # nunca una variante real.
    assert not _es_fila_de_datos(["P-13\np", "Semicambio", "91.537,95"])


def test_cabecera_con_glifos_sin_decodificar_se_trata_como_sin_cabecera():
    # `6.21/28510.0016_ANEJO_e40fc4e4546ec90b.pdf` p.13: "Nº MATRÍCULA", "REF.
    # ADIF"... en una fuente sin mapa Unicode.
    from app.extraccion.mapeo_cabecera import cabecera_sin_senal
    from app.extraccion.tabla import _combinar_filas_cabecera

    cabecera = _combinar_filas_cabecera([
        ["(cid:69)(cid:465)(cid:3)(cid:68)(cid:4)(cid:100)(cid:90)", "(cid:90)(cid:28)(cid:38)(cid:856)(cid:3)",
         "(cid:24)(cid:28)(cid:94)(cid:18)", "(cid:87)(cid:62)(cid:4)(cid:69)(cid:75)(cid:3) 015-05"],
    ])
    assert cabecera == [None, None, None, None]
    assert cabecera_sin_senal(cabecera)


def test_cabecera_legible_con_un_glifo_suelto_se_conserva():
    # Cabecera real cacheada (`cache_mapeo_cabecera` 81/82): "(€)" en glifos
    # dentro de una celda perfectamente legible -- no se toca.
    from app.extraccion.tabla import _combinar_filas_cabecera

    celda = "PRECIO UNITARIO DE\nREFERENCIA (cid:11)(cid:227)(cid:12)"
    assert _combinar_filas_cabecera([["Nº MATRÍCULA", celda]]) == ["Nº MATRÍCULA", celda]


def test_tabla_que_pierde_su_primera_columna_se_recupera_con_el_segundo_intento():
    # `6.22/28510.0016` (LOTE 6), ANEJO_1 p.21: con los ajustes por defecto,
    # el borde izquierdo de la tabla del LOTE 5 arrastra el del LOTE 6 y
    # esta pierde la columna de los códigos -- sin ellos, se descartaba.
    with pdfplumber.open(fx.ANEJO_LOTES_5_Y_6_BALASTO_0016) as pdf:
        pagina = pdf.pages[0]
        tablas = extraer_tablas_pagina(pagina)
        por_defecto = [t.extract() for t in pagina.find_tables()]

    assert not any(f and f[0] == "P-1" for filas in por_defecto[1:] for f in filas)
    assert len(tablas) == 2
    lote_5, lote_6 = tablas
    assert lote_5.bbox[1] < lote_6.bbox[1]
    assert [f[0] for f in lote_5.filas] == ["P-1", "P-2", "P-3", "P-4"]
    assert [f[0] for f in lote_6.filas] == ["P-1", "P-2", "P-3", "P-4"]
    valores = [[c for c in f if c] for f in lote_6.filas]
    assert [v[-1] for v in valores] == ["14,20 €", "16,50 €", "1,10 €", "0,12 €"]
    assert [v[-2] for v in valores] == ["65.000", "64.000", "65.000", "100.000"]


def test_segundo_intento_no_toca_las_tablas_que_ya_salen():
    # La del LOTE 5, en la misma página, sale igual que con los ajustes por
    # defecto (mismas celdas, misma caja).
    with pdfplumber.open(fx.ANEJO_LOTES_5_Y_6_BALASTO_0016) as pdf:
        pagina = pdf.pages[0]
        lote_5 = extraer_tablas_pagina(pagina)[0]
        por_defecto = pagina.find_tables()[0]

    assert lote_5.bbox == tuple(por_defecto.bbox)
    assert lote_5.filas == por_defecto.extract()[3:]


# Sesión 2026-09-15: cuadro de precios de un solo artículo, sin código de
# precio ni matrícula -- antes se descartaba entero como espurio.
def test_cuadro_sin_codigo_con_cabecera_de_cuadro_se_extrae_sin_el_pie_de_totales():
    with pdfplumber.open(fx.PPT_COMPRESOR_SIN_CODIGO_0027) as pdf:
        tablas = extraer_tablas_pagina(pdf.pages[0])

    assert len(tablas) == 1
    assert tablas[0].cabecera == ["CONCEPTO", "CANTIDAD", "PRECIO", "TOTAL"]
    assert tablas[0].filas == [["Compresor", "1", "18.000,00€", "18.000,00€"]]


def test_tabla_sin_codigo_necesita_descripcion_cantidad_y_precio_en_la_cabecera():
    from app.extraccion.tabla import _filas_cuadro_sin_codigo

    # Resumen de presupuesto por lotes (`2.24/28510.0050`, PPT p.9): sin
    # columna de cantidad no es un cuadro de precios.
    assert _filas_cuadro_sin_codigo([
        ["SUMINISTRO DE ADBLUE (SOLUCIÓN DE UREA AL 32,5%)", None],
        ["TOTAL LOTE 1: Líneas de la Zona Noreste", "35.490,00 €"],
    ]) is None
    # Valor estimado del contrato (`2.26/28510.0006`, PPT p.6).
    assert _filas_cuadro_sin_codigo([
        ["Presupuesto de licitación:", None, "(A) BASE IMPONIBLE", "IVA: (21%)", "TOTAL CON IVA"],
        [None, None, "2.740.603,26 €", "575.526,68 €", "3.316.129,94 €"],
    ]) is None


def test_tabla_sin_codigo_se_corta_en_la_primera_fila_sin_descripcion_o_sin_importe():
    from app.extraccion.tabla import _filas_cuadro_sin_codigo

    filas = [
        ["Nº", "DESCRIPCIÓN", "UD", "PRECIO", "IMPORTE"],
        ["1", "SUMINISTRO\nGAÓLEO C", "89.900,00", "0,808", "72.639,20"],
        [None, None, None, "TOTAL:", "72.639,20"],
        ["2", "Otra cosa", "1", "5,00", "5,00"],
    ]
    assert _filas_cuadro_sin_codigo(filas) == [filas[1]]
    # "TOTAL..." en la columna de descripción es el pie, aunque traiga importe.
    assert _filas_cuadro_sin_codigo([
        ["CONCEPTO", "CANTIDAD", "PRECIO", "TOTAL"],
        ["TOTAL, IVA no incluido", None, "18.000,00€", "18.000,00€"],
    ]) is None


# --- Sesión 2026-09-16 ---


def test_matricula_con_puntos_de_miles_es_fila_de_datos():
    """`6.26/28510.0004`, anejo nº 1 del PPT p.7: un cuadro de un solo
    artículo, sin ninguna columna de código de precio, con la matrícula
    escrita "667.500.506". La normalización de la línea ya la trataba como
    el mismo número desde la sesión 2026-09-14
    (`app.catalogo._MATRICULA_CON_PUNTOS_RE`), pero este detector exigía los
    9 dígitos seguidos: sin ninguna fila de datos, la tabla entera se
    descartaba por espuria y el expediente se quedaba sin líneas."""
    from app.extraccion.tabla import _es_fila_de_datos

    fila = [
        "", "667.500.506", "", "",
        "MÓDEMS G.SHDSL.BIS 2/4 HILOS CON 4 PUERTOS ETHERNET", "", "",
        "100,00", "", "", "400", "",
    ]
    assert _es_fila_de_datos(fila) is True


def test_un_importe_de_nueve_digitos_no_se_confunde_con_una_matricula():
    """El patrón con puntos es exactamente 3+3+3 y nada más: un importe con
    decimales ("1.234.567,89") o un número de otra longitud no entra."""
    from app.extraccion.tabla import _es_fila_de_datos

    assert _es_fila_de_datos(["Presupuesto base de licitación", "1.234.567,89"]) is False
    assert _es_fila_de_datos(["Total", "1.234.567"]) is False
    assert _es_fila_de_datos(["Total", "12.345.678.901"]) is False


def test_matricula_antigua_de_8_cifras_cuenta_como_fila_de_datos():
    # Sesión 2026-09-17, decisión del cliente: "59020019" (fusibles AT,
    # `6.18/28510.0066`) es el formato antiguo real de la matrícula.
    from app.extraccion.tabla import _indice_primera_fila_datos

    filas = [
        ["MATRÍCULA", "DESIGNACIÓN", "PRECIO DE REFERENCIA"],
        ["59020019", "FUSIBLE AT - CA", "116,15"],
    ]
    assert _indice_primera_fila_datos(filas) == 1
    # Sin cabecera de matrícula, hacen falta varias filas con ella.
    assert _indice_primera_fila_datos([["59020019", "FUSIBLE", "116,15"]]) is None
    assert _indice_primera_fila_datos([[f"5902001{i}", "FUSIBLE", "116,15"] for i in range(3)]) == 0
