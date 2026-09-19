"""Las cuatro decisiones del cliente aplicadas el 2026-09-19 (segunda parte):
`PA` fuera de la columna de unidad, la columna "Código de precio" con su
motivo, las descripciones desplazadas de `6.24/28510.0171` y el afinado de la
garantía del reparto por lotes.
"""
from decimal import Decimal

import pytest

from app.catalogo import (
    _construir_campos,
    corregir_descripcion_desplazada_entre_tablas,
)
from app.celdas_vacias import NO_APLICA, NO_CONSTA, celdas_vacias
from app.extraccion.invalidado import INVALIDADO
from app.extraccion.lote_tabla import MOTIVO_TABLA_DEL_CONJUNTO
from app.extraccion.orquestador import _el_cuadro_declara_todos_los_lotes
from app.extraccion.unidad_medida import es_marca_de_partida_alzada, es_unidad_conocida
from app.models import LineaCatalogo

_MAPEO = {
    "codigo_precio": 0, "matricula": 1, "descripcion": 2,
    "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5,
}


# --- 1. "PA" no es una unidad de medida -------------------------------------

@pytest.mark.parametrize("valor", ["PA", "pa", " Pa. ", "P.A."])
def test_pa_se_reconoce_como_marca_de_partida_alzada(valor):
    assert es_marca_de_partida_alzada(valor)


@pytest.mark.parametrize("valor", ["ud", "m", "t", "P", "m3", "t·km"])
def test_una_unidad_real_no_se_confunde_con_la_marca(valor):
    assert not es_marca_de_partida_alzada(valor)


def test_pa_sigue_siendo_valor_conocido_para_no_mandar_la_linea_a_revision():
    """No es un valor ilegible ni un fallo de mapeo: el documento lo pone a
    posta. Si saliera de `_UNIDADES`, la línea se iría a revisión con el
    motivo de "unidad descartada por no ser conocida", que sería falso."""
    assert es_unidad_conocida("PA")


def test_la_celda_de_unidad_queda_vacia_y_sin_motivo_de_revision():
    fila = ["P-07", None, "Partida alzada a justificar para imprevistos", "PA", "1", "234.000,00 €"]
    estado, campos = _construir_campos(fila, _MAPEO)
    assert estado == "ok"
    # `INVALIDADO`, no `None`: tiene que borrar el "PA" ya guardado.
    assert campos["unidad_medida"] is INVALIDADO
    # El literal del documento no se pierde.
    assert campos["unidad_medida_original"] == "PA"
    # No es un defecto de lectura: nada que revisar por esto.
    assert campos["motivo_revision"] is None


def test_el_motivo_de_esa_celda_es_no_aplica_por_partida_alzada():
    linea = LineaCatalogo(
        codigo_precio="P-07", matricula=None, codigo_material=None,
        descripcion="Partida alzada a justificar para imprevistos",
        cantidad=Decimal("1"), precio_unitario=Decimal("234000"),
        baja_lote=Decimal("0.1"), precio_adjudicado=Decimal("210600"),
        unidad_medida=None, motivo_revision=None,
    )
    motivos = {c.campo: (c.motivo, c.detalle) for c in celdas_vacias(linea, "1")}
    assert motivos["unidad_medida"] == (NO_APLICA, "partida alzada")


def test_una_unidad_real_sigue_guardandose():
    fila = ["P-01", "591200013", "DISYUNTOR", "UD", "26", "12.790,80 €"]
    _estado, campos = _construir_campos(fila, _MAPEO)
    assert campos["unidad_medida"] == "ud"


# --- 2. La columna "Código de precio" ---------------------------------------

def _linea(**campos):
    datos = dict(
        codigo_precio="P-001", matricula="697500900", codigo_material="GUANTE",
        descripcion="GUANTE", cantidad=Decimal("30"), precio_unitario=Decimal("24"),
        baja_lote=Decimal("0.54"), precio_adjudicado=Decimal("11.04"),
        unidad_medida="ud", motivo_revision=None,
    )
    datos.update(campos)
    return LineaCatalogo(**datos)


def test_sin_codigo_de_precio_la_celda_lleva_su_motivo():
    motivos = {c.campo: (c.motivo, c.detalle) for c in celdas_vacias(_linea(codigo_precio=None), "1")}
    assert motivos["codigo_precio"] == (
        NO_CONSTA, "el cuadro de precios de este documento no numera sus renglones"
    )


def test_con_codigo_de_precio_no_aparece_ningun_motivo():
    assert "codigo_precio" not in {c.campo for c in celdas_vacias(_linea(), "1")}


