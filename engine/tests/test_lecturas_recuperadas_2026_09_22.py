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


# La fila sin código ni matrícula cuya clave (hash de descripción y orden)
# cambió porque cambió su orden de aparición.
def _lote_sin_codigos(db_session):
    from app.models import Expediente, Lote

    expediente = Expediente(codigo_expediente="2.24/28510.9118")
    db_session.add(expediente)
    db_session.commit()
    lote = Lote(expediente_id=expediente.id, identificador_lote="1")
    db_session.add(lote)
    db_session.commit()
    return lote


_MAPEO_SIN_CODIGOS = {"codigo_precio": None, "matricula": None, "descripcion": 0, "unidad_medida": None,
                      "cantidad": 1, "precio_unitario": 2}


def _guardar_filas(db_session, lote, filas, orden_inicial=0):
    from app.catalogo import guardar_lineas_catalogo

    lineas = [
        construir_linea_catalogo(fila, _MAPEO_SIN_CODIGOS, 8, None, lote.expediente_id, None, orden_inicial + i)
        for i, fila in enumerate(filas)
    ]
    guardar_lineas_catalogo(db_session, lote.id, lineas)
    db_session.commit()


def test_la_misma_fila_con_otro_orden_toma_la_clave_nueva_sin_motivo_de_fusion(db_session):
    from app.models import LineaCatalogo

    lote = _lote_sin_codigos(db_session)
    _guardar_filas(db_session, lote, [["Pala cuadrada", "10", "50,00 €"]], orden_inicial=3)
    antes = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id).one()
    id_antes, clave_antes = antes.id, antes.clave_linea

    _guardar_filas(db_session, lote, [["Pala cuadrada", "10", "50,00 €"]], orden_inicial=5)

    despues = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id).one()
    assert despues.id == id_antes
    assert despues.clave_linea != clave_antes
    assert "fila fundida" not in (despues.motivo_revision or "")


def test_dos_filas_iguales_del_mismo_cuadro_siguen_marcadas_como_fundidas(db_session):
    from app.models import LineaCatalogo

    lote = _lote_sin_codigos(db_session)
    _guardar_filas(db_session, lote, [["Pala cuadrada", "10", "50,00 €"], ["Pala cuadrada", "10", "50,00 €"]])

    filas = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id).all()
    assert len(filas) == 1
    assert "fila fundida" in (filas[0].motivo_revision or "")


# La cita de la baja en "Conciliación", desde la traza de cada lote.
def test_la_cita_de_la_baja_por_lote_sale_de_la_traza_de_cada_lote():
    from decimal import Decimal

    from app.conciliacion import _texto_baja
    from app.models import Expediente, Lote, TrazaOrigen

    expediente = Expediente(codigo_expediente="6.23/28510.9051")
    lote1 = Lote(id=1, identificador_lote="1", baja_lote=Decimal("0.2531"))
    lote2 = Lote(id=2, identificador_lote="2", baja_lote=Decimal("0.2510"))
    trazas = {
        1: [(TrazaOrigen(valor_extraido="0.2531", fragmento="25,31 % de baja", documento_id=7), "ADJUDICACION_1.pdf")],
        2: [
            # La más reciente declara otra cifra: es historia, no la explica.
            (TrazaOrigen(valor_extraido="0.30", fragmento="30 % de baja", documento_id=8), "CONTRATO_9.pdf"),
            (TrazaOrigen(valor_extraido="0.2510", fragmento="baja del 25,10%", documento_id=8), "CONTRATO_2.pdf"),
        ],
    }
    # La traza vieja del expediente ya no manda cuando los lotes tienen la suya.
    vieja = TrazaOrigen(valor_extraido="0.2531", fragmento="baja del 25,31%", documento_id=9)

    texto = _texto_baja(expediente, [lote2, lote1], vieja, "CONTRATO_1.pdf", trazas)

    assert texto == (
        "Sí, distinta por lote: 25,10 % (lote 2, declarada en CONTRATO_2.pdf: “baja del 25,10%”), "
        "25,31 % (lote 1, declarada en ADJUDICACION_1.pdf: “25,31 % de baja”)"
    )


def test_sin_traza_de_lote_sigue_la_del_expediente():
    from decimal import Decimal

    from app.conciliacion import _texto_baja
    from app.models import Expediente, Lote, TrazaOrigen

    expediente = Expediente(codigo_expediente="6.24/28510.9124")
    lote = Lote(id=1, identificador_lote="1", baja_lote=Decimal("0.045"))
    traza = TrazaOrigen(valor_extraido="0.045", fragmento="baja del 4,50%", documento_id=3)

    assert _texto_baja(expediente, [lote], traza, "ADJUDICACION_1.pdf", {}) == (
        "Sí, 4,50 % (declarada en ADJUDICACION_1.pdf: “baja del 4,50%”)"
    )
