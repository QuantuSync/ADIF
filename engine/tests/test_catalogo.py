from decimal import Decimal

from app.catalogo import (
    _combinar_por_clave,
    calcular_clave_linea,
    construir_linea_catalogo,
    construir_lineas_desde_tabla,
    guardar_lineas_catalogo,
)
from app.extraccion.tabla import TablaExtraida
from app.models import Expediente, Lote, LineaCatalogo


def _lote(db_session, identificador="1"):
    expediente = Expediente(codigo_expediente="6.24/28510.9999")
    db_session.add(expediente)
    db_session.commit()
    lote = Lote(expediente_id=expediente.id, identificador_lote=identificador)
    db_session.add(lote)
    db_session.commit()
    return lote


def test_construir_linea_catalogo_deriva_precio_adjudicado():
    mapeo = {"codigo_precio": 0, "matricula": 1, "descripcion": 2, "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5}
    fila = ["P-001", "697500900", "GUANTE X", "UN", "30", "24,00"]

    linea = construir_linea_catalogo(
        fila, mapeo, pagina=11, documento_origen_id=7, baja_lote=Decimal("0.10"), orden_aparicion=0
    )

    assert linea["clave_linea"] == "P-001"
    assert linea["matricula"] == "697500900"
    assert linea["descripcion"] == "GUANTE X"
    assert linea["cantidad"] == Decimal("30")
    assert linea["precio_unitario"] == Decimal("24.00")
    assert linea["precio_adjudicado"] == Decimal("21.600")  # 24,00 * 0,90
    assert linea["documento_origen_id"] == 7
    assert linea["pagina"] == 11


def test_construir_linea_catalogo_sin_baja_no_deriva_precio_adjudicado():
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["P-050", "PARTIDA ALZADA", "100.000,00"]

    linea = construir_linea_catalogo(fila, mapeo, pagina=18, documento_origen_id=None, baja_lote=None, orden_aparicion=0)

    assert linea["precio_unitario"] == Decimal("100000.00")
    assert linea["precio_adjudicado"] is None


def test_construir_linea_catalogo_codigo_partido_por_salto_de_linea_se_limpia():
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["P-\n001", "Traviesa", "1,00\n€"]

    linea = construir_linea_catalogo(fila, mapeo, pagina=23, documento_origen_id=None, baja_lote=None, orden_aparicion=0)

    assert linea["codigo_precio"] == "P-001"
    assert linea["precio_unitario"] == Decimal("1.00")


def test_clave_linea_usa_codigo_precio_por_encima_de_matricula():
    assert calcular_clave_linea("P-001", "697500900", "x", 0) == "P-001"


def test_clave_linea_cae_a_hash_de_descripcion_sin_codigo_ni_matricula():
    clave = calcular_clave_linea(None, None, "PARTIDA ALZADA", 3)
    assert clave != ""
    assert calcular_clave_linea(None, None, "PARTIDA ALZADA", 3) == clave
    assert calcular_clave_linea(None, None, "PARTIDA ALZADA", 4) != clave


def test_guardar_lineas_catalogo_primera_vez_crea(db_session):
    lote = _lote(db_session)
    lineas = [
        construir_linea_catalogo(
            ["P-001", "Guante", "24,00"],
            {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2},
            pagina=11,
            documento_origen_id=None,
            baja_lote=None,
            orden_aparicion=0,
        )
    ]

    resultado = guardar_lineas_catalogo(db_session, lote.id, lineas)

    assert resultado.creadas == 1
    assert resultado.actualizadas == 0
    assert db_session.query(LineaCatalogo).count() == 1


def test_guardar_lineas_catalogo_reprocesar_no_duplica(db_session):
    # CLAUDE.md sección 9.9: idempotencia. Reprocesar el mismo expediente
    # actualiza sus filas, nunca las duplica.
    lote = _lote(db_session)
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    fila = ["P-001", "Guante", "24,00"]
    lineas = [construir_linea_catalogo(fila, mapeo, 11, None, None, 0)]

    guardar_lineas_catalogo(db_session, lote.id, lineas)
    resultado = guardar_lineas_catalogo(db_session, lote.id, lineas)

    assert resultado.creadas == 0
    assert resultado.actualizadas == 1
    assert db_session.query(LineaCatalogo).count() == 1


def test_guardar_lineas_catalogo_no_borra_campo_con_valor_nulo_entrante(db_session):
    # Caso real del fixture 6.24/28510.0088: el mismo código de precio
    # aparece en dos tablas del documento, una con cantidad y otra sin ella
    # (una tabla de "criterios técnicos" que repite código, descripción y
    # precio pero no trae cantidad). La segunda pasada no debe borrar la
    # cantidad que sí trajo la primera.
    lote = _lote(db_session)
    mapeo_con_cantidad = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": 2, "precio_unitario": 3}
    mapeo_sin_cantidad = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}

    primera = construir_linea_catalogo(["P-003", "Traviesa", "80000", "1,95"], mapeo_con_cantidad, 18, None, None, 0)
    segunda = construir_linea_catalogo(["P-003", "Traviesa", "1,95"], mapeo_sin_cantidad, 23, None, None, 0)

    guardar_lineas_catalogo(db_session, lote.id, [primera])
    guardar_lineas_catalogo(db_session, lote.id, [segunda])

    linea = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id, clave_linea="P-003").one()
    assert linea.cantidad == Decimal("80000")
    assert linea.pagina == 23  # la traza sí se actualiza a la pasada más reciente


