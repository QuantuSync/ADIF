"""Sesión 2026-09-19 (quinta parte) -- los tres residuales del bloque 1, las
cantidades relocalizadas por página y posición del bloque 2, y los 14 de
cobertura parcial de lotes del bloque 3.

Cada mecanismo con su contraejemplo: lo que hace que estas vías sean
aceptables es exactamente lo que se niegan a hacer.
"""
from decimal import Decimal

import pytest

from app.catalogo import construir_linea_catalogo
from app.extraccion.codigo_material import (
    guardar_codigo_material_cacheado,
    obtener_codigo_material_cacheado,
)
from app.extraccion.localizador import (
    _linea_cuadra_consigo_misma,
    _lineas_que_cuadran,
    localizar_paginas_candidatas,
)
from app.extraccion.mapeo_cabecera import intentar_mapeo_determinista
from app.extraccion.pipeline_anejo import descartar_bloques_de_lote_que_no_cuadran
from app.extraccion.tabla import (
    _bloques_por_fila_de_lote,
    _cifra_sin_decimales,
    _cuadro_demostrado_por_aritmetica,
    _etiqueta_de_lote,
    _filas_cuadro_sin_codigo,
    _precios_demostrados_por_un_total,
    _tripleta_que_cuadra,
)
from app.extraccion.texto import PaginaTexto

# --------------------------------------------------------------------------
# Bloque 1 — la cantidad que cae en su propia columna fantasma
# --------------------------------------------------------------------------

# Fila real de `6.24/28510.0173` ANEJO_1 p.9: cabecera "PARTIDA | MATRÍCULA |
# [fantasma] | DESIGNACIÓN | [fantasma] | [fantasma] | PRECIO ADQUISICIÓN |
# [fantasma] | CANTIDAD ESTIMADA" y una fila con descripción, precio y
# cantidad cada uno un sitio a la izquierda de su columna.
_MAPEO_0173 = {
    "codigo_precio": 0, "matricula": 1, "descripcion": 3,
    "unidad_medida": None, "cantidad": 8, "precio_unitario": 6,
}
_FILA_0173 = ["", "663310005", "", "", "Disyuntor Térmico, TCP, 8 A", "22,37 €", "", "1", ""]


def test_la_cantidad_desplazada_entra_con_la_descripcion_y_el_precio():
    linea = construir_linea_catalogo(_FILA_0173, _MAPEO_0173, 9, None, 1, None, 0)
    assert linea is not None
    assert linea["descripcion"].startswith("Disyuntor Térmico")
    assert linea["precio_unitario"] == Decimal("22.37")
    assert linea["cantidad"] == Decimal("1")
    assert "columna fantasma" in linea["motivo_revision"]


def test_una_descripcion_que_es_solo_una_cifra_se_descarta():
    """`2.22/28510.0075` p.96: la tabla es "código | servicio | PRECIO |
    CANTIDAD | IMPORTE" -- precio antes de cantidad -- y el mapeo derivado del
    contenido dejaba `descripcion = "5.200,00 €"` y `precio_unitario = 1`.

    Descartada la cifra, la recuperación de último recurso encuentra la
    designación de verdad en la columna que el mapeo no reclama, y la fila
    sale con su precio bien: 1 × 5.200,00 €. Sin esa recuperación se quedaría
    sin descripción, y sin descripción ni matrícula no entraría (comprobación
    permanente de 2026-09-06) -- las dos salidas son correctas; la que nunca
    vale es guardar un importe como descripción."""
    mapeo = {
        "codigo_precio": None, "matricula": None, "descripcion": 2,
        "unidad_medida": None, "cantidad": 3, "precio_unitario": 4,
    }
    fila = ["1.1", "SERVICIO DE DESMONTAJE Y MONTAJE", "5.200,00 €", "1", "5.200,00 €"]
    linea = construir_linea_catalogo(fila, mapeo, 96, None, 1, None, 0)
    assert linea is not None
    assert linea["descripcion"] == "SERVICIO DE DESMONTAJE Y MONTAJE"
    assert linea["cantidad"] == Decimal("1")
    assert linea["precio_unitario"] == Decimal("5200.00")
    assert "solo una cifra" in linea["motivo_revision"]