def test_la_columna_va_detras_de_las_que_el_cliente_fijo_al_final():
    """"Comentarios" la última (sesión 2026-09-09) y "Motivo de las celdas
    vacías" justo antes (sesión 2026-09-14): la nueva no puede colarse entre
    ellas ni desplazar a ninguna de las trece primeras."""
    from app.exportacion import COLUMNAS

    assert COLUMNAS[-3:] == ["Código de precio", "Motivo de las celdas vacías", "Comentarios"]
    assert COLUMNAS[:13] == [
        "Código interno", "Código de expediente", "Código matriz", "Título expediente",
        "Matrícula del material", "Descripción del material", "Código del material",
        "Cantidad", "Precio unitario", "Lote", "Precio adjudicado", "Baja del lote",
        "Unidad de medida",
    ]


# --- 3. La descripción desplazada de una tabla ------------------------------

# Las descripciones reales de `6.24/28510.0171_ANEJO_1.pdf`: el cuadro de
# precios (p.18) y el anejo de criterios (p.22), el mismo texto cortado en
# sitios distintos.
_P18 = [
    "DISYUNTOR EXTRARRÁPIDO MODELO UR26ED64S DE SECHERON O EQUIVALENTE",
    "CONTACTO FIJO MODELO UR26ED64S DE SECHERON O EQUIVALENTE",
    "CONTACTO MÓVIL MODELO UR26ED64S DE SECHERON O EQUIVALENTE",
]
_P22 = [
    "DISYUNTOR EXTRARRÁPIDO MODELO UR26ED64S DE",
    "SECHERON O EQUIVALENTE CONTACTO FIJO MODELO UR26ED64S DE",
    "SECHERON O EQUIVALENTE CONTACTO MÓVIL MODELO",
]


def _lineas_de_tabla(origen, descripciones, claves=None):
    claves = claves or [f"P-0{i + 1}" for i in range(len(descripciones))]
    return [
        {"tabla_origen": origen, "clave_linea": c, "identificador_lote": "1", "descripcion": d}
        for c, d in zip(claves, descripciones)
    ]


def test_la_tabla_desplazada_toma_la_descripcion_de_la_otra():
    cuadro = _lineas_de_tabla((923, 1), _P18)
    criterios = _lineas_de_tabla((923, 2), _P22)
    assert corregir_descripcion_desplazada_entre_tablas(cuadro + criterios) == 3
    assert [l["descripcion"] for l in criterios] == _P18
    # La tabla buena no se toca.
    assert [l["descripcion"] for l in cuadro] == _P18
    # Y ninguna empieza por el final de la descripción anterior.
    assert not any(l["descripcion"].startswith("SECHERON O EQUIVALENTE") for l in criterios)


def test_dos_tablas_de_materiales_distintos_no_se_tocan():
    a = _lineas_de_tabla((923, 1), ["BRIDA DE 54", "PLACA DE ASIENTO"])
    b = _lineas_de_tabla((923, 2), ["TORNILLO DE 22", "TUERCA DE 22"])
    assert corregir_descripcion_desplazada_entre_tablas(a + b) == 0
    assert [l["descripcion"] for l in a] == ["BRIDA DE 54", "PLACA DE ASIENTO"]


def test_con_una_sola_clave_compartida_no_se_comprueba_nada():
    """Un prefijo entre dos descripciones sueltas sí puede ser casualidad."""
    a = _lineas_de_tabla((923, 1), ["BRIDA"], claves=["P-01"])
    b = _lineas_de_tabla((923, 2), ["BRIDA DE 54 CON TORNILLERÍA"], claves=["P-01"])
    assert corregir_descripcion_desplazada_entre_tablas(a + b) == 0


def test_dos_tablas_identicas_no_se_tocan():
    a = _lineas_de_tabla((923, 1), _P18)
    b = _lineas_de_tabla((923, 2), _P18)
    assert corregir_descripcion_desplazada_entre_tablas(a + b) == 0


def test_con_una_sola_tabla_no_hay_nada_contra_lo_que_probar():
    assert corregir_descripcion_desplazada_entre_tablas(_lineas_de_tabla((923, 2), _P22)) == 0


# --- 4. La garantía afinada -------------------------------------------------

class _Resultado:
    def __init__(self, lineas):
        self.lineas = lineas


def _linea_lote(identificador, motivo=None):
    return {"identificador_lote": identificador, "motivo_revision": motivo}