def test_combinar_por_clave_funde_repeticiones_dentro_del_mismo_lote_de_lineas():
    # Bug real (sesión de validación del mapeo de cabecera contra la API):
    # SessionLocal (app/db.py) usa autoflush=False, así que un mismo
    # clave_linea repetido más de una vez dentro de un único `lineas` (el
    # mismo cuadro de precios reaparece en el documento — CLAUDE.md sección
    # 3) llegaba sin fundir hasta el INSERT final y violaba la constraint
    # UNIQUE de golpe, tirando el trabajo entero. `_combinar_por_clave` debe
    # resolverlo en Python, sin depender de autoflush.
    primera = {"clave_linea": "P-003", "cantidad": Decimal("80000"), "precio_unitario": None, "pagina": 18}
    segunda = {"clave_linea": "P-003", "cantidad": None, "precio_unitario": Decimal("1.95"), "pagina": 23}
    otra = {"clave_linea": "P-004", "cantidad": Decimal("10"), "precio_unitario": Decimal("5.00"), "pagina": 18}

    combinadas = _combinar_por_clave([primera, segunda, otra])

    assert len(combinadas) == 2
    p003 = next(c for c in combinadas if c["clave_linea"] == "P-003")
    assert p003["cantidad"] == Decimal("80000")  # el None de `segunda` no borra el valor de `primera`
    assert p003["precio_unitario"] == Decimal("1.95")
    assert p003["pagina"] == 23  # el campo si presente en ambas se queda con el más reciente


def test_guardar_lineas_catalogo_funde_clave_repetida_en_un_solo_lote(db_session):
    lote = _lote(db_session)
    mapeo_con_cantidad = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": 2, "precio_unitario": 3}
    mapeo_sin_cantidad = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}
    primera = construir_linea_catalogo(["P-003", "Traviesa", "80000", "1,95"], mapeo_con_cantidad, 18, None, None, 0)
    segunda = construir_linea_catalogo(["P-003", "Traviesa", "1,95"], mapeo_sin_cantidad, 23, None, None, 1)

    resultado = guardar_lineas_catalogo(db_session, lote.id, [primera, segunda])

    assert resultado.creadas == 1
    assert resultado.actualizadas == 0
    linea = db_session.query(LineaCatalogo).filter_by(lote_id=lote.id, clave_linea="P-003").one()
    assert linea.cantidad == Decimal("80000")


def test_construir_lineas_desde_tabla_usa_orden_inicial():
    tabla = TablaExtraida(
        cabecera=["Código", "Descripción", "Precio"],
        filas=[["P-001", "A", "1,00"], ["P-002", "B", "2,00"]],
        pagina=1,
    )
    mapeo = {"codigo_precio": 0, "matricula": None, "descripcion": 1, "unidad_medida": None, "cantidad": None, "precio_unitario": 2}

    lineas = construir_lineas_desde_tabla(tabla, mapeo, None, None, orden_inicial=5)

    assert [l["orden_aparicion"] for l in lineas] == [5, 6]