def test_sin_otra_columna_con_texto_la_linea_no_entra():
    """Misma regla, sin red de recuperación: si la única columna con texto es
    la que traía el importe, no hay descripción que salvar."""
    mapeo = {
        "codigo_precio": None, "matricula": None, "descripcion": 0,
        "unidad_medida": None, "cantidad": 1, "precio_unitario": 2,
    }
    assert construir_linea_catalogo(["5.200,00 €", "1", "5.200,00 €"], mapeo, 96, None, 1, None, 0) is None


def test_si_la_designacion_cayo_en_otra_columna_reclamada_la_fila_tampoco_entra():
    """El caso real de `2.22/28510.0075` p.96, medido en el reproceso: su
    cabecera es `['PRESUPUESTO', None, None, None, None]` -- nada que mapear -,
    así que el mapeo cayó entero un sitio a la izquierda y la designación no
    quedó en una columna libre, sino en la que el mapeo llama `cantidad`.

    La recuperación de último recurso solo mira columnas sin reclamar, así que
    aquí no encuentra nada, y la fila **no entra**: el mapeo está demostrado
    mal y su precio (1,00 € por un servicio de 5.200,00 €) sería una mentira
    publicada. Cuatro filas del corpus dependen de esto."""
    mapeo = {
        "codigo_precio": 2, "matricula": None, "descripcion": 2,
        "unidad_medida": None, "cantidad": 1, "precio_unitario": 3,
    }
    fila = ["1.1", "SERVICIO DE DESMONTAJE Y MONTAJE", "5.200,00 €", "1", "5.200,00 €"]
    assert construir_linea_catalogo(fila, mapeo, 96, None, 1, None, 0) is None


def test_una_descripcion_de_verdad_no_se_descarta_por_traer_cifras():
    mapeo = {
        "codigo_precio": 0, "matricula": None, "descripcion": 1,
        "unidad_medida": None, "cantidad": 2, "precio_unitario": 3,
    }
    fila = ["P-1", "Armario ETSI 2200*600*300 mm.", "10", "830,91 €"]
    linea = construir_linea_catalogo(fila, mapeo, 18, None, 1, None, 0)
    assert linea is not None and linea["descripcion"].startswith("Armario ETSI")


def test_no_se_inventa_una_cantidad_cuando_la_columna_vecina_no_es_un_numero():
    """Contraejemplo: la celda contigua a la de cantidad trae texto, no un
    número. La descripción y el precio sí se recuperan; la cantidad no."""
    fila = ["", "663310005", "", "", "Disyuntor Térmico, TCP, 8 A", "22,37 €", "", "Ancho 1668", ""]
    linea = construir_linea_catalogo(fila, _MAPEO_0173, 9, None, 1, None, 0)
    assert linea is not None and linea["cantidad"] is None


# --------------------------------------------------------------------------
# Bloque 1 — el precio sin decimales ni símbolo, demostrado por un total
# --------------------------------------------------------------------------

# Cuadro real de `6.17/28510.0116` ANEJO_1 p.9 (reconocimiento óptico):
# matrícula con letra final, precio sin decimales ni símbolo.
CUADRO_0116 = [
    ["MATRÍCULA", "DESIGNACIÓN", "PRECIO DE REFERENCIA € / ud"],
    ["69520000N", "CELDA DE LÍNEA, corte y aislamiento íntegro en SF6", "5.400"],
    ["69520015N", "CELDA DE MEDIDA, aislamiento 36kV", "9.480"],
    ["69520020N", "CELDA DE LÍNEA CON TRANSFORMADOR", "9.900"],
]
# Su propio ANEJO declara las cantidades ("2 celdas de cada") y el total
# ("49.560 € sin IVA"): 2 × (5.400 + 9.480 + 9.900) = 49.560,00 €.
PRESUPUESTO_0116 = (Decimal("49560.0000"),)