def test_las_filas_del_anejo_de_criterios_ya_no_cuentan_como_huerfanas():
    """`6.22/28510.0173`: cubre sus dos lotes y sus 183 huérfanas son, las
    183, del anejo de criterios técnicos -- que por diseño no pertenece a
    ningún lote y quedaría huérfano igual."""
    resultado = _Resultado(
        [_linea_lote("1"), _linea_lote("2")]
        + [_linea_lote(None, MOTIVO_TABLA_DEL_CONJUNTO) for _ in range(183)]
    )
    assert _el_cuadro_declara_todos_los_lotes(resultado, {"1": None, "2": None})


def test_una_huerfana_de_verdad_sigue_descartando_el_intento():
    """`4.25/28510.0132`: sus huérfanas son de banda vacía y de tabla
    separada por páginas, no de criterios. La garantía no se afloja."""
    resultado = _Resultado([
        _linea_lote("1"), _linea_lote("2"),
        _linea_lote(None, "banda vacía: posible continuación de tabla partida entre páginas, sin inferir"),
    ])
    assert not _el_cuadro_declara_todos_los_lotes(resultado, {"1": None, "2": None})


def test_mezclar_criterios_con_una_huerfana_real_tambien_descarta():
    resultado = _Resultado([
        _linea_lote("1"), _linea_lote("2"),
        _linea_lote(None, MOTIVO_TABLA_DEL_CONJUNTO),
        _linea_lote(None, "ninguna cabecera LOTE N encontrada en la franja que precede a esta tabla"),
    ])
    assert not _el_cuadro_declara_todos_los_lotes(resultado, {"1": None, "2": None})


def test_sigue_haciendo_falta_cubrir_todos_los_lotes():
    resultado = _Resultado([_linea_lote("1"), _linea_lote(None, MOTIVO_TABLA_DEL_CONJUNTO)])
    assert not _el_cuadro_declara_todos_los_lotes(resultado, {"1": None, "2": None})


def test_un_cuadro_que_solo_trae_criterios_no_reparte_nada():
    resultado = _Resultado([_linea_lote(None, MOTIVO_TABLA_DEL_CONJUNTO) for _ in range(196)])
    assert not _el_cuadro_declara_todos_los_lotes(resultado, {"1": None, "2": None})


# --- 5b. El arreglo del título tiene que ser idempotente ---------------------

class _LoteFalso:
    def __init__(self, identificador):
        self.identificador_lote = identificador
        self.baja_lote = self.importe_licitacion = self.importe_adjudicacion = None


class _ExpedienteFalso:
    def __init__(self, titulo, declarados):
        self.nombre_proyecto = titulo
        self.lotes_totales_declarados = declarados


def test_el_lote_que_declara_el_titulo_no_se_confunde_con_el_sentinela():
    """`LOTE_UNICO` vale "1", el mismo texto que un lote real "Lote 1".
    `6.22/28510.0011` se queda con su lote 1 en una pasada; sin esta guarda,
    en la siguiente ese "1" se vuelve a leer como sentinela, el reparto del
    cuadro lo parte en seis otra vez y recupera los cuadros de sus hermanos."""
    from app.extraccion.orquestador import _lotes_candidatos_del_cuadro

    expediente = _ExpedienteFalso("Lote 1: Jefatura de Barcelona", 6)
    assert _lotes_candidatos_del_cuadro(expediente, [_LoteFalso("1")], None) is None


def test_un_sentinela_de_verdad_sigue_entrando_al_reparto():
    expediente = _ExpedienteFalso("Suministro de balasto. 6 LOTES", 6)
    candidatos = _lotes_candidatos_del_cuadro_seguro(expediente, [_LoteFalso("1")])
    assert sorted(candidatos) == ["1", "2", "3", "4", "5", "6"]


def test_un_titulo_que_declara_otro_lote_no_protege_al_sentinela():
    """El título dice "Lote 4" y el único lote es el sentinela "1": no son el
    mismo, así que la guarda no aplica y el reparto se intenta como siempre."""
    expediente = _ExpedienteFalso("Lote 4: Jefatura de Irún", 6)
    candidatos = _lotes_candidatos_del_cuadro_seguro(expediente, [_LoteFalso("1")])
    assert sorted(candidatos) == ["1", "2", "3", "4", "5", "6"]


def _lotes_candidatos_del_cuadro_seguro(expediente, lotes):
    from app.extraccion.orquestador import _lotes_candidatos_del_cuadro

    candidatos = _lotes_candidatos_del_cuadro(expediente, lotes, None)
    assert candidatos is not None
    return candidatos
