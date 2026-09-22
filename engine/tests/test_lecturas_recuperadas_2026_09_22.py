"""Sesión 2026-09-22 -- las celdas que el código ya no leía y la reconstrucción
desde cero perdía (CONTEXTO.md sección 13, "Reconstrucción en paralelo").

Tres causas, cada una con sus filas y su geometría reales:

1. `heredar_mapeo_por_geometria`: en `6.26/28510.0016` la cabecera de la p.10
   parte "PRECIO ADQUISICIÓN" y "CANTIDAD ESTIMADA" en subcolumnas, y las
   pp.11-12 no heredaban el mapeo (83 cantidades).
2. `completar_unidad_por_contenido`: tablas sin cabecera propia de
   `6.22/28510.0094`/`0122`/`0155`/`0156` con "UD." en cada fila y ninguna
   columna de unidad en el mapeo.
3. La columna fantasma de la unidad en `4.26/28510.0020` pp.14-17.
"""
from app.catalogo import construir_linea_catalogo
from app.extraccion.invalidado import INVALIDADO
from app.extraccion.mapeo_cabecera import completar_unidad_por_contenido, heredar_mapeo_por_geometria

# 6.26/28510.0016, anejo p.10 (con cabecera) y p.11 (sin ella), medidos.
COLUMNAS_P10 = (
    (56.94, 93.56), (93.56, 141.14), (141.14, 427.20), (427.20, 487.14), (430.68, 483.66),
    (483.66, 487.14), (487.14, 538.44), (490.68, 534.90), (534.90, 538.44),
)
MAPEO_P10 = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": None, "cantidad": 7,
             "precio_unitario": 4}
COLUMNAS_P11 = ((56.94, 93.56), (93.56, 141.14), (141.14, 427.20), (427.20, 487.14), (487.14, 538.44))


def test_la_continuacion_hereda_la_columna_que_contiene_a_la_subcolumna_de_la_cabecera():
    mapeo = heredar_mapeo_por_geometria(MAPEO_P10, COLUMNAS_P10, COLUMNAS_P11)
    assert mapeo == {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": None,
                     "cantidad": 4, "precio_unitario": 3}


def test_la_coincidencia_exacta_sigue_mandando():
    assert heredar_mapeo_por_geometria(MAPEO_P10, COLUMNAS_P10, COLUMNAS_P10) == MAPEO_P10


def test_dos_campos_no_caen_en_la_misma_columna_por_contencion():
    """Si precio y cantidad fueran subcolumnas de una sola columna de la
    continuación, no se sabe cuál es cuál: no se hereda nada."""
    destino = ((56.94, 93.56), (93.56, 141.14), (141.14, 427.20), (427.20, 538.44))
    assert heredar_mapeo_por_geometria(MAPEO_P10, COLUMNAS_P10, destino) is None


def test_la_contencion_no_le_quita_la_columna_a_un_campo_que_coincide_exacto():
    origen = ((0.0, 50.0), (10.0, 40.0))
    mapeo = {"descripcion": 0, "cantidad": 1}
    assert heredar_mapeo_por_geometria(mapeo, origen, ((0.0, 50.0),)) is None


# 6.22/28510.0094, anejo p.5 (sin cabecera): el mapeo por contenido, sin unidad.
MAPEO_P5 = {"codigo_precio": 0, "matricula": 1, "descripcion": 3, "unidad_medida": None, "cantidad": None,
            "precio_unitario": 9}
FILAS_P5 = [
    ["P-060", "", "", "DSIH-G-60-500-0,085-CC-I-TC", "", "UD.", "", "ALTO", "", "207.349,98 €", ""],
    ["P-061", "", "", "DSIH-G-60-760-0,071-CC-D-TC", "", "UD.", "", "ALTO", "", "240.367,27 €", ""],
    ["P-104", "618060500", "ENMIH-60", None, None, "UD.", "", "ALTO", "", "129.708,59 €", ""],
]


def test_completa_la_unidad_cuando_el_documento_la_declara():
    mapeo = completar_unidad_por_contenido(MAPEO_P5, FILAS_P5, True)
    assert mapeo == {**MAPEO_P5, "unidad_medida": 5}


def test_no_completa_la_unidad_si_el_documento_nunca_la_declara():
    assert completar_unidad_por_contenido(MAPEO_P5, FILAS_P5, False) is MAPEO_P5


def test_una_columna_de_texto_que_no_es_unidad_no_se_toma_por_unidad():
    """"ALTO" (el impacto del fallo) es la otra columna sin reclamar con texto
    corto en todas las filas: no es una unidad."""
    filas = [[c if i != 5 else "" for i, c in enumerate(f)] for f in FILAS_P5]
    assert completar_unidad_por_contenido(MAPEO_P5, filas, True)["unidad_medida"] is None


def test_con_dos_columnas_de_unidad_no_se_adivina():
    filas = [f[:6] + ["ud"] + f[7:] for f in FILAS_P5]
    assert completar_unidad_por_contenido(MAPEO_P5, filas, True)["unidad_medida"] is None


# 4.26/28510.0020, p.14: la cabecera "Ud." ocupa los rangos 3 y 4, y el mapeo
# dice 4; en las filas de jornadas la unidad cae en el 3.
MAPEO_0020 = {"codigo_precio": 0, "matricula": None, "descripcion": 8, "unidad_medida": 4, "cantidad": 5,
              "precio_unitario": 11, "importe": 14}


def _fila_0020(unidad_3, unidad_4, codigo="P-3"):
    return [codigo, None, None, unidad_3, unidad_4, "22", None, "", "Jornada de equipo especializado", "",
            "641,16 €", None, None, "14.105,52 €", None, None]


def _linea(fila):
    return construir_linea_catalogo(fila, MAPEO_0020, 14, None, 1, None, 0)


def test_la_unidad_en_la_columna_de_al_lado_se_recupera():
    linea = _linea(_fila_0020("Ud.", None))
    assert linea["unidad_medida"] == "ud"
    assert linea["unidad_medida_original"] == "Ud."


def test_un_texto_que_no_es_unidad_en_la_columna_de_al_lado_no_se_recupera():
    assert _linea(_fila_0020("Precio\nmensual", None))["unidad_medida"] is None


def test_la_partida_alzada_de_al_lado_sigue_sin_ser_unidad():
    linea = _linea(_fila_0020("PA", None, codigo="P-8"))
    assert linea["unidad_medida_original"] == "PA"
    assert linea["unidad_medida"] is INVALIDADO


def test_la_unidad_de_su_columna_manda():
    assert _linea(_fila_0020("PA", "Ud."))["unidad_medida"] == "ud"