def test_un_precio_sin_decimales_entra_si_el_presupuesto_lo_demuestra():
    datos = _filas_cuadro_sin_codigo(CUADRO_0116, PRESUPUESTO_0116)
    assert datos is not None and len(datos) == 3


def test_sin_presupuesto_publicado_el_cuadro_se_queda_fuera():
    """Condición literal del cliente: "si no hay con qué demostrarlo, se
    quedan fuera"."""
    assert _filas_cuadro_sin_codigo(CUADRO_0116, ()) is None


def test_un_presupuesto_que_no_es_multiplo_exacto_no_demuestra_nada():
    assert _filas_cuadro_sin_codigo(CUADRO_0116, (Decimal("49000"),)) is None


def test_una_tabla_que_mezcla_importes_y_cifras_peladas_se_descarta():
    """Si unas filas traen importe de verdad y otras una cifra pelada, la
    cifra pelada no es un precio sin demostrar: es otra cosa."""
    mezclada = [
        CUADRO_0116[0],
        ["69520000N", "CELDA DE LÍNEA", "5.400,00 €"],
        CUADRO_0116[2],
        CUADRO_0116[3],
    ]
    assert _filas_cuadro_sin_codigo(mezclada, PRESUPUESTO_0116) is None


def test_una_cifra_pelada_corta_no_pasa_por_precio():
    """Un entero suelto ("16", "2") es indistinguible de una cantidad."""
    assert _cifra_sin_decimales("16") is None
    assert _cifra_sin_decimales("2") is None
    assert _cifra_sin_decimales("5.400,00 €") is None
    assert _cifra_sin_decimales("5.400") == Decimal("5400")


def test_dos_presupuestos_que_cuadran_a_la_vez_no_demuestran_nada():
    precios = [Decimal("100"), Decimal("100"), Decimal("100")]
    assert _precios_demostrados_por_un_total(precios, (Decimal("300"), Decimal("600"))) is False
    assert _precios_demostrados_por_un_total(precios, (Decimal("300"),)) is True


# --------------------------------------------------------------------------
# Bloque 1 — la tabla que se demuestra por la aritmética de sus filas
# --------------------------------------------------------------------------

# Cuadro real de `3.16/28510.0044` ANEJO_1 p.17, releído con un modelo mejor:
# "MEDICIÓN PRESUPUESTADA | P.UNITARIO | TOTAL" -- ningún rótulo que la etapa
# 4 reconozca, y la columna de descripción rotulada con el título del cuadro.
CUADRO_0044 = [
    ["Nº\nOrden", "Código", "PRESUPUESTO. SUSTITUCIÓN DE EQUIPOS", "MEDICIÓN\nPRESUPUESTADA",
     "P.UNITARIO", "TOTAL"],
    ["01", "", "Obra civil", "", "", ""],
    ["", "1.3", "Acondicionamiento de emplazamientos", "", "", ""],
    ["", "", "Suministro e instalación de equipo de aire acondicionado", "1", "2.280,23 €",
     "2.280,23 €"],
    ["", "", "ADM STM-4. Incluye mínimo 16 tributarios de 2 Mb/s", "92", "7.191,18 €",
     "661.588,56 €"],
    ["", "", "Interfaz STM-1 S1.1, óptica", "14", "1.360,00 €", "19.040,00 €"],
]


def test_la_aritmetica_de_las_filas_demuestra_el_cuadro():
    demostrado = _cuadro_demostrado_por_aritmetica(CUADRO_0044)
    assert demostrado is not None
    inicio, datos = demostrado
    # La cabecera es solo la fila 0; las filas de sección no son datos.
    assert inicio == 1
    assert len(datos) == 3
    assert all(fila[3] and fila[4] and fila[5] for fila in datos)


def test_las_filas_de_seccion_no_entran_como_lineas():
    """Condición del cliente: "las líneas que salgan solo entran si pasan la
    comprobación aritmética de su fila". "Obra civil" no la pasa."""
    _inicio, datos = _cuadro_demostrado_por_aritmetica(CUADRO_0044)
    assert not any("Obra civil" in (c or "") for fila in datos for c in fila)


def test_una_tabla_sin_columna_de_descripcion_no_se_demuestra():
    """Defecto real encontrado por la auditoría del reproceso completo:
    `2.23/28510.0098`/`6.22/28510.0051`/`0159` traen "código | cantidad |
    precio | importe" y ni una designación. Sus filas cuadran (20 × 24,00 =
    480,00) y entraron como 45 líneas de catálogo **sin descripción**, que es
    lo que la comprobación permanente de `construir_linea_catalogo` existe
    para impedir. Un código es un solo token con dígitos; una designación es
    una frase."""
    solo_codigos = [
        ["SFT01-2388L-PH-6920", "20", "24,00 €", "480,00 €"],
        ["SFT01-2389-PH-6920", "130", "18,00 €", "2.340,00 €"],
        ["SFT01-2390-PH-6920", "1.400", "8,00 €", "11.200,00 €"],
    ]
    assert _tripleta_que_cuadra(solo_codigos) is not None  # la aritmética sí cuadra
    assert _cuadro_demostrado_por_aritmetica(solo_codigos) is None  # y aun así no entra


def test_una_fila_sin_descripcion_no_sale_aunque_su_tabla_si_sea_un_cuadro():
    """`3.16/28510.0044` p.19: la fila "12.01" cuadra (1 × 1.980,50) pero su
    celda de descripción vuelve vacía del reconocimiento óptico -- el rótulo
    "Seguridad y Salud" cae en la fila de arriba. La tabla entra; esa fila
    no."""
    filas = [
        ["09.01", "Instalación y puesta a punto de equipo SDH, armario ETSI", "90", "931,03 €",
         "83.792,70 €"],
        ["12", "Seguridad y Salud", "", "", ""],
        ["12.01", "", "1", "1.980,50", "1.980,50 €"],
        ["", "", "", "TOTAL", "824.323,67 €"],
    ]
    demostrado = _cuadro_demostrado_por_aritmetica(filas)
    assert demostrado is not None
    _inicio, datos = demostrado
    assert len(datos) == 1 and datos[0][0] == "09.01"


def test_un_resumen_de_presupuesto_no_se_demuestra():
    """Contraejemplo real, la p.15 del mismo documento: tres conceptos y su
    importe, sin ninguna multiplicación."""
    resumen = [
        ["PRESUPUESTO DE CONTRATA", "824.323,67", "EUROS"],
        ["I.V.A. (21%).", "173.107,97 €", "EUROS"],
        ["TOTAL PRESUPUESTO DE CONTRATA", "997.431,64 €", "EUROS"],
    ]
    assert _cuadro_demostrado_por_aritmetica(resumen) is None


def test_la_identidad_gratis_de_cantidad_uno_no_basta():
    """"1 × X = X" la cumple cualquier tabla de conceptos a tanto alzado: se
    exige al menos una fila con una multiplicación de verdad."""
    a_tanto_alzado = [
        ["Concepto", "Uds", "Precio", "Importe"],
        ["Servicio A", "1", "1.000,00 €", "1.000,00 €"],
        ["Servicio B", "1", "2.000,00 €", "2.000,00 €"],
    ]
    assert _tripleta_que_cuadra(a_tanto_alzado) is None


def test_una_tabla_con_dos_tripletas_que_cuadran_es_ambigua():
    ambigua = [
        ["a", "2", "10,00 €", "20,00 €", "10,00 €", "20,00 €"],
        ["b", "3", "10,00 €", "30,00 €", "10,00 €", "30,00 €"],
    ]
    assert _tripleta_que_cuadra(ambigua) is None


# --------------------------------------------------------------------------
# Bloque 1 — la etapa 3 abre la página por su propia aritmética
# --------------------------------------------------------------------------

_LINEA_0044 = (
    "ADM STM-4. Incluye mínimo 16 tributarios de 2 Mb/s, 2 interfaces ópticas S4.1 "
    "92 7.191,18 € 661.588,56 €"
)


def test_una_linea_que_cuadra_consigo_misma_se_reconoce():
    assert _linea_cuadra_consigo_misma(_LINEA_0044)


def test_una_frase_que_cita_un_precio_no_cuadra():
    assert not _linea_cuadra_consigo_misma(
        "El presupuesto máximo de licitación asciende a 49.560,00 € sin IVA"
    )


def test_una_fila_de_cifras_sin_descripcion_no_cuadra():
    assert not _linea_cuadra_consigo_misma("92 7.191,18 € 661.588,56 €")


def test_tres_lineas_que_cuadran_abren_la_pagina():
    texto = "\n".join([
        "Suministro e instalación de equipo de aire acondicionado 1 2.280,23 € 2.280,23 €",
        _LINEA_0044,
        "Interfaz STM-1 S1.1, óptica, según especificación técnica 14 1.360,00 € 19.040,00 €",
    ])
    assert _lineas_que_cuadran(texto) == 3
    localizacion = localizar_paginas_candidatas([PaginaTexto(numero=1, texto=texto)])
    assert [c.numero for c in localizacion.candidatas] == [1]


def test_una_sola_linea_que_cuadra_no_abre_una_pagina_por_si_sola():
    texto = "Interfaz STM-1 S1.1, óptica, según especificación técnica 14 1.360,00 € 19.040,00 €"
    localizacion = localizar_paginas_candidatas([PaginaTexto(numero=1, texto=texto)])
    assert localizacion.candidatas == []


# --------------------------------------------------------------------------
# Bloque 2 — "MEDICIÓN" es la columna de cantidad
# --------------------------------------------------------------------------

def test_medicion_se_mapea_a_cantidad():
    """Cabecera real de `4.26/28510.0031` p.8. `app.extraccion.tabla` y
    `app.extraccion.localizador` ya trataban "MEDICIÓN" como cantidad desde
    2026-09-15; el vocabulario del mapeo se había quedado sin ella."""
    mapeo = intentar_mapeo_determinista(
        ["SUMINSTRO CODIGO", "DESCRIPCIÓN", "UNIDAD", "MEDICIÓN", "Precio Unitario", "IMPORTE"]
    )
    assert mapeo is not None
    assert mapeo["cantidad"] == 3
    assert mapeo["precio_unitario"] == 4
    assert mapeo["unidad_medida"] == 2


# --------------------------------------------------------------------------
# Bloque 3 — el cuadro que mete todos sus lotes en la misma tabla
# --------------------------------------------------------------------------

# Tabla real de `3.21/28510.0098` CONTRATO_1 p.106: tres lotes en una sola
# caja de tabla, y el tercero sin repetir la cabecera de columnas.
TABLA_TRES_LOTES = [
    ["LOTE 1", "", ""],
    ["Concepto", "Unidades", "Importe"],
    ["Calibrador multiproducto con opción de calibración", "3", "210.000,00 €"],
    ["LOTE 2", "", ""],
    ["Concepto", "Unidades", "Importe"],
    ["Calibrador de comprobadores de seguridad eléctrica", "1", "23.000,00 €"],
    ["LOTE 3", "", ""],
    ["Divisor de tensión y Multímetro de alta tensión", "1", "10.000,00 €"],
    ["TOTAL: 243.000,00 €", "", ""],
]


def test_una_fila_que_es_solo_la_etiqueta_de_un_lote_se_reconoce():
    assert _etiqueta_de_lote(["LOTE 1", "", ""]) == "LOTE 1"
    assert _etiqueta_de_lote(["LOTE 1. REPUESTOS PARA REGLAS", "", ""]).startswith("LOTE 1.")
    # Una fila con datos además de la etiqueta no es una etiqueta de bloque.
    assert _etiqueta_de_lote(["LOTE 1", "3", "210.000,00 €"]) is None
    assert _etiqueta_de_lote(["Concepto", "Unidades", "Importe"]) is None


def test_la_tabla_se_parte_en_un_bloque_por_lote():
    bloques = _bloques_por_fila_de_lote(TABLA_TRES_LOTES, ())
    assert bloques is not None and len(bloques) == 3
    assert [etiqueta for etiqueta, _cab, _datos, _i, _f in bloques] == ["LOTE 1", "LOTE 2", "LOTE 3"]
    # El tercero no repite cabecera: usa la del bloque anterior.
    assert all(len(datos) == 1 for _e, _c, datos, _i, _f in bloques)
    assert bloques[2][1] == ["Concepto", "Unidades", "Importe"]


def test_el_pie_de_totales_no_entra_como_linea():
    bloques = _bloques_por_fila_de_lote(TABLA_TRES_LOTES, ())
    assert not any("TOTAL" in (c or "") for _e, _c, datos, _i, _f in bloques for fila in datos for c in fila)


def test_una_tabla_sin_etiquetas_de_lote_no_se_parte():
    assert _bloques_por_fila_de_lote(CUADRO_0116, ()) is None


def test_un_bloque_que_no_es_un_cuadro_descarta_la_particion_entera():
    con_basura = TABLA_TRES_LOTES[:3] + [["LOTE 2", "", ""], ["Notas varias", "", ""]]
    assert _bloques_por_fila_de_lote(con_basura, ()) is None


def test_la_etiqueta_de_lote_de_la_tabla_gana_sobre_la_franja():
    """Defecto real encontrado al verificar `3.22/28510.0106`: entre el bloque
    del lote N y el del N+1 el documento imprime "El presupuesto base del lote
    N es de VEINTISEIS MIL EUROS (26.000,00 €)". La franja gana normalmente, y
    así cada bloque se quedaba con el lote del ANTERIOR -- los cinco
    desplazados uno. La etiqueta está DENTRO de la tabla, justo encima de sus
    filas: es la declaración más específica que hay sobre ella."""
    from app.extraccion.lote_tabla import asociar_lote_tabla

    class _PaginaFalsa:
        width = 595.0

        def crop(self, caja):
            pagina = self

            class _Recorte:
                def extract_text(self_inner):
                    return "El presupuesto base del lote 2 es de NUEVE MIL EUROS (9.000,00 €), IVA excluido."

            return _Recorte()

    resultado = asociar_lote_tabla(
        _PaginaFalsa(), 100.0, (0.0, 200.0, 595.0, 300.0),
        identificadores_validos={"3", "5"},
        texto_titulo_tabla="Concepto Unidades Precio unitario (€) Importe (€)",
        texto_lote_propio="LOTE 3 ‐ Equipos para ensayos de materiales",
    )
    assert resultado.identificador_lote == "3"
    # Sin etiqueta propia, la franja sigue mandando como siempre.
    sin_etiqueta = asociar_lote_tabla(
        _PaginaFalsa(), 100.0, (0.0, 200.0, 595.0, 300.0),
        identificadores_validos={"2", "3"},
        texto_titulo_tabla="Concepto Unidades Precio unitario (€) Importe (€)",
    )
    assert sin_etiqueta.identificador_lote == "2"


# --------------------------------------------------------------------------
# Bloque 3 — la prueba aritmética que exigió el cliente
# --------------------------------------------------------------------------

def _linea(identificador, cantidad, precio, de_bloque=True):
    linea = {
        "identificador_lote": identificador,
        "cantidad": Decimal(cantidad),
        "precio_unitario": Decimal(precio),
        "motivo_revision": None,
    }
    if de_bloque:
        linea["de_bloque_de_lote"] = True
    return linea


def test_un_lote_que_cuadra_con_su_presupuesto_se_queda():
    lineas = [_linea("3", "1", "10000")]
    quedan, motivos = descartar_bloques_de_lote_que_no_cuadran(
        lineas, {"3": Decimal("10000.0000")}
    )
    assert len(quedan) == 1 and motivos == []
    assert "de_bloque_de_lote" not in quedan[0]


def test_un_lote_que_no_cuadra_no_entra():
    """Caso real: "Concepto | Unidades | Importe" cuya tercera columna es el
    IMPORTE de la fila, no el precio unitario -- 3 × 210.000,00 € da el triple
    del presupuesto de su lote."""
    lineas = [_linea("1", "3", "210000")]
    quedan, motivos = descartar_bloques_de_lote_que_no_cuadran(
        lineas, {"1": Decimal("210000.0000")}
    )
    assert quedan == []
    assert len(motivos) == 1 and "no cuadra con el presupuesto" in motivos[0]


def test_sin_presupuesto_publicado_no_hay_con_que_comprobar_y_entran():
    lineas = [_linea("4", "2", "100")]
    quedan, _motivos = descartar_bloques_de_lote_que_no_cuadran(lineas, {"4": None})
    assert len(quedan) == 1


def test_no_se_descarta_una_linea_que_ya_salia_antes():
    """Solo se descartan las recuperadas por esta vía; la suma sí es la del
    lote entero."""
    previa = _linea("1", "1", "1000", de_bloque=False)
    nueva = _linea("1", "3", "210000")
    quedan, motivos = descartar_bloques_de_lote_que_no_cuadran(
        [previa, nueva], {"1": Decimal("210000.0000")}
    )
    assert quedan == [previa] and len(motivos) == 1


# --------------------------------------------------------------------------
# Defecto de paso: la caché de código de material tolera el duplicado
# --------------------------------------------------------------------------

def test_guardar_dos_veces_el_mismo_termino_no_revienta(db_session):
    """`3.22/28510.0009`: dos tablas del mismo documento derivan el término
    "CEPILLO" y la segunda inserción tumbaba la extracción del documento
    entero con una `UniqueViolation`."""
    primera = guardar_codigo_material_cacheado(db_session, "CEPILLO", "CEPILLO", origen="modelo")
    segunda = guardar_codigo_material_cacheado(db_session, "CEPILLO", "OTRA COSA", origen="modelo")
    assert segunda.id == primera.id
    # El valor cacheado no se pisa: la primera respuesta es la que vale.
    assert obtener_codigo_material_cacheado(db_session, "CEPILLO").codigo_material == "CEPILLO"


def test_un_cuadro_con_el_precio_antes_que_la_cantidad_tambien_se_demuestra():
    """`2.19/28510.0214`: "Concepto | Precio unitario | Cantidad |
    Presupuesto". La identidad se cumple igual —la multiplicación es
    conmutativa— y quién es cada columna lo decide la etapa 5 con la cabecera,
    no esta comprobación. Se probó a exigir que la primera columna de la
    tripleta no llevara el símbolo de moneda y **se revirtió**: quitaba 9
    líneas buenas de dos expedientes para dejar fuera 4 malas de otro."""
    precio_antes_que_cantidad = [
        ["Concepto", "Precio unitario", "Cantidad", "Presupuesto"],
        ["Mascarilla tipo FFP2 para partículas finas", "1,00 €", "1.500", "1.500,00 €"],
        ["Mascarilla tipo FFP2 para gases y vapores", "2,10 €", "1.500", "3.150,00 €"],
    ]
    assert _tripleta_que_cuadra(precio_antes_que_cantidad) == (1, 2, 3)
